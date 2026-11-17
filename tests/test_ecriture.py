"""Tests : Écriture, IA et jury (sketchs mis de côté compris).
Lancer tous les tests : python -m unittest discover -s tests -v"""
from commun import *  # noqa: F401,F403 (chemins, réglages des tests, modules, SKETCH, FauxClaude…)


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


class TestCycle(unittest.TestCase):
    def test_trois_courts_puis_un_long(self):
        import programme
        f = programme.format_du_jour; H = lambda *fs: [{"format": x} for x in fs]
        self.assertEqual([f("cycle", []), f("cycle", H("mini")), f("cycle", H("mini", "mini", "mini")), f("cycle", H("mini", "mini", "mini", "libre")),
                          f("cycle", H("libre", "mini", "actu", "mini")), f("", []), f("actu", []), f("n_importe", [])],
                         ["mini", "mini", "libre", "mini", "mini", "mini", "mini", "mini"])


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


class TestCompteRendu(unittest.TestCase):
    """Demande de l'auteur du 7 novembre : les problèmes du compte rendu de chaque vidéo sont corrigés tout de suite."""

    def test_texte_du_compte_rendu(self):
        import compte_rendu as CR
        pts = [{"t": 12.3, "quoi": "pendant la réplique de invite, c'est un autre personnage qui bouge"},
               {"t": 60.1, "quoi": "saut d'image hors d'une coupe prévue"}]
        jury = {"directeur_artistique": {"remarques": [{"moment": 4.0, "probleme": "Aucun téléphone visible alors qu'elle appelle"},
                                                       {"probleme": "Les personnages pourraient être plus expressifs"}]}}
        t = CR.texte(pts, jury, [{"ok": False, "revoir": True, "controle": "dialogue équilibré", "detail": "une voix dit 90 %"}])
        self.assertIn("à 12.3 s", t); self.assertIn("téléphone", t); self.assertIn("dialogue équilibré", t)
        self.assertNotIn("saut d'image", t); self.assertNotIn("pourraient", t)       # technique / avis de goût : rien à corriger
        h = {"a_verifier": pts, "jury": {"remarques": ["Le malade devrait être alité dans une chambre"]}}
        self.assertIn("alité", CR.depuis_historique(h))
        self.assertTrue(CR.meilleure(60, 72)); self.assertFalse(CR.meilleure(72, 60)); self.assertTrue(CR.meilleure(70, 70, 7.5, 8.1))

    def test_branche_dans_la_fabrication(self):
        src = open(os.path.join(ICI, "..", "moteur", "principal.py"), encoding="utf-8").read()
        self.assertIn("corriger_compte_rendu(sk, base, audios, mots, decors, fmt, A_VERIFIER, modal_ok, QUALITE)", src)
        self.assertIn('_mode == "compte_rendu"', src); self.assertIn('sortie/.perdante', src)
        r = open(os.path.join(ICI, "..", "moteur", "remarque.py"), encoding="utf-8").read(); self.assertIn("def appliquer(sk, texte, memoriser=True)", r)
        s = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn('|compte_rendu"', s); self.assertIn('id="tkCorrigerTout"', s)


class TestNotesTikTok(unittest.TestCase):
    """Demande de l'auteur du 7 novembre : notes des vidéos sur les sons TikTok au plus haut (défauts réglés, reproches injustes retirés)."""

    def test_sous_titres_lisibles(self):
        import jt
        t = "Mais qu est-ce que tu racontes là, t es complètement fou mon pote"
        r = jt.minutage(t, None, 10, [(w, i * 0.15, i * 0.15 + 0.12) for i, w in enumerate(t.split())])
        self.assertTrue(all(b - a + (0.2 if k == len(r) - 1 else 0) >= 0.3 for k, (_, a, b) in enumerate(r)))   # plus de groupe qui « clignote »
        self.assertTrue(all(r[k][2] <= r[k + 1][1] + 1e-9 for k in range(len(r) - 1)))   # jamais deux groupes en même temps
        self.assertEqual(" ".join(g for g, _, _ in r).split(), t.split())             # aucun mot perdu
        self.assertEqual(jt.lisibles([("Bonjour à tous", 0.0, 1.0)]), [("Bonjour à tous", 0.0, 1.0)])

    def test_debut_coupe_au_premier_mot(self):
        import doublage
        self.assertAlmostEqual(doublage.attente_premier_mot([{"s": 4.28, "e": 4.5}]), 3.98)
        self.assertEqual(doublage.attente_premier_mot([{"s": 0.6, "e": 0.9}]), 0.0)
        src = open(os.path.join(ICI, "..", "moteur", "doublage.py"), encoding="utf-8").read()
        self.assertIn("extra = attente_premier_mot(mots)", src)

    def test_son_impose_jamais_reproche(self):
        import qualite
        jury = {"humoriste": {"note": 6.4, "remarques": [{"probleme": "La chute finale manque de punch."},
                                                         {"probleme": "Le chat devrait grimacer", "correction": {"type": "jeu"}}]},
                "son": {"note": 7.0, "remarques": [{"probleme": "Ambiance sonore vide, aucun bruitage"}]},
                "directeur_artistique": {"note": 8.0, "remarques": [{"probleme": "La chambre manque de détails"}]}}
        self.assertEqual(qualite.sans_reproches_son_impose(jury), 2)
        self.assertEqual(jury["humoriste"]["note"], 7.2); self.assertEqual(len(jury["humoriste"]["remarques"]), 1)
        self.assertEqual(jury["directeur_artistique"]["note"], 8.0)
        self.assertTrue(qualite.son_impose({"doublage": True}))
        R = {"ph": [{"i": 0, "p": "presentateur", "deb": 0.2, "fin": 40, "texte": "x " * 50, "emo": "neutre", "scene": 0, "groupes": [("x x", 0.2, 0.8)]}],
             "total": 45, "doublage": True, "mini": True, "plans": [], "fiches": {}}
        cats = [r["categorie"] for v in qualite.jury_gratuit(R, {"repliques": []}).values() for r in v["remarques"]]
        self.assertNotIn("trop_long", cats); self.assertNotIn("sous_titres_rapides", cats)   # durée imposée par le son, groupes lisibles

    def test_corrige_compte_comme_bon(self):
        src = open(os.path.join(ICI, "..", "moteur", "equipe.py"), encoding="utf-8").read()
        self.assertIn('"téléphone en main seulement s\'il en est question", True', src)
        self.assertIn("accord >= 0.85 or (accord >= 0.6 and tranches)", src)
        v = open(os.path.join(ICI, "..", "moteur", "verif_finale.py"), encoding="utf-8").read()
        self.assertNotIn('"invite": "Kévin"', v)                                # prénoms internes trompaient l'IA de contrôle
