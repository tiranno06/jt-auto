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
