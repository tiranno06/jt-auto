"""Décors dessinés par le robot (gratuits, sans IA) : un lieu complet, dans le même style que les personnages (trait noir, aplats).

Chaque lieu est composé comme un vrai décor de dessin animé :
- un fond : mur (couleur et papier peint de l'épisode), sol en perspective (parquet, carrelage, moquette, sol de salle de sport),
  plinthe, fenêtre dont le ciel suit l'heure de l'épisode (matin, jour, soir, nuit : nuages, soleil, lune, étoiles, ville au loin),
  meubles et objets propres au lieu, tableaux, étagères garnies, plantes, horloge, lampes allumées le soir ;
- des « gags écrits » dans le décor (affiche, tableau blanc, enseigne, post-it…), dessinés en vraie police (lisibles) ;
- un premier plan séparé (comptoir, bureau, caisse) posé DEVANT les personnages : la caméra le fait glisser plus vite que le fond,
  ce qui donne du relief (parallaxe) ;
- la lumière : tache de soleil au sol sous la fenêtre, halo des lampes, ombre au pied des murs.

dessiner(lieu, bible) -> {"fond": RGB HxW, "avant": RGBA HxW ou None, "fenetre": (x0, y0, x1, y1) ou None, "lampes": [(x, y)],
                          "vapeur": [(x, y)], "neons": [(x0, y0, x1, y1)], "ecrans": [(x0, y0, x1, y1)]}"""
import math, os, re
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

import decor_details as DX

W, H = 1080, 1920
SOL = 1210                                                                 # ligne mur / sol (les pieds des personnages sont à 1500)
TRAIT = (26, 22, 30)
AA = cv2.LINE_AA
POLICE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "polices", "Poppins-Bold.ttf")
LIEUX = ("salon", "cuisine", "bureau", "cabinet_medical", "bar", "chambre", "salle_sport", "magasin", "classe", "rue", "restaurant",
         "administration", "hall", "caverne", "palais")

# ------------------------------------------------------------------ outils de dessin
def _c(c): return tuple(int(max(0, min(255, v))) for v in c)
def fonce(c, k=0.78): return _c(v * k for v in c)
def clair(c, k=0.35): return _c(v + (255 - v) * k for v in c)

def boite(img, x0, y0, x1, y1, couleur, ep=6, r=0):
    """Rectangle (coins arrondis si r) rempli, contour noir."""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    for col, d in ((TRAIT, 0), (couleur, ep)):
        a, b, c, e = x0 + d, y0 + d, x1 - d, y1 - d
        if c <= a or e <= b: continue
        rr = max(0, r - d)
        if rr:
            cv2.rectangle(img, (a + rr, b), (c - rr, e), col, -1, AA); cv2.rectangle(img, (a, b + rr), (c, e - rr), col, -1, AA)
            for px, py in ((a + rr, b + rr), (c - rr, b + rr), (a + rr, e - rr), (c - rr, e - rr)): cv2.circle(img, (px, py), rr, col, -1, AA)
        else: cv2.rectangle(img, (a, b), (c, e), col, -1, AA)

def poly(img, pts, couleur, ep=6):
    p = np.array(pts, np.int32).reshape(-1, 1, 2)
    cv2.fillPoly(img, [p], couleur, AA)
    if ep: cv2.polylines(img, [p], True, TRAIT, ep, AA)

def rond(img, c, r, couleur, ep=6):
    cv2.circle(img, (int(c[0]), int(c[1])), int(r), TRAIT, -1, AA)
    if r - ep > 0: cv2.circle(img, (int(c[0]), int(c[1])), int(r - ep), couleur, -1, AA)

def ligne(img, a, b, couleur, ep):
    cv2.line(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), couleur, max(1, int(ep)), AA)

_POL = {}
def texte(img, txt, x0, y0, x1, y1, couleur=TRAIT, taille=None, centre=True, contour=0, c_contour=(255, 255, 255)):
    """Texte lisible dans un cadre (retour à la ligne automatique, taille ajustée au cadre)."""
    txt = re.sub(r"\s+", " ", str(txt or "")).strip()
    if not txt: return
    lw, lh = int(x1 - x0), int(y1 - y0)
    for t_ in range(int(taille or 64), 13, -2):
        f = _POL.get(t_) or _POL.setdefault(t_, ImageFont.truetype(POLICE, t_))
        d0 = ImageDraw.Draw(Image.new("RGB", (1, 1))); mots, lignes, cur = txt.split(), [], ""
        for m in mots:
            if d0.textlength((cur + " " + m).strip(), font=f) > lw: lignes.append(cur); cur = m
            else: cur = (cur + " " + m).strip()
        lignes.append(cur); hl = int(t_ * 1.18)
        if hl * len(lignes) <= lh and all(d0.textlength(l, font=f) <= lw for l in lignes): break
    pil = Image.fromarray(img[int(y0):int(y1), int(x0):int(x1)]); d = ImageDraw.Draw(pil)
    yy = (lh - hl * len(lignes)) / 2
    for k, l in enumerate(lignes):
        w = d.textlength(l, font=f); xx = (lw - w) / 2 if centre else 0
        d.text((xx, yy + k * hl), l, font=f, fill=couleur, stroke_width=contour, stroke_fill=c_contour)
    img[int(y0):int(y1), int(x0):int(x1)] = np.array(pil)

# ------------------------------------------------------------------ ciel, mur, sol
CIELS = {"matin": ((255, 190, 150), (180, 210, 245)), "jour": ((120, 185, 245), (205, 232, 252)),
         "soir": ((90, 60, 140), (250, 150, 90)), "nuit": ((14, 20, 52), (44, 56, 110))}

def ciel(img, x0, y0, x1, y1, moment, rng, ville=True):
    haut, bas = CIELS.get(moment, CIELS["jour"]); h = max(1, y1 - y0)
    g = np.linspace(0, 1, h)[:, None, None]
    img[y0:y1, x0:x1] = (np.array(haut) * (1 - g) + np.array(bas) * g).astype(np.uint8)
    zone = img[y0:y1, x0:x1]
    if moment == "nuit":
        for _ in range(int((x1 - x0) * (y1 - y0) / 6000)):
            cv2.circle(zone, (int(rng.uniform(0, x1 - x0)), int(rng.uniform(0, h * 0.7))), int(rng.choice([1, 1, 2])), (250, 250, 220), -1, AA)
        cv2.circle(zone, (int((x1 - x0) * 0.72), int(h * 0.22)), 34, (250, 245, 210), -1, AA); cv2.circle(zone, (int((x1 - x0) * 0.72) + 14, int(h * 0.22) - 8), 30, haut, -1, AA)
    elif moment in ("jour", "matin"):
        cv2.circle(zone, (int((x1 - x0) * 0.25), int(h * (0.22 if moment == "jour" else 0.55))), 40, (255, 240, 170), -1, AA)
        for _ in range(3):                                                 # nuages
            cx, cy, r = rng.uniform(0, x1 - x0), rng.uniform(h * 0.1, h * 0.5), rng.uniform(26, 44)
            for dx in (-1.1, 0, 1.1, 0.5): cv2.circle(zone, (int(cx + dx * r), int(cy - (r * 0.5 if dx == 0 else 0))), int(r), (252, 252, 255), -1, AA)
    else:
        cv2.circle(zone, (int((x1 - x0) * 0.4), int(h * 0.85)), 60, (255, 200, 120), -1, AA)
    if ville:                                                              # silhouette de la ville au loin, fenêtres allumées le soir
        c_v = fonce(bas, 0.62) if moment != "nuit" else (30, 34, 70); x = 0
        while x < x1 - x0:
            bw, bh = int(rng.uniform(40, 90)), int(rng.uniform(h * 0.18, h * 0.5))
            cv2.rectangle(zone, (x, h - bh), (x + bw, h), c_v, -1)
            if moment in ("soir", "nuit"):
                for yy in range(h - bh + 10, h - 8, 18):
                    for xx in range(x + 8, x + bw - 8, 16):
                        if rng.random() < 0.45: cv2.rectangle(zone, (xx, yy), (xx + 6, yy + 8), (255, 220, 120), -1)
            x += bw + int(rng.uniform(2, 10))

def fenetre(img, x0, y0, x1, y1, moment, rng, cadre=(250, 250, 248), rideaux=None, ville=True):
    boite(img, x0 - 14, y0 - 14, x1 + 14, y1 + 14, cadre, 7)
    ciel(img, x0, y0, x1, y1, moment, rng, ville)
    cv2.rectangle(img, (x0, y0), (x1, y1), TRAIT, 6, AA)
    xm, ym = (x0 + x1) // 2, (y0 + y1) // 2
    cv2.line(img, (xm, y0), (xm, y1), cadre, 14, AA); cv2.line(img, (x0, ym), (x1, ym), cadre, 14, AA)
    cv2.line(img, (xm, y0), (xm, y1), TRAIT, 3, AA); cv2.line(img, (x0, ym), (x1, ym), TRAIT, 3, AA)
    for k in range(2):                                                     # reflets sur la vitre
        a = (x0 + 20 + k * 40, y0 + 120); b = (x0 + 80 + k * 40, y0 + 40)
        cv2.line(img, a, b, (255, 255, 255), 6, AA)
    boite(img, x0 - 30, y1 + 10, x1 + 30, y1 + 34, cadre, 6)                # rebord
    if rideaux:
        for sg, xb in ((-1, x0), (1, x1)):
            pts = [(xb - sg * 10, y0 - 40), (xb + sg * 70, y0 - 40), (xb + sg * 50, y1 + 60), (xb - sg * 20, y1 + 80)]
            poly(img, pts, rideaux, 5)
            for k in range(3): ligne(img, (xb + sg * (8 + k * 18), y0 - 30), (xb + sg * (4 + k * 14), y1 + 60), fonce(rideaux, 0.8), 4)
        boite(img, x0 - 90, y0 - 56, x1 + 90, y0 - 40, (150, 110, 70), 4)

def mur(img, couleur, motif, rng, bas=SOL):
    img[:bas] = couleur
    c2 = fonce(couleur, 0.93)
    if motif == "rayures":
        for x in range(0, W, 90): cv2.rectangle(img, (x, 0), (x + 40, bas), c2, -1)
    elif motif == "losanges":
        for y in range(0, bas, 120):
            for x in range(-60 if (y // 120) % 2 else 0, W, 120): poly(img, [(x + 60, y), (x + 120, y + 60), (x + 60, y + 120), (x, y + 60)], c2, 0)
    elif motif == "fleurs":
        for y in range(40, bas, 140):
            for x in range(40 + (70 if (y // 140) % 2 else 0), W, 140):
                for a in range(5): cv2.circle(img, (int(x + 12 * math.cos(a * 1.26)), int(y + 12 * math.sin(a * 1.26))), 8, c2, -1, AA)
    elif motif == "briques":
        for k, y in enumerate(range(0, bas, 56)):
            cv2.line(img, (0, y), (W, y), fonce(couleur, 0.82), 4)
            for x in range(-60 if k % 2 else 0, W, 120): cv2.line(img, (x, y), (x, y + 56), fonce(couleur, 0.82), 4)
    elif motif == "lambris":                                               # soubassement en bois
        cv2.rectangle(img, (0, bas - 330), (W, bas), fonce(couleur, 0.88), -1); cv2.line(img, (0, bas - 330), (W, bas - 330), TRAIT, 6, AA)
        for x in range(60, W, 150): cv2.rectangle(img, (x, bas - 290), (x + 110, bas - 40), fonce(couleur, 0.8), 4, AA)
    grain = rng.normal(0, 3.2, (bas, W, 1)).astype(np.float32)               # grain du papier
    img[:bas] = np.clip(img[:bas].astype(np.float32) + grain, 0, 255).astype(np.uint8)

def sol(img, couleur, motif, haut=SOL):
    img[haut:] = couleur; c2 = fonce(couleur, 0.85); fuite = (W / 2, haut - 900)
    if motif == "parquet":
        for k in range(-14, 15):                                           # lames qui fuient vers le point de fuite
            x_b = W / 2 + k * 150; x_h = fuite[0] + (x_b - fuite[0]) * (900 / (900 + H - haut))
            cv2.line(img, (int(x_h), haut), (int(x_b), H), c2, 4, AA)
        for j, y in enumerate((haut + 70, haut + 170, haut + 300, haut + 470, haut + 690)):
            for k in range(-8, 9):
                x = W / 2 + (k + 0.5 * (j % 2)) * 150 * (y - fuite[1]) / (H - fuite[1]) * 1.6
                cv2.line(img, (int(x), y - 20), (int(x), y + 20), c2, 3, AA)
    elif motif in ("carrelage", "damier"):
        ys = [haut]; y = haut; d = 60
        while y < H: y += d; d *= 1.32; ys.append(int(y))
        for k in range(-14, 15):
            x_b = W / 2 + k * 160; x_h = fuite[0] + (x_b - fuite[0]) * (900 / (900 + H - haut))
            cv2.line(img, (int(x_h), haut), (int(x_b), H), c2, 3, AA)
        for y in ys: cv2.line(img, (0, y), (W, y), c2, 3, AA)
        if motif == "damier":
            for i in range(len(ys) - 1):
                for k in range(-14, 14):
                    if (i + k) % 2: continue
                    def X(kk, yy): xb = W / 2 + kk * 160; return fuite[0] + (xb - fuite[0]) * (yy - fuite[1]) / (H - fuite[1])
                    poly(img, [(X(k, ys[i]), ys[i]), (X(k + 1, ys[i]), ys[i]), (X(k + 1, ys[i + 1]), ys[i + 1]), (X(k, ys[i + 1]), ys[i + 1])], c2, 0)
    elif motif == "moquette":
        rng = np.random.default_rng(5); n = rng.normal(0, 5, (H - haut, W, 1)).astype(np.float32)
        img[haut:] = np.clip(img[haut:].astype(np.float32) + n, 0, 255).astype(np.uint8)
    elif motif == "trottoir":
        cv2.rectangle(img, (0, haut + 260), (W, H), (70, 72, 80), -1)
        cv2.rectangle(img, (0, haut + 240), (W, haut + 262), (200, 200, 205), -1); cv2.line(img, (0, haut + 262), (W, haut + 262), TRAIT, 5)
        for x in range(0, W, 200): cv2.line(img, (x, haut), (x - 60, haut + 240), c2, 3, AA)
        for x in range(40, W, 260): cv2.rectangle(img, (x, haut + 520), (x + 140, haut + 540), (240, 240, 230), -1)
    g = np.clip((np.arange(H - haut, dtype=np.float32) / 160.0), 0, 1)[:, None, None]     # ombre au pied du mur
    img[haut:] = (img[haut:].astype(np.float32) * (0.82 + 0.18 * g)).astype(np.uint8)
    cv2.line(img, (0, haut), (W, haut), TRAIT, 6, AA)

def plinthe(img, couleur=(248, 248, 244)):
    boite(img, -10, SOL - 34, W + 10, SOL + 3, couleur, 5)

# ------------------------------------------------------------------ objets du décor
def cadre_tableau(img, x0, y0, x1, y1, rng, c_cadre=(170, 120, 70), sujet=None):
    boite(img, x0, y0, x1, y1, c_cadre, 6); m = 16; a, b, c, d = x0 + m, y0 + m, x1 - m, y1 - m
    sujet = sujet or rng.choice(["montagne", "abstrait", "portrait", "mer"])
    if sujet == "montagne":
        ciel(img, a, b, c, d, "jour", rng, False); poly(img, [(a, d), ((a + c) // 2 - 20, b + (d - b) // 3), (c, d)], (110, 140, 120), 0)
        poly(img, [((a + c) // 2 - 20, b + (d - b) // 3), ((a + c) // 2 - 45, b + (d - b) // 2), ((a + c) // 2 + 5, b + (d - b) // 2)], (250, 250, 250), 0)
    elif sujet == "mer":
        ciel(img, a, b, c, d, "soir", rng, False); cv2.rectangle(img, (a, (b + d) // 2 + 10), (c, d), (60, 110, 170), -1)
    elif sujet == "portrait":
        cv2.rectangle(img, (a, b), (c, d), (230, 215, 190), -1); cv2.circle(img, ((a + c) // 2, (b + d) // 2 - 10), max(8, (c - a) // 4), (250, 250, 248), -1, AA)
        cv2.circle(img, ((a + c) // 2, (b + d) // 2 - 10), max(8, (c - a) // 4), TRAIT, 3, AA); cv2.ellipse(img, ((a + c) // 2, d), ((c - a) // 3, (d - b) // 4), 0, 180, 360, (120, 80, 140), -1, AA)
    else:
        cv2.rectangle(img, (a, b), (c, d), (245, 240, 228), -1)
        for _ in range(4):
            col = tuple(int(v) for v in rng.choice([(230, 80, 70), (60, 120, 200), (250, 200, 60), (40, 40, 50)]))
            cv2.circle(img, (int(rng.uniform(a, c)), int(rng.uniform(b, d))), int(rng.uniform(10, (c - a) / 4)), col, -1, AA)
    cv2.rectangle(img, (a, b), (c, d), TRAIT, 3, AA)

def etagere(img, x0, y, x1, rng, livres=True, plante=True):
    boite(img, x0, y, x1, y + 22, (180, 130, 85), 5)
    x = x0 + 14
    while livres and x < x1 - 60:
        bw, bh = int(rng.uniform(16, 30)), int(rng.uniform(70, 110)); col = tuple(int(v) for v in rng.choice(
            [(200, 70, 70), (60, 110, 180), (240, 190, 70), (90, 160, 110), (150, 90, 160), (230, 130, 60), (70, 70, 80)]))
        if rng.random() < 0.12: poly(img, [(x, y), (x + bw, y), (x + bw + 26, y - bh + 6), (x + 26, y - bh)], col, 4); x += bw + 34; continue
        boite(img, x, y - bh, x + bw, y + 2, col, 4); ligne(img, (x + 5, y - bh + 16), (x + bw - 5, y - bh + 16), clair(col, 0.4), 3)
        x += bw + 2
        if rng.random() < 0.1: x += 30
    if plante: pot(img, x1 - 40, y, 0.7)

def pot(img, x, y, k=1.0, couleur=(210, 110, 80)):
    for a in (-60, -30, 0, 30, 60):                                        # feuilles
        r = math.radians(a - 90); fx, fy = x + math.cos(r) * 90 * k, y - 60 * k + math.sin(r) * 90 * k
        cv2.ellipse(img, (int((x + fx) / 2), int((y - 60 * k + fy) / 2)), (int(52 * k), int(18 * k)), a - 90 + 90 + 90, 0, 360, TRAIT, -1, AA)
        cv2.ellipse(img, (int((x + fx) / 2), int((y - 60 * k + fy) / 2)), (int(46 * k), int(12 * k)), a + 90, 0, 360, (90, 160, 90), -1, AA)
    poly(img, [(x - 36 * k, y - 66 * k), (x + 36 * k, y - 66 * k), (x + 26 * k, y), (x - 26 * k, y)], couleur, 5)

def horloge(img, x, y, r=56, heure=None):
    rond(img, (x, y), r, (252, 252, 248), 7)
    for k in range(12):
        a = k * math.pi / 6; ligne(img, (x + math.cos(a) * r * 0.72, y + math.sin(a) * r * 0.72), (x + math.cos(a) * r * 0.85, y + math.sin(a) * r * 0.85), TRAIT, 3)
    h_, m_ = heure or (10, 10)
    a = math.radians(h_ % 12 * 30 + m_ / 2 - 90); ligne(img, (x, y), (x + math.cos(a) * r * 0.45, y + math.sin(a) * r * 0.45), TRAIT, 7)
    a = math.radians(m_ * 6 - 90); ligne(img, (x, y), (x + math.cos(a) * r * 0.7, y + math.sin(a) * r * 0.7), TRAIT, 5)
    cv2.circle(img, (int(x), int(y)), 6, (210, 50, 50), -1, AA)

def lampe_pied(img, x, y_sol, allumee):
    ligne(img, (x, y_sol - 520), (x, y_sol - 10), TRAIT, 10); boite(img, x - 50, y_sol - 24, x + 50, y_sol, (90, 80, 70), 5)
    poly(img, [(x - 70, y_sol - 520), (x + 70, y_sol - 520), (x + 46, y_sol - 640), (x - 46, y_sol - 640)], (255, 236, 170) if allumee else (240, 225, 190), 6)
    return (x, y_sol - 560)

def suspension(img, x, y, allumee):
    ligne(img, (x, 0), (x, y), TRAIT, 5)
    cv2.ellipse(img, (x, y + 10), (70, 60), 0, 180, 360, TRAIT, -1, AA); cv2.ellipse(img, (x, y + 10), (63, 53), 0, 180, 360, (60, 70, 80), -1, AA)
    cv2.ellipse(img, (x, y + 10), (40, 16), 0, 0, 180, (255, 240, 180) if allumee else (220, 220, 210), -1, AA)
    return (x, y + 30)

def ecran(img, x0, y0, x1, y1, contenu="bleu", rng=None):
    boite(img, x0, y0, x1, y1, (40, 40, 48), 7, 8)
    a, b, c, d = x0 + 16, y0 + 16, x1 - 16, y1 - 16
    if contenu == "graphique":
        cv2.rectangle(img, (a, b), (c, d), (240, 246, 252), -1)
        pts = [(a + 10 + k * (c - a - 20) / 5, b + 20 + (d - b - 40) * v) for k, v in enumerate((0.1, 0.3, 0.2, 0.55, 0.7, 0.95))]
        cv2.polylines(img, [np.array(pts, np.int32)], False, (220, 60, 60), 6, AA)
    elif contenu == "code":
        cv2.rectangle(img, (a, b), (c, d), (30, 34, 44), -1)
        for k, yy in enumerate(range(b + 14, d - 8, 18)): cv2.line(img, (a + 12 + (k % 3) * 18, yy), (a + 40 + ((k * 37) % (c - a - 60)), yy), [(120, 200, 120), (200, 160, 90), (130, 170, 230)][k % 3], 6)
    else:
        g = np.linspace(0, 1, max(1, d - b))[:, None, None]; img[b:d, a:c] = (np.array((90, 150, 230)) * (1 - g) + np.array((160, 210, 250)) * g).astype(np.uint8)
    return (a, b, c, d)

def affiche(img, x0, y0, x1, y1, txt, fond_c=(250, 220, 90), c_txt=TRAIT, punaises=True, dessin=None):
    boite(img, x0, y0, x1, y1, fond_c, 6, 6)
    m = 22; haut_txt = y0 + m
    if dessin == "squelette":                                              # planche d'anatomie
        cx = (x0 + x1) // 2; cv2.circle(img, (cx, y0 + 70), 30, TRAIT, 5, AA)
        for k in range(5): cv2.ellipse(img, (cx, y0 + 140 + k * 22), (40 - k * 3, 8), 0, 0, 360, TRAIT, 4, AA)
        ligne(img, (cx, y0 + 100), (cx, y0 + 260), TRAIT, 5)
        for sg in (-1, 1): ligne(img, (cx, y0 + 125), (cx + sg * 60, y0 + 200), TRAIT, 5); ligne(img, (cx, y0 + 260), (cx + sg * 40, y0 + 330), TRAIT, 5)
        haut_txt = y0 + 340
    elif dessin == "montagne":
        cv2.rectangle(img, (x0 + m, y0 + m), (x1 - m, y0 + m + (y1 - y0) // 2), (130, 180, 230), -1)
        poly(img, [(x0 + m, y0 + m + (y1 - y0) // 2), ((x0 + x1) // 2, y0 + m + 30), (x1 - m, y0 + m + (y1 - y0) // 2)], (110, 130, 150), 0)
        haut_txt = y0 + m + (y1 - y0) // 2 + 8
    texte(img, txt, x0 + m, haut_txt, x1 - m, y1 - m, c_txt, 56)
    if punaises:
        for px in (x0 + 18, x1 - 18): cv2.circle(img, (px, y0 + 16), 9, (220, 50, 60), -1, AA)

def postit(img, x, y, txt, couleur=(255, 236, 110), angle=0):
    t = np.zeros((170, 170, 3), np.uint8); t[:] = couleur
    cv2.rectangle(t, (0, 0), (169, 26), fonce(couleur, 0.92), -1)
    texte(t, txt, 12, 30, 158, 160, (40, 50, 120), 30)
    M_ = cv2.getRotationMatrix2D((85, 85), angle, 1.0); t = cv2.warpAffine(t, M_, (170, 170), borderValue=(1, 2, 3))
    m = (np.abs(t.astype(int) - (1, 2, 3)).sum(2) > 6)[..., None]
    y0, x0 = int(y), int(x); zone = img[y0:y0 + 170, x0:x0 + 170]
    if zone.shape[:2] == (170, 170): img[y0:y0 + 170, x0:x0 + 170] = np.where(m, t, zone)

def neon(img, x0, y0, x1, y1, txt, couleur=(255, 90, 170)):
    boite(img, x0, y0, x1, y1, (34, 30, 44), 6, 18)
    calque = np.zeros_like(img); texte(calque, txt, x0 + 24, y0 + 18, x1 - 24, y1 - 18, couleur, 72)
    halo = cv2.GaussianBlur(calque, (0, 0), 14).astype(np.float32)
    img[:] = np.clip(img.astype(np.float32) + halo * 0.9, 0, 255).astype(np.uint8)
    m = calque.sum(2) > 30; img[m] = np.clip(np.array(couleur) * 0.5 + 255 * 0.5, 0, 255).astype(np.uint8)
    return (x0, y0, x1, y1)

def halo(img, c, r, couleur=(255, 220, 140), force=0.35):
    """Lumière d'une lampe : éclaircit l'image autour du point (dégradé)."""
    yy, xx = np.ogrid[:img.shape[0], :img.shape[1]]
    d = np.sqrt((xx - c[0]) ** 2 + (yy - c[1]) ** 2) / r; g = np.clip(1 - d, 0, 1) ** 2 * force
    img[:] = np.clip(img * (1 - g[..., None]) + np.array(couleur) * g[..., None] + img * g[..., None] * 0.15, 0, 255).astype(np.uint8)

def tache_soleil(img, fen, moment):
    """Lumière de la fenêtre projetée au sol (parallélogramme plus clair)."""
    if moment == "nuit" or not fen: return
    x0, y0, x1, y1 = fen; dec = 260 if (x0 + x1) / 2 < W / 2 else -260
    pts = np.array([(x0, SOL + 10), (x1, SOL + 10), (x1 + dec, H - 80), (x0 + dec, H - 80)], np.int32)
    m = np.zeros(img.shape[:2], np.uint8); cv2.fillPoly(m, [pts], 255); m = cv2.GaussianBlur(m, (0, 0), 18).astype(np.float32)[..., None] / 255
    col = np.array((255, 240, 200) if moment != "soir" else (255, 190, 130), np.float32)
    img[:] = np.clip(img * (1 - 0.22 * m) + col * 0.22 * m, 0, 255).astype(np.uint8)

def ombre_portee(img, x0, x1, y, h=26):
    """Ombre douce au pied d'un meuble."""
    m = np.zeros(img.shape[:2], np.uint8); cv2.ellipse(m, (int((x0 + x1) / 2), int(y)), (int((x1 - x0) / 2 + 20), h), 0, 0, 360, 255, -1)
    m = cv2.GaussianBlur(m, (0, 0), 10).astype(np.float32)[..., None] / 255
    img[:] = (img * (1 - 0.28 * m)).astype(np.uint8)

# ------------------------------------------------------------------ meubles
def canape(img, x0, x1, y_sol, couleur):
    ombre_portee(img, x0, x1, y_sol)
    boite(img, x0 + 30, y_sol - 330, x1 - 30, y_sol - 150, couleur, 7, 30)                 # dossier
    for k in range(3):
        a = x0 + 40 + k * (x1 - x0 - 80) / 3; boite(img, a + 6, y_sol - 300, a + (x1 - x0 - 80) / 3 - 6, y_sol - 160, clair(couleur, 0.12), 5, 22)
    boite(img, x0 + 20, y_sol - 180, x1 - 20, y_sol - 60, fonce(couleur, 0.92), 7, 20)       # assise
    boite(img, x0, y_sol - 250, x0 + 80, y_sol - 50, couleur, 7, 30); boite(img, x1 - 80, y_sol - 250, x1, y_sol - 50, couleur, 7, 30)
    for xx in (x0 + 30, x1 - 50): boite(img, xx, y_sol - 60, xx + 20, y_sol, (90, 60, 40), 4)
    boite(img, x0 + 110, y_sol - 290, x0 + 230, y_sol - 180, (250, 210, 90), 5, 18)            # coussin

def table_basse(img, x0, x1, y_sol):
    ombre_portee(img, x0, x1, y_sol); boite(img, x0, y_sol - 120, x1, y_sol - 96, (170, 120, 80), 5)
    for xx in (x0 + 20, x1 - 40): boite(img, xx, y_sol - 98, xx + 20, y_sol, (140, 95, 60), 4)

def tele(img, x0, x1, y_sol, rng):
    boite(img, x0, y_sol - 160, x1, y_sol, (150, 105, 70), 6)
    for k in range(2): boite(img, x0 + 20 + k * (x1 - x0) / 2, y_sol - 140, x0 + (k + 1) * (x1 - x0) / 2 - 10, y_sol - 20, (170, 120, 80), 4)
    return ecran(img, x0 + 10, y_sol - 460, x1 - 10, y_sol - 170, "bleu")

def bureau_meuble(img, x0, x1, y_sol, rng, ordinateur=True):
    ombre_portee(img, x0, x1, y_sol)
    boite(img, x0, y_sol - 300, x1, y_sol - 270, (190, 150, 110), 6)
    for xx in (x0 + 20, x1 - 44): boite(img, xx, y_sol - 272, xx + 24, y_sol, (120, 120, 130), 4)
    if ordinateur:
        e = ecran(img, x0 + 40, y_sol - 520, x0 + 300, y_sol - 340, rng.choice(["graphique", "code", "bleu"]), rng); boite(img, x0 + 150, y_sol - 340, x0 + 190, y_sol - 300, (60, 60, 70), 4)
        boite(img, x0 + 330, y_sol - 340, x0 + 380, y_sol - 300, (250, 250, 248), 4); ligne(img, (x0 + 380, y_sol - 330), (x0 + 396, y_sol - 318), TRAIT, 5)   # tasse
        return e

def plan_travail(img, y_haut, couleur, rng):
    """Cuisine : placards hauts, crédence carrelée, plan de travail, placards bas, évier, plaques, casserole."""
    for x in range(40, W - 40, 250): boite(img, x, 260, x + 240, 600, couleur, 6, 8); boite(img, x + 100, 420, x + 140, 436, (200, 200, 205), 3)
    for y in range(610, y_haut, 46):
        for x in range(0, W, 46): cv2.rectangle(img, (x, y), (x + 46, y + 46), (220, 225, 230), 2)
    boite(img, -10, y_haut, W + 10, y_haut + 40, (230, 225, 215), 6)
    for x in range(20, W - 20, 260): boite(img, x, y_haut + 40, x + 250, SOL + 120, fonce(couleur, 0.95), 6, 6); boite(img, x + 110, y_haut + 80, x + 150, y_haut + 92, (200, 200, 205), 3)
    boite(img, 640, y_haut - 6, 900, y_haut + 14, (120, 120, 130), 4)
    for xx in (690, 820): cv2.ellipse(img, (xx, y_haut + 2), (46, 10), 0, 0, 360, (40, 40, 48), -1, AA)
    boite(img, 720, y_haut - 100, 880, y_haut - 6, (190, 70, 60), 6, 10); boite(img, 690, y_haut - 116, 910, y_haut - 98, (150, 50, 45), 5)
    return [(800, y_haut - 120)]

def frigo(img, x0, y_sol, gag):
    boite(img, x0, y_sol - 860, x0 + 260, y_sol - 10, (238, 242, 246), 7, 18)
    ligne(img, (x0 + 6, y_sol - 560), (x0 + 254, y_sol - 560), TRAIT, 6)
    for yy in (y_sol - 760, y_sol - 460): boite(img, x0 + 220, yy, x0 + 236, yy + 110, (180, 180, 190), 3)
    for k, (dx, dy, col) in enumerate(((40, -820, (230, 80, 70)), (150, -790, (80, 150, 230)), (60, -650, (250, 200, 60)))): cv2.circle(img, (x0 + dx, y_sol + dy), 14, col, -1, AA)
    postit(img, x0 + 50, y_sol - 760, gag, angle=-5)

def lit(img, x0, x1, y_sol, couleur):
    ombre_portee(img, x0, x1, y_sol)
    boite(img, x0, y_sol - 420, x0 + 40, y_sol, (150, 105, 70), 6)
    boite(img, x0 + 30, y_sol - 230, x1, y_sol - 80, (250, 250, 248), 6, 16)
    boite(img, x0 + 50, y_sol - 300, x0 + 240, y_sol - 210, (250, 250, 248), 6, 30)
    boite(img, x0 + 230, y_sol - 250, x1, y_sol - 60, couleur, 6, 20)
    for k in range(3): ligne(img, (x0 + 300 + k * 90, y_sol - 230), (x0 + 290 + k * 90, y_sol - 70), fonce(couleur, 0.8), 4)
    for xx in (x0 + 40, x1 - 30): boite(img, xx, y_sol - 80, xx + 24, y_sol, (150, 105, 70), 4)

def _avant(dessin, y_haut, zones):
    """Calque RGBA du premier plan : `dessin(img)` peint le comptoir ; opaque sous `y_haut` et dans les petites `zones` posées
    dessus (toujours au bord de l'image : jamais devant le visage d'un personnage)."""
    av = np.zeros((H, W, 4), np.uint8); a3 = av[..., :3].copy(); dessin(a3); av[..., :3] = a3
    av[y_haut:, :, 3] = 255
    for x0, y0, x1, y1 in zones:
        z = a3[y0:y1, x0:x1].astype(int); av[y0:y1, x0:x1, 3] = np.where(np.abs(z).sum(2) > 0, 255, 0)
    return av

def comptoir_avant(av, y, couleur, deco=(170, 120, 70), rng=None):
    """Premier plan : comptoir / bureau qui passe DEVANT les personnages (calque RGBA)."""
    boite(av, -20, y, W + 20, y + 44, deco, 7)
    boite(av, -20, y + 40, W + 20, H + 20, couleur, 7)
    for x in range(60, W, 240): boite(av, x, y + 90, x + 180, H - 60, fonce(couleur, 0.92), 5, 10)

# ------------------------------------------------------------------ lieux
GAGS = {
    "salon": ["Home sweet home (sauf le lundi)", "Vivre, rire, payer son loyer", "Ici on fait la sieste"],
    "cuisine": ["Qui a mangé mon yaourt ?", "Régime : demain", "Liste : chocolat, chocolat, pain"],
    "bureau": ["Objectif : survivre à la réunion", "Ensemble, on va plus loin (en retard)", "Réunion pour préparer la réunion"],
    "cabinet_medical": ["Avez-vous bien bu de l'eau ?", "Ne cherchez pas vos symptômes sur internet", "Le docteur est en retard (comme vous)"],
    "bar": ["Happy hour toute la nuit", "Ici on ne juge pas (un peu)", "Eau plate : sur demande écrite"],
    "chambre": ["Ne pas déranger (jamais)", "5 minutes de plus", "Rêve grand, dors longtemps"],
    "salle_sport": ["No pain… no pain.", "Lundi, je commence", "Transpirer, c'est pleurer du muscle"],
    "magasin": ["Promo : -0 %", "Prix choc (pour votre compte)", "Caisse rapide (en théorie)"],
    "classe": ["Interro surprise (pas une surprise)", "Silence = 20/20", "Le savoir, c'est le pouvoir (de dormir)"],
    "rue": ["Boulangerie Le Pain Perdu", "Coiffure Hair Mess", "Pressing Sec et Net"],
    "administration": ["Merci de patienter (encore)", "Formulaire B12 : voir formulaire A7", "Pièce manquante ? Revenez demain"],
    "hall": ["Merci de ne pas claquer la porte", "Réunion de copropriété : venez nombreux (personne)", "Ascenseur en panne depuis 2009"],
    "caverne": ["Ugh", "Chasse au mammouth : mardi", "Feu : ne pas toucher"],
    "palais": ["Silence, le roi dort", "Brioche à volonté", "Interdit aux gueux"],
    "restaurant": ["Plat du jour : celui d'hier", "Menu : tout est fait maison (la maison d'à côté)", "Chef : de mauvaise humeur"],
}
COULEURS_MUR = {"salon": (238, 214, 190), "cuisine": (214, 232, 222), "bureau": (214, 222, 234), "cabinet_medical": (220, 238, 236),
                "bar": (150, 76, 60), "chambre": (210, 208, 236), "salle_sport": (226, 228, 232), "magasin": (244, 240, 230),
                "classe": (240, 226, 196), "rue": (160, 190, 220), "restaurant": (236, 206, 176),
                "administration": (52, 92, 160), "hall": (236, 226, 206), "caverne": (150, 120, 92), "palais": (244, 236, 214)}

def _variante(c, rng, amp=14): return _c(np.array(c) + rng.integers(-amp, amp + 1, 3))

def dessiner(lieu, bible=None, graine=7):
    """Décor complet d'un lieu (voir le docstring du module). `bible` : moment, gags, palette… (studio.bible)."""
    b = bible or {}; rng = np.random.default_rng(graine); moment = b.get("moment", "jour")
    lieu = lieu if lieu in LIEUX else "salon"
    img = np.zeros((H, W, 3), np.uint8); av = None
    gags = list(b.get("gags") or []) + GAGS[lieu]; gag = lambda k: gags[k % len(gags)]
    allume = moment in ("soir", "nuit")
    res = {"fenetre": None, "lampes": [], "vapeur": [], "neons": [], "ecrans": []}
    c_mur = _variante(b.get("c_mur") or COULEURS_MUR[lieu], rng)
    if lieu == "rue":
        ciel(img, 0, 0, W, SOL, moment, rng, False)
        x = -40; k = 0
        while x < W:                                                       # façades d'immeubles
            bw = int(rng.uniform(300, 420)); col = _variante(rng.choice([(236, 200, 160), (220, 160, 140), (200, 210, 225), (240, 226, 190)]), rng)
            top = int(rng.uniform(150, 360)); boite(img, x, top, x + bw, SOL + 4, col, 7)
            for yy in range(top + 50, SOL - 360, 170):
                for xx in range(x + 40, x + bw - 90, 120):
                    fen_c = (255, 220, 130) if (allume and rng.random() < 0.6) else (140, 180, 220)
                    boite(img, xx, yy, xx + 70, yy + 100, fen_c, 5); boite(img, xx - 8, yy + 100, xx + 78, yy + 112, (240, 240, 240), 4)
            boite(img, x + 30, SOL - 330, x + bw - 30, SOL - 250, (200, 60, 60) if k % 2 == 0 else (60, 110, 160), 6, 6)
            texte(img, gag(k), x + 46, SOL - 324, x + bw - 46, SOL - 256, (255, 255, 255), 44)
            boite(img, x + 50, SOL - 240, x + bw - 50, SOL, (150, 190, 215), 6)      # vitrine
            for kk in range(3): ligne(img, (x + 70 + kk * 40, SOL - 200), (x + 110 + kk * 40, SOL - 120), (255, 255, 255), 5)
            x += bw; k += 1
        sol(img, (186, 186, 190), "trottoir")
        lx = 900; ligne(img, (lx, SOL + 120), (lx, 420), TRAIT, 16); ligne(img, (lx, SOL + 120), (lx, 420), (60, 70, 80), 9)
        boite(img, lx - 60, 380, lx + 20, 430, (60, 70, 80), 5); res["lampes"].append((lx - 20, 440))
        res["fenetre"] = (0, 0, W, SOL)
    elif lieu not in DX.NOUVEAUX:
        motif_mur = b.get("motif_mur") or {"salon": "rayures", "cuisine": "uni", "bureau": "uni", "cabinet_medical": "lambris", "bar": "briques",
                                            "chambre": "fleurs", "salle_sport": "uni", "magasin": "uni", "classe": "lambris", "restaurant": "losanges"}[lieu]
        mur(img, c_mur, motif_mur, rng)
        c_sol, m_sol = {"salon": ((196, 150, 110), "parquet"), "cuisine": ((236, 236, 232), "damier"), "bureau": ((150, 160, 175), "moquette"),
                        "cabinet_medical": ((210, 220, 225), "carrelage"), "bar": ((120, 80, 55), "parquet"), "chambre": ((200, 160, 120), "parquet"),
                        "salle_sport": ((70, 74, 82), "moquette"), "magasin": ((230, 230, 226), "carrelage"), "classe": ((190, 150, 110), "parquet"),
                        "restaurant": ((180, 120, 90), "damier")}[lieu]
        sol(img, _variante(c_sol, rng, 8), m_sol)
        if lieu not in ("bar",): plinthe(img)
    if lieu == "salon":
        res["fenetre"] = (90, 330, 430, 760); fenetre(img, *res["fenetre"], moment, rng, rideaux=_variante((200, 90, 80), rng))
        cadre_tableau(img, 620, 340, 860, 560, rng); horloge(img, 950, 640, 50, (b.get("heure") or (10, 10)))
        etagere(img, 560, 760, 1040, rng); affiche(img, 560, 580, 860, 730, gag(0), (252, 248, 236), punaises=False)
        canape(img, 120, 960, SOL + 110, _variante((80, 120, 170), rng)); table_basse(img, 380, 700, SOL + 260)
        res["lampes"].append(lampe_pied(img, 1010, SOL + 60, allume))
    elif lieu == "cuisine":
        res["vapeur"] = plan_travail(img, 940, _variante((120, 170, 160), rng), rng)
        frigo(img, 20, SOL + 40, gag(0))
        res["fenetre"] = (330, 280, 600, 560); fenetre(img, *res["fenetre"], moment, rng)
        horloge(img, 920, 200, 48, b.get("heure"))
    elif lieu == "bureau":
        res["fenetre"] = (60, 280, 520, 820); fenetre(img, *res["fenetre"], moment, rng, cadre=(200, 205, 215))
        boite(img, 600, 380, 1040, 700, (252, 252, 250), 7, 6)              # tableau blanc
        pts = [(640, 470), (720, 520), (800, 500), (880, 600), (980, 650)]
        cv2.polylines(img, [np.array(pts, np.int32)], False, (220, 60, 60), 7, AA); ligne(img, (640, 670), (1010, 670), TRAIT, 4); ligne(img, (640, 670), (640, 450), TRAIT, 4)
        texte(img, gag(0), 620, 392, 1020, 452, (40, 60, 160), 40)
        affiche(img, 640, 740, 960, 980, gag(1), (90, 130, 190), (255, 255, 255), dessin="montagne")
        pot(img, 1000, SOL + 40, 1.4); boite(img, 40, SOL - 380, 160, SOL + 40, (220, 236, 250), 6, 10)    # fontaine à eau
        boite(img, 60, SOL - 500, 140, SOL - 380, (150, 200, 240), 6, 20); horloge(img, 540, 200, 46, b.get("heure"))
        av = _avant(lambda a3: (comptoir_avant(a3, 1560, (200, 170, 130), (160, 120, 80)), boite(a3, 30, 1486, 150, 1566, (250, 250, 248), 5),
                                ligne(a3, (150, 1502), (176, 1524), TRAIT, 6), pot(a3, 1010, 1566, 0.8)), 1560, [(0, 1400, 200, 1566), (930, 1410, W, 1566)])
    elif lieu == "cabinet_medical":
        res["fenetre"] = (720, 300, 1020, 640); fenetre(img, *res["fenetre"], moment, rng, cadre=(240, 244, 248))
        affiche(img, 70, 380, 330, 850, gag(0), (252, 252, 248), dessin="squelette")
        for k in range(2): cadre_tableau(img, 380 + k * 160, 300, 510 + k * 160, 430, rng, (60, 60, 70), "abstrait"); texte(img, "DIPLÔME", 396 + k * 160, 340, 494 + k * 160, 390, TRAIT, 20)
        for k in range(10): ligne(img, (680, 760 + k * 40), (700 if k % 2 else 720, 760 + k * 40), TRAIT, 4)    # toise
        boite(img, 380, SOL - 260, 700, SOL - 190, (150, 210, 200), 6, 20); boite(img, 380, SOL - 196, 700, SOL - 170, (220, 225, 230), 5)
        for xx in (400, 660): boite(img, xx, SOL - 172, xx + 20, SOL + 40, (180, 185, 195), 4)
        boite(img, 880, SOL - 280, 1040, SOL - 230, (250, 250, 250), 6, 10); ligne(img, (960, SOL - 330), (960, SOL - 280), (180, 185, 195), 8)
        av = _avant(lambda a3: (comptoir_avant(a3, 1570, (236, 238, 242), (200, 205, 215)), boite(a3, 40, 1480, 110, 1576, (90, 140, 200), 5, 6),
                                [ligne(a3, (60 + 14 * k, 1480), (54 + 18 * k, 1430), c, 7) for k, c in enumerate(((220, 50, 50), (40, 80, 200), (40, 40, 48)))],
                                boite(a3, 950, 1520, 1050, 1576, (250, 250, 250), 5, 8)), 1570, [(0, 1420, 130, 1576), (940, 1510, W, 1576)])
    elif lieu == "bar":
        for k in range(3):                                                 # étagères de bouteilles rétroéclairées
            y = 720 + k * 180; boite(img, 60, y, 1020, y + 20, (90, 60, 40), 5)
            for x in range(90, 1000, 64):
                col = tuple(int(v) for v in rng.choice([(70, 150, 90), (160, 100, 50), (200, 200, 220), (120, 50, 70), (230, 180, 70)]))
                hb = int(rng.uniform(110, 160)); boite(img, x, y - hb + 40, x + 40, y, col, 4, 6); boite(img, x + 12, y - hb, x + 28, y - hb + 44, col, 4)
                boite(img, x + 6, y - hb + 70, x + 34, y - hb + 100, (245, 235, 210), 3)
        res["neons"].append(neon(img, 190, 400, 890, 550, gag(0)))
        for xx in (200, 540, 880): res["lampes"].append(suspension(img, xx, 120, True))
        sol(img, (110, 70, 50), "parquet")
        av = _avant(lambda a3: (comptoir_avant(a3, 1540, (120, 70, 45), (180, 130, 80)), boite(a3, 30, 1450, 90, 1546, (250, 200, 80), 4, 6),
                                boite(a3, 990, 1450, 1050, 1546, (250, 200, 80), 4, 6)), 1540, [(0, 1440, 100, 1546), (980, 1440, W, 1546)])
    elif lieu == "chambre":
        res["fenetre"] = (640, 300, 980, 700); fenetre(img, *res["fenetre"], "nuit" if moment == "soir" else moment, rng, rideaux=_variante((120, 100, 180), rng))
        affiche(img, 90, 380, 400, 700, gag(0), (60, 70, 120), (255, 255, 255))
        cadre_tableau(img, 440, 360, 580, 500, rng, sujet="portrait")
        lit(img, 40, 900, SOL + 160, _variante((230, 150, 170), rng))
        boite(img, 920, SOL - 140, 1060, SOL + 40, (170, 120, 80), 6); res["lampes"].append((990, SOL - 240))
        poly(img, [(950, SOL - 140), (1030, SOL - 140), (1010, SOL - 230), (970, SOL - 230)], (255, 236, 170) if allume else (240, 225, 190), 5)
    elif lieu == "salle_sport":
        boite(img, 60, 300, 1020, 900, (200, 225, 240), 8, 6)              # grand miroir
        for k in range(3): ligne(img, (120 + k * 300, 860), (260 + k * 300, 360), (235, 245, 252), 8)
        affiche(img, 340, 400, 740, 590, gag(0), (230, 60, 60), (255, 255, 255))
        horloge(img, 900, 420, 52, b.get("heure"))
        boite(img, 60, SOL - 220, 520, SOL - 200, (90, 90, 100), 5)          # râtelier d'haltères
        for k in range(6): boite(img, 80 + k * 72, SOL - 290, 130 + k * 72, SOL - 222, (40, 40, 48), 4, 10)
        for xx in (80, 500): boite(img, xx, SOL - 200, xx + 20, SOL + 40, (90, 90, 100), 4)
        poly(img, [(640, SOL + 40), (1040, SOL + 40), (1020, SOL - 30), (660, SOL - 30)], (50, 50, 60), 6)    # tapis de course
        ligne(img, (980, SOL - 30), (1010, SOL - 300), TRAIT, 14); boite(img, 930, SOL - 330, 1060, SOL - 280, (60, 60, 70), 5)
    elif lieu == "magasin":
        for k in range(3):                                                 # rayons garnis de produits
            y = 520 + k * 210; boite(img, 30, y + 170, 1050, y + 194, (200, 200, 205), 5)
            x = 50
            while x < 1020:
                bw = int(rng.uniform(50, 90)); bh = int(rng.uniform(100, 160)); col = _variante(rng.choice([(230, 80, 70), (60, 130, 210), (250, 200, 60), (90, 170, 110), (240, 140, 60), (170, 100, 180)]), rng)
                boite(img, x, y + 170 - bh, x + bw, y + 172, col, 4, 4); boite(img, x + 8, y + 190 - bh, x + bw - 8, y + 210 - bh + 20, (250, 250, 245), 3)
                x += bw + 6
            for xx in range(80, 1000, 220): boite(img, xx, y + 196, xx + 80, y + 226, (255, 235, 90), 3); texte(img, f"{int(rng.integers(1, 9))},99 €", xx + 4, y + 198, xx + 76, y + 224, TRAIT, 20)
        boite(img, 200, 370, 880, 500, (230, 50, 60), 7, 10); texte(img, gag(0), 220, 382, 860, 488, (255, 255, 255), 60)
        av = _avant(lambda a3: (comptoir_avant(a3, 1560, (90, 100, 120), (60, 60, 70)), boite(a3, 900, 1430, 1070, 1566, (60, 60, 70), 6, 8),
                                ecran(a3, 920, 1440, 1050, 1530, "bleu")), 1560, [(890, 1420, W, 1566)])
    elif lieu == "classe":
        boite(img, 120, 360, 960, 820, (50, 90, 70), 14, 6)                # tableau noir
        texte(img, gag(0), 160, 390, 920, 660, (245, 245, 235), 64)
        for k in range(3): ligne(img, (200 + k * 20, 760), (300 + k * 40, 750), (240, 240, 230), 4)
        boite(img, 140, 820, 940, 844, (160, 120, 80), 5); horloge(img, 1010, 260, 44, b.get("heure"))
        for xx in (40, 860): boite(img, xx, SOL - 200, xx + 200, SOL - 176, (200, 160, 110), 5); boite(img, xx + 20, SOL - 176, xx + 40, SOL + 40, (100, 100, 110), 4); boite(img, xx + 160, SOL - 176, xx + 180, SOL + 40, (100, 100, 110), 4)
        res["fenetre"] = None
    elif lieu == "restaurant":
        res["fenetre"] = (640, 300, 1000, 660); fenetre(img, *res["fenetre"], moment, rng, rideaux=(190, 60, 60))
        boite(img, 80, 360, 500, 820, (40, 44, 48), 12, 6); texte(img, "MENU", 100, 380, 480, 460, (250, 240, 200), 54); texte(img, gag(0), 110, 470, 470, 800, (250, 240, 200), 40)
        for xx in (200, 880): res["lampes"].append(suspension(img, xx, 150, allume))
        boite(img, 600, SOL - 120, 1060, SOL - 90, (250, 250, 250), 5)       # table nappée (carreaux)
        for x in range(610, 1050, 40):
            for kk, y in enumerate(range(SOL - 90, SOL + 10, 34)):
                if (x // 40 + kk) % 2: cv2.rectangle(img, (x, y), (x + 40, y + 34), (220, 70, 70), -1)
        cv2.rectangle(img, (600, SOL - 90), (1060, SOL + 10), TRAIT, 5)
        boite(img, 760, SOL - 200, 900, SOL - 120, (250, 250, 248), 5, 30); ligne(img, (700, SOL - 200), (700, SOL - 120), (200, 200, 205), 5)
    elif lieu in DX.NOUVEAUX:                                              # administration, hall, caverne, palais
        if lieu == "administration": mur(img, c_mur, "uni", rng); sol(img, _variante((200, 200, 196), rng, 6), "carrelage"); plinthe(img)
        r_ = DX.NOUVEAUX[lieu](img, rng, res, gag, moment, allume)
        if r_ is not None: av = r_
    DX.habiller(img, lieu, rng, res, moment, gag)                          # petits objets qui rendent le lieu vivant
    # lumière : soleil par la fenêtre, lampes allumées le soir
    tache_soleil(img, res["fenetre"] if lieu != "rue" else None, moment)
    for c in res["lampes"]:
        if allume or lieu == "bar": halo(img, c, 420, (255, 214, 140), 0.32)
    if moment == "nuit" and lieu != "rue": img[:] = (img.astype(np.float32) * np.array((0.72, 0.74, 0.9))).astype(np.uint8)   # pénombre bleutée
    res["fond"] = img; res["avant"] = av
    return res

def lieu_de(texte_, defaut="salon"):
    """Lieu du catalogue d'après une description (anglais ou français) : « doctor's office », « au bureau »… (le plus cité gagne)."""
    t = (texte_ or "").lower()
    regles = [("caverne", r"pr[ée]histo|caverne|grotte|mammouth|cro-?magnon|n[ée]andert|homme des cavernes"),
              ("palais", r"palace|castle|throne|chandelier|ch[âa]teau|palais|versailles|\broi\b|\breine\b|majest[ée]|cour royale|marquis"),
              ("administration", r"government|town hall|city hall|tax office|prefecture|\bcaf\b|pr[ée]fecture|mairie|administration|guichet|formulaire|imp[ôo]ts|france travail|p[ôo]le emploi|\bs[ée]cu\b|dossier"),
              ("hall", r"hallway|apartment building|staircase|stairs|mailbox|immeuble|voisin|palier|escalier|concierge|gardien|ascenseur|bo[iî]te aux lettres|copropri"),
              ("cabinet_medical", r"m[ée]decin|docteur|doctor|medical|m[ée]dical|clinic|hospital|h[ôo]pital|cabinet|infirmi|nurse|dentist|pharmac"),
              ("salle_sport", r"gym|salle de sport|fitness|muscu|coach|sport|treadmill|halt[èe]re"),
              ("bar", r"\bbar\b|pub|ap[ée]ro|cocktail|bi[èe]re|beer|boire un verre|night ?club|bo[îi]te de nuit"),
              ("restaurant", r"restaurant|resto|serveur|waiter|menu|addition|caf[ée] ?terrasse|brasserie|diner"),
              ("cuisine", r"kitchen|cuisine|frigo|fridge|cuisin|recette|four|repas|d[îi]ner|petit[- ]d[ée]j"),
              ("bureau", r"office|bureau|boss|patron|chef de|r[ée]union|meeting|coll[èe]gue|entreprise|open ?space|boulot|travail|job|manager|stagiaire"),
              ("classe", r"class|[ée]cole|school|prof|teacher|[ée]l[èe]ve|lyc[ée]e|coll[èe]ge|cours|devoir|interro|exam"),
              ("magasin", r"shop|store|magasin|supermarket|supermarch|caisse|cashier|courses|boutique|vendeu|achat|soldes"),
              ("chambre", r"bedroom|chambre|\blit\b|\bbed\b|dormir|sleep|r[ée]veil|alarm|sieste|nuit blanche"),
              ("rue", r"street|\brue\b|outside|dehors|trottoir|sidewalk|parking|arr[êe]t de bus|bus stop|city|ville|parc\b|park"),
              ("salon", r"living room|apartment|salon|canap[ée]|sofa|t[ée]l[ée]\b|\btv\b|maison|home|ch[ée]ri|cl[ée]s|famille|maman|papa|coloc|appart")]
    scores = {lieu: len(re.findall(motif, t)) for lieu, motif in regles}      # le lieu le plus souvent évoqué (à égalité : le 1er de la liste)
    if re.search(r"parking|car park|\bcar\b|voiture garée|devant le magasin", t): scores["rue"] += 2   # un parking est dehors
    meilleur = max(regles, key=lambda r: scores[r[0]])[0]
    return meilleur if scores[meilleur] else defaut
