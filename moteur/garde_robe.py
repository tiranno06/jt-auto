"""Garde-robe détaillée des personnages (style « toons ») : coiffures avec mèches et volume, barbes, couvre-chefs, motifs de tissu
et finitions des vêtements (coutures, poches, poignets, lacets…). Tout est dessiné au trait noir et en aplats, sans IA.

Appelé par marionnette.py ; les coordonnées sont celles de la tête : centre (cx, cy), rayons (rx, ry), échelle s, inclinaison p["tilt"]."""
import math
import numpy as np, cv2

import marionnette as M

# coiffures en plus de celles de marionnette.COIFFURES
COIFFURES = ("ondule", "frange", "afro", "herisse", "raie", "rase", "tresses", "anglaises", "banane", "court_texture", "degarni")
ARRIERE = ("ondule", "frange", "afro", "herisse", "tresses", "anglaises")
BARBES = ("barbe_courte", "barbe_pleine", "bouc", "favoris")
CHAPEAUX = ("bonnet", "casquette", "beret", "chapeau", "melon", "tricorne", "casque_chantier", "toque", "bob", "couronne", "bandana", "serre_tete")
MOTIFS = ("fleurs", "palmiers", "taches", "losanges", "chevrons", "etoiles")


def _R(cx, cy, p):
    a = math.radians(p["tilt"])
    return lambda px, py: M._rot(px, py, cx, cy, a)


def _masse(img, pts, col, ep):
    """Forme pleine au trait noir."""
    M._poly(img, pts, col); M._poly(img, pts, M.TRAIT, True, ep)


def _meche(img, a, b, c, col, ep):
    """Mèche (courbe de Bézier quadratique a -> c, tirée vers b)."""
    pts = [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * b[0] + t * t * c[0], (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * b[1] + t * t * c[1]) for t in np.linspace(0, 1, 10)]
    M._poly(img, pts, col, False, ep)


def _boucle(img, c, r, col, fonce, s):
    """Une boucle (anglaise, perruque) : rond cerné avec une petite spirale."""
    M._ellipse(img, c, (r + 4 * s, r + 4 * s), 0, M.TRAIT); M._ellipse(img, c, (r, r), 0, col)
    M._arc(img, c, (r * 0.55, r * 0.55), 0, 200, 470, fonce, 3 * s)


def _calotte(cx, cy, rx, ry, R, k=0.98, bas=0.22, n=16):
    """Dessus de la tête (moitié haute de l'ellipse), descendu jusqu'à cy - bas * ry sur les côtés."""
    return [R(cx + rx * k * math.cos(math.pi + math.pi * j / n), cy - ry * bas + ry * k * math.sin(math.pi + math.pi * j / n)) for j in range(n + 1)]


# ------------------------------------------------------------------ coiffures (derrière la tête)
def cheveux_arriere(img, t, rx, ry, s, p, style, col):
    cx, cy = t; bal = p.get("balance", 0.0); ep = 6 * s; fonce = M._fonce(col, 0.74); R = _R(cx, cy, p)
    if style in ("ondule", "frange"):                                      # longs ondulés jusqu'aux épaules / carré plongeant
        bas = 1.75 if style == "ondule" else 0.85; larg = 1.2 if style == "ondule" else 1.16
        g, d = [], []
        for v in np.linspace(-0.15, bas, 14):
            w = rx * (larg + (0.07 * math.sin(v * 9 + p.get("t", 0) * 1.5) if style == "ondule" else 0.02 * v))
            g.append(R(cx - w + bal * 8 * s * max(0, v), cy + ry * v)); d.append(R(cx + w + bal * 8 * s * max(0, v), cy + ry * v))
        haut = [R(cx + rx * larg * math.cos(math.pi + math.pi * j / 12), cy - ry * 0.15 + ry * 1.08 * math.sin(math.pi + math.pi * j / 12)) for j in range(13)]
        fond = []
        for j in range(9):                                                 # bas en festons (ondulés) ou coupé net, pointes vers l'intérieur
            u = j / 8; fx = cx + rx * larg * (2 * u - 1) + bal * 8 * s * bas
            fond.append(R(fx, cy + ry * (bas + (0.08 * math.sin(u * math.pi * 4) if style == "ondule" else -0.06 * math.sin(u * math.pi)))))
        pts = haut + d + fond[::-1] + g[::-1]
        _masse(img, pts, col, ep)
        for k in range(-3, 4):                                              # mèches ondulées dans la masse
            x0 = cx + k * rx * 0.3
            _meche(img, R(x0, cy + ry * 0.6), R(x0 + rx * 0.12 * (1 if k % 2 else -1) + bal * 10 * s, cy + ry * (0.6 + bas) / 2 + ry * 0.4), R(x0 + bal * 10 * s, cy + ry * (bas - 0.08)), fonce, 3 * s)
    elif style == "afro":
        c0 = (cx, cy - ry * 0.28); A = (rx * 1.42, ry * 1.32); n = 26
        for j in range(n):                                                 # bord bouclé : petits ronds tout autour
            a = 2 * math.pi * j / n; M._ellipse(img, (c0[0] + math.cos(a) * A[0], c0[1] + math.sin(a) * A[1]), (26 * s + ep, 26 * s + ep), 0, M.TRAIT)
        M._ellipse(img, c0, (A[0] + ep, A[1] + ep), 0, M.TRAIT)
        for j in range(n):
            a = 2 * math.pi * j / n; M._ellipse(img, (c0[0] + math.cos(a) * A[0], c0[1] + math.sin(a) * A[1]), (26 * s, 26 * s), 0, col)
        M._ellipse(img, c0, A, 0, col)
        rng = np.random.default_rng(5)
        for _ in range(40):                                                # texture : petites boucles
            a = rng.uniform(0, 2 * math.pi); r_ = rng.uniform(0.3, 0.92)
            M._arc(img, (c0[0] + math.cos(a) * A[0] * r_, c0[1] + math.sin(a) * A[1] * r_), (9 * s, 9 * s), 0, rng.uniform(0, 360), rng.uniform(0, 360) + 200, fonce, 3 * s)
    elif style == "herisse":                                               # touffe en bataille (homme des cavernes)
        pts = []
        for j in range(25):
            a = math.pi * (0.92 + 1.16 * j / 24); r_ = 1.16 + (0.16 if j % 2 else 0.0)
            pts.append(R(cx + math.cos(a) * rx * r_, cy - ry * 0.05 + math.sin(a) * ry * r_ * 0.98))
        pts += [R(cx + rx * 1.05, cy + ry * 0.35), R(cx - rx * 1.05, cy + ry * 0.35)]
        _masse(img, pts, col, ep)
        for k in range(8):
            a = math.pi * (1.05 + 0.9 * k / 7); _meche(img, R(cx + math.cos(a) * rx * 0.75, cy + math.sin(a) * ry * 0.75), R(cx + math.cos(a) * rx * 1.0, cy + math.sin(a) * ry * 0.95), R(cx + math.cos(a + 0.12) * rx * 1.18, cy + math.sin(a + 0.12) * ry * 1.12), fonce, 3 * s)
    elif style == "tresses":                                               # deux nattes qui pendent et se balancent
        for sg in (-1, 1):
            x0, y0 = cx + sg * rx * 0.9, cy + ry * 0.1; sw = (bal * 14 + 6 * math.sin(p.get("t", 0) * 3 + sg)) * s
            for k in range(7):
                u = k / 6; c = (x0 + sg * 10 * s * u + sw * u, y0 + u * ry * 1.25)
                M._ellipse(img, c, (24 * s + ep, 17 * s + ep), sg * 20, M.TRAIT); M._ellipse(img, c, (24 * s, 17 * s), sg * 20, col)
                M._arc(img, c, (16 * s, 10 * s), sg * 20, 20, 160, fonce, 3 * s)
            bout = (x0 + sg * 10 * s + sw, y0 + ry * 1.25 + 26 * s)
            M._ellipse(img, (bout[0], bout[1] - 8 * s), (10 * s, 7 * s), 0, (230, 80, 120))
            M._poly(img, [(bout[0] - 14 * s, bout[1]), (bout[0] + 14 * s, bout[1]), (bout[0], bout[1] + 26 * s)], col); M._poly(img, [(bout[0] - 14 * s, bout[1]), (bout[0] + 14 * s, bout[1]), (bout[0], bout[1] + 26 * s)], M.TRAIT, True, 3 * s)
    elif style == "anglaises":                                             # boucles en grappes jusqu'aux épaules (perruque, grande dame)
        _masse(img, [R(cx + rx * 1.15 * math.cos(math.pi + math.pi * j / 14), cy + ry * 0.05 + ry * 1.15 * math.sin(math.pi + math.pi * j / 14)) for j in range(15)]
               + [R(cx + rx * 1.15, cy + ry * 0.9), R(cx - rx * 1.15, cy + ry * 0.9)], col, ep)
        for sg in (-1, 1):
            for k in range(5):
                for j in range(2):
                    _boucle(img, R(cx + sg * rx * (1.0 + 0.2 * j), cy - ry * 0.3 + k * ry * 0.33 + j * ry * 0.16 + bal * 4 * s), 24 * s, col, fonce, s)


# ------------------------------------------------------------------ coiffures (devant : frange, dessus de la tête)
def cheveux_avant(img, t, rx, ry, s, p, style, col, dos):
    cx, cy = t; ep = 5 * s; fonce = M._fonce(col, 0.74); R = _R(cx, cy, p)
    if dos:                                                                # vu de dos : l'arrière de la tête est couvert
        if style not in ("rase", "degarni"): M._ellipse(img, t, (rx * 1.02, ry * 1.0), p["tilt"], col)
        return
    if style in ("ondule", "frange", "raie", "court_texture"):              # raie sur le côté, frange balayée
        raie = cx - rx * 0.32
        cap = _calotte(cx, cy, rx, ry, R, 0.99, 0.18)
        bord = [R(cx + rx * 0.95, cy - ry * (0.05 if style in ("ondule", "frange") else 0.3)), R(cx + rx * 0.45, cy - ry * 0.42),
                R(cx - rx * 0.1, cy - ry * 0.5), R(raie, cy - ry * 0.72), R(cx - rx * 0.6, cy - ry * 0.45), R(cx - rx * 0.95, cy - ry * (0.05 if style in ("ondule", "frange") else 0.3))]
        pts = cap + bord
        _masse(img, pts, col, ep)
        for k in range(5):                                                 # mèches qui partent de la raie
            sg = 1 if k >= 2 else -1; u = (k - 1.5) / 3 if sg > 0 else (k + 1) / 2
            _meche(img, R(raie + sg * 6 * s, cy - ry * 0.88), R(raie + sg * rx * (0.22 + 0.2 * abs(u)), cy - ry * 0.85), R(raie + sg * rx * (0.28 + 0.28 * abs(u)), cy - ry * (0.55 - 0.08 * abs(u))), fonce, 3 * s)
        M._ligne(img, R(raie, cy - ry * 0.97), R(raie, cy - ry * 0.74), fonce, 3 * s)
        if style in ("ondule", "frange"):                                  # longueurs devant les joues, de chaque côté du visage
            bas = 0.95 if style == "ondule" else 0.62
            for sg in (-1, 1):
                pts = [R(cx + sg * rx * 0.97, cy - ry * 0.15), R(cx + sg * rx * 1.12, cy + ry * 0.2), R(cx + sg * rx * 1.1, cy + ry * bas),
                       R(cx + sg * rx * 0.86, cy + ry * (bas - 0.1)), R(cx + sg * rx * 0.88, cy + ry * 0.2)]
                _masse(img, pts, col, ep); _meche(img, R(cx + sg * rx * 0.98, cy), R(cx + sg * rx * 1.06, cy + ry * 0.3), R(cx + sg * rx * 1.0, cy + ry * (bas - 0.12)), fonce, 3 * s)
        elif style == "raie":
            for sg in (-1, 1): M._ligne(img, R(cx + sg * rx * 0.86, cy - ry * 0.32), R(cx + sg * rx * 0.88, cy - ry * 0.05), col, 11 * s)   # pattes
    elif style == "afro":
        pts = _calotte(cx, cy, rx, ry, R, 1.0, 0.25) + [R(cx + rx * (0.8 - 0.2 * j), cy - ry * (0.48 + (0.06 if j % 2 else 0))) for j in range(9)]
        M._poly(img, pts, col)
        for j in range(9): M._arc(img, R(cx + rx * (0.8 - 0.2 * j), cy - ry * 0.5), (rx * 0.11, ry * 0.07), p["tilt"], 0, 180, M.TRAIT, 4 * s)
    elif style == "herisse":                                               # frange en pointes sur le front
        pts = _calotte(cx, cy, rx, ry, R, 1.0, 0.12)
        for j in range(11):
            u = j / 10; pts.append(R(cx + rx * (0.95 - 1.9 * u), cy - ry * (0.18 if j % 2 else 0.5)))
        _masse(img, pts, col, ep)
    elif style in ("tresses",):                                            # cheveux tirés, raie au milieu
        pts = _calotte(cx, cy, rx, ry, R, 0.99, 0.15)
        _masse(img, pts, col, ep); M._ligne(img, R(cx, cy - ry * 0.98), R(cx, cy - ry * 0.55), fonce, 3 * s)
        for sg in (-1, 1):
            for k in range(3): M._arc(img, R(cx + sg * rx * 0.02, cy + ry * 0.1), (rx * (0.45 + 0.17 * k), ry * 0.95), p["tilt"], 270 - sg * 15 - sg * 30, 270 - sg * 15, fonce, 3 * s)
    elif style == "anglaises":                                             # rangée de boucles sur le front
        for j in range(7):
            u = j / 6; a = math.pi * (1.08 + 0.84 * u)
            _boucle(img, R(cx + math.cos(a) * rx * 0.95, cy - ry * 0.12 + math.sin(a) * ry * 0.95), 24 * s, col, fonce, s)
    elif style == "banane":                                                # banane (quiff) relevée sur le devant
        pts = _calotte(cx, cy, rx, ry, R, 0.98, 0.3) + [R(cx + rx * 0.7, cy - ry * 0.55), R(cx + rx * 0.2, cy - ry * 1.0), R(cx - rx * 0.1, cy - ry * 1.3),
                                                          R(cx - rx * 0.55, cy - ry * 1.2), R(cx - rx * 0.75, cy - ry * 0.6)]
        _masse(img, pts, col, ep)
        for k in range(4): _meche(img, R(cx - rx * (0.5 - 0.25 * k), cy - ry * 1.12), R(cx + rx * (0.1 + 0.2 * k), cy - ry * 1.05), R(cx + rx * (0.35 + 0.15 * k), cy - ry * 0.65), fonce, 3 * s)
        for sg in (-1, 1): M._ligne(img, R(cx + sg * rx * 0.93, cy - ry * 0.35), R(cx + sg * rx * 0.95, cy - ry * 0.05), col, 10 * s)
    elif style == "rase":                                                  # cheveux ras : ombre + piqué
        pts = _calotte(cx, cy, rx, ry, R, 0.97, 0.3) + [R(cx + rx * 0.7, cy - ry * 0.5), R(cx - rx * 0.7, cy - ry * 0.5)]
        M._poly(img, pts, col)
        rng = np.random.default_rng(11)
        for _ in range(60):
            a = rng.uniform(math.pi * 1.05, math.pi * 1.95); r_ = rng.uniform(0.6, 0.95)
            M._ellipse(img, R(cx + math.cos(a) * rx * r_, cy - ry * 0.3 + math.sin(a) * ry * r_), (1.8 * s, 1.8 * s), 0, M._fonce(col, 0.6))
    elif style == "degarni":                                               # front dégarni, couronne de cheveux et mèche rabattue
        for sg in (-1, 1):
            pts = [R(cx + sg * rx * 0.98, cy - ry * 0.45), R(cx + sg * rx * 1.04, cy - ry * 0.1), R(cx + sg * rx * 0.96, cy + ry * 0.2), R(cx + sg * rx * 0.84, cy - ry * 0.3)]
            _masse(img, pts, col, 4 * s)
        _meche(img, R(cx - rx * 0.7, cy - ry * 0.75), R(cx, cy - ry * 1.02), R(cx + rx * 0.6, cy - ry * 0.82), col, 7 * s)
    if style == "court_texture":
        for k in range(4): _meche(img, R(cx - rx * (0.6 - 0.35 * k), cy - ry * 0.95), R(cx - rx * (0.5 - 0.35 * k), cy - ry * 0.78), R(cx - rx * (0.7 - 0.35 * k), cy - ry * 0.55), fonce, 3 * s)


# ------------------------------------------------------------------ barbes
def barbe(img, t, rx, ry, s, p, style, col):
    """Barbe en masse (dessinée par-dessus le bas du visage ; la bouche est redessinée ensuite)."""
    cx, cy = t; R = _R(cx, cy, p); ep = 5 * s; fonce = M._fonce(col, 0.72)
    o = float(np.clip(p.get("bouche", 0), 0, 1))
    if style in ("barbe_courte", "barbe_pleine"):
        k = 1.06 if style == "barbe_courte" else 1.22; pic = 0.0 if style == "barbe_courte" else 0.22
        ext = []
        for j in range(19):
            a = math.pi * (0.0 + j / 18); r_ = k + (0.07 * (j % 2) if style == "barbe_pleine" else 0)
            ext.append(R(cx + math.cos(a) * rx * min(1.0, r_ * 0.95), cy + ry * 0.12 + math.sin(a) * ry * (r_ * 0.95 + pic * math.sin(a)) + o * 14 * s * math.sin(a)))
        inte = [R(cx - rx * 0.8, cy + ry * 0.3), R(cx - rx * 0.45, cy + ry * 0.46), R(cx - rx * 0.2, cy + ry * 0.38), R(cx, cy + ry * 0.36),
                R(cx + rx * 0.2, cy + ry * 0.38), R(cx + rx * 0.45, cy + ry * 0.46), R(cx + rx * 0.8, cy + ry * 0.3)]      # moustache en arc au-dessus de la bouche
        ext = [q for q in ext if q is not None]
        pts = [R(cx + rx * 0.96, cy + ry * 0.12)] + ext + [R(cx - rx * 0.96, cy + ry * 0.12)] + inte
        _masse(img, pts, col, ep)
        for j in range(7):                                                 # poils
            a = math.pi * (0.2 + 0.6 * j / 6); r0 = 0.55
            M._ligne(img, R(cx + math.cos(a) * rx * r0, cy + ry * 0.3 + math.sin(a) * ry * r0 * 0.6), R(cx + math.cos(a) * rx * (r0 + 0.2), cy + ry * 0.3 + math.sin(a) * ry * (r0 + 0.35) * 0.8), fonce, 3 * s)
    elif style == "bouc":
        pts = [R(cx - rx * 0.2, cy + ry * 0.66), R(cx + rx * 0.2, cy + ry * 0.66), R(cx + rx * 0.15, cy + ry * 0.98), R(cx, cy + ry * 1.08), R(cx - rx * 0.15, cy + ry * 0.98)]
        _masse(img, pts, col, 4 * s)
    elif style == "favoris":
        for sg in (-1, 1): _masse(img, [R(cx + sg * rx * 0.96, cy - ry * 0.3), R(cx + sg * rx * 0.97, cy + ry * 0.35), R(cx + sg * rx * 0.74, cy + ry * 0.5), R(cx + sg * rx * 0.8, cy - ry * 0.25)], col, 4 * s)


# ------------------------------------------------------------------ couvre-chefs
def chapeau(img, t, rx, ry, s, p, nom, col):
    cx, cy = t; R = _R(cx, cy, p); ep = 6 * s; fonce = M._fonce(col, 0.75); clair = M._clair(col, 0.3); el = p.get("balance", 0.0)
    if nom == "bonnet":                                                    # bonnet à revers (sans pompon), côtes du tricot
        cap = _calotte(cx, cy, rx * 1.02, ry * 1.08, R, 1.0, 0.3)
        _masse(img, cap, col, ep)
        for k in range(-4, 5): M._ligne(img, R(cx + k * rx * 0.18, cy - ry * 0.6), R(cx + k * rx * 0.15, cy - ry * (1.12 - 0.015 * k * k)), fonce, 3 * s)
        rev = [R(cx - rx * 1.06, cy - ry * 0.62), R(cx + rx * 1.06, cy - ry * 0.62), R(cx + rx * 1.04, cy - ry * 0.3), R(cx - rx * 1.04, cy - ry * 0.3)]
        _masse(img, rev, M._fonce(col, 0.88), ep)
        for k in range(-5, 6): M._ligne(img, R(cx + k * rx * 0.18, cy - ry * 0.58), R(cx + k * rx * 0.18, cy - ry * 0.34), fonce, 2.5 * s)
    elif nom in ("casquette", "bob"):
        cap = _calotte(cx, cy, rx, ry, R, 1.0, 0.32)
        _masse(img, cap, col, ep)
        if nom == "casquette":
            for k in (-1, 1): M._arc(img, R(cx + k * rx * 0.12, cy - ry * 0.32), (rx * 0.4, ry * 0.9), p["tilt"], 190, 350, fonce, 3 * s)
            vis = [R(cx - rx * 0.95, cy - ry * 0.32), R(cx + rx * 0.95, cy - ry * 0.32), R(cx + rx * 0.8, cy - ry * 0.15), R(cx, cy - ry * 0.08), R(cx - rx * 0.8, cy - ry * 0.15)]
            _masse(img, vis, fonce, ep); M._ellipse(img, R(cx, cy - ry * 0.97), (12 * s, 8 * s), 0, M.TRAIT)
            M._ellipse(img, R(cx, cy - ry * 0.62), (20 * s, 14 * s), 0, clair)
        else:
            brd = [R(cx - rx * 1.3, cy - ry * 0.18), R(cx + rx * 1.3, cy - ry * 0.18), R(cx + rx * 1.05, cy - ry * 0.4), R(cx - rx * 1.05, cy - ry * 0.4)]
            _masse(img, brd, fonce, ep)
            for k in range(4): M._arc(img, R(cx, cy - ry * 0.3), (rx * (0.95 - 0.12 * k), ry * (0.75 - 0.1 * k)), p["tilt"], 200, 340, fonce, 2.5 * s)
    elif nom == "beret":
        c0 = R(cx + rx * 0.15, cy - ry * 0.72)
        M._ellipse(img, c0, (rx * 1.12 + ep, ry * 0.42 + ep), p["tilt"] - 8, M.TRAIT); M._ellipse(img, c0, (rx * 1.12, ry * 0.42), p["tilt"] - 8, col)
        M._ligne(img, R(cx + rx * 0.1, cy - ry * 1.12), R(cx + rx * 0.12, cy - ry * 1.24), M.TRAIT, 6 * s)
    elif nom in ("chapeau", "melon"):
        haut = 0.95 if nom == "chapeau" else 0.75
        cal = [R(cx - rx * 0.78, cy - ry * 0.5), R(cx - rx * 0.72, cy - ry * (0.5 + haut)), R(cx, cy - ry * (0.42 + haut) if nom == "chapeau" else cy - ry * (0.62 + haut)),
               R(cx + rx * 0.72, cy - ry * (0.5 + haut)), R(cx + rx * 0.78, cy - ry * 0.5)]
        if nom == "melon": cal = [R(cx + rx * 0.8 * math.cos(math.pi + math.pi * j / 12), cy - ry * 0.5 + ry * haut * math.sin(math.pi + math.pi * j / 12)) for j in range(13)]
        _masse(img, cal, col, ep)
        M._poly(img, [R(cx - rx * 0.79, cy - ry * 0.68), R(cx + rx * 0.79, cy - ry * 0.68), R(cx + rx * 0.79, cy - ry * 0.52), R(cx - rx * 0.79, cy - ry * 0.52)], M._fonce(col, 0.55))
        bord = [R(cx - rx * 1.32, cy - ry * 0.42), R(cx - rx * 1.1, cy - ry * 0.56), R(cx + rx * 1.1, cy - ry * 0.56), R(cx + rx * 1.32, cy - ry * 0.42), R(cx + rx * 0.9, cy - ry * 0.4), R(cx - rx * 0.9, cy - ry * 0.4)]
        _masse(img, bord, col, ep)
    elif nom == "tricorne":                                                # tricorne bordé d'or
        pts = [R(cx - rx * 1.45, cy - ry * 0.85), R(cx - rx * 0.6, cy - ry * 0.5), R(cx + rx * 0.6, cy - ry * 0.5), R(cx + rx * 1.45, cy - ry * 0.85),
               R(cx + rx * 0.9, cy - ry * 1.05), R(cx + rx * 0.3, cy - ry * 1.45), R(cx - rx * 0.3, cy - ry * 1.45), R(cx - rx * 0.9, cy - ry * 1.05)]
        _masse(img, pts, col, ep); M._poly(img, pts[:4], (210, 170, 70), False, 6 * s)
    elif nom == "casque_chantier":
        cap = _calotte(cx, cy, rx * 1.05, ry * 1.08, R, 1.0, 0.3)
        _masse(img, cap, (250, 200, 40), ep); M._ligne(img, R(cx, cy - ry * 1.12), R(cx, cy - ry * 0.5), (220, 170, 20), 14 * s)
        _masse(img, [R(cx - rx * 1.25, cy - ry * 0.42), R(cx + rx * 1.25, cy - ry * 0.42), R(cx + rx * 1.2, cy - ry * 0.3), R(cx - rx * 1.2, cy - ry * 0.3)], (240, 190, 30), ep)
    elif nom == "toque":                                                   # toque de cuisinier
        _masse(img, [R(cx - rx * 0.8, cy - ry * 0.5), R(cx + rx * 0.8, cy - ry * 0.5), R(cx + rx * 0.82, cy - ry * 0.9), R(cx - rx * 0.82, cy - ry * 0.9)], (250, 250, 250), ep)
        for k in range(3): M._ellipse(img, R(cx + (k - 1) * rx * 0.55, cy - ry * 1.25), (rx * 0.42 + ep, ry * 0.45 + ep), 0, M.TRAIT)
        for k in range(3): M._ellipse(img, R(cx + (k - 1) * rx * 0.55, cy - ry * 1.25), (rx * 0.42, ry * 0.45), 0, (250, 250, 250))
        M._poly(img, [R(cx - rx * 0.78, cy - ry * 0.95), R(cx + rx * 0.78, cy - ry * 0.95), R(cx + rx * 0.78, cy - ry * 0.88), R(cx - rx * 0.78, cy - ry * 0.88)], (250, 250, 250))
    elif nom == "couronne":
        pts = [R(cx - rx * 0.7, cy - ry * 0.7), R(cx + rx * 0.7, cy - ry * 0.7), R(cx + rx * 0.8, cy - ry * 1.3), R(cx + rx * 0.4, cy - ry * 1.0), R(cx, cy - ry * 1.4),
               R(cx - rx * 0.4, cy - ry * 1.0), R(cx - rx * 0.8, cy - ry * 1.3)]
        _masse(img, pts, (240, 200, 60), ep)
        for k in (-1, 0, 1): M._ellipse(img, R(cx + k * rx * 0.4, cy - ry * 0.82), (9 * s, 9 * s), 0, (200, 40, 60))
    elif nom == "bandana":
        _masse(img, _calotte(cx, cy, rx, ry, R, 1.0, 0.38), col, ep)
        _masse(img, [R(cx + rx * 0.95, cy - ry * 0.45), R(cx + rx * 1.35 + el * 10 * s, cy - ry * 0.2), R(cx + rx * 1.2, cy - ry * 0.55)], col, ep)
        for j in range(8): M._ellipse(img, R(cx + rx * (0.7 - 0.2 * j), cy - ry * (0.8 - 0.05 * (j % 2))), (5 * s, 5 * s), 0, (250, 250, 250))
    elif nom == "serre_tete":
        M._arc(img, R(cx, cy - ry * 0.1), (rx * 0.98, ry * 0.95), p["tilt"], 200, 340, M.TRAIT, 16 * s); M._arc(img, R(cx, cy - ry * 0.1), (rx * 0.98, ry * 0.95), p["tilt"], 202, 338, col, 9 * s)


# ------------------------------------------------------------------ motifs de tissu
def motif(img, roi_c, ax, nom, couleur, s, masque):
    """Motifs dessinés (fleurs, palmiers, taches de fourrure…) à l'intérieur du masque du vêtement. masque : (x0, y0, m)."""
    x0, y0, m = masque; h, w = m.shape; z = img[y0:y0 + h, x0:x0 + w].copy(); rng = np.random.default_rng(int(ax[0] * 7) % 997)
    pas = max(10, int(70 * s))
    for j, y in enumerate(range(pas // 2, h, pas)):
        for x in range(pas // 2 + (pas // 2 if j % 2 else 0), w, pas):
            c = (x + rng.uniform(-8, 8) * s, y + rng.uniform(-8, 8) * s)
            if nom == "fleurs":
                for k in range(5):
                    a = 2 * math.pi * k / 5; M._ellipse(z, (c[0] + math.cos(a) * 11 * s, c[1] + math.sin(a) * 11 * s), (8 * s, 8 * s), 0, couleur)
                M._ellipse(z, c, (6 * s, 6 * s), 0, (250, 220, 90))
            elif nom == "palmiers":
                M._ligne(z, (c[0], c[1] + 24 * s), (c[0] + 4 * s, c[1] - 6 * s), couleur, 5 * s)
                for k in range(5):
                    a = math.pi * (1.1 + 0.2 * k); M._poly(z, [(c[0] + 4 * s, c[1] - 6 * s), (c[0] + 4 * s + math.cos(a) * 24 * s, c[1] - 6 * s + math.sin(a) * 14 * s + 8 * s)], couleur, False, 5 * s)
            elif nom == "taches":                                         # fourrure (léopard, peau de bête)
                M._ellipse(z, c, (rng.uniform(10, 16) * s, rng.uniform(13, 20) * s), rng.uniform(0, 180), couleur)
            elif nom == "losanges":
                M._poly(z, [(c[0], c[1] - 16 * s), (c[0] + 12 * s, c[1]), (c[0], c[1] + 16 * s), (c[0] - 12 * s, c[1])], couleur)
            elif nom == "chevrons":
                M._poly(z, [(c[0] - 18 * s, c[1] + 6 * s), (c[0], c[1] - 8 * s), (c[0] + 18 * s, c[1] + 6 * s)], couleur, False, 5 * s)
            elif nom == "etoiles":
                M._poly(z, [(c[0] + 12 * s * math.cos(math.pi / 2 + i * 4 * math.pi / 5), c[1] - 12 * s * math.sin(math.pi / 2 + i * 4 * math.pi / 5)) for i in range(5)], couleur)
    a = (m.astype(np.float32) / 255)[..., None]
    img[y0:y0 + h, x0:x0 + w] = (img[y0:y0 + h, x0:x0 + w] * (1 - a) + z * a).astype(np.uint8)


# ------------------------------------------------------------------ finitions des vêtements (adultes)
def finitions_buste(img, pts, x, cy, w, h, s, C):
    """Coutures d'épaule, ourlet, poches et ornements selon le haut."""
    haut = C.get("haut"); col = C.get("c_haut", M.BLANC); fonce = M._fonce(col, 0.72); bas_ = cy + h / 2; top = cy - h / 2
    for sg in (-1, 1):                                                     # coutures d'épaule (pointillés)
        for k in range(4): M._ligne(img, (x + sg * w * (0.55 + 0.08 * k), top + w * (0.07 + 0.05 * k)), (x + sg * w * (0.58 + 0.08 * k), top + w * (0.09 + 0.05 * k)), fonce, 2.5 * s)
    if haut not in ("robe", "tablier", "tunique"):                         # ourlet
        M._ligne(img, (x - w * 0.95, bas_ - 12 * s), (x + w * 0.95, bas_ - 12 * s), fonce, 2.5 * s)
    if haut == "col_roule":
        M._poly(img, [(x - w * 0.42, top - 18 * s), (x + w * 0.42, top - 18 * s), (x + w * 0.45, top + 16 * s), (x - w * 0.45, top + 16 * s)], col)
        M._poly(img, [(x - w * 0.42, top - 18 * s), (x + w * 0.42, top - 18 * s), (x + w * 0.45, top + 16 * s), (x - w * 0.45, top + 16 * s)], M.TRAIT, True, 4 * s)
        for k in range(3): M._ligne(img, (x - w * 0.4, top - 8 * s + k * 9 * s), (x + w * 0.4, top - 8 * s + k * 9 * s), fonce, 2.5 * s)
    elif haut == "doudoune":                                               # matelassage
        for k in range(1, 6): M._ligne(img, (x - w * 0.98, top + k * h / 6), (x + w * 0.98, top + k * h / 6), fonce, 4 * s)
        M._ligne(img, (x, top + 6 * s), (x, bas_ - 4 * s), fonce, 5 * s); M._ellipse(img, (x, top + 26 * s), (5 * s, 8 * s), 0, (210, 210, 215))
    elif haut == "blouson":                                                # blouson ouvert sur un t-shirt
        inner = C.get("c_dessous") or (245, 245, 245)
        M._poly(img, [(x - w * 0.3, top), (x + w * 0.3, top), (x + w * 0.22, bas_), (x - w * 0.22, bas_)], inner)
        for sg in (-1, 1):
            M._ligne(img, (x + sg * w * 0.28, top), (x + sg * w * 0.22, bas_), M.TRAIT, 4 * s)
            M._poly(img, [(x + sg * w * 0.5, cy + h * 0.05), (x + sg * w * 0.8, cy + h * 0.05), (x + sg * w * 0.8, cy + h * 0.25), (x + sg * w * 0.5, cy + h * 0.25)], fonce, True, 3 * s)
        M._ligne(img, (x - w * 0.95, bas_ - 18 * s), (x + w * 0.95, bas_ - 18 * s), fonce, 8 * s)
    elif haut == "redingote":                                              # habit d'époque : galons dorés, gilet, jabot
        or_ = (215, 175, 70)
        M._poly(img, [(x - w * 0.32, top), (x + w * 0.32, top), (x + w * 0.3, bas_ - h * 0.12), (x - w * 0.3, bas_ - h * 0.12)], C.get("c_dessous") or (235, 185, 80))
        for k in range(4): M._ellipse(img, (x, top + h * (0.25 + 0.15 * k)), (5 * s, 5 * s), 0, M._fonce(C.get("c_dessous") or (235, 185, 80), 0.6))
        for sg in (-1, 1):
            M._ligne(img, (x + sg * w * 0.33, top), (x + sg * w * 0.33, bas_), or_, 7 * s); M._ligne(img, (x + sg * w * 0.33, top), (x + sg * w * 0.33, bas_), M.TRAIT, 2 * s)
            for k in range(6): M._ellipse(img, (x + sg * w * 0.42, top + h * (0.1 + 0.14 * k)), (3.5 * s, 3.5 * s), 0, or_)
        M._ligne(img, (x - w * 0.95, bas_ - 6 * s), (x + w * 0.95, bas_ - 6 * s), or_, 7 * s)
        for k in range(3):                                                 # jabot de dentelle
            yy = top + 10 * s + k * 20 * s
            M._poly(img, [(x - 26 * s + k * 3 * s, yy), (x + 26 * s - k * 3 * s, yy), (x + 20 * s, yy + 22 * s), (x, yy + 28 * s), (x - 20 * s, yy + 22 * s)], (252, 252, 250))
            M._poly(img, [(x - 26 * s + k * 3 * s, yy), (x + 26 * s - k * 3 * s, yy), (x + 20 * s, yy + 22 * s), (x, yy + 28 * s), (x - 20 * s, yy + 22 * s)], M.TRAIT, True, 3 * s)
    elif haut == "uniforme":                                               # uniforme : épaulettes, poches à rabat, écusson
        for sg in (-1, 1):
            M._ligne(img, (x + sg * w * 0.5, top + 8 * s), (x + sg * w * 0.88, top + w * 0.25), fonce, 12 * s)
            M._poly(img, [(x + sg * w * 0.25, cy - h * 0.2), (x + sg * w * 0.7, cy - h * 0.2), (x + sg * w * 0.7, cy), (x + sg * w * 0.25, cy)], M.TRAIT, True, 3 * s)
            M._ligne(img, (x + sg * w * 0.25, cy - h * 0.12), (x + sg * w * 0.7, cy - h * 0.12), M.TRAIT, 3 * s)
        M._ellipse(img, (x + w * 0.48, cy - h * 0.32), (15 * s, 17 * s), 0, (240, 200, 80)); M._ellipse(img, (x + w * 0.48, cy - h * 0.32), (8 * s, 9 * s), 0, (60, 80, 150))
        for k in range(4): M._ellipse(img, (x, top + h * (0.15 + 0.2 * k)), (5 * s, 5 * s), 0, (230, 200, 90))
    elif haut == "tunique":                                                # peau de bête sur une épaule, bas en dents de scie
        rng_ = [(x - w * 1.0 + j * w * 0.2, bas_ + (14 * s if j % 2 else 0)) for j in range(11)]
        M._poly(img, [(x - w * 1.0, bas_ - 10 * s)] + rng_ + [(x + w * 1.0, bas_ - 10 * s)], col); M._poly(img, rng_, M.TRAIT, False, 4 * s)
        M._poly(img, [(x - w * 0.95, top + w * 0.25), (x - w * 0.35, top), (x - w * 0.2, top + 8 * s), (x - w * 0.9, top + w * 0.6)], M.BLANC)   # épaule nue
        M._ligne(img, (x - w * 0.2, top + 8 * s), (x + w * 0.9, bas_ - h * 0.35), M.TRAIT, 4 * s)
    elif haut == "hawai":
        for sg in (-1, 1):
            M._poly(img, [(x, top + 22 * s), (x + sg * 40 * s, top - 4 * s), (x + sg * 50 * s, top + 34 * s)], M._clair(col, 0.2)); M._poly(img, [(x, top + 22 * s), (x + sg * 40 * s, top - 4 * s), (x + sg * 50 * s, top + 34 * s)], M.TRAIT, True, 3 * s)
        M._ligne(img, (x, top + 22 * s), (x, bas_), M.TRAIT, 3 * s)
        for k in range(3): M._ellipse(img, (x + 9 * s, top + 50 * s + k * 50 * s), (4.5 * s, 4.5 * s), 0, (250, 250, 245))


def finitions_jambe(img, a, b, larg, s, bas, col, cote):
    """Pantalon détaillé : pli, poche, ourlet et revers ; jean : surpiqûres orangées."""
    fonce = M._fonce(col, 0.72); dx, dy = b[0] - a[0], b[1] - a[1]; n = math.hypot(dx, dy) or 1; ux, uy = dx / n, dy / n
    m = (a[0] + dx * 0.1, a[1] + dy * 0.1)
    M._ligne(img, m, (b[0] - ux * 14 * s, b[1] - uy * 14 * s), fonce, 2.5 * s)                    # pli du pantalon
    M._ligne(img, (b[0] - ux * 16 * s - uy * larg * 0.42, b[1] - uy * 16 * s + ux * larg * 0.42), (b[0] - ux * 16 * s + uy * larg * 0.42, b[1] - uy * 16 * s - ux * larg * 0.42), fonce, 3 * s)
    if bas == "jean":
        M._ligne(img, (a[0] + cote * larg * 0.3, a[1] + 6 * s), (a[0] + cote * larg * 0.05, a[1] + 34 * s), (230, 160, 70), 2.5 * s)


def lacets(img, c, s, C):
    if (C or {}).get("chaussures") in ("baskets", "ville"):
        for k in range(3): M._ligne(img, (c[0] - 6 * s + k * 5 * s, c[1] - 8 * s), (c[0] - 2 * s + k * 5 * s, c[1] - 3 * s), (250, 250, 250), 2.5 * s)
