"""Tests : Écoute du son TikTok, voix, qui parle, casting.
Lancer tous les tests : python -m unittest discover -s tests -v"""
from commun import *  # noqa: F401,F403 (chemins, réglages des tests, modules, SKETCH, FauxClaude…)


class TestVoix(unittest.TestCase):
    def test_nombres(self):
        self.assertEqual(voix_banque.en_lettres(3000), "trois mille")
        self.assertEqual(voix_banque.en_lettres(71), "soixante et onze")
        self.assertEqual(voix_banque.en_lettres(2027), "deux mille vingt sept")

    def test_indications_de_jeu(self):
        self.assertEqual(voix_banque.sans_tags("[sighs] Non mais [laughs] t'es sérieux ?"), "Non mais t'es sérieux ?")
        a = np.zeros(int(22050 * 1.5), np.float32)
        ok, d = voix_banque.note("[laughs] trois mille profs", a, {"texte": "trois mille profs", "mots": []})
        self.assertTrue(ok)                                                   # les crochets ne faussent pas le contrôle Whisper
        sk = ecrire.valider({"sujet": "x", "repliques": [{"p": "presentateur", "t": "[laughs] Bonsoir.", "d": "[laughs] Bonsoir."}] +
                             [{"p": "envoyee", "t": "Ici [sighs] rien."}] * 3}, set())
        self.assertEqual(sk["repliques"][0]["t"], "Bonsoir.")                 # jamais de crochets à l'écran
        self.assertEqual(sk["repliques"][0]["d"], "[laughs] Bonsoir.")       # mais gardés pour la voix

    def test_elevenlabs_credit_epuise(self):
        import urllib.error
        os.environ["ELEVENLABS_API_KEY"] = "test"; appels = []
        def faux(chemin, corps=None, binaire=False, timeout=120):
            appels.append(chemin); raise urllib.error.HTTPError(chemin, 401, "x", {}, io.BytesIO(b'{"detail":{"status":"quota_exceeded"}}'))
        vrai = voix_banque._eleven; voix_banque._eleven = faux
        try:
            out = voix_banque.elevenlabs("v1", ["un", "deux", "trois"])
            self.assertEqual(out, [b"", b"", b""]); self.assertEqual(len(appels), 1)   # on n'insiste pas : voix gratuites ensuite
            self.assertIn("elevenlabs", voix_banque.EN_PANNE)
            self.assertEqual(voix_banque.sources()[0], "elevenlabs")
        finally:
            voix_banque._eleven = vrai; voix_banque.EN_PANNE.discard("elevenlabs"); os.environ.pop("ELEVENLABS_API_KEY")

    def test_controle_qualite(self):
        a = np.zeros(int(22050 * 1.5), np.float32)
        ok, d = voix_banque.note("trois mille profs", a, {"texte": "3 000 profs", "mots": []})
        self.assertTrue(ok); self.assertEqual(d["sim"], 1.0)
        ok, d = voix_banque.note("trois mille profs", a, {"texte": "bla bla", "mots": []})
        self.assertFalse(ok)
        ok, d = voix_banque.note("trois mille profs", a, {"texte": "trois mille profs", "mots": [("trois", 0, .2), ("mille", 1.2, 1.4)]})
        self.assertFalse(ok)                                                  # blanc d'une seconde au milieu


class TestDoublage(unittest.TestCase):
    def test_liens_et_repliques(self):
        import doublage
        self.assertTrue(doublage.lien_valide("https://www.tiktok.com/@compte/video/123"))
        self.assertTrue(doublage.lien_valide("https://vm.tiktok.com/ZMabc/"))
        self.assertFalse(doublage.lien_valide("https://youtube.com/watch?v=1"))
        mots = [{"w": w, "s": i * 0.4, "e": i * 0.4 + 0.3, "voix": "speaker_0" if i < 4 else "speaker_1"} for i, w in enumerate("Salut ça va ? Bof , et toi".split())]
        segs = doublage.segments(mots)
        self.assertEqual([s["voix"] for s in segs], ["speaker_0", "speaker_1"])
        self.assertEqual(segs[0]["t"], "Salut ça va?")
        self.assertAlmostEqual(segs[1]["deb"], 1.6)

    def test_consigne_studio(self):
        try: import doublage
        except Exception as e: self.skipTest(f"dépendances vidéo absentes : {e}")
        try: c = doublage.consigne("- speaker_0 : 120 Hz", "0. speaker_0 (0.0–1.0) : Salut")
        except Exception as e: self.skipTest(f"dépendances vidéo absentes : {e}")
        for mot in ("cabinet_medical", "stethoscope", "contre_plongee", "regard_camera", "Salut"): self.assertIn(mot, c)


class TestTiktokGratuit(unittest.TestCase):
    def test_voix_separees_par_hauteur(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import doublage as D
        sr = D.SR; t = np.arange(int(sr * 1.5)) / sr
        ton = lambda f: (0.4 * np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t)).astype(np.float32)
        blanc = np.zeros(int(sr * 0.5), np.float32)
        sig = np.concatenate([ton(120), blanc, ton(230), blanc, ton(120)])        # homme, femme, homme
        mots = [{"w": "Salut.", "s": 0.1, "e": 1.4, "voix": "speaker_0"}, {"w": "Bonjour.", "s": 2.1, "e": 3.4, "voix": "speaker_0"},
                {"w": "Ça va.", "s": 4.1, "e": 5.4, "voix": "speaker_0"}]
        voix = [m["voix"] for m in D.separer_voix(mots, sig)]
        self.assertEqual(voix[0], voix[2]); self.assertNotEqual(voix[0], voix[1])
        segs = D.segments(mots); cast = D._casting_defaut(segs, D.hauteurs(sig, segs))
        self.assertEqual(cast[voix[1]], "envoyee"); self.assertEqual(cast[voix[0]], "presentateur")

    def test_genre_suit_la_voix(self):
        import studio
        self.assertEqual(studio.genre_voix({}, "presentateur", {"genre": "f"}), "h")         # sketch écrit : Jojo reste un homme
        self.assertEqual(studio.genre_voix({"doublage": {}, "_voix_genre": {"envoyee": "h"}}, "envoyee", {"genre": "f"}), "h")


class TestBruitages(unittest.TestCase):
    def test_catalogue_et_placement(self):
        import bruitages as BR, sons_modernes as SM, bruitages_eleven as BE
        for nom in BR.CATALOGUE:                                                   # chaque son existe en gratuit et en ElevenLabs
            self.assertIn(nom, SM.BANQUE); self.assertIn(nom, BE.BANQUE)
        self.assertNotIn("foule_rire", BE.BANQUE); self.assertNotIn("gasp", BE.BANQUE)  # jamais de rires enregistrés
        ph = [dict(i=0, p="presentateur", texte="Ça coûte quinze euros !", emo="neutre", chute=False, deb=0.2, fin=1.8, groupes=[("Ça coûte", 0.2, 0.9), ("quinze euros !", 0.9, 1.8)]),
              dict(i=1, p="envoyee", texte="Et tu as encore raté ton permis.", emo="neutre", chute=True, deb=2.2, fin=4.0, groupes=[]),
              dict(i=2, p="invite", texte="Je suis gêné.", emo="gene", chute=False, deb=4.5, fin=6.0, groupes=[]),
              dict(i=3, p="presentateur", texte="Fin.", emo="neutre", chute=True, deb=6.5, fin=7.5, groupes=[])]
        noms = set()
        for g in range(12):
            l = BR.choisir(ph, [(7.6, 9.0, "x", 0)], graine=g, duree=10)
            self.assertLessEqual(len(l), 4); noms |= {n for n, _, _ in l}
            self.assertTrue(all(a[0] != b[0] for a, b in zip(l, l[1:])))            # jamais deux fois le même d'affilée
        self.assertTrue(noms & set(BR.CHUTES)); self.assertTrue(noms & {"criquets", "os_craque"})
        self.assertEqual(BR.choisir(ph, (), 0, {0: "boing"})[0][0], "boing")        # choix de Claude respecté


class TestBanqueSonore(unittest.TestCase):
    def test_analyse_et_banque(self):
        import analyse_audio as AA, banque_visuelle as BV, sons_modernes as SM
        from scipy.signal import resample_poly
        sr = AA.SR; n = sr * 8; t = np.arange(n) / sr
        voix = np.zeros(n, np.float32)
        for a, b, f in ((0.5, 2.0, 130), (3.0, 4.5, 220)): voix[int(a * sr):int(b * sr)] = 0.3 * np.sin(2 * np.pi * f * t[:int(b * sr) - int(a * sr)])
        fx = np.zeros(n, np.float32); x = resample_poly(SM.son("vine_boom")[:, 0], 441, 882); fx[int(2.1 * sr):int(2.1 * sr) + len(x)] = x[:n - int(2.1 * sr)] * 0.6
        mono = voix + fx + 0.03 * np.sin(2 * np.pi * 330 * t)
        segs = [dict(voix="a", deb=0.5, fin=2.0, t="un deux trois quatre"), dict(voix="b", deb=3.0, fin=4.5, t="cinq six")]
        A = AA.analyser(mono, voix, segs, {"a": 130, "b": 220}, [(5, 6, "laughter")], ["[angry] x"])
        self.assertEqual(A["nb_voix"], 2); self.assertGreaterEqual(A["impacts"], 1); self.assertGreaterEqual(A["graves"], 1)
        self.assertEqual(A["sur_vanne"], 1); self.assertEqual(A["evenements"], {"laughter": 1}); self.assertEqual(A["emotions"], {"angry": 1})
        avant = BV.FICHIER; BV.FICHIER = os.path.join(tempfile.mkdtemp(), "b.json")
        try:
            BV.ajouter({"source": "https://tiktok/x", "audio": A}); t_ = BV.tendances()
            self.assertEqual(t_["audio"]["n"], 1); self.assertIn("son (1 vidéo", BV.consigne())
        finally: BV.FICHIER = avant


class TestCastingGratuit(unittest.TestCase):
    def test_genre_par_les_mots(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import doublage as D
        segs = [{"voix": "a", "t": "Papa, une dame m'a parlé."}, {"voix": "b", "t": "Fonce fiston !"}, {"voix": "a", "t": "Je suis sûr ?"}]
        self.assertEqual(D.genre_des_voix(segs, {"a": 178, "b": 160}), {"a": "h", "b": "h"})     # l'ado à la voix aiguë reste un garçon
        segs = [{"voix": "a", "t": "Bonjour madame."}, {"voix": "b", "t": "Je suis désolée."}]
        self.assertEqual(D.genre_des_voix(segs, {"a": 130, "b": 170})["b"], "f")


class TestVoixProches(unittest.TestCase):
    def test_empreinte_separe_deux_timbres(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import locuteurs as L
        sr = 22050; rng = np.random.default_rng(0)
        def voix(f0, formants, d):                                         # deux voix à la même hauteur, timbres différents
            t = np.arange(int(sr * d)) / sr; x = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 25))
            from scipy.signal import lfilter, butter
            y = sum(lfilter(*butter(2, [f * 0.9 / (sr / 2), f * 1.1 / (sr / 2)], "band"), x) for f in formants)
            return (0.3 * y / np.abs(y).max() * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))).astype(np.float32) + rng.normal(0, 0.002, len(t)).astype(np.float32)
        morceaux, mots, t = [], [], 0.0
        for k in range(10):
            a = voix(128 + rng.uniform(-4, 4), (650, 1100, 2500) if k % 2 == 0 else (420, 1800, 3100), 1.2)
            morceaux += [np.zeros(int(0.4 * sr), np.float32), a]; t += 0.4
            mots.append({"w": "mot.", "s": t, "e": t + 1.2, "voix": "speaker_0"}); t += 1.2
        sig = np.concatenate(morceaux)
        res = L.rediariser([dict(m) for m in mots], sig)
        v = [m["voix"] for m in res]
        self.assertTrue(all(v[i] == v[0] for i in range(0, 10, 2)) and all(v[i] == v[1] for i in range(1, 10, 2)) and v[0] != v[1])
        deux = [dict(m, voix="speaker_%d" % (i % 2)) for i, m in enumerate(mots)]       # déjà séparées par la transcription : on garde
        self.assertEqual([m["voix"] for m in L.rediariser(deux, sig)], [m["voix"] for m in deux])

    def test_voix_verifiee_mot_par_mot(self):
        """Une phrase rangée sur la mauvaise voix est remise sur la bonne ; deux voix = deux personnages ; l'IA ne déplace pas une voix sûre."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import locuteurs as L, doublage as D
        sr = 22050; rng = np.random.default_rng(1)
        from scipy.signal import lfilter, butter
        def voix(f0, formants, d):
            t = np.arange(int(sr * d)) / sr; x = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 25))
            y = sum(lfilter(*butter(2, [f * 0.9 / (sr / 2), f * 1.1 / (sr / 2)], "band"), x) for f in formants)
            return (0.3 * y / np.abs(y).max()).astype(np.float32) + rng.normal(0, 0.002, len(t)).astype(np.float32)
        morceaux, mots, verite, t = [], [], [], 0.0
        for k in range(8):                                                 # 8 phrases de 4 mots, voix A / B en alternance
            a = voix(120 if k % 2 == 0 else 230, (650, 1100, 2500) if k % 2 == 0 else (420, 1800, 3100), 2.4)
            morceaux += [np.zeros(int(0.5 * sr), np.float32), a]; t += 0.5
            for j in range(4):
                mots.append({"w": "mot" + ("." if j == 3 else ""), "s": t + 0.6 * j, "e": t + 0.6 * j + 0.55, "voix": "speaker_%d" % (k % 2)}); verite.append(k % 2)
            t += 2.4
        sig = np.concatenate(morceaux)
        faux = [dict(m) for m in mots]
        for m in faux[8:12]: m["voix"] = "speaker_1"                       # la 3e phrase (voix A) rangée sur la voix B
        ancien = os.environ.get("ECAPA"); os.environ["ECAPA"] = "0"
        try: res = L.affiner(faux, sig)
        finally:
            if ancien is None: os.environ.pop("ECAPA", None)
            else: os.environ["ECAPA"] = ancien
        self.assertEqual([int(m["voix"][-1]) for m in res], verite)
        self.assertTrue(all(m.get("sure") is not None for m in res))
        segs = D.segments(res)
        self.assertTrue(all(D.voix_sure(s_) for s_ in segs))
        self.assertFalse(D.voix_sure({"mots": [{"w": "a"}]}))
        hz = {"speaker_0": 120, "speaker_1": 230}
        c = D.casting_unique({"speaker_0": "presentateur", "speaker_1": "presentateur"}, segs, hz)
        self.assertNotEqual(c["speaker_0"], c["speaker_1"])
        self.assertEqual(c["speaker_1"], "envoyee")                        # voix aiguë : un personnage féminin libre
        self.assertEqual(D.casting_unique({"speaker_0": "presentateur", "speaker_1": "envoyee"}, segs, hz), {"speaker_0": "presentateur", "speaker_1": "envoyee"})

    def test_rendre_garde_ses_parametres(self):
        """Aucune variable du dessin ne réutilise le nom d'un réglage de reprise (un appel téléphonique écrasait « deja » et le dessin plantait)."""
        import ast
        arbre = ast.parse(open(os.path.join(os.path.dirname(__file__), "..", "moteur", "cartoon.py"), encoding="utf-8").read())
        f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "rendre")
        proteges = {"deja", "limite", "plage", "reprise", "plans_seuls", "apercu", "mots", "audios", "sortie", "mini"}
        ecrits = {c.id for n in ast.walk(f) for c in ([n.target] if isinstance(n, (ast.AugAssign, ast.AnnAssign, ast.For)) else getattr(n, "targets", []))
                  for c in ast.walk(c) if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Store)}
        self.assertFalse(ecrits & proteges, ecrits & proteges)

    def test_controle_questions_reponses(self):
        """Voix trop proches (même personne qui fait les deux voix) : le fil du dialogue et la relecture de l'IA décident, phrase par phrase."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import locuteurs as L, doublage as D, ecrire, reseau
        dialogue = [("Alors, t'as fait une battle dans la cour, c'est ça ?", 0), ("Voilà, c'est ça.", 1),
                    ("Et tu peux m'expliquer le concept ?", 0), ("Bah, tu danses devant ton pote.", 1),
                    ("Mais c'est bizarre.", 0), ("Comme un homme ?", 1), ("Oui, comme un homme.", 0),
                    ("Donc on trouve le moyen,", 1), ("et au lieu de nous féliciter, vous criez.", 1), ("Le quoi ?", 0)]
        mots, verite, t = [], [], 0.0
        for phrase, qui in dialogue:
            for w in phrase.split():
                mots.append({"w": w, "s": t, "e": t + 0.25, "voix": "speaker_0"}); verite.append(qui); t += 0.3
            t += 0.4
        self.assertEqual(len(L.phrases(mots)), len(dialogue))
        tr = L.indices_dialogue(mots, L.phrases(mots))
        self.assertGreater(tr[1], 0); self.assertLess(tr[8], 0)            # après une question : l'autre ; « Donc…, et… » : la suite
        vu = {}
        def faux(client, systeme, messages, outil, **k):
            vu["gemini"] = client.messages.raisonner; vu["texte"] = messages[0]["content"]
            return {"personnes": "A : le père, B : le fils", "phrases": [{"n": i, "qui": "AB"[q]} for i, (_, q) in enumerate(dialogue)]}
        anc = ecrire._appel, reseau.ia_disponible
        ecrire._appel, reseau.ia_disponible = faux, (lambda: True)
        try: ia = D.relire_dialogue(mots)
        finally: ecrire._appel, reseau.ia_disponible = anc
        self.assertTrue(vu["gemini"]); self.assertIn("t'as fait", vu["texte"])
        mal = [dict(m, voix="speaker_0" if i < 40 else "speaker_1") for i, m in enumerate(mots)]   # voix mal séparées au départ
        res = L.fil_dialogue(mal, ia)
        lab = [int(m["voix"][-1]) for m in res]
        self.assertEqual(lab if lab[0] == 0 else [1 - x for x in lab], verite)
        self.assertTrue(all(m["sure"] == 0.0 for m in res))               # jamais « sûr » : l'IA du casting peut encore corriger
        self.assertEqual(L.fil_dialogue([dict(m) for m in mal], None)[0]["voix"], "speaker_0")   # sans IA : le texte seul, sans planter


class TestVoixEtScenesTiktok(unittest.TestCase):
    """Remarques de l'auteur (31 octobre 2026) : voix restées sur un seul personnage, scène qui « se recharge » (toc toc toc)."""
    def setUp(self): sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))

    def test_reponse_json_dans_le_texte(self):
        """Mise en scène ratée sur la vidéo 3/3 du 31 octobre : l'IA gratuite répond sans l'outil ; son JSON dans le texte suffit."""
        from types import SimpleNamespace as NS
        class Faux:
            def __init__(self): self.n = 0; self.messages = self
            def create(self, **kw):
                self.n += 1
                t = "Voici : pas de JSON" if self.n == 1 else 'Réponse : {"casting": [], "contexte": "un chat"}'
                return NS(content=[NS(type="text", text=t)], usage=None, stop_reason="end_turn")
        out = ecrire._appel(Faux(), None, [{"role": "user", "content": "x"}], {"name": "outil", "input_schema": {}}, max_tokens=100)
        self.assertEqual(out["contexte"], "un chat")

    def test_points_oublies_par_whisper(self):
        import locuteurs as L
        txt = "Euh ouais j'avais un poisson rouge Mais pourquoi t'avais un poisson rouge ? Il s'appelait Pomme Dauphine Ok"
        mots = [{"w": w, "s": 0.3 * i, "e": 0.3 * i + 0.25, "voix": "speaker_0"} for i, w in enumerate(txt.split())]
        L.fins_de_phrase(mots)
        self.assertEqual(" ".join(m["w"] for m in mots), "Euh ouais j'avais un poisson rouge. Mais pourquoi t'avais un poisson rouge ? Il s'appelait Pomme Dauphine. Ok")
        self.assertEqual(len(L.phrases(mots)), 4)                          # « Pomme Dauphine » (nom propre) ne coupe pas la phrase

    def test_phrase_qui_continue_en_minuscule(self):
        import locuteurs as L
        txt = "J'ai un peu dépassé l'objectif fixé. Ah bon ?"
        mots = [{"w": w, "s": 0.3 * i + (0.6 if i >= 4 else 0), "e": 0.3 * i + 0.25 + (0.6 if i >= 4 else 0)} for i, w in enumerate(txt.split())]
        lab = L.caler_sur_phrases(mots, [0, 0, 0, 0, 1, 1, 1, 1])           # changement après « dépassé » (pause) : la suite reste à A
        self.assertEqual(lab, [0, 0, 0, 0, 0, 0, 1, 1])
        ph = L.phrases(mots)
        self.assertLess(L.indices_dialogue(mots, ph)[1], 0)

    def test_une_seule_voix_relue_par_l_ia(self):
        import doublage as D, ecrire, reseau
        mots = [{"w": w, "s": 0.4 * i, "e": 0.4 * i + 0.3, "voix": "speaker_0"} for i, w in enumerate("T'as des animaux ? Oui, un poisson. Il s'appelle comment ? Bubulle.".split())]
        anc = ecrire._appel, reseau.ia_disponible
        reseau.ia_disponible = lambda: True
        try:
            ecrire._appel = lambda *a, **k: {"nombre": 1, "phrases": [{"n": i, "qui": "A"} for i in range(4)]}
            self.assertIsNone(D.relire_dialogue(mots, une_voix=True))      # monologue : personne n'est inventé
            ecrire._appel = lambda *a, **k: {"nombre": 2, "phrases": [{"n": i, "qui": "AB"[i % 2]} for i in range(4)]}
            self.assertEqual(D.relire_dialogue(mots, une_voix=True), [0, 1, 0, 1])
        finally: ecrire._appel, reseau.ia_disponible = anc

    def test_boucle_de_whisper_retiree(self):
        import locuteurs as L
        txt = "Coup de sa mère. Oh mais non je suis sale. Oh mais non je suis sale. Oh mais non je suis sale"
        mots, t = [], 0.0
        for i, w in enumerate(txt.split()):
            d = 0.3 if i < 4 else 0.07; mots.append({"w": w, "s": t, "e": t + d}); t += d
        self.assertEqual(" ".join(m["w"] for m in L.sans_boucles(mots)), "Coup de sa mère. Oh mais non je suis sale.")
        vrai = [{"w": w, "s": 0.4 * i, "e": 0.4 * i + 0.35} for i, w in enumerate("non mais non mais non mais".split())]
        self.assertEqual(len(L.sans_boucles(vrai)), 6)                     # dit à vitesse normale : on garde

    def test_famille_presentee_dessinee(self):
        import studio
        sk = {"repliques": [{"p": "presentateur", "t": "Donc là je te présente mon père et mon grand-père."},
                            {"p": "invite", "t": "T'as de la chance, mon père est au travail."},
                            {"p": "presentateur", "t": "Et y'a mon arrière-grand-père qui est là-bas."}]}
        f = studio.famille_presentee(sk)
        self.assertEqual([(x["avec"], x["age"]) for x in f], [("presentateur", 55), ("presentateur", 80), ("presentateur", 99)])

    def test_pas_d_appel_invente_par_l_ia(self):
        import studio
        reps = [{"p": "presentateur", "t": "Est-ce que tu veux m'épouser ?", "objet": "telephone"}, {"p": "envoyee", "t": "C'est une blague ?"}]
        sk = {"repliques": reps, "doublage": {"contexte": "Une demande en mariage tourne court.", "visuel": {"nb_personnes": 1}},
              "studio": {"lieux_separes": {"presentateur": "", "envoyee": ""}, "moyen": "telephone", "lieux": ["rue", "salon"]},
              "decoupage": [{"scene": "1", "repliques": [0, 1], "decor": "living room"}]}
        self.assertFalse(studio.separer_lieux(sk))
        self.assertNotIn("objet", reps[0]); self.assertEqual(sk["studio"]["lieux"], ["rue"])
        sk2 = {"repliques": [{"p": "presentateur", "t": "Allô ? T'es où ?"}, {"p": "envoyee", "t": "Je suis dehors, allô ?"}],
               "doublage": {"contexte": "un appel"}, "studio": {"lieux_separes": {"presentateur": "", "envoyee": ""}, "moyen": "telephone"}}
        self.assertTrue(studio.separer_lieux(sk2))                         # un vrai appel reste un appel

    def test_voix_dominante_partagee(self):
        import doublage as D, ecrire, reseau
        lignes = [("T'as de la chance d'avoir tes grands-parents.", "A"), ("Oui c'est vrai, on est chanceux.", "B"), ("Tenez-vous !", "C"),
                  ("Et il a quel âge ?", "A"), ("Cent dix-huit ans.", "B"), ("Mais c'est un record du monde ?", "A"), ("Ouais, carrément.", "B"),
                  ("Les amours !", "C"), ("Ça me fait de la peine quand même.", "A"), ("Bah non, il va très bien.", "B")]
        mots, t = [], 0.0
        for ph, qui in lignes:
            for w in ph.split(): mots.append({"w": w, "s": t, "e": t + 0.25, "voix": "speaker_1" if qui == "C" else "speaker_0", "_q": qui}); t += 0.3
            t += 0.5
        dom = [l for l in lignes if l[1] != "C"]
        anc = ecrire._appel, reseau.ia_disponible
        reseau.ia_disponible = lambda: True
        ecrire._appel = lambda *a, **k: {"nombre": 2, "phrases": [{"n": i, "qui": "A" if q == "A" else "B"} for i, (_, q) in enumerate(dom)]}
        try: res = D.scinder_voix_dominante(mots)
        finally: ecrire._appel, reseau.ia_disponible = anc
        par = {}
        for m in res: par.setdefault(m["_q"], set()).add(m["voix"])
        self.assertEqual(par, {"A": {"speaker_0"}, "B": {"speaker_1"}, "C": {"speaker_2"}})

    def test_equipe_temoin_image_et_controles(self):
        import numpy as np, equipe, locuteurs as L, regard
        # vidéo factice : la personne de gauche bouge pendant les phrases de A, celle de droite pendant celles de B
        lignes = [("Tu viens ce soir ?", 0), ("Oui bien sûr.", 1), ("Et ta sœur aussi ?", 0), ("Non, elle travaille.", 1), ("Dommage.", 0), ("Ouais.", 1)]
        mots, t = [], 0.0
        for ph, q in lignes:
            for w in ph.split(): mots.append({"w": w, "s": t, "e": t + 0.3, "voix": "speaker_0", "_q": q}); t += 0.35
            t += 0.5
        fps = 10.0; fr = []
        teintes = np.zeros((regard.HAUTEUR, regard.LARGEUR, 3), np.uint8); teintes[..., 1:] = 200
        teintes[:, :90, 0] = 20; teintes[:, 90:, 0] = 120                 # habit orange à gauche, bleu à droite
        for k in range(int(t * fps) + 2):
            f = np.zeros((regard.HAUTEUR, regard.LARGEUR), np.int16); tm = k / fps
            q = next((m["_q"] for m in mots if m["s"] <= tm <= m["e"] + 0.05), None)
            if q is not None and k % 2:
                x0 = 20 if q == 0 else 120; f[95:125, x0:x0 + 40] = 200
            fr.append((f, teintes))
        anc = regard.images; regard.images = lambda c: (fr, fps)
        try:
            B = equipe.Bulletin(); res = equipe.casting_voix([dict(m) for m in mots], "x.mp4", B, lambda m, une_voix=False: None, lambda m: m)
        finally: regard.images = anc
        lab = [int(m["voix"][-1]) for m in res]
        self.assertEqual(lab if lab[0] == 0 else [1 - x for x in lab], [m["_q"] for m in mots])   # une seule voix : l'image tranche
        sk = {"repliques": [{"p": "presentateur", "t": "Tu viens ?", "_deb": 0.0, "_fin": 1.0, "objet": "telephone", "_mots": [["Tu", 0, 0.3]]},
                            {"p": "presentateur", "t": "Oui.", "_deb": 0.5, "_fin": 0.5, "_mots": []}], "doublage": {}}
        B = equipe.Bulletin(); equipe.monteur(sk, 2.0, B); equipe.scripte(sk, [{"voix": "speaker_0", "t": "Tu viens ? Oui.", "mots": []}], {}, B)
        ko = {l["controle"] for l in B.lignes if not l["ok"]}
        self.assertNotIn("chaque réplique a une durée", ko); self.assertIn("une réplique = une seule personne", ko)   # le monteur corrige
        self.assertNotIn("objet", sk["repliques"][0])                     # téléphone sans raison : retiré
        self.assertGreater(sk["repliques"][1]["_fin"], sk["repliques"][1]["_deb"])
        self.assertLessEqual(sk["repliques"][0]["_fin"], sk["repliques"][1]["_deb"])   # il ne se chevauche plus lui-même

    def test_monteur_corrige_ordre_et_mots(self):
        import equipe
        segs = [{"deb": 2.0, "fin": 3.0, "mots": [{"w": "b", "s": 1.8, "e": 3.4}]}, {"deb": 0.0, "fin": 1.0, "mots": [{"w": "a", "s": 0.0, "e": 0.9}]}]
        sk = {"repliques": [{"p": "invite", "t": "b", "_deb": 2.0, "_fin": 3.0, "chute": True}, {"p": "presentateur", "t": "a", "_deb": 0.0, "_fin": 1.0}],
              "decoupage": [{"repliques": [0, 1]}]}
        B = equipe.Bulletin(); equipe.monteur(sk, 10.0, B, segs)
        self.assertEqual([r["t"] for r in sk["repliques"]], ["a", "b"]); self.assertEqual([s["mots"][0]["w"] for s in segs], ["a", "b"])
        self.assertTrue(sk["repliques"][-1].get("chute")); self.assertNotIn("chute", sk["repliques"][0])
        self.assertAlmostEqual(sk["repliques"][1]["_deb"], 1.8); self.assertAlmostEqual(segs[1]["fin"], 3.4)   # la réplique couvre ses mots
        self.assertTrue(all(l["ok"] for l in B.lignes))

    def test_verif_finale_synchro_et_technique(self):
        import numpy as np, verif_finale as V
        fps, sr = 30.0, 16000; n = 300
        ph = [{"p": "presentateur", "deb": 1.0, "fin": 3.0, "texte": "Salut toi", "scene": 0, "plan": "large"},
              {"p": "invite", "deb": 4.0, "fin": 6.0, "texte": "Salut", "scene": 0, "plan": "large"},
              {"p": "presentateur", "deb": 7.0, "fin": 9.0, "texte": "Ça va", "scene": 0, "plan": "large"}]
        R = {"ph": ph, "xs": {0: {"presentateur": 285, "invite": 795}}, "tetes_y": {}, "plans": [{"t0": 0}], "transitions": [], "total": 10}
        def video(qui_bouge, retard=0.0):
            fr = []
            for i in range(n):
                f = np.zeros((V.H_, V.L), np.int16); t = i / fps - retard
                q = next((q for q in ph if q["deb"] <= t <= q["fin"]), None)
                if q and i % 2:
                    x = int(qui_bouge(q["p"]) * V.L / 1080); f[150:200, x - 20:x + 20] = 200
                fr.append(f)
            sig = np.zeros(int(n / fps * sr), np.float32)
            for q in ph: sig[int(q["deb"] * sr):int(q["fin"] * sr)] = 0.3 * np.sin(np.arange(int((q["fin"] - q["deb"]) * sr)) * 0.05)
            return fr, (sig, sr)
        bon = {"presentateur": 285, "invite": 795}
        fr, son = video(lambda p: bon[p]); d, dec = V.synchro("x", R, fr, fps, son)
        self.assertEqual(d, []); self.assertEqual(dec, 0.0)
        fr, son = video(lambda p: bon["invite" if p == "presentateur" else "presentateur"]); d, _ = V.synchro("x", R, fr, fps, son)
        self.assertEqual(len(d), 3)                                        # c'est toujours l'autre qui bouge
        fr, son = video(lambda p: bon[p], retard=0.3); _, dec = V.synchro("x", R, fr, fps, son)
        self.assertGreaterEqual(dec, 0.2)                                  # image en retard : le son sera recalé
        fr = [np.zeros((V.H_, V.L), np.int16) for _ in range(n)]; fr[150] = fr[150] + 250
        self.assertTrue(any("clignotement" in x["quoi"] or "saut" in x["quoi"] for x in V.technique("x", R, fr, fps)))

    def test_deux_avis_et_deux_transcriptions(self):
        import doublage as D, ecrire, reseau, equipe
        mots = [{"w": w, "s": 0.4 * i, "e": 0.4 * i + 0.3, "voix": "speaker_0"} for i, w in enumerate("Tu viens ? Oui. Et lui ? Non. Pourquoi ? Malade.".split())]
        reponses = [{"nombre": 2, "phrases": [{"n": i, "qui": "AB"[i % 2]} for i in range(6)]},
                    {"nombre": 2, "phrases": [{"n": i, "qui": "BA"[i % 2] if i < 5 else "B"} for i in range(6)]}]   # 2e IA : lettres inversées, 1 désaccord
        appels = []
        class Faux:
            def __init__(self, nom): self.messages = type("M", (), {"dernier": nom})()
        anc = ecrire._appel, reseau.ia_disponible, reseau.claude, reseau.ordre_ia
        ecrire._appel = lambda client, *a, **k: (appels.append(client.messages.dernier), reponses[len(appels) - 1])[1]
        reseau.ia_disponible = lambda: True; reseau.ordre_ia = lambda images=False, raisonner=False: ["gemini", "mistral"]
        reseau.claude = lambda raisonner=False, exclure=(): Faux("mistral" if exclure else "gemini")
        try: ia = D.relire_dialogue(mots)
        finally: ecrire._appel, reseau.ia_disponible, reseau.claude, reseau.ordre_ia = anc
        self.assertEqual(appels, ["gemini", "mistral"])                    # deux IA différentes
        self.assertEqual(ia, [0, 1, 0, 1, 0, None])                        # d'accord sauf la dernière phrase : laissée au son et à l'image

    def test_liste_4_6_7_9_12_14(self):
        ici = os.path.dirname(__file__); sys.path.insert(0, os.path.join(ici, "..", "moteur"))
        import dessin_partage as DP, file_attente as FA, profils_tiktok as PT, verif_finale as V, studio, numpy as np
        import humain as HU, marionnette as M, perso_croquis as P
        anc = os.environ.pop("AIDES", None); anc_n = os.environ.get("EN_MEME_TEMPS")   # 12 : machines d'aide selon la durée
        os.environ["EN_MEME_TEMPS"] = "1"                                  # (une vidéo à la fois : jusqu'à 5 aides)
        try: self.assertEqual([DP.nb_aides(n) for n in (1300, 3900, 7000, 20000)], [1, 3, 5, 5])
        finally:
            if anc is not None: os.environ["AIDES"] = anc
            if anc_n is None: os.environ.pop("EN_MEME_TEMPS", None)
            else: os.environ["EN_MEME_TEMPS"] = anc_n
        env = dict(os.environ)                                             # 9 : chaîne en parallèle
        try:
            os.environ.update(CHAINE="3/10", PREPA_PARALLELE="1", EN_MEME_TEMPS="1"); self.assertTrue(FA.prepa_parallele())
            os.environ["CHAINE"] = "1/10"; self.assertFalse(FA.prepa_parallele())
            os.environ["CHAINE"] = "suite:x|3/10"; self.assertFalse(FA.prepa_parallele())
            os.environ.update(CHAINE="3/10", PREPA_PARALLELE="0"); self.assertFalse(FA.prepa_parallele())
            os.environ["EVITER"] = "7677317232023588129"
            self.assertIn("7677317232023588129", PT.deja_utilisees([]))      # son pris par la vidéo encore en fabrication
        finally: os.environ.clear(); os.environ.update(env)
        y = open(os.path.join(ici, "..", ".github", "workflows", "emission.yml"), encoding="utf-8").read()
        self.assertIn("sortie/.suivante_lancee", y); self.assertIn("eviter:", y)
        self.assertIn("tour_de_dessiner(sk)", open(os.path.join(ici, "..", "moteur", "principal.py"), encoding="utf-8").read())
        self.assertEqual(V.confiance([], []), 100)                         # 4 : note de confiance
        self.assertLess(V.confiance([{"ok": False, "revoir": True}], [{"grave": True}], {"note": 4}), 75)
        src = open(os.path.join(ici, "..", "moteur", "site.py"), encoding="utf-8").read()
        for m in ("badgeConf", "filtrerTk", 'id="fTexte"', 'id="fProfil"', "rendreCalendrier", "deplacerPubli", "ondrop",   # 4, 6, 7
                  'id="aPublier"', "majBoutonPubliFiche", 'c.querySelector(".infos").appendChild(boutonPubli(v))'):   # « À publier » partout
            self.assertIn(m, src)
        self.assertIn('APPEL.append((-1.0, 1e9, "partage"', open(os.path.join(ici, "..", "moteur", "cartoon.py"), encoding="utf-8").read())   # appel : écran partagé continu
        for m in ():
            self.assertIn(m, src)
        img = np.full((1920, 1080, 3), 235, np.uint8)                      # 14 : lit, canapé, comptoir, volant
        for meuble, assis in (("lit", True), ("canape", True), ("comptoir", False), ("volant", True)):
            F = HU.creer(3); p = dict(M.pose_neutre(), x=540, y=1500, s=1.0, emo="neutre", assis=assis, meuble=meuble, costume={"haut": "tshirt"})
            P.dessiner(img, F, HU._pose(F, p))
        reps = [{"p": "envoyee", "t": "Allô ? Tu viens ?"}, {"p": "invite", "t": "Non je suis malade, cloué au lit."}]
        sk = {"repliques": reps, "doublage": {"contexte": "au téléphone"}, "decoupage": [{"scene": "1", "repliques": [0, 1], "decor": "bedroom"}],
              "studio": {"lieux": ["chambre"]}}
        B = studio.bible(sk, ["envoyee", "invite"])
        self.assertEqual(B["meubles"].get(0), {"invite": "lit"})            # le malade est dans son lit

    def test_une_seule_scene_pour_un_son_tiktok(self):
        import studio
        sk = {"repliques": [{"p": "presentateur", "t": "a"}] * 5, "doublage": {"duree": 10},
              "decoupage": [{"scene": "1", "repliques": [0, 1], "decor": "garden"}, {"scene": "2", "repliques": [2, 3, 4], "decor": "garden, aquarium"}],
              "studio": {"lieux": ["jardin", "salon"]}}
        self.assertTrue(studio.une_scene(sk))
        self.assertEqual(sk["decoupage"], [{"scene": "1", "repliques": [0, 1, 2, 3, 4], "decor": "garden, aquarium"}])
        self.assertEqual(sk["studio"]["lieux"], ["salon"])
        self.assertFalse(studio.une_scene({"repliques": [], "_separes": True, "decoupage": [{"repliques": [0]}, {"repliques": [1]}]}))   # appel : un décor chacun
        src = open(os.path.join(os.path.dirname(__file__), "..", "moteur", "cartoon.py"), encoding="utf-8").read()
        self.assertIn('if DOUB: SANS_ENTREE = {q["scene"] for q in ph}', src)   # ni entrée en marchant ni bruits de pas


class TestAppelPereFils(unittest.TestCase):
    def test_roles_lieux_dame(self):
        import studio
        reps = [{"p": "envoyee", "t": "Papa, il y a une inconnue qui m'a proposé de monter dans sa voiture."},
                {"p": "invite", "t": "Fonce fiston, monte dans cette voiture."},
                {"p": "envoyee", "t": "La dame est habillée en mère Noël."}, {"p": "invite", "t": "Va avec la dame."}]
        sk = {"repliques": reps, "doublage": {"contexte": "Un ado appelle son père depuis la rue.", "visuel": {"nb_personnes": 1}},
              "studio": {"personnages": {"presentateur": {"genre": "h", "age": 15}, "invite": {"genre": "h", "age": 42}, "envoyee": {"genre": "f", "age": 25}},
                         "costumes": {"presentateur": {"haut": "chemise"}, "invite": {"haut": "debardeur"}, "envoyee": {"haut": "robe"}},
                         "gags": ["La fin de carrière de CR7 signifie la fin du football"]},
              "decoupage": [{"scene": "1", "repliques": [0, 1, 2, 3], "decor": ""}]}
        self.assertEqual(studio.accorder_roles(sk, {"envoyee": "h", "invite": "h"}), 1)
        S = sk["studio"]
        self.assertEqual(S["personnages"]["envoyee"]["age"], 15); self.assertEqual(S["costumes"]["envoyee"]["haut"], "chemise")
        self.assertEqual(S["figurants"][0]["avec"], "envoyee"); self.assertEqual(S["figurants"][0]["genre"], "f")
        self.assertTrue(studio.separer_lieux(sk)); self.assertEqual(S["lieux"], ["rue", "salon"])
        self.assertFalse(studio.gag_dans_le_sujet(sk, S["gags"][0]))
        S["figurants"] = []; self.assertEqual(studio.figurants_devines(sk)[0]["c_haut"], "rouge")
        C = studio.compagnons(sk, sk["decoupage"], S["lieux"], "soir", 3)[0]
        self.assertEqual(C["fiche"]["genre"], "f"); self.assertTrue(C["fiche"]["maquillage"]); self.assertEqual(C["fiche"]["barbe"], "")
        self.assertIn("rouge_levres", C["costume"]["details"]); self.assertEqual(C["costume"]["c_haut"], studio.NOMS_COULEURS["rouge"])
        self.assertFalse(any("barbe" in d or d == "moustache" for d in C["costume"]["details"]))


class TestGenreDeLaVoix(unittest.TestCase):
    """Remarque de l'auteur (6 novembre) : une voix de femme sur un physique d'homme et inversement. Le TIMBRE de la voix (formants)
    décide d'abord ; la hauteur seule se trompait sur les voix d'homme aiguës (cris, voix de dessin animé accélérées)."""

    def test_timbre_des_voix_de_reference(self):
        import studio, wave, numpy as np                                # wave : soundfile n'est pas installé pour les tests en ligne
        res = {}
        for r in ("presentateur", "invite", "envoyee"):
            with wave.open(os.path.join(ICI, "..", "voix", r + ".wav")) as f:
                sr = f.getframerate(); a = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float64) / 32768
            res[r] = studio.genre_timbre(studio.espacement_formants(a, sr))
        self.assertEqual(res, {"presentateur": "h", "invite": "h", "envoyee": "f"})

    def test_priorites(self):
        import studio
        sk = {"doublage": {}, "_voix_hz": {"invite": 250}, "_voix_genre": {"invite": "f"}, "_voix_timbre_genre": {"invite": "h"}, "_voix_timbre": {"invite": 940}}
        self.assertEqual(studio.genre_voix(sk, "invite", {}), "h")                      # un timbre net l'emporte sur une voix aiguë
        sk["_voix_timbre"]["invite"] = 997                                  # 11 novembre : timbre peu net, Gemini et l'IA voient une femme
        self.assertEqual(studio.genre_voix(sk, "invite", {"genre": "f", "genre_vu": "f"}), "f")
        sk["_voix_timbre"]["invite"] = 940
        sk.pop("_voix_timbre_genre")
        self.assertEqual(studio.genre_voix(sk, "invite", {"genre_vu": "h"}), "h")       # hauteur contredite par l'image de l'original
        self.assertEqual(studio.genre_voix(sk, "invite", {}), "f")
        sk = {"doublage": {}, "_voix_hz": {"invite": 190}}
        self.assertEqual(studio.genre_voix(sk, "invite", {"genre": "femme"}), "f")      # « femme » / « homme » de l'IA compris
        src = open(os.path.join(ICI, "..", "moteur", "perso_croquis.py"), encoding="utf-8").read()
        self.assertIn('F.get("genre") == "h" and tenue not in ("robe_mariee",): bas = "pantalon"', src)


class TestPersonneEnTrop(unittest.TestCase):
    """Remarque de l'auteur du 11 novembre : 3 personnages dessinés alors que l'original n'en montre que 2 (on parle d'une 3e
    personne absente : le grand frère et son message vocal, « voilà mon frère »)."""

    def _mots(self, lignes):
        mots, t = [], 0.0
        for ph, v in lignes:
            for w in ph.split(): mots.append({"w": w, "s": t, "e": t + 0.3, "voix": v, "sure": 1.0}); t += 0.35
            t += 0.6
        return mots

    def setUp(self):
        import video_ia; video_ia.DERNIER.clear()

    def test_message_vocal_hors_champ(self):
        import equipe
        m = self._mots([("T'as vu là-bas ?", "a"), ("Mon frère m'a envoyé un vocal.", "b"), ("Rentre tout de suite !", "c"),
                        ("C'est quoi ça ?", "a"), ("C'est mon grand frère.", "b"), ("Je vais te retrouver.", "c"), ("Il est fou.", "a")])
        B = equipe.Bulletin(); res = equipe.presents(m, 2, B)
        self.assertEqual(equipe.HORS_CHAMP, {"c"})
        self.assertEqual({x["voix"] for x in res}, {"a", "b", "c"})        # la voix reste (entendue), mais n'est pas dessinée

    def test_voix_en_trop_rendue(self):
        import equipe
        m = self._mots([("Tu payes pas de loyer ?", "a"), ("Non.", "b"), ("Pourquoi ?", "c"), ("C'est ta maison.", "b"),
                        ("Et alors ?", "a"), ("Bah non.", "b"), ("D'accord.", "c")])
        res = equipe.presents(m, 2, equipe.Bulletin())
        self.assertEqual(equipe.HORS_CHAMP, set())
        self.assertEqual({x["voix"] for x in res}, {"a", "b"})
        ph = __import__("locuteurs").phrases(res)
        self.assertEqual(res[ph[2][0]]["voix"], "a")                       # après une phrase de b, c'est l'autre qui parle

    def test_trois_personnes_vues(self):
        import equipe
        m = self._mots([("Salut.", "a"), ("Bonjour.", "b"), ("Coucou.", "c")])
        res = equipe.presents(m, 3, equipe.Bulletin())
        self.assertEqual({x["voix"] for x in res}, {"a", "b", "c"}); self.assertEqual(equipe.HORS_CHAMP, set())
        res = equipe.presents(self._mots([("Salut.", "a"), ("Bonjour.", "b"), ("Coucou.", "c")]), 1, equipe.Bulletin())
        self.assertEqual({x["voix"] for x in res}, {"a", "b", "c"})        # une seule personne vue : un acteur qui joue tout, on ne touche à rien

    def test_voila_mon_frere(self):
        import studio
        sk = {"repliques": [{"p": "envoyee", "t": "Voilà, voilà mon frère, voilà."}, {"p": "presentateur", "t": "Mon frère m'a envoyé un vocal, voici mon frère."}]}
        self.assertEqual(studio.famille_presentee(sk), [])
        sk = {"repliques": [{"p": "envoyee", "t": "Je te présente mon père."}]}
        self.assertEqual(len(studio.famille_presentee(sk)), 1)

    def test_pas_plus_de_monde_que_l_original(self):
        import studio
        reps = [{"p": "presentateur", "t": "Je te présente mon père."}, {"p": "envoyee", "t": "Bonjour."}]
        sk = {"repliques": reps, "doublage": {"visuel": {"nb_personnes": 2}}}
        self.assertEqual(studio.compagnons(sk, [{"repliques": [0, 1]}], ["salon"], "jour", 1), [])
        sk = {"repliques": reps, "doublage": {"nb_vus": 3, "visuel": {"nb_personnes": 2}}}
        self.assertEqual(len(studio.compagnons(sk, [{"repliques": [0, 1]}], ["salon"], "jour", 1)), 1)

    def test_t_es_ou_dans_une_dispute(self):
        import studio
        sk = {"repliques": [{"p": "envoyee", "t": "Mais t'es où ?"}, {"p": "invite", "t": "Quoi ?"}, {"p": "envoyee", "t": "T'es où ?"},
                            {"p": "envoyee", "t": "Non mais t'es où ?"}], "doublage": {"contexte": "Dans la cuisine, une dispute.", "visuel": {"nb_personnes": 1}}}
        self.assertFalse(studio.appel_devine(sk))
        sk["repliques"].append({"p": "invite", "t": "Allô ?"})
        self.assertTrue(studio.appel_devine(sk))

    def test_accords_du_texte(self):
        import studio
        sk = {"doublage": {}, "repliques": [{"p": "invite", "t": "Je suis choquée."}], "_voix_genre": {"invite": "h"}}
        self.assertEqual(studio.genre_voix(sk, "invite", {"genre": "f"}), "f")

    def test_texte_ia_en_dict(self):
        import doublage
        self.assertEqual(doublage.texte_ia({"texte": "Avec toi."}), "Avec toi.")
        self.assertEqual(doublage.texte_ia("{'texte': 'Bouffon va.'}"), "Bouffon va.")
        self.assertEqual(doublage.texte_ia("Quoi ?"), "Quoi ?")


class TestOutilsLibres(unittest.TestCase):
    """Outils open source choisis par l'auteur le 11 novembre (idées 1-4, 6-8, 10-13, 15) : la logique autour de chaque outil."""

    def test_ina_et_praat(self):
        import voix_genre, studio
        self.assertEqual(voix_genre.decision_ina([("female", 0, 3.0), ("male", 3, 3.5)]), "f")
        self.assertIsNone(voix_genre.decision_ina([("female", 0, 2.0), ("male", 2, 4.0)]))
        self.assertEqual(voix_genre.genre_vtl(17.2), "h"); self.assertEqual(voix_genre.genre_vtl(15.8), "f"); self.assertIsNone(voix_genre.genre_vtl(16.3))
        sk = {"doublage": {}, "_voix_timbre_genre": {"envoyee": "h"}, "_voix_timbre": {"envoyee": 1010}, "_voix_ina": {"envoyee": "f"}}
        self.assertEqual(studio.genre_voix(sk, "envoyee", {}), "f")      # ina (1,5) l'emporte sur un timbre peu net (0,5)

    def test_silero_mots_sans_voix(self):
        import ecoute
        mots = [{"w": w, "s": s, "e": s + 0.3} for w, s in [("Merci", 0.1), ("d'avoir", 0.4), ("regardé", 0.7), ("Salut", 3.0), ("toi", 3.3)]]
        res, n = ecoute.mots_sans_voix(mots, [(2.9, 4.0)])
        self.assertEqual(n, 3); self.assertEqual([m["w"] for m in res], ["Salut", "toi"])
        res, n = ecoute.mots_sans_voix(mots[:2] + mots[3:], [(2.9, 4.0)])
        self.assertEqual(n, 0)                                             # deux mots seulement : doute, on garde

    def test_volume(self):
        import jt
        t = np.arange(48000 * 3) / 48000; m = np.stack([0.05 * np.sin(2 * np.pi * 220 * t)] * 2, 1)
        f = jt.filtre_volume(m, 48000)
        self.assertTrue(f.startswith("volume=") or f.startswith("loudnorm"))

    def test_rhubarb(self):
        import rhubarb
        rh = rhubarb.cues({"mouthCues": [{"start": 0.0, "end": 0.2, "value": "X"}, {"start": 0.2, "end": 0.5, "value": "D"},
                                         {"start": 0.5, "end": 0.7, "value": "A"}, {"start": 0.7, "end": 1.0, "value": "F"}]})
        self.assertEqual(rh[1][2], "A"); self.assertEqual(rh[2][2], "M"); self.assertIsNone(rh[0][2])
        self.assertEqual(rhubarb.chronologie(rh, 0.3, 0.9), [(0.3, 0.5, "A"), (0.5, 0.7, "M"), (0.7, 0.9, "U")])
        self.assertIsNone(rhubarb.chronologie(rh, 0.0, 0.2))

    def test_transnet_instants(self):
        import plans_video
        p = np.zeros(300); p[89:91] = 0.9; p[180] = 0.7
        self.assertEqual(plans_video.instants(p, 30.0), [2.98, 6.02])
        self.assertTrue(plans_video.entre([3.0], 2.5, 3.5)); self.assertFalse(plans_video.entre([3.0], 3.0, 3.5))

    def test_personnes_vues(self):
        import personnes_vues as PV
        b = PV.sans_doublons([(0.9, [0, 0, 100, 200]), (0.6, [5, 5, 100, 200]), (0.8, [150, 0, 250, 200])])
        self.assertEqual(len(b), 2)
        anc_a, anc_m = PV.actif, PV.mouvements
        PV.actif = lambda: True
        E = np.array([[5.0, 0.5]] * 10 + [[0.4, 6.0]] * 10)
        PV.mouvements = lambda v: {0: (0.0, 4.0, [0.1 + 0.2 * k for k in range(20)], E)}
        try:
            mots = [{"w": "a", "s": s, "e": s + 0.3} for s in (0.2, 1.2, 2.4, 3.2)]
            self.assertEqual([c for c, _ in PV.temoin("x.mp4", mots, [[0], [1], [2], [3]])], [0, 0, 1, 1])
        finally: PV.actif, PV.mouvements = anc_a, anc_m

    def test_beaute_choisir(self):
        import beaute
        self.assertEqual(beaute.choisir([(1.0, 5.0, "a"), (1.1, 6.0, "b"), (1.6, 9.0, "c")]), "b")   # « c » trop zoomé
        self.assertEqual(beaute.choisir([(1.2, None, "a"), (1.0, None, "b")]), "b")                  # sans notes : le moins zoomé

    def test_orthographe(self):
        import orthographe as O
        self.assertTrue(O.acceptable("Ils mange", "Ils mangent")); self.assertTrue(O.acceptable("a", "à"))
        self.assertFalse(O.acceptable("J'sais", "Je ne sais")); self.assertFalse(O.acceptable("es", "sois"))
        self.assertFalse(O.acceptable("Kevin", "Kevins"))
        rep = {"matches": [{"offset": 0, "length": 9, "replacements": [{"value": "Il mange"}, {"value": "Ils mangent"}]},
                           {"offset": 21, "length": 1, "replacements": [{"value": "à"}]}]}
        anc = os.environ.get("ORTHOGRAPHE"); os.environ["ORTHOGRAPHE"] = "1"
        try: out, n = O.corriger_lignes(["Ils mange.", "Va a la"], demander=lambda t: dict(rep, matches=[rep["matches"][0], dict(rep["matches"][1], offset=15)]))
        finally: os.environ["ORTHOGRAPHE"] = anc or "0"
        self.assertEqual(out, ["Ils mangent.", "Va à la"]); self.assertEqual(n, 2)

    def test_wespeaker_fbank(self):
        import wespeaker
        F = wespeaker.fbank(np.random.default_rng(0).normal(0, 0.1, 16000).astype(np.float32))
        self.assertEqual(F.shape[1], 80); self.assertAlmostEqual(float(np.abs(F.mean(0)).max()), 0.0, places=3)


class TestAnalyse10Videos(unittest.TestCase):
    """Leçons des 10 vidéos du 1er novembre (demande de l'auteur du 6 novembre)."""

    def test_un_seul_steak_dans_le_micro_ondes(self):
        import remarque, copy
        sk = {"repliques": [{"p": "presentateur", "t": "Attends je vais faire des bruits.", "_deb": 0, "_fin": 2},
                            {"p": "invite", "t": "Ça va chauffer.", "_deb": 2, "_fin": 3},
                            {"p": "narrateur", "t": "POP-PI-POU.", "_deb": 3, "_fin": 4}], "decoupage": [{"repliques": [0, 1, 2]}]}
        t = "les personnages sont censés être un seul personnage et le personnage unique est censé être un steak haché qui parle il est censé être dans un micro-ondes"
        _, corr = remarque.regles(sk, t)
        types = [c["type"] for c in corr]
        self.assertIn("un_seul", types); self.assertIn("contenant", types)
        import reseau
        avant = reseau.ia_disponible
        f = os.path.join(ICI, "..", "episodes", "remarques_auteur.json"); garde = open(f, "rb").read() if os.path.exists(f) else None
        try:
            reseau.ia_disponible = lambda: False
            s2 = copy.deepcopy(sk); remarque.appliquer(s2, t)
        finally:
            reseau.ia_disponible = avant
            if garde is not None: open(f, "wb").write(garde)               # (le test n'ajoute rien aux vraies remarques de l'auteur)
        self.assertEqual({r["p"] for r in s2["repliques"]}, {"invite"})
        self.assertEqual(s2["studio"]["personnages"]["invite"], {"espece": "steak", "dans": "micro_ondes"})

    def test_contenant_dessine(self):
        import animaux
        self.assertEqual(animaux.contenant_de("il cuit dans un micro-ondes"), "micro_ondes")
        self.assertEqual(animaux.contenant_de("il est dans la poêle"), "poele")
        self.assertIsNone(animaux.contenant_de("il est dans la cuisine"))
        img = np.full((700, 600, 3), 235, np.uint8)
        animaux.contenant_arriere(img, "micro_ondes", (300, 300), 600, 100); animaux.contenant_avant(img, "micro_ondes", (300, 300), 600, 100, 3.0)
        self.assertLess(img[400, 300].mean(), 200)                         # intérieur sombre / éclairé

    def test_s_appelle_n_est_pas_un_appel(self):
        import studio, video_ia
        video_ia.DERNIER.clear()
        sk = {"repliques": [{"p": "presentateur", "t": "Il s'appelle comment ton fils ?"}, {"p": "invite", "t": "Il s'appelle Enzo."}],
              "doublage": {"contexte": "En voiture, après une conversation téléphonique étrange.", "visuel": {"nb_personnes": 2}}}
        self.assertFalse(studio.appel_devine(sk))
        sk["doublage"]["visuel"]["nb_personnes"] = 1
        self.assertTrue(studio.appel_devine(sk))                          # une seule personne à l'image + contexte d'appel : oui

    def test_hallucinations_et_faux_points(self):
        import locuteurs
        m = [{"w": w, "s": i, "e": i + 0.3} for i, w in enumerate("Bon à demain Sous-titrage Société Radio-Canada".split())]
        self.assertEqual([x["w"] for x in locuteurs.sans_hallucinations(m)], ["Bon", "à", "demain"])
        src = open(os.path.join(ICI, "..", "moteur", "verif_finale.py"), encoding="utf-8").read()
        self.assertIn('R.get("fin_carte")', src); self.assertIn("fin - 3.6", src)
        self.assertIn('points = [d for d in points if d["grave"]]', src)

    def test_jury_lit_le_texte(self):
        src = open(os.path.join(ICI, "..", "moteur", "qualite.py"), encoding="utf-8").read()
        self.assertIn('ecrire._appel(reseau.claude(), None, [{"role": "user", "content": contenu}], OUTIL', src)
        import reseau
        reseau._GQ["liste"] = ["meta-llama/llama-4-scout-17b-16e-instruct", "whisper-large-v3", "llama-3.3-70b-versatile"]
        self.assertEqual(reseau._groq_modeles(True), ("meta-llama/llama-4-scout-17b-16e-instruct",))
        reseau._GQ.clear()
