"""Audit des 10 vidéos du 23 novembre 2026 (demande de l'auteur : dialogues mélangés, caméras et scènes qui ne vont pas, erreurs
signalées mais jamais réparées)."""
import json, os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
from commun import *  # noqa: F401,F403,E402 (réglages des tests : mémoire des modèles Gemini dans un dossier temporaire…)


def _sk(reps, **doublage):
    return {"repliques": [dict(r) for r in reps], "doublage": dict({"duree": 30}, **doublage), "studio": {"personnages": {}}}


class TestAudit23Novembre(unittest.TestCase):
    def test_filles_jouees_par_un_homme(self):
        """« comment les meufs organisent leurs plans » : un homme joue deux filles ; Gemini voit un homme, les mots disent « fille »."""
        import studio
        reps = [{"p": "presentateur", "t": "Tu sors ce soir ?"}, {"p": "invite", "t": "Je pensais mettre ma robe noire avec les talons."},
                {"p": "presentateur", "t": "Moi à 19h j'ai rendez-vous pour faire mes cils."}, {"p": "invite", "t": "Je me fais épiler à 17h."}]
        sk = _sk(reps, meme_interprete=True, legende_ecran="Pov: comment les meufs organisent leurs plans")
        sk["studio"]["personnages"] = {"presentateur": {"genre_vu": "h"}, "invite": {"genre_vu": "h"}}
        sk["_voix_timbre_genre"] = {"presentateur": "h", "invite": "h"}; sk["_voix_ina"] = {"presentateur": "h", "invite": "h"}
        self.assertTrue(studio.un_acteur(sk))
        for r in ("presentateur", "invite"):
            self.assertEqual(studio.genre_voix(sk, r, sk["studio"]["personnages"][r]), "f", r)
        sk2 = _sk([{"p": "presentateur", "t": "Salut frérot"}, {"p": "invite", "t": "Ça va ?"}])   # rien de net : rien ne change
        sk2["studio"]["personnages"] = {"presentateur": {"genre_vu": "h"}, "invite": {"genre_vu": "h"}}
        self.assertEqual(studio.genre_voix(sk2, "invite", {"genre_vu": "h"}), "h")

    def test_image_qui_n_alterne_pas_ne_juge_pas(self):
        """On ne voit qu'une personne à la fois pendant de longs moments : l'image dit qui est là, pas qui parle."""
        import verif_finale as V
        reps = [{"p": "presentateur" if k % 2 == 0 else "invite", "t": "x", "_deb": 2.0 * k, "_fin": 2.0 * k + 1.5} for k in range(12)]
        vue = [[2.0 * k, 2.0 * k + 1.5, 0 if k < 6 else 1, 1.0] for k in range(12)]
        sk = _sk(reps, vue=vue)
        self.assertFalse(V.vue_fiable(sk))
        self.assertEqual(V.attribution_image(sk), [])

    def test_image_decide_quand_un_acteur(self):
        import verif_finale as V
        roles = ["invite", "presentateur", "invite", "invite", "presentateur", "invite", "presentateur", "presentateur", "invite", "presentateur"]
        vrai = [0, 1, 0, 1, 1, 0, 1, 0, 0, 1]                              # 0 = invité, 1 = présentateur (d'après l'image)
        reps = [{"p": r, "t": "x", "_deb": 2.0 * k, "_fin": 2.0 * k + 1.5} for k, r in enumerate(roles)]
        vue = [[2.0 * k, 2.0 * k + 1.5, c, 1.0] for k, c in enumerate(vrai)]
        sk = _sk(reps, vue=vue, meme_interprete=True)
        self.assertTrue(V.vue_fiable(sk))
        out = V.attribuer_par_image(sk, journal=lambda *_: None)
        self.assertEqual([r["p"] for r in sk["repliques"]], ["invite" if c == 0 else "presentateur" for c in vrai])
        self.assertEqual(sorted(out), [3, 7])
        sk2 = _sk([dict(r, p=roles[k]) for k, r in enumerate(reps)], vue=vue)   # voix bien différentes : l'image ne décide pas
        self.assertEqual(V.attribuer_par_image(sk2, journal=lambda *_: None), {})

    def test_appel_chacun_dans_son_decor(self):
        """Répliques changées de personnage après le découpage : les deux apparaissaient dans chaque moitié de l'écran."""
        import studio
        sk = {"_separes": True, "repliques": [{"p": "a"}, {"p": "b"}, {"p": "a"}, {"p": "b"}, {"p": "a"}, {"p": "narrateur"}],
              "decoupage": [{"scene": "1", "repliques": [0, 1, 2]}, {"scene": "2", "repliques": [3, 4, 5]}]}
        studio.resynchroniser_lieux(sk)
        sc = {i: k for k, d in enumerate(sk["decoupage"]) for i in d["repliques"]}
        self.assertEqual(len({sc[0], sc[2], sc[4]}), 1); self.assertEqual(sc[1], sc[3]); self.assertNotEqual(sc[0], sc[1])

    def test_decor_du_bon_lieu(self):
        """Fiche « bureau » mais lieu exact « chambre avec un lit défait » : une chambre était peinte."""
        import fiche_tournage as FT
        F = {"lieu": "bureau", "lieu_precis": "small cluttered bedroom with a messy bed", "details": ["pillow with sweat stains", "crumpled tissues on the floor"]}
        d = FT.decor_compose(F)
        self.assertNotIn("bedroom", d); self.assertNotIn("pillow", d); self.assertIn("tissues", d)
        sk = _sk([{"p": "a", "t": "atchoum"}], legende_ecran="Pov: t'es au bureau et GTA6 sort demain")
        self.assertEqual(FT.lieu_ecrit(sk), "bureau")
        self.assertIsNone(FT.lieu_ecrit(_sk([{"p": "a", "t": "x"}], legende_ecran="une amitié solide")))

    def test_fidelite_ne_change_jamais_le_genre(self):
        import fiche_tournage as FT
        sk = {"_fiche": {"personnages": {"presentateur": {"genre": "h"}}, "repliques": {}}, "repliques": [{"p": "presentateur", "t": "x"}]}
        pts = [{"correction": [{"champ": "personnages.presentateur.genre", "valeur": "f"}]}]
        self.assertEqual(FT.corriger_depuis_points(sk, pts), [])
        self.assertEqual(sk["_fiche"]["personnages"]["presentateur"]["genre"], "h")

    def test_compte_rendu_ne_change_pas_le_genre(self):
        import remarque
        sk = {"repliques": [{"p": "presentateur", "t": "Salut"}], "studio": {}}
        with mock.patch.object(remarque, "interpreter", lambda s, t: ({}, [{"type": "casting", "role": "presentateur", "genre": "f"}])), \
             mock.patch("qualite.corriger", lambda s, c: [f"casting {x}" for x in c]):
            self.assertEqual(remarque.appliquer(sk, "dessiné en femme", memoriser=False), [])

    def test_barriere_de_qualite(self):
        import deuxieme_chance as DC
        e = {"fichier": "v.mp4", "a_verifier": [{"poste": "attribution", "quoi": "l'image montre l'autre parler", "grave": True},
                                                 {"poste": "contrôle IA", "quoi": "trop neutre", "grave": True}]}
        out = DC.recaler(e, "https://www.tiktok.com/@x/video/1", 0)
        self.assertTrue(e["essai"]); self.assertEqual(len(e["recalee"]), 1)
        self.assertEqual(out.splitlines(), ["1", "https://www.tiktok.com/@x/video/1"])
        e2 = dict(e, essai=None, recalee=None)
        self.assertEqual(DC.recaler(e2, "u", 2), ""); self.assertTrue(e2["essai"])   # 2 remplaçantes déjà : plus de nouvelle tentative
        e3 = {"fichier": "w.mp4", "manuel": True, "a_verifier": e["a_verifier"]}
        self.assertEqual(DC.recaler(e3, "u", 0), ""); self.assertFalse(e3.get("essai"))   # lien collé par l'auteur : jamais recalé
        self.assertEqual(DC.barriere({"a_verifier": [{"poste": "contrôle IA", "quoi": "x"}]}), [])
        with mock.patch.dict(os.environ, {"BARRIERE": "0"}): self.assertEqual(DC.barriere(e2), [])
        with open(os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "emission.yml"), encoding="utf-8") as f_: src = f_.read()
        self.assertIn("sortie/.remplacante", src); self.assertIn("RECALE: ${{ inputs.recale }}", src)

    def test_dialogue_une_personne_qui_se_repond(self):
        import verif_finale as V
        t = ["Ouais, qu'est-ce que tu veux ?", "Pourquoi tu m'appelles ?", "Tu fais quoi ?", "Pourquoi tu veux savoir ?",
             "Bah, je te demande comme ça.", "Pourquoi ?", "Ouais, comme ça."]
        reps = [{"p": "presentateur" if k == 0 else "invite", "t": x, "_deb": k, "_fin": k + 0.8} for k, x in enumerate(t)]
        reps.append({"p": "presentateur", "t": "Ok.", "_deb": 9, "_fin": 9.5})
        sk = _sk(reps, meme_interprete=True)
        p = V.dialogue_logique(sk)
        self.assertEqual(len(p), 1); self.assertEqual(p[0]["poste"], "dialogue")
        self.assertEqual(V.dialogue_logique(_sk(reps)), [])                # voix bien distinctes : le son décide

    def test_gemini_patient(self):
        """503 « surchargé » sur tous les modèles : on attend puis on refait un tour au lieu d'abandonner."""
        import video_ia, reseau, time
        n = {"k": 0}
        def faux(req, timeout=0, essais=0):
            n["k"] += 1
            if n["k"] <= 2: raise RuntimeError("HTTP Error 503: Service Unavailable")
            return json.dumps({"candidates": [{"content": {"parts": [{"text": '{"lieu": "bureau"}'}]}}]}).encode()
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "x"}), mock.patch.object(reseau, "ouvrir", faux), \
             mock.patch.object(reseau, "gemini_disponibles", lambda v: ("m1", "m2")), mock.patch.object(time, "sleep", lambda s: None):
            r = video_ia.generer({"contents": []}, valide=lambda r: bool(r.get("lieu")))
        self.assertEqual(r["lieu"], "bureau"); self.assertEqual(n["k"], 3)
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "x"}), mock.patch.object(reseau, "gemini_disponibles", lambda v: ("m1",)), \
             mock.patch.object(reseau, "ouvrir", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("HTTP Error 404: Not Found"))), \
             mock.patch.object(time, "sleep", lambda s: self.fail("pas d'attente sur une erreur définitive")):
            self.assertIsNone(video_ia.generer({"contents": []}))
        reseau.GEMINI_MORTS.discard("m1")

    def test_texte_pose_sur_la_video(self):
        import ocr
        lignes = [{"deb": 0, "fin": 29, "t": "Pov: t'es au bureau"}, {"deb": 3, "fin": 4, "t": "QUOI"}]
        self.assertEqual(ocr.legende(lignes, 30), "Pov: t'es au bureau")


if __name__ == "__main__":
    unittest.main()
