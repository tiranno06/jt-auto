"""Marionnettes 2D animées pour les sketchs libres et les gags éclair (moteur « cartoon », distinct du JT).

Personnages maison : petits bonshommes blancs à grosse tête ronde, trait noir, visage minimaliste, chacun avec un signe
distinctif (bonnet, casquette, nœud, lunettes, mèche). Tout est dessiné image par image (pas d'image fixe) :
bouche synchronisée sur la voix, clignements, regard, sourcils, émotions, gestes des bras, rebonds, effets (larmes, colère…).

dessiner(img, perso, pose) dessine un personnage dans l'image (RGB uint8) selon une « pose » (dict de paramètres)."""
import math
import numpy as np, cv2

TRAIT = (26, 22, 30)
BLANC = (252, 252, 250)
AA = cv2.LINE_AA

# ------------------------------------------------------------------ distribution
PERSOS = {
    "bonnet":    dict(nom="Jojo", accessoire="bonnet", couleur=(240, 120, 40)),     # bonnet orange à pompon
    "casquette": dict(nom="Kévin", accessoire="casquette", couleur=(50, 110, 220)), # casquette bleue à l'envers
    "noeud":     dict(nom="Lila", accessoire="noeud", couleur=(240, 90, 150)),      # nœud rose
    "lunettes":  dict(nom="Dédé", accessoire="lunettes", couleur=(30, 30, 30)),     # grosses lunettes noires
    "meche":     dict(nom="Momo", accessoire="meche", couleur=(30, 30, 30)),        # mèche rebelle
}
ROLES = {"presentateur": "bonnet", "invite": "casquette", "envoyee": "noeud"}       # rôle du sketch -> personnage

def pose_neutre():
    return dict(x=540, y=1500, s=1.0, sq=0.0, tilt=0.0, regard=(0.0, 0.0), yeux="ouverts", paupiere=0.0, sourcils="neutre",
                bouche=0.0, forme="neutre", bras_g=(-18, 8), bras_d=(18, -8), effets=(), rougeur=0.0, tremble=0.0, t=0.0,
                main_g=None, main_d=None, face=0.0)

# ------------------------------------------------------------------ géométrie
def _pt(x, y): return (int(round(x * 4)), int(round(y * 4)))           # coordonnées sous-pixel (shift=2)

def _ellipse(img, c, ax, ang, couleur, ep=-1):
    cv2.ellipse(img, _pt(*c), _pt(max(1, ax[0]), max(1, ax[1])), ang, 0, 360, couleur, ep if ep < 0 else max(1, int(ep)), AA, 2)

def _ligne(img, a, b, couleur, ep):
    cv2.line(img, _pt(*a), _pt(*b), couleur, max(1, int(ep)), AA, 2)
    r = ep / 2
    if r >= 2: _ellipse(img, a, (r, r), 0, couleur); _ellipse(img, b, (r, r), 0, couleur)

def _poly(img, pts, couleur, ferme=True, ep=-1):
    p = np.array([[x * 4, y * 4] for x, y in pts], np.int32).reshape(-1, 1, 2)
    if ep < 0: cv2.fillPoly(img, [p], couleur, AA, 2)
    else: cv2.polylines(img, [p], ferme, couleur, max(1, int(ep)), AA, 2)

def _rot(px, py, cx, cy, a):
    c, s = math.cos(a), math.sin(a); dx, dy = px - cx, py - cy
    return cx + dx * c - dy * s, cy + dx * s + dy * c

def _bras(epaule, angles, L, s):
    """Bras en deux segments : angles (épaule, coude) en degrés, 0 = vers le bas, positif = vers l'extérieur droit."""
    a1, a2 = math.radians(angles[0]), math.radians(angles[0] + angles[1])
    coude = (epaule[0] + math.sin(a1) * L * s, epaule[1] + math.cos(a1) * L * s)
    main = (coude[0] + math.sin(a2) * L * 0.9 * s, coude[1] + math.cos(a2) * L * 0.9 * s)
    return coude, main

# ------------------------------------------------------------------ dessin
def dessiner(img, perso, p):
    """Dessine le personnage `perso` (clé de PERSOS ou dict) dans `img` selon la pose `p`. Renvoie la position de la tête."""
    P = PERSOS[perso] if isinstance(perso, str) else perso
    s = p["s"]; sq = p["sq"]; sx, sy = 1 - 0.55 * sq, 1 + sq
    x = p["x"] + (math.sin(p["t"] * 61) * 9 * p["tremble"] if p["tremble"] else 0)
    y = p["y"]
    ep = 8 * s                                                             # épaisseur du trait
    # proportions : grosse tête, petit corps
    pieds = y; corps_h = 150 * s * sy; corps_w = 92 * s * sx
    cy_corps = pieds - 38 * s - corps_h / 2
    R = 150 * s; tete = (x + math.sin(math.radians(p["tilt"])) * 30 * s, cy_corps - corps_h / 2 - R * 0.78 * sy)
    rx, ry = R * (1 + 0.25 * sq) * (1 - 0.1 * sq), R * (1 - 0.18 * sq)

    # ombre au sol
    _ellipse(img, (x, pieds + 4 * s), (120 * s * sx, 16 * s), 0, tuple(int(c * 0.82) for c in _fond(img, x, pieds + 4 * s)))
    # jambes
    for dx in (-34, 34):
        a = (x + dx * s * sx, cy_corps + corps_h * 0.35); b = (x + dx * 1.25 * s * sx, pieds)
        _ligne(img, a, b, TRAIT, 34 * s); _ligne(img, a, b, BLANC, 34 * s - 2 * ep)
        _ellipse(img, (b[0] + dx * 0.25 * s, b[1] - 6 * s), (24 * s, 13 * s), 0, TRAIT)
    # bras (épaules)
    ep_g = (x - corps_w * 0.82, cy_corps - corps_h * 0.22); ep_d = (x + corps_w * 0.82, cy_corps - corps_h * 0.22)
    bras = []
    for epaule, ang, signe in ((ep_g, p["bras_g"], -1), (ep_d, p["bras_d"], 1)):
        coude, main = _bras(epaule, (ang[0], ang[1]), 64, s)
        bras.append((epaule, coude, main))
    # contour d'abord (tout en noir, un peu plus gros), puis remplissage blanc : le contour des formes se fond
    for c_, ax, an in ((( x, cy_corps), (corps_w + ep, corps_h / 2 + ep), 0), (tete, (rx + ep, ry + ep), p["tilt"])):
        _ellipse(img, c_, ax, an, TRAIT)
    _ellipse(img, (x, cy_corps), (corps_w, corps_h / 2), 0, BLANC)
    _ellipse(img, tete, (rx, ry), p["tilt"], BLANC)
    if p["rougeur"] > 0:                                                   # colère : la tête rougit par le haut
        m = np.zeros(img.shape[:2], np.uint8)
        cv2.ellipse(m, _pt(*tete), _pt(rx - ep / 2, ry - ep / 2), p["tilt"], 0, 360, 255, -1, AA, 2)
        yy = np.arange(img.shape[0], dtype=np.float32)[:, None]
        g = np.clip((tete[1] - ry + 2 * ry * min(1, p["rougeur"]) - yy) / (ry * 0.9), 0, 1)        # dégradé : rouge en haut
        a = (m.astype(np.float32) / 255 * 0.6 * g)[..., None]
        img[:] = (img * (1 - a) + np.array((235, 70, 60), np.float32) * a).astype(np.uint8)
    # bras (devant le corps, avec leur propre contour)
    for e_, c_, m_ in bras:
        e2 = (e_[0] + (x - e_[0]) * 0.25, e_[1] + 6 * s)
        _ligne(img, e2, c_, TRAIT, 34 * s + 2 * ep); _ligne(img, c_, m_, TRAIT, 34 * s + 2 * ep); _ellipse(img, m_, (22 * s + ep, 22 * s + ep), 0, TRAIT)
    for e_, c_, m_ in bras:
        e2 = (e_[0] + (x - e_[0]) * 0.25, e_[1] + 6 * s)
        _ligne(img, e2, c_, BLANC, 34 * s); _ligne(img, c_, m_, BLANC, 34 * s); _ellipse(img, m_, (22 * s, 22 * s), 0, BLANC)
    # visage
    _visage(img, tete, rx, ry, s, p, P)
    _accessoire(img, tete, rx, ry, s, p, P)
    _effets(img, tete, rx, ry, s, p)
    for nom in ("main_g", "main_d"):                                       # objet tenu en main (calque RGBA)
        if p.get(nom) is not None:
            m_ = bras[0][2] if nom == "main_g" else bras[1][2]; _coller(img, p[nom], m_[0], m_[1])
    return tete, (rx, ry)

def _fond(img, x, y):
    x, y = int(np.clip(x, 0, img.shape[1] - 1)), int(np.clip(y, 0, img.shape[0] - 1)); return tuple(int(v) for v in img[y, x])

def _coller(img, rgba, cx, cy):
    h, w = rgba.shape[:2]; x0, y0 = int(cx - w / 2), int(cy - h * 0.6)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(img.shape[1], x0 + w), min(img.shape[0], y0 + h)
    if xb <= xa or yb <= ya: return
    s = rgba[ya - y0:yb - y0, xa - x0:xb - x0].astype(np.float32); a = s[..., 3:4] / 255
    img[ya:yb, xa:xb] = (img[ya:yb, xa:xb] * (1 - a) + s[..., :3] * a).astype(np.uint8)

def _visage(img, t, rx, ry, s, p, P):
    cx, cy = t; tilt = math.radians(p["tilt"]); gx, gy = p["regard"]
    def R(px, py): return _rot(px, py, cx, cy, tilt)
    ex = 52 * s; ey = cy + 4 * s; er = 15 * s
    yeux, pa = p["yeux"], p["paupiere"]
    for k, sg in enumerate((-1, 1)):
        ox, oy = R(cx + sg * ex + gx * 10 * s, ey + gy * 8 * s)
        if yeux in ("fermes",) or pa >= 0.95:
            _ligne(img, (ox - er, oy), (ox + er, oy), TRAIT, 6 * s)
        elif yeux == "heureux":                                            # ^ ^
            _poly(img, [(ox - er * 1.1, oy + 5 * s), (ox, oy - er * 0.9), (ox + er * 1.1, oy + 5 * s)], TRAIT, False, 6 * s)
        elif yeux == "plisses":                                            # > <
            _poly(img, [(ox - sg * er, oy - er * 0.8), (ox + sg * er * 0.6, oy), (ox - sg * er, oy + er * 0.8)], TRAIT, False, 6 * s)
        elif yeux == "grands":
            _ellipse(img, (ox, oy), (er * 2.0, er * 2.3), 0, TRAIT); _ellipse(img, (ox, oy), (er * 2.0 - 5 * s, er * 2.3 - 5 * s), 0, BLANC)
            _ellipse(img, (ox + gx * 6 * s, oy + gy * 6 * s), (er * 0.75, er * 0.75), 0, TRAIT)
        elif yeux == "vides":                                              # blasé : demi-paupière
            _ellipse(img, (ox, oy), (er * 1.05, er * 1.15), 0, TRAIT)
            _poly(img, [(ox - er * 1.6, oy - er * 1.7), (ox + er * 1.6, oy - er * 1.7), (ox + er * 1.6, oy - er * 0.05), (ox - er * 1.6, oy - er * 0.05)], BLANC)
            _ligne(img, (ox - er * 1.2, oy - er * 0.05), (ox + er * 1.2, oy - er * 0.05), TRAIT, 5 * s)
        else:
            _ellipse(img, (ox, oy), (er, er * 1.15 * (1 - pa)), 0, TRAIT)
        # sourcils
        so = p["sourcils"]; by = oy - 34 * s
        # côté intérieur (vers le nez) = ox - sg * … : colère = intérieur bas (en V), tristesse = intérieur haut
        if so == "colere": a, b = (ox - sg * 22 * s, by + 10 * s), (ox + sg * 20 * s, by - 10 * s)
        elif so == "triste": a, b = (ox - sg * 22 * s, by - 10 * s), (ox + sg * 20 * s, by + 8 * s)
        elif so == "hausses": a, b = (ox - 22 * s, by - 16 * s), (ox + 22 * s, by - 16 * s)
        else: a, b = None, None
        if a: _ligne(img, R(*a), R(*b), TRAIT, 7 * s)
    if p.get("joues"):
        for sg in (-1, 1): _ellipse(img, R(cx + sg * 88 * s, cy + 46 * s), (20 * s, 11 * s), 0, (245, 170, 170))
    # bouche
    mx, my = R(cx, cy + 64 * s); o = float(np.clip(p["bouche"], 0, 1)); f = p["forme"]
    if f == "cri" or (o > 0.75 and f != "sourire"):
        w, h = 34 * s * (0.8 + 0.5 * o), 30 * s * (0.6 + 1.0 * o)
        _ellipse(img, (mx, my + h * 0.3), (w, h), 0, TRAIT); _ellipse(img, (mx, my + h * 0.75), (w * 0.6, h * 0.4), 0, (220, 80, 90))
    elif o > 0.08:
        w, h = 28 * s * (0.8 + 0.4 * o), 24 * s * o + 3 * s
        if f == "sourire":
            _poly(img, [(mx - w * 1.3, my - 4 * s)] + [(mx + w * 1.3 * math.cos(math.pi * k / 10), my - 4 * s + (h + 10 * s) * math.sin(math.pi * k / 10)) for k in range(10, -1, -1)], TRAIT)
        else:
            _ellipse(img, (mx, my + h * 0.4), (w, h), 0, TRAIT)
            if h > 14 * s: _ellipse(img, (mx, my + h * 0.9), (w * 0.55, h * 0.35), 0, (220, 80, 90))
    elif f == "sourire":
        _poly(img, [(mx - 30 * s + k * 6 * s, my + 10 * s * math.sin(math.pi * k / 10)) for k in range(11)], TRAIT, False, 6 * s)
    elif f == "triste":
        _poly(img, [(mx - 24 * s + k * 4.8 * s, my + 10 * s - 10 * s * math.sin(math.pi * k / 10)) for k in range(11)], TRAIT, False, 6 * s)
    elif f == "o":
        _ellipse(img, (mx, my + 4 * s), (10 * s, 12 * s), 0, TRAIT)
    else:
        _ligne(img, (mx - 16 * s, my), (mx + 16 * s, my), TRAIT, 6 * s)

def _accessoire(img, t, rx, ry, s, p, P):
    cx, cy = t; a = P["accessoire"]; col = P["couleur"]; tilt = math.radians(p["tilt"])
    def R(px, py): return _rot(px, py, cx, cy, tilt)
    if a == "bonnet":
        top = [R(cx + rx * 0.95 * math.cos(math.pi + math.pi * k / 16), cy - ry * 0.35 + ry * 0.95 * math.sin(math.pi + math.pi * k / 16) * 0.9) for k in range(17)]
        _poly(img, top, TRAIT); _poly(img, [(u + 0, v + 0) for u, v in top], TRAIT, True, 8 * s)
        top2 = [R(cx + (rx * 0.95 - 8 * s) * math.cos(math.pi + math.pi * k / 16), cy - ry * 0.35 + (ry * 0.95 - 8 * s) * math.sin(math.pi + math.pi * k / 16) * 0.9) for k in range(17)]
        _poly(img, top2, col)
        bx0, by0 = R(cx - rx * 1.0, cy - ry * 0.42); bx1, by1 = R(cx + rx * 1.0, cy - ry * 0.42)
        _ligne(img, (bx0, by0), (bx1, by1), TRAIT, 46 * s); _ligne(img, (bx0, by0), (bx1, by1), tuple(int(c * 0.82) for c in col), 46 * s - 16 * s)
        px_, py_ = R(cx, cy - ry * 1.22); _ellipse(img, (px_, py_), (30 * s, 30 * s), 0, TRAIT); _ellipse(img, (px_, py_), (22 * s, 22 * s), 0, (250, 240, 225))
    elif a == "casquette":
        pts = [R(cx + rx * 0.98 * math.cos(math.pi + math.pi * k / 16), cy - ry * 0.25 + ry * 0.9 * math.sin(math.pi + math.pi * k / 16)) for k in range(17)]
        _poly(img, pts, TRAIT); _poly(img, [R(cx + (rx * 0.98 - 9 * s) * math.cos(math.pi + math.pi * k / 16), cy - ry * 0.25 + (ry * 0.9 - 9 * s) * math.sin(math.pi + math.pi * k / 16)) for k in range(17)], col)
        v0, v1 = R(cx - rx * 0.6, cy - ry * 0.3), R(cx - rx * 1.45, cy - ry * 0.05)               # visière vers l'arrière
        _ligne(img, v0, v1, TRAIT, 36 * s); _ligne(img, v0, v1, tuple(int(c * 0.8) for c in col), 22 * s)
        b = R(cx, cy - ry * 0.98); _ellipse(img, b, (12 * s, 9 * s), 0, TRAIT)
    elif a == "noeud":
        c0 = R(cx + rx * 0.55, cy - ry * 0.82)
        for sg in (-1, 1):
            pts = [c0, (c0[0] + sg * 62 * s, c0[1] - 40 * s), (c0[0] + sg * 62 * s, c0[1] + 40 * s)]
            _poly(img, pts, TRAIT); cxx = sum(q[0] for q in pts) / 3; cyy = sum(q[1] for q in pts) / 3
            _poly(img, [(cxx + (q[0] - cxx) * 0.72, cyy + (q[1] - cyy) * 0.72) for q in pts], col)
        _ellipse(img, c0, (17 * s, 17 * s), 0, TRAIT); _ellipse(img, c0, (11 * s, 11 * s), 0, col)
    elif a == "lunettes":
        for sg in (-1, 1):
            o = R(cx + sg * 56 * s, cy + 4 * s); _ellipse(img, o, (46 * s, 40 * s), 0, TRAIT, 11 * s)
        _ligne(img, R(cx - 12 * s, cy - 4 * s), R(cx + 12 * s, cy - 4 * s), TRAIT, 9 * s)
        for sg in (-1, 1): _ligne(img, R(cx + sg * 100 * s, cy - 2 * s), R(cx + sg * rx * 0.97, cy - 12 * s), TRAIT, 8 * s)
    elif a == "meche":
        b = R(cx + 10 * s, cy - ry * 0.97)
        for dx, h, k in ((-30, 1.42, -40), (10, 1.55, 10), (50, 1.40, 60)):          # trois épis de cheveux noirs
            pts = [R(cx + dx * s - 22 * s, cy - ry * 0.95), R(cx + (dx + k) * s, cy - ry * h), R(cx + dx * s + 22 * s, cy - ry * 0.95)]
            _poly(img, pts, TRAIT)

def objet(nom, s=1.0):
    """Petit accessoire dessiné (calque RGBA) à tenir en main : telephone, billet, portefeuille, micro, verre, cafe."""
    w, h = int(140 * s), int(170 * s); im = np.zeros((h, w, 4), np.uint8)
    def r(x0, y0, x1, y1, c, rad=8):
        cv2.rectangle(im, (int(x0), int(y0)), (int(x1), int(y1)), c + (255,), -1, AA)
    k = s
    if nom == "telephone":
        r(30*k, 10*k, 110*k, 160*k, TRAIT); r(38*k, 20*k, 102*k, 140*k, (120, 200, 250))
    elif nom == "billet":
        r(5*k, 50*k, 135*k, 120*k, TRAIT); r(11*k, 56*k, 129*k, 114*k, (150, 210, 140)); cv2.circle(im, (int(70*k), int(85*k)), int(16*k), (90, 160, 90, 255), -1, AA)
    elif nom == "portefeuille":
        r(15*k, 50*k, 125*k, 140*k, TRAIT); r(21*k, 56*k, 119*k, 134*k, (150, 95, 60)); r(80*k, 80*k, 125*k, 110*k, TRAIT)
    elif nom == "micro":
        r(60*k, 70*k, 80*k, 165*k, TRAIT); cv2.circle(im, (int(70*k), int(55*k)), int(30*k), TRAIT + (255,), -1, AA); cv2.circle(im, (int(70*k), int(55*k)), int(24*k), (150, 150, 160, 255), -1, AA)
    elif nom == "verre":
        r(40*k, 40*k, 100*k, 160*k, TRAIT); r(46*k, 60*k, 94*k, 154*k, (245, 190, 60)); r(46*k, 46*k, 94*k, 64*k, (250, 250, 245))
    elif nom == "cafe":
        r(40*k, 70*k, 100*k, 160*k, TRAIT); r(46*k, 76*k, 94*k, 154*k, (250, 250, 245)); cv2.circle(im, (int(108*k), int(110*k)), int(16*k), TRAIT + (255,), int(7*k), AA)
    else:
        return None
    return im

def _effets(img, t, rx, ry, s, p):
    cx, cy = t; tm = p["t"]
    for e in p["effets"]:
        if e == "larmes":                                                  # cascades de larmes
            for sg in (-1, 1):
                x0 = cx + sg * 52 * s
                for k in range(4):
                    ph = (tm * 2.2 + k / 4) % 1; yy = cy + 30 * s + ph * 140 * s
                    _ellipse(img, (x0 + sg * ph * 30 * s, yy), (9 * s, 13 * s), 0, (90, 170, 245))
        elif e == "larme":
            _ellipse(img, (cx + 70 * s, cy + 40 * s + (tm * 60 % 60) * s), (10 * s, 15 * s), 0, (90, 170, 245))
        elif e == "sueur":
            _ellipse(img, (cx + rx * 0.85, cy - ry * 0.35 + (tm * 40 % 30) * s), (11 * s, 17 * s), 0, (120, 200, 250))
        elif e == "veine":                                                 # veine de colère ╬
            v = (cx + rx * 0.55, cy - ry * 0.55); k = 14 * s
            for a, b in (((-k, -k * 0.4), (-k * 0.4, -k)), ((k * 0.4, -k), (k, -k * 0.4)), ((-k, k * 0.4), (-k * 0.4, k)), ((k * 0.4, k), (k, k * 0.4))):
                _ligne(img, (v[0] + a[0], v[1] + a[1]), (v[0] + b[0], v[1] + b[1]), (220, 40, 40), 7 * s)
        elif e == "etoiles":
            for k in range(3):
                a = tm * 4 + k * 2.09; px_, py_ = cx + math.cos(a) * rx * 0.9, cy - ry * 1.1 + math.sin(a) * 20 * s
                _poly(img, [(px_ + 18 * s * math.cos(math.pi / 2 + j * 4 * math.pi / 5), py_ - 18 * s * math.sin(math.pi / 2 + j * 4 * math.pi / 5)) for j in range(5)], (250, 200, 40))
        elif e == "traits":                                                # traits d'énervement / de choc autour de la tête
            for k in range(5):
                a = -math.pi * 0.85 + k * math.pi * 0.17; r0, r1 = rx * 1.15, rx * 1.38
                _ligne(img, (cx + math.cos(a) * r0, cy + math.sin(a) * r0), (cx + math.cos(a) * r1, cy + math.sin(a) * r1), TRAIT, 6 * s)
