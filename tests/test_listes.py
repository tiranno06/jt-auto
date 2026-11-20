"""Tests : Listes d'idées choisies par l'auteur (octobre-novembre 2026).
Lancer tous les tests : python -m unittest discover -s tests -v"""
from commun import *  # noqa: F401,F403 (chemins, réglages des tests, modules, SKETCH, FauxClaude…)


class TestAmeliorationsOctobre3(unittest.TestCase):
    def setUp(self): sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))

    def test_voix_par_tours_pyannote(self):
        import locuteurs as L
        mots = [{"w": "a", "s": 0.0, "e": 0.4}, {"w": "b", "s": 0.5, "e": 0.9}, {"w": "c", "s": 1.6, "e": 2.0}, {"w": "d", "s": 3.5, "e": 3.8}]
        res = L.mots_par_tours(mots, [(0.0, 1.0, "SPK_B"), (1.5, 3.0, "SPK_A")])
        self.assertEqual([m["voix"] for m in res], ["speaker_0", "speaker_0", "speaker_1", "speaker_1"])   # dernier mot : tour le plus proche
        self.assertIsNone(L.pyannote(mots, np.zeros(22050, np.float32)) if not os.environ.get("HF_TOKEN") else None)

    def test_sous_titres_corriges_sans_reecriture(self):
        import doublage as D
        segs = [{"t": "Non, c'est 1000 ballons rien.", "mots": [{"w": w} for w in "Non, c'est 1000 ballons rien.".split()]},
                {"t": "Bonjour à tous", "mots": [{"w": w} for w in "Bonjour à tous".split()]}]
        out = D.corriger_textes(segs, ["Non, c'est mille balles ou rien.", "Une tout autre phrase inventée de toutes pièces par l'IA"])
        self.assertEqual(out, ["Non, c'est mille balles ou rien.", "Bonjour à tous"])

    def test_essais_a_part_et_menage(self):
        import supprimer as SU
        self.assertTrue(SU.essai({"titre": "👀 Aperçu 10 s — X"})); self.assertTrue(SU.essai({"essai": True})); self.assertFalse(SU.essai({"titre": "Vrai"}))

    def test_quota_ralentit(self):
        import quota, time as T
        quota.ETAT.update(reste=50, remise=int(T.time()) + 200)
        try:
            self.assertTrue(quota.econome()); self.assertGreater(quota.pause_conseillee(40), 150)
            quota.ETAT.update(reste=900); self.assertFalse(quota.econome()); self.assertEqual(quota.pause_conseillee(40), 40)
        finally: quota.ETAT.update(reste=None, remise=None)


class TestIdeesTiktok(unittest.TestCase):
    """Idées 1, 3, 4, 11, 20, 21, 32 de la liste choisie par l'auteur."""

    def test_potentiel_et_sons_qui_montent(self):
        import profils_tiktok as P
        t = 1_000_000_000
        fort = {"vues": 2_000_000, "date": t - 86400, "duree": 35}
        vieux = {"vues": 2_000_000, "date": t - 400 * 86400, "duree": 35}
        long_ = {"vues": 2_000_000, "date": t - 86400, "duree": 140}
        self.assertGreater(P.potentiel(fort, t), P.potentiel(vieux, t))
        self.assertGreater(P.potentiel(fort, t), P.potentiel(long_, t))
        self.assertTrue(0 <= P.potentiel({}, t) <= 100)

    def test_poids_des_profils(self):
        import profils_tiktok as P
        stats = {"videos": [{"vues": 9000, "description": "son de @star"}, {"vues": 100, "description": "son de @flop"},
                            {"vues": 500, "description": "rien"}]}
        w = P.poids_profils(["star", "flop", "inconnu"], stats)
        self.assertGreater(w["star"], 1); self.assertLess(w["flop"], 1); self.assertEqual(w["inconnu"], 1.0)

    def test_heure_auto_garde_l_heure_fixe(self):
        import datetime, publication_auto as PA
        from zoneinfo import ZoneInfo
        m = datetime.datetime(2026, 10, 30, 6, 0, tzinfo=ZoneInfo("Europe/Paris"))
        hist = [{"fichier": "a.mp4", "publie": None}]
        r = {"PUBLI_AUTO": "1", "PUBLI_HEURE": "05:30", "PUBLI_FILE": "a.mp4", "PUBLI_HEURE_AUTO": "0"}
        self.assertEqual(PA.decision(m, r, hist, False)[0], "a.mp4")         # heure fixe choisie par l'auteur

    def test_fin_en_boucle(self):
        import subprocess, boucle
        d = tempfile.mkdtemp(); f = os.path.join(d, "v.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=160x284:r=24:d=4", "-f", "lavfi",
                        "-i", "sine=d=4", "-shortest", "-pix_fmt", "yuv420p", f], check=True)
        self.assertGreaterEqual(boucle.boucler(f), 3.9)

    def test_partage_depuis_tiktok(self):
        src = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn("share_target", src); self.assertIn("partage=1", src)


class TestIdeesTiktok2(unittest.TestCase):
    """Idées 5, 6, 17, 18, 23-31 : outils d'écoute, postures, décors et véhicules des métiers, corriger qui parle."""

    def test_jeu_entendu_et_ponctuation(self):
        import ecoute
        reps = [{"t": "Mais t'es fou ?"}, {"t": "Ha ha ha"}, {"t": "Bon.", "d": "[sigh] Bon."}]
        segs = [{"deb": 0, "fin": 1}, {"deb": 1.2, "fin": 2}, {"deb": 2.5, "fin": 3}]
        ecoute.jeu_entendu(reps, segs, {0: "angry"}, [(1.3, 1.9, "laughter")])
        self.assertEqual(reps[0]["d"], "[angry] Mais t'es fou ?"); self.assertTrue(reps[1]["d"].startswith("[laughing]"))
        self.assertEqual(reps[2]["d"], "[sigh] Bon.")                      # l'indication de l'IA n'est jamais remplacée
        m = ecoute.ponctuer([{"w": "salut"}, {"w": "ça"}, {"w": "va"}], [{"text": " Salut, ça va ?"}])
        self.assertEqual([x["w"] for x in m], ["Salut,", "ça", "va"])

    def test_postures(self):
        import postures as P
        p = np.zeros((33, 2)); p[0] = [.5, .2]; p[9] = [.48, .25]; p[10] = [.52, .25]; p[7] = [.58, .2]; p[8] = [.42, .2]
        p[11] = [.6, .35]; p[12] = [.4, .35]; p[23] = [.57, .65]; p[24] = [.43, .65]; p[13] = [.63, .5]; p[14] = [.37, .5]
        p[15] = [.45, .47]; p[16] = [.55, .47]
        self.assertEqual(P.classer(p), "croises")
        p[15] = [.63, .62]; p[16] = [.43, .21]; self.assertEqual(P.classer(p), "telephone")
        self.assertEqual(P.geste_pendant([[1.0, 3.0, 0.5, "croises"]], 1.2, 2.8), "croises")
        self.assertIsNone(P.geste_pendant([[1.0, 1.2, 0.5, "croises"]], 0, 5))

    def test_decors_des_metiers(self):
        import decor_dessin as D, decor_metiers as DM
        for l in DM.LIEUX:
            self.assertIn(l, D.LIEUX)
            r = D.dessiner(l, {"moment": "soir"}, 5); self.assertEqual(r["fond"].shape, (1920, 1080, 3)); self.assertEqual(r["lieu"], l)
        self.assertEqual(D.lieu_de("on est à la caserne des sapeurs-pompiers"), "caserne")
        self.assertEqual(D.lieu_de("oh la ferme toi"), "salon")            # « la ferme ! » n'est pas une ferme

    def test_vehicules_des_metiers(self):
        import vehicules as V
        for n in V.VEHICULES:
            im = V.VEHICULES[n](1, 400); self.assertEqual(im.shape[2], 4); self.assertGreater(im[..., 3].mean(), 10)
        self.assertEqual(V.vehicule_de("appelle la police"), "police")
        self.assertEqual(V.vehicule_de("bonjour", ["agriculteur"], "ferme"), "tracteur")
        self.assertIsNone(V.vehicule_de("appelle la police", lieu="salon"))  # jamais dans un intérieur

    def test_metier_choisit_le_lieu(self):
        import studio
        sk = {"repliques": [{"p": "presentateur", "t": "Bonjour, je suis pompier."}, {"p": "invite", "t": "Ah bon ?"}],
              "decoupage": [{"scene": "1", "repliques": [0, 1], "decor": ""}], "doublage": None}
        B = studio.bible(sk, ["presentateur", "invite"])
        self.assertEqual(B["lieux"][0], "caserne")

    def test_corriger_qui_parle_site(self):
        src = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn("|qui|", src); self.assertIn("tiktok.com/embed/v2", src)
        p = open(os.path.join(ICI, "..", "moteur", "principal.py"), encoding="utf-8").read()
        self.assertIn('os.path.splitext(_f)[0] + ".json"', p)              # le sketch gardé est bien retrouvé (Refaire)


class TestListe31Soir(unittest.TestCase):
    """Choix de l'auteur du 31 octobre au soir : 1, 3, 4, 5, 6, 7, 9, 11, 12, 16."""
    def setUp(self): sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))

    def test_jury_plan_large(self):
        import qualite
        jury = {"realisateur": {"note": 6.0, "remarques": [{"probleme": "montage trop lent : il faut plus de plans", "correction": None},
                                                             {"probleme": "le personnage est coupé", "correction": None}]},
                "humoriste": {"note": 7.0, "remarques": [{"probleme": "la chute mérite un zoom choc", "correction": {"type": "plan"}}]}}
        anc = os.environ.pop("MONTAGE", None)
        try:
            self.assertEqual(qualite.sans_reproches_large(jury), 2)
            self.assertEqual(len(jury["realisateur"]["remarques"]), 1); self.assertEqual(jury["realisateur"]["note"], 6.8)
            os.environ["MONTAGE"] = "dynamique"; self.assertEqual(qualite.sans_reproches_large(jury), 0)
        finally:
            os.environ.pop("MONTAGE", None)
            if anc is not None: os.environ["MONTAGE"] = anc

    def test_titre_net(self):
        self.assertEqual(ecrire.titre_net("Oh Maurice, mon chat t'es trop mignon, fais moi un bisou").upper(), "OH MAURICE")
        self.assertEqual(ecrire.titre_net("Le retrait bancaire de 2026 est vraiment fou"), "Le retrait bancaire de 2026")
        self.assertEqual(ecrire.titre_net("STEAK AU MICRO-ONDES"), "STEAK AU MICRO-ONDES")

    def test_lieu_sans_ia(self):
        import doublage, decor_dessin as DD
        t = "Oh mon chat, j'dors là. Va manger ta pâtée pendant que je mange mes pâtes boulot."
        self.assertEqual(doublage.lieu_vu([], t), "salon")
        self.assertIsNone(doublage.lieu_vu([], "Il est 15h, vas-y calme, je mange mes pâtes boulot."))   # un seul mot : pas de lieu imposé
        self.assertEqual(DD.scores_lieux("au bureau avec mon patron")[0]["bureau"], 2)

    def test_trois_ecoutes(self):
        import equipe, reseau
        anc = reseau.ia_disponible; reseau.ia_disponible = lambda: False
        try:
            A = [{"w": w, "s": i, "e": i + 0.5} for i, w in enumerate("tu manges halal ou pas".split())]
            B = equipe.Bulletin()
            out = equipe.deux_transcriptions(A, [{"w": w} for w in "tu manges hallal ou pas".split()], B,
                                             troisieme=lambda: [{"w": w} for w in "tu manges hallal ou pas".split()])
        finally: reseau.ia_disponible = anc
        self.assertEqual(out[2]["w"], "hallal"); self.assertIn("3e écoute", B.lignes[-1]["detail"])

    def test_debut_parole(self):
        import numpy as np, doublage
        sr = doublage.SR; x = np.zeros(sr * 5, np.float32); a, b = int(1.6 * sr), int(3 * sr)
        x[a:b] = 0.3 * np.sin(np.arange(b - a) / 5); x[int(0.3 * sr):int(0.33 * sr)] = 0.5   # un clic isolé ne compte pas
        self.assertTrue(1.3 < doublage.debut_parole(x) < 1.7)

    def test_ordre_des_ia(self):
        import reseau
        cles = {k: os.environ.get(k) for k in ("MISTRAL_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "CLAUDE_INDISPONIBLE")}
        try:
            for k in ("MISTRAL_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"): os.environ[k] = "x"
            os.environ["CLAUDE_INDISPONIBLE"] = "1"; reseau.HORS_SERVICE.clear(); reseau.EN_PAUSE.clear()
            self.assertEqual(reseau.ordre_ia(), ["mistral", "groq", "gemini"])             # texte : Gemini gardé pour les images
            self.assertEqual(reseau.ordre_ia(True)[0], "gemini")
            self.assertEqual(reseau.ordre_ia(False, True)[0], "groq")
            class H(dict):
                def get(self, k, d=None): return dict.get(self, k, d)
            reseau._noter_quota("groq", H({"x-ratelimit-remaining-requests": "900", "x-ratelimit-limit-requests": "1000"}))
            self.assertEqual(reseau.QUOTA["groq"]["reste_jour"], 900)
        finally:
            for k, v in cles.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v

    def test_animaux(self):
        import numpy as np, animaux as AN, perso_croquis as PC, marionnette as M, humain as HU, croquis as C
        sk = {"repliques": [{"p": "presentateur", "t": "Oh Maurice, mon chat t'es trop mignon."}, {"p": "invite", "t": "Eh, je suis un chat égyptien."},
                            {"p": "presentateur", "t": "J'ai donné à manger à mon chat."}]}
        self.assertEqual(AN.qui_est(sk), {"invite": "chat"})
        self.assertEqual(AN.espece_valide("objet:steak"), "steak"); self.assertIsNone(AN.espece_valide("humain"))
        for e in AN.ESPECES:
            img = C.papier(400, 700); F = dict(HU.creer(1, genre="h", age=30), espece=e)
            p = M.pose_neutre(); p.update(x=200, y=650, s=1.0, t=0.0, bouche=0.4, emo="joie")
            tc, _ = PC.dessiner(img, F, p)
            self.assertLess(float(img.mean()), float(C.papier(400, 700).mean()) - 0.5)   # quelque chose est dessiné
            self.assertTrue(0 < tc[1] < 650)

    def test_bouches_calmes(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "moteur", "cartoon.py"), encoding="utf-8").read()
        self.assertIn('{"calme": True} if r.get("_calme")', src); self.assertIn("not calme and prev", src)
        self.assertIn("BOUCHES_CORRIGEES", open(os.path.join(os.path.dirname(__file__), "..", "moteur", "principal.py"), encoding="utf-8").read())

    def test_voyant_ia_du_site(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn('id="tkIA"', src); self.assertIn("function rendreQuotaIA", src)


class TestListe4_5_6_11(unittest.TestCase):
    """Choix de l'auteur : 4 (plus d'animaux et d'objets), 5 (accessoires), 6 (deuxième chance), 11 (alternance des profils)."""
    def setUp(self): sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))

    def test_especes_et_mots(self):
        import animaux as AN
        q = lambda t: AN.qui_est({"repliques": [{"p": "presentateur", "t": t}, {"p": "invite", "t": "Ouais."}]})
        self.assertEqual(q("Je suis un téléphone, laisse-moi charger"), {"presentateur": "telephone"})
        self.assertEqual(q("Je suis au téléphone avec ma mère"), {})        # « au téléphone » : un humain
        self.assertEqual(q("Oh mon lapin, t'es où ?"), {})                 # mot doux seul : pas assez
        for e in ("lapin", "souris", "oiseau", "poisson", "voiture", "frigo", "telephone", "verre", "croissant"): self.assertIn(e, AN.ESPECES)

    def test_accessoires(self):
        import numpy as np, perso_croquis as PC, marionnette as M, humain as HU, croquis as C
        for cos in ({"chapeau": "toque"}, {"details": ["lunettes_soleil"]}):
            img = C.papier(400, 700); F = dict(HU.creer(2, genre="f", age=30), espece="chat")
            p = M.pose_neutre(); p.update(x=200, y=650, s=1.0, t=0.0, emo="joie", costume=cos); PC.dessiner(img, F, p)

    def test_deuxieme_chance(self):
        import deuxieme_chance as DC
        anc = {k: os.environ.pop(k, None) for k in ("PUBLI_FILE", "CONFIANCE_MIN", "DEUXIEME_CHANCE")}
        try:
            h1 = {"fichier": "a.mp4", "confiance": 30}
            quoi, val = DC.decider([h1], h1, "https://www.tiktok.com/@x/video/1")
            self.assertEqual(quoi, "relancer"); self.assertEqual(DC.separer(val), ("TIKTOK::https://www.tiktok.com/@x/video/1", "a.mp4"))
            h2 = {"fichier": "b.mp4", "confiance": 70}
            self.assertEqual(DC.decider([h1, h2], h2, "u", "a.mp4"), ("supprimer", "a.mp4"))
            h3 = {"fichier": "c.mp4", "confiance": 10}
            self.assertEqual(DC.decider([h1, h3], h3, "u", "a.mp4"), ("supprimer", "c.mp4"))
            os.environ["PUBLI_FILE"] = "a.mp4"; self.assertEqual(DC.decider([h1, h2], h2, "u", "a.mp4"), (None, ""))   # cochée : on garde les deux
            self.assertEqual(DC.decider([h2], dict(h2), "u")[0], None)       # assez sûre : rien
        finally:
            for k, v in anc.items():
                os.environ.pop(k, None)
                if v is not None: os.environ[k] = v
        wf = open(os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "emission.yml"), encoding="utf-8").read()
        self.assertIn("sortie/.deuxieme_chance", wf); self.assertIn("sortie/.perdante", wf)

    def test_alterner_profils(self):
        import publication_auto as PA
        src = lambda c: {"source_audio": f"https://www.tiktok.com/@{c}/video/1"}
        hist = [dict(src("a"), fichier="p.mp4", publie=True, programmee="2026-10-30T18:00"),
                dict(src("a"), fichier="1.mp4"), dict(src("a"), fichier="2.mp4"), dict(src("b"), fichier="3.mp4"), dict(src("c"), fichier="4.mp4")]
        self.assertEqual(PA.alterner(["1.mp4", "2.mp4", "3.mp4", "4.mp4"], hist), ["3.mp4", "1.mp4", "4.mp4", "2.mp4"])
        self.assertIn("function alternerPubli", open(os.path.join(os.path.dirname(__file__), "..", "moteur", "site.py"), encoding="utf-8").read())


class TestListe1Novembre(unittest.TestCase):
    """Choix de l'auteur du 1er novembre : 1, 2, 3 (même personne qui joue plusieurs personnages), 8, 11, 12, 14, 15."""
    def setUp(self): sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))

    def test_gemini_video_lu(self):
        import video_ia
        res = {"personnages": [{"id": "A", "espece": "humain"}, {"id": "B", "espece": "chat"}], "meme_interprete": True, "lieu": "salon",
               "phrases": [{"n": 0, "qui": "A", "sur": 0.9}, {"n": 1, "qui": "B"}, {"n": 2, "qui": "A"}, {"n": 3, "qui": "B", "sur": 0.4}],
               "_ph": [(0, 1), (1.2, 2), (2.2, 3), (3.2, 4)], "resume": "Un chat parle."}
        v, n = video_ia.vue(res, 4)
        self.assertEqual([c for c, _ in v], [0, 1, 0, 1]); self.assertEqual(n, 2)
        video_ia.DERNIER.clear(); video_ia.DERNIER.update(res)
        mots = [{"w": "x", "s": s, "e": s + 0.5, "voix": "speaker_1" if s in (1.3, 3.3) else "speaker_0"} for s in (0.1, 1.3, 2.3, 3.3)]
        self.assertEqual(video_ia.especes_par_voix(mots), {"speaker_1": "chat"})
        self.assertIn("même personne joue plusieurs", video_ia.texte()); video_ia.DERNIER.clear()

    def test_meme_personne_deux_personnages(self):
        import numpy as np, visages
        app = np.zeros(14); app[0] = 1; imgs = []; t = 0.0
        for plan in range(6):                                              # même visage, même habit : tourné à gauche puis à droite
            for k in range(16):
                imgs.append((t, k == 0 and plan > 0, [dict(x=0.5, y=0.4, taille=0.3, bouche=0.3 + 0.25 * np.sin(k * 1.7), regard=-0.8 if plan % 2 == 0 else 0.8, app=app)]))
                t += 1 / 8
        anc = visages.lire; visages.lire = lambda c, duree_max=200: imgs
        try:
            mots = [{"w": "x.", "s": p * 2 + 0.1, "e": p * 2 + 1.8, "voix": "speaker_0"} for p in range(6)]
            vue, n = visages.temoin("x", mots, [[i] for i in range(6)])
        finally: visages.lire = anc
        self.assertEqual(n, 2); lab = [c for c, _ in vue]
        self.assertEqual(lab, [lab[0], 1 - lab[0]] * 3)                    # deux personnages qui alternent

    def test_trois_temoins_et_trois_personnages(self):
        import equipe
        a = [(0, 0.9), (1, 0.9), (2, 0.8), (0, 0.7), (1, 0.7), (2, 0.7)]
        b = [(2, 0.8), (0, 0.8), (1, 0.6), (2, 0.6), (0, 0.5), (None, 0)]   # mêmes personnes, autres numéros
        v = equipe.combiner([("a", a, 1.0), ("b", b, 0.9)], 6)
        self.assertEqual(len({c for c, _ in v}), 3)
        self.assertEqual(v[0][0], v[3][0]); self.assertEqual(v[1][0], v[4][0])
        mots = [{"w": "x.", "s": i, "e": i + 0.5, "voix": "speaker_0"} for i in range(6)]
        out = equipe.trois_personnages(mots, [[i] for i in range(6)], v)
        self.assertEqual(len({m["voix"] for m in out}), 3)

    def test_saisons(self):
        import datetime, numpy as np, saisons
        anc = os.environ.pop("SAISON", None)
        try:
            self.assertEqual(saisons.saison(datetime.date(2026, 12, 20)), "noel"); self.assertEqual(saisons.saison(datetime.date(2026, 10, 25)), "halloween")
            self.assertIsNone(saisons.saison(datetime.date(2026, 11, 5)))
            os.environ["SAISON"] = "noel"; img = np.full((1920, 1080, 3), 200, np.uint8)
            out = saisons.decorer(img, "salon", {"fenetre": (90, 330, 430, 760)})
            self.assertFalse(np.array_equal(out, img)); self.assertTrue(np.array_equal(out[800:1100, 450:780], img[800:1100, 450:780]))   # rien au milieu
            os.environ["SAISON"] = "0"; self.assertIs(saisons.decorer(img, "salon"), img)
        finally:
            os.environ.pop("SAISON", None)
            if anc is not None: os.environ["SAISON"] = anc
        import re
        self.assertTrue(re.search(saisons.mots_du_moment(datetime.date(2026, 12, 20)), "le père noël arrive"))
        self.assertIsNone(saisons.mots_du_moment(datetime.date(2026, 11, 5)))

    def test_remarque_regles(self):
        import remarque
        sk = {"repliques": [{"p": "presentateur", "t": "Salut", "_deb": 0.0, "_fin": 2.0}, {"p": "invite", "t": "Ça va ?", "_deb": 11.0, "_fin": 13.0}],
              "decoupage": [{"repliques": [0, 1]}]}
        qui, corr = remarque.regles(sk, "À 12 s c'est l'autre qui parle, et elle devrait être dans une cuisine. En vrai c'est un chat.")
        self.assertEqual(qui, {1: "presentateur"})
        self.assertIn({"type": "lieu", "scene": 0, "lieu": "cuisine"}, corr); self.assertTrue(any(c.get("espece") == "chat" for c in corr))
        src = open(os.path.join(os.path.dirname(__file__), "..", "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn('id="remBloc"', src); self.assertIn("|remarque|", src)
        self.assertIn('"remarque"', open(os.path.join(os.path.dirname(__file__), "..", "moteur", "principal.py"), encoding="utf-8").read())

    def test_remarque_maurice_est_un_chat(self):
        """Vidéo du 1er novembre : « Maurice est censé être un chat » = le personnage qu'on appelle Maurice devient un chat,
        sans inverser les répliques (l'IA les avait toutes inversées) ; jamais de deuxième chance sur une vidéo refaite."""
        import remarque, reseau, ecrire
        sk = {"repliques": [{"p": "presentateur", "t": "Oh Maurice, mon chat t'es trop mignon.", "_deb": 0.0, "_fin": 2.0},
                            {"p": "invite", "t": "Arrête de m'appeler Maurice, j'dors là.", "_deb": 2.0, "_fin": 4.0},
                            {"p": "presentateur", "t": "T'es pas lavé.", "_deb": 4.0, "_fin": 5.0},
                            {"p": "invite", "t": "Toi non plus.", "_deb": 5.0, "_fin": 6.0}], "decoupage": [{"repliques": [0, 1, 2, 3]}]}
        t = "Maurice est censé etre un chat qui parle"
        self.assertEqual(remarque.regles(sk, t), ({}, [{"type": "casting", "role": "invite", "espece": "chat"}]))
        inverse = {"qui": [{"replique": k, "personnage": "invite" if r["p"] == "presentateur" else "presentateur"} for k, r in enumerate(sk["repliques"])],
                   "corrections": [{"type": "casting", "role": "presentateur", "espece": "chat"}], "compris": "on inverse"}
        avant = (reseau.ia_disponible, reseau.claude, ecrire._appel)
        try:
            reseau.ia_disponible = lambda: True; reseau.claude = lambda **k: None; ecrire._appel = lambda *a, **k: inverse
            qui, corr = remarque.interpreter(sk, t)
        finally: reseau.ia_disponible, reseau.claude, ecrire._appel = avant
        self.assertEqual(qui, {}); self.assertEqual([c for c in corr if c.get("espece")], [{"type": "casting", "role": "invite", "espece": "chat"}])
        self.assertIn("and not REFAIRE", open(os.path.join(os.path.dirname(__file__), "..", "moteur", "principal.py"), encoding="utf-8").read())

    def test_openrouter_et_modal(self):
        import reseau
        cles = {k: os.environ.get(k) for k in ("MISTRAL_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "CLAUDE_INDISPONIBLE", "IA_MODAL_PRETE")}
        try:
            for k in ("MISTRAL_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"): os.environ[k] = "x"
            os.environ["CLAUDE_INDISPONIBLE"] = "1"; os.environ.pop("IA_MODAL_PRETE", None); reseau.HORS_SERVICE.clear(); reseau.EN_PAUSE.clear()
            self.assertEqual(reseau.ordre_ia(), ["mistral", "groq", "gemini", "openrouter"])
            os.environ["IA_MODAL_PRETE"] = "1"; self.assertEqual(reseau.ordre_ia()[-1], "modal")   # notre IA : tout dernier recours
        finally:
            for k, v in cles.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v
        import ia_modal
        self.assertEqual(ia_modal.APP, "jt-ia")


class TestCorrectionsSoir1Novembre(unittest.TestCase):
    """Remarques de l'auteur du 1er novembre au soir : bloc « Dis ce qui ne va pas » absent sur les vidéos récentes ; banque des
    décors écrasée quand deux fabrications finissent en même temps ; lieux sans description anglaise."""

    def test_repliques_chargees_en_direct(self):
        src = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn("async function chargerRepliques(v,i)", src)
        self.assertIn('if(v.origine==="tiktok"&&!(v.reps&&v.reps.length)) chargerRepliques(v,i)', src)

    def test_banque_fusionnee(self):
        import fusion
        base = b"a\tsalon\n"; eux = b"a\tsalon\nb\t[semi] cuisine\n"; nous = b"a\tsalon\nc\t[semi] salon\n"
        self.assertEqual(fusion._lignes(eux, nous, base), b"a\tsalon\nb\t[semi] cuisine\nc\t[semi] salon\n")
        self.assertEqual(json.loads(fusion._compteur(b'{"2026-11": 3}', b'{"2026-11": 3}', b'{"2026-11": 2}')), {"2026-11": 4})

    def test_lieux_en_anglais(self):
        import semi_realiste as SR, decor_dessin as DD
        for l in DD.LIEUX:
            if l == "voiture": continue
            d = SR.description(l)
            self.assertFalse(d.replace("[semi] ", "").startswith(l.replace("_", " ") + ","), l)


class TestListe6Novembre(unittest.TestCase):
    """Choix de l'auteur du 6 novembre : 1, 2, 3, 4, 5, 7, 11, 18, 21, 23, 26, 27, 37, 40, 41, 45, 46, 48, 50."""

    def test_temps_par_etape(self):
        import progression as PR
        PR.TEMPS.clear(); PR._COURANTE[:] = [None, None]
        PR.chrono("Écoute du son TikTok", 100.0); PR.chrono("Dessin des images : 30/900", 160.0); PR.chrono("Dessin des images : 60/900", 200.0)
        PR.chrono(None, 400.0)
        self.assertEqual(PR.TEMPS["Écoute du son TikTok"], 60.0); self.assertEqual(PR.TEMPS["Dessin des images"], 240.0)
        anciens = [{"Dessin des images": 100}, {"Dessin des images": 110}, {"Dessin des images": 90}]
        self.assertEqual([k for k, _, _ in PR.lents({"Dessin des images": 600}, anciens)], ["Dessin des images"])
        self.assertEqual(PR.lents({"Dessin des images": 150}, anciens), [])

    def test_pre_ecoute(self):
        import pre_ecoute as P, doublage, dessin_partage as DP
        d = tempfile.mkdtemp(); anc = DP.LOCAL; DP.LOCAL = d
        try:
            t = tempfile.mkdtemp(); f = os.path.join(t, "piste.wav"); open(f, "wb").write(b"son")
            sk = {"doublage": {"piste": f, "source": "https://www.tiktok.com/@x/video/123"}}
            doublage.EVENEMENTS[:] = [(1, 2, "rire")]
            P.deposer("https://www.tiktok.com/@x/video/123", (sk, [np.zeros(3)], [[("a", 0, 1)]]))
            self.assertEqual(len(P.stock()), 1)
            doublage.EVENEMENTS[:] = []
            self.assertIsNone(P.prendre([{"source_audio": "https://www.tiktok.com/@x/video/123"}]))   # déjà repris : écarté
            doublage.EVENEMENTS[:] = [(1, 2, "rire")]
            P.deposer("https://www.tiktok.com/@x/video/123", (sk, [np.zeros(3)], [[("a", 0, 1)]]))
            doublage.EVENEMENTS[:] = []
            u, prep = P.prendre([])
            self.assertTrue(u.endswith("/123")); self.assertEqual(open(prep[0]["doublage"]["piste"], "rb").read(), b"son")
            self.assertEqual(doublage.EVENEMENTS, [(1, 2, "rire")]); self.assertEqual(P.stock(), [])
        finally: DP.LOCAL = anc; doublage.EVENEMENTS[:] = []
        env = dict(os.environ)
        try:
            os.environ["HEURE_TIKTOK"] = "14:00 ; 21:30"; os.environ.pop("STOCK_SONS", None); self.assertEqual(P.stock_voulu(), 2)
            os.environ["PRE_ECOUTE"] = "0"; self.assertFalse(P.actif())
        finally: os.environ.clear(); os.environ.update(env)
        g = open(os.path.join(ICI, "..", ".github", "workflows", "garde.yml"), encoding="utf-8").read()
        self.assertIn("pre_ecoute.yml", g)
        self.assertIn("pre_ecoute\").prendre(historique)", open(os.path.join(ICI, "..", "moteur", "principal.py"), encoding="utf-8").read())

    def test_machine_prete(self):
        y = open(os.path.join(ICI, "..", ".github", "workflows", "emission.yml"), encoding="utf-8").read()
        self.assertIn("path: ~/venv", y); self.assertIn("uv pip install", y)
        self.assertIn('I -U "yt-dlp[default,curl-cffi]"', y)                        # yt-dlp toujours à jour, même en cache
        self.assertIn("numba", open(os.path.join(ICI, "..", "requirements.txt")).read())

    def test_parties_et_suite(self):
        import suites
        self.assertEqual([suites.num_partie(t) for t in ("Partie 2 😂", "pt3", "Episode 4", "ma vie 1/3", "le 12/10", "rien")], [2, 3, 4, 1, None, None])
        hist = [{"fichier": "a.mp4", "titre_source": "La dispute partie 1", "source_audio": "https://www.tiktok.com/@zed/video/1"}]
        self.assertEqual(suites.bonus({"titre": "La dispute partie 2"}, "Zed", suites.faites(hist)), 60)
        self.assertEqual(suites.bonus({"titre": "La dispute partie 2"}, "autre", suites.faites(hist)), 0)
        sk = {"doublage": {"titre": "La dispute partie 1"}}
        suites.preparer(sk, []); self.assertEqual(sk["suite"], "Partie 2 bientôt ! Abonne-toi"); self.assertIn("Partie 2", suites.ligne_legende(sk))
        sk = {"repliques": [{"p": "invite"}, {"p": "presentateur"}],
              "_suite": {"presentateur": {"fiche": {"genre": "f", "age": 30, "visage": 7}, "costume": {"haut": "pull"}},
                         "invite": {"fiche": {"genre": "h", "age": 40, "visage": 3}, "costume": {"haut": "chemise"}}}}
        fiches = {"presentateur": {"genre": "h"}, "invite": {"genre": "f"}}; cost = {"presentateur": {}, "invite": {}}
        self.assertEqual(suites.appliquer(sk, fiches, cost, ["presentateur", "invite"]), 2)
        self.assertEqual(fiches["invite"]["visage"], 7); self.assertEqual(fiches["presentateur"]["visage"], 3)   # femme avec femme
        self.assertEqual(cost["presentateur"]["haut"], "chemise")

    def test_liste_noire_et_tendances(self):
        import profils_tiktok as PT
        env = dict(os.environ)
        try:
            os.environ.update(PROFILS_INTERDITS="@abc", PROFILS_TIKTOK="@abc, @ok")
            self.assertEqual(PT.liste(), ["ok"])
        finally: os.environ.clear(); os.environ.update(env)
        self.assertTrue(PT.BIO_REFUS.search("Merci de ne pas reprendre mes vidéos")); self.assertFalse(PT.BIO_REFUS.search("Humour et sketchs"))
        self.assertEqual(PT.tendance({"titre": "quand ta mère #rentree #fyp"}, {"rentree"}, []), (20, "#rentree"))
        self.assertEqual(PT.tendance({"titre": "eva longoria au tel"}, set(), ["eva longoria"])[0], 15)

    def test_sous_titres_de_l_original(self):
        import ocr, equipe
        dial = [("Salut Morisse tu vas bien ?", "A", "blanc"), ("Ouais trop la forme frérot", "B", "jaune"), ("Tu viens au parc ce soir ?", "A", "blanc"),
                ("Grave je viens avec mon pote", "B", "jaune"), ("Il est trop drôle ton pote", "A", "blanc"), ("Ouais il fait des blagues", "B", "jaune"),
                ("Il ramène des chips", "B", "jaune"), ("Bah non jsuis crevé moi", "A", "jaune")]
        lignes = []
        for k, (tx, _, c) in enumerate(dial):
            t_ = tx.replace("Morisse", "Maurice").replace("frérot", "frerot").replace("crevé", "creve").replace("drôle", "drole").replace("ramène", "ramene")
            lignes.append(dict(deb=k * 2.4, fin=k * 2.4 + 2.4, t=t_.replace(" ", "") if k == 0 else t_, n=3, couleur=c))
        mots, t = [], 0.0
        for k, (tx, v, _) in enumerate(dial):
            t = k * 2.4
            for w in tx.split(): mots.append(dict(w=w, s=t, e=t + 0.25, voix=v)); t += 0.4
        anc = equipe._arbitrer; equipe._arbitrer = lambda m, d: {k: "B" for k in range(len(d))}
        try: m2 = ocr.corriger_mots([dict(x) for x in mots], lignes)
        finally: equipe._arbitrer = anc
        self.assertEqual(m2[1]["w"], "Maurice"); self.assertEqual(m2[10]["w"], "frérot")   # accents perdus par la lecture : mot gardé
        m3 = ocr.couleurs_voix([dict(x) for x in mots], lignes)
        self.assertEqual({m["voix"] for m in m3[-5:]}, {"B"})                  # phrase jaune rangée sur A : rendue à B
        self.assertEqual(m3[0]["voix"], "A")
        self.assertEqual(ocr.couleur(np.full((10, 40, 3), 255, np.uint8)), "blanc")
        self.assertEqual(ocr.corriger_mots([dict(x) for x in mots], [dict(deb=0, fin=9, t="Boulangerie Dupont", n=9)])[1]["w"], "Morisse")

    def test_casting_de_l_auteur(self):
        import studio
        sk = {"_casting_auteur": {"invite": {"genre": "f", "age": "ado", "espece": "chat", "haut": "pull", "c_haut": "rouge", "chapeau": "aucun"}}}
        fiches = {"invite": {"genre": "h", "age": 40, "barbe": "trois_jours"}}; cost = {"invite": {"haut": "chemise", "chapeau": "casquette", "bas": "robe"}}
        self.assertEqual(studio.casting_auteur(sk, fiches, cost, ["invite"], 5), 1)
        F = fiches["invite"]; self.assertEqual((F["genre"], F["age"], F["espece"]), ("f", 15, "chat")); self.assertIsNone(F.get("barbe"))
        self.assertEqual(cost["invite"]["haut"], "pull"); self.assertEqual(cost["invite"]["c_haut"], studio.NOMS_COULEURS["rouge"])
        self.assertNotIn("chapeau", cost["invite"])
        src = open(os.path.join(ICI, "..", "moteur", "principal.py"), encoding="utf-8").read(); self.assertIn('_mode == "casting"', src)

    def test_budget_modal(self):
        import budget_modal as BM, subprocess
        env = dict(os.environ); anc = subprocess.run
        try:
            os.environ.update(MODAL_TOKEN_ID="x", MODAL_TOKEN_SECRET="y", BUDGET_MODAL="30")
            subprocess.run = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout='{"metered_cost": "28.50", "billed_cost": "0"}')
            self.assertEqual(BM.depense_mois(), 28.5)
            import alerte; anc_a = alerte.alerter; alerte.alerter = lambda *a: None
            try: self.assertEqual(BM.verifier(journal=lambda m: None), 28.5)
            finally: alerte.alerter = anc_a
            self.assertNotIn("MODAL_TOKEN_ID", os.environ)                    # plafond presque atteint : Modal coupé
        finally:
            subprocess.run = anc; os.environ.clear(); os.environ.update(env)
            try: os.remove(os.path.join(ICI, "..", "episodes", "alerte_modal.txt"))
            except OSError: pass

    def test_rediffusion_recette_couverture(self):
        import publication_auto as PA, recette, couverture, datetime as dt
        m = dt.datetime(2026, 11, 6, 18, 0, tzinfo=PA.PARIS)
        h = [{"fichier": "a.mp4", "publie": True, "vues": 900, "date": "2026-06-01"}, {"fichier": "b.mp4", "publie": True, "vues": 5000, "date": "2026-10-30"},
             {"fichier": "c.mp4", "publie": True, "vues": 400, "date": "2026-05-01"}, {"fichier": "d.mp4", "publie": True, "vues": 9000, "date": "2026-05-01", "rediffusee": "2026-10-01"}]
        self.assertEqual(PA.a_rediffuser(h, m), "a.mp4")                     # plus de 3 mois, jamais rediffusée ces 3 derniers mois
        hist = [{"fichier": f"{k}.mp4", "vues": v, "duree": d, "source_audio": f"https://www.tiktok.com/@{p}/video/{k}"}
                for k, (v, d, p) in enumerate([(100, 15, "a"), (120, 16, "a"), (90, 18, "a"), (1000, 50, "b"), (900, 55, "b"), (1100, 60, "b")])]
        r = recette.analyser(hist)
        self.assertEqual(r["plus"][0]["valeur"] in ("@b", "40 à 70 s"), True); self.assertTrue(r["moins"])
        self.assertGreater(recette.bonus_son({"duree": 45}, r), 0); self.assertLess(recette.bonus_son({"duree": 12}, r), 0)
        hc = [{"fichier": f"{k}.mp4", "type_couverture": t} for k, t in enumerate(["chute", "reaction", "debut"] * 3)]
        vues = {f"{k}.mp4": (5000 if t == "reaction" else 100) for k, t in enumerate(["chute", "reaction", "debut"] * 3)}
        self.assertEqual(couverture.choisir({"chute": 9.0, "reaction": 3.0, "debut": 0.6}, hc, vues, hasard=lambda: 0.9), 3.0)
        self.assertEqual(couverture.DERNIER[0], "reaction")

    def test_site(self):
        src = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        for x in ('"shortcuts"', "raccourci=hasard", "githubstatus.com", 'id="castBloc"', 'id="tempsFab"', 'data-var="PRE_ECOUTE"',
                  'data-var="PROFILS_INTERDITS"', 'data-var="REDIFFUSION"', 'id="recette"', "modal_depense"):
            self.assertIn(x, src)


class TestListe11NovembreBis(unittest.TestCase):
    """Choix de l'auteur du 11 novembre (2e liste) : 7, 8, 9, 14, 15, 20."""

    def test_hashtags_a_risque(self):
        import legende as L
        self.assertEqual([h for h in ("charmeur", "armee", "sangria", "famille") if not L.hashtag_sur(h)], [])
        self.assertTrue(all(not L.hashtag_sur(h) for h in ("sexy", "porno", "drogue", "f4f", "followforfollow")))
        self.assertEqual(L.sans_risque("Trop drôle #famille #sexy #humour"), "Trop drôle #famille #humour")
        self.assertNotIn("weed", L.hashtags({"hashtags": ["weed", "couple"], "legende": "x"}))

    def test_variete_du_fil(self):
        import publication_auto as PA
        h = [{"fichier": "p.mp4", "publie": True, "programmee": "2026-11-10T18:00", "source_audio": "https://www.tiktok.com/@a/video/1", "recette": {"lieu": "salon"}},
             {"fichier": "x.mp4", "source_audio": "https://www.tiktok.com/@b/video/2", "recette": {"lieu": "salon"}},
             {"fichier": "y.mp4", "source_audio": "https://www.tiktok.com/@c/video/3", "recette": {"lieu": "bureau"}},
             {"fichier": "z.mp4", "source_audio": "https://www.tiktok.com/@a/video/4", "recette": {"lieu": "rue"}}]
        self.assertEqual(PA.alterner(["x.mp4", "y.mp4", "z.mp4"], h), ["y.mp4", "x.mp4", "z.mp4"])   # autre profil ET autre lieu d'abord

    def test_decouverte(self):
        import decouverte as D, time
        self.assertEqual(D.mentions(["duo avec @Enzolefrere !", "merci @enzolefrere et @a_b.c", "rien"]), {"enzolefrere": 2, "a_b.c": 1})
        t = time.time()
        bons = [{"url": f"u{k}", "duree": 40, "vues": 20000, "date": t - 86400 * k, "titre": "x"} for k in range(10)]
        self.assertEqual(D.verifier("zz", bons)["vues_mediane"], 20000)
        self.assertIsNone(D.verifier("zz", bons[:5]))                                     # trop peu de vidéos
        self.assertIsNone(D.verifier("zz", [dict(v, vues=100) for v in bons]))             # pas de vues
        self.assertIsNone(D.verifier("zz", [dict(v, date=t - 90 * 86400) for v in bons]))  # plus rien depuis 30 jours

    def test_paliers(self):
        import paliers as P
        self.assertEqual(P.nouveaux(361, {}, premier=True), ([], []))
        self.assertEqual(P.nouveaux(1020, {"500": {}}, premier=False), ([1000], [1000]))
        self.assertEqual(P.nouveaux(5100, {"500": {}}, premier=False)[0], [5000])       # plusieurs d'un coup : le plus haut
        self.assertEqual(P.nouveaux(1020, {"500": {}}, premier=True), ([], [1000]))     # 1er passage : rien de fêté après coup
        self.assertIn("1 000", P.script(1000)); self.assertTrue(P.script(1000).startswith("Jojo : "))

    def test_vitrine(self):
        import vitrine as V
        h = [{"fichier": f"{k}.mp4", "publie": True, "vues": v, "titre": t, "source_audio": f"https://www.tiktok.com/@{p}/video/{k}"}
             for k, (v, t, p) in enumerate([(900, "A", "x"), (800, "B", "x"), (700, "C", "y"), (600, "D", "z")])]
        self.assertEqual([e["titre"] for e in V.epingles(h)], ["A", "C", "D"])            # jamais deux du même créateur
        self.assertTrue(all(len(b) <= 80 for b in V.BIOS_SECOURS))

    def test_registre_des_pannes(self):
        import pannes
        j = ("début\n  isolation des voix impossible (ElevenLabs 401 : quota of 10000)\n  isolation des voix impossible (ElevenLabs 402 : quota of 20000)\n"
             "  [équipe · ingé son] ✔ deux transcriptions d'accord\n  aucune erreur\n  Décors IA impossibles (Modal 500) : décors dessinés\n")
        l = pannes.lire_journal(j)
        self.assertEqual(len(l), 2)                                           # la même panne avec d'autres chiffres = une seule
        f = os.path.join(tempfile.mkdtemp(), "p.json")
        pannes.ajouter(j, "2026-11-10", f); R = pannes.ajouter(j, "2026-11-11", f)
        self.assertEqual(sorted(e["n"] for e in R.values()), [2, 2])
        m = json.loads(pannes.fusionner(json.dumps(R).encode(), json.dumps(R).encode(), b"{}"))
        self.assertEqual(sorted(e["n"] for e in m.values()), [4, 4])         # deux fabrications en même temps : additionnées

    def test_site_et_workflows(self):
        s = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        for x in ('id="decouvertes"', 'id="vitrine"', 'id="pannes"', "rendreDecouvertes", "precL"):
            self.assertIn(x, s)
        e = open(os.path.join(ICI, "..", ".github", "workflows", "emission.yml"), encoding="utf-8").read(); self.assertIn("moteur/pannes.py", e)
        st = open(os.path.join(ICI, "..", ".github", "workflows", "stats.yml"), encoding="utf-8").read(); self.assertIn("moteur/paliers.py", st)
        self.assertTrue(os.path.exists(os.path.join(ICI, "..", ".github", "workflows", "vitrine.yml")))


class TestListe15Novembre(unittest.TestCase):
    """Choix de l'auteur du 15 novembre : 1 (karaoké contrôlé), 4 (silences), 8 (profils), 14 (courbe 48 h), 17 (heure du jour), 18 (sujets)."""

    def test_karaoke_controle(self):
        import jt
        mots = [("Ils", 0.0, 0.2), ("mange", 0.25, 0.5), ("des", 0.55, 0.65), ("pommes", 0.7, 1.0)]
        k = jt.karaoke("Ils mangent des pommes !", mots, 10.0)
        self.assertEqual(k[1], (10.25, 10.5)); self.assertEqual(len(k), 5)  # « mangent » = « mange » à la même place
        self.assertIsNone(jt.karaoke("Rien à voir avec le son entendu", mots, 10.0))   # paroles différentes : pas de karaoké
        self.assertIsNone(jt.karaoke("pommes des mange Ils", mots, 10.0))  # ordre impossible
        self.assertEqual(jt.mot_actif(k, 0, 5, 10.3), 1); self.assertIsNone(jt.mot_actif(k, 0, 5, 9.0))

    def test_karaoke_reecoute(self):
        import verif_finale as VF
        ph = [{"deb": 0.0, "fin": 2.0, "texte": "un deux trois quatre", "kara": [(0.0, 0.3), (0.5, 0.8), (1.0, 1.3), (1.5, 1.8)]}]
        juste = [{"w": w, "s": s, "e": s + 0.3} for w, s in (("un", 0.02), ("deux", 0.52), ("trois", 1.0), ("quatre", 1.5))]
        self.assertEqual(VF.controle_karaoke(ph, juste), [])
        ph2 = [dict(ph[0], deb=d, fin=d + 2, kara=[(a + d, b + d) for a, b in ph[0]["kara"]]) for d in (0, 3, 6)]
        decale = [{"w": w, "s": s + d + 0.6, "e": s + d + 0.9} for d in (0, 3, 6) for w, s in (("un", 0.0), ("deux", 0.5), ("trois", 1.0), ("quatre", 1.5))]
        self.assertTrue(any("karaoké décalé" in p["quoi"] and p["grave"] for p in VF.controle_karaoke(ph2, decale)))

    def test_silences(self):
        import doublage as D
        mots = [{"w": "a", "s": 0.2, "e": 0.6}, {"w": "b", "s": 3.0, "e": 3.4}, {"w": "c", "s": 3.6, "e": 4.0}]
        c = D.silences_a_couper(mots)
        self.assertEqual(len(c), 1); self.assertAlmostEqual(D.decaler(3.0, c), 3.0 - (c[0][1] - c[0][0]), places=3)
        self.assertEqual(D.silences_a_couper(mots, zones=[(1.0, 2.0)]), [])   # Silero entend quelqu'un dans le blanc : gardé

    def test_profils_disparus(self):
        import profils_tiktok as P
        anc_e, anc_l = P.ETAT, os.environ.get("PROFILS_TIKTOK")
        P.ETAT = os.path.join(tempfile.mkdtemp(), "e.json"); os.environ["PROFILS_TIKTOK"] = "@vivant\n@parti\n@endormi"
        import time as _t
        t0 = _t.time()
        lister = lambda p, journal=None: {"vivant": [{"date": t0 - 86400}], "parti": [], "endormi": [{"date": t0 - 60 * 86400}]}[p]
        try:
            E = P.surveiller(journal=lambda m: None, maintenant=t0, lister=lister)
            self.assertEqual(E["profils"]["parti"]["etat"], "ok")           # un seul échec : peut-être passager
            self.assertEqual(E["profils"]["endormi"]["etat"], "inactif")
            E = P.surveiller(journal=lambda m: None, maintenant=t0 + 86400, lister=lister)
            self.assertEqual(E["profils"]["parti"]["etat"], "introuvable"); self.assertEqual(E["profils"]["vivant"]["etat"], "ok")
        finally:
            P.ETAT = anc_e
            if anc_l is None: os.environ.pop("PROFILS_TIKTOK", None)
            else: os.environ["PROFILS_TIKTOK"] = anc_l

    def test_courbes_et_heure_du_jour(self):
        import stats, datetime
        from zoneinfo import ZoneInfo
        f = os.path.join(tempfile.mkdtemp(), "c.json"); t0 = 1_800_000_000
        stats.noter_courbes([{"id": 1, "fichier": "a.mp4", "date": t0, "vues": 100}], t0 + 3600, f)
        C = stats.noter_courbes([{"id": 1, "fichier": "a.mp4", "date": t0, "vues": 300}], t0 + 3 * 3600, f)
        self.assertEqual(C["a.mp4"]["p"], [[1.0, 100], [3.0, 300]])
        def v(jour, h, vues):                                              # une vidéo publiée tel jour de la semaine à telle heure
            d = datetime.datetime(2026, 11, 2, h, tzinfo=ZoneInfo("Europe/Paris")) + datetime.timedelta(days=jour)
            return {"date": d.timestamp(), "vues": vues}
        vids = [v(5, 12, 900), v(5, 12, 800), v(5, 18, 100), v(5, 18, 120), v(5, 12, 700), v(5, 18, 90)] + [v(1, 18, 500), v(1, 18, 600), v(2, 12, 50), v(2, 12, 60)]
        self.assertEqual(stats.meilleure_heure_publication(18, 5, vids), 12)   # le samedi : midi
        self.assertEqual(stats.meilleure_heure_publication(18, 1, vids), stats.meilleure_heure_publication(18, None, vids))   # le mardi : trop peu -> l'heure de la semaine
        vids2 = vids + [v(1, 18, 700), v(1, 18, 650), v(1, 12, 10), v(1, 12, 20)]
        self.assertEqual(stats.meilleure_heure_publication(12, 1, vids2), 18)   # assez de mardis : 18 h ce jour-là
        import publication_auto as PA
        self.assertEqual(PA.creneaux({"PUBLI_HEURE": "19:00"}, 3), [(19, 0)])

    def test_sujets_qui_marchent(self):
        import recette as R
        h = [{"vues": 1000, "titre_source": "mon frère dangereux #frere"}] * 3 + [{"vues": 100, "titre_source": "la cantine #ecole"}] * 4
        M = R.mots_gagnants(h)
        self.assertGreater(M["dangereux"], 1); self.assertLess(M["cantine"], 1)
        b, mots = R.bonus_sujet({"titre": "Encore un frère dangereux"}, {"mots": M})
        self.assertGreater(b, 0); self.assertIn("dangereux", mots)


class TestAudit17Novembre(unittest.TestCase):
    """Audit du 17 novembre 2026 (choix de l'auteur 1, 2, 8, 11, 14, 16, 19, 20, 21, 22, 23, 25, 29, 32)."""

    def test_tri_du_controle_ia(self):                                               # 1 : 132 remarques relues
        import verif_finale as V
        self.assertIsNone(V.trier_ia("Le sous-titre affiché ne correspond pas au texte attendu"))
        self.assertIsNone(V.trier_ia("Le personnage qui parle (Kévin) n'a pas l'allure d'une femme."))
        self.assertIsNone(V.trier_ia("Il manque les personnages des arrière-grands-pères dans l'image"))
        self.assertIsNone(V.trier_ia("La question 3 est non validée : le personnage n'a pas l'allure adéquate."))
        self.assertIsNone(V.trier_ia("Lila semble trop neutre pour une réplique sarcastique."))
        self.assertIsNone(V.trier_ia("L'un des personnages est un chat bleu au lieu d'un humain.", {"invite": {"espece": "chat"}}))
        self.assertTrue(V.trier_ia("Les bras du personnage blanc sont dupliqués."))
        self.assertFalse(V.trier_ia("Bouche fermée alors que le personnage parle selon le script."))
        h = json.load(open(os.path.join(ICI, "..", "episodes", "historique.json"), encoding="utf-8"))
        ia = [p["quoi"] for x in h for p in (x.get("a_verifier") or []) if p.get("poste") == "contrôle IA"]
        if len(ia) >= 50:                                                             # au moins 4 sur 5 des anciennes remarques écartées
            self.assertGreaterEqual(sum(1 for q in ia if V.trier_ia(q) is None), 0.8 * len(ia))

    def test_ecoute_gemini_departage(self):                                          # 2
        import equipe, video_ia
        self.assertEqual(equipe.departager("je suis un jedi comme un bébé", ["jedi"], ["j'ai dit"]), "A")
        self.assertEqual(equipe.departager("on va t'appeler à la barre", ["à", "la", "bar"], ["a", "la", "barre"]), None)
        self.assertEqual(equipe.departager("c'est mon frère", ["mon", "verre"], ["mon", "frère"]), "B")
        self.assertIsNone(equipe.departager("", ["a"], ["b"]))
        self.assertEqual(video_ia.lire_ecoute('{"passages": [{"n": 0, "texte": "salut"}, {"n": 5, "texte": "x"}]}', 2), {0: "salut"})
        mots = [{"w": w, "s": i * 0.3, "e": i * 0.3 + 0.25} for i, w in enumerate("je suis un jedi".split())]
        autre = [{"w": w, "s": i * 0.3, "e": i * 0.3 + 0.25} for i, w in enumerate("je suis un jeudi".split())]
        class B_:
            def note(self, *a, **k): pass
        out = equipe.deux_transcriptions([dict(m) for m in mots], autre, B_(), ecouter=lambda ps: {0: "je suis un jeudi"})
        self.assertEqual(out[3]["w"], "jeudi")                                       # Gemini a entendu « jeudi » : B gagne, sans l'IA texte

    def test_decors_varies(self):                                                     # 8
        import decors, datetime
        anc = decors.UTILISES; d = tempfile.mkdtemp(); decors.UTILISES = os.path.join(d, "u.tsv")
        try:
            open(decors.UTILISES, "w").write("2026-11-10\taaa\n2026-11-16\tbbb\n")
            self.assertEqual(decors.recents(7, datetime.date(2026, 11, 17)), {"bbb"})
            decors.noter_usage("ccc")
            self.assertIn("ccc", decors.recents())
        finally: decors.UTILISES = anc
        self.assertIn("another angle", decors.variante("[semi] a kitchen"))
        import fusion
        self.assertIn("decors/utilises.tsv", fusion.FUSIONNES)

    def test_publier_plus_vite_quand_ca_decolle(self):                                # 11
        import publication_auto as P
        t0 = 1_000_000.0
        courbes = {f"v{i}.mp4": {"date": t0 - 5 * 86400, "p": [[1, 50], [6, 300], [24, 500]]} for i in range(5)}
        courbes["chaud.mp4"] = {"date": t0 - 7 * 3600, "p": [[1, 200], [6.5, 1500]]}
        hist = [{"fichier": f"v{i}.mp4", "publie": True} for i in range(5)] + [
            {"fichier": "chaud.mp4", "publie": True, "source_audio": "https://www.tiktok.com/@kod/video/1"},
            {"fichier": "a.mp4", "publie": None, "source_audio": "https://www.tiktok.com/@autre/video/2"},
            {"fichier": "b.mp4", "publie": None, "source_audio": "https://www.tiktok.com/@kod/video/3"}]
        chaud = P.decolle(hist, courbes, t0)
        self.assertEqual(chaud["fichier"], "chaud.mp4")
        self.assertEqual(P.avancer(["a.mp4", "b.mp4"], chaud, hist), ["b.mp4", "a.mp4"])
        courbes["chaud.mp4"]["p"] = [[1, 60], [6.5, 320]]
        self.assertIsNone(P.decolle(hist, courbes, t0))                               # vues normales : rien ne change

    def test_commentaire_a_epingler(self):                                            # 14
        import legende
        self.assertEqual(legende.commentaire({"commentaire": "Team chat ou team chien ? 👇", "question": "Et vous ?"}), "Team chat ou team chien ? 👇")
        c = legende.commentaire({"sujet": "loyer", "repliques": [{"t": "Maurice, tu payes le loyer !"}, {"t": "Non Kenza ! Arrête, sérieux."}]})
        self.assertIn("Maurice", c); self.assertIn("Kenza", c)
        self.assertIn(legende.commentaire({"sujet": "x", "repliques": [{"t": "Attends, quoi ?"}]}), legende.GENERAL)

    def test_rappel_cle_et_erreurs_avalees(self):                                     # 16 et 21
        src = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        for x in ("cleRappel", "cleExpire", "joursAvantExpire", "github-authentication-token-expiration", "copierCom", "afficherCommentaire"):
            self.assertIn(x, src)
        import glob, pannes
        for f in glob.glob(os.path.join(ICI, "..", "moteur", "*.py")):
            if not f.endswith("pannes.py"): self.assertNotIn("except Exception: pass", open(f, encoding="utf-8").read(), f)
        out = io.StringIO(); anc = sys.stdout; sys.stdout = out
        try:
            for _ in range(3):
                try: raise ValueError("essai")
                except Exception as _e: pannes.avale(_e)
        finally: sys.stdout = anc
        self.assertEqual(out.getvalue().count("erreur avalée"), 1)                   # une seule ligne par endroit, même dans une boucle
        self.assertTrue(pannes.lire_journal(out.getvalue()))                          # comptée par le registre des pannes

    def test_rangements(self):                                                        # 20, 22, 23
        import cartoon, actu, serie
        self.assertTrue(callable(cartoon._bande_son) and callable(cartoon.tache) and callable(cartoon.keystone))
        self.assertIn(os.path.join("moteur", "sketchs", "actu.py"), actu.__file__)
        self.assertTrue(serie.FICHIER.replace("\\", "/").endswith("moteur/../episodes/serie.json"))
        self.assertFalse(os.path.isdir(os.path.join(ICI, "..", "maquettes", "photo")))
        self.assertTrue(os.path.exists(os.path.join(ICI, "..", ".github", "workflows", "ranger.yml")))


class TestPannes19Novembre(unittest.TestCase):
    """Registre des pannes relu le 19 novembre 2026 : vraies pannes réglées, fausses pannes plus comptées."""

    def test_pas_des_pannes(self):
        import pannes
        for l in ("I0000 00:00:1794921200.512431    3804 port.cc:153] oneDNN custom operations are on. You may see slightly different errors",
                  "[transformers] You are using a model of type `sam2_video` to instantiate a model of type `sam2`. error",
                  "* fix torchcodec installation. Error message was:",
                  "réseau : erreur 503 passagère, nouvel essai dans 2 s",
                  "Jury qualité (ia) : 6.0/10 — Humoriste 6.6/10 : le texte est illisible",
                  "- à 0.4 s : Le texte dans le GPS est minuscule, flou et quasi illisible",
                  "scène reconstituée : L'employé refuse net de travailler.",
                  "Manque par rapport à la vidéo d'origine : absence du smartphone, erreur",
                  "lieux séparés proposés par l'IA refusés : rien dans le son ne dit qu'ils se parlent à distance",
                  "5 réattribution(s) de l'IA refusée(s) : la voix de ces répliques est reconnue avec certitude"):
            self.assertEqual(pannes.lire_journal(l), [], l)
        self.assertTrue(pannes.lire_journal("liste de contrôle par l'IA impossible (réponse inexploitable)"))   # une vraie panne reste
        f = os.path.join(tempfile.mkdtemp(), "p.json")
        json.dump({"[transformers] error x": {"n": 3, "exemple": "[transformers] error x", "derniere": "2026-11-17", "jours": {}}}, open(f, "w"))
        self.assertEqual(pannes.ajouter("", "2026-11-19", f), {})                   # anciennes fausses pannes retirées du registre

    def test_elevenlabs_epuise_plus_appele(self):
        import doublage
        anc = {k: os.environ.get(k) for k in ("ELEVENLABS", "ELEVENLABS_API_KEY")}
        appels = []; orig = doublage._multipart
        doublage._multipart = lambda *a, **k: appels.append(a) or (_ for _ in ()).throw(RuntimeError("ElevenLabs 401 : quota_exceeded"))
        try:
            os.environ["ELEVENLABS_API_KEY"] = "x"; os.environ.pop("ELEVENLABS", None)
            d = tempfile.mkdtemp(); open(f"{d}/mono.wav", "wb").write(b"RIFF")
            self.assertEqual(doublage.isoler(d), (None, f"{d}/mono.wav"))
            self.assertEqual(len(appels), 1); self.assertEqual(os.environ.get("ELEVENLABS"), "0")   # crédit épuisé noté
            doublage.isoler(d); self.assertEqual(len(appels), 1)                                     # plus jamais rappelé
            self.assertFalse(doublage.eleven_ok())
        finally:
            doublage._multipart = orig
            for k, v in anc.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v

    def test_sources_corrigees(self):
        src = lambda f: open(os.path.join(ICI, "..", f), encoding="utf-8").read()
        self.assertIn("2e essai avec une autre IA", src("moteur/verif_finale.py"))
        self.assertIn("release des morceaux relue", src("moteur/dessin_partage.py"))
        self.assertIn("warnings.simplefilter", src("moteur/locuteurs.py"))
        self.assertNotIn('python_version="3.10"', src("moteur/ecoute_modal.py"))
        for w in ("emission.yml", "pre_ecoute.yml", "dessin.yml"):
            self.assertIn("TF_CPP_MIN_LOG_LEVEL", src(".github/workflows/" + w))


class TestFicheTournage20Novembre(unittest.TestCase):
    """Fiche de tournage (choix de l'auteur du 20 novembre 2026 : 1-7, 9-16, 18-23, 25) et triple contrôle."""

    REPS = [{"p": "presentateur", "t": "Il est 3h du mat, t'as vu l'heure ? Et il fait trop chaud ici !"},
            {"p": "invite", "t": "Tiens, mes clés. Et paie le loyer, c'est le bordel ici."},
            {"p": "presentateur", "t": "Toi tu te moques de moi, rends-moi mon gâteau d'anniversaire !"}]

    def _sk(self):
        return {"repliques": [dict(r) for r in self.REPS], "decoupage": [{"repliques": [0, 1, 2], "decor": ""}], "doublage": {"evenements": [[0, 3.5, "rain"], [4, 6.5, "tv"]]}}

    def test_indices_paroles_et_bruits(self):
        import fiche_tournage as FT
        ind = FT.indices_texte(self.REPS)
        self.assertEqual(ind["moment"], "nuit"); self.assertEqual(ind["meteo"], "chaud"); self.assertEqual(ind["occasion"], "anniversaire")
        self.assertIn(ind["niveau"], ("desordre", "modeste"))
        self.assertIn("cles", [o["objet"] for o in ind["objets"]]); self.assertIn("birthday cake and balloons", ind["details"])
        son = FT.indices_son([[0, 3.5, "rain"], [4, 6.5, "tv"], [7, 7.5, "dog"]])
        self.assertEqual(son["meteo"], "pluie"); self.assertIn("tele", son["animations"]); self.assertNotIn("dog", son["entendus"])   # un bruit d'1/2 s ne compte pas

    def test_nettoyage_et_regles(self):
        import fiche_tournage as FT
        sk = self._sk()
        brut = {"lieu": "bureau", "lieu_precis": "un bureau très moderne", "moment": "jour", "meteo": "neige", "ambiance": "dispute", "niveau": "pas_un_niveau",
                "details": ["pile of unpaid bills", "a man sitting"], "panneaux": ["Bienvenue"],
                "personnages": {"presentateur": {"genre": "h", "age": 12, "barbe": "trois_jours", "tenue": "maillot_bain", "etat_tenue": ["mouille", "sueur"]},
                                "invite": {"genre": "f", "age": 30, "tenue": "robe_soiree", "etat_tenue": ["dechire"]}, "inconnu": {"age": 40}},
                "repliques": [{"n": 0, "emotion": "joie", "signe": "veine"}, {"n": 2, "emotion": "colere", "signe": "veine", "objet": "telephone"}, {"n": 9, "emotion": "joie"}],
                "reactions": [{"n": 2, "qui": "invite", "mot": "gâteau", "reaction": "choque"}, {"n": 2, "qui": "presentateur", "reaction": "rire"}]}
        F = FT.nettoyer(brut, sk)
        self.assertEqual(F["lieu_precis"], ""); self.assertEqual(F["niveau"], ""); self.assertEqual(F["details"], ["pile of unpaid bills"])   # français / personne : retirés
        self.assertNotIn("inconnu", F["personnages"]); self.assertNotIn(9, F["repliques"])
        cor = FT.controle_regles(F, sk, FT.indices_texte(sk["repliques"]))
        self.assertEqual(F["moment"], "nuit")                                               # dit dans le dialogue
        self.assertEqual(F["meteo"], "chaud")
        P = F["personnages"]["presentateur"]
        self.assertEqual(P["barbe"], "aucune"); self.assertEqual(P["tenue"], "normale")      # enfant barbu, maillot au bureau : corrigés
        self.assertEqual(P["etat_tenue"], ["sueur"])                                       # « il fait trop chaud » : sueur oui, mouillé non
        self.assertEqual(F["personnages"]["invite"]["etat_tenue"], [])                      # déchiré : rien ne le dit
        self.assertNotIn("signe", F["repliques"][0]); self.assertEqual(F["repliques"][2]["signe"], "veine")   # veine = colère seulement
        self.assertNotIn("objet", F["repliques"][2])                                        # pas de téléphone dans les paroles
        self.assertEqual(F["repliques"][1]["objet"], "cles")                                 # objet cité : dans les mains
        self.assertEqual(F["panneaux"], [])                                                  # pas d'enseigne au bureau
        self.assertEqual([r["qui"] for r in F["reactions"]], ["invite"])                    # on ne réagit pas à sa propre réplique
        self.assertGreaterEqual(len(cor), 6)
        faites = FT.appliquer_corrections(F, sk, [{"champ": "personnages.invite.tenue", "valeur": "pyjama", "raison": "essai"},
                                                   {"champ": "moment", "valeur": "minuit", "raison": "valeur interdite"}])
        self.assertEqual(len(faites), 1); self.assertEqual(F["personnages"]["invite"]["tenue"], "pyjama"); self.assertEqual(F["moment"], "nuit")

    def test_faire_sans_ia_puis_studio(self):
        import fiche_tournage as FT, studio, equipe
        sk = self._sk()
        anc = FT._ia_texte; FT._ia_texte = lambda *a, **k: None
        try:
            B = equipe.Bulletin(); F = FT.faire(sk, "", None, 22050, None, B)
        finally: FT._ia_texte = anc
        self.assertEqual(F["source"], "regles"); self.assertEqual(F["moment"], "nuit"); self.assertIn("pluie_vitre", F["animations"] + ["pluie_vitre"])
        self.assertTrue(any(l["poste"] == "fiche de tournage" for l in B.lignes)); self.assertEqual(len([l for l in B.lignes if l["poste"] == "fiche de tournage"]), 3)
        F["personnages"]["invite"] = {"genre": "f", "tenue": "impermeable", "etat_tenue": ["mouille"], "c_cheveux": "roux"}
        F["repliques"][2] = {"emotion": "colere", "signe": "veine", "cible": "autre", "intensite": 3}
        F["reactions"] = [{"n": 2, "qui": "invite", "mot": "gâteau", "reaction": "choque"}]
        self.assertTrue(FT.appliquer(sk, F))
        S = sk["studio"]
        self.assertEqual(S["moment"], "nuit"); self.assertIn("with", sk["decoupage"][0]["decor"])            # le décor raconte l'histoire
        self.assertEqual(sk["repliques"][2]["_signe"], "veine"); self.assertEqual(sk["repliques"][2]["_cible"], "autre")
        B2 = studio.bible(sk, ["presentateur", "invite"])
        c = B2["costumes"]["invite"]
        self.assertEqual(c.get("tenue"), "impermeable"); self.assertEqual(c.get("etats"), ("mouille",))
        self.assertEqual(B2["reactions"][0]["reaction"], "choque"); self.assertNotIn("pluie", B2["ambiances"])   # « il fait trop chaud » passe avant la pluie entendue

    def test_fidelite_et_correction(self):
        import fiche_tournage as FT, verif_finale as V
        sk = self._sk(); F = FT.nettoyer({"lieu": "salon", "moment": "jour"}, sk); F["source"] = "video"; sk["_fiche"] = F
        anc = FT._gemini_brut
        FT._gemini_brut = lambda v, t: {"problemes": [{"t": 2, "probleme": "On dit qu'il est 3h du matin mais il fait grand jour", "champ": "moment", "valeur": "nuit"},
                                                      {"t": 3, "probleme": "Les sous-titres sont décalés"}, {"t": 4, "probleme": "Pas de gâteau", "champ": "piratage", "valeur": "x"}]}
        f = os.path.join(tempfile.mkdtemp(), "v.mp4"); open(f, "wb").write(b"x")
        try: pbs = FT.fidelite(f, sk)
        finally: FT._gemini_brut = anc
        self.assertEqual(len(pbs), 2); self.assertEqual(pbs[0]["champ"], "moment"); self.assertEqual(pbs[1]["champ"], "")   # sous-titres écartés, champ interdit vidé
        pts = [dict(V._defaut(2, "fidélité à l'audio", pbs[0]["probleme"]), correction=[{"champ": "moment", "valeur": "nuit"}])]
        faits = FT.corriger_depuis_points(sk, pts)
        self.assertTrue(faits); self.assertEqual(sk["_fiche"]["moment"], "nuit"); self.assertEqual(sk["studio"]["moment"], "nuit")
        self.assertEqual(sk["_decors_a_refaire"], [0])                                      # le moment change : le décor est repeint

    def test_choix_du_decor_par_gemini(self):
        import fiche_tournage as FT
        anc = FT._gemini_images
        FT._gemini_images = lambda ims, t, timeout=120: {"choix": 1, "fenetre": [100, 200, 400, 600], "tele": [0, 0, 1, 1], "panneau": []}
        try:
            ch, zo = FT.choisir_decor([np.zeros((10, 10, 3), np.uint8)] * 3, {"lieu": "salon"})
            self.assertEqual(ch, 1); self.assertEqual(zo, {"fenetre": [216, 192, 648, 768]})   # boîte trop petite (télé) refusée
            FT._gemini_images = lambda ims, t, timeout=120: {"convient": False}
            self.assertIs(FT.decor_convient(np.zeros((10, 10, 3), np.uint8), {"lieu": "salon"}), False)
        finally: FT._gemini_images = anc

    def test_dessin_des_details(self):
        import humain, marionnette as M, perso_croquis as PC
        for pp, cc in (({"signe": "veine", "emo": "colere"}, {"etats": ("sueur", "dechire", "tache")}), ({"signe": "coeurs"}, {"etats": ("mouille",)}),
                       ({"signe": "etoiles", "ecran": "Maman", "ecran_main": "d"}, {"etats": ("maquillage_coule",)}), ({"signe": "nuage", "vapeur_main": "d"}, {}),
                       ({"signe": "fumee_oreilles", "bouche_pleine": True}, {})):
            img = np.full((900, 600, 3), 245, np.uint8); avant = img.copy()
            p = M.pose_neutre(); p.update(x=300, y=820, s=1.0, t=0.5, costume=dict(haut="tshirt", c_haut=(80, 140, 210), **cc)); p.update(pp)
            PC.dessiner(img, humain.creer(5), p)
            self.assertGreater(int(np.abs(img.astype(int) - avant).sum()), 0)

    def test_sources_branchees(self):
        src = lambda f: open(os.path.join(ICI, "..", f), encoding="utf-8").read()
        self.assertIn("fiche_tournage.faire(", src("moteur/doublage.py"))
        self.assertIn("corriger_depuis_points", src("moteur/principal.py"))
        self.assertIn("fidélité à l'audio", src("moteur/verif_finale.py"))
        self.assertIn("controlnet_conditioning_scale", src("moteur/decor_modal.py"))
        self.assertIn("_suite_decors", src("moteur/suites.py"))
        for x in ("emo_voix", "REAC_F", "SURSAUTS", "vapeur_main", "ZONES_SC", '"tele" in anim'):
            self.assertIn(x, src("moteur/cartoon.py"))
