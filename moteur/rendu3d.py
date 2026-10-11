"""Vraie 3D (réglage RENDU_3D, coupé par défaut) : les personnages adultes sont rendus par Blender puis posés sur nos décors.

1. le moteur cartoon fait un premier passage « à blanc » qui note, image par image, la pose de chaque personnage (bras, mains,
   bouche, yeux, sourcils, tête, épaules…) et sa place à l'écran ;
2. Blender (module bpy, Python 3.11 : variable BLENDER_PYTHON, installée par le workflow quand le réglage est activé) construit
   chaque personnage en 3D d'après sa fiche et sa tenue (blender_humain.py) et le rend image par image, sur fond transparent ;
   les poses identiques ne sont rendues qu'une fois ;
3. au vrai passage, chaque personnage 3D est mis à l'échelle et posé dans le décor à la place du dessin 2D ; les objets tenus
   et les effets comiques sont ajoutés par-dessus. Vue de dos (plan par-dessus l'épaule) : dessin 2D, flou de toute façon.
Si Blender manque ou échoue, la vidéo sort en 2D (rien n'est perdu).

Temps de calcul : environ 1 à 3 s par pose sur le processeur des serveurs GitHub ; une vidéo de 90 s peut prendre plus d'une heure."""
import json, os, subprocess, tempfile
import numpy as np, cv2

ICI = os.path.dirname(os.path.abspath(__file__))
LARGEUR, HAUTEUR = 780, 1100                                               # taille du rendu d'un personnage (pixels)
CADRE_H, PIEDS_BAS = 2.6, 0.1                                              # = blender_humain.CADRE_H, PIEDS_BAS (mètres)

def actif():
    return os.environ.get("RENDU_3D", "0") == "1" and bool(os.environ.get("BLENDER_PYTHON"))

def _cle(p):
    """Ce qui compte pour la pose 3D (pas la place à l'écran)."""
    garde = ("bras_g", "bras_d", "tilt", "bouche", "viseme", "forme", "yeux", "paupiere", "sourcils", "sourcils_h", "sourcil_leve",
             "epaules", "penche", "regard", "coins", "plisse", "pupille", "main_forme_g", "main_forme_d")
    out = {}
    for k in garde:
        v = p.get(k)
        if v is None: continue
        if isinstance(v, (tuple, list)): v = [round(float(x), 2) for x in v]
        elif isinstance(v, (bool, np.bool_)): v = bool(v)
        elif isinstance(v, (int, float, np.integer, np.floating)): v = round(float(v), 3)      # les nombres numpy aussi (sinon JSON en texte)
        out[k] = v
    return out

class Rendu:
    """Personnages rendus en 3D pour toute la vidéo : sprite(role, image) -> RGBA ou None."""
    def __init__(self, fiches, costumes, poses, echantillons=10, delai=7200):
        self.dossier = tempfile.mkdtemp(); self.ok = False; self.cache = {}
        roles = {r: {"fiche": fiches[r], "costume": costumes.get(r) or {}, "poses": [_cle(x) if x else None for x in poses[r]]} for r in poses if r in fiches}
        if not roles: return
        travail = os.path.join(self.dossier, "travail.json")
        json.dump({"sortie": self.dossier, "largeur": LARGEUR, "hauteur": HAUTEUR, "echantillons": echantillons, "roles": roles,
                   "gpu": os.environ.get("RENDU_3D_GPU") == "1"}, open(travail, "w"), default=lambda o: list(o) if isinstance(o, tuple) else str(o))
        try:
            r = subprocess.run([os.environ["BLENDER_PYTHON"], os.path.join(ICI, "blender_humain.py"), travail], capture_output=True, text=True, timeout=delai)
            for l in (r.stdout or "").splitlines():
                if l.startswith("3D :"): print("  " + l, flush=True)
            self.ok = r.returncode == 0
            if not self.ok: print(f"3D en échec : {(r.stderr or '')[-400:]}", flush=True)
        except Exception as e: print(f"3D impossible ({str(e)[:200]}) : rendu 2D", flush=True)

    def sprite(self, role, fi):
        f = os.path.join(self.dossier, f"{role}_{fi:05d}.png")
        if f in self.cache: return self.cache[f]
        im = cv2.imread(f, cv2.IMREAD_UNCHANGED) if os.path.exists(f) else None
        if im is not None: im = cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)
        if len(self.cache) > 64: self.cache.clear()
        self.cache[f] = im; return im

def poser(img, sprite, p, taille):
    """Pose le personnage 3D dans l'image : pieds en (p["x"], p["y"]), hauteur d'adulte à l'échelle p["s"] (comme le dessin 2D)."""
    k = 6.6 * 122 * p["s"] * taille / (1.75 * taille * HAUTEUR / CADRE_H)
    w, h = max(2, int(LARGEUR * k)), max(2, int(HAUTEUR * k))
    sp = cv2.resize(sprite, (w, h), interpolation=cv2.INTER_LINEAR if k > 1 else cv2.INTER_AREA)
    pieds_y = HAUTEUR * (1 - PIEDS_BAS / CADRE_H) * k
    x0, y0 = int(p["x"] - w / 2), int(p["y"] - pieds_y)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(img.shape[1], x0 + w), min(img.shape[0], y0 + h)
    if xb <= xa or yb <= ya: return
    s = sp[ya - y0:yb - y0, xa - x0:xb - x0].astype(np.float32); a = s[..., 3:4] / 255
    img[ya:yb, xa:xb] = (img[ya:yb, xa:xb] * (1 - a) + s[..., :3] * a).astype(np.uint8)
