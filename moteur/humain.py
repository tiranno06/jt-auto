"""Personnages humains ADULTES, dans le style de nos anciens personnages, différents à chaque vidéo (casting libre).

Chaque personnage est une FICHE (creer) : genre, âge, corpulence, taille, couleur de peau, forme du visage, yeux (couleur, taille),
nez, lèvres, sourcils, coiffure et couleur des cheveux (grisonnants avec l'âge), barbe ou moustache, lunettes, rides.
Le dessin reprend le CORPS de nos marionnettes en version adulte (marionnette.dessiner avec p["adulte"]) : même tête ronde
au trait noir, même buste en forme d'œuf, mêmes bras et jambes en tubes, mêmes yeux, sourcils, bouche synchronisée, coiffures,
mains et effets ; mais un corps d'adulte (plus grand, jambes et bras longs, cou, tête un peu moins grosse), la coiffure, la
couleur de cheveux, la barbe, les lunettes et la tenue de chaque personnage du casting. Peau : couleur humaine (réglage PEAU)
ou blanche comme nos bonshommes. Mêmes commandes de pose : toute la mise en scène du studio s'applique.
"""
import math
import numpy as np, cv2

import marionnette as M

AA = cv2.LINE_AA
PEAUX = [(255, 226, 200), (246, 205, 172), (234, 186, 146), (214, 160, 118), (176, 118, 82), (130, 86, 58), (96, 64, 46)]
CHEVEUX = [(30, 24, 22), (62, 42, 30), (104, 70, 44), (150, 100, 58), (196, 150, 90), (228, 196, 130), (170, 70, 40)]
IRIS = [(80, 50, 30), (110, 75, 45), (60, 110, 150), (80, 130, 90), (120, 120, 110)]
COIFFURES_H = ("court", "raie", "rase", "boucles", "chauve", "banane", "herisse", "afro", "degarni", "court_texture")
COIFFURES_F = ("long", "carre", "queue", "chignon", "boucles", "mi_long", "ondule", "frange", "afro", "tresses")
P_H = [0.16, 0.16, 0.1, 0.07, 0.06, 0.11, 0.07, 0.06, 0.1, 0.11]
P_F = [0.15, 0.11, 0.1, 0.1, 0.07, 0.05, 0.17, 0.13, 0.06, 0.06]
# coiffures cohérentes avec le genre (donné par la voix) : une coiffure imposée qui ne va pas est remplacée par la plus proche
POUR_H = {"long": "raie", "carre": "raie", "mi_long": "raie", "queue": "court_texture", "chignon": "court_texture", "ondule": "banane",
          "frange": "raie", "tresses": "court_texture"}
POUR_F = {"court": "carre", "raie": "frange", "rase": "carre", "banane": "frange", "herisse": "ondule", "degarni": "chignon",
          "chauve": "chignon", "court_texture": "carre", "meches": "carre", "nuque": "carre", "couronne": "chignon"}

COURTS_JEUNE_H = ("court", "court_texture", "herisse")  # garçon ado : coiffures courtes de son âge

def _hex(c): return tuple(int(v) for v in c)
def _melange(a, b, k): return tuple(int(x + (y - x) * k) for x, y in zip(a, b))
def _fonce(c, k=0.7): return tuple(int(v * k) for v in c)

# ------------------------------------------------------------------ casting
def creer(graine, genre=None, age=None, cheveux=None, c_cheveux=None, corpulence=None, lunettes=None, barbe=None, peau=None):
    """Fiche d'un personnage adulte (tirée au hasard avec la graine, en respectant les indices donnés : voix, image, texte)."""
    rng = np.random.default_rng(graine)
    g = genre if genre in ("h", "f") else ("h" if rng.random() < 0.5 else "f")
    a = int(age) if age else int(rng.choice([24, 28, 32, 36, 42, 48, 55, 63, 70], p=[0.13, 0.15, 0.15, 0.14, 0.13, 0.11, 0.09, 0.06, 0.04]))
    style = cheveux or (rng.choice(COIFFURES_H, p=P_H) if g == "h" else rng.choice(COIFFURES_F, p=P_F))
    if a > 55 and g == "h" and not cheveux and rng.random() < 0.4: style = "chauve"
    style = (POUR_H if g == "h" else POUR_F).get(str(style), style)          # jamais de coiffure qui brouille le genre
    cc = _hex(c_cheveux) if c_cheveux else CHEVEUX[int(rng.integers(len(CHEVEUX)))]
    if a >= 50 and not c_cheveux: cc = _melange(cc, (190, 190, 192), min(1.0, (a - 45) / 25))       # grisonnant
    jeune = a < 18                                                         # ado ou enfant : plus petit, cheveux courts, jamais de barbe
    if jeune:
        if g == "h" and style not in COURTS_JEUNE_H: style = COURTS_JEUNE_H[int(rng.integers(len(COURTS_JEUNE_H)))]
        barbe, corpulence = "", min(float(corpulence if corpulence is not None else rng.beta(2, 3)), 0.45)
    taille_age = 1.0 if not jeune else (0.8 if a >= 14 else 0.7 if a >= 10 else 0.6)
    return dict(genre=g, age=a, corpulence=float(corpulence if corpulence is not None else rng.beta(2, 3)),
                taille=float(rng.uniform(0.94, 1.06) * (1.04 if g == "h" else 0.97) * taille_age),
                peau=_hex(peau) if peau else PEAUX[int(rng.integers(len(PEAUX)))], visage=str(rng.choice(["ovale", "rond", "carre", "long"])),
                iris=IRIS[int(rng.integers(len(IRIS)))], yeux=float(rng.uniform(0.9, 1.12)), nez=str(rng.choice(["droit", "rond", "fort", "fin"])),
                levres=float(rng.uniform(0.8, 1.25) * (1.12 if g == "f" else 1.0)), sourcils=float(rng.uniform(0.85, 1.3) * (1.15 if g == "h" else 0.9)),
                cheveux=str(style), c_cheveux=cc,
                barbe="" if g == "f" else barbe if barbe is not None else (str(rng.choice(["", "", "", "trois_jours", "courte", "moustache", "bouc", "favoris", "barbe_pleine"])) if g == "h" and a >= 20 else ""),
                lunettes=lunettes if lunettes is not None else (str(rng.choice(["rondes", "rectangle"])) if rng.random() < (0.18 + 0.006 * max(0, a - 35)) else ""),
                maquillage=bool(g == "f" and not jeune and rng.random() < 0.6))

# ------------------------------------------------------------------ dessin (corps des marionnettes, version adulte)
import os
PEAU_HUMAINE = (os.environ.get("PEAU") or "blanche") == "humaine"     # peau blanche comme nos bonshommes (défaut) ou couleur humaine

COIFF_M = {"carre": "carre", "long": "long", "queue": "queue", "chignon": "chignon", "boucles": "boucles", "court": "court_texture",
           "rase": "rase", "mi_long": "carre", "meches": "meches", "nuque": "nuque", "raie": "raie"}
COIFF_M.update({c: c for c in M.GR.COIFFURES})

def _P(F):
    """Le personnage vu par marionnette.py : pas d'accessoire fixe, coiffure, nez et cils de la fiche."""
    st = F["cheveux"]; c = tuple(F["c_cheveux"])
    if st == "rase": c = _melange(c, F["peau"] if PEAU_HUMAINE else (250, 250, 250), 0.35)
    ch = (COIFF_M[st], c) if st in COIFF_M else (("couronne", c) if F["age"] > 45 else None)
    return dict(nom="", accessoire=None, couleur=(0, 0, 0), cheveux=ch, nez={"droit": "pointu", "rond": "rond", "fort": "rond", "fin": "petit"}[F["nez"]],
                cils=F["genre"] == "f", moustache=F.get("barbe") == "moustache")

def _pose(F, p):
    C = dict(p.get("costume") or {}); det = list(C.get("details") or ())
    if F.get("lunettes") and "lunettes_vue" not in det: det.append("lunettes_vue")
    if F["age"] < 18: det = [d for d in det if d not in M.GR.BARBES + ("moustache", "barbe")]   # ado : aucune barbe, même imposée
    b = {"courte": "barbe_courte", "trois_jours": "barbe"}.get(F.get("barbe"), F.get("barbe"))
    if b and b != "moustache" and b not in det: det.append(b)
    C.setdefault("c_barbe", tuple(F["c_cheveux"]))
    C["details"] = tuple(det); C.pop("cheveux", None); C.pop("c_cheveux", None)
    rouge = (200, 60, 80) if F.get("maquillage") or "rouge_levres" in det else None
    return dict(p, adulte=True, s=p["s"] * F["taille"], peau=tuple(F["peau"]) if PEAU_HUMAINE else None, costume=C, reflets=True,
                age=F["age"], yeux_k=F.get("yeux", 1.0), sourcil_ep=F.get("sourcils", 1.0), rouge=rouge, maquillage=F.get("maquillage"))

def dessiner(img, F, p):
    """Dessine le personnage de fiche F (version adulte de nos marionnettes) selon la pose p. Renvoie (tête, (rx, ry))."""
    return M.dessiner(img, _P(F), _pose(F, p))

def tete_y(s, taille=1.0):
    """Hauteur du centre de la tête pour des pieds à y=1500 (cadrages du moteur)."""
    return M.squelette(dict(M.pose_neutre(), y=1500, s=s * taille, adulte=True))["tete"][1]

def hauteur_tete(s, taille=1.0): return 2 * M.squelette(dict(M.pose_neutre(), y=1500, s=s * taille, adulte=True))["ry"]

def reperes(F, p):
    """Centre et rayons de la tête, positions des deux mains (pour poser objets et effets)."""
    K = M.squelette(_pose(F, p)); return K["tete"], (K["rx"], K["ry"]), [K["bras"][0][2], K["bras"][1][2]]
