"""Personnages humains ADULTES, dans le style de nos anciens personnages, différents à chaque vidéo (casting libre).

Chaque personnage est une FICHE (creer) : genre, âge, corpulence, taille, couleur de peau, forme du visage, yeux (couleur, taille),
nez, lèvres, sourcils, coiffure et couleur des cheveux (grisonnants avec l'âge), barbe ou moustache, lunettes, rides.
Le dessin reprend le style des marionnettes de la chaîne (trait noir, aplats, ombrage net, grosse tête ronde très expressive :
mêmes yeux brillants, sourcils, bouche synchronisée, coiffures, effets) sur un VRAI corps d'adulte : cou, épaules, buste, taille,
hanches selon le genre et la corpulence, bras et jambes d'un seul tenant qui se plient en souplesse au coude et au genou (aucune
pièce articulée visible), mains à quatre doigts et pouce, pieds chaussés ; peau de couleur humaine, oreilles, nez, rides, barbe,
lunettes, tenue complète. Mêmes commandes de pose que les marionnettes : toute la mise en scène du studio s'applique.
"""
import math
import numpy as np, cv2

import marionnette as M

AA = cv2.LINE_AA
PEAUX = [(255, 226, 200), (246, 205, 172), (234, 186, 146), (214, 160, 118), (176, 118, 82), (130, 86, 58), (96, 64, 46)]
CHEVEUX = [(30, 24, 22), (62, 42, 30), (104, 70, 44), (150, 100, 58), (196, 150, 90), (228, 196, 130), (170, 70, 40)]
IRIS = [(80, 50, 30), (110, 75, 45), (60, 110, 150), (80, 130, 90), (120, 120, 110)]
COIFFURES_H = ("court", "raie", "rase", "boucles", "chauve", "mi_long", "queue")
COIFFURES_F = ("long", "carre", "queue", "chignon", "boucles", "mi_long", "court")

def _hex(c): return tuple(int(v) for v in c)
def _melange(a, b, k): return tuple(int(x + (y - x) * k) for x, y in zip(a, b))
def _fonce(c, k=0.7): return tuple(int(v * k) for v in c)

# ------------------------------------------------------------------ casting
def creer(graine, genre=None, age=None, cheveux=None, c_cheveux=None, corpulence=None, lunettes=None, barbe=None, peau=None):
    """Fiche d'un personnage adulte (tirée au hasard avec la graine, en respectant les indices donnés : voix, image, texte)."""
    rng = np.random.default_rng(graine)
    g = genre if genre in ("h", "f") else ("h" if rng.random() < 0.5 else "f")
    a = int(age) if age else int(rng.choice([24, 28, 32, 36, 42, 48, 55, 63, 70], p=[0.13, 0.15, 0.15, 0.14, 0.13, 0.11, 0.09, 0.06, 0.04]))
    style = cheveux or (rng.choice(COIFFURES_H, p=[0.3, 0.25, 0.12, 0.1, 0.08, 0.1, 0.05]) if g == "h" else rng.choice(COIFFURES_F, p=[0.28, 0.2, 0.17, 0.12, 0.1, 0.08, 0.05]))
    if a > 55 and g == "h" and not cheveux and rng.random() < 0.4: style = "chauve"
    cc = _hex(c_cheveux) if c_cheveux else CHEVEUX[int(rng.integers(len(CHEVEUX)))]
    if a >= 50 and not c_cheveux: cc = _melange(cc, (190, 190, 192), min(1.0, (a - 45) / 25))       # grisonnant
    return dict(genre=g, age=a, corpulence=float(corpulence if corpulence is not None else rng.beta(2, 3)), taille=float(rng.uniform(0.94, 1.06) * (1.04 if g == "h" else 0.97)),
                peau=_hex(peau) if peau else PEAUX[int(rng.integers(len(PEAUX)))], visage=str(rng.choice(["ovale", "rond", "carre", "long"])),
                iris=IRIS[int(rng.integers(len(IRIS)))], yeux=float(rng.uniform(0.9, 1.12)), nez=str(rng.choice(["droit", "rond", "fort", "fin"])),
                levres=float(rng.uniform(0.8, 1.25) * (1.12 if g == "f" else 1.0)), sourcils=float(rng.uniform(0.85, 1.3) * (1.15 if g == "h" else 0.9)),
                cheveux=str(style), c_cheveux=cc,
                barbe=barbe if barbe is not None else (str(rng.choice(["", "", "trois_jours", "courte", "moustache"])) if g == "h" else ""),
                lunettes=lunettes if lunettes is not None else (str(rng.choice(["rondes", "rectangle"])) if rng.random() < (0.18 + 0.006 * max(0, a - 35)) else ""),
                maquillage=bool(g == "f" and rng.random() < 0.6))

# ------------------------------------------------------------------ outils
TRAIT = M.TRAIT
def _pts(pts): return np.array([[int(round(x * 4)), int(round(y * 4))] for x, y in pts], np.int32).reshape(-1, 1, 2)
def _poly(img, pts, c): cv2.fillPoly(img, [_pts(pts)], c, AA, 2)
def _contour(img, pts, ep): cv2.polylines(img, [_pts(pts)], True, TRAIT, max(1, int(round(ep))), AA, 2)
def _ligne(img, a, b, c, ep): cv2.line(img, (int(a[0] * 4), int(a[1] * 4)), (int(b[0] * 4), int(b[1] * 4)), c, max(1, int(round(ep))), AA, 2)
def _courbe(img, pts, c, ep): cv2.polylines(img, [_pts(pts)], False, c, max(1, int(round(ep))), AA, 2)
def _rond(img, c, r, col): cv2.circle(img, (int(c[0] * 4), int(c[1] * 4)), max(1, int(r * 4)), col, -1, AA, 2)
def _ell(c, rx, ry, ang=0.0, n=40, a0=0.0, a1=2 * math.pi):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(c[0] + rx * math.cos(u) * ca - ry * math.sin(u) * sa, c[1] + rx * math.cos(u) * sa + ry * math.sin(u) * ca) for u in np.linspace(a0, a1, n)]

def _lisse(pts, n=3):
    """Lissage de Chaikin : la ligne épaule → coude → poignet devient une courbe souple."""
    for _ in range(n):
        q = [pts[0]]
        for a, b in zip(pts[:-1], pts[1:]): q += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]), (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
        pts = q + [pts[-1]]
    return pts

def _tube(ligne, rayons, bouts=(True, True)):
    """Contour d'un membre souple : une ligne centrale lissée, une épaisseur qui varie le long du membre, bouts arrondis."""
    L = _lisse(ligne); n = len(L)
    r = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(rayons)), rayons)
    g, d = [], []
    for i, (x, y) in enumerate(L):
        a, b = L[max(0, i - 1)], L[min(n - 1, i + 1)]; dx, dy = b[0] - a[0], b[1] - a[1]; l = math.hypot(dx, dy) or 1
        nx, ny = -dy / l, dx / l; g.append((x + nx * r[i], y + ny * r[i])); d.append((x - nx * r[i], y - ny * r[i]))
    def bout(c, rr, ang, sens):
        return [(c[0] + rr * math.cos(ang + sens * u), c[1] + rr * math.sin(ang + sens * u)) for u in np.linspace(0, math.pi, 9)][1:-1]
    a0 = math.atan2(L[1][1] - L[0][1], L[1][0] - L[0][0]); a1 = math.atan2(L[-1][1] - L[-2][1], L[-1][0] - L[-2][0])
    fin = bout(L[-1], r[-1], a1 + math.pi / 2, -1) if bouts[1] else []
    deb = bout(L[0], r[0], a1 * 0 + a0 - math.pi / 2, -1) if bouts[0] else []
    return g + fin + d[::-1] + deb

# ------------------------------------------------------------------ géométrie
def _geo(F, p):
    """Repères du corps (pieds en p["y"]) : tête, cou, épaules, taille, hanches, articulations des bras et des jambes."""
    s = p["s"]; hd = 165 * s * F["taille"]; sq = p.get("sq", 0.0); x, Y = p["x"], p["y"]
    fem = F["genre"] == "f"; corp = F["corpulence"]
    Ht = 5.0 * hd * (1 - 0.3 * max(0.0, sq)) * (1 + 0.12 * max(0.0, -sq)); k = Ht / (5.0 * hd)
    yb = lambda u: Y - Ht + u * hd * k
    epaules, penche = float(p.get("epaules", 0.0)), float(p.get("penche", 0.0)); dxp = penche * 0.18 * hd
    tete = (x + dxp + math.sin(math.radians(p.get("tilt", 0))) * 0.2 * hd, yb(0.5) + epaules * 0.1 * hd)
    G = dict(hd=hd, x=x, Y=Y, yb=yb, dxp=dxp, tete=tete, sh=hd / 300 * 1.0,
             y_ep=yb(1.16) - epaules * 0.13 * hd, y_ta=yb(2.1), y_ha=yb(2.58), y_ent=yb(2.8),
             l_ep=hd * (0.66 if not fem else 0.56) * (1 + 0.2 * corp), l_ta=hd * (0.46 if not fem else 0.37) * (1 + 0.45 * corp),
             l_ha=hd * (0.48 if not fem else 0.55) * (1 + 0.3 * corp), corp=corp, fem=fem)
    G["epaule_g"] = (x + dxp - G["l_ep"] + 0.1 * hd, G["y_ep"] + 0.12 * hd); G["epaule_d"] = (x + dxp + G["l_ep"] - 0.1 * hd, G["y_ep"] + 0.12 * hd)
    bras = {}
    for nom, cle in (("g", "bras_g"), ("d", "bras_d")):
        a1d, a2d = p.get(cle, (0, 0)); a1, a2 = math.radians(a1d), math.radians(a1d + a2d); e = G["epaule_" + nom]
        c = (e[0] + math.sin(a1) * 0.88 * hd, e[1] + math.cos(a1) * 0.88 * hd); m = (c[0] + math.sin(a2) * 0.78 * hd, c[1] + math.cos(a2) * 0.78 * hd)
        bras[nom] = (e, c, m, a2)
    G["bras"] = bras
    return G

def tete_y(s, taille=1.0):
    """Hauteur du centre de la tête pour des pieds à y=1500 (cadrages du moteur)."""
    hd = 165 * s * taille; return 1500 - 5.0 * hd + 0.5 * hd

def hauteur_tete(s, taille=1.0): return 165 * s * taille

def reperes(F, p):
    """Centre et rayons de la tête, positions des deux mains (pour poser objets et effets sur un personnage rendu en 3D)."""
    G = _geo(F, p); return G["tete"], (G["hd"] * 0.47, G["hd"] * 0.5), [G["bras"]["g"][2], G["bras"]["d"][2]]

COIFF_M = {"carre": "carre", "long": "long", "queue": "queue", "chignon": "chignon", "boucles": "boucles", "court": "court", "raie": "court",
           "rase": "court", "mi_long": "carre", "meches": "meches", "nuque": "nuque"}

def _P(F):
    """Le personnage vu par marionnette.py (visage, coiffure) : pas d'accessoire fixe, coiffure et nez de la fiche."""
    st = F["cheveux"]; c = tuple(F["c_cheveux"])
    if st == "rase": c = _melange(c, F["peau"], 0.45)
    ch = (COIFF_M[st], c) if st in COIFF_M else (("couronne", c) if F["age"] > 45 else None)
    return dict(nom="", accessoire=None, couleur=(0, 0, 0), cheveux=ch, nez={"droit": "pointu", "rond": "rond", "fort": "rond", "fin": "petit"}[F["nez"]],
                cils=F["genre"] == "f", moustache=F.get("barbe") == "moustache")

# ------------------------------------------------------------------ dessin
def dessiner(img, F, p):
    """Dessine le personnage de fiche F dans img selon la pose p (mêmes clés que marionnette.dessiner). Renvoie (tête, (rx, ry))."""
    G = _geo(F, p); hd = G["hd"]; x, Y, yb, dxp = G["x"], G["Y"], G["yb"], G["dxp"]
    ep = max(2.0, 0.045 * hd); peau = tuple(F["peau"]); C = p.get("costume") or {}; lum = p.get("lumiere", 0) or -1
    haut = C.get("haut") or "tshirt"; c_haut = tuple(C.get("c_haut") or (120, 140, 170))
    if haut == "blouse": c_haut = (244, 246, 250)
    bas = C.get("bas") or "pantalon"; c_bas = tuple(C.get("c_bas") or (60, 70, 90)); jupe = bas == "jupe" or haut == "robe"
    P = _P(F); rx = ry = 0.5 * hd; sh = hd / 300; dos = bool(p.get("dos"))
    tete = G["tete"]
    # ombre au sol
    cv2.ellipse(img, (int(x * 4), int((Y + 0.03 * hd) * 4)), (int(hd * (0.75 + 0.25 * G["corp"]) * 4), int(hd * 0.09 * 4)), 0, 0, 360,
                tuple(int(v * 0.8) for v in M._fond(img, x, Y + 0.03 * hd)), -1, AA, 2)
    # cheveux derrière la tête
    if P["cheveux"] and P["cheveux"][0] in M.CHEVEUX_ARRIERE:
        M._cheveux_arriere(img, tete, rx, ry, sh, dict(p, s=sh), P)
    # jambes (contour d'abord, puis remplissage : le bas du corps se fond en une seule forme)
    pied = float(p.get("pied", 0.0)); jambes = []
    for sg in (-1, 1):
        h = (x + sg * G["l_ha"] * 0.45, G["y_ha"] + 0.05 * hd); g = (x + sg * G["l_ha"] * 0.42, Y - 1.15 * hd); c = (x + sg * G["l_ha"] * 0.4, Y - 0.16 * hd - (pied * 0.18 * hd if sg > 0 else 0))
        jambes.append((sg, h, g, c))
    rj = [0.22 * hd * (1 + 0.3 * G["corp"]), 0.15 * hd, 0.105 * hd]
    tronc = _tronc(G)
    for sg, h, g, c in jambes: _contour(img, _tube([h, g, c], rj), 2 * ep)
    for sg, h, g, c in jambes:
        _chaussure(img, c, hd, C, ep, sg)
    for sg, h, g, c in jambes:
        nu = jupe or bas == "short"; _poly(img, _tube([h, g, c], rj), peau if nu else c_bas)
        if bas == "short": _poly(img, _tube([h, (h[0] * 0.5 + g[0] * 0.5, h[1] * 0.5 + g[1] * 0.5)], rj[:2]), c_bas)
        if not nu and bas in ("jean", "pantalon", "jogging"):                # pli au genou, couture
            _courbe(img, [(g[0] - rj[1] * 0.7, g[1] - 0.05 * hd), (g[0], g[1] + 0.02 * hd), (g[0] + rj[1] * 0.6, g[1] - 0.04 * hd)], M._fonce(c_bas, 0.7), ep * 0.7)
            if bas == "jogging": _ligne(img, (h[0] + sg * rj[0] * 0.8, h[1]), (c[0] + sg * rj[2] * 0.9, c[1] - 0.1 * hd), (245, 245, 245), ep)
    # jupe / robe
    if jupe:
        cj = c_haut if haut == "robe" else c_bas
        jp = [(x - G["l_ha"] * 0.95, G["y_ha"] - 0.15 * hd), (x + G["l_ha"] * 0.95, G["y_ha"] - 0.15 * hd), (x + G["l_ha"] * 1.35, Y - 1.05 * hd), (x - G["l_ha"] * 1.35, Y - 1.05 * hd)]
        _contour(img, jp, 2 * ep); _poly(img, jp, cj)
        for k in (-1, 0, 1): _ligne(img, (x + k * G["l_ha"] * 0.35, G["y_ha"]), (x + k * G["l_ha"] * 0.55, Y - 1.2 * hd), M._fonce(cj, 0.8), ep * 0.7)
    # buste, cou, tête : contour commun puis remplissage
    cou = [(tete[0] - 0.13 * hd, tete[1] + 0.35 * hd), (tete[0] + 0.13 * hd, tete[1] + 0.35 * hd), (x + dxp + 0.15 * hd, G["y_ep"] + 0.05 * hd), (x + dxp - 0.15 * hd, G["y_ep"] + 0.05 * hd)]
    _contour(img, tronc, 2 * ep); _contour(img, cou, 2 * ep)
    if not jupe and bas != "short" or bas == "short":
        bassin = [(x - G["l_ta"] * 1.02, G["y_ta"] + 0.05 * hd), (x + G["l_ta"] * 1.02, G["y_ta"] + 0.05 * hd), (x + G["l_ha"], G["y_ha"]), (x + G["l_ha"] * 0.9, G["y_ent"] + 0.12 * hd), (x - G["l_ha"] * 0.9, G["y_ent"] + 0.12 * hd), (x - G["l_ha"], G["y_ha"])]
        if not jupe: _poly(img, bassin, c_bas)
    _poly(img, cou, peau); M._ombre(img, (x + dxp, G["y_ep"]), (0.15 * hd, 0.2 * hd), 0, lum, 0.25)
    _poly(img, tronc, c_haut)
    if C.get("motif") in ("rayures", "carreaux", "pois"): _motif(img, tronc, C["motif"], tuple(C.get("c_motif") or M._fonce(c_haut, 0.75)), hd)
    _ombre_poly(img, tronc, lum, p.get("ombre", 0.24))
    _details(img, C, G, ep, haut, c_haut)
    # tête : contour, peau, oreilles, ombrage, visage des anciens personnages
    if not dos:
        for sg in (-1, 1):
            o = (tete[0] + sg * rx * 0.97, tete[1] + 0.06 * hd); _rond(img, o, 0.1 * hd + ep, TRAIT); _rond(img, o, 0.1 * hd, peau); _rond(img, (o[0] - sg * 0.02 * hd, o[1]), 0.05 * hd, M._fonce(peau, 0.85))
    t_pts = _ell(tete, rx * (0.95 if F["visage"] == "long" else 1.0), ry * (1.04 if F["visage"] == "long" else 1.0), math.radians(p.get("tilt", 0)))
    _contour(img, t_pts, 2 * ep); _poly(img, t_pts, peau)
    M._ombre(img, tete, (rx, ry), p.get("tilt", 0), lum, p.get("ombre", 0.24) * 0.8)
    for cle, teinte in (("rougeur", (235, 70, 60)), ("paleur", (150, 190, 235))):
        if p.get(cle, 0) > 0: _teinte(img, tete, rx, ry, teinte, p[cle])
    pv = dict(p, s=sh, reflets=True, peau=peau, joues=p.get("joues"))
    if not dos:
        if F["age"] > 45:                                                  # rides du front et pattes d'oie
            for k in range(2): _courbe(img, [(tete[0] - 0.18 * hd, tete[1] - (0.28 + 0.06 * k) * hd), (tete[0], tete[1] - (0.3 + 0.06 * k) * hd), (tete[0] + 0.18 * hd, tete[1] - (0.28 + 0.06 * k) * hd)], M._fonce(peau, 0.78), ep * 0.6)
        if F.get("barbe") in ("courte", "trois_jours"): _barbe(img, F, tete, rx, ry, hd)
        M._visage(img, tete, rx, ry, sh, pv, P)
        if F.get("lunettes"): M._details_tete(img, tete, rx, ry, sh, pv, {"details": ("lunettes_vue",)})
        if F.get("maquillage"):
            for sg in (-1, 1): _rond(img, (tete[0] + sg * 0.27 * hd, tete[1] + 0.17 * hd), 0.045 * hd, _melange(peau, (235, 120, 130), 0.35))
    if P["cheveux"] and p.get("coiffure", True): M._cheveux_avant(img, tete, rx, ry, sh, pv, P, dos)
    # bras et mains (devant) : contour du bras à partir du milieu du haut du bras (l'épaule se fond dans le buste)
    manche = haut not in ("debardeur",); court = haut in ("tshirt", "polo", "debardeur", "robe")
    c_m = tuple(C.get("c_manche") or c_haut)
    rb = [0.115 * hd * (1 + 0.25 * G["corp"]), 0.095 * hd, 0.08 * hd]
    for nom in ("g", "d"):
        e, c, m, a2 = G["bras"][nom]
        ligne = [e, c, m]; L = _tube(ligne, rb)
        mi = (e[0] * 0.55 + c[0] * 0.45, e[1] * 0.55 + c[1] * 0.45)
        _contour(img, _tube([mi, c, m], rb[1:]), 2 * ep)
        forme = p.get("main_forme_" + nom) or "ouverte"
        _main(img, m, a2, forme, hd, peau, ep, nom == "g", contour_seul=True)
        _poly(img, L, peau if (court and False) else (c_m if manche else peau))
        if court or not manche:                                            # avant-bras nu (manches courtes)
            _poly(img, _tube([(e[0] * 0.3 + c[0] * 0.7, e[1] * 0.3 + c[1] * 0.7), c, m], [rb[1] * 0.98, rb[1] * 0.98, rb[2]]), peau)
            _courbe(img, [(e[0] * 0.3 + c[0] * 0.7 + (c[1] - e[1]) / (math.hypot(c[0] - e[0], c[1] - e[1]) or 1) * rb[1], e[1] * 0.3 + c[1] * 0.7 - (c[0] - e[0]) / (math.hypot(c[0] - e[0], c[1] - e[1]) or 1) * rb[1]),
                          (e[0] * 0.3 + c[0] * 0.7 - (c[1] - e[1]) / (math.hypot(c[0] - e[0], c[1] - e[1]) or 1) * rb[1], e[1] * 0.3 + c[1] * 0.7 + (c[0] - e[0]) / (math.hypot(c[0] - e[0], c[1] - e[1]) or 1) * rb[1])], TRAIT, ep)
        else:                                                              # pli du coude
            _courbe(img, [(c[0] - 0.05 * hd, c[1] - 0.02 * hd), (c[0] + 0.03 * hd, c[1] + 0.03 * hd)], M._fonce(c_m, 0.65), ep * 0.8)
        _main(img, m, a2, forme, hd, peau, ep, nom == "g")
    if "montre" in C.get("details", ()):
        e, c, m, a2 = G["bras"]["g"]; w_ = (c[0] * 0.25 + m[0] * 0.75, c[1] * 0.25 + m[1] * 0.75); _rond(img, w_, 0.06 * hd, TRAIT); _rond(img, w_, 0.04 * hd, (235, 225, 200))
    for nom, cle in (("g", "main_g"), ("d", "main_d")):
        if p.get(cle) is not None: M._coller(img, p[cle], G["bras"][nom][2][0], G["bras"][nom][2][1] + 0.08 * hd)
    if p.get("effets"): M._effets(img, tete, rx, ry, sh, dict(p, s=sh))
    return tete, (rx, ry)

def _tronc(G):
    x, hd, dxp = G["x"], G["hd"], G["dxp"]; y_ep, y_ta, y_ha = G["y_ep"], G["y_ta"], G["y_ha"]
    l_ep, l_ta, l_ha = G["l_ep"], G["l_ta"], G["l_ha"]
    epaule = lambda sg: [(x + dxp + sg * (l_ep - 0.16 * hd) + sg * 0.16 * hd * math.cos(u), y_ep + 0.16 * hd - 0.16 * hd * math.sin(u)) for u in np.linspace(0, math.pi / 2, 6)]
    g = epaule(-1)[::-1]; d = epaule(1)
    return [(x + dxp - l_ep, y_ep + 0.2 * hd)] + g[::-1][::-1] + [(x + dxp, y_ep - 0.02 * hd)] + d[::-1] + \
           [(x + dxp + l_ep, y_ep + 0.2 * hd), (x + dxp * 0.5 + l_ta, y_ta), (x + l_ha * 0.98, y_ha + 0.02 * hd), (x - l_ha * 0.98, y_ha + 0.02 * hd), (x + dxp * 0.5 - l_ta, y_ta)]

def _ombre_poly(img, pts, lum, force):
    """Ombre nette du côté opposé à la lumière (comme sur nos marionnettes)."""
    xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    x0, y0, x1, y1 = int(max(0, min(xs))), int(max(0, min(ys))), int(min(img.shape[1], max(xs) + 1)), int(min(img.shape[0], max(ys) + 1))
    if x1 - x0 < 3 or y1 - y0 < 3: return
    m = np.zeros((y1 - y0, x1 - x0), np.uint8); cv2.fillPoly(m, [_pts([(a - x0, b - y0) for a, b in pts])], 255, AA, 2)
    lim = int((x1 - x0) * (0.72 if lum < 0 else 0.28))
    if lum < 0: m[:, :lim] = 0
    else: m[:, lim:] = 0
    z = img[y0:y1, x0:x1]; k = (256 * (1 - force + force * np.array(M.PEAU_OMBRE, np.float32) / 255)).astype(np.uint16); sel = m > 128
    z[sel] = ((z[sel].astype(np.uint16) * k) >> 8).astype(np.uint8)

def _teinte(img, t, rx, ry, teinte, force):
    x0, y0, x1, y1 = int(max(0, t[0] - rx)), int(max(0, t[1] - ry)), int(min(img.shape[1], t[0] + rx)), int(min(img.shape[0], t[1] + ry))
    if x1 <= x0 or y1 <= y0: return
    m = np.zeros((y1 - y0, x1 - x0), np.uint8); cv2.ellipse(m, (int(t[0] - x0), int(t[1] - y0)), (int(rx), int(ry)), 0, 0, 360, 255, -1)
    yy = np.arange(y0, y1, dtype=np.float32)[:, None]; g = np.clip((t[1] - ry + 2 * ry * min(1, force) - yy) / (ry * 0.9), 0, 1)
    a = (m.astype(np.float32) / 255 * 0.55 * g)[..., None]; z = img[y0:y1, x0:x1].astype(np.float32)
    img[y0:y1, x0:x1] = (z * (1 - a) + np.array(teinte, np.float32) * a).astype(np.uint8)

def _barbe(img, F, t, rx, ry, hd):
    """Barbe : une bande le long de la mâchoire et sous la bouche (courte : couleur des cheveux ; trois jours : ombre légère)."""
    c = M._fonce(F["c_cheveux"], 0.9) if F["barbe"] == "courte" else _melange(F["peau"], F["c_cheveux"], 0.2)
    ext = [(t[0] + rx * 0.97 * math.cos(u), t[1] + ry * 0.97 * math.sin(u)) for u in np.linspace(0.25, math.pi - 0.25, 16)]
    inte = [(t[0] + rx * 0.62 * math.cos(u), t[1] + ry * 0.55 + ry * 0.2 * math.sin(u)) for u in np.linspace(math.pi - 0.35, 0.35, 12)]
    _poly(img, ext + inte, c)

def _chaussure(img, c, hd, C, ep, sg):
    col = tuple(C.get("c_chaussures") or (50, 40, 35)); f = C.get("chaussures") or "ville"
    pts = _ell((c[0] + sg * 0.05 * hd, c[1] + 0.07 * hd), 0.17 * hd, 0.085 * hd)
    _contour(img, pts, 2 * ep); _poly(img, pts, col)
    if f == "baskets": _ligne(img, (c[0] - 0.1 * hd + sg * 0.05 * hd, c[1] + 0.13 * hd), (c[0] + 0.2 * hd * sg, c[1] + 0.13 * hd), (245, 245, 245), ep * 1.6)

def _motif(img, tronc, motif, c, hd):
    xs, ys = [q[0] for q in tronc], [q[1] for q in tronc]
    x0, y0, x1, y1 = int(max(0, min(xs))), int(max(0, min(ys))), int(min(img.shape[1], max(xs))), int(min(img.shape[0], max(ys)))
    if x1 - x0 < 4 or y1 - y0 < 4: return
    m = np.zeros((y1 - y0, x1 - x0), np.uint8); cv2.fillPoly(m, [_pts([(a - x0, b - y0) for a, b in tronc])], 255, AA, 2)
    z = img[y0:y1, x0:x1].copy(); pas = max(5, int(0.13 * hd))
    if motif == "rayures":
        for y in range(0, y1 - y0, pas): cv2.line(z, (0, y), (x1 - x0, y), c, max(1, pas // 3), AA)
    elif motif == "carreaux":
        for y in range(0, y1 - y0, pas): cv2.line(z, (0, y), (x1 - x0, y), c, max(1, pas // 4), AA)
        for xx in range(0, x1 - x0, pas): cv2.line(z, (xx, 0), (xx, y1 - y0), c, max(1, pas // 4), AA)
    else:
        for j, y in enumerate(range(pas // 2, y1 - y0, pas)):
            for xx in range(pas // 2 + (pas // 2 if j % 2 else 0), x1 - x0, pas): cv2.circle(z, (xx, y), max(1, pas // 5), c, -1, AA)
    a = (m.astype(np.float32) / 255)[..., None]; img[y0:y1, x0:x1] = (img[y0:y1, x0:x1] * (1 - a) + z * a).astype(np.uint8)

def _details(img, C, G, ep, haut, c_tr):
    """Col, boutons, cravate, capuche, revers de veste, tablier, badge, stéthoscope, ceinture, logo…"""
    x, hd = G["x"] + G["dxp"], G["hd"]; y_ep, y_ta = G["y_ep"], G["y_ta"]; det = C.get("details", ()) or (); f = M._fonce(c_tr, 0.65)
    if haut in ("tshirt", "pull", "robe", "debardeur", "pyjama", "survetement", "capuche"):
        _courbe(img, _ell((x, y_ep + 0.02 * hd), 0.16 * hd, 0.09 * hd, 0, 12, 0, math.pi), f, ep)
    if haut in ("chemise", "polo", "pyjama"):
        for sg in (-1, 1):
            col = [(x, y_ep + 0.12 * hd), (x + sg * 0.2 * hd, y_ep - 0.02 * hd), (x + sg * 0.19 * hd, y_ep + 0.12 * hd)]
            _poly(img, col, _melange(c_tr, (255, 255, 255), 0.25)); _contour(img, col, ep * 0.8)
        for k in range(3 if haut != "polo" else 1): _rond(img, (x, y_ep + (0.25 + 0.27 * k) * hd), 0.025 * hd, f)
        if haut == "chemise": _contour(img, [(x - 0.42 * hd, y_ep + 0.28 * hd), (x - 0.2 * hd, y_ep + 0.28 * hd), (x - 0.2 * hd, y_ep + 0.48 * hd), (x - 0.42 * hd, y_ep + 0.48 * hd)], ep * 0.7)
    if haut in ("costume", "blouse", "gilet"):
        dessous = tuple(C.get("c_dessous") or ((150, 190, 230) if haut == "blouse" else (246, 246, 246)))
        v = [(x - 0.17 * hd, y_ep), (x + 0.17 * hd, y_ep), (x + 0.03 * hd, y_ta), (x - 0.03 * hd, y_ta)]; _poly(img, v, dessous)
        for sg in (-1, 1): _courbe(img, [(x + sg * 0.17 * hd, y_ep), (x + sg * 0.25 * hd, y_ep + 0.35 * hd), (x + sg * 0.03 * hd, y_ta)], TRAIT, ep)
        if haut == "blouse":
            for sg in (-1, 1): _contour(img, [(x + sg * 0.18 * hd, y_ta + 0.1 * hd), (x + sg * 0.42 * hd, y_ta + 0.1 * hd), (x + sg * 0.42 * hd, y_ta + 0.32 * hd), (x + sg * 0.18 * hd, y_ta + 0.32 * hd)], ep * 0.7)
    if haut == "capuche":
        for sg in (-1, 1): _ligne(img, (x + sg * 0.07 * hd, y_ep + 0.05 * hd), (x + sg * 0.08 * hd, y_ep + 0.42 * hd), (245, 245, 245), ep)
        _contour(img, [(x - 0.33 * hd, y_ta - 0.25 * hd), (x + 0.33 * hd, y_ta - 0.25 * hd), (x + 0.4 * hd, y_ta + 0.12 * hd), (x - 0.4 * hd, y_ta + 0.12 * hd)], ep * 0.8)
    if haut == "survetement": _ligne(img, (x, y_ep + 0.05 * hd), (x, G["y_ha"]), f, ep)
    if haut == "tablier":
        ct = tuple(C.get("c_tablier") or (250, 250, 245))
        t_ = [(x - 0.3 * hd, y_ep + 0.15 * hd), (x + 0.3 * hd, y_ep + 0.15 * hd), (x + 0.45 * hd, G["y_ha"] + 0.3 * hd), (x - 0.45 * hd, G["y_ha"] + 0.3 * hd)]
        _poly(img, t_, ct); _contour(img, t_, ep)
    if "cravate" in det:
        ct = tuple(C.get("c_cravate") or (190, 40, 55))
        cr = [(x - 0.05 * hd, y_ep), (x + 0.05 * hd, y_ep), (x + 0.08 * hd, y_ta - 0.1 * hd), (x, y_ta + 0.02 * hd), (x - 0.08 * hd, y_ta - 0.1 * hd)]
        _poly(img, cr, ct); _contour(img, cr, ep * 0.8)
    if "noeud_pap" in det:
        for sg in (-1, 1):
            n_ = [(x, y_ep + 0.04 * hd), (x + sg * 0.14 * hd, y_ep - 0.03 * hd), (x + sg * 0.14 * hd, y_ep + 0.11 * hd)]; _poly(img, n_, tuple(C.get("c_cravate") or (40, 40, 50))); _contour(img, n_, ep * 0.7)
    if "stethoscope" in det:
        _courbe(img, _ell((x, y_ep + 0.05 * hd), 0.22 * hd, 0.25 * hd, 0, 14, 0, math.pi), (60, 60, 70), ep * 1.4); _rond(img, (x + 0.2 * hd, y_ep + 0.5 * hd), 0.06 * hd, (190, 195, 205))
    if "badge" in det:
        b = [(x + 0.25 * hd, y_ep + 0.28 * hd), (x + 0.45 * hd, y_ep + 0.28 * hd), (x + 0.45 * hd, y_ep + 0.42 * hd), (x + 0.25 * hd, y_ep + 0.42 * hd)]; _poly(img, b, (250, 250, 250)); _contour(img, b, ep * 0.7)
    if "collier" in det: _courbe(img, _ell((x, y_ep + 0.02 * hd), 0.14 * hd, 0.12 * hd, 0, 12, 0.2, math.pi - 0.2), (230, 195, 80), ep)
    if "echarpe" in det:
        ce = tuple(C.get("c_echarpe") or (200, 60, 60)); e_ = _ell((x, y_ep + 0.02 * hd), 0.3 * hd, 0.11 * hd); _poly(img, e_, ce); _contour(img, e_, ep)
    if "ceinture" in det and haut not in ("robe", "tablier", "blouse"):
        _ligne(img, (x - G["l_ta"] * 1.0, G["y_ha"] - 0.12 * hd), (x + G["l_ta"] * 1.0, G["y_ha"] - 0.12 * hd), (70, 45, 30), 0.06 * hd); _rond(img, (x, G["y_ha"] - 0.12 * hd), 0.04 * hd, (215, 185, 90))
    if "logo" in det and haut in ("tshirt", "capuche", "pull", "survetement"): _rond(img, (x, y_ep + 0.45 * hd), 0.1 * hd, _melange(c_tr, (255, 255, 255), 0.5))

def _main(img, m, direction, forme, hd, peau, ep, gauche, contour_seul=False):
    """Main de dessin animé : paume, quatre doigts et pouce (ouverte, poing, index pointé, pouce levé, paume « stop »)."""
    dx, dy = math.sin(direction), math.cos(direction); nx, ny = -dy, dx
    if gauche: nx, ny = -nx, -ny
    r = 0.085 * hd; c = (m[0] + dx * r * 0.6, m[1] + dy * r * 0.6)
    formes = []
    if forme in ("ouverte", "paume"):
        e = 0.28 if forme == "paume" else 0.14
        for k in range(4): formes.append(("doigt", (c[0] + dx * r * 0.7 + nx * r * (0.55 - 0.37 * k), c[1] + dy * r * 0.7 + ny * r * (0.55 - 0.37 * k)), direction + (k - 1.5) * e, 0.14 * hd, 0.028 * hd))
        formes.append(("doigt", (c[0] + nx * r * 0.85, c[1] + ny * r * 0.85), direction + (1.1 if not gauche else -1.1), 0.1 * hd, 0.03 * hd))
    elif forme == "index": formes.append(("doigt", (c[0] + dx * r * 0.6 + nx * r * 0.4, c[1] + dy * r * 0.6 + ny * r * 0.4), direction, 0.17 * hd, 0.028 * hd))
    elif forme == "pouce": formes.append(("doigt", (c[0] + nx * r * 0.5, c[1] - r * 0.4), math.pi, 0.13 * hd, 0.03 * hd))
    def doigt(base, ang, L, e):
        bout = (base[0] + math.sin(ang) * L, base[1] + math.cos(ang) * L); return _tube([base, bout], [e, e * 0.9])
    pts_paume = _ell(c, r * (1.05 if forme != "poing" else 0.95), r * (1.1 if forme in ("ouverte", "paume") else 0.9), -direction)
    if contour_seul:
        for _, b, a, L, e in formes: _contour(img, doigt(b, a, L, e), 2 * ep)
        _contour(img, pts_paume, 2 * ep); return
    for _, b, a, L, e in formes: _poly(img, doigt(b, a, L, e), peau)
    _poly(img, pts_paume, peau)
    if forme in ("poing", "index", "pouce"):
        for k in range(3): _ligne(img, (c[0] + nx * r * (0.5 - 0.45 * k) + dx * r * 0.4, c[1] + ny * r * (0.5 - 0.45 * k) + dy * r * 0.4),
                                  (c[0] + nx * r * (0.5 - 0.45 * k) + dx * r * 0.85, c[1] + ny * r * (0.5 - 0.45 * k) + dy * r * 0.85), TRAIT, ep * 0.6)
