"""Tests : robots à part (choix de l'auteur du 22 novembre 2026) : réserve de sons, éclaireur, contrôleur du soir, et vidéo refaite
qui remplace l'ancienne dans la liste. Lancer tous les tests : python -m unittest discover -s tests -v"""
from commun import *  # noqa: F401,F403
RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestRobots(unittest.TestCase):
    def setUp(self): sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))

    def test_video_refaite_remplace_l_ancienne(self):
        import deuxieme_chance as DC, publication_auto as P
        anc = {"fichier": "a.mp4", "confiance": 60, "publie": None}
        nouv = {"fichier": "b.mp4", "confiance": 80}
        self.assertEqual(DC.remplacement(anc, nouv, "remarque"), "a.mp4"); self.assertEqual(nouv["remplace"], "a.mp4")
        moins = {"fichier": "c.mp4", "confiance": 40}                          # compte rendu moins sûr : la nouvelle est retirée
        self.assertEqual(DC.remplacement(anc, moins, "compte_rendu"), "c.mp4"); self.assertNotIn("remplace", moins)
        n2 = {"fichier": "d.mp4", "confiance": 10}                             # demandé par l'auteur : remplace même moins sûre
        self.assertEqual(DC.remplacement(anc, n2, "qui"), "a.mp4")
        pub = {"fichier": "a.mp4", "publie": True}                             # déjà sur TikTok : les deux restent
        self.assertEqual(DC.remplacement(pub, {"fichier": "e.mp4"}, "remarque"), "")
        with mock.patch.dict(os.environ, {"PUBLI_FILE": "a.mp4"}):            # cochée « À publier » : remplacée quand même (place gardée)
            self.assertEqual(DC.remplacement(anc, {"fichier": "f.mp4", "confiance": 90}, "compte_rendu"), "a.mp4")
        hist = [{"fichier": "x.mp4", "publie": None}, {"fichier": "b.mp4", "remplace": "a.mp4", "publie": None},
                {"fichier": "c.mp4", "remplace": "b.mp4", "publie": None}]   # refaite deux fois : a -> b -> c
        self.assertEqual(P.remplacant("a.mp4", hist), "c.mp4")
        self.assertEqual(P.file_attente("a.mp4\nx.mp4\nc.mp4", hist), ["c.mp4", "x.mp4"])   # même place, pas de doublon
        src = open(os.path.join(RACINE, "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn("const remplacant=", src); self.assertIn("map(x=>remplacant(x.trim()))", src)

    def test_reserve_de_sons(self):
        import pre_ecoute as PE
        with mock.patch.dict(os.environ, {"RESERVE_SONS": "", "STOCK_SONS": ""}): self.assertEqual(PE.stock_voulu(), 6)
        with mock.patch.dict(os.environ, {"RESERVE_SONS": "3", "STOCK_SONS": ""}): self.assertEqual(PE.stock_voulu(), 3)
        with mock.patch.dict(os.environ, {"RESERVE_SONS": "40"}): self.assertEqual(PE.stock_voulu(), 10)
        with mock.patch.dict(os.environ, {"PRE_ECOUTE": "1", "RESERVE_SONS": "6"}), mock.patch.object(PE, "stock", return_value=[{}, {}]):
            self.assertEqual(PE.manque(), 4)
        g = open(os.path.join(RACINE, ".github", "workflows", "garde.yml"), encoding="utf-8").read()
        self.assertIn("% 2 ))", g); self.assertIn("eclaireur.yml", g); self.assertIn("controleur.yml", g)
        w = open(os.path.join(RACINE, ".github", "workflows", "pre_ecoute.yml"), encoding="utf-8").read()
        self.assertIn("needs.reserve.outputs.manque != '0'", w)

    def test_eclaireur(self):
        import profils_tiktok as PT, time as T
        sons = [{"url": f"https://www.tiktok.com/@{p}/video/{i}", "id": str(i), "profil": p, "potentiel": 50 + i}
                for i, p in enumerate(["aa", "aa", "bb", "bb", "cc", "zz"])]
        f = os.path.join(tempfile.mkdtemp(), "c.json")
        json.dump({"date": int(T.time()), "sons": sons}, open(f, "w"))
        with mock.patch.object(PT, "CANDIDATS", f), mock.patch.dict(os.environ, {"PROFILS_TIKTOK": "aa\nbb\ncc", "ECLAIREUR": "1", "PROFILS_INTERDITS": ""}), \
                mock.patch.object(PT, "videos", side_effect=AssertionError("pas de lecture en direct")), \
                mock.patch.object(PT, "poids_profils", return_value={"aa": 1, "bb": 1, "cc": 1}):
            out = PT.choisir([{"sources": ["https://www.tiktok.com/@aa/video/0"]}], journal=lambda m: None, graine=1, essais=4)
        self.assertTrue(out); self.assertNotIn("https://www.tiktok.com/@aa/video/0", out)          # déjà utilisé : écarté
        self.assertFalse(any("@zz/" in u for u in out))                                               # profil plus suivi : écarté
        json.dump({"date": int(T.time()) - 9 * 3600, "sons": sons}, open(f, "w"))                   # trop vieux : lecture en direct
        with mock.patch.object(PT, "CANDIDATS", f): self.assertIsNone(PT.candidats_frais())

    def test_controleur_du_soir(self):
        import controleur_soir as C
        hist = [{"fichier": "2026-11-22_10h00_emission.mp4", "filiere": "tiktok", "publie": None},
                {"fichier": "2026-11-22_11h00_emission.mp4", "filiere": "tiktok", "publie": True},
                {"fichier": "2026-11-22_12h00_emission.mp4", "filiere": "tiktok", "essai": True},
                {"fichier": "2026-11-21_22h00_emission.mp4", "filiere": "tiktok", "publie": None},
                {"fichier": "2026-11-20_10h00_emission.mp4", "filiere": "tiktok", "publie": None},
                {"fichier": "2026-11-22_13h00_emission.mp4", "filiere": "tiktok", "controle_soir": {"date": "x"}}]
        hist.append({"fichier": "2026-11-21_12h00_emission.mp4", "filiere": "tiktok", "controle_soir": {"version": C.VERSION}})
        # toutes les non publiées, les plus récentes d'abord ; revues quand la version des contrôles change (22 novembre)
        self.assertEqual([h["fichier"] for h in C.candidats(hist, "2026-11-22")],
                         ["2026-11-22_13h00_emission.mp4", "2026-11-22_10h00_emission.mp4", "2026-11-21_22h00_emission.mp4",
                          "2026-11-20_10h00_emission.mp4"])
        D = json.load(open(os.path.join(RACINE, "tests", "banc_voix", "pire_date.json"), encoding="utf-8"))
        sk = {"repliques": D["repliques_robot"], "doublage": {"x": 1}, "decoupage": [{"repliques": list(range(len(D["repliques_robot"])))}],
              "studio": {"personnages": {"presentateur": {"genre_vu": "h"}, "invite": {"genre_vu": "f"}}}}   # (vu par Gemini, comme dans la vraie vidéo)
        pts = C.controler(os.path.join(RACINE, "tests", "banc_voix", "pire_date.opus"), sk)     # « Pire date » : voix mal rangées trouvées
        self.assertGreaterEqual(len(pts), 3); self.assertTrue(any("bulle" in p["quoi"] for p in pts))
        w = open(os.path.join(RACINE, ".github", "workflows", "controleur.yml"), encoding="utf-8").read()
        self.assertIn("|compte_rendu|soir", w)                                # jamais refaite en boucle (refait_par_soir)


class TestAudit22Novembre(unittest.TestCase):
    def setUp(self): sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))

    def test_attribution_image(self):
        import verif_finale as V
        reps = [{"p": "presentateur" if k % 2 == 0 else "invite", "_deb": 2.0 * k, "_fin": 2.0 * k + 1.8, "t": "x"} for k in range(10)]
        vue_ok = [[2.0 * k + 0.1, 2.0 * k + 1.5, (k + 1) % 2, 0.8] for k in range(10)]   # numéros inversés : même découpage = accord
        self.assertEqual(V.attribution_image({"repliques": reps, "doublage": {"vue": vue_ok}}), [])
        vue_ko = [list(v) for v in vue_ok]
        for k in (1, 4, 7): vue_ko[k][2] = 1 - vue_ko[k][2]                 # 3 phrases sur 10 contredites par l'image
        pts = V.attribution_image({"repliques": reps, "doublage": {"vue": vue_ko}})
        self.assertEqual(len(pts), 1); self.assertEqual(pts[0]["poste"], "attribution"); self.assertEqual(pts[0]["repliques_douteuses"], [1, 4, 7])
        for k in (1, 4, 7): reps[k]["_hauteur_ok"] = True                   # confirmées par la hauteur de la voix : plus contestées
        self.assertEqual(V.attribution_image({"repliques": reps, "doublage": {"vue": vue_ko}}), [])

    def test_conditions_des_workflows(self):
        # GitHub : une variable jamais créée vaut null, et null != '0' est FAUX (les deux deviennent 0) : le robot ne tournait jamais
        import glob, re
        for f in glob.glob(os.path.join(RACINE, ".github", "workflows", "*.yml")):
            for k, l in enumerate(open(f, encoding="utf-8"), 1):
                for m in re.finditer(r"(\(?)vars\.([A-Z_0-9]+)(\s*\|\|[^)]*\))?\s*(!=|==)\s*'(0|)'", l):
                    self.assertTrue(m.group(3), f"{os.path.basename(f)}:{k} : vars.{m.group(2)} comparé à '{m.group(5)}' sans valeur par défaut")

    def test_alerte_reessaie_un_appareil_note_disparu(self):
        import alerte
        f = os.path.join(tempfile.mkdtemp(), "morts.json")
        with mock.patch.object(alerte, "MORTS", f), mock.patch.object(alerte, "noter", lambda *a: None), \
                mock.patch.object(alerte, "envoyer", lambda *a, **k: None), \
                mock.patch.dict(os.environ, {"VAPID_PRIVEE": "x", "VAPID_PUBLIQUE": "y", "PUSH_ABONNEMENTS": json.dumps([{"endpoint": "https://e/1"}])}):
            json.dump([alerte.empreinte("https://e/1")], open(f, "w"))
            self.assertEqual(alerte.alerter("t", "x"), 1)                    # essayé quand même
            self.assertEqual(alerte.morts(), set())                          # et retiré des disparus

    def test_reprise_point_de_sauvegarde_sans_chaine(self):
        src = open(os.path.join(RACINE, "moteur", "principal.py"), encoding="utf-8").read()
        self.assertIn('if CHAINE_ORIG is not None: os.environ["CHAINE"] = CHAINE_ORIG', src)


class TestListe23Novembre(unittest.TestCase):
    """Choix de l'auteur du 23 novembre : 5, 8, 10, 11, 13, 14, 16."""
    def setUp(self): sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))

    def test_16_veille_des_robots(self):
        import veille_robots as V, datetime as dt
        m = dt.datetime(2026, 11, 23, 12, tzinfo=dt.timezone.utc)
        self.assertIsNone(V.etat_robot({"updated_at": "2026-11-22T21:00:00Z"}, [], m, 27))          # robot tout neuf : on attend
        self.assertIn("jamais lancé", V.etat_robot({"updated_at": "2026-11-20T21:00:00Z"}, [], m, 27))
        echec = {"status": "completed", "conclusion": "failure", "created_at": "2026-11-23T11:00:00Z"}
        self.assertIn("échoué", V.etat_robot({}, [echec, echec], m, 6))
        envoyes = []
        with mock.patch.object(V, "ETAT", os.path.join(tempfile.mkdtemp(), "v.json")), mock.patch.dict(os.environ, {"CONTROLEUR_SOIR": "0"}):
            lire = lambda c: {"updated_at": "2026-11-01T00:00:00Z"} if c.endswith(".yml") else {"workflow_runs": []}
            out = V.verifier(m, lire, lambda t, msg: envoyes.append(msg))
            self.assertEqual(len(out), 3); self.assertEqual(len(envoyes), 1)        # contrôleur coupé : pas surveillé
            self.assertEqual(V.verifier(m, lire, lambda t, msg: envoyes.append(msg)), [])   # une fois par jour

    def test_11_confiance_honnete(self):
        import verif_finale as VF
        self.assertEqual(VF.confiance([], [], None), 100)
        self.assertEqual(VF.confiance([], [], None, ["attribution"]), 90)
        self.assertEqual(VF.confiance([], [], None, ["a", "b", "c"]), 82)

    def test_5_createurs_d_origine(self):
        import decouverte as D, profils_tiktok as P, time as T
        self.assertTrue(D.francais(["Déjà sur doctolib", "J’ai posé aucune question", "Ennemi en commun"]))
        self.assertFalse(D.francais(["luteal phase final girl every month", "Dad might be the NBL player"]))
        vs = [{"duree": 30, "vues": 20000, "date": T.time() - 86400, "titre": "Quand tu es en retard"} for _ in range(9)]
        self.assertTrue(D.origine_ok("x", vs)); self.assertIsNone(D.origine_ok("x", vs[:5]))
        f = os.path.join(tempfile.mkdtemp(), "createurs_origine.json")
        os.makedirs(os.path.join(os.path.dirname(f), "episodes"), exist_ok=True)
        json.dump({"profils": [{"profil": "aguerin30"}, {"profil": "zequoiza"}]}, open(os.path.join(os.path.dirname(f), "episodes", "createurs_origine.json"), "w"))
        with mock.patch.object(P, "RACINE", os.path.dirname(f)), \
                mock.patch.dict(os.environ, {"PROFILS_TIKTOK": "@vignianimation", "PROFILS_ORIGINE_AJOUTES": "zequoiza", "PROFILS_INTERDITS": "", "ORIGINES": "1"}):
            self.assertEqual(P.liste(), ["vignianimation", "aguerin30"])     # zequoiza : déjà traité par le site (ajouté ou retiré)
            self.assertEqual(P.liste(sans_origines=True), ["vignianimation"])
        src = open(os.path.join(RACINE, "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn("async function ajouterOrigines(v)", src); self.assertIn('ecrireVar("PROFILS_ORIGINE_AJOUTES"', src)

    def test_8_rejouer(self):
        import rejouer as RJ, publication_auto as P, datetime as dt
        hist = [{"fichier": f"v{k}.mp4", "filiere": "tiktok", "publie": True, "vues": 300 + k, "date": "2026-09-01"} for k in range(8)]
        hist.append({"fichier": "top.mp4", "filiere": "tiktok", "publie": True, "vues": 900, "date": "2026-09-10"})
        hist.append({"fichier": "recent.mp4", "filiere": "tiktok", "publie": True, "vues": 2000, "date": "2026-11-20"})   # trop récente
        self.assertEqual(RJ.choisir(hist, dt.date(2026, 11, 23))["fichier"], "top.mp4")
        hist[-2]["rejouee"] = "2026-11-23"; self.assertIsNone(RJ.choisir(hist, dt.date(2026, 11, 23)))
        h2 = [{"fichier": "a.mp4", "publie": None}, {"fichier": "n.mp4", "publie": None, "publier_auto": True}]
        self.assertEqual(P.file_attente("a.mp4", h2), ["a.mp4", "n.mp4"])     # la nouvelle version entre seule dans la file
        with mock.patch.dict(os.environ, {"PUBLI_NON": "n.mp4"}): self.assertEqual(P.file_attente("a.mp4", h2), ["a.mp4"])

    def test_10_banc_ajout(self):
        import banc_voix as B
        d = tempfile.mkdtemp()
        with mock.patch.object(B, "DOSSIERS", [B.DOSSIER, d]):
            D = json.load(open(os.path.join(RACINE, "tests", "banc_voix", "pire_date.json"), encoding="utf-8"))
            vraies = [{"p": "presentateur" if q == "H" else "invite", "_deb": a, "_fin": b, "t": t} for a, b, q, t in D["verite"]]
            r = B.ajouter("essai", "Essai", vraies, vraies, os.path.join(RACINE, "tests", "banc_voix", "pire_date.opus"),
                          {"presentateur": "h", "invite": "f"}, journal=lambda m: None)
            self.assertEqual(r["avant"], 1.0); self.assertGreaterEqual(r["apres"], 0.97)
            self.assertGreaterEqual(json.load(open(os.path.join(d, "essai.json")))["attendu"], 0.95)

    def test_13_bouche_muette(self):
        import verif_finale as VF
        fps = 10; n = 60; fr = [np.zeros((VF.H_, VF.L), np.float32) for _ in range(n)]
        R = {"ph": [{"scene": 0, "p": "presentateur", "deb": 0.0, "fin": 3.0, "texte": "a"}, {"scene": 0, "p": "invite", "deb": 3.0, "fin": 6.0, "texte": "b"}],
             "xs": {0: {"presentateur": 260, "invite": 820}}, "tetes_y": {0: 900}}
        k = VF.L / 1080; y = int((900 + 50) * k)
        def bouge(x, i): fr[i][y:y + 5, int((x - 20) * k):int((x + 20) * k)] = 100 * (i % 2)
        for i in range(n):
            bouge(260 if i < 30 else 820, i)                                   # chacun bouge la bouche pendant SA réplique : juste
        self.assertEqual(VF.bouches_muettes(R, fr, fps), [])
        for i in range(30, n): bouge(260, i)                                   # le présentateur bouge aussi la bouche en écoutant
        pts = VF.bouches_muettes(R, fr, fps)
        self.assertEqual(len(pts), 1); self.assertEqual(pts[0]["poste"], "bouches")

    def test_14_jeu_du_dessin_anime(self):
        import jeu_dessin as J
        reps = [{"p": "presentateur" if k % 2 == 0 else "invite", "_deb": 2.0 * k, "_fin": 2.0 * k + 1.5, "t": "x"} for k in range(6)]
        ch = J.choisir_repliques(reps)
        rep = {"images": [{"i": k, "parle": "gauche" if k % 2 == 0 else "droite", "gauche": {"emotion": "colere", "force": 3},
                           "droite": {"emotion": "surprise", "force": 2}} for k in range(6)]}
        out = J.interpreter(rep, ch)
        self.assertEqual(out["presentateur"][0][2], "colere"); self.assertEqual(out["invite"][0][2], "choc")
        p = {"emo": "neutre"}; J.appliquer(p, out, "invite", 0.5, False); self.assertEqual(p["emo"], "choc")
        p = {"emo": "rire"}; J.appliquer(p, out, "invite", 0.5, False); self.assertEqual(p["emo"], "rire")   # jamais par-dessus un jeu fort
        self.assertEqual(J.interpreter({"images": [{"i": 0, "parle": "?"}]}, ch), {})           # côtés pas nets : rien


class TestPannes23Novembre(unittest.TestCase):
    def setUp(self): sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))

    def test_modele_gemini_mort_retenu_7_jours(self):
        import reseau, datetime as dt
        f = os.path.join(tempfile.mkdtemp(), "m.json")
        with mock.patch.object(reseau, "MORTS_FICHIER", f):
            reseau.GEMINI_MORTS.discard("m_mort"); reseau.gemini_mort("m_mort", "HTTP Error 404: Not Found")
            self.assertIn("m_mort", reseau._morts_lus())                        # gardé pour les autres machines
            json.dump({"vieux": (dt.date.today() - dt.timedelta(days=9)).isoformat()}, open(f, "w"))
            self.assertNotIn("vieux", reseau._morts_lus())                     # au bout de 7 jours : réessayé
        reseau.GEMINI_MORTS.discard("m_mort")
        import fusion
        out = json.loads(fusion._union_dates(b'{"a": "2026-11-20"}', b'{"a": "2026-11-23", "b": "2026-11-22"}', b"{}"))
        self.assertEqual(out, {"a": "2026-11-23", "b": "2026-11-22"})

    def test_bouton_abonne_toi(self):
        import marque
        with mock.patch.dict(os.environ, {"ABONNE_HAUT": ""}): a = marque.filigrane(52)
        with mock.patch.dict(os.environ, {"ABONNE_HAUT": "0"}): b = marque.filigrane(52)
        self.assertGreater(a.shape[0], b.shape[0])                              # bouton sous le nom (et « 0 » l'enlève)
        self.assertGreater(a[-5:, :, 3].max(), 0)                               # rien de coupé en bas
