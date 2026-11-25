"""Envois vers TikTok (25 novembre 2026) : bon compte Buffer et vérification de chaque envoi."""
from commun import *  # noqa: F401,F403
import datetime, unittest
import publier, verif_envois

PD = {"id": "pd", "name": "petitsdramas", "displayName": "petitsdramas", "externalLink": "https://tiktok.com/@petitsdramas", "service": "tiktok"}
BZ = {"id": "bz", "name": "buzz.insolite", "displayName": "buzz.insolite", "externalLink": "https://tiktok.com/@buzz.insolite", "service": "tiktok"}
MAINT = datetime.datetime(2026, 11, 25, 10, 0, tzinfo=datetime.timezone.utc)


class TestCompteBuffer(unittest.TestCase):
    def setUp(self):
        for v in ("BUFFER_TIKTOK", "TIKTOK_COMPTE", "BUFFER_CHANNEL_ID"): os.environ.pop(v, None)

    def test_bon_compte_meme_si_un_autre_est_premier(self):
        self.assertEqual(publier.choisir_canal([BZ, PD], "tiktok"), "pd")
        self.assertEqual(publier.choisir_canal([PD, BZ], "tiktok"), "pd")

    def test_nom_avec_point(self):
        os.environ["TIKTOK_COMPTE"] = "@petits.dramas"
        try: self.assertEqual(publier.choisir_canal([BZ, PD], "tiktok"), "pd")
        finally: os.environ.pop("TIKTOK_COMPTE")
        self.assertFalse(publier.meme_compte("petitsdramas", "buzz.insolite"))

    def test_jamais_au_hasard(self):
        autre = dict(BZ, id="x", name="autre", displayName="autre", externalLink="https://tiktok.com/@autre")
        with self.assertRaises(RuntimeError): publier.choisir_canal([BZ, autre], "tiktok")
        self.assertEqual(publier.choisir_canal([BZ], "tiktok"), "bz")       # un seul compte : utilisé (nom changé ?)
        self.assertIsNone(publier.choisir_canal([BZ], "youtube"))


class TestVerificationEnvois(unittest.TestCase):
    def etat(self, **k):
        d = {"status": "sent", "dueAt": "2026-11-25T06:30:00.000Z", "error": None, "channel": PD,
             "externalLink": "https://tiktok.com/@petitsdramas/video/1"}
        d.update(k); return d

    def test_juger(self):
        self.assertEqual(verif_envois.juger(self.etat(), "petitsdramas", MAINT)[0], "ok")
        v, r = verif_envois.juger(self.etat(channel=BZ, externalLink="https://tiktok.com/@buzz.insolite/video/2"), "petitsdramas", MAINT)
        self.assertEqual(v, "rate"); self.assertIn("buzz.insolite", r)
        self.assertEqual(verif_envois.juger(self.etat(status="error", error={"message": "video too long"}, externalLink=""), "petitsdramas", MAINT)[0], "rate")
        self.assertEqual(verif_envois.juger(self.etat(status="scheduled", externalLink="", dueAt="2026-11-25T09:30:00Z"), "petitsdramas", MAINT)[0], "attente")
        self.assertEqual(verif_envois.juger(self.etat(status="scheduled", externalLink=""), "petitsdramas", MAINT)[0], "rate")   # 3h30 de retard

    def test_mauvais_compte_rattrape_puis_mis_de_cote(self):
        hist = [{"fichier": "a.mp4", "publie": True, "buffer_post": "p1"},
                {"fichier": "b.mp4", "publie": True, "buffer_post": "p2"},
                {"fichier": "c.mp4", "publie": True, "buffer_post": "p3"},
                {"fichier": "d.mp4", "publie": True}]
        etats = {"p1": self.etat(channel=BZ, externalLink="https://tiktok.com/@buzz.insolite/video/2"),
                 "p2": self.etat(channel=BZ, externalLink="https://tiktok.com/@buzz.insolite/video/3", dueAt="2026-11-24T21:30:00Z"),
                 "p3": self.etat()}
        alertes, ratt = verif_envois.verifier(hist, etats.get, "petitsdramas", MAINT)
        self.assertEqual(ratt, ["a.mp4"])                                   # prévue il y a 3 h 30 : repart tout de suite
        self.assertIsNone(hist[0]["publie"]); self.assertIsNone(hist[1]["publie"])   # redeviennent « à publier »
        self.assertNotIn("buffer_post", hist[0]); self.assertIn("mauvais compte", hist[0]["erreur"])
        self.assertEqual(hist[2]["envoi_verifie"], "ok"); self.assertTrue(hist[2]["lien_tiktok"].endswith("/1"))
        self.assertEqual(len(alertes), 2)
        hist[0].update(publie=True, buffer_post="p4")                       # le rattrapage rate aussi -> mis de côté
        alertes, ratt = verif_envois.verifier(hist, {"p4": self.etat(status="error", error="refus", externalLink="")}.get, "petitsdramas", MAINT)
        self.assertIs(hist[0]["publie"], False); self.assertEqual(ratt, [])
        self.assertEqual(verif_envois.verifier(hist, etats.get, "petitsdramas", MAINT), ([], []))   # rien revu deux fois

    def test_numero_garde_dans_l_historique(self):
        import json, tempfile
        d = tempfile.mkdtemp(); h = os.path.join(d, "h.json"); st = os.path.join(d, "s.json")
        json.dump([{"fichier": "a.mp4", "publie": None}], open(h, "w"))
        anc = (publier.HIST, publier.STATUT); publier.HIST, publier.STATUT = h, st
        try:
            publier.ENVOIS[:] = ["p9"]; publier.marquer("a.mp4", True, None, "texte")
            self.assertEqual(json.load(open(h))[0]["buffer_post"], "p9")
        finally: publier.HIST, publier.STATUT = anc; publier.ENVOIS[:] = []


if __name__ == "__main__":
    unittest.main()
