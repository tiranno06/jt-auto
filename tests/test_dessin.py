"""Tests : Dessin, décors, mise en scène et rendu vidéo.
Lancer tous les tests : python -m unittest discover -s tests -v"""
from commun import *  # noqa: F401,F403 (chemins, réglages des tests, modules, SKETCH, FauxClaude…)


class TestCartoon(unittest.TestCase):
    def test_emotions(self):
        try: import cartoon
        except Exception as e: self.skipTest(f"dépendances vidéo absentes : {e}")
        self.assertEqual(cartoon.emotion("[laughs] Non mais"), "rire")
        self.assertEqual(cartoon.emotion("[angry] Kévin !"), "colere")
        self.assertEqual(cartoon.emotion("[deadpan] Super."), "blase")
        self.assertEqual(cartoon.emotion("Bonjour."), "neutre")

    def test_rendu_apercu(self):
        try: import cartoon, tempfile, glob
        except Exception as e: self.skipTest(f"dépendances vidéo absentes : {e}")
        sk = {"titre_accroche": "Quand ton pote dit « j'arrive »",
              "repliques": [{"p": "presentateur", "t": "J'arrive dans cinq minutes.", "d": "[confident] J'arrive dans cinq minutes."},
                            {"p": "envoyee", "t": "Ça fait deux heures.", "d": "[angry] Ça fait deux heures.", "objet": "telephone"},
                            {"p": "presentateur", "t": "Bientôt.", "chute": True}],
              "decoupage": [{"scene": "bar", "repliques": [0, 1]}, {"scene": "rue", "repliques": [2], "effet": "pluie_billets", "titre": "Plus tard"}]}
        auds = [np.random.default_rng(k).normal(0, 0.2, 22050).astype(np.float32) for k in range(3)]
        d = tempfile.mkdtemp(); total = cartoon.rendre(sk, d, auds, apercu=True)
        self.assertGreater(total, 3); self.assertEqual(len(glob.glob(d + "/*.png")), 8)   # + réaction finale et arrêt sur image

    def test_decoupage_dessin(self):
        sk = ecrire.valider({"sujet": "x", "repliques": [{"p": "invite", "t": "Salut.", "objet": "telephone"}, {"p": "envoyee", "t": "Non."},
                                                         {"p": "invite", "t": "Si."}, {"p": "envoyee", "t": "Bon.", "objet": "bazooka"}],
                             "decoupage": [{"scene": "s", "repliques": [0, 1], "decor": "a cozy bar <script>", "titre": "Le bar", "effet": "pluie_billets"},
                                           {"scene": "t", "repliques": [2, 3], "effet": "explosion"}]}, set(), libre=True)
        self.assertEqual(sk["repliques"][0]["objet"], "telephone"); self.assertNotIn("objet", sk["repliques"][3])
        self.assertEqual(sk["decoupage"][0]["decor"], "a cozy bar script"); self.assertEqual(sk["decoupage"][0]["effet"], "pluie_billets")
        self.assertNotIn("effet", sk["decoupage"][1])


class TestRendu(unittest.TestCase):
    def test_sous_titres_cales_sur_whisper(self):
        try: import jt
        except Exception as e: self.skipTest(f"dépendances vidéo absentes : {e}")
        g = jt.minutage("Bonsoir. Le budget est perdu.", np.zeros(44100, np.float32), 10.0,
                        [("Bonsoir.", 0.0, 0.5), ("Le", 0.7, 0.8), ("budget", 0.8, 1.2), ("est", 1.2, 1.3), ("perdu.", 1.3, 1.8)])
        self.assertEqual(g[0], ("Bonsoir.", 10.0, 10.7))                    # reste affiché jusqu'au groupe suivant (jt.lisibles, 7 novembre)
        self.assertAlmostEqual(g[-1][2], 11.8)


class TestSousTitres(unittest.TestCase):
    def test_groupes_naturels(self):
        import jt
        g = jt.groupes("Je sens le « entre 8 h et 18 h ».")
        self.assertTrue(all(len(x) <= 22 for x in g))
        self.assertFalse(any(x.split()[-1].lower() in jt.PETITS for x in g[:-1]))
        self.assertIn("8 h", " ".join(g))


class TestPetitsDramas(unittest.TestCase):
    def test_script_manuel(self):
        r = ecrire.lire_script("Jojo : Salut !\nKévin: T'as vu ?\nMaman : Rends-la !")
        self.assertEqual([x["p"] for x in r], ["presentateur", "invite", "envoyee"])

    def test_cycle_ignore_manuel(self):
        import programme
        h = [{"format": "libre"}, {"format": "mini"}, {"format": "mini"}, {"format": "mini", "manuel": True}]
        self.assertEqual(programme.format_du_jour("cycle", h), "mini")

    def test_fusion_historique(self):
        import fusion
        m = fusion.fusion_historique([{"fichier": "a"}, {"fichier": "b"}], [{"fichier": "a", "vues": 3}, {"fichier": "c"}])
        self.assertEqual([x["fichier"] for x in m], ["a", "c", "b"]); self.assertEqual(m[0]["vues"], 3)
        # « d » supprimée sur le site pendant la fabrication (dans le point de départ, plus dans la version distante) : ne revient pas
        m = fusion.fusion_historique([{"fichier": "a"}, {"fichier": "d"}, {"fichier": "e"}], [{"fichier": "a"}], [{"fichier": "a"}, {"fichier": "d"}])
        self.assertEqual([x["fichier"] for x in m], ["a", "e"])

    def test_serie(self):
        import serie
        os.environ["EPISODES"] = "serie"
        try:
            vrai = serie.FICHIER; serie.FICHIER = os.path.join(os.path.dirname(__file__), "_serie_test.json")
            self.assertIn("NOUVELLE série", serie.contexte())
            self.assertEqual(serie.enregistrer({"serie_titre": "Jojo déménage", "resume_episode": "Il cherche un appart."}), 1)
            self.assertIn("épisode 2", serie.contexte()); self.assertIn("Il cherche un appart", serie.contexte())
        finally:
            os.environ.pop("EPISODES"); os.path.exists(serie.FICHIER) and os.remove(serie.FICHIER); serie.FICHIER = vrai

    def test_personnalites_reglables(self):
        os.environ["PERSO_JOJO"] = "un radin absolu"
        try: self.assertIn("un radin absolu", ecrire.personnalites())
        finally: os.environ.pop("PERSO_JOJO")


class TestImageEtBanque(unittest.TestCase):
    """Analyse de l'image de la vidéo d'origine, intonation de la voix, banque visuelle qui s'enrichit."""
    def setUp(self):
        try:
            import studio, analyse_video, banque_visuelle
        except Exception as e: self.skipTest(f"dépendances vidéo absentes : {e}")
        self.S, self.A, self.BV = studio, analyse_video, banque_visuelle

    def test_intonation(self):
        sr = 22050; tt = np.arange(int(sr * 1.2)) / sr
        a = (0.5 * np.sin(2 * np.pi * np.cumsum(180 * (1 + 0.3 * tt)) / sr)).astype(np.float32)
        f0, en = self.S.prosodie(a)
        self.assertAlmostEqual(float(np.median(f0[f0 > 0][:5])), 182, delta=8)      # la voix monte de 180 à 234 Hz
        z, r = self.S.intonation(f0, 180.0)
        self.assertGreater(r["moy"], 0.5); self.assertGreater(z[-5], z[5])
        self.assertEqual(self.S.emotion_texte("Bonjour.", 0.8, dict(moy=1.3, etendue=1.0, fin=0.1)), "joie")
        self.assertEqual(self.S.emotion_texte("Bonjour.", 0.3, dict(moy=-1.0, etendue=0.3, fin=0.0)), "blase")

    def test_analyse_image(self):
        import tempfile, cv2
        chemin = os.path.join(tempfile.mkdtemp(), "v.mp4"); vw = cv2.VideoWriter(chemin, cv2.VideoWriter_fourcc(*"mp4v"), 30, (360, 640))
        for k in range(150):                                               # plan 1 : mur orangé, un carré qui bouge ; plan 2 : pièce sombre
            im = np.zeros((640, 360, 3), np.uint8)
            if k < 75: im[:] = (60, 120, 220); cv2.rectangle(im, (40 + k, 200), (140 + k, 320), (200, 60, 40), -1)
            else: im[:] = (30, 25, 20)
            vw.write(im)
        vw.release()
        r, cles = self.A.analyser(chemin)
        if not r: self.skipTest("lecture vidéo indisponible")
        self.assertEqual(r["nb_plans"], 2); self.assertEqual(len(cles), 2)
        self.assertAlmostEqual(sum(r["plans"].values()), 1.0, delta=0.01); self.assertIn(r["moment"], ("jour", "soir", "nuit"))
        self.assertIn("plans", self.A.texte(r))

    def test_bible_depuis_image_et_banque(self):
        import tempfile
        BV, S = self.BV, self.S; ancien = (BV.FICHIER, BV.STATS); d = tempfile.mkdtemp()
        BV.FICHIER, BV.STATS = os.path.join(d, "b.json"), os.path.join(d, "s.json")
        try:
            V = dict(plans={"tres_serre": 0.5, "serre": 0.3, "moyen": 0.1, "large": 0.1}, camera={"avance": 0.6, "fixe": 0.4}, energie=0.8, sourires=0.5,
                     duree_plan=1.5, moment="nuit", mur=[60, 90, 160], personnes=[dict(habit=[200, 30, 40], cheveux=[230, 190, 110], presence=0.9)])
            sk = {"sujet": "x", "repliques": [{"p": "presentateur", "t": "Bonjour à tous, ça va bien ?"}, {"p": "invite", "t": "Oui."}],
                  "decoupage": [{"scene": "1", "repliques": [0, 1]}], "doublage": {"visuel": V, "source": "https://www.tiktok.com/@a/video/1"}}
            B = S.bible(sk, ["presentateur", "invite"])
            self.assertEqual(B["moment"], "nuit"); self.assertIsNotNone(B["c_mur"])
            self.assertEqual(B["costumes"]["presentateur"]["c_haut"], (200, 30, 40))          # celui qui parle le plus porte l'habit de la vidéo
            self.assertEqual(B["costumes"]["presentateur"]["c_cheveux"], (230, 190, 110))
            self.assertGreater(B["rythme"]["serre"], 0.6)
            BV.ajouter(sk["doublage"], {"lieux": ["bar"], "objets": [{"replique": 0, "objet": "verre"}]}, {"lieux": ["bar"]}, "v1.mp4")
            BV.ajouter(sk["doublage"], {"lieux": ["bar"]}, {"lieux": ["bar"]}, "v1.mp4")              # même vidéo d'origine : remplacée
            self.assertEqual(len(BV.lire()), 1)
            json.dump({"videos": [{"fichier": "v1.mp4", "vues": 500}]}, open(BV.STATS, "w"))
            t = BV.tendances(); self.assertEqual(t["lieux"], ["bar"]); self.assertEqual(t["meilleures"][0][0], 500)
            self.assertIn("BANQUE VISUELLE", BV.consigne())
            sk2 = {"sujet": "y", "repliques": [{"p": "presentateur", "t": "Salut."}, {"p": "invite", "t": "Salut."}]}
            self.assertGreater(S.bible(sk2, ["presentateur", "invite"])["rythme"]["serre"], 0.6)   # sans image : le rythme de la banque
        finally: BV.FICHIER, BV.STATS = ancien

    def test_consigne_images(self):
        import doublage
        texte = doublage.IMAGES.format(mesures="2 plans", banque="", coiffures="carre, ondule", coupes="1.0 s")
        self.assertIn("coiffure", texte); self.assertIn("objets", texte)
        self.assertIn("queue", doublage.consigne("v", "l"))


class TestVideoComplete(unittest.TestCase):
    """Fumée : une vraie mini-vidéo fabriquée de bout en bout (rendu sur plusieurs processeurs, son, encodage)."""
    def test_mini_video(self):
        import shutil, subprocess
        if not shutil.which("ffmpeg"): self.skipTest("ffmpeg absent")
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import cartoon
        reps = [("presentateur", "Tiens, c'est pour toi !"), ("invite", "Bravo, tope là !"), ("presentateur", "Courage, ça va aller.")]
        sk = {"titre_accroche": "Essai", "sujet": "Essai", "repliques": [{"p": p, "t": t} for p, t in reps],
              "decoupage": [{"scene": "1", "repliques": [0, 1, 2], "decor": "an office with a desk"}]}
        sk["repliques"][-1]["chute"] = True
        auds = [(0.3 * np.sin(np.arange(int(22050 * 1.4)) / 22050 * 2 * np.pi * 150) * (np.sin(np.arange(int(22050 * 1.4)) / 22050 * 16) > -0.3)).astype(np.float32) for _ in reps]
        sortie = os.path.join(tempfile.mkdtemp(), "v.mp4")
        total = cartoon.rendre(sk, sortie, auds, mini=True)
        self.assertGreater(total, 3); self.assertTrue(os.path.getsize(sortie) > 50000)
        self.assertTrue(0 < cartoon.COUVERTURE < total)                                        # instant de couverture choisi
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", sortie], capture_output=True, text=True)
        self.assertIn("video", r.stdout); self.assertIn("audio", r.stdout)

    def test_appel_pause_et_reprise(self):
        """Fumée de bout en bout : un appel téléphonique (lieux séparés, écran partagé), une pause faute de temps, puis une reprise
        avec les blocs d'images déjà dessinés (c'est ce chemin qui plantait le 25 octobre)."""
        import shutil
        if not shutil.which("ffmpeg"): self.skipTest("ffmpeg absent")
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import cartoon, studio, copy, time as _t
        lignes = [("presentateur", "Allô, t'es où là ?"), ("invite", "Je suis dans la rue, j'arrive bientôt !"), ("presentateur", "Tu dis ça depuis une heure."),
                  ("invite", "Promis, je suis au coin de la rue, je vois ta fenêtre."), ("presentateur", "Ah oui ? Elle est de quelle couleur ?"),
                  ("invite", "Euh… bleue ?"), ("presentateur", "Je vis au dixième étage, sans fenêtre.")]
        sk = {"titre_accroche": "Essai", "sujet": "Essai", "repliques": [{"p": p, "t": t} for p, t in lignes],
              "studio": {"lieux_separes": {"presentateur": "a cozy living room", "invite": "a city street"}, "moyen": "telephone"},
              "decoupage": [{"scene": "1", "repliques": list(range(len(lignes))), "decor": "a cozy living room"}]}
        sk["repliques"][-1]["chute"] = True
        self.assertTrue(studio.separer_lieux(sk))
        auds = [(0.3 * np.sin(np.arange(int(22050 * 1.6)) / 22050 * 2 * np.pi * 150) * (np.sin(np.arange(int(22050 * 1.6)) / 22050 * 16) > -0.3)).astype(np.float32) for _ in lignes]
        anc = {k: os.environ.get(k) for k in ("BLOC_IMAGES", "DESSIN_PARTAGE", "REDESSIN_PARTIEL")}
        os.environ.update(BLOC_IMAGES="60", DESSIN_PARTAGE="0")
        dossier = tempfile.mkdtemp(); gardes = []
        def garder(a_, b_, c_):
            copie = os.path.join(dossier, f"b_{a_}_{b_}.mp4"); shutil.copy(c_, copie); gardes.append((a_, b_, copie))
        try:
            with self.assertRaises(cartoon.TempsDepasse):                 # plus le temps : pause avant le 1er bloc
                cartoon.rendre(copy.deepcopy(sk), os.path.join(dossier, "p.mp4"), auds, mini=True, limite=_t.time() - 1)
            cartoon.APRES_BLOC[0] = garder
            import contextlib, io
            journal = io.StringIO()
            with contextlib.redirect_stdout(journal): d1 = cartoon.rendre(copy.deepcopy(sk), os.path.join(dossier, "v1.mp4"), auds, mini=True)
            cartoon.APRES_BLOC[0] = None
            self.assertIn("appel : écran partagé du début à la fin", journal.getvalue())   # l'écran partagé de l'appel tient tout du long
            self.assertGreaterEqual(len(gardes), 2)
            d2 = cartoon.rendre(copy.deepcopy(sk), os.path.join(dossier, "v2.mp4"), auds, mini=True, deja=gardes[:-1])   # reprise
            self.assertAlmostEqual(d1, d2, places=2); self.assertTrue(os.path.getsize(os.path.join(dossier, "v2.mp4")) > 50000)
        finally:
            cartoon.APRES_BLOC[0] = None
            for k, v in anc.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v


class TestRedessinPartiel(unittest.TestCase):
    def test_seules_les_images_changees(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import cartoon as C
        anc = {"sig_global": "g", "nf": 300, "fps": 30, "sig_plans": [(0, 4, "a"), (4, 7, "b"), (7, 10, "c")], "sig_ph": [(0, 5, "x"), (5, 10, "y")]}
        neuf = dict(anc, sig_plans=[(0, 4, "a"), (4, 7, "B"), (7, 10, "c")])            # seul le 2e plan change
        r = C.images_a_refaire(anc, neuf, 300, 30)
        self.assertTrue(r and min(r) >= 3 * 30 - 1 and max(r) <= 8 * 30 + 1)              # autour du plan changé (± 1 s)
        self.assertEqual(C.images_a_refaire(anc, dict(anc), 300, 30), [])
        self.assertIsNone(C.images_a_refaire(anc, dict(anc, sig_global="autre"), 300, 30))   # réglages généraux changés : tout refaire
        self.assertEqual(C.plages([95, 96, 100, 200], [0, 60, 120, 180, 240], 300), [(60, 120), (180, 240)])
        self.assertEqual(C.plages([10, 70], [0, 60, 120], 300), [(0, 120)])


class TestDessinPartage(unittest.TestCase):
    def test_aide_en_echec_morceau_dessine_ici(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import dessin_partage as DP
        d = tempfile.mkdtemp(); ancien = DP.LOCAL; DP.LOCAL = d
        lance = []
        def aides_en_echec(nom, sha, plages):                              # chaque aide signale tout de suite son échec
            for a, b in plages:
                lance.append((a, b)); open(os.path.join(d, f"{nom}_{a}_{b}.echec"), "w").write("panne")
        faits = []
        def plage(a, b, chemin, progres=None): faits.append((a, b)); open(chemin, "w").write(f"{a}-{b}")
        vieux = DP.lancer_aides; DP.lancer_aides = aides_en_echec
        try:
            os.environ["AIDES"] = "3"
            liste = DP.dessiner(400, {"sk": {}}, plage, journal=lambda m: None)
        finally:
            DP.lancer_aides = vieux; DP.LOCAL = ancien; os.environ.pop("AIDES", None)
        self.assertEqual(DP.decouper(400, 4), [(0, 100), (100, 200), (200, 300), (300, 400)])
        self.assertEqual(lance, [(100, 200), (200, 300), (300, 400)])
        self.assertEqual(sorted(faits), [(0, 100), (100, 200), (200, 300), (300, 400)])          # tout dessiné ici, rien de perdu
        self.assertEqual([open(c).read() for c in liste], ["0-100", "100-200", "200-300", "300-400"])   # dans l'ordre
        self.assertEqual(os.listdir(d), [])                                                     # release temporaire vidée


class TestPauseReprise(unittest.TestCase):
    def test_sauver_puis_reprendre(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import dessin_partage as DP, reprise as RP
        d = tempfile.mkdtemp(); ancien = DP.LOCAL; DP.LOCAL = d
        try:
            bloc = os.path.join(tempfile.mkdtemp(), "bloc_0_600.mp4"); open(bloc, "wb").write(b"images")
            ctx = {"phase": "v1", "faits": [(0, 600, bloc)], "sk": {"doublage": {"piste": bloc}}, "base": "sortie/x", "audios": [np.zeros(4, np.float32)]}
            nom = RP.sauver(ctx, [bloc, None, "/inexistant"])
            os.environ["CHAINE"] = f"suite:{nom}|2/3"
            self.assertEqual(RP.demandee(), (nom, "2/3"))
            S = RP.charger(nom)
            self.assertEqual(S["phase"], "v1"); self.assertEqual(S["faits"][0][:2], (0, 600))
            self.assertNotEqual(S["faits"][0][2], bloc); self.assertEqual(open(S["faits"][0][2], "rb").read(), b"images")   # copie locale
            self.assertEqual(S["sk"]["doublage"]["piste"], S["faits"][0][2])
            RP.nettoyer(nom); self.assertEqual(os.listdir(d), [])
        finally:
            DP.LOCAL = ancien; os.environ.pop("CHAINE", None)
        self.assertEqual(RP.demandee(), (None, None))


class TestQualiteVisuelle(unittest.TestCase):
    def test_levres_par_sons(self):
        import levres
        self.assertEqual(levres.phonemes("papa"), ["M", "A", "M", "A"])
        self.assertEqual(levres.phonemes("oui"), ["U", "I"])
        self.assertEqual(levres.phonemes("chaussure")[:2], ["CH", "O"])
        self.assertNotIn("S", levres.phonemes("grands"))                     # lettres muettes de fin de mot
        seg = levres.chronologie([("Papa, oui", 1.0, 2.0)])
        self.assertEqual(levres.forme(seg, 1.01), "M"); self.assertIsNone(levres.forme(seg, 3.0))
        seg2 = levres.chronologie([], [("oui", 0.2, 0.6)], 10.0)               # instants exacts des mots (transcription)
        self.assertEqual(levres.forme(seg2, 10.25), "U"); self.assertEqual(levres.forme(seg2, 10.55), "I")

    def test_controle_image(self):
        import cartoon
        tetes = [dict(t=1.0, role="a", x=-30.0, y=800.0, rx=120.0, ry=130.0, plan="moyen", seul=None, parle=True, i=0, sous_titre=False),
                 dict(t=1.0, role="b", x=600.0, y=1650.0, rx=120.0, ry=130.0, plan="serre", seul=None, parle=True, i=0, sous_titre=True),
                 dict(t=1.0, role="c", x=650.0, y=1600.0, rx=120.0, ry=130.0, plan="serre", seul=None, parle=False, i=0, sous_titre=True)]
        types = {d["type"] for d in cartoon.controle_image(tetes)}
        self.assertEqual(types, {"tete_coupee", "sous_titre_visage", "chevauchement"})

    def test_jeu_exagere(self):
        import studio
        ph = [dict(i=0, p="a", scene=0, deb=0.0, fin=1.5, emo="neutre", texte="Quoi ?", chute=False, cam="large"),
              dict(i=1, p="b", scene=0, deb=1.6, fin=3.0, emo="cri", texte="Dégage !", chute=True, cam="serre")]
        B = {"graine": 3, "plans": [], "jeu": [{"replique": 0, "emotion": "choc", "geste": "desespoir", "intensite": 3}]}
        studio.realiser(ph, {0: ["a", "b"]}, B)
        self.assertEqual((ph[0]["emo"], ph[0]["geste"], ph[0]["intensite"]), ("choc", "desespoir", 3))
        self.assertEqual(ph[1]["intensite"], 2)                              # cri : joué fort même sans IA


class TestHumains(unittest.TestCase):
    """Personnages adultes (casting libre) ."""
    def setUp(self):
        try:
            import humain, studio, marionnette
        except Exception as e: self.skipTest(f"dépendances vidéo absentes : {e}")
        self.H, self.S, self.M = humain, studio, marionnette

    def test_fiches_et_dessin(self):
        H, M = self.H, self.M
        self.assertEqual(H.creer(5), H.creer(5)); self.assertNotEqual(H.creer(5), H.creer(6))       # même épisode = même casting
        f = H.creer(3, genre="f", age=70, cheveux="chignon"); self.assertEqual((f["genre"], f["age"], f["cheveux"]), ("f", 70, "chignon"))
        img = np.zeros((1920, 1080, 3), np.uint8); img[:] = 200
        for k, st in enumerate(H.COIFFURES_H + H.COIFFURES_F):
            p = M.pose_neutre(); p.update(x=540, y=1500, s=1.0, mains=True, main_forme_g=M.FORMES_MAIN[k % 5], main_forme_d="index", yeux=M.YEUX[k % len(M.YEUX)],
                                          forme=M.BOUCHES[k % len(M.BOUCHES)], viseme=("A", "M", None)[k % 3], bouche=0.5, sourcils=M.SOURCILS[k % len(M.SOURCILS)],
                                          costume=dict(haut=M.HAUTS[k % len(M.HAUTS)], c_haut=(90, 120, 200), motif=M.MOTIFS[k % 4], bas=M.BAS[k % 5], details=M.DETAILS),
                                          dos=(k == 4), effets=("goutte",), epaules=0.5, penche=0.5, pied=1.0)
            H.dessiner(img, H.creer(k, cheveux=st, lunettes="rondes", barbe="courte"), p)
        tete, (rx, ry), mains = H.reperes(H.creer(1), dict(M.pose_neutre(), x=540, y=1500, s=1.0))
        self.assertTrue(650 < tete[1] < 1000 and 400 < tete[0] < 700); self.assertEqual(len(mains), 2)
        self.assertLess(H.tete_y(1.0), H.tete_y(0.5)); self.assertGreater(1500 - H.tete_y(1.0), 2 * H.hauteur_tete(1.0))   # adulte : au moins 3 têtes de haut

    def test_garde_robe_themes_et_lieux(self):
        S, M, H = self.S, self.M, self.H
        import decor_dessin as DD
        img = np.zeros((1920, 1080, 3), np.uint8); img[:] = 200
        for k, st in enumerate(M.GR.COIFFURES):                                                     # chaque coiffure, barbe, chapeau, haut, motif
            c = dict(haut=M.HAUTS[k % len(M.HAUTS)], c_haut=(90, 120, 200), motif=M.MOTIFS[k % len(M.MOTIFS)], bas="jean",
                     chapeau=M.CHAPEAUX[k % len(M.CHAPEAUX)], details=(M.GR.BARBES[k % 4], "sac_bandouliere", "casque_audio"))
            H.dessiner(img, H.creer(k, cheveux=st), dict(M.pose_neutre(), x=540, y=1500, s=1.0, costume=c, mains=True, bouche=0.8, viseme="A"))
        sk = {"repliques": [{"p": "presentateur", "t": "Ugh, moi trouver feu dans la caverne"}, {"p": "envoyee", "t": "Encore ?"}]}
        B = S.bible(sk, ["presentateur", "envoyee"])
        self.assertEqual(B["lieux"][0], "caverne"); self.assertEqual(B["costumes"]["presentateur"]["haut"], "tunique")
        self.assertIn("barbe", B["costumes"]["presentateur"]["details"])                 # barbe mal rasée, jamais de grosse barbe
        self.assertEqual(DD.lieu_de("je dois aller à la CAF pour mon dossier"), "administration")
        for l in ("administration", "hall", "caverne", "palais"):
            r = DD.dessiner(l, {"moment": "soir"}, 3); self.assertEqual(r["fond"].shape, (1920, 1080, 3))

    def test_montage_dynamique(self):
        S = self.S
        lv = np.abs(np.sin(np.arange(150) / 6.0)).astype(np.float32)
        ph = [dict(i=i, p=("presentateur", "invite")[i % 2], deb=i * 5.2, fin=i * 5.2 + 5.0, lv=lv, emo=("neutre", "cri", "neutre")[i], scene=0,
                   chute=i == 2, texte="Bonjour à tous ?", plan="serre", mouvement="fixe") for i in range(3)]
        P = S.decouper(ph, {0: ["presentateur", "invite"]}, {"graine": 3, "rythme": {}}, 30)
        self.assertGreaterEqual(len(P), 6)                                                          # plusieurs plans par réplique
        self.assertTrue(any(x["plan"] in S.LARGES for x in P) and any(x["plan"] in S.SERRES for x in P))
        self.assertTrue(any(x["cible"] == "invite" and ph[x["j"]]["p"] == "presentateur" for x in P))   # plan de réaction
        for a_, b_ in zip(P, P[1:]):
            self.assertAlmostEqual(a_["t1"], b_["t0"], places=3); self.assertGreater(b_["t1"] - b_["t0"], 0.3)
            self.assertNotEqual((a_["cible"], a_["plan"]), (b_["cible"], b_["plan"]))
        cri = [x for x in P if x["j"] == 1]; calme = [x for x in P if x["j"] == 0]
        self.assertGreaterEqual(len(cri), len(calme))                                               # la dispute coupe plus vite

    def test_mode_payant_connait_tout(self):
        S, M = self.S, self.M
        import decor_dessin as DD, doublage
        t = S.consigne_studio()
        for x in list(DD.LIEUX) + list(M.CHAPEAUX) + list(M.GR.BARBES) + ["redingote", "ondule", "fleurs", "cadence", "tres_serre", "zoom_choc"]:
            self.assertIn(x, t)
        self.assertIn("cadence", doublage.consigne("- A : 120 Hz", "0. A (0.0-1.0) : Bonjour"))
        sk = {"repliques": [{"p": "presentateur", "t": "Bonjour"}, {"p": "invite", "t": "Salut"}],
              "studio": {"cadence": "rapide", "costumes": {"presentateur": {"haut": "chemise", "chapeau": "melon", "details": ["barbe_courte"]}},
                         "personnages": {"invite": {"genre": "h", "age": 30, "cheveux": "afro", "barbe": "bouc"}}}}
        B = S.bible(sk, ["presentateur", "invite"])
        self.assertEqual(B["cadence"], "rapide"); self.assertEqual(B["costumes"]["presentateur"]["chapeau"], "melon")
        self.assertEqual((B["fiches"]["invite"]["cheveux"], B["fiches"]["invite"]["barbe"]), ("afro", "bouc"))

    def test_casting(self):
        S = self.S
        sk = {"repliques": [{"p": "presentateur", "t": "Mamie, tu veux du thé ?"}, {"p": "invite", "t": "Oui mon chéri."}], "doublage": {"source": "x"},
              "_voix_hz": {"presentateur": 120, "invite": 230}}
        F = S.casting(sk, ["presentateur", "invite"], {"invite": {"cheveux": "chignon", "c_cheveux": (200, 200, 200), "details": ("lunettes_vue",)}}, {}, 7)
        self.assertEqual((F["presentateur"]["genre"], F["invite"]["genre"]), ("h", "f"))                 # la voix décide
        self.assertEqual(F["invite"]["age"], 70); self.assertEqual(F["invite"]["cheveux"], "chignon"); self.assertEqual(F["invite"]["lunettes"], "rondes")
        sk2 = {"repliques": [{"p": "envoyee", "t": "Salut."}]}                                          # sketch écrit : Lila est une femme
        self.assertEqual(S.casting(sk2, ["envoyee"], {}, {}, 1)["envoyee"]["genre"], "f")


class TestStyleToon(unittest.TestCase):
    """Nouveau style de personnage (référence de l'auteur) : il dessine toutes les poses et la bouche reste dans le visage."""
    def test_poses_et_bouche(self):
        import humain as HU, marionnette as M, studio, toon
        F = HU.creer(3, genre="h", age=30)
        for nom, (bras, _) in list(studio.GESTES.items())[:8]:
            for tq, ouv in ((0.0, 0.0), (0.5, 0.8), (-0.5, 0.3)):
                img = np.full((1920, 1080, 3), 200, np.uint8)
                p = dict(M.pose_neutre(), x=540, y=1700, s=1.2, tq=tq, bras_g=bras[0], bras_d=bras[1], bouche=ouv, viseme="A", mains=True,
                         costume=dict(haut="capuche", c_haut=(30, 190, 40), bas="short", c_bas=(30, 190, 40), chaussures="pieds_nus", details=("lunettes_soleil",)))
                (tx, ty), (rx, ry) = HU.dessiner(img, F, p)
                self.assertGreater((np.abs(img.astype(int) - 200).sum(2) > 30).mean(), 0.03)
        K = toon.squelette(dict(M.pose_neutre(), x=540, y=1700, s=1.2, bras_g=studio.POSES["croises"][0], bras_d=studio.POSES["croises"][1], adulte=True))
        self.assertGreater(K["croise"], 0.9)                                                            # bras croisés reconnus
        self.assertGreater(K["bras"][0][2][0], 540)                                                    # main gauche de l'autre côté


class TestStyleCroquis(unittest.TestCase):
    """Style croquis (défaut, validé par l'auteur) : personnage dessiné, tête au même endroit, petit et grand, rapide."""

    def test_dessin_et_reperes(self):
        import time, humain as HU, marionnette as M, perso_croquis as P
        vus = set()
        for g in range(12):
            F = HU.creer(g); vus.add(P.silhouette(F))
            img = np.full((1920, 1080, 3), 200, np.uint8)
            p = dict(M.pose_neutre(), x=540, y=1500, s=1.0, emo="joie", bouche=0.6, viseme="O", costume={"haut": "capuche", "c_haut": (90, 130, 190), "chapeau": "casquette"})
            t = time.time(); (tx, ty), (rx, ry) = P.dessiner(img, F, HU._pose(F, p))
            self.assertLess(time.time() - t, 1.5)                                      # rapide (petit cadre autour du personnage)
            self.assertTrue((img != 200).any())
            (hx, hy), _, mains = P.reperes(F, HU._pose(F, p)); self.assertAlmostEqual(hx, tx); self.assertEqual(len(mains), 2)
            self.assertLess(hy, 1500)
        self.assertEqual(vus, {"petit", "grand"})                                      # les deux silhouettes (choix de l'auteur)

    def test_style_par_defaut(self):
        src = open(os.path.join(ICI, "..", "moteur", "humain.py"), encoding="utf-8").read()
        self.assertIn('os.environ.get("STYLE_PERSO") or "croquis"', src)


class TestListeCroquis(unittest.TestCase):
    """Liste de l'auteur créée avec le style croquis : 39 lieux, 45 métiers, tenues, accessoires, assis, micro-expressions."""

    def test_lieux(self):
        import decor_dessin as D, decor_lieux as DL
        self.assertEqual(len(DL.LIEUX), 39)
        for l in DL.LIEUX:
            r = D.dessiner(l, {"moment": "jour"}, 3); self.assertEqual(r["fond"].shape, (1920, 1080, 3))
            if r.get("avant") is not None: self.assertGreater(r["avant"][..., 3][:1300].mean(), -1)
        self.assertEqual(D.lieu_de("on se retrouve à la plage"), "plage"); self.assertEqual(D.lieu_de("on est aux urgences"), "urgences")
        self.assertEqual(D.lieu_de("maman, t'as vu le film à la télé ?"), "salon")    # les anciens lieux gagnent à égalité

    def test_metiers_et_tenues(self):
        import humain as HU, marionnette as M, metiers as MT, perso_croquis as P, studio
        self.assertGreaterEqual(len(MT.CATALOGUE), 82)
        for m in ("pirate", "pere_noel", "zombie", "super_heros", "maitre_nageur"):
            F = HU.creer(4); img = np.full((1920, 1080, 3), 200, np.uint8)
            P.dessiner(img, F, HU._pose(F, dict(M.pose_neutre(), costume=MT.costume(m, {}, "h"))))
            self.assertTrue((img != 200).any())
        self.assertEqual(MT.qui_fait({"repliques": [{"p": "presentateur", "t": "Je suis pirate !"}]}), {"presentateur": "pirate"})
        sk = {"repliques": [{"p": "presentateur", "t": "Allez, on va bronzer à la plage avec ta valise !"}, {"p": "invite", "t": "Ok."}],
              "decoupage": [{"scene": "1", "repliques": [0, 1], "decor": ""}], "doublage": None}
        B = studio.bible(sk, ["presentateur", "invite"])
        self.assertEqual(B["lieux"][0], "plage"); self.assertEqual(B["costumes"]["presentateur"].get("tenue"), "maillot_bain")
        self.assertEqual(sk["repliques"][0].get("objet"), "valise")

    def test_assis_et_micro(self):
        import humain as HU, marionnette as M, perso_croquis as P
        F = HU.creer(5); img = np.full((1920, 1080, 3), 200, np.uint8)
        p = dict(M.pose_neutre(), assis=True, emo="gene", t=1.0)
        self.assertEqual(P._fx(p, "honteux").get("micro"), "mord")
        P.dessiner(img, F, HU._pose(F, p)); self.assertTrue((img != 200).any())


class TestDecorsSemiRealistes(unittest.TestCase):
    """Décors « semi-réalistes » (choix de l'auteur, 1er novembre 2026) : peinture, pieds posés sur le sol libre, réglage STYLE_DECOR."""

    @staticmethod
    def _decor(meuble=None):
        """Faux décor 880x1536 : mur au fond (loin), sol en plan qui se rapproche vers le bas, un meuble éventuel (x0, x1, y0, y1)."""
        h, w = 1536, 880; y = np.arange(h, dtype=np.float32)[:, None]
        prof = np.where(y < 700, 40.0, 40 + (y - 700) / (h - 700) * 200).repeat(w, 1)
        im = np.zeros((h, w, 3), np.uint8); im[:700] = (200, 190, 170); im[700:] = (180, 140, 100)
        if meuble:
            x0, x1, y0, y1 = meuble; prof[y0:y1, x0:x1] = prof[y1 - 1, x0] + 60; im[y0:y1, x0:x1] = (90, 90, 120)
        return im, prof.astype(np.uint8)

    def test_reglage_et_description(self):
        import semi_realiste as SR
        avant = os.environ.pop("STYLE_DECOR", None)
        try:
            self.assertTrue(SR.actif())                                    # semi-réaliste par défaut
            os.environ["STYLE_DECOR"] = "croquis"; self.assertFalse(SR.actif())
        finally:
            os.environ.pop("STYLE_DECOR", None)
            if avant is not None: os.environ["STYLE_DECOR"] = avant
        self.assertIn("[semi]", SR.description("salon")); self.assertIn("living room", SR.description("salon"))
        self.assertIn("pavement", SR.description("rue"))
        self.assertNotIn("canapé", SR.description("salon", "salon avec un canapé beige"))   # français -> description anglaise du lieu
        self.assertIn("evening", SR.description("salon", "", "warm golden evening light"))
        src = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn('data-var="STYLE_DECOR" data-def="semi_realiste"', src); self.assertIn("Semi-réaliste", src)
        self.assertIn("STYLE_DECOR: ${{ vars.STYLE_DECOR }}", open(os.path.join(ICI, "..", ".github", "workflows", "emission.yml"), encoding="utf-8").read())

    def test_pieds_au_sol(self):
        import semi_realiste as SR
        im, prof = self._decor()
        r = SR.cadrer(im, prof, 2); self.assertIsNotNone(r)
        c, pr, z = r; self.assertEqual(c.shape, (1920, 1080, 3)); self.assertEqual(pr.shape, (1920, 1080))
        self.assertTrue((c[SR.PIED_Y, 285] == (180, 140, 100)).all())     # les pieds tombent sur le sol, pas sur le mur
        im, prof = self._decor(meuble=(300, 600, 1200, 1536))              # un meuble au milieu, jusqu'en bas : les pieds l'évitent
        r = SR.cadrer(im, prof, 2)
        if r is not None:
            obs = SR.obstacles(prof); self.assertTrue(obs[1300, 450])
            c = r[0]
            for x in (260, 820): self.assertFalse((c[SR.PIED_Y, x] == (90, 90, 120)).all())
        im, prof = self._decor(meuble=(0, 880, 1100, 1536))                # aucun sol libre : refusé (décor dessiné à la place)
        self.assertIsNone(SR.cadrer(im, prof, 2))

    def test_banque_et_budget(self):
        """Fausse IA Modal : 2 tirages (un sans sol libre, un bon) -> le bon est cadré, rangé dans la banque à part, compté dans le
        budget du mois ; la 2e fois, le lieu est repris de la banque sans rien demander à Modal."""
        import decors, cv2 as _cv
        dossier = tempfile.mkdtemp(); avant = decors.BANQUE, decors.COMPTEUR, decors.UTILISES
        decors.BANQUE = dossier; decors.COMPTEUR = os.path.join(dossier, "compteur.json"); decors.UTILISES = os.path.join(dossier, "u.tsv")
        def png(a): return _cv.imencode(".png", a[..., ::-1] if a.ndim == 3 else a)[1].tobytes()
        mauvais = self._decor(meuble=(0, 880, 1100, 1536)); bon = self._decor()
        appels = []
        class _Rep:
            def get(self, timeout=None): return [[(png(mauvais[0]), png(mauvais[1])), (png(bon[0]), png(bon[1]))]]
        class _Methode:
            def spawn(self, d, g, n): appels.append((d, n)); return _Rep()
        class _Decor:
            generer_semi = _Methode()
        faux = types.SimpleNamespace(Cls=types.SimpleNamespace(from_name=lambda a, b: (lambda: _Decor())))
        sk = {"repliques": [{"p": "presentateur", "t": "Salut"}, {"p": "invite", "t": "Ça va ?"}],
              "decoupage": [{"repliques": [0, 1], "decor": ""}]}
        anc = sys.modules.get("modal"); sys.modules["modal"] = faux
        try:
            self.assertEqual(decors.generes_ce_mois(), 0)
            out = decors.generer_semi(sk)
            self.assertEqual(list(out), [0]); self.assertEqual(decors.SEMI, {0}); self.assertEqual(out[0].shape, (1920, 1080, 3))
            self.assertEqual(len(appels), 1); self.assertEqual(appels[0][1], 3); self.assertNotIn("[semi]", appels[0][0][0])
            self.assertEqual(decors.generes_ce_mois(), 1)                 # compteur tenu à part (plus la date des fichiers)
            os.environ["DECORS_VARIES"] = "0"
            try: out2 = decors.generer_semi(sk)
            finally: os.environ.pop("DECORS_VARIES", None)
            self.assertEqual(list(out2), [0]); self.assertEqual(len(appels), 1)   # repris de la banque
            decors.generer_semi(sk); self.assertEqual(len(appels), 2)     # déjà montré cette semaine : nouveau tirage (audit, idée 8)
            self.assertIn("another angle", appels[1][0][0])
            self.assertIsNone(decors.voisin("cozy living room, sofa, posters on the wall, coffee table, lamp, television", 0.1))   # jamais pour un décor croquis
        finally:
            decors.BANQUE, decors.COMPTEUR, decors.UTILISES = avant
            if anc is None: sys.modules.pop("modal", None)
            else: sys.modules["modal"] = anc

    def test_moteur_garde_la_peinture(self):
        src = open(os.path.join(ICI, "..", "moteur", "cartoon.py"), encoding="utf-8").read()
        self.assertIn('SEMI_ = set(sk.get("_decors_semi") or [])', src); self.assertEqual(src.count("if sc_ in SEMI_: continue"), 2)
        p = open(os.path.join(ICI, "..", "moteur", "principal.py"), encoding="utf-8").read()
        self.assertIn("decors_mod.generer_semi(sk", p); self.assertIn('sk["_decors_semi"] = sorted(decors_mod.SEMI)', p)
        self.assertIn("def generer_semi", open(os.path.join(ICI, "..", "moteur", "decor_modal.py"), encoding="utf-8").read())


class TestDessinRapide(unittest.TestCase):
    """Idée 4 (6 novembre) : les mélanges compilés par Numba donnent EXACTEMENT les mêmes pixels que le calcul NumPy d'avant."""

    def test_memes_pixels(self):
        import rapide, croquis as C
        if rapide.LAVIS is None: self.skipTest("Numba absent")
        rng = np.random.default_rng(3)
        for k in range(12):
            h, w = (int(x) for x in rng.integers(20, 200, 2))
            img = (rng.random((h + 40, w + 40, 3)) * 255).astype(np.uint8); m = np.zeros((h + 40, w + 40), np.uint8)
            m[20:20 + h, 20:20 + w] = (rng.random((h, w)) > 0.3) * 255; coul = tuple(int(x) for x in rng.integers(0, 255, 3))
            a, b = img.copy(), img.copy()
            C._LAVIS_NB, C._HACH_NB = rapide.LAVIS, rapide.HACHURES
            C.lavis(a, m, coul, 0.85, k, bool(k % 2)); C.hachures(a, m, graine=k)
            C._LAVIS_NB, C._HACH_NB = None, None
            try: C.lavis(b, m, coul, 0.85, k, bool(k % 2)); C.hachures(b, m, graine=k)
            finally: C._LAVIS_NB, C._HACH_NB = rapide.LAVIS, rapide.HACHURES
            self.assertTrue(np.array_equal(a, b))
        z = (rng.random((50, 60, 3)) * 255).astype(np.uint8); ao = rng.random((50, 60, 1)).astype(np.float32)
        ac = rng.random((50, 60, 1)).astype(np.float32); co = (rng.random((50, 60, 3)) * 200).astype(np.float32)
        ref = np.clip(z.astype(np.float32) * (1 - 0.2 * ao) * (1 - ac) + co, 0, 255).astype(np.uint8)
        z2 = z.copy(); rapide.COLLER(z2, ao, ac, co); self.assertTrue(np.array_equal(z2, ref))
        ref = (z.astype(np.float32) * (1 - ac)).astype(np.uint8); z3 = z.copy(); rapide.ASSOMBRIR(z3, ac); self.assertTrue(np.array_equal(z3, ref))


class TestImagesDeReference(unittest.TestCase):
    """Idée 46 : 10 images types du dessin comparées aux images validées (tests/references). Changement voulu du dessin :
    python moteur/references.py --refaire (puis regarder les images)."""

    def test_dessin_inchange(self):
        import references as R
        ims = R.images(); self.assertEqual(len(ims), 10)
        for nom, im in ims.items():
            ref = R.lire(nom); self.assertIsNotNone(ref, nom)
            moy, part = R.ecart(im, ref)
            self.assertLess(moy, 1.5, f"{nom} : dessin changé (écart moyen {moy:.2f})")
            self.assertLess(part, 0.01, f"{nom} : dessin changé ({100 * part:.2f} % de pixels différents)")


class TestMetiers(unittest.TestCase):
    def test_metier_entendu_habille_le_bon_personnage(self):
        """« Je suis pompier » : lui ; « t'es plombier ? », « bonjour docteur » : l'autre ; un métier juste cité n'habille personne."""
        import metiers as MT, studio, marionnette as M
        q = lambda *l: MT.qui_fait({"repliques": [{"p": p, "t": t} for p, t in l]})
        self.assertEqual(q(("presentateur", "Bonjour docteur, j'ai mal au ventre."), ("invite", "Asseyez-vous.")), {"invite": "medecin"})
        self.assertEqual(q(("presentateur", "Je suis pompier depuis dix ans."), ("invite", "Ah ouais ?")), {"presentateur": "pompier"})
        self.assertEqual(q(("presentateur", "T'es plombier toi ?"), ("invite", "Ouais.")), {"invite": "plombier"})
        self.assertEqual(q(("presentateur", "Monsieur l'agent, je roulais pas vite."), ("invite", "Vos papiers.")), {"invite": "policier"})
        self.assertEqual(q(("presentateur", "Moi je suis prof, et toi ?"), ("invite", "Moi je suis infirmière.")), {"presentateur": "enseignant", "invite": "infirmier"})
        self.assertEqual(q(("presentateur", "Mon père est plombier."), ("invite", "Les pompiers arrivent !")), {})
        for nom, m in MT.CATALOGUE.items():                               # tout ce que le catalogue demande sait être dessiné
            c = m["costume"]
            self.assertIn(c["haut"], M.HAUTS, nom); self.assertTrue(not c.get("chapeau") or c["chapeau"] in M.CHAPEAUX, nom)
            if m.get("outil"):
                o = M.objet(m["outil"], 0.8); self.assertIsNotNone(o, nom); self.assertGreater(int(o[..., 3].max()), 0, nom)
        sk = {"repliques": [{"p": "presentateur", "t": "Je suis pompier, reculez !"}, {"p": "invite", "t": "Mais c'est ma maison qui brûle !"}],
              "decoupage": [{"scene": "1", "repliques": [0, 1], "decor": "a street"}]}
        B = studio.bible(sk, ["presentateur", "invite"])
        c = B["costumes"]["presentateur"]
        self.assertEqual((c["haut"], c["chapeau"], c["outil"]), ("veste_pompier", "casque_pompier", "lance"))
        self.assertNotEqual(B["costumes"]["invite"].get("metier"), "pompier")


class TestHistoireRecreee(unittest.TestCase):
    def test_lieux_separes_au_telephone(self):
        import studio
        sk = {"repliques": [{"p": "invite", "t": "Allô papa, je suis au parking."}, {"p": "presentateur", "t": "T'es où exactement ?"},
                            {"p": "invite", "t": "Devant le Leclerc."}, {"p": "presentateur", "t": "Je t'entends mal, je te rappelle."}],
              "decoupage": [{"scene": "1", "repliques": [0, 1, 2, 3]}]}
        self.assertTrue(studio.separer_lieux(sk))
        sc = {i: k for k, d in enumerate(sk["decoupage"]) for i in d["repliques"]}
        self.assertEqual(sc[0], sc[2]); self.assertNotEqual(sc[0], sc[1])                 # un décor chacun
        self.assertTrue(all(r.get("objet") == "telephone" for r in sk["repliques"]))
        sk2 = {"repliques": [{"p": "invite", "t": "Salut."}, {"p": "presentateur", "t": "Salut toi."}], "decoupage": []}
        self.assertFalse(studio.separer_lieux(sk2))                                     # même endroit : rien ne change

    def test_ado_et_compagnon(self):
        import studio, humain as H
        sk = {"repliques": [{"p": "invite", "t": "Papa, elle me fait signe."}, {"p": "presentateur", "t": "Vas-y fiston."}],
              "studio": {"personnages": {"invite": {"genre": "h", "age": 22, "cheveux": "long", "barbe": "barbe_pleine"}},
                         "figurants": [{"avec": "invite", "genre": "f", "age": 28, "geste": "signe", "haut": "robe", "c_haut": "rouge"}]}}
        f = studio.casting(sk, ["presentateur", "invite"], {}, sk["studio"], 3)
        self.assertLess(f["invite"]["age"], 18); self.assertEqual(f["invite"]["barbe"], ""); self.assertLess(f["invite"]["taille"], f["presentateur"]["taille"])
        self.assertIn(f["invite"]["cheveux"], H.COURTS_JEUNE_H)
        c = studio.compagnons(sk, [{"repliques": [0, 1]}], ["parking"], "jour", 3)
        self.assertEqual(len(c), 1); self.assertEqual(c[0]["activite"], "signe"); self.assertEqual(c[0]["fiche"]["genre"], "f")


class TestStudio(unittest.TestCase):
    """Rendu détaillé : réalisateur sans IA, garde-robe, décors dessinés, mains et visages."""
    def setUp(self):
        try:
            import studio, decor_dessin, marionnette
        except Exception as e: self.skipTest(f"dépendances vidéo absentes : {e}")
        self.S, self.D, self.M = studio, decor_dessin, marionnette

    def test_emotion_et_geste_sans_indication(self):
        S = self.S
        self.assertEqual(S.emotion_texte("Euh… désolé, j'ai oublié."), "gene")
        self.assertEqual(S.emotion_texte("Non mais t'es sérieux ?", 0.3), "colere")
        self.assertEqual(S.emotion_texte("Non mais t'es sérieux ?", 0.95), "cri")
        self.assertEqual(S.emotion_texte("Hahaha t'es nul"), "rire")
        self.assertEqual(S.emotion_texte("Bonjour madame."), "neutre")
        self.assertEqual(S.geste("Stop, attends deux secondes.", "neutre"), "stop")
        self.assertEqual(S.geste("Allô ? Oui maman.", "neutre"), "telephone")
        for g, (bras, mains) in S.GESTES.items():
            self.assertEqual(len(bras), 2); self.assertTrue(all(m in self.M.FORMES_MAIN for m in mains), g)

    def test_lieu_et_bible(self):
        D, S = self.D, self.S
        self.assertEqual(D.lieu_de("a doctor's office with an examination table"), "cabinet_medical")
        self.assertEqual(D.lieu_de("de l'eau dans un bar ? j'ai sport demain, un verre au bar"), "bar")
        sk = {"sujet": "Prise de sang", "repliques": [{"p": "presentateur", "t": "Combien de verres par semaine ?"}, {"p": "invite", "t": "Deux-trois."}],
              "decoupage": [{"scene": "1", "repliques": [0, 1], "decor": "doctor office"}]}
        B = S.bible(sk, ["presentateur", "invite"])
        self.assertEqual(B["lieux"], ["cabinet_medical"]); self.assertIn(B["moment"], S.MOMENTS)
        self.assertEqual(B["costumes"]["presentateur"]["haut"], "blouse")          # celui qui pose les questions est le médecin
        self.assertNotEqual(B["costumes"]["invite"]["haut"], "blouse")
        self.assertEqual(S.bible(sk, ["presentateur", "invite"])["costumes"], B["costumes"])   # même épisode = mêmes choix
        sk["studio"] = {"moment": "nuit", "lieux": ["bar"], "costumes": {"invite": {"haut": "costume", "c_haut": "bleu marine", "details": ["cravate", "bazooka"]}},
                        "gags": ["Eau : 12 €"], "plans": [{"replique": 1, "plan": "tres_serre", "reaction": "regard_camera"}]}
        B = S.bible(sk, ["presentateur", "invite"])
        self.assertEqual((B["moment"], B["lieux"], B["gags"]), ("nuit", ["bar"], ["Eau : 12 €"]))
        self.assertEqual(B["costumes"]["invite"]["c_haut"], S.NOMS_COULEURS["bleu marine"]); self.assertEqual(B["costumes"]["invite"]["details"], ("cravate",))
        ph = [dict(i=0, p="presentateur", deb=0.0, fin=1.0, emo="neutre", scene=0, texte="Combien ?", chute=False, lv=[0.2]),
              dict(i=1, p="invite", deb=2.0, fin=3.0, emo="neutre", scene=0, texte="Deux.", chute=True, lv=[0.2])]
        S.realiser(ph, {0: ["presentateur", "invite"]}, B)
        self.assertEqual((ph[1]["plan"], ph[1]["reaction"]), ("tres_serre", "regard_camera"))
        self.assertTrue(ph[1]["regard_camera"])                                    # silence d'une seconde avant la réplique
        self.assertTrue(all(q["plan"] in S.PLANS and q["mouvement"] in S.MOUVEMENTS for q in ph))

    def test_memoire(self):
        import tempfile
        S = self.S; ancien = S.MEMOIRE; S.MEMOIRE = os.path.join(tempfile.mkdtemp(), "m.json")
        try:
            S.memoriser({"moment": "soir", "lieux": ["bar"], "costumes": {"invite": {"haut": "pull"}}}, [{"plan": "serre", "mouvement": "fixe"}], 12.3)
            self.assertEqual(S.memoire_recente("moment"), "soir")
        finally: S.MEMOIRE = ancien

    def test_decors_dessines(self):
        D = self.D
        for k, lieu in enumerate(D.LIEUX):
            r = D.dessiner(lieu, {"moment": ("matin", "jour", "soir", "nuit")[k % 4]}, graine=k)
            self.assertEqual(r["fond"].shape, (1920, 1080, 3), lieu)
            if r["avant"] is not None:
                self.assertEqual(r["avant"].shape, (1920, 1080, 4))
                self.assertFalse(r["avant"][800:1300, 300:800, 3].any(), lieu)     # le premier plan ne cache jamais les visages

    def test_marionnettes_detaillees(self):
        M = self.M; img = np.zeros((1920, 1080, 3), np.uint8); img[:] = 200
        for k, haut in enumerate(M.HAUTS):
            p = M.pose_neutre(); p.update(costume=dict(haut=haut, c_haut=(200, 80, 80), motif=M.MOTIFS[k % 4], bas=M.BAS[k % 5], c_bas=(60, 60, 90),
                                                       chaussures=M.CHAUSSURES[k % 5], c_chaussures=(240, 240, 240), details=M.DETAILS),
                                          reflets=True, lumiere=1, ombre=0.3, mains=True, main_forme_g=M.FORMES_MAIN[k % 5], main_forme_d="index",
                                          yeux=M.YEUX[k % len(M.YEUX)], sourcils=M.SOURCILS[k % len(M.SOURCILS)], forme=M.BOUCHES[k % len(M.BOUCHES)],
                                          effets=M.EFFETS, dos=(k == 3), gene=True, paleur=0.5)
            M.dessiner(img, ("bonnet", "casquette", "noeud", "lunettes", "meche")[k % 5], p)
        for nom in M.OBJETS: self.assertIsNotNone(M.objet(nom), nom)
        self.assertEqual(set(ecrire.OBJETS), set(M.OBJETS))

    def test_rendu_detaille_apercu(self):
        try: import cartoon, tempfile, glob
        except Exception as e: self.skipTest(f"dépendances vidéo absentes : {e}")
        if not cartoon.DETAIL: self.skipTest("rendu détaillé coupé")
        sk = {"titre_accroche": "Au bar", "repliques": [{"p": "presentateur", "t": "Je vous sers quoi ?"}, {"p": "invite", "t": "Euh… de l'eau ?"},
                                                         {"p": "presentateur", "t": "Non mais t'es sérieux !", "chute": True}],
              "decoupage": [{"scene": "1", "repliques": [0, 1, 2], "decor": "a bar counter"}],
              "studio": {"plans": [{"replique": 1, "plan": "epaule"}, {"replique": 2, "plan": "contre_plongee"}], "ambiances": ["neon", "poussiere"]}}
        auds = [np.random.default_rng(k).normal(0, 0.2, 22050).astype(np.float32) for k in range(3)]
        import copy as _cp
        sk_large = _cp.deepcopy(sk)
        ancien = os.environ.get("MONTAGE"); os.environ["MONTAGE"] = "dynamique"          # le storyboard (plans voulus) en montage dynamique
        try: d = tempfile.mkdtemp(); total = cartoon.rendre(sk, d, auds, apercu=True)
        finally:
            if ancien is None: os.environ.pop("MONTAGE", None)
            else: os.environ["MONTAGE"] = ancien
        self.assertGreater(total, 3); self.assertEqual(len(glob.glob(d + "/*.png")), 8)
        self.assertEqual(sk["_bible"]["lieux"], ["bar"]); self.assertEqual([q["plan"] for q in cartoon.PH][1:], ["epaule", "contre_plongee"])
        os.environ.pop("MONTAGE", None)                                                  # par défaut : plan large fixe partout
        try: cartoon.rendre(sk_large, tempfile.mkdtemp(), auds, apercu=True)
        finally:
            if ancien is not None: os.environ["MONTAGE"] = ancien
        self.assertEqual({q["plan"] for q in cartoon.PH}, {"large"}); self.assertEqual({q["mouvement"] for q in cartoon.PH}, {"fixe"})


class TestJeuOriginal(unittest.TestCase):
    """Choix de l'auteur du 11 novembre : expressions, tête et doigts de l'original (1, 3), objets vus (4), nom du compte (9)."""

    def _piste(self, t0, t1, bouche, plan=0, x=0.3, **bs):
        ech = []
        for k, t in enumerate(np.arange(t0, t1, 0.125)):
            ech.append((float(t), dict(x=x, y=0.4, bouche=bouche(k), regard=0.0, roll=3.0, pitch=0.0, main=None, plat=0.6,
                                       bs=dict(mouthSmileLeft=bs.get("sourire", 0.0), mouthSmileRight=bs.get("sourire", 0.0)))))
        return {"ech": ech, "plan": plan}

    def test_qui_est_qui(self):
        import jeu_original as J
        reps = [{"p": "presentateur", "_deb": 0.0, "_fin": 2.0}, {"p": "invite", "_deb": 2.0, "_fin": 4.0}]
        parle = lambda k: 0.5 * (k % 2); muet = lambda k: 0.1
        P = [self._piste(0, 2, parle, x=0.3), self._piste(0, 2, muet, x=0.7)]
        self.assertEqual(J.roles_des_pistes(P, reps), ["presentateur", "invite"])   # la piste muette vue en même temps = l'autre

    def test_application_douce(self):
        import jeu_original as J
        d = {"expr": {"invite": [[t, 0.8, 0.1, 0, 0, 0, 0, 0, 0, 0.1, 6.0, 0.0] for t in np.arange(0, 3, 0.25)]},
             "mains": {"invite": [[1.0, 2.0, "pouce"]]}}
        j = J.Jeu(d)
        p = {"emo": "neutre", "tilt": 0.0, "tq": 0.0, "regard": (0.0, 0.0), "bras_d": (0, 0)}
        J.appliquer(p, j, "invite", 1.5, parle=False)
        self.assertEqual(p["emo"], "joie"); self.assertEqual(p["doigts_d"], "pouce"); self.assertEqual(tuple(p["bras_d"]), J.BRAS_DOIGTS["pouce"])
        p2 = {"emo": "colere", "bras_d": (0, 0)}; J.appliquer(p2, j, "invite", 1.5, parle=True); self.assertEqual(p2["emo"], "colere")   # jeu fort gardé
        p3 = {"emo": "neutre"}; J.appliquer(p3, j, "presentateur", 1.5, parle=False); self.assertEqual(p3, {"emo": "neutre"})   # rien lu : rien
        self.assertIsNone(j.valeurs("invite", 9.0))                           # personne à l'image à cet instant dans l'original

    def test_dessin_anime_ignore(self):
        import jeu_original as J, visages
        anc = visages.lire
        visages.lire = lambda v, duree_max=200: [(t, False, [dict(x=0.5, y=0.4, bouche=0.1, regard=0, roll=0, pitch=0, plat=0.9, bs={})]) for t in np.arange(0, 3, 0.125)]
        try:
            f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False); f.close()
            self.assertEqual(J.extraire(f.name, [{"p": "presentateur", "_deb": 0, "_fin": 3}], journal=lambda m: None), {})
        finally: visages.lire = anc

    def test_doigts_dessines(self):
        import croquis as C
        for forme in ("index", "deux", "pouce", "pouce_bas", "poing", "ouverte"):
            img = np.full((200, 200, 3), 240, np.uint8); C.main(img, (100, 100), 20, 0, forme)
            self.assertTrue((img < 200).any(), forme)

    def test_objets_vus(self):
        import objets_vus as O
        reps = [{"p": "presentateur", "_deb": 0.0, "_fin": 3.0}, {"p": "invite", "_deb": 3.0, "_fin": 6.0, "objet": "verre"}]
        vus = [(1.0, "telephone", 0.3), (2.5, "telephone", 0.25), (4.0, "pizza", 0.4), (4.5, "pizza", 0.3), (5.0, "guitare", 0.5)]
        O.attribuer(reps, vus, journal=lambda m: None)
        self.assertEqual(reps[0]["objet"], "telephone"); self.assertEqual(reps[1]["objet"], "verre")   # objet déjà choisi : gardé
        self.assertNotIn("ordinateur", O.CHERCHES)                            # un écran sur un bureau n'est pas un objet tenu

    def test_nom_du_compte(self):
        import marque
        env = dict(os.environ)
        try:
            os.environ["TIKTOK_COMPTE"] = "petitsdramas"; self.assertEqual(marque.compte(), "@petitsdramas")
            os.environ.pop("TIKTOK_COMPTE"); self.assertEqual(marque.compte(), marque.COMPTE)
        finally: os.environ.clear(); os.environ.update(env)
        src = open(os.path.join(ICI, "..", "moteur", "cartoon.py"), encoding="utf-8").read()
        self.assertIn("FIL_Y = 215", src); self.assertNotIn("FILIGRANE, 28, 118", src)
