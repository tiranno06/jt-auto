"""Tests des composants du robot (sans réseau, sans clé API, sans GPU).
Lancer : python -m unittest discover -s tests -v"""
import json, os, sys, types, unittest
import numpy as np

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, "..", "moteur"))
os.environ.setdefault("LONGUEUR", "pro")
import actu, ecrire, voix_banque, planning  # noqa: E402


def article(titre, source, lien=None, resume=""):
    return dict(titre=titre, resume=resume, lien=lien or f"https://{source}.fr/{abs(hash(titre))}", date=None, source=source)


class TestRecherche(unittest.TestCase):
    def setUp(self):
        self._lire = actu.lire_flux

    def tearDown(self):
        actu.lire_flux = self._lire

    def test_filtres(self):
        self.assertTrue(actu.DRAMES.search("Un mort dans un accident"))
        self.assertTrue(actu.RUBRIQUES.search("L’actu de ce vendredi 9 octobre"))
        self.assertTrue(actu.RUBRIQUES.search("Les seuils techniques sur les marchés - 09/10"))
        self.assertFalse(actu.DRAMES.search("Budget 2027 : les députés rejettent les économies"))

    def test_candidats_distincts_et_classes(self):
        items = [article("Budget 2027 : les députés rejettent les économies", "a"),
                 article("Les économies du budget rejetées par les députés", "b"),
                 article("Budget : les députés taillent dans les économies", "c"),
                 article("Carburant : le prix de l'essence bat un record", "d"),
                 article("Prix record de l'essence à la pompe, le carburant flambe", "e"),
                 article("Un chat élu maire d'un village", "f"),
                 article("Accident mortel sur l'autoroute", "g")]
        actu.lire_flux = lambda u: items if u == actu.FLUX[0] else []
        c = actu.candidats_du_jour()
        self.assertGreaterEqual(len(c), 2)
        self.assertIn("Budget", c[0][0][0]["titre"])                          # le sujet le plus repris en premier
        tous = [a["titre"] for sel, _ in c for a in sel]
        self.assertFalse(any("Accident" in t for t in tous))                  # drames exclus
        self.assertFalse(any("chat" in t for t in tous))                      # sujet repris une seule fois : écarté

    def test_gros_titres_a_la_une_en_premier(self):
        politique = [article(f"Réforme des retraites : le Sénat examine le texte ({m})", m) for m in "abcd"]
        une = [article(f"Carburant : le prix de l'essence bat un record ({m})", m) for m in ("lemonde", "figaro", "bfm", "franceinfo")]
        sport = [article(f"Lens - OL : revivez le match ({m})", m) for m in ("lequipe", "bfm", "rmc")]
        bruit = [article(f"Brève {chr(97 + i % 26)}{i} isolée numéro{i} motunique{i}", f"s{i}") for i in range(60)]   # volume réaliste de flux
        actu.lire_flux = lambda u: politique + bruit if u == actu.FLUX[0] else une + sport if u == actu.UNES[0] else []
        c = actu.candidats_du_jour()
        self.assertIn("essence", c[0][0][0]["titre"])                           # le sujet à la une passe devant
        self.assertIn("à la une chez 4", c[0][1])
        self.assertIn("secondaire", c[1][1])                                     # pas à la une : signalé comme secondaire
        self.assertFalse(any("Lens" in a["titre"] for sel, _ in c for a in sel)) # direct sportif écarté

    def test_titre_reduit_a_un_nom(self):
        items = [article("Gabriel Attal", "a"), article("Gabriel Attal ", "b", resume="gabriel attal"),
                 article("Gabriel Attal annonce sa candidature à la présidentielle", "c"),
                 article("Présidentielle : Gabriel Attal candidat, annonce surprise", "d")]
        actu.lire_flux = lambda u: items if u == actu.UNES[0] else []
        c = actu.candidats_du_jour()
        self.assertGreaterEqual(len(c[0][0][0]["titre"].split()), 4)            # on présente un vrai titre, pas un simple nom
        self.assertIn("Attal", c[0][0][0]["titre"])

    def test_sujet_deja_traite_ecarte(self):
        recents = [sorted(actu.empreinte("3000 PROFS EXPRESS Le ministère a trouvé 3 000 profs en 24 heures, des remplaçants recrutés en vitesse."))]
        profs = [article(f"Les 3024 professeurs remplaçants recrutés en un jour : le ministre interrogé ({m})", m) for m in ("lemonde", "figaro", "bfm")]
        budget = [article(f"Budget 2027 : la commission des finances rejette les recettes ({m})", m) for m in ("lemonde", "figaro", "libe")]
        bruit = [article(f"Brève {i} isolée motunique{i}", f"s{i}") for i in range(60)]
        actu.lire_flux = lambda u: profs + budget + bruit if u == actu.UNES[0] else []
        c = actu.candidats_du_jour(sujets_recents=recents)
        self.assertIn("Budget", c[0][0][0]["titre"])                            # le sujet d'hier n'est pas repris
        self.assertFalse(any("professeurs" in sel[0]["titre"] for sel, _ in c))
        self.assertTrue(actu.DRAMES.search("Un séisme de magnitude 7,7 a secoué le Panama"))   # catastrophes exclues

    def test_deja_vus_et_flux_en_panne(self):
        items = [article("Budget 2027 : les députés rejettent les économies", "a", "L1"),
                 article("Les économies du budget rejetées par les députés", "b", "L2"),
                 article("Un chat élu maire d'un village", "c", "L3")]
        def lire(u):
            if u == actu.FLUX[1]: raise OSError("flux en panne")
            return items if u == actu.FLUX[0] else []
        actu.lire_flux = lire
        self.assertEqual(len(actu.candidats_du_jour()), 1)                    # un flux en panne ne bloque pas
        self.assertEqual(actu.candidats_du_jour(deja_vus={"L1", "L2"}), [])   # liens déjà traités : rien


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
    """Simule l'API : choix du candidat 1, puis sketch noté 60 (réécriture demandée) puis 86."""
    def __init__(self, web_en_panne=False, critique_vide=False, sources=("L1",)):
        self.notes = [60, 86]; self.appels = []; self.web_en_panne = web_en_panne; self.choix = 1; self.prompts = []
        self.critique_vide = critique_vide; self.sources = list(sources); self.reecritures = []; self.sans_total = False; self.chute_fausse = False; self.metaphore = False
        self.messages = self

    def create(self, **kw):
        noms = [t.get("name") for t in kw.get("tools", [])]
        self.appels.append(noms)
        if self.web_en_panne and "web_search" in noms: raise RuntimeError("outil web non autorisé")
        if "choisir_sujet" in noms: self.prompts.append(kw["messages"][0]["content"]); out = {"notes": [{"index": 0, "note": 4}, {"index": 1, "note": 9}], "choix": self.choix, "angle": "angle test", "faits_verifies": ["fait"]}
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
        self.assertEqual(sk["fiche"]["note"], 86)
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
        self.assertEqual(sk["fiche"]["note"], 86)                             # sous-notes incomplètes : pas de 0/100 arbitraire

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

    def test_variable_reecritures_vide(self):
        os.environ["MAX_REECRITURES"] = ""
        try:
            sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda: FauxClaude())
            cands = [[article("Budget 2027 : les économies rejetées", "a", "L1"), article("Budget : les députés et les économies", "b", "L2")]] * 2
            self.assertEqual(ecrire.ecrire_sketch(cands)["fiche"]["note"], 86)    # variable vide : 3 réécritures par défaut, pas de plantage
        finally: os.environ.pop("MAX_REECRITURES")

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
        self.assertEqual(sk["fiche"]["note"], 86)                             # repli sans recherche web, sans planter


class TestVoix(unittest.TestCase):
    def test_nombres(self):
        self.assertEqual(voix_banque.en_lettres(3000), "trois mille")
        self.assertEqual(voix_banque.en_lettres(71), "soixante et onze")
        self.assertEqual(voix_banque.en_lettres(2027), "deux mille vingt sept")

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


if __name__ == "__main__":
    unittest.main()
