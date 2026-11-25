"""Tests : Site, planning, file d'attente, profils, publication.
Lancer tous les tests : python -m unittest discover -s tests -v"""
from commun import *  # noqa: F401,F403 (chemins, réglages des tests, modules, SKETCH, FauxClaude…)


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
        reg = {"PUBLI_AUTO": "1", "PUBLI_HEURE": "18:30", "PUBLI_DEUX": "1", "PUBLI_HEURE2": "12:00", "PUBLI_FILE": "d.mp4\nb.mp4",
               "PUBLI_FRANCO": "0"}                                        # (2e heure libre : créneau francophonie coupé)
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
        fr = dict(reg, PUBLI_FRANCO="1", PUBLI_HEURE="07:30")                 # francophonie (24 novembre) : 22 h 30 chaque jour
        self.assertEqual(P.decision(dt.datetime(2026, 11, 2, 22, 10, tzinfo=ZoneInfo("Europe/Paris")), fr, hist, 1)[:2], ("d.mp4", "2026-11-02T22:30"))


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


class TestOngletTiktokReplie(unittest.TestCase):
    def test_menus_deroulants(self):
        """Demande de l'auteur (1er novembre 2026) : tout l'onglet TikTok en menus déroulants, ouverts / fermés gardés sur l'appareil."""
        src = open(os.path.join(os.path.dirname(__file__), "..", "moteur", "site.py"), encoding="utf-8").read()
        i = src.index('<div id="o-tiktok"'); j = src.index("STATISTIQUES -->", i); bloc = src[i:j]
        self.assertGreaterEqual(bloc.count('class="groupe repliTk"'), 6)
        self.assertEqual(bloc.count('<section class="panneau">'), 1)        # seule la fabrication en cours reste toujours visible
        self.assertIn('id="filtresRepli"', bloc); self.assertIn("jt_replis", src)


class TestPublicationAutoGh(unittest.TestCase):
    """Les 2 créneaux de publication automatique ne partaient jamais : « gh api … -R dépôt » est refusé par gh."""
    def test_pas_de_R_pour_gh_api(self):
        import publication_auto as P
        vus = []
        avant = P.subprocess.run, os.environ.get("GITHUB_REPOSITORY")
        try:
            os.environ["GITHUB_REPOSITORY"] = "moi/depot"
            P.subprocess.run = lambda cmd, **k: vus.append(cmd) or types.SimpleNamespace(returncode=0, stdout="[]", stderr="")
            P._gh("api", "repos/moi/depot/actions/runs"); P._gh("workflow", "run", "publier.yml")
        finally:
            P.subprocess.run = avant[0]
            if avant[1] is None: os.environ.pop("GITHUB_REPOSITORY", None)
            else: os.environ["GITHUB_REPOSITORY"] = avant[1]
        self.assertNotIn("-R", vus[0]); self.assertEqual(vus[1][-2:], ["-R", "moi/depot"])


class TestPhraseAbonne(unittest.TestCase):
    """Choix de l'auteur (6 novembre, proposition 5) : une phrase d'abonnement dans chaque description."""
    def test_phrase(self):
        import legende
        d = legende.composer({"legende": "Texte.", "question": "Et toi ?"}, "🎧 Son original : @x")
        self.assertIn(legende.ABONNE, d); self.assertLess(d.index(legende.ABONNE), d.index("🎧"))
        v = legende.completer("Ancien texte\n\n🎧 Son original : @x\n\n#humour")
        self.assertEqual(v.count("Abonne-toi"), 1); self.assertLess(v.index("Abonne-toi"), v.index("🎧"))
        self.assertEqual(legende.completer(v).count("Abonne-toi"), 1)    # jamais deux fois
        os.environ["PHRASE_ABONNE"] = "0"
        try: self.assertNotIn("Abonne", legende.composer({"legende": "T."}))
        finally: os.environ.pop("PHRASE_ABONNE", None)


class TestStockPublication(unittest.TestCase):
    def test_compteur_au_dessus_de_la_fabrication(self):
        src = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        for o in ("o-tiktok", "o-accueil"):
            k = src.index('id="%s"' % o) if 'id="%s"' % o in src else 0
            bloc = src[k:k + 4000]
            if "Fabrication en cours" in bloc:
                self.assertLess(bloc.index("stockPubli"), bloc.index("Fabrication en cours"))
        self.assertIn("function rendreStock()", src); self.assertIn("attentePubli(filePubli())", src)


class TestSiteTikTokSeul(unittest.TestCase):
    """Grand ménage du 15 novembre : sketchs et Jojo / Kévin / Lila masqués sur le site (pas effacés)."""
    def test_masque_pas_efface(self):
        src = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn('class="tiktok-seul"', src); self.assertIn("body.tiktok-seul .ancien{display:none!important}", src)
        self.assertIn('<button class="onglet ancien" data-o="accueil">', src); self.assertIn('<button class="onglet ancien" data-o="videos">', src)
        self.assertIn('<details class="groupe ancien"><summary>✍️ Écriture</summary>', src)
        self.assertIn('data-var="PERSO_JOJO"', src)                       # toujours là, juste caché
        self.assertIn("SITE_COMPLET", src)
        self.assertTrue(os.path.exists(os.path.join(ICI, "..", "docs", "archives_sketchs.md")))


class TestChargerVersion(unittest.TestCase):
    def test_bouton_charger_la_derniere_version(self):
        src = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn('id="chargerVersion"', src); self.assertIn("async function rechargerPropre()", src)
        self.assertNotIn('class="action" id="chargerVersion"', src)        # jamais grisé : marche même sans la clé de la régie


class TestRegistreDesPannes15Nov(unittest.TestCase):
    """Registre des pannes du 15 novembre : Gemini « quota dépassé » / « trop lent » coupait Gemini pour toute la vidéo."""

    def _faux(self, reponses):
        import urllib.error
        vus = []
        def urlopen(req, timeout=None):
            corps = json.loads(req.data.decode()); vus.append(corps["model"])
            r = reponses.pop(0)
            if isinstance(r, Exception): raise r
            o = io.BytesIO(json.dumps(r).encode()); o.headers = {}; return o
        return urlopen, vus

    def test_gemini_quota_d_un_modele_passe_au_suivant(self):
        import reseau, urllib.error, urllib.request
        q = urllib.error.HTTPError("u", 429, "Too Many", {}, io.BytesIO(b'{"error":{"message":"You exceeded your current quota","details":[{"quotaId":"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}}'))
        lent = TimeoutError("The read operation timed out")
        ok = {"choices": [{"message": {"content": "bonjour"}}]}
        f, vus = self._faux([q, lent, lent, ok])
        anc, anc_a = urllib.request.urlopen, reseau._attendre
        urllib.request.urlopen = f; reseau._attendre = lambda x: None
        os.environ.setdefault("GEMINI_API_KEY", "x")
        try: r = reseau._appel_openai("gemini", {"messages": [{"role": "user", "content": "salut"}], "max_tokens": 50})
        finally: urllib.request.urlopen, reseau._attendre = anc, anc_a
        self.assertEqual(r.content[0].text, "bonjour")
        m = reseau.FOURNISSEURS["gemini"]["texte"]
        self.assertEqual(vus, [m[0], m[1], m[1], m[2]])                    # quota du 1er -> 2e ; 2e trop lent deux fois -> 3e

    def test_notification_avec_les_vraies_notes(self):
        import principal
        self.assertEqual(principal.resume_alerte({"filiere": "tiktok", "confiance": 76, "jury": {"note": 8.6}, "a_verifier": [1, 2]}),
                         "confiance 76/100 · jury 8.6/10 · ⚠️ 2 point(s) à vérifier")
        self.assertEqual(principal.resume_alerte({}, {"note": 88}), "note 88/100")


class TestHeureStatsAffichee(unittest.TestCase):
    def test_heure_des_stats_sous_la_case(self):
        src = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        i = src.index('data-var="PUBLI_HEURE_AUTO"'); self.assertIn('id="heureStats"', src[i:i + 800])
        self.assertIn("function heuresStats(vids)", src); self.assertIn("HEURES_LIVE=H_", src)


class TestPlusieursEnMemeTemps(unittest.TestCase):
    """Demande de l'auteur du 15 novembre : plusieurs vidéos fabriquées en même temps (EN_MEME_TEMPS, 2 par défaut)."""
    def test_places_et_aides(self):
        import file_attente as F, dessin_partage as DP
        env = dict(os.environ)
        try:
            os.environ.pop("AIDES", None); os.environ.pop("EN_MEME_TEMPS", None)
            self.assertEqual(F.en_meme_temps(), 2)
            self.assertEqual(F.bloquants([1]), []); self.assertEqual(F.bloquants([1, 2]), [2]); self.assertEqual(F.bloquants([1, 2, 3], 3), [3])
            self.assertEqual(F.bloquants([1], 1), [1])                     # 1 = l'une après l'autre (comme avant)
            os.environ["CHAINE"] = "3/10"; self.assertFalse(F.prepa_parallele())   # plusieurs à la fois : chaque vidéo a sa place entière
            self.assertEqual(DP.nb_aides(7000), 3)                         # 2 à la fois : 3 aides au plus chacune
            os.environ["EN_MEME_TEMPS"] = "5"; self.assertEqual(DP.nb_aides(7000), 0)   # 5 et plus : chacune dessine seule
            os.environ["EN_MEME_TEMPS"] = "99"; self.assertEqual(F.en_meme_temps(), 8)
        finally: os.environ.clear(); os.environ.update(env)
        src = open(os.path.join(ICI, "..", "moteur", "site.py"), encoding="utf-8").read()
        self.assertIn('data-var="EN_MEME_TEMPS" data-def="2"', src)
        y = open(os.path.join(ICI, "..", ".github", "workflows", "emission.yml"), encoding="utf-8").read()
        self.assertEqual(y.count("EN_MEME_TEMPS: ${{ vars.EN_MEME_TEMPS || '2' }}"), 2)
