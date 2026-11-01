"""Tests des composants du robot (sans réseau, sans clé API, sans GPU).
Lancer : python -m unittest discover -s tests -v"""
import io, json, os, sys, tempfile, types, unittest
import numpy as np

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, "..", "moteur"))
os.environ.setdefault("LONGUEUR", "pro")
import actu, ecrire, voix_banque, planning  # noqa: E402
os.environ.setdefault("FORCER_FABRICATION", "1")   # les anciens tests vérifient l'écriture, pas le seuil de fabrication


def article(titre, source, lien=None, resume=""):
    return dict(titre=titre, resume=resume, lien=lien or f"https://{source}.fr/{abs(hash(titre))}", date=None, source=source)


SKETCH = {
    "sujet": "budget", "ecran": "budget 2027", "titre_accroche": "4 milliards perdus",
    "concept": "c", "format": "faux JT", "angle": "a", "resume_factuel": "r", "faits_reels": ["f"], "inventions": ["i"],
    "decoupage": [{"scene": "plateau", "repliques": [0, 1], "lieu": "plateau", "son": "rimshot", "duree": 6},
                  {"scene": "direct", "repliques": [2, 99], "lieu": "nulle part", "son": "explosion"}],
    "repliques": [{"p": "presentateur", "t": "Les députés ont rejeté les économies du budget. " * 3, "chute": True}] +
                 [{"p": "envoyee", "t": "Au budget, les économies ont disparu dans les couloirs du palais. " * 2} for _ in range(4)] +
                 [{"p": "intrus", "t": "à ignorer"}],
    "legende": "l", "hashtags": ["Économie", "#Budget"], "sources": ["L1", "inconnu"],
    "gag": {"replique": 2, "prompt": "Flat 2D cartoon, thick black outlines, simple shapes. Sofa."},
}


class TestEcriture(unittest.TestCase):
    def test_prompt_humour_charge(self):
        self.assertIn("MOTEUR PROFESSIONNEL DE SATIRE", ecrire.MOTEUR_HUMOUR)

    def test_valider_et_decoupage(self):
        sk = ecrire.valider(json.loads(json.dumps(SKETCH)), {"L1"})
        self.assertEqual(len(sk["repliques"]), 5)                             # rôle inconnu écarté
        self.assertEqual(sk["sources"], ["L1"])                               # seuls les liens fournis sont gardés
        self.assertEqual(sk["hashtags"], ["economie", "budget"])
        self.assertEqual(sk["decoupage"][0]["son"], "rimshot")
        self.assertEqual(sk["decoupage"][1], {"scene": "direct", "repliques": [2], "lieu": "", "son": "", "duree": 0})
        self.assertEqual(sk["gag"]["replique"], 2)

    def test_roles_et_repliques_tolerants(self):
        sk = json.loads(json.dumps(SKETCH)); sk["invite_nom"] = "Aymeric Ponction"
        sk["repliques"] = json.dumps([{"p": "Présentateur", "t": "Bonsoir."}, {"p": "Envoyée spéciale", "t": "Ici."},
                                      {"p": "Aymeric Ponction", "t": "Je conteste."}, {"p": "INVITÉ", "t": "Encore."}])
        v = ecrire.valider(sk, set())
        self.assertEqual([r["p"] for r in v["repliques"]], ["presentateur", "envoyee", "invite", "invite"])
        with self.assertRaisesRegex(ValueError, "champs reçus"): ecrire.valider({"sujet": "x"}, set())   # diagnostic dans le journal

    def test_sources_jamais_inventees(self):
        liens = {"https://www.lemonde.fr/politique/article/budget.html", "https://www.bfmtv.com/x/"}
        self.assertEqual(ecrire._sources(["http://lemonde.fr/politique/article/budget.html?utm=1", "https://invente.fr/faux", "Le Monde"], liens),
                         ["https://www.lemonde.fr/politique/article/budget.html"])    # variante d'URL reconnue, lien inventé écarté

    def test_chute_doit_parler_du_sujet(self):
        titres = [article("Pesticides autorisés à vie : mobilisations contre le projet européen", "a")]
        sk = {"sujet": "PESTICIDES", "verite": "Bruxelles protège les fabricants de pesticides, pas les consommateurs.",
              "repliques": [{"p": "presentateur", "t": "Bonsoir."}, {"p": "envoyee", "t": "Trop tard. Votre yaourt vient d'embaucher un lobbyiste. Il périme en 2051."}]}
        with self.assertRaisesRegex(ValueError, "chute hors sujet"): ecrire.chute_sur_sujet(sk, titres)      # gag annexe : refusé
        sk["repliques"][-1]["t"] = "En clair : les pesticides ont un CDI à Bruxelles, et vous, vous avez le cancer en CDD."
        ecrire.chute_sur_sujet(sk, titres)                                     # vérité sur le sujet : acceptée

    def test_exemple_finit_sur_la_verite(self):
        self.assertTrue(ecrire.EXEMPLE["repliques"][-1]["t"].startswith("Rassurez-vous"))
        self.assertNotIn("rappel à la fin (le plombier)", ecrire.TONS["clash"])

    def test_articles_hors_sujet_retires(self):
        t = [article("Pesticides autorisés à vie : mobilisations contre le projet européen", "a", "P1"),
             article("Projet européen sur les pesticides : les agriculteurs divisés", "b", "P2"),
             article("Livret A, retraites : les députés modifient le budget en commission", "c", "B1")]
        self.assertEqual([x["lien"] for x in ecrire.pertinents(t)], ["P1", "P2"])

    def test_longueur_et_hors_sujet(self):
        sk = ecrire.valider(json.loads(json.dumps(SKETCH)), set())
        self.assertGreater(ecrire.longueur(sk), 0)
        court = dict(sk, repliques=sk["repliques"][:1])
        with self.assertRaises(ValueError): ecrire.longueur(court)             # trop court pour 60-90 s
        ecrire.hors_sujet(sk, [{"titre": "Budget 2027 : les économies rejetées"}])
        with self.assertRaises(ValueError): ecrire.hors_sujet(sk, [{"titre": "Mobilisation des lycéens contre la réforme"}])


class FauxClaude:
    """Simule l'API : choix du candidat 1, puis sketch noté 60 (réécriture demandée) puis 92."""
    def __init__(self, web_en_panne=False, critique_vide=False, sources=("L1",)):
        self.notes = [60, 92]; self.appels = []; self.web_en_panne = web_en_panne; self.choix = 1; self.prompts = []
        self.critique_vide = critique_vide; self.sources = list(sources); self.reecritures = []; self.sans_total = False; self.chute_fausse = False; self.metaphore = False; self.systemes = []
        self.messages = self

    def create(self, **kw):
        noms = [t.get("name") for t in kw.get("tools", [])]
        self.appels.append(noms)
        if self.web_en_panne and "web_search" in noms: raise RuntimeError("outil web non autorisé")
        if "choisir_sujet" in noms: self.prompts.append(kw["messages"][0]["content"]); out = {"notes": [{"index": 0, "note": 4}, {"index": 1, "note": 9}], "choix": self.choix, "angle": "angle test", "faits_verifies": ["fait"]}
        elif "proposer_idees" in noms:
            out = {"idees": [{"titre": "Les réunions qui auraient pu être un mail", "description": "Une heure pour rien."},
                             {"titre": "Le budget du mois : les économies disparaissent le 5", "description": "Toujours le 5."}]}
        elif "atelier_vannes" in noms:
            out = {"vannes": [f"vanne {i}" for i in range(15)], "chutes": [f"Rassurez-vous : chute {i}." for i in range(15)]}
        elif "jury" in noms:
            out = {"notes_chutes": [3] * 7 + [9] + [3] * 7, "meilleures_vannes": [2, 5], "meilleure_chute": 7,
                   "chute_affutee": "Rassurez-vous : le budget est sauvé. Il suffit de ne plus le voter."}
        elif "noter_sketch" in noms:
            n = self.notes.pop(0)
            if self.sans_total:                                              # 1re fois : total oublié et sous-notes incomplètes
                self.sans_total = False; self.notes.insert(0, n); out = {"critique": "x" * 50, "originalite": 15}
            else: out = {"total": n, "chute_vraie": not self.chute_fausse, "metaphore_filee": self.metaphore, "critique": "" if self.critique_vide else "chute trop faible"}
            if self.critique_vide and not self.sans_total:                                            # critique écrite hors de l'outil
                return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text="Réplique 3 trop plate."),
                                                      types.SimpleNamespace(type="tool_use", name="noter_sketch", input=out)],
                                             usage=types.SimpleNamespace(input_tokens=10, output_tokens=5))
        else:
            out = json.loads(json.dumps(SKETCH)); out["sources"] = self.sources
            out["concept"] = "Le budget au restaurant. Note qualité interne : 84/100. Décision : prêt pour production."
        self.reecritures.append(kw["messages"][-1]["content"]) if "rendre_sketch" in noms else None
        s_ = kw.get("system", ""); self.systemes.append("".join(b.get("text", "") for b in s_) if isinstance(s_, list) else s_)
        bloc = types.SimpleNamespace(type="tool_use", name=noms[0], input=out)
        return types.SimpleNamespace(content=[bloc], usage=types.SimpleNamespace(input_tokens=100, output_tokens=50))


class TestMoteurHumour(unittest.TestCase):
    def _lancer(self, faux):
        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda: faux)
        cands = [[article("Mobilisation des lycéens", "x", "L0")],
                 [article("Budget 2027 : les économies rejetées", "a", "L1"), article("Budget : les députés et les économies", "b", "L2")]]
        return ecrire.ecrire_sketch(cands, essais=3)

    def test_selection_qualite_reecriture(self):
        faux = FauxClaude(); sk = self._lancer(faux)
        self.assertEqual(sk["fiche"]["note"], 92)
        self.assertEqual(sk["fiche"]["decision"], "prêt pour production")
        self.assertEqual(sk["sources"], ["L1"])                               # c'est bien le candidat choisi (index 1)
        ecritures = [a for a in faux.appels if a and a[0] == "rendre_sketch"]
        self.assertEqual(len(ecritures), 2)                                   # une réécriture après la note de 60
        self.assertIn("web_search", faux.appels[0])                           # vérification web demandée à la sélection

    def test_fiche_honnete(self):
        faux = FauxClaude(critique_vide=True, sources=[]); sk = self._lancer(faux)
        self.assertNotIn("84", sk["fiche"]["concept"])                        # l'auteur ne s'attribue pas de note
        self.assertEqual(sk["fiche"]["concept"], "Le budget au restaurant.")
        self.assertIn("Réplique 3 trop plate", faux.reecritures[-1])          # la critique hors outil arrive bien dans la réécriture
        self.assertEqual(sk["sources"], ["L1", "L2"])                         # aucun lien recopié : liens RSS réels du sujet choisi
        self.assertIn("decoupage", sk["fiche"])

    def test_note_sans_total(self):
        faux = FauxClaude(); faux.sans_total = True
        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda: faux)
        cands = [[article("Budget 2027 : les économies rejetées", "a", "L1"), article("Budget : les députés et les économies", "b", "L2")]]
        sk = ecrire.ecrire_sketch(cands, essais=3)
        self.assertEqual(sk["fiche"]["note"], 92)                             # sous-notes incomplètes : pas de 0/100 arbitraire

    def test_chute_hors_sujet_plafonnee(self):
        faux = FauxClaude(); faux.notes = [90, 90, 90, 90, 90, 90]; faux.chute_fausse = True
        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda: faux)
        cands = [[article("Budget 2027 : les économies rejetées", "a", "L1"), article("Budget : les députés et les économies", "b", "L2")]]
        sk = ecrire.ecrire_sketch(cands, essais=1)
        self.assertEqual(sk["fiche"]["note"], 70)                             # 90 mais chute hors sujet : plafonné, donc pas publié
        self.assertEqual(sk["fiche"]["decision"], "à retravailler")

    def test_metaphore_filee_plafonnee(self):
        faux = FauxClaude(); faux.notes = [90, 90, 90, 90, 90, 90]; faux.metaphore = True
        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda: faux)
        cands = [[article("Budget 2027 : les économies rejetées", "a", "L1"), article("Budget : les députés et les économies", "b", "L2")]]
        self.assertEqual(ecrire.ecrire_sketch(cands, essais=1)["fiche"]["note"], 70)

    def test_retouche_repart_de_la_meilleure_version(self):
        faux = FauxClaude(); faux.notes = [75, 60, 92]
        sk = self._lancer(faux)
        self.assertEqual(sk["fiche"]["note"], 92)
        self.assertIn("obtenu 75/100", faux.reecritures[2])                   # après la baisse à 60, on retouche la version à 75
        self.assertIn("objectif : au moins 90", faux.reecritures[2])
        self.assertIn("Réserve de vannes", faux.reecritures[2])

    def test_variable_reecritures_vide(self):
        os.environ["MAX_REECRITURES"] = ""
        try:
            sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda: FauxClaude())
            cands = [[article("Budget 2027 : les économies rejetées", "a", "L1"), article("Budget : les députés et les économies", "b", "L2")]] * 2
            self.assertEqual(ecrire.ecrire_sketch(cands)["fiche"]["note"], 92)    # variable vide : 4 retouches par défaut, pas de plantage
        finally: os.environ.pop("MAX_REECRITURES")

    def test_atelier_et_jury_nourrissent_l_ecriture(self):
        faux = FauxClaude(); sk = self._lancer(faux)
        ecriture = next(m for m in faux.reecritures)                          # premier message envoyé à l'auteur
        self.assertIn("CHUTE IMPOSÉE", ecriture)
        self.assertIn("Il suffit de ne plus le voter", ecriture)              # chute affûtée par le jury
        self.assertIn("vanne 2", ecriture); self.assertNotIn("vanne 3", ecriture)   # seules les vannes retenues
        self.assertIn("RETOUCHE CIBLÉE", faux.reecritures[1])                # réécriture = punch-up, pas tout jeter

    def test_sketch_libre(self):
        faux = FauxClaude(); faux.choix = 1
        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda: faux)
        os.environ["TENDANCES"] = "0"                                          # (les tendances utilisent la recherche web, testées à part)
        try: idees = ecrire.idees_libres(recents=["MÉTRO BONDÉ : ..."])
        finally: os.environ.pop("TENDANCES")
        self.assertEqual(len(idees), 2)
        self.assertIn("économies", idees[1][0]["titre"])
        sk = ecrire.ecrire_sketch(idees, essais=3, libre=True)
        self.assertFalse(any("web_search" in a for a in faux.appels))          # pas de recherche web en sketch libre
        self.assertTrue(any("MODE « SKETCH LIBRE »" in (x or "") and "FICHE DE STYLE" in x for x in faux.systemes))
        self.assertEqual(sk["sources"], [])                                    # aucune source inventée
        self.assertEqual(sk["fiche"]["note"], 92)

    def test_idees_en_texte(self):
        faux = FauxClaude(); vrai = faux.create
        def create(**kw):
            if kw.get("tools", [{}])[0].get("name") == "proposer_idees":
                bloc = types.SimpleNamespace(type="tool_use", name="proposer_idees",
                                             input={"idees": json.dumps([{"titre": "POV : le réveil sonne", "description": "x"}, "Quand le wifi saute"])})
                return types.SimpleNamespace(content=[bloc], usage=None)
            return vrai(**kw)
        faux.create = create
        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda: faux)
        self.assertEqual([c[0]["titre"] for c in ecrire.idees_libres()], ["POV : le réveil sonne", "Quand le wifi saute"])

    def test_choix_hors_gros_titres_refuse(self):
        faux = FauxClaude(); faux.choix = 4
        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda: faux)
        budget = [article("Budget 2027 : les économies rejetées", "a", "L1"), article("Budget : les députés et les économies", "b", "L2")]
        autres = [[article(f"Sujet secondaire numéro {i} sans rapport", "z", f"Z{i}")] for i in range(4)]
        sk = ecrire.ecrire_sketch([budget] + autres, essais=3)
        self.assertEqual(sk["sources"], ["L1"])                               # choix n°4 refusé : on garde le plus gros titre (n°0)
        self.assertNotIn("numéro 3", faux.prompts[0])                         # seuls les 3 plus gros titres sont soumis
        self.assertIn("numéro 1", faux.prompts[0])

    def test_credit_epuise_arret_net(self):
        faux = FauxClaude(); faux.notes = [60]
        vrai = faux.create; n = {"ecritures": 0}
        def create(**kw):
            if kw.get("tools", [{}])[0].get("name") == "rendre_sketch":
                n["ecritures"] += 1
                if n["ecritures"] > 1: raise RuntimeError("Error code: 400 - Your credit balance is too low to access the Anthropic API.")
            return vrai(**kw)
        faux.create = create
        sk = self._lancer(faux)
        self.assertEqual(n["ecritures"], 2)                                   # pas d'acharnement : on s'arrête net
        self.assertEqual(sk["fiche"]["note"], 60)                             # meilleure version gardée, marquée à retravailler
        self.assertEqual(sk["fiche"]["decision"], "à retravailler")

    def test_recherche_web_indisponible(self):
        faux = FauxClaude(web_en_panne=True); sk = self._lancer(faux)
        self.assertEqual(sk["fiche"]["note"], 92)                             # repli sans recherche web, sans planter


class TestGagEclair(unittest.TestCase):
    def test_format_mini(self):
        import subprocess
        code = ("import os,sys; sys.path.insert(0,'moteur'); os.environ['LONGUEUR']='eclair'; import ecrire; "
                "print(ecrire.MINI, ecrire.SECONDES, ecrire.MOTS, 'GAG ÉCLAIR' in ecrire.STYLE_LIBRE); "
                "sk=ecrire.valider({'sujet':'x','repliques':[{'p':'invite','t':'Mon compte.'},{'p':'invite','t':'[cries] Non.'},{'p':'envoyee','t':'Petit plaisir !'}]}, set()); "
                "print(len(sk['repliques']))")
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(os.environ, FORMAT="mini"),
                           cwd=os.path.join(ICI, ".."))
        self.assertEqual(r.stdout.split(), ["True", "15", "à", "22", "60", "True", "3"], r.stderr[-500:])


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


class TestCycle(unittest.TestCase):
    def test_trois_courts_puis_un_long(self):
        import programme
        f = programme.format_du_jour; H = lambda *fs: [{"format": x} for x in fs]
        self.assertEqual([f("cycle", []), f("cycle", H("mini")), f("cycle", H("mini", "mini", "mini")), f("cycle", H("mini", "mini", "mini", "libre")),
                          f("cycle", H("libre", "mini", "actu", "mini")), f("", []), f("actu", []), f("n_importe", [])],
                         ["mini", "mini", "libre", "mini", "mini", "mini", "mini", "mini"])


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


class TestPlanning(unittest.TestCase):
    def test_lancement_manuel(self):
        os.environ["EVENEMENT"] = "workflow_dispatch"
        self.assertTrue(planning.decision()[0])

    def test_pause(self):
        os.environ.update(EVENEMENT="schedule", FREQUENCE="0")
        self.assertFalse(planning.decision()[0])
        os.environ.pop("FREQUENCE"); os.environ.pop("EVENEMENT")

    def test_creneau_de_la_demande_et_doublons(self):
        """Une vidéo qui a attendu son tour garde son créneau ; une 2e demande pour le même créneau ne part pas (doublon)."""
        import datetime as dt
        from zoneinfo import ZoneInfo
        auj = dt.datetime.now(ZoneInfo("Europe/Paris")).date()
        utc = lambda h, mi: dt.datetime.combine(auj, dt.time(h, mi), ZoneInfo("Europe/Paris")).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        moi = {"id": 2, "created_at": utc(8, 1), "display_title": "Créneau son TikTok", "status": "in_progress"}
        autres = [{"id": 1, "created_at": utc(7, 31), "display_title": "Créneau son TikTok", "status": "queued", "html_url": "u1"},   # avant le créneau
                  {"id": 3, "created_at": utc(8, 20), "display_title": "Créneau son TikTok", "status": "queued"}]                      # après nous
        api = lambda c: moi if c.endswith("/runs/2") else {"workflow_runs": [moi] + autres}
        anc = planning._api, dict(os.environ)
        planning._api = api; planning._MOI.clear()
        os.environ.update(EVENEMENT="schedule", FREQUENCE="1", HEURE="08:00", FILIERE="tiktok", GITHUB_RUN_ID="2", ESSAIS_MAX="99")
        try:
            from unittest import mock
            with mock.patch.object(planning, "_hist", return_value=[]):
                self.assertEqual(planning.moment().strftime("%H:%M"), "08:01")       # heure de la demande, même 3 h plus tard
                self.assertTrue(planning.decision()[0])                              # rien avant nous pour ce créneau
                autres[0]["created_at"] = utc(8, 0)                                  # une demande du même créneau, avant nous
                go, raison = planning.decision()
                self.assertFalse(go); self.assertIn("déjà en file", raison)
                self.assertTrue(planning.decision(file=False)[0])                    # au départ de la fabrication : on y va
        finally:
            planning._api = anc[0]; planning._MOI.clear(); os.environ.clear(); os.environ.update(anc[1])


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


class TestPublicationAuto(unittest.TestCase):
    def test_une_video_cochee_par_jour(self):
        """Vidéos cochées dans l'onglet TikTok : la plus ancienne cochée non publiée part chaque jour à l'heure choisie (via Buffer)."""
        import datetime as dt, publication_auto as P
        from zoneinfo import ZoneInfo
        hist = [{"fichier": "a.mp4", "publie": True}, {"fichier": "b.mp4"}, {"fichier": "c.mp4", "publie": False}, {"fichier": "d.mp4"}]
        reg = {"PUBLI_AUTO": "1", "PUBLI_HEURE": "18:30", "PUBLI_FILE": "c.mp4\na.mp4\nd.mp4\nb.mp4\ninconnue.mp4\n-"}
        self.assertEqual(P.file_attente(reg["PUBLI_FILE"], hist), ["d.mp4", "b.mp4"])      # publiée / en échec / inconnue : sautées
        a = lambda h, mi: dt.datetime(2026, 10, 30, h, mi, tzinfo=ZoneInfo("Europe/Paris"))
        self.assertIsNone(P.decision(a(17, 0), reg, hist, False)[0])                    # trop tôt
        self.assertEqual(P.decision(a(18, 0), reg, hist, False)[:2], ("d.mp4", "2026-10-30T18:30"))   # demandée pour l'heure exacte
        self.assertEqual(P.decision(a(21, 0), reg, hist, False)[:2], ("d.mp4", ""))     # heure passée (réveil en retard) : tout de suite
        self.assertIsNone(P.decision(a(18, 25), reg, hist, True)[0])                    # déjà fait aujourd'hui
        self.assertIsNone(P.decision(a(18, 25), dict(reg, PUBLI_AUTO="0"), hist, False)[0])
        self.assertIsNone(P.decision(a(18, 25), dict(reg, PUBLI_FILE="a.mp4"), hist, False)[0])   # rien en attente
        self.assertEqual(P.heure("7h05"), (7, 5)); self.assertEqual(P.heure("n'importe"), (18, 0))

    def test_deux_videos_par_jour(self):
        """2e heure de publication (choix de l'auteur, 1er novembre 2026) : une vidéo par créneau."""
        import datetime as dt, publication_auto as P
        from zoneinfo import ZoneInfo
        hist = [{"fichier": "b.mp4"}, {"fichier": "d.mp4"}]
        reg = {"PUBLI_AUTO": "1", "PUBLI_HEURE": "18:30", "PUBLI_DEUX": "1", "PUBLI_HEURE2": "12:00", "PUBLI_FILE": "d.mp4\nb.mp4"}
        a = lambda h, mi: dt.datetime(2026, 11, 1, h, mi, tzinfo=ZoneInfo("Europe/Paris"))
        self.assertEqual(P.creneaux(reg), [(12, 0), (18, 30)])
        self.assertIsNone(P.decision(a(10, 0), reg, hist, 0)[0])                      # avant midi : rien
        self.assertEqual(P.decision(a(11, 40), reg, hist, 0)[:2], ("d.mp4", "2026-11-01T12:00"))   # 1er créneau
        self.assertIsNone(P.decision(a(14, 0), reg, hist, 1)[0])                      # midi fait, 18 h 30 pas encore
        self.assertEqual(P.decision(a(18, 0), reg, hist, 1)[:2], ("d.mp4", "2026-11-01T18:30"))    # 2e créneau
        self.assertIsNone(P.decision(a(20, 0), reg, hist, 2)[0])                      # les deux faits
        self.assertEqual(P.creneaux(dict(reg, PUBLI_DEUX="0")), [(18, 30)])
        self.assertEqual(P.creneaux(dict(reg, PUBLI_HEURE2="18:45")), [(18, 30)])     # moins d'une heure d'écart : un seul créneau
        self.assertEqual(P.creneaux(dict(reg, PUBLI_HEURE2="")), [(12, 0), (18, 30)])


class TestRendu(unittest.TestCase):
    def test_sous_titres_cales_sur_whisper(self):
        try: import jt
        except Exception as e: self.skipTest(f"dépendances vidéo absentes : {e}")
        g = jt.minutage("Bonsoir. Le budget est perdu.", np.zeros(44100, np.float32), 10.0,
                        [("Bonsoir.", 0.0, 0.5), ("Le", 0.7, 0.8), ("budget", 0.8, 1.2), ("est", 1.2, 1.3), ("perdu.", 1.3, 1.8)])
        self.assertEqual(g[0], ("Bonsoir.", 10.0, 10.5))
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


class TestSerieLot(unittest.TestCase):
    def test_plan_puis_episodes(self):
        import serie
        os.environ["EPISODES"] = "serie"; vrai = serie.FICHIER
        serie.FICHIER = os.path.join(os.path.dirname(__file__), "_serie_lot.json")
        try:
            json.dump({"titre": "Jojo déménage", "episodes": [], "plan": [{"titre": f"Ép {k}", "resume": f"r{k}"} for k in range(1, 4)]},
                      open(serie.FICHIER, "w", encoding="utf-8"))
            for k in range(1, 4):
                prevu, n = serie.a_faire(); self.assertEqual((prevu["titre"], n), (f"Ép {k}", k))
                self.assertIn(f"ÉCRIS L'ÉPISODE {k}", serie.contexte())
                self.assertEqual(serie.enregistrer({"serie_titre": "Jojo déménage", "resume_episode": f"fait {k}"}), k)
            self.assertEqual(serie.a_faire(), (None, 0))
        finally:
            os.environ.pop("EPISODES"); os.path.exists(serie.FICHIER) and os.remove(serie.FICHIER); serie.FICHIER = vrai


class TestQualiteMinimale(unittest.TestCase):
    def test_pas_de_video_sous_le_minimum(self):
        faux = FauxClaude(); faux.chute_fausse = True
        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda: faux)
        cands = [[article("Budget 2027 : les économies rejetées", "a", "L1"), article("Budget : les députés et les économies", "b", "L2")]] * 2
        os.environ["FORCER_FABRICATION"] = "0"
        try:
            with self.assertRaises(ecrire.QualiteInsuffisante): ecrire.ecrire_sketch(cands, essais=1)
        finally: os.environ["FORCER_FABRICATION"] = "1"


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


class TestCastingGratuit(unittest.TestCase):
    def test_genre_par_les_mots(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import doublage as D
        segs = [{"voix": "a", "t": "Papa, une dame m'a parlé."}, {"voix": "b", "t": "Fonce fiston !"}, {"voix": "a", "t": "Je suis sûr ?"}]
        self.assertEqual(D.genre_des_voix(segs, {"a": 178, "b": 160}), {"a": "h", "b": "h"})     # l'ado à la voix aiguë reste un garçon
        segs = [{"voix": "a", "t": "Bonjour madame."}, {"voix": "b", "t": "Je suis désolée."}]
        self.assertEqual(D.genre_des_voix(segs, {"a": 130, "b": 170})["b"], "f")


class TestJuryQualite(unittest.TestCase):
    def test_jury_gratuit_et_corrections(self):
        import shutil, copy
        if not shutil.which("ffmpeg"): self.skipTest("ffmpeg absent")
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import cartoon, qualite
        reps = [("invite", "Papa, elle me fait signe de venir."), ("presentateur", "Vas-y fiston, fonce !"), ("invite", "Bon d'accord, j'y vais.")]
        sk = {"titre_accroche": "Essai", "sujet": "Essai", "repliques": [{"p": p, "t": t} for p, t in reps],
              "decoupage": [{"scene": "1", "repliques": [0, 1, 2], "decor": "a living room"}]}
        sk["repliques"][-1]["chute"] = True
        auds = [(0.3 * np.sin(np.arange(int(22050 * 1.4)) / 22050 * 2 * np.pi * 150)).astype(np.float32) for _ in reps]
        sortie = os.path.join(tempfile.mkdtemp(), "v.mp4"); cartoon.rendre(sk, sortie, auds, mini=True)
        avant = os.environ.get("CLAUDE_INDISPONIBLE"); os.environ["CLAUDE_INDISPONIBLE"] = "1"
        mem = qualite.MEMOIRE; qualite.MEMOIRE = os.path.join(tempfile.mkdtemp(), "q.json")
        try:
            Q = qualite.evaluer(sortie, cartoon.RENDU, sk)
            self.assertEqual(Q["source"], "gratuit"); self.assertEqual(set(Q["jury"]), set(qualite.CRITIQUES))
            self.assertTrue(0 < Q["note"] <= 10)
            cats = {r["categorie"] for v in Q["jury"].values() for r in v["remarques"]}
            self.assertIn("personne_invisible", cats)                                  # « elle me fait signe » mais personne à l'image
            sk2 = copy.deepcopy(sk); faites = qualite.corriger(sk2, Q["corrections"])
            self.assertTrue(faites); self.assertTrue(sk2["studio"].get("figurants"))
            qualite.memoriser(Q, "v.mp4", faites); qualite.memoriser(Q, "w.mp4"); qualite.memoriser(Q, "x.mp4")
            self.assertIn("ERREURS QUI REVIENNENT", qualite.regles_apprises())
        finally:
            qualite.MEMOIRE = mem
            if avant is None: os.environ.pop("CLAUDE_INDISPONIBLE", None)
            else: os.environ["CLAUDE_INDISPONIBLE"] = avant


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
        anc = os.environ.pop("AIDES", None)                                # 12 : machines d'aide selon la durée
        try: self.assertEqual([DP.nb_aides(n) for n in (1300, 3900, 7000, 20000)], [1, 3, 5, 5])
        finally:
            if anc is not None: os.environ["AIDES"] = anc
        env = dict(os.environ)                                             # 9 : chaîne en parallèle
        try:
            os.environ.update(CHAINE="3/10", PREPA_PARALLELE="1"); self.assertTrue(FA.prepa_parallele())
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


class TestFileAttente(unittest.TestCase):
    def test_une_video_a_la_fois_dans_l_ordre(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import file_attente as F
        J = {1: [{"name": "planning", "status": "completed", "conclusion": "success"}, {"name": "emission", "status": "in_progress"}],      # en fabrication
             2: [{"name": "planning", "status": "completed", "conclusion": "success"}, {"name": "emission", "status": "completed", "conclusion": "skipped"}],   # rien à faire
             3: [{"name": "planning", "status": "in_progress"}],                                                                          # planning en cours
             4: [{"name": "planning", "status": "completed", "conclusion": "success"}, {"name": "file", "status": "in_progress"}]}       # attend déjà
        J[5] = J[4]
        R = lambda i, t: {"id": i, "status": "in_progress", "run_started_at": t}
        runs = [R(1, "2026-10-25T10:00:00Z"), R(2, "2026-10-25T10:05:00Z"), R(3, "2026-10-25T10:06:00Z"), R(4, "2026-10-25T10:07:00Z"), R(5, "2026-10-25T10:08:00Z")]
        self.assertEqual([r["id"] for r in F.devant(runs, runs[4], J.get)], [1, 3, 4])     # la 5e attend les 1, 3 et 4 (pas la 2)
        self.assertEqual(F.devant(runs, runs[0], J.get), [])                                # la 1re passe
        relance = dict(runs[0], id=1, run_started_at="2026-10-25T11:00:00Z")                # relancée par le garde : en fin de file
        self.assertEqual([r["id"] for r in F.devant(runs[1:] + [relance], relance, J.get)], [3, 4, 5])


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


class TestReveilSecours(unittest.TestCase):
    def test_relance_coupees_par_github_pas_par_l_auteur(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import relance as R, time as T
        t = T.strftime("%Y-%m-%dT%H:%M:%SZ", T.gmtime(T.time() - 3600)); vieux = T.strftime("%Y-%m-%dT%H:%M:%SZ", T.gmtime(T.time() - 9 * 3600))
        runs = [{"id": 1, "status": "completed", "conclusion": "failure", "run_attempt": 1, "created_at": t},
                {"id": 2, "status": "completed", "conclusion": "cancelled", "run_attempt": 1, "created_at": t},     # coupée par GitHub
                {"id": 3, "status": "completed", "conclusion": "cancelled", "run_attempt": 1, "created_at": t},     # annulée par l'auteur
                {"id": 4, "status": "completed", "conclusion": "failure", "run_attempt": 2, "created_at": t},       # déjà relancée
                {"id": 5, "status": "completed", "conclusion": "failure", "run_attempt": 1, "created_at": vieux},   # trop ancienne
                {"id": 6, "status": "completed", "conclusion": "success", "run_attempt": 1, "created_at": t}]
        self.assertEqual(R.a_relancer(runs, T.time(), lambda i: i == 2), [1, 2])
        self.assertTrue(R.COUPE_GITHUB.search("The job has exceeded the maximum execution time of 2h0m0s"))

    def test_alertes_appareil_mort(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import alerte
        ancien = alerte.MORTS; alerte.MORTS = os.path.join(tempfile.mkdtemp(), "m.json")
        try:
            alerte.noter_mort("https://push.exemple/abc")
            self.assertIn(alerte.empreinte("https://push.exemple/abc"), alerte.morts())
            self.assertNotIn("push.exemple", open(alerte.MORTS).read())                         # jamais l'adresse elle-même
        finally: alerte.MORTS = ancien


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


class TestRelaisIA(unittest.TestCase):
    def test_bascule_claude_vers_mistral_puis_gemini(self):
        import json as _j, io, urllib.request, urllib.error, reseau
        appels = []
        class Rep(io.BytesIO): pass
        def faux_urlopen(req, timeout=0):
            corps = _j.loads(req.data.decode()); appels.append((req.full_url, corps))
            if "mistral" in req.full_url: raise urllib.error.HTTPError(req.full_url, 429, "quota", {}, io.BytesIO(b"monthly quota exceeded"))
            if "tools" not in corps:
                return Rep(_j.dumps({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}}).encode())
            outil = corps["tools"][0]["function"]
            self.assertEqual(outil["parameters"]["properties"]["studio"]["type"], "string")          # Gemini : objet libre demandé en texte
            img = [p for m in corps["messages"] if isinstance(m["content"], list) for p in m["content"] if p["type"] == "image_url"]
            self.assertTrue(img and img[0]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
            rep = {"choices": [{"message": {"tool_calls": [{"id": "1", "function": {"name": "jury", "arguments": _j.dumps(
                {"note": 7, "studio": _j.dumps({"lieux": ["salon"]})})}}]}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
            return Rep(_j.dumps(rep).encode())
        class FauxAnthropic:
            def __init__(self, **k): pass
            class messages:
                @staticmethod
                def create(**kw): raise RuntimeError("Your credit balance is too low")
        avant = {k: os.environ.get(k) for k in ("MISTRAL_API_KEY", "GEMINI_API_KEY", "CLAUDE_INDISPONIBLE")}
        vieux = urllib.request.urlopen, sys.modules.get("anthropic"), reseau.time.sleep
        try:
            reseau.time.sleep = lambda s: None
            os.environ.update(MISTRAL_API_KEY="m", GEMINI_API_KEY="g"); os.environ.pop("CLAUDE_INDISPONIBLE", None)
            urllib.request.urlopen = faux_urlopen; sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=FauxAnthropic)
            reseau.HORS_SERVICE.clear(); reseau.UTILISES.clear()
            outil = {"name": "jury", "description": "x", "input_schema": {"type": "object", "properties": {"note": {"type": "number"}, "studio": {"type": "object"}}}}
            r = reseau.claude().messages.create(model="claude-sonnet-5-5", max_tokens=100, tools=[outil], tool_choice={"type": "tool", "name": "jury"},
                                                messages=[{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}},
                                                                                       {"type": "text", "text": "note"}]}])
            b = [x for x in r.content if x.type == "tool_use"][0]
            self.assertEqual(b.input, {"note": 7, "studio": {"lieux": ["salon"]}}); self.assertTrue(r.gratuit)
            self.assertIn("gemini", reseau.UTILISES)
            r2 = reseau.claude().messages.create(model="x", max_tokens=50, messages=[{"role": "user", "content": "texte seul"}])   # Mistral à 429 : Gemini
            self.assertIn("mistral", reseau.HORS_SERVICE); self.assertEqual(reseau.UTILISES["gemini"], 2)
        finally:
            urllib.request.urlopen = vieux[0]; reseau.time.sleep = vieux[2]
            if vieux[1] is not None: sys.modules["anthropic"] = vieux[1]
            reseau.HORS_SERVICE.clear(); reseau.UTILISES.clear()
            for k, v in avant.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v


class TestLimiteMistral(unittest.TestCase):
    def test_limite_minute_passe_a_gemini(self):
        import json as _j, io, urllib.request, urllib.error, reseau
        vus = []
        def faux_urlopen(req, timeout=0):
            vus.append(req.full_url)
            if "mistral" in req.full_url:
                raise urllib.error.HTTPError(req.full_url, 429, "x", {"Retry-After": "1"}, io.BytesIO(b'{"message":"Rate limit exceeded","code":"1300"}'))
            return io.BytesIO(_j.dumps({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}}).encode())
        avant = {k: os.environ.get(k) for k in ("MISTRAL_API_KEY", "GEMINI_API_KEY", "CLAUDE_INDISPONIBLE")}
        vieux = urllib.request.urlopen, reseau.time.sleep
        try:
            reseau.time.sleep = lambda s: None; urllib.request.urlopen = faux_urlopen
            os.environ.update(MISTRAL_API_KEY="m", GEMINI_API_KEY="g", CLAUDE_INDISPONIBLE="1")
            reseau.HORS_SERVICE.clear(); reseau.EN_PAUSE.clear()
            r = reseau.claude().messages.create(model="x", max_tokens=5, messages=[{"role": "user", "content": "salut"}])
            self.assertEqual(r.content[0].text, "ok"); self.assertNotIn("mistral", reseau.HORS_SERVICE)
            self.assertEqual(sum("mistral" in u for u in vus), 4)                 # 14b, puis 8b avec 2 patiences, puis Gemini
            vus.clear(); reseau.claude().messages.create(model="x", max_tokens=5, messages=[{"role": "user", "content": "encore"}])
            self.assertFalse(any("mistral" in u for u in vus))                    # Mistral en pause une minute
        finally:
            urllib.request.urlopen, reseau.time.sleep = vieux
            reseau.HORS_SERVICE.clear(); reseau.EN_PAUSE.clear(); reseau.UTILISES.clear()
            for k, v in avant.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v


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


class TestRemarqueAuteur(unittest.TestCase):
    def test_remarque_retenue_par_le_jury(self):
        import json as _j, tempfile, regie_action, qualite
        d = tempfile.mkdtemp(); h = os.path.join(d, "historique.json"); r = os.path.join(d, "remarques_auteur.json")
        _j.dump([{"fichier": "v.mp4", "titre": "T"}], open(h, "w"))
        vieux = regie_action.HIST, regie_action.REMARQUES, qualite.REMARQUES_AUTEUR
        avant = {k: os.environ.get(k) for k in ("ACTION", "FICHIER", "VALEUR")}
        try:
            regie_action.HIST, regie_action.REMARQUES, qualite.REMARQUES_AUTEUR = h, r, r
            os.environ.update(ACTION="remarque", FICHIER="v.mp4", VALEUR="4|le père doit être en marcel sur le canapé")
            self.assertEqual(regie_action.main(), 0); self.assertEqual(regie_action.main(), 0)      # rejouable : pas de doublon
            self.assertEqual(len(_j.load(open(r))), 1); self.assertEqual(_j.load(open(h))[0]["note_auteur"], 4)
            self.assertIn("marcel sur le canapé", qualite.regles_apprises())
        finally:
            regie_action.HIST, regie_action.REMARQUES, qualite.REMARQUES_AUTEUR = vieux
            for k, v in avant.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v


class TestModeEco(unittest.TestCase):
    def test_mode_eco(self):
        import reseau
        cles = ("MODE_ECO", "MODELE_CLAUDE", "ETAPES_ECO", "VERSIONS", "PUBLIC_TEST", "TENDANCES", "AMBIANCES_ELEVEN", "MAX_REECRITURES", "SUJETS_MAX")
        avant = {k: os.environ.get(k) for k in cles}
        try:
            os.environ.pop("MODE_ECO", None); os.environ["MAX_REECRITURES"] = "6"
            self.assertFalse(reseau.mode_eco()); self.assertEqual(os.environ["MAX_REECRITURES"], "6")     # coupé : rien ne change
            os.environ["MODE_ECO"] = "1"; os.environ["SUJETS_MAX"] = "1"
            self.assertTrue(reseau.mode_eco())
            self.assertEqual(os.environ["MODELE_CLAUDE"], "claude-sonnet-5-5")
            self.assertEqual((os.environ["MAX_REECRITURES"], os.environ["SUJETS_MAX"], os.environ["VERSIONS"]), ("2", "1", "1"))
            self.assertEqual((os.environ["PUBLIC_TEST"], os.environ["TENDANCES"], os.environ["ETAPES_ECO"]), ("0", "0", "1"))
        finally:
            for k, v in avant.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v

    def test_site_reglage_et_videos_neuves(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn('data-var="MODE_ECO"', src); self.assertIn("ajouterNouvelles(h)", src)
        for wf in ("emission",):                                            # une seule file de mise en ligne du site (nouvelles vidéos seulement :
            # suppression, publication et actions de la régie se voient dans l'appli sans reconstruire le site)
            y = open(os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", wf + ".yml"), encoding="utf-8").read()
            self.assertIn("gh workflow run site.yml", y); self.assertNotIn("deploy-pages", y)


class TestSiteRapide(unittest.TestCase):
    """Site et appli plus rapides (choix de l'auteur du 31 octobre 2026 : A 1-2-3-6, B 7-11, C 12-15, D 16-17)."""
    def test_suppression_directe_et_rafraichissement(self):
        ici = os.path.dirname(__file__)
        src = open(os.path.join(ici, "..", "moteur", "site.py"), encoding="utf-8").read()
        for morceau in ("async function retirerHistorique", "effacerArchives", "noterSuppr(v.fichier,true)", "Supprimée pour de bon",   # A 1-3
                        "If-None-Match", "touchstart", "toutRafraichir", "SUIVI.enCours", "verifierVersion", "version.txt",             # C 12-15
                        "jt_historique", "pleinDe", "posterDe", "_web.mp4", "dessinerCnx", "retour en arrière"):                     # B, D
            self.assertIn(morceau, src)
        for wf in ("supprimer", "publier", "regie"):                       # plus de reconstruction du site (A6, B9)
            self.assertNotIn("site.yml", open(os.path.join(ici, "..", ".github", "workflows", wf + ".yml"), encoding="utf-8").read())
        self.assertNotIn("ffmpeg", open(os.path.join(ici, "..", ".github", "workflows", "supprimer.yml"), encoding="utf-8").read())
        self.assertIn("_web.mp4", open(os.path.join(ici, "..", ".github", "workflows", "emission.yml"), encoding="utf-8").read())
        self.assertIn('nom.replace(".mp4", "_web.mp4")', open(os.path.join(ici, "..", "moteur", "supprimer.py"), encoding="utf-8").read())
        sys.path.insert(0, os.path.join(ici, "..", "moteur"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("site_appli", os.path.join(ici, "..", "moteur", "site.py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        f = m.fiche({"fichier": "2026-10-31_10h03_emission.mp4", "tag": "emissions-2026-10", "titre": "T", "a_verifier": [{"t": 1.0, "quoi": "x"}]})
        self.assertEqual(f["tag"], "emissions-2026-10"); self.assertEqual(len(f["a_verifier"]), 1)

    def test_malade_au_lit_et_appel_avec_telephone(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import studio
        reps = [{"p": "envoyee", "t": "Allô ? Tu viens pas aujourd'hui ?"}, {"p": "invite", "t": "Non je suis malade, je suis cloué au lit."}]
        sk = {"repliques": reps, "doublage": {"contexte": "un employé au téléphone"},
              "studio": {"lieux_separes": {"envoyee": "office", "invite": "cozy living room"}, "lieux_de": {"envoyee": "bureau", "invite": "salon"}}}
        self.assertTrue(studio.separer_lieux(sk))
        self.assertEqual(sk["studio"]["lieux"], ["bureau", "chambre"]); self.assertIn("bed", sk["decoupage"][1]["decor"])
        self.assertTrue(all(r.get("objet") == "telephone" for r in reps))  # un appel : téléphone en main, même si l'IA n'a pas dit « telephone »


class TestAccroches(unittest.TestCase):
    def test_deux_styles_departages_par_les_vues(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import accroches
        sk = {"titre_accroche": "POV : tu commandes de l'eau au bar", "question": "Toi aussi tu fais ça ?"}
        self.assertEqual(set(accroches.variantes(sk)), {"pov", "question"})
        h = [{"style_accroche": "pov", "fichier": f"p{k}"} for k in range(3)] + [{"style_accroche": "question", "fichier": f"q{k}"} for k in range(3)]
        vues = {**{f"p{k}": 100 for k in range(3)}, **{f"q{k}": 900 for k in range(3)}}
        s2 = dict(sk); self.assertEqual(accroches.choisir(s2, h, vues, hasard=lambda: 0.9), "question"); self.assertEqual(s2["titre_accroche"], "Toi aussi tu fais ça ?")
        s3 = dict(sk); self.assertIn(accroches.choisir(s3, [], {}, hasard=lambda: 0.9), ("pov", "question"))   # sans vues : on alterne

class TestSecours(unittest.TestCase):
    """Sans crédit Claude : bascule automatique sur la réserve de sketchs déjà écrits."""
    def test_reserve(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "moteur"))
        import secours, ecrire
        self.assertTrue(secours.claude_indisponible(RuntimeError("aucun sketch exploitable : Your credit balance is too low to access the Anthropic API")))
        self.assertTrue(secours.claude_indisponible(TypeError("Could not resolve authentication method")))
        self.assertFalse(secours.claude_indisponible(ValueError("sketch trop court")))
        ancien = secours.UTILISES; secours.UTILISES = os.path.join(tempfile.mkdtemp(), "u.json")
        try:
            vus = set()
            for fmt in ("mini", "libre", "mini"):
                sk = secours.sketch(fmt); vus.add(sk["sujet"])
                ecrire.valider(sk, set(), libre=True)
                self.assertTrue(sk["repliques"][-1].get("chute"))
                self.assertEqual(sum(len(d["repliques"]) for d in sk["decoupage"]), len(sk["repliques"]))
            self.assertEqual(len(vus), 3)                                                            # jamais deux fois le même
        finally: secours.UTILISES = ancien

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


class TestProfilsTiktok(unittest.TestCase):
    """Sons TikTok : filière à part des sketchs (liste des profils, vidéos déjà utilisées écartées, planning séparé)."""
    def test_liste(self):
        import profils_tiktok as P
        self.assertEqual(P.liste("@charly.bse\nhttps://www.tiktok.com/@Foo_Bar?lang=fr ; baz, @charly.bse"), ["charly.bse", "Foo_Bar", "baz"])
        h = [{"sources": ["https://www.tiktok.com/@x/video/123?_r=1"]}, {"source_audio": "https://www.tiktok.com/@y/video/456"}]
        self.assertEqual(P.deja_utilisees(h), {"123", "456"})
        self.assertFalse(hasattr(P, "tirage"))                             # plus aucun mélange avec les sketchs automatiques
        c = P.connus()                                                     # profils déjà connus : jamais notre propre chaîne
        self.assertTrue(all(x.lower() not in P.NOTRE_CHAINE for x in c))
        anc = os.environ.pop("PROFILS_TIKTOK", None)
        try: self.assertEqual(P.liste(), c)                                # liste vide : les profils déjà connus
        finally:
            if anc is not None: os.environ["PROFILS_TIKTOK"] = anc

    def test_plannings_separes(self):
        import datetime as dt
        from zoneinfo import ZoneInfo
        now = dt.datetime.now(ZoneInfo("Europe/Paris"))
        hhmm = (now - dt.timedelta(minutes=5)).strftime("%H:%M")
        if (now - dt.timedelta(minutes=5)).date() != now.date(): self.skipTest("minuit")
        fich = f"{now.date()}_{now.strftime('%Hh%M')}_emission.mp4"
        hist = [{"date": now.date().isoformat(), "auto": True, "filiere": "tiktok", "fichier": fich}]
        anc = {k: os.environ.get(k) for k in ("EVENEMENT", "FILIERE", "HEURE", "FREQUENCE")}
        try:
            os.environ.update(EVENEMENT="schedule", HEURE=hhmm, FREQUENCE="1")
            planning._hist = lambda: hist
            os.environ["FILIERE"] = "tiktok"; self.assertFalse(planning.decision()[0])     # créneau TikTok déjà traité
            os.environ["FILIERE"] = ""; self.assertTrue(planning.decision()[0])            # le planning des sketchs n'est pas touché
        finally:
            import importlib; importlib.reload(planning)
            for k, v in anc.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v


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


class TestLegende(unittest.TestCase):
    """Description TikTok : source du son sans lien, beaucoup de hashtags liés à la vidéo."""

    def test_sans_lien_et_hashtags(self):
        import legende, doublage
        sk = {"legende": "Quand ton père voit ta note", "question": "Et vous ?", "hashtags": ["pov", "École"],
              "repliques": [{"p": "presentateur", "t": "Ma puce, c'est quoi cette note ?"}, {"p": "invite", "t": "Bah… deux, papa."}],
              "doublage": {"auteur": "compte", "source": "https://www.tiktok.com/@compte/video/123"}}
        c = doublage.credit(sk); self.assertNotIn("http", c); self.assertIn("@compte", c)
        t = legende.composer(sk, c)
        self.assertNotIn("http", t); self.assertIn("#petitsdramas", t); self.assertIn("#famille", t); self.assertIn("#ecole", t)
        self.assertGreaterEqual(t.count("#"), 10)
        self.assertEqual(legende.sans_lien("Son : @a — https://vm.tiktok.com/xyz"), "Son : @a")

    def test_ancienne_legende_completee(self):
        import legende
        t = legende.completer("Super vidéo\n\n🎧 Son original : @x — https://www.tiktok.com/@x/video/1")
        self.assertNotIn("http", t); self.assertIn("#petitsdramas", t)


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


class TestOngletTiktokReplie(unittest.TestCase):
    def test_menus_deroulants(self):
        """Demande de l'auteur (1er novembre 2026) : tout l'onglet TikTok en menus déroulants, ouverts / fermés gardés sur l'appareil."""
        src = open(os.path.join(os.path.dirname(__file__), "..", "moteur", "site.py"), encoding="utf-8").read()
        i = src.index('<div id="o-tiktok"'); j = src.index("STATISTIQUES -->", i); bloc = src[i:j]
        self.assertGreaterEqual(bloc.count('class="groupe repliTk"'), 6)
        self.assertEqual(bloc.count('<section class="panneau"'), 1)        # seule la fabrication en cours reste toujours visible
        self.assertIn('id="filtresRepli"', bloc); self.assertIn("jt_replis", src)


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
            for x in (285, 795): self.assertFalse((c[SR.PIED_Y, x] == (90, 90, 120)).all())
        im, prof = self._decor(meuble=(0, 880, 1100, 1536))                # aucun sol libre : refusé (décor dessiné à la place)
        self.assertIsNone(SR.cadrer(im, prof, 2))

    def test_banque_et_budget(self):
        """Fausse IA Modal : 2 tirages (un sans sol libre, un bon) -> le bon est cadré, rangé dans la banque à part, compté dans le
        budget du mois ; la 2e fois, le lieu est repris de la banque sans rien demander à Modal."""
        import decors, cv2 as _cv
        dossier = tempfile.mkdtemp(); avant = decors.BANQUE, decors.COMPTEUR
        decors.BANQUE = dossier; decors.COMPTEUR = os.path.join(dossier, "compteur.json")
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
            out2 = decors.generer_semi(sk); self.assertEqual(list(out2), [0]); self.assertEqual(len(appels), 1)   # repris de la banque
            self.assertIsNone(decors.voisin("cozy living room, sofa, posters on the wall, coffee table, lamp, television", 0.1))   # jamais pour un décor croquis
        finally:
            decors.BANQUE, decors.COMPTEUR = avant
            if anc is None: sys.modules.pop("modal", None)
            else: sys.modules["modal"] = anc

    def test_moteur_garde_la_peinture(self):
        src = open(os.path.join(ICI, "..", "moteur", "cartoon.py"), encoding="utf-8").read()
        self.assertIn('SEMI_ = set(sk.get("_decors_semi") or [])', src); self.assertEqual(src.count("if sc_ in SEMI_: continue"), 2)
        p = open(os.path.join(ICI, "..", "moteur", "principal.py"), encoding="utf-8").read()
        self.assertIn("decors_mod.generer_semi(sk", p); self.assertIn('sk["_decors_semi"] = sorted(decors_mod.SEMI)', p)
        self.assertIn("def generer_semi", open(os.path.join(ICI, "..", "moteur", "decor_modal.py"), encoding="utf-8").read())


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
