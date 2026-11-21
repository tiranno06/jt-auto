"""Préparation commune à tous les fichiers de tests (sans réseau, sans clé API, sans GPU) : chemins, réglages, modules,
données d'essai (SKETCH, article, FauxClaude). Lancer : python -m unittest discover -s tests -v"""
import io, json, os, sys, tempfile, types, unittest
from unittest import mock
import numpy as np

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, "..", "moteur"))
os.environ.setdefault("LONGUEUR", "pro")
for _k in ("ORTHOGRAPHE", "PERSONNES_VUES", "TRANSNET", "RHUBARB", "INA_GENRE", "EMOTION2VEC", "WESPEAKER", "BEAUTE", "VAD"):
    os.environ.setdefault(_k, "0")                 # outils libres du 11 novembre : ni réseau ni gros modèle pendant les tests
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


import decors as _decors  # noqa: E402
_decors.UTILISES = os.path.join(tempfile.mkdtemp(), "utilises.tsv")   # les tests ne notent pas de décors « montrés » dans le dépôt
