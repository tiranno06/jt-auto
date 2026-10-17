"""Nouveau style de personnage (« toon trois-quarts ») : le rendu des chaînes d'animation TikTok à la sauce @petitsdramas.

Tête en œuf blanche ombrée (dégradé doux du côté opposé à la lumière), visage de TROIS-QUARTS (les deux yeux du même côté,
bouche de profil qui dépasse du contour), grands yeux blancs à pupille noire, sourcils épais ; buste tourné, vêtements modelés
(capuche, cordons, poche, bord-côtes, plis, ombre en aplat), bras en manches qui passent devant ou derrière le corps (bras
croisés, mains sur les hanches…), jambes et pieds en perspective. Trait noir épais et net.

Le squelette est celui de marionnette.py (mêmes repères : tête, épaules, coudes, mains, pieds) : cadrages, gestes, objets
tenus et caméras du moteur fonctionnent sans changement. Seul le DESSIN change. Gratuit, sans 3D."""
import math
import numpy as np, cv2
import marionnette as M
import garde_robe as GR

TRAIT = M.TRAIT
BLANC = (252, 252, 252)
_ellipse, _ligne, _poly, _tube, _arc = M._ellipse, M._ligne, M._poly, M._tube, M._arc
_fonce, _clair = M._fonce, M._clair


# ------------------------------------------------------------------ géométrie
def lisse(pts, ferme=True, n=6):
    """Courbe lisse (Catmull-Rom) passant par les points."""
    P = list(pts); m = len(P)
    if m < 3: return P
    out = []
    rng = range(m) if ferme else range(m - 1)
    for i in rng:
        p0 = P[(i - 1) % m] if ferme else P[max(0, i - 1)]; p1 = P[i]; p2 = P[(i + 1) % m] if ferme else P[i + 1]
        p3 = P[(i + 2) % m] if ferme else P[min(m - 1, i + 2)]
        for k in range(n):
            t = k / n; t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    if not ferme: out.append(P[-1])
    return out


def oeuf(cx, cy, rx, ry, ang, n=72, d=0):
    """Contour d'une tête en œuf : un peu plus large en haut, plus fine vers le menton, inclinée de `ang` degrés."""
    a = math.radians(ang); out = []
    for k in range(n):
        t = 2 * math.pi * k / n; cx_, sy = math.cos(t), math.sin(t)
        kx = 1.0 - 0.04 * max(0.0, sy) + 0.02 * max(0.0, -sy)                  # tête large jusqu'en bas (référence), côtés un peu plats
        if d and cx_ * d > 0: kx += 0.07 * max(0.0, sy)                        # trois-quarts : mâchoire un peu en avant, côté visage
        e = 2.35; x = rx * kx * math.copysign(abs(cx_) ** (2 / e), cx_); y = ry * math.copysign(abs(sy) ** (2 / e), sy)
        out.append((cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)))
    return out


def _bbox(pts, img, marge=6):
    a = np.array(pts, np.float32)
    x0, y0 = np.floor(a.min(0)).astype(int) - marge; x1, y1 = np.ceil(a.max(0)).astype(int) + marge
    return max(0, x0), max(0, y0), min(img.shape[1], x1), min(img.shape[0], y1)


def _masque(pts, roi):
    x0, y0, x1, y1 = roi; m = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.fillPoly(m, [((np.array(pts, np.float32) - [x0, y0]) * 4).astype(np.int32)], 255, cv2.LINE_AA, 2)
    return m


def ombre_cel(img, pts, cote, larg, coul):
    """Ombre en aplat (cel) : bande le long du bord de la forme, du côté opposé à la lumière, qui suit sa silhouette."""
    roi = _bbox(pts, img)
    if roi[2] <= roi[0] or roi[3] <= roi[1]: return
    m = _masque(pts, roi) > 127; d = int(max(2, larg))
    dec = np.zeros_like(m)
    if cote > 0: dec[:, :-d] = m[:, d:]
    else: dec[:, d:] = m[:, :-d]
    bande = m & ~dec
    if bande.any():
        z = img[roi[1]:roi[3], roi[0]:roi[2]]; z[bande] = coul


def degrade(img, pts, centre, rayon, coul, force=0.6, debut=0.45):
    """Volume doux : la forme s'assombrit en s'éloignant du point de lumière."""
    roi = _bbox(pts, img)
    if roi[2] <= roi[0] or roi[3] <= roi[1]: return
    m = _masque(pts, roi).astype(np.float32) / 255
    yy, xx = np.mgrid[roi[1]:roi[3], roi[0]:roi[2]].astype(np.float32)
    dist = np.sqrt((xx - centre[0]) ** 2 + (yy - centre[1]) ** 2) / max(1.0, rayon)
    a = (np.clip((dist - debut) / (1.15 - debut), 0, 1) ** 1.5 * force * m)[..., None]
    z = img[roi[1]:roi[3], roi[0]:roi[2]].astype(np.float32)
    img[roi[1]:roi[3], roi[0]:roi[2]] = (z * (1 - a) + np.array(coul, np.float32) * a).astype(np.uint8)


def forme(img, pts, coul, ep):
    """Forme pleine avec son trait noir (le trait est posé APRÈS le remplissage)."""
    _poly(img, pts, coul); _poly(img, pts, TRAIT, True, ep)


def motif(img, pts, nom, coul, s):
    """Motif du tissu (rayures, carreaux, pois, fleurs) découpé dans la forme."""
    if not nom or nom == "uni": return
    roi = _bbox(pts, img)
    if roi[2] <= roi[0] or roi[3] <= roi[1]: return
    m = _masque(pts, roi) > 127; x0, y0, x1, y1 = roi
    calque = img[y0:y1, x0:x1].copy(); h, w = m.shape; pas = max(8, int(30 * s))
    if nom in ("rayures", "carreaux"):
        for y in range(0, h, pas): cv2.line(calque, (0, y), (w, y), coul, max(2, int(9 * s)), cv2.LINE_AA)
    if nom == "carreaux":
        for x in range(0, w, pas): cv2.line(calque, (x, 0), (x, h), coul, max(2, int(9 * s)), cv2.LINE_AA)
    if nom in ("pois", "fleurs", "taches"):
        for y in range(pas // 2, h, pas):
            for x in range((y // pas % 2) * pas // 2, w, pas): cv2.circle(calque, (x, y), max(2, int((7 if nom == "pois" else 9) * s)), coul, -1, cv2.LINE_AA)
    z = img[y0:y1, x0:x1]; z[m] = calque[m]



# ------------------------------------------------------------------ proportions (d'après l'image de référence)
# Unité : R = demi-hauteur de la tête. Hauteur totale ≈ 8 R : tête 2 R, sweat 2,4 R, short jusqu'à 5,3 R, pieds à 7 R du centre de la tête.
COU, EPAULE, OURLET, HANCHE = 0.92, 1.30, 3.25, 3.0
LARG_EP, LARG_B = 0.86, 0.80                                              # demi-largeur aux épaules / au corps
BRAS1, BRAS2, MANCHE = 1.22, 1.10, 0.50                                   # bras, avant-bras, diamètre de la manche
CUISSE, GENOU, CHEVILLE = 0.58, 0.52, 0.40                                # diamètres de la jambe
OEUF_X = 0.86                                                              # tête en œuf : largeur / hauteur


# positions dessinées (unités R) : (coude, main) par bras, chacun (u, v, repère) ; repère "corps" : u vers l'extérieur du bras depuis
# le milieu du buste, v sous la ligne des épaules ; repère "tete" : u vers où il regarde depuis le centre de la tête, v vers le bas
CIBLES = {
    "croises": (((LARG_EP + 0.10, 0.82, "corps"), (-0.88, 0.62, "corps")), ((LARG_EP + 0.10, 0.82, "corps"), (-0.88, 0.80, "corps"))),
    "mains_hanches": (((LARG_EP + 0.50, 0.78, "corps"), (LARG_B + 0.02, 1.42, "corps")), ((LARG_EP + 0.50, 0.78, "corps"), (LARG_B + 0.02, 1.42, "corps"))),
    "facepalm": (None, ((LARG_EP + 0.1, 1.15, "corps"), (0.25, 0.30, "tete"))),
    "menton": (((LARG_EP + 0.05, 1.0, "corps"), (-0.62, 1.12, "corps")), ((LARG_EP - 0.05, 1.2, "corps"), (0.45, 0.95, "tete"))),
    "telephone": (None, ((LARG_EP + 0.25, 0.95, "corps"), (-0.55, 0.15, "tete"))),
    "supplie": (((LARG_EP + 0.1, 1.05, "corps"), (0.05, 0.85, "corps")), ((LARG_EP + 0.1, 1.05, "corps"), (0.05, 0.85, "corps"))),
}


def studio_pose(nom):
    try:
        import studio
        return studio.POSES.get(nom)
    except Exception:
        return None


def squelette(p):
    """Squelette du style toon : même tête et mêmes pieds que marionnette.squelette (cadrages inchangés), corps redessiné
    aux proportions de la référence ; mains recalculées (objets tenus, gestes)."""
    K = dict(M.squelette(p)); R = K["ry"]; tx, ty = K["tete"]; x = K["x"] + K["penche"] * 0.12 * R
    ep_y = ty + EPAULE * R - K["epaules"] * 0.15 * R
    bras = []
    for sg, ang in ((-1, p["bras_g"]), (1, p["bras_d"])):
        e = (x + sg * (LARG_EP - 0.22) * R, ep_y)
        a1, a2 = math.radians(ang[0]), math.radians(ang[0] + ang[1]); et = 1 + 0.14 * max(0.0, min(1.0, float(p.get("etire", 0.0))))
        c = (e[0] + math.sin(a1) * BRAS1 * R * et, e[1] + math.cos(a1) * BRAS1 * R * et)
        m = (c[0] + math.sin(a2) * BRAS2 * R * et, c[1] + math.cos(a2) * BRAS2 * R * et)
        bras.append((e, c, m))
    # gestes « naturels » copiés sur les vidéos de référence : quand la pose demandée est proche d'un geste connu,
    # le coude et la main glissent (en douceur) vers la position dessinée par l'animateur (coudes dehors, mains posées…)
    d = 1 if float(p.get("tq", 0.0)) > 0 else (-1 if float(p.get("tq", 0.0)) < 0 else 1)
    out = []; croise = 0.0
    for i, (sg, ang) in enumerate(((-1, p["bras_g"]), (1, p["bras_d"]))):
        e, c, m = bras[i]; best, w = None, 0.0
        for nom, cible in CIBLES.items():
            a_ = studio_pose(nom)
            if a_ is None: continue
            dist = abs(ang[0] - a_[i][0]) + abs(ang[1] - a_[i][1])
            w_ = max(0.0, 1.0 - dist / 50.0)
            if w_ > w: best, w, nom_b = cible, w_, nom
        if best is not None and best[i] is not None:
            (cx_, cy_, rel_c), (mx_, my_, rel_m) = best[i]
            def pt(u, v, rel): return ((tx + d * u * R, ty + v * R) if rel == "tete" else (x + sg * u * R, ep_y + v * R))
            c2, m2 = pt(cx_, cy_, rel_c), pt(mx_, my_, rel_m)
            w = w * w * (3 - 2 * w)
            if nom_b == "croises": croise = max(croise, w)
            c = (c[0] + (c2[0] - c[0]) * w, c[1] + (c2[1] - c[1]) * w); m = (m[0] + (m2[0] - m[0]) * w, m[1] + (m2[1] - m[1]) * w)
        out.append((e, c, m))
    bras = out; K["croise"] = croise
    K.update(bras=bras, x=x, cy_corps=ty + (COU + OURLET) / 2 * R, corps_h=(OURLET - COU) * R, corps_w=LARG_B * R, r_m=0.22 * R, membre=MANCHE * R)
    return K


# ------------------------------------------------------------------ visage
def _oeil(img, c, ex, ey, p, d, ep):
    """Œil de la référence : ovale vertical blanc bleuté cerclé de noir, pupille noire allongée collée du côté où il regarde."""
    yeux = p.get("yeux", "ouverts"); pa = float(p.get("paupiere", 0.0)); gx, gy = p.get("regard", (0.0, 0.0))
    if yeux == "grands": ex, ey = ex * 1.2, ey * 1.15
    if yeux == "fermes" or pa >= 0.95:
        _arc(img, (c[0], c[1] + ey * 0.15), (ex * 1.05, ey * 0.45), 0, 15, 165, TRAIT, ep * 1.1); return
    if yeux == "heureux":
        _arc(img, (c[0], c[1] + ey * 0.45), (ex * 1.05, ey * 0.8), 0, 200, 340, TRAIT, ep * 1.2); return
    _ellipse(img, c, (ex + ep * 0.5, ey + ep * 0.5), 0, TRAIT); _ellipse(img, c, (ex - ep * 0.5, ey - ep * 0.5), 0, (238, 238, 250))
    k = {"grands": 0.26, "minuscules": 0.2}.get(yeux, 0.36) * float(np.clip(p.get("pupille", 1.0), 0.6, 1.5))
    px = c[0] + float(np.clip(0.30 * d + 0.45 * gx, -0.6, 0.6)) * (ex - k * ex); py = c[1] + float(np.clip(0.05 + 0.4 * gy, -0.5, 0.5)) * (ey - k * ex * 1.2)
    if yeux == "roule": py = c[1] - ey * 0.45
    if yeux == "coeur":
        for sg in (-1, 1): _ellipse(img, (px + sg * ex * 0.25, py - ey * 0.1), (ex * 0.32, ey * 0.24), 0, (220, 40, 70))
        _poly(img, [(px - ex * 0.55, py - ey * 0.02), (px + ex * 0.55, py - ey * 0.02), (px, py + ey * 0.45)], (220, 40, 70))
    else:
        _ellipse(img, (px, py), (ex * k, ex * k * 1.2), 0, TRAIT)
        _ellipse(img, (px - ex * k * 0.3, py - ex * k * 0.45), (ex * k * 0.28, ex * k * 0.28), 0, (250, 250, 250))
    if yeux == "grands" or p.get("cernes"):                                # choc : petits arcs sous les yeux (référence)
        _arc(img, (c[0], c[1] + ey * 0.95), (ex * 0.75, ey * 0.3), 0, 20, 160, TRAIT, ep * 0.8)
    paup = {"vides": 0.42, "plisses": 0.5}.get(yeux, 0.0) + (0.12 if p.get("plisse") else 0.0) + pa * 0.8
    if paup > 0.05:                                                        # paupière (couleur de peau) qui descend
        hy = c[1] - ey + 2 * ey * min(1.0, paup); roi = M._roi(img, c[0], c[1], ex + ep, ey + ep)
        if roi:
            x0, y0, x1, y1 = roi; mm = M._masque_ellipse(roi, c, (ex - ep * 0.5, ey - ep * 0.5), 0) > 128
            yy = np.arange(y0, y1)[:, None]; img[y0:y1, x0:x1][mm & (yy < hy)] = tuple(p.get("peau") or BLANC)
        _ligne(img, (c[0] - ex * 0.95, hy), (c[0] + ex * 0.95, hy), TRAIT, ep)


def _sourcil(img, c, ex, ey, p, sg, d, ep):
    """Sourcil court et épais (référence) ; sg : -1 sourcil gauche, +1 droit (pour l'inclinaison de la colère)."""
    so = p.get("sourcils", "neutre"); by = c[1] - ey * 1.45 - float(p.get("sourcils_h", 0.0)) * ey * 0.4
    if p.get("sourcil_leve") and sg * d > 0: by -= float(p["sourcil_leve"]) * ey * 0.5
    k = ey * 0.35; a_, b_ = (c[0] - ex * 0.85, by + k * 0.15), (c[0] + ex * 0.85, by + k * 0.15)
    if so == "colere": a_, b_ = (c[0] - sg * ex * 1.05, by - k * 0.6), (c[0] + sg * ex * 0.85, by + k * 0.9)
    elif so == "triste": a_, b_ = (c[0] - sg * ex * 1.05, by + k * 0.6), (c[0] + sg * ex * 0.85, by - k * 0.7)
    elif so == "hausses": a_, b_ = (c[0] - ex, by - k * 0.9), (c[0] + ex, by - k * 0.9)
    elif so == "fronces": a_, b_ = (c[0] - sg * ex * 1.05, by - k * 0.2), (c[0] + sg * ex * 0.85, by + k * 0.6)
    elif so == "sceptique" and sg * d > 0: a_, b_ = (c[0] - ex, by - k * 1.1), (c[0] + ex, by - k * 0.6)
    mil = ((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2 - k * 0.45)
    pts = lisse([a_, mil, b_], ferme=False, n=6)
    for i in range(len(pts) - 1): _ligne(img, pts[i], pts[i + 1], TRAIT, ep * 1.15)


def _bouche(img, cx, cy, rxe, R, d, k34, p, ep, tilt):
    """Bouche des vidéos de référence : fermée, petite moue en arc vers le bas du visage, côté où il regarde ; ouverte (il parle),
    grande bouche près du bord, dents du haut (et du bas) en grille, langue rose ; suit les sons (visèmes)."""
    o = float(np.clip(p.get("bouche", 0.0), 0, 1)); f = p.get("forme", "neutre"); v = p.get("viseme")
    def T(u, w): return M._rot(cx + u, cy + w, cx, cy, tilt)
    mx = d * rxe * 0.58 * k34; my = R * 0.55; w = rxe * (0.24 - 0.06 * k34)
    if v == "M" or (o < 0.08 and f not in ("o", "cri", "grand_sourire", "dents")):
        courbe = {"sourire": 0.55, "grand_sourire": 0.7, "coin": 0.3, "triste": -0.6, "moue": -0.45, "tordue": 0.1}.get(f, -0.35)
        courbe += float(np.clip(p.get("coins", 0.0), -1, 1)) * 0.5
        w_ = w * (0.75 if courbe < 0 else 1.0)
        pts = [T(mx - w_, my + 0.02 * R - courbe * R * 0.06), T(mx, my + courbe * R * 0.05 - 0.01 * R), T(mx + w_, my + 0.02 * R - courbe * R * 0.06 + (0.03 * R if f == "tordue" else 0))]
        _trait(img, pts, ep * (1.7 if p.get("rouge") else 1.15), tuple(p["rouge"]) if p.get("rouge") else TRAIT)
        if p.get("rouge"): _trait(img, pts, ep * 0.6)
        if courbe < 0: _trait(img, [T(mx - w_ * 0.25, my + R * 0.13), T(mx + w_ * 0.1, my + R * 0.16), T(mx + w_ * 0.35, my + R * 0.13)], ep * 0.7)   # petit pli du menton
        return
    if v in ("O", "U", "CH") or f == "o":                                  # lèvres en avant (« o », « ou ») : petite bouche ronde
        rr = R * (0.07 + 0.08 * o); c_ = T(mx + d * rxe * 0.05 * k34, my)
        _ellipse(img, c_, (rr * 0.85 + ep, rr + ep), 0, tuple(p["rouge"]) if p.get("rouge") else TRAIT); _ellipse(img, c_, (rr * 0.85 - ep * 0.4, rr - ep * 0.4), 0, (60, 22, 34))
        if rr > R * 0.1: _ellipse(img, (c_[0], c_[1] + rr * 0.45), (rr * 0.45, rr * 0.25), 0, (220, 85, 100))
        return
    h = R * (0.10 + 0.30 * o) * {"I": 0.55, "E": 0.7, "A": 1.15, "S": 0.45, "T": 0.6, "F": 0.45}.get(v, 1.0)
    w2 = w * (1.35 + 0.25 * o) * (1.15 if v in ("I", "E", "S") else 1.0)
    if f == "cri": h = R * (0.28 + 0.2 * o); w2 *= 1.1
    sour = 0.4 if f in ("sourire", "grand_sourire", "dents") else (-0.2 if f == "triste" else 0.0)
    m0 = mx + d * w * 0.25 * k34                                           # la bouche ouverte glisse vers le bord du visage
    out = lisse([T(m0 - w2, my - h * 0.18 - sour * h * 0.3), T(m0 - w2 * 0.3, my - h * 0.36), T(m0 + w2 * 0.5, my - h * 0.34), T(m0 + w2, my - h * 0.2 - sour * h * 0.3),
                 T(m0 + w2 * 0.8, my + h * 0.42), T(m0 + w2 * 0.1, my + h * 0.68), T(m0 - w2 * 0.7, my + h * 0.45)], n=6)
    _poly(img, out, (60, 22, 34))
    roi = _bbox(out, img); m = _masque(out, roi) > 127; z = img[roi[1]:roi[3], roi[0]:roi[2]]
    yy = np.arange(roi[1], roi[3])[:, None] - (cy + my)
    if h > R * 0.08:                                                       # dents du haut et du bas, en grille (référence)
        dh = (yy < -h * 0.36 + h * 0.34) & m; z[dh] = (250, 250, 250)
        if h > R * 0.16: db = (yy > h * 0.36) & (yy < h * 0.62) & m & (np.arange(roi[0], roi[2])[None, :] < (cx + m0 + w2 * 0.55)); z[db] = (238, 238, 240)
        n_ = 5 if w2 > R * 0.2 else 4
        for k in range(1, n_):
            xk = cx + m0 - w2 + 2 * w2 * k / n_
            _ligne(img, (xk, cy + my - h * 0.36), (xk, cy + my - h * 0.36 + h * 0.34), TRAIT, ep * 0.5)
        _ligne(img, T(m0 - w2 * 0.9, my - h * 0.02), T(m0 + w2 * 0.9, my - h * 0.02), TRAIT, ep * 0.45)
    if h > R * 0.15: _ellipse(img, T(m0 + d * w2 * 0.05, my + h * 0.38), (w2 * 0.5, h * 0.18), 0, (220, 85, 100))   # langue
    if p.get("rouge"): _poly(img, out, tuple(p["rouge"]), True, ep * 1.5)
    _poly(img, out, TRAIT, True, ep)


def visage(img, t, rxe, R, p, d, k34, tilt_deg, ep):
    """Visage de la référence : de face (k34 ≈ 0) ou de trois-quarts vers d (+1 droite / -1 gauche)."""
    cx, cy = t; tilt = math.radians(tilt_deg)
    def T(u, w): return M._rot(cx + u, cy + w, cx, cy, tilt)
    ex, ey = R * 0.115 * float(p.get("yeux_k", 1.0)), R * 0.175 * float(p.get("yeux_k", 1.0))
    if k34 < 0.15: cs = [(-rxe * 0.36, 1.0), (rxe * 0.36, 1.0)]
    else:                                                                   # œil lointain près du bord (un peu plus petit), œil proche vers le milieu
        cs = [(d * rxe * (0.40 + 0.30 * k34), 0.92), (d * rxe * (0.40 + 0.30 * k34) - d * rxe * (0.80 - 0.32 * k34), 1.05)]
    centres = []
    for (u, k) in cs:
        c = T(u, R * 0.05); centres.append((c, ex * k, ey)); _oeil(img, c, ex * k, ey * (0.96 + 0.04 * k), p, d if k34 >= 0.15 else (1 if (p.get("regard") or (0, 0))[0] > 0.2 else (-1 if (p.get("regard") or (0, 0))[0] < -0.2 else 0)), ep)
        _sourcil(img, c, ex * k, ey, p, 1 if u > 0 else -1, d, ep)
    lun = p.get("_lunettes")
    if lun:                                                                # lunettes posées sur les yeux (de vue : cercles ; de soleil : verres noirs)
        for c, ex_, ey_ in centres:
            if lun == "soleil":
                verre = lisse([(c[0] - ex_ * 1.55, c[1] - ey_ * 0.75), (c[0] + ex_ * 1.55, c[1] - ey_ * 0.85), (c[0] + ex_ * 1.3, c[1] + ey_ * 0.75), (c[0] - ex_ * 1.25, c[1] + ey_ * 0.8)])
                forme(img, verre, (22, 22, 26), ep * 1.2)
                _ligne(img, (c[0] - ex_ * 0.9, c[1] - ey_ * 0.35), (c[0] - ex_ * 0.3, c[1] - ey_ * 0.55), (120, 120, 130), ep * 1.2)
            else: _ellipse(img, c, (ex_ * 1.5, ey_ * 1.18), 0, TRAIT, ep * 1.3)
        (c1, e1, _), (c2, e2, _) = centres
        _ligne(img, (c1[0] - (1 if c1[0] > c2[0] else -1) * e1 * 1.45, c1[1]), (c2[0] + (1 if c1[0] > c2[0] else -1) * e2 * 1.45, c2[1]), TRAIT, ep * 1.3)
        if k34 >= 0.15:                                                    # branche vers l'oreille (côté du dos)
            cp = c2; _ligne(img, (cp[0] - d * centres[1][1] * 1.5, cp[1] - ey * 0.2), (cx - d * rxe * 0.85, cy - R * 0.02), TRAIT, ep * 1.2)
    _bouche(img, cx, cy, rxe, R, d, k34, p, ep, tilt)
    if p.get("rougeur"):
        _ellipse(img, T(d * rxe * 0.15 * k34, R * 0.38), (rxe * 0.2, R * 0.07), 0, (245, 175, 180))


BARBES_T = ("barbe", "barbe_courte", "barbe_pleine", "bouc", "moustache", "favoris", "collier_barbe")


def barbe(img, ov, t, rxe, R, d, k34, det, cb, tilt):
    """Barbe mal rasée : ombre légère et grain sur la mâchoire, bouc et moustache autour de la bouche."""
    roi = _bbox(ov, img)
    if roi[2] <= roi[0] or roi[3] <= roi[1]: return
    x0, y0, x1, y1 = roi; m = _masque(ov, roi).astype(np.float32) / 255
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    u = (xx - t[0]) / rxe; v = (yy - t[1]) / R
    cote = np.clip((u * d + 0.45) / 0.4, 0, 1) if k34 >= 0.15 else 1.0
    zone = np.clip((v - 0.30) / 0.25, 0, 1) * cote
    if "bouc" in det and not any(b in det for b in ("barbe", "barbe_courte", "barbe_pleine")):
        zone = zone * np.clip(1.0 - np.abs(u - d * 0.55 * k34) / 0.35, 0, 1)
    if any(b in det for b in ("barbe", "barbe_courte", "barbe_pleine", "collier_barbe", "favoris", "bouc")):
        rng = np.random.default_rng(5); grain = (rng.random(m.shape) < 0.10).astype(np.float32)
        a = (zone * m * (0.14 + 0.30 * grain))[..., None]
        z = img[y0:y1, x0:x1].astype(np.float32); img[y0:y1, x0:x1] = (z * (1 - a) + np.array(cb, np.float32) * a).astype(np.uint8)
    def T(u_, w_): return M._rot(t[0] + u_, t[1] + w_, t[0], t[1], math.radians(tilt))
    mx = d * rxe * 0.50 * k34; w = rxe * (0.34 - 0.10 * k34)
    if "moustache" in det:
        _poly(img, lisse([T(mx - w * 1.05, R * 0.47), T(mx, R * 0.36), T(mx + w * 1.0, R * 0.47), T(mx, R * 0.44)]), tuple(cb))
    # bouc : petite ombre de poils sur le menton seulement (jamais de tache)


# ------------------------------------------------------------------ corps
def _main(img, m, a, forme_, r, peau, ep):
    M._main(img, m, a, forme_, r, TRAIT, ep * 0.9); M._main(img, m, a, forme_, r, peau)


def _trait(img, pts, ep, coul=TRAIT, ferme=False):
    pts = lisse(pts, ferme=ferme, n=6)
    for i in range(len(pts) - 1): _ligne(img, pts[i], pts[i + 1], coul, ep)


def _manche(img, e, c, m, larg, coul, courte, peau, ep, forme_main, r_m, R):
    """Bras en manche épaisse (sweat), plis au coude, bord-côte au poignet, main blanche à 4 doigts."""
    if courte:
        mi = (e[0] + (c[0] - e[0]) * 0.6, e[1] + (c[1] - e[1]) * 0.6)
        _tube(img, e, c, larg * 0.72 + 2 * ep, larg * 0.62 + 2 * ep, TRAIT); _tube(img, c, m, larg * 0.62 + 2 * ep, larg * 0.5 + 2 * ep, TRAIT)
        _tube(img, e, c, larg * 0.72, larg * 0.62, peau); _tube(img, c, m, larg * 0.62, larg * 0.5, peau)
        _tube(img, e, mi, larg + 2 * ep, larg * 0.95 + 2 * ep, TRAIT); _tube(img, e, mi, larg, larg * 0.95, coul)
    else:
        _tube(img, e, c, larg + 2 * ep, larg * 0.95 + 2 * ep, TRAIT); _tube(img, c, m, larg * 0.95 + 2 * ep, larg * 0.82 + 2 * ep, TRAIT)
        _tube(img, e, c, larg, larg * 0.95, coul); _tube(img, c, m, larg * 0.95, larg * 0.82, coul)
        for q0, q1, l0 in ((e, c, larg), (c, m, larg * 0.9)):            # ombre douce le long du dessous de la manche
            dx_, dy_ = q1[0] - q0[0], q1[1] - q0[1]; n_ = math.hypot(dx_, dy_) or 1; ox, oy = -dy_ / n_ * l0 * 0.28, dx_ / n_ * l0 * 0.28
            if oy < 0: ox, oy = -ox, -oy
            _tube(img, (q0[0] + ox, q0[1] + oy), (q1[0] + ox, q1[1] + oy), l0 * 0.32, l0 * 0.3, _fonce(coul, 0.88))
        dx, dy = m[0] - c[0], m[1] - c[1]; n = math.hypot(dx, dy) or 1; ux, uy = dx / n, dy / n; nx, ny = -uy, ux
        for k in (-0.25, 0.2):                                             # plis du coude
            a_ = (c[0] + nx * larg * k * 1.4, c[1] + ny * larg * k * 1.4)
            _trait(img, [a_, (a_[0] + ux * larg * 0.35 + nx * larg * 0.08, a_[1] + uy * larg * 0.35 + ny * larg * 0.08)], ep * 0.7)
        pg = (m[0] - ux * r_m * 1.15, m[1] - uy * r_m * 1.15); pg2 = (pg[0] - ux * larg * 0.42, pg[1] - uy * larg * 0.42)
        _tube(img, pg, pg2, larg * 0.84 + 2 * ep, larg * 0.84 + 2 * ep, TRAIT); _tube(img, pg, pg2, larg * 0.84, larg * 0.84, coul)
        _ligne(img, (pg2[0] + nx * larg * 0.45, pg2[1] + ny * larg * 0.45), (pg2[0] - nx * larg * 0.45, pg2[1] - ny * larg * 0.45), TRAIT, ep * 0.8)
    a = math.atan2(m[0] - c[0], m[1] - c[1])
    if forme_main: _main(img, m, a, forme_main, r_m, peau, ep)
    else: _ellipse(img, m, (r_m + ep, r_m + ep), 0, TRAIT); _ellipse(img, m, (r_m, r_m), 0, peau)


def _pied(img, c, d, R, C, peau, ep, peau_o):
    """Grand pied de trois-quarts (pointe vers d) : pied nu avec orteils, ou chaussure."""
    forme_ = (C or {}).get("chaussures") or "baskets"; col = tuple((C or {}).get("c_chaussures") or (240, 240, 240))
    L, h = 1.10 * R, 0.30 * R
    if forme_ in ("pieds_nus", "aucune"):                                  # grand pied plat, cheville, 5 orteils en bosses (référence)
        pts = [(c[0] - d * L * 0.12, c[1] - h * 2.2), (c[0] + d * L * 0.12, c[1] - h * 1.9), (c[0] + d * L * 0.25, c[1] - h * 1.4), (c[0] + d * L * 0.55, c[1] - h * 0.95),
               (c[0] + d * L * 0.86, c[1] - h * 0.55), (c[0] + d * L * 0.98, c[1] + h * 0.05), (c[0] + d * L * 0.90, c[1] + h * 0.42),
               (c[0] + d * L * 0.3, c[1] + h * 0.5), (c[0] - d * L * 0.26, c[1] + h * 0.42), (c[0] - d * L * 0.30, c[1] - h * 0.4)]
        pts = lisse(pts); forme(img, pts, peau, ep)
        degrade(img, pts, (c[0] + d * L * 0.3, c[1] - h * 1.2), L * 1.1, peau_o, 0.3, 0.55)
        _poly(img, pts, TRAIT, True, ep)
        for k in range(4):                                                 # séparations des orteils (petits arcs « ɔ »)
            ox = c[0] + d * L * (0.90 - 0.11 * k); oy = c[1] + h * (0.30 - 0.02 * k)
            _trait(img, [(ox - d * L * 0.04, oy + h * 0.18), (ox + d * L * 0.01, oy - h * 0.12), (ox - d * L * 0.05, oy - h * 0.42)], ep * 0.75)
        return
    pts = lisse([(c[0] - d * L * 0.40, c[1] - h * 1.25), (c[0] + d * L * 0.30, c[1] - h * 1.0), (c[0] + d * L * 0.95, c[1] - h * 0.25),
                 (c[0] + d * L * 0.95, c[1] + h * 0.40), (c[0] - d * L * 0.45, c[1] + h * 0.40)])
    forme(img, pts, col, ep)
    semelle = (250, 250, 250) if sum(col) < 600 else (175, 175, 185)
    if forme_ in ("baskets", "chaussons"):
        _ligne(img, (c[0] - d * L * 0.42, c[1] + h * 0.18), (c[0] + d * L * 0.92, c[1] + h * 0.18), semelle, ep * 1.3)
        for k in range(3): _ligne(img, (c[0] + d * L * (0.02 + 0.14 * k), c[1] - h * (1.0 - 0.2 * k)), (c[0] + d * L * (0.16 + 0.14 * k), c[1] - h * (0.72 - 0.2 * k)), TRAIT, ep * 0.6)
    else:
        _ligne(img, (c[0] - d * L * 0.42, c[1] + h * 0.30), (c[0] + d * L * 0.92, c[1] + h * 0.30), _fonce(col, 0.55), ep)
        _ellipse(img, (c[0] + d * L * 0.5, c[1] - h * 0.5), (L * 0.16, h * 0.15), 0, _clair(col, 0.45))


def buste(x, y_cou, y_ourlet, R):
    """Sweat ample : épaules tombantes arrondies, plus large à la poitrine, bas resserré qui « blouse » sur le bord-côte."""
    h = y_ourlet - y_cou; L = LARG_B * R
    g = [(x - 0.42 * R, y_cou), (x - 0.64 * R, y_cou + 0.10 * R), (x - L * 0.98, y_cou + 0.36 * R), (x - L * 1.08, y_cou + 0.72 * R),
         (x - L * 1.08, y_cou + h * 0.55), (x - L * 1.04, y_ourlet - 0.30 * R), (x - L * 0.92, y_ourlet)]
    return lisse(g + [(2 * x - px, py) for px, py in reversed(g)], ferme=True, n=5)


def casquette(img, t, rxe, R, tilt, col, ep, d):
    """Casquette (portée à l'envers en trois-quarts, comme les vidéos de référence) : calotte en 6 pans, visière, réglage à l'avant."""
    cx, cy = t
    def T(u, w): return M._rot(cx + u, cy + w, cx, cy, math.radians(tilt))
    if d:                                                                  # visière dans le dos, qui dépasse
        vis = lisse([T(-d * rxe * 0.55, -R * 0.62), T(-d * rxe * 1.25, -R * 0.55), T(-d * rxe * 1.55, -R * 0.30), T(-d * rxe * 1.30, -R * 0.22), T(-d * rxe * 0.70, -R * 0.36)])
        forme(img, vis, _fonce(col, 0.85), ep)
    cal = lisse([T(-rxe * 1.06, -R * 0.40), T(-rxe * 1.0, -R * 0.95), T(-rxe * 0.4, -R * 1.22), T(rxe * 0.4, -R * 1.22), T(rxe * 1.0, -R * 0.95), T(rxe * 1.06, -R * 0.40),
                 T(0, -R * 0.50)])
    forme(img, cal, col, ep)
    degrade(img, cal, T(-rxe * 0.2, -R * 1.0), rxe * 1.5, _fonce(col, 0.75), 0.45, 0.55)
    for k in (-0.45, 0.1):                                                 # coutures des pans
        _trait(img, [T(rxe * k * 0.3, -R * 1.2), T(rxe * k, -R * 0.85), T(rxe * k * 1.4, -R * 0.48)], ep * 0.6, _fonce(col, 0.6))
    if d:                                                                  # ouverture du réglage (on voit le front) et sa languette
        ou = lisse([T(d * rxe * 0.05, -R * 0.47), T(d * rxe * 0.55, -R * 0.44), T(d * rxe * 0.52, -R * 0.68), T(d * rxe * 0.08, -R * 0.70)])
        forme(img, ou, BLANC, ep * 0.8)
        _ligne(img, T(d * rxe * 0.05, -R * 0.60), T(d * rxe * 0.55, -R * 0.58), _fonce(col, 0.4), R * 0.06)
    else:
        vis = lisse([T(-rxe * 0.95, -R * 0.45), T(0, -R * 0.62), T(rxe * 0.95, -R * 0.45), T(rxe * 0.8, -R * 0.28), T(0, -R * 0.36), T(-rxe * 0.8, -R * 0.28)])
        forme(img, vis, _fonce(col, 0.85), ep)
    _ellipse(img, T(0, -R * 1.2), (R * 0.07, R * 0.04), 0, _fonce(col, 0.6))


def bonnet(img, t, rxe, R, tilt, col, ep):
    """Bonnet de la référence : calotte ronde qui couvre le haut de la tête et large revers replié."""
    cx, cy = t
    def T(u, w): return M._rot(cx + u, cy + w, cx, cy, math.radians(tilt))
    calotte = lisse([T(-rxe * 1.05, -R * 0.40), T(-rxe * 0.95, -R * 0.95), T(-rxe * 0.35, -R * 1.25), T(rxe * 0.35, -R * 1.25), T(rxe * 0.95, -R * 0.95), T(rxe * 1.05, -R * 0.40)])
    forme(img, calotte, col, ep)
    revers = lisse([T(-rxe * 1.10, -R * 0.74), T(0, -R * 0.84), T(rxe * 1.10, -R * 0.74), T(rxe * 1.10, -R * 0.36), T(0, -R * 0.44), T(-rxe * 1.10, -R * 0.36)])
    forme(img, revers, _fonce(col, 0.93), ep)
    degrade(img, calotte, T(-rxe * 0.3, -R * 0.95), rxe * 1.6, _fonce(col, 0.8), 0.4, 0.6)


def dessiner(img, P, p):
    """Même interface que marionnette.dessiner (P = personnage, p = pose). Renvoie (tête, (rx, ry))."""
    C = dict(p.get("costume") or {})
    if C.get("cheveux") in M.COIFFURES:
        c_ch = tuple(C.get("c_cheveux") or (P.get("cheveux") or ("", (95, 65, 40)))[1])
        P = dict(P, cheveux=None if C["cheveux"] == "aucune" else (C["cheveux"], c_ch))
    elif C.get("c_cheveux") and P.get("cheveux"): P = dict(P, cheveux=(P["cheveux"][0], tuple(C["c_cheveux"])))
    K = squelette(p)
    s, x, pieds, tete, rx, R = K["s"], K["x"], K["pieds"], K["tete"], K["rx"], K["ry"]
    st = K["st"]; r_m = K["r_m"]; ty = tete[1]
    ep = max(1.6, 0.034 * R)                                               # trait fin et régulier (référence)
    peau = tuple(p.get("peau") or BLANC); peau_o = (196, 198, 208) if peau == BLANC else _fonce(peau, 0.80)
    lum = p.get("lumiere", 0) or -1; sh = -1 if lum > 0 else 1
    tq = float(np.clip(p.get("tq", 0.0), -1, 1)); d = 1 if tq > 0 else (-1 if tq < 0 else (1 if (p.get("regard") or (0, 0))[0] >= 0 else -1))
    k34 = min(1.0, abs(tq) / 0.5) if abs(tq) > 0.05 else 0.0
    dos = bool(p.get("dos"))
    haut = C.get("haut") or "tshirt"; c_haut = tuple(C.get("c_haut") or (90, 140, 200)); c_haut_o = _fonce(c_haut, 0.88)
    bas = C.get("bas") or "jean"; c_bas = tuple(C.get("c_bas") or (60, 80, 130)); c_bas_o = _fonce(c_bas, 0.90)
    robe = haut in ("robe", "tunique") or bas == "jupe"
    courte = haut in ("tshirt", "polo", "debardeur", "hawai")
    det = tuple(C.get("details") or ())
    def tourne(px, py):                                                    # trois-quarts : le côté fuyant (vers d) se resserre
        dx = px - x; k = (0.86 if dx * d > 0 else 1.04) if k34 else 1.0
        return (x + dx * k + d * R * 0.06 * k34, py)
    y_cou, y_ep, y_ourlet, y_hanche = ty + COU * R, ty + EPAULE * R, ty + OURLET * R, ty + HANCHE * R
    assis = bool(p.get("assis"))

    # --- ombre au sol
    _ellipse(img, (x - lum * 0.2 * R, pieds + 0.04 * R), (1.25 * R, 0.17 * R), 0,
             tuple(p["couleur_ombre"]) if p.get("couleur_ombre") is not None else tuple(int(c * 0.80) for c in M._fond(img, x, pieds + 4 * s)))
    rxe = R * OEUF_X * (1.0 - 0.05 * k34)
    if P.get("cheveux") and P["cheveux"][0] in M.CHEVEUX_ARRIERE and p.get("coiffure", True): M._cheveux_arriere(img, tete, rxe * 1.05, R, st, p, P)

    bras = K["bras"]; formes = (p.get("main_forme_g") or "ouverte", p.get("main_forme_d") or "ouverte") if p.get("mains") else ("ouverte", "ouverte")
    loin_i = 1 if d > 0 else 0
    larg_b = MANCHE * R
    def bras_k(i, coul_m): e_, c_, m_ = bras[i]; _manche(img, e_, c_, m_, larg_b, coul_m, courte, peau, ep, formes[i], r_m, R)
    def devant(i):                                                         # main devant le buste (ou croisée de l'autre côté)
        m_ = bras[i][2]; sg_ = -1 if i == 0 else 1
        return (m_[0] - x) * sg_ < LARG_B * R * 0.95 and y_cou < m_[1] < y_ourlet + 0.2 * R
    if not devant(loin_i): bras_k(loin_i, c_haut_o)

    # --- jambes, pieds, bas
    xp = K["x_pieds"]; marche = p.get("marche")
    jambes = []
    for k_j, sg in enumerate((-1, 1)):
        loin_j = (sg > 0) == (d > 0) if k34 else False
        a = tourne(x + sg * 0.34 * R, y_hanche); b = (xp + sg * 0.62 * R * (0.85 if loin_j else 1.0) + d * 0.05 * R * k34, pieds - (0.06 * R if loin_j else 0) - 0.12 * R)
        if marche is not None:
            ph_ = marche + (math.pi if k_j else 0.0); b = (b[0] + math.sin(ph_) * 0.25 * R, b[1] - max(0.0, math.cos(ph_)) * 0.16 * R)
        g = ((a[0] + b[0]) / 2 + d * 0.04 * R - sg * 0.06 * R, (a[1] + b[1]) / 2)   # genoux un peu rentrés (référence)
        if assis: g = (x + sg * 0.5 * R, y_hanche + 0.35 * R); b = (g[0] + sg * 0.05 * R, pieds - 0.12 * R)
        jambes.append((loin_j, a, g, b, sg))
    jambes.sort(key=lambda j: not j[0])                                    # la jambe lointaine d'abord
    for loin_j, a, g, b, sg in jambes:
        long_ = not (robe or bas in ("short", "bermuda"))
        if long_:
            cj = c_bas_o if loin_j else c_bas; lw = (0.74 * R, 0.66 * R, 0.6 * R)
            _tube(img, a, g, lw[0] + 2 * ep, lw[1] + 2 * ep, TRAIT); _tube(img, g, b, lw[1] + 2 * ep, lw[2] + 2 * ep, TRAIT)
            _tube(img, a, g, lw[0], lw[1], cj); _tube(img, g, b, lw[1], lw[2], cj)
            _trait(img, [(g[0] - lw[1] * 0.3, g[1] - 0.1 * R), (g[0] + lw[1] * 0.15, g[1] + 0.02 * R)], ep * 0.7)   # pli du genou
            if bas == "jean": _ligne(img, (a[0] + sh * lw[0] * 0.25, a[1] + 0.2 * R), (b[0] + sh * lw[2] * 0.25, b[1] - 0.1 * R), _clair(cj, 0.3), ep * 0.6)
            if bas == "jogging": _tube(img, (b[0], b[1] - 0.14 * R), (b[0], b[1]), lw[2] * 0.9 + 2 * ep, lw[2] * 0.9 + 2 * ep, TRAIT); _tube(img, (b[0], b[1] - 0.14 * R), (b[0], b[1]), lw[2] * 0.9, lw[2] * 0.9, _fonce(cj, 0.88))
        else:
            nu = (C.get("chaussures") or "baskets") in ("pieds_nus", "aucune")
            _tube(img, a, g, CUISSE * R + 2 * ep, GENOU * R + 2 * ep, TRAIT); _tube(img, g, b, GENOU * R + 2 * ep, CHEVILLE * R + 2 * ep, TRAIT)
            if nu: _pied(img, (b[0], b[1] + 0.08 * R), d, R, C, peau, ep, peau_o)   # pied nu : la jambe se fond dans le pied (pas de trait à la cheville)
            _tube(img, a, g, CUISSE * R, GENOU * R, peau); _tube(img, g, b, GENOU * R, CHEVILLE * R, peau)
            cote = [(g[0] + sh * GENOU * R * 0.5, g[1]), (b[0] + sh * CHEVILLE * R * 0.5, b[1]), (b[0] + sh * CHEVILLE * R * 0.1, b[1]), (g[0] + sh * GENOU * R * 0.15, g[1])]
            ombre_cel(img, cote, sh, GENOU * R * 0.12, _fonce(peau, 0.93))   # liseré d'ombre discret au bord de la jambe
            if nu: continue
        _pied(img, (b[0], b[1] + 0.08 * R), d, R, C, peau, ep, peau_o)
    if bas in ("short", "bermuda") and not robe:                           # short long et large jusqu'au genou (référence)
        y_bas = ty + (4.85 if bas == "short" else 5.25) * R
        for loin_j, a, g, b, sg in jambes:
            t_ = (y_bas - a[1]) / max(1.0, (g[1] - a[1])); gx = a[0] + (g[0] - a[0]) * min(1.3, t_)
            cj = c_bas_o if loin_j else c_bas
            ent = (a[0] - sg * 0.30 * R, a[1] + 0.55 * R)                    # entrejambe : les deux jambes du short se séparent
            pts = [(a[0] - sg * 0.40 * R, a[1] - 0.2 * R), (a[0] + sg * 0.44 * R, a[1] - 0.2 * R), (gx + sg * 0.56 * R, y_bas + 0.03 * R), (gx - sg * 0.40 * R, y_bas), ent]
            forme(img, pts, cj, ep)
            motif(img, pts, C.get("motif"), tuple(C.get("c_motif") or _fonce(cj, 0.7)), s)
            q0, q1 = pts[2], pts[3]                                        # ourlet
            _ligne(img, (q0[0], q0[1] - 0.10 * R), (q1[0], q1[1] - 0.10 * R), TRAIT, ep * 0.8)
            ext = (a[0] + sg * 0.44 * R, a[1] - 0.2 * R); ext2 = (gx + sg * 0.56 * R, y_bas)   # bande sur le côté
            _ligne(img, (ext[0] - sg * 0.1 * R, ext[1] + 0.3 * R), (ext2[0] - sg * 0.1 * R, ext2[1] - 0.14 * R), _clair(cj, 0.35), ep * 0.9)
            _poly(img, pts, TRAIT, True, ep)
        ceinture = [tourne(x - 0.78 * R, y_hanche - 0.32 * R), tourne(x + 0.78 * R, y_hanche - 0.32 * R), tourne(x + 0.78 * R, y_hanche + 0.05 * R), tourne(x - 0.78 * R, y_hanche + 0.05 * R)]
        forme(img, ceinture, c_bas, ep)
        cx_ = x + d * 0.22 * R * k34                                       # cordon du short
        for sg in (-1, 1): _trait(img, [(cx_, y_ourlet + 0.04 * R), (cx_ + sg * 0.12 * R, y_ourlet + 0.25 * R), (cx_ + sg * 0.08 * R, y_ourlet + 0.55 * R)], ep * 1.6, _fonce(c_bas, 0.75))
    if robe:
        jy = ty + 5.0 * R
        jupe = [tourne(x - 0.95 * R, y_hanche - 0.4 * R), tourne(x + 0.95 * R, y_hanche - 0.4 * R), tourne(x + 1.3 * R, jy), tourne(x - 1.3 * R, jy)]
        cj = c_haut if haut in ("robe", "tunique") else c_bas
        forme(img, jupe, cj, ep); ombre_cel(img, jupe, sh, 0.3 * R, _fonce(cj, 0.82)); _poly(img, jupe, TRAIT, True, ep)
        for k in (-1, 0, 1): _ligne(img, tourne(x + k * 0.4 * R, y_hanche), tourne(x + k * 0.62 * R, jy - 0.1 * R), _fonce(cj, 0.78), ep * 0.7)

    # --- capuche dans le dos (derrière le buste)
    hood = haut == "capuche" and not dos
    if hood:
        b_ = -d if k34 else 1
        cap = lisse([(x - b_ * 0.50 * R, y_cou + 0.1 * R), (x + b_ * 0.30 * R, y_cou - 0.25 * R),
                     (x + b_ * 0.58 * R, y_cou - 0.08 * R), (x + b_ * 0.80 * R, y_cou + 0.12 * R), (x + b_ * 0.80 * R, y_ep + 0.15 * R)])
        forme(img, cap, c_haut_o, ep)

    # --- buste : sweat / pull / chemise…
    pts_b = [tourne(*q) for q in buste(x, y_cou, y_ourlet, R)]
    forme(img, pts_b, c_haut, ep)
    motif(img, pts_b, C.get("motif"), tuple(C.get("c_motif") or _fonce(c_haut, 0.72)), s)
    ombre_cel(img, pts_b, sh, 0.16 * R, c_haut_o)
    degrade(img, pts_b, (x - sh * 0.3 * R, y_cou + 0.5 * R), R * 2.6, _fonce(c_haut, 0.72), 0.45, 0.5)   # volume doux du sweat
    _poly(img, pts_b, TRAIT, True, ep)
    fx = x + d * 0.25 * R * k34                                            # milieu du vêtement (tourné)
    for sg in (-1, 1):                                                     # coutures raglan (du col à l'aisselle)
        if haut in ("capuche", "pull", "survetement", "sweat"):
            _trait(img, [tourne(x + sg * 0.55 * R, y_cou + 0.08 * R), tourne(x + sg * 0.78 * R, y_ep + 0.3 * R), tourne(x + sg * 0.86 * R, y_ep + 0.75 * R)], ep * 0.8)
    if haut in ("capuche", "pull", "col_roule", "survetement", "doudoune", "gilet", "sweat"):   # bord-côte en bas
        bc = [tourne(x - LARG_B * 0.95 * R, y_ourlet - 0.30 * R), tourne(x + LARG_B * 0.95 * R, y_ourlet - 0.30 * R), tourne(x + LARG_B * 0.9 * R, y_ourlet), tourne(x - LARG_B * 0.9 * R, y_ourlet)]
        forme(img, bc, c_haut, ep)
    if haut == "capuche":                                                  # poche kangourou
        _trait(img, [tourne(x - 0.55 * R, y_ourlet - 0.4 * R), tourne(x - 0.45 * R, y_ourlet - 0.9 * R), tourne(x + 0.45 * R, y_ourlet - 0.9 * R), tourne(x + 0.55 * R, y_ourlet - 0.4 * R)], ep * 0.8, _fonce(c_haut, 0.6))
    if haut in ("chemise", "polo", "pyjama"):
        for sg in (-1, 1): forme(img, [(fx, y_cou + 0.22 * R), (fx + sg * 0.42 * R, y_cou - 0.02 * R), (fx + sg * 0.36 * R, y_cou + 0.3 * R)], _clair(c_haut, 0.15), ep * 0.8)
        _ligne(img, (fx, y_cou + 0.22 * R), (fx, y_ourlet), _fonce(c_haut, 0.8), ep * 0.7)
        for k in range(4 if haut != "polo" else 1): _ellipse(img, (fx + 0.06 * R, y_cou + 0.45 * R + k * 0.5 * R), (0.045 * R, 0.045 * R), 0, _fonce(c_haut, 0.65))
    if haut in ("costume", "blouse", "blouson", "redingote", "gilet", "uniforme"):
        inner = tuple(C.get("c_dessous") or (248, 248, 248))
        _poly(img, [(fx - 0.28 * R, y_cou), (fx + 0.28 * R, y_cou), (fx + 0.06 * R, y_cou + 1.2 * R), (fx - 0.06 * R, y_cou + 1.2 * R)], inner)
        for sg in (-1, 1):
            forme(img, [(fx + sg * 0.28 * R, y_cou - 0.04 * R), (fx + sg * 0.06 * R, y_cou + 1.2 * R), (fx + sg * 0.5 * R, y_cou + 0.5 * R)], _fonce(c_haut, 0.88), ep * 0.8)
        _ligne(img, (fx, y_cou + 1.2 * R), (fx, y_ourlet), TRAIT, ep * 0.7)
        _ellipse(img, (fx + 0.07 * R, y_cou + 1.6 * R), (0.05 * R, 0.05 * R), 0, TRAIT)
    if haut == "col_roule": _tube(img, (fx - 0.4 * R, y_cou + 0.05 * R), (fx + 0.4 * R, y_cou + 0.05 * R), 0.36 * R + 2 * ep, 0.36 * R + 2 * ep, TRAIT); _tube(img, (fx - 0.4 * R, y_cou + 0.05 * R), (fx + 0.4 * R, y_cou + 0.05 * R), 0.36 * R, 0.36 * R, c_haut_o)
    if haut in ("tshirt", "pull", "debardeur", "hawai", "survetement"): _arc(img, (fx, y_cou + 0.04 * R), (0.42 * R, 0.2 * R), 0, 0, 180, TRAIT, ep * 0.9)
    if haut == "doudoune":
        for k in range(1, 5): _trait(img, [tourne(x - 0.98 * R, y_cou + k * 0.48 * R), tourne(x, y_cou + k * 0.48 * R + 0.06 * R), tourne(x + 0.98 * R, y_cou + k * 0.48 * R)], ep * 0.8)
    if haut in ("survetement", "doudoune", "blouson"): _ligne(img, (fx, y_cou + 0.1 * R), (fx, y_ourlet - 0.05 * R), TRAIT, ep * 0.8)
    if "cravate" in det:
        cr = tuple(C.get("c_cravate") or (180, 40, 50))
        forme(img, [(fx - 0.1 * R, y_cou + 0.08 * R), (fx + 0.1 * R, y_cou + 0.08 * R), (fx + 0.16 * R, y_cou + 1.1 * R), (fx, y_cou + 1.3 * R), (fx - 0.16 * R, y_cou + 1.1 * R)], cr, ep * 0.8)
    if "badge" in det: forme(img, [(fx + 0.3 * R, y_cou + 0.6 * R), (fx + 0.7 * R, y_cou + 0.6 * R), (fx + 0.7 * R, y_cou + 0.85 * R), (fx + 0.3 * R, y_cou + 0.85 * R)], (245, 245, 245), ep * 0.8)
    if "collier" in det: _arc(img, (fx, y_cou + 0.1 * R), (0.36 * R, 0.26 * R), 0, 10, 170, (240, 200, 80), ep)
    if "ceinture" in det: _ligne(img, tourne(x - 0.97 * R, y_ourlet - 0.08 * R), tourne(x + 0.97 * R, y_ourlet - 0.08 * R), (60, 40, 30), 0.1 * R)
    if hood:                                                               # col de la capuche autour du cou + cordons à embouts
        col_ = lisse([(fx - 0.72 * R, y_cou + 0.02 * R), (fx - 0.4 * R, y_cou - 0.12 * R), (fx + 0.4 * R, y_cou - 0.12 * R), (fx + 0.72 * R, y_cou + 0.02 * R),
                      (fx + 0.45 * R, y_cou + 0.34 * R), (fx, y_cou + 0.42 * R), (fx - 0.45 * R, y_cou + 0.34 * R)])
        forme(img, col_, c_haut, ep)
        for xc in (fx - 0.24 * R, fx + 0.18 * R):
            _trait(img, [(xc, y_cou + 0.32 * R), (xc - 0.02 * R, y_cou + 0.8 * R), (xc, y_cou + 1.25 * R)], ep * 2.6)
            _trait(img, [(xc, y_cou + 0.32 * R), (xc - 0.02 * R, y_cou + 0.8 * R), (xc, y_cou + 1.25 * R)], ep * 1.2, _fonce(c_haut, 0.7))
            forme(img, [(xc - 0.05 * R, y_cou + 1.22 * R), (xc + 0.05 * R, y_cou + 1.22 * R), (xc + 0.04 * R, y_cou + 1.42 * R), (xc - 0.04 * R, y_cou + 1.42 * R)], (200, 200, 205), ep * 0.7)
    if "echarpe" in det: _tube(img, (fx - 0.5 * R, y_cou), (fx + 0.5 * R, y_cou), 0.34 * R + 2 * ep, 0.34 * R + 2 * ep, TRAIT); _tube(img, (fx - 0.5 * R, y_cou), (fx + 0.5 * R, y_cou), 0.34 * R, 0.34 * R, tuple(C.get("c_echarpe") or (200, 60, 60)))
    M._sacs(img, x, K["cy_corps"], K["corps_w"], K["corps_h"], s, C)

    # --- bras devant le corps
    if devant(loin_i): bras_k(loin_i, c_haut)
    bras_k(1 - loin_i, c_haut)
    if K.get("croise", 0) > 0.5:                                           # bras croisés : la main lointaine ressort sur le biceps
        e_, c_, m_ = bras[loin_i]; _main(img, m_, math.atan2(m_[0] - c_[0], m_[1] - c_[1]), formes[loin_i], r_m, peau, ep)
    for i_ in (0, 1):
        if ("montre" in det and i_ == 0) or ("bracelet" in det and i_ == 1):
            e_, c_, m_ = bras[i_]; w_ = (c_[0] + (m_[0] - c_[0]) * 0.72, c_[1] + (m_[1] - c_[1]) * 0.72)
            _ellipse(img, w_, (0.12 * R, 0.08 * R), 0, TRAIT); _ellipse(img, w_, (0.08 * R, 0.055 * R), 0, (240, 200, 80))

    # --- tête en œuf
    tilt = float(p.get("tilt", 0.0)) + d * 4 * k34
    ov = oeuf(tete[0], tete[1], rxe, R, tilt, d=d if k34 >= 0.15 else 0)
    _poly(img, ov, TRAIT, True, ep * 2.2); _poly(img, ov, peau)
    b_ = -d if k34 else sh                                                 # ombre douce du côté du dos (croissant gris)
    degrade(img, ov, (tete[0] + b_ * -rxe * 0.35, tete[1] - R * 0.25), rxe * 1.55, peau_o, 0.85, 0.62)
    if not dos:
        lun = "soleil" if "lunettes_soleil" in det else ("vue" if ("lunettes_vue" in det or P.get("accessoire") == "lunettes") else None)
        visage(img, tete, rxe, R, dict(p, _lunettes=lun), d, k34, tilt, ep)
        if C:
            roi_t = M._roi(img, tete[0], tete[1], rxe * 1.7, R * 1.4)
            garde = img[roi_t[1]:roi_t[3], roi_t[0]:roi_t[2]].copy() if roi_t else None
            barbe(img, ov, tete, rxe, R, d, k34, det, tuple(C.get("c_barbe") or (90, 65, 45)), tilt)
            M._details_tete(img, (tete[0] + d * rxe * 0.3 * k34, tete[1]), rxe, R, st, p, dict(C, details=tuple(x_ for x_ in det if x_ not in BARBES_T + ("lunettes_vue", "lunettes_soleil"))))
            if garde is not None:
                x0_, y0_, x1_, y1_ = roi_t; m_ = _masque(ov, roi_t) > 127; z_ = img[y0_:y1_, x0_:x1_]; z_[~m_] = garde[~m_]
    if P.get("cheveux") and p.get("coiffure", True) and C.get("chapeau") not in ("bonnet", "casquette"): M._cheveux_avant(img, tete, rxe * 1.04, R, st, p, P, dos)
    if P.get("accessoire") and P["accessoire"] != "lunettes": M._accessoire(img, tete, rxe, R, st, p, P)
    if C.get("chapeau") == "bonnet": bonnet(img, tete, rxe, R, tilt, tuple(C.get("c_chapeau") or (190, 150, 70)), ep)
    elif C.get("chapeau") == "casquette": casquette(img, tete, rxe, R, tilt, tuple(C.get("c_chapeau") or (40, 60, 140)), ep, d if k34 else 0)
    elif C.get("chapeau") in M.CHAPEAUX: GR.chapeau(img, tete, rxe * 1.05, R, st, p, C["chapeau"], tuple(C.get("c_chapeau") or (60, 60, 70)))
    M._effets(img, tete, rx, R, st, p)
    for nom in ("main_g", "main_d"):
        if p.get(nom) is not None:
            m_ = bras[0][2] if nom == "main_g" else bras[1][2]; M._coller(img, p[nom], m_[0], m_[1])
    return tete, (rx, R)
