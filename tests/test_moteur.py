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
        for wf in ("emission", "publier", "supprimer", "regie"):                # une seule file de mise en ligne du site
            y = open(os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", wf + ".yml"), encoding="utf-8").read()
            self.assertIn("gh workflow run site.yml", y); self.assertNotIn("deploy-pages", y)


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
