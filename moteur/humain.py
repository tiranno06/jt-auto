"""Personnages humains ADULTES dessinés en volume (2D « semi-réaliste »), différents à chaque vidéo (casting libre).

Chaque personnage est une FICHE (creer) : genre, âge, corpulence, taille, couleur de peau, forme du visage, yeux (couleur, taille),
nez, lèvres, sourcils, coiffure et couleur des cheveux (grisonnants avec l'âge), barbe ou moustache, lunettes, rides.
Le dessin (dessiner) reprend EXACTEMENT les mêmes commandes de pose que les marionnettes (marionnette.py) : bras (épaule, coude),
forme des mains, bouche synchronisée (visèmes), yeux, sourcils et leur hauteur, coins de la bouche, yeux plissés, pupilles,
regard, tête penchée, épaules, buste, pied, costume, objets tenus, effets, vue de dos : toute la mise en scène du studio s'applique.

Rendu « en volume » : chaque partie du corps est remplie puis ombrée d'après sa forme (plus sombre vers les bords, plus claire
du côté de la lumière), avec un contour fin de sa propre couleur assombrie (et non un trait noir de dessin animé).
Proportions d'adulte : environ 7 têtes de haut, épaules, taille et hanches selon le genre et la corpulence, mains à cinq doigts."""
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

# ------------------------------------------------------------------ géométrie et volume
def _pts(pts): return np.array([[int(round(x * 4)), int(round(y * 4))] for x, y in pts], np.int32).reshape(-1, 1, 2)

def _forme(img, pts, couleur, lum=-1, rondeur=0.3, contour=True, ep=2.0):
    """Remplit un polygone en VOLUME : ombré vers les bords, éclairé du côté de la lumière ; contour fin de la même teinte assombrie."""
    pts = [(float(x), float(y)) for x, y in pts]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0 = int(max(0, min(xs) - 3)), int(max(0, min(ys) - 3)); x1, y1 = int(min(img.shape[1], max(xs) + 4)), int(min(img.shape[0], max(ys) + 4))
    if x1 - x0 < 2 or y1 - y0 < 2: return
    m = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.fillPoly(m, [_pts([(x - x0, y - y0) for x, y in pts])], 255, AA, 2)
    if not m.any(): return
    d = cv2.distanceTransform((m > 127).astype(np.uint8), cv2.DIST_L2, 3); dm = float(d.max()) or 1.0
    vol = 1 - rondeur + rondeur * np.sqrt(np.clip(d / dm, 0, 1))
    xx = (np.arange(x1 - x0, dtype=np.float32)[None, :] - (x1 - x0) / 2) / max(1.0, (x1 - x0) / 2)
    vol = vol * (1 + 0.1 * lum * xx)
    a = (m.astype(np.float32) / 255)[..., None]
    col = np.clip(np.array(couleur, np.float32)[None, None, :] * vol[..., None], 0, 255)
    z = img[y0:y1, x0:x1]; img[y0:y1, x0:x1] = (z * (1 - a) + col * a).astype(np.uint8)
    if contour: cv2.polylines(img, [_pts(pts)], True, _fonce(couleur, 0.5), max(1, int(round(ep))), AA, 2)

def _ellipse_pts(c, rx, ry, ang=0.0, n=36, a0=0.0, a1=2 * math.pi):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(c[0] + rx * math.cos(t) * ca - ry * math.sin(t) * sa, c[1] + rx * math.cos(t) * sa + ry * math.sin(t) * ca) for t in np.linspace(a0, a1, n)]

def _membre(a, b, ra, rb):
    """Contour d'un membre fuselé de a (rayon ra) à b (rayon rb), bouts arrondis."""
    dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy) or 1; nx, ny = -dy / L, dx / L; ang = math.atan2(dy, dx)
    pts = [(a[0] + nx * ra, a[1] + ny * ra), (b[0] + nx * rb, b[1] + ny * rb)]
    pts += [(b[0] + rb * math.cos(ang + math.pi / 2 - t), b[1] + rb * math.sin(ang + math.pi / 2 - t)) for t in np.linspace(0, math.pi, 8)]
    pts += [(b[0] - nx * rb, b[1] - ny * rb), (a[0] - nx * ra, a[1] - ny * ra)]
    pts += [(a[0] + ra * math.cos(ang - math.pi / 2 - t), a[1] + ra * math.sin(ang - math.pi / 2 - t)) for t in np.linspace(0, math.pi, 8)]
    return pts

def _ligne(img, a, b, c, ep): cv2.line(img, (int(a[0] * 4), int(a[1] * 4)), (int(b[0] * 4), int(b[1] * 4)), c, max(1, int(round(ep))), AA, 2)
def _courbe(img, pts, c, ep): cv2.polylines(img, [_pts(pts)], False, c, max(1, int(round(ep))), AA, 2)
def _rond(img, c, r, col): cv2.circle(img, (int(c[0] * 4), int(c[1] * 4)), max(1, int(r * 4)), col, -1, AA, 2)

def tete_y(s, taille=1.0):
    """Hauteur du centre de la tête pour des pieds à y=1500 (cadrages du moteur)."""
    hh = 122 * s * taille; return 1500 - 6.6 * hh + 0.52 * hh

def hauteur_tete(s, taille=1.0): return 122 * s * taille

# ------------------------------------------------------------------ repères (pour poser objets et effets sur un personnage rendu en 3D)
def reperes(F, p):
    """Centre et rayons de la tête, positions des deux mains, avec la même géométrie que dessiner()."""
    s = p["s"]; hh = 122 * s * F["taille"]; sq = p.get("sq", 0.0); x, Y = p["x"], p["y"]
    Ht = 6.6 * hh * (1 - 0.35 * max(0.0, sq)) * (1 + 0.15 * max(0.0, -sq)); yb = lambda k: Y - Ht + k * hh * (Ht / (6.6 * hh))
    epaules, penche = float(p.get("epaules", 0.0)), float(p.get("penche", 0.0)); dx_p = penche * 0.25 * hh; corp = F["corpulence"]
    l_ep = hh * (0.98 if F["genre"] != "f" else 0.82) * (1 + 0.22 * corp); y_ep = yb(1.27) - epaules * 0.18 * hh
    tete = (x + dx_p + math.sin(math.radians(p.get("tilt", 0))) * 0.3 * hh, yb(0.52) + epaules * 0.12 * hh)
    mains = []
    for sg, cle in ((-1, "bras_g"), (1, "bras_d")):
        ang = p.get(cle, (0, 0)); a1, a2 = math.radians(ang[0]), math.radians(ang[0] + ang[1])
        e = (x + dx_p + sg * l_ep * 0.92, y_ep + 0.12 * hh); c = (e[0] + math.sin(a1) * 1.2 * hh, e[1] + math.cos(a1) * 1.2 * hh)
        mains.append((c[0] + math.sin(a2) * 1.02 * hh, c[1] + math.cos(a2) * 1.02 * hh))
    return tete, (hh * 0.39, hh * 0.5), mains

# ------------------------------------------------------------------ dessin
def dessiner(img, F, p):
    """Dessine le personnage de fiche F dans img selon la pose p (mêmes clés que marionnette.dessiner). Renvoie (tête, (rx, ry))."""
    s = p["s"]; hh = 122 * s * F["taille"]; lum = p.get("lumiere", 0) or -1; C = p.get("costume") or {}
    corp = F["corpulence"]; fem = F["genre"] == "f"; sq = p.get("sq", 0.0)
    x = p["x"] + (math.sin(p["t"] * 61) * 7 * p["tremble"] if p.get("tremble") else 0); Y = p["y"]
    ep_ = max(1.5, 2.2 * s)
    epaules, penche = float(p.get("epaules", 0.0)), float(p.get("penche", 0.0))
    Ht = 6.6 * hh * (1 - 0.35 * max(0.0, sq)) * (1 + 0.15 * max(0.0, -sq))
    yb = lambda k: Y - Ht + k * hh * (Ht / (6.6 * hh))                    # repère vertical en « têtes » depuis le haut
    dx_p = penche * 0.25 * hh                                              # le buste penche
    # ombre au sol
    cv2.ellipse(img, (int(x * 4), int((Y + 4 * s) * 4)), (int(hh * (1.1 + 0.4 * corp) * 4), int(hh * 0.16 * 4)), 0, 0, 360,
                tuple(int(v * 0.78) for v in M._fond(img, x, Y + 4 * s)), -1, AA, 2)
    l_ep = hh * (0.98 if not fem else 0.82) * (1 + 0.22 * corp); l_ta = hh * (0.6 if not fem else 0.5) * (1 + 0.55 * corp)
    l_ha = hh * (0.66 if not fem else 0.8) * (1 + 0.35 * corp)
    y_ep = yb(1.27) - epaules * 0.18 * hh; y_ta = yb(2.65); y_ha = yb(3.25); y_ent = yb(3.5)
    tete = (x + dx_p + math.sin(math.radians(p.get("tilt", 0))) * 0.3 * hh, yb(0.52) + epaules * 0.12 * hh)
    rx, ry = hh * 0.39 * (1.06 if F["visage"] == "rond" else (0.94 if F["visage"] == "long" else 1)), hh * 0.5 * (1.05 if F["visage"] == "long" else 1)
    dos = bool(p.get("dos")); tilt = math.radians(p.get("tilt", 0) * 0.6)
    peau = F["peau"]; haut = C.get("haut") or "tshirt"; c_haut = C.get("c_haut") or (120, 140, 170)
    if haut == "blouse": c_haut = (244, 246, 250)
    bas = C.get("bas") or "pantalon"; c_bas = C.get("c_bas") or (60, 70, 90)
    # cheveux derrière la tête
    if F["cheveux"] in ("long", "carre", "queue", "chignon", "boucles", "mi_long"): _cheveux_arriere(img, F, tete, rx, ry, p, lum, dos)
    # jambes
    pied = float(p.get("pied", 0.0)); jambes = []
    for sg in (-1, 1):
        hanche = (x + sg * l_ha * 0.5, y_ha + 0.05 * hh); genou = (x + sg * l_ha * 0.5, yb(4.95)); cheville = (x + sg * l_ha * 0.52, Y - 0.22 * hh - (pied * 0.25 * hh if sg > 0 else 0))
        jambes.append((hanche, genou, cheville))
    for hanche, genou, cheville in jambes:
        r_c, r_g, r_m = max(hh * (0.3 + 0.08 * corp), l_ha * 0.5), hh * (0.2 + 0.04 * corp), hh * 0.14   # la cuisse prolonge la hanche
        nu_haut = bas == "jupe" or haut == "robe"; c_cuisse = peau if nu_haut else c_bas
        c_tibia = peau if (bas in ("short", "jupe") or haut == "robe") else c_bas
        _forme(img, _membre(hanche, genou, r_c, r_g), c_cuisse, lum, ep=ep_)
        _forme(img, _membre(genou, cheville, r_g, r_m), c_tibia, lum, ep=ep_)
        if bas == "jean" and c_tibia == c_bas: _ligne(img, (genou[0] - r_g * 0.2, genou[1]), (cheville[0] - r_m * 0.2, cheville[1] - hh * 0.1), _fonce(c_bas, 0.8), ep_)
        _chaussure(img, cheville, hh, C, lum, ep_, sg=1 if cheville[0] > x else -1)
    # buste (vêtement)
    tronc = [(x - l_ep + dx_p, y_ep + 0.05 * hh)] + [(x + dx_p + l_ep * math.cos(t), y_ep + 0.05 * hh - 0.28 * hh * math.sin(t)) for t in np.linspace(math.pi, 0, 9)] + \
            [(x + l_ep + dx_p, y_ep + 0.05 * hh), (x + l_ta + dx_p * 0.5, y_ta)]
    y_bas_haut = y_ent + 0.1 * hh if haut in ("blouse", "robe", "tablier") else y_ha - 0.05 * hh   # le haut s'arrête aux hanches (sauf vêtements longs)
    tronc += [(x + l_ha * 0.98, y_bas_haut), (x - l_ha * 0.98, y_bas_haut), (x - l_ta + dx_p * 0.5, y_ta)]
    if haut == "robe" or bas == "jupe":                                    # jupe / bas de robe jusqu'aux genoux
        c_j = c_haut if haut == "robe" else c_bas
        _forme(img, [(x - l_ha * 1.0, y_ha - 0.2 * hh), (x + l_ha * 1.0, y_ha - 0.2 * hh), (x + l_ha * 1.35, yb(5.05)), (x - l_ha * 1.35, yb(5.05))], c_j, lum, rondeur=0.2, ep=ep_)
    elif bas in ("jean", "pantalon", "jogging", "short"):
        _forme(img, [(x - l_ta * 1.02, y_ta + 0.1 * hh), (x + l_ta * 1.02, y_ta + 0.1 * hh), (x + l_ha * 0.98, y_ha), (x + l_ha * 0.9, y_ent + 0.2 * hh), (x - l_ha * 0.9, y_ent + 0.2 * hh), (x - l_ha * 0.98, y_ha)], c_bas, lum, rondeur=0.2, ep=ep_)
    c_tr = c_haut
    if haut in ("costume", "blouse", "gilet"):                             # veste ouverte sur une chemise
        _forme(img, tronc, c_tr, lum, ep=ep_)
        dessous = C.get("c_dessous") or ((150, 190, 230) if haut == "blouse" else (246, 246, 246))
        _forme(img, [(x + dx_p - 0.32 * hh, y_ep - 0.12 * hh), (x + dx_p + 0.32 * hh, y_ep - 0.12 * hh), (x + dx_p * 0.6 + 0.08 * hh, y_ta + 0.1 * hh), (x + dx_p * 0.6 - 0.08 * hh, y_ta + 0.1 * hh)], dessous, lum, rondeur=0.15, contour=False)
        for sg in (-1, 1): _courbe(img, [(x + dx_p + sg * 0.32 * hh, y_ep - 0.12 * hh), (x + dx_p * 0.6 + sg * 0.1 * hh, y_ta + 0.1 * hh)], _fonce(c_tr, 0.55), ep_ * 1.2)
    else:
        _forme(img, tronc, c_tr, lum, ep=ep_)
        if C.get("motif") in ("rayures", "carreaux", "pois"): _motif(img, tronc, C["motif"], C.get("c_motif") or _fonce(c_tr, 0.75), hh)
    _details_buste(img, C, x + dx_p, y_ep, y_ta, l_ep, hh, ep_, haut, c_tr, fem)
    # cou
    cou = [(tete[0] - 0.17 * hh, tete[1] + ry * 0.75), (tete[0] + 0.17 * hh, tete[1] + ry * 0.75), (x + dx_p + 0.2 * hh, y_ep - 0.05 * hh), (x + dx_p - 0.2 * hh, y_ep - 0.05 * hh)]
    _forme(img, cou, _fonce(peau, 0.9), lum, rondeur=0.25, contour=False)
    if haut in ("tshirt", "pull", "debardeur", "robe", "polo", "capuche", "survetement", "pyjama"):
        cv2.ellipse(img, (int((x + dx_p) * 4), int((y_ep - 0.08 * hh) * 4)), (int(0.24 * hh * 4), int(0.12 * hh * 4)), 0, 0, 180, _fonce(c_tr, 0.6), max(1, int(ep_)), AA, 2)
    # tête
    if dos: _forme(img, _ellipse_pts(tete, rx, ry, tilt), peau, lum, rondeur=0.35, ep=ep_)
    else: _visage(img, F, tete, rx, ry, tilt, p, lum, ep_, s)
    _cheveux_avant(img, F, tete, rx, ry, tilt, p, lum, dos, ep_)
    if F.get("lunettes") and not dos: _lunettes(img, F, tete, rx, ry, tilt, ep_)
    # bras et mains (devant)
    ep_g = (x + dx_p - l_ep * 0.92, y_ep + 0.12 * hh); ep_d = (x + dx_p + l_ep * 0.92, y_ep + 0.12 * hh)
    manche = haut not in ("debardeur", "robe") or haut == "robe" and False
    courte = haut in ("tshirt", "polo", "debardeur")
    c_manche = C.get("c_manche") or c_tr
    mains_xy = []
    for epaule, ang, nom in ((ep_g, p["bras_g"], "g"), (ep_d, p["bras_d"], "d")):
        a1, a2 = math.radians(ang[0]), math.radians(ang[0] + ang[1])
        coude = (epaule[0] + math.sin(a1) * 1.2 * hh, epaule[1] + math.cos(a1) * 1.2 * hh)
        poignet = (coude[0] + math.sin(a2) * 1.02 * hh, coude[1] + math.cos(a2) * 1.02 * hh)
        r_b, r_c, r_p = hh * (0.17 + 0.06 * corp), hh * (0.14 + 0.04 * corp), hh * 0.1
        _forme(img, _membre(epaule, coude, r_b, r_c), peau if haut == "debardeur" else c_manche, lum, ep=ep_)
        _forme(img, _membre(coude, poignet, r_c, r_p), peau if (courte or haut == "debardeur") else c_manche, lum, ep=ep_)
        if courte and haut != "debardeur": _forme(img, _membre(epaule, (epaule[0] + (coude[0] - epaule[0]) * 0.55, epaule[1] + (coude[1] - epaule[1]) * 0.55), r_b * 1.08, r_b * 1.04), c_manche, lum, ep=ep_)
        if not courte and haut != "debardeur":                             # poignet de manche
            _ligne(img, (poignet[0] - r_p * 1.1, poignet[1]), (poignet[0] + r_p * 1.1, poignet[1]), _fonce(c_manche, 0.6), ep_)
        forme = p.get("main_forme_" + nom) or "ouverte"
        _main(img, poignet, a2, forme, hh, peau, lum, ep_, gauche=(nom == "g"))
        mains_xy.append(poignet)
    if "montre" in C.get("details", ()):
        _rond(img, mains_xy[0], 0.07 * hh, (60, 60, 70)); _rond(img, mains_xy[0], 0.045 * hh, (235, 225, 200))
    for nom, xy in (("main_g", mains_xy[0]), ("main_d", mains_xy[1])):    # objet tenu
        if p.get(nom) is not None: M._coller(img, p[nom], xy[0], xy[1] + 0.25 * hh)
    if p.get("effets"): M._effets(img, tete, rx * 1.15, ry * 1.05, rx / 150 * 1.6, p)   # effets comiques à l'échelle d'une tête d'adulte
    return tete, (rx, ry)

def _chaussure(img, cheville, hh, C, lum, ep_, sg):
    col = C.get("c_chaussures") or (50, 40, 35); f = C.get("chaussures") or "ville"
    c = (cheville[0] + sg * 0.08 * hh, cheville[1] + 0.12 * hh)
    _forme(img, _ellipse_pts(c, 0.24 * hh, 0.11 * hh), col, lum, rondeur=0.4, ep=ep_)
    if f == "baskets": _ligne(img, (c[0] - 0.2 * hh, c[1] + 0.06 * hh), (c[0] + 0.2 * hh, c[1] + 0.06 * hh), (245, 245, 245), ep_ * 2.2)
    if f == "bottes": _forme(img, _membre((cheville[0], cheville[1] - 0.45 * hh), (cheville[0], cheville[1] + 0.05 * hh), 0.15 * hh, 0.14 * hh), col, lum, ep=ep_)

def _motif(img, tronc, motif, c, hh):
    xs, ys = [p[0] for p in tronc], [p[1] for p in tronc]
    x0, y0, x1, y1 = int(max(0, min(xs))), int(max(0, min(ys))), int(min(img.shape[1], max(xs))), int(min(img.shape[0], max(ys)))
    if x1 - x0 < 4 or y1 - y0 < 4: return
    m = np.zeros((y1 - y0, x1 - x0), np.uint8); cv2.fillPoly(m, [_pts([(x - x0, y - y0) for x, y in tronc])], 255, AA, 2)
    z = img[y0:y1, x0:x1].copy(); pas = max(5, int(0.16 * hh))
    if motif == "rayures":
        for y in range(0, y1 - y0, pas): cv2.line(z, (0, y), (x1 - x0, y), c, max(1, pas // 3), AA)
    elif motif == "carreaux":
        for y in range(0, y1 - y0, pas): cv2.line(z, (0, y), (x1 - x0, y), c, max(1, pas // 4), AA)
        for xx in range(0, x1 - x0, pas): cv2.line(z, (xx, 0), (xx, y1 - y0), c, max(1, pas // 4), AA)
    else:
        for j, y in enumerate(range(pas // 2, y1 - y0, pas)):
            for xx in range(pas // 2 + (pas // 2 if j % 2 else 0), x1 - x0, pas): cv2.circle(z, (xx, y), max(1, pas // 5), c, -1, AA)
    a = (m.astype(np.float32) / 255 * 0.9)[..., None]; img[y0:y1, x0:x1] = (img[y0:y1, x0:x1] * (1 - a) + z * a).astype(np.uint8)

def _details_buste(img, C, x, y_ep, y_ta, l_ep, hh, ep_, haut, c_tr, fem):
    det = C.get("details", ()) or ()
    if haut in ("chemise", "polo", "pyjama"):                              # col et boutons
        for sg in (-1, 1): _forme(img, [(x, y_ep + 0.05 * hh), (x + sg * 0.3 * hh, y_ep - 0.12 * hh), (x + sg * 0.26 * hh, y_ep + 0.14 * hh)], _melange(c_tr, (255, 255, 255), 0.2), -1, 0.1, ep=ep_)
        for k in range(3 if haut != "polo" else 1): _rond(img, (x, y_ep + (0.3 + 0.35 * k) * hh), 0.035 * hh, _fonce(c_tr, 0.6))
    if haut == "capuche":
        for sg in (-1, 1): _ligne(img, (x + sg * 0.1 * hh, y_ep), (x + sg * 0.12 * hh, y_ep + 0.55 * hh), (240, 240, 240), ep_)
        _forme(img, [(x - 0.45 * hh, y_ta - 0.35 * hh), (x + 0.45 * hh, y_ta - 0.35 * hh), (x + 0.55 * hh, y_ta + 0.15 * hh), (x - 0.55 * hh, y_ta + 0.15 * hh)], _fonce(c_tr, 0.85), -1, 0.1, ep=ep_)
    if haut == "survetement":
        _ligne(img, (x, y_ep), (x, y_ta + 0.6 * hh), _fonce(c_tr, 0.6), ep_)
    if haut == "tablier":
        ct = C.get("c_tablier") or (250, 250, 245)
        _forme(img, [(x - 0.42 * hh, y_ep + 0.15 * hh), (x + 0.42 * hh, y_ep + 0.15 * hh), (x + 0.6 * hh, y_ta + 0.9 * hh), (x - 0.6 * hh, y_ta + 0.9 * hh)], ct, -1, 0.15, ep=ep_)
    if "cravate" in det:
        ct = C.get("c_cravate") or (180, 40, 55)
        _forme(img, [(x - 0.07 * hh, y_ep - 0.02 * hh), (x + 0.07 * hh, y_ep - 0.02 * hh), (x + 0.11 * hh, y_ta - 0.1 * hh), (x, y_ta + 0.05 * hh), (x - 0.11 * hh, y_ta - 0.1 * hh)], ct, -1, 0.2, ep=ep_)
    if "noeud_pap" in det:
        for sg in (-1, 1): _forme(img, [(x, y_ep), (x + sg * 0.2 * hh, y_ep - 0.09 * hh), (x + sg * 0.2 * hh, y_ep + 0.09 * hh)], C.get("c_cravate") or (40, 40, 50), -1, 0.1, ep=ep_)
    if "stethoscope" in det:
        cv2.ellipse(img, (int(x * 4), int(y_ep * 4)), (int(0.3 * hh * 4), int(0.35 * hh * 4)), 0, 0, 180, (60, 60, 70), max(1, int(ep_ * 1.5)), AA, 2)
        _rond(img, (x + 0.28 * hh, y_ep + 0.65 * hh), 0.08 * hh, (190, 195, 205))
    if "badge" in det:
        _forme(img, [(x + 0.35 * hh, y_ep + 0.35 * hh), (x + 0.62 * hh, y_ep + 0.35 * hh), (x + 0.62 * hh, y_ep + 0.55 * hh), (x + 0.35 * hh, y_ep + 0.55 * hh)], (250, 250, 250), -1, 0.05, ep=ep_)
    if "collier" in det:
        cv2.ellipse(img, (int(x * 4), int((y_ep - 0.05 * hh) * 4)), (int(0.22 * hh * 4), int(0.2 * hh * 4)), 0, 10, 170, (230, 195, 80), max(1, int(ep_)), AA, 2)
    if "echarpe" in det:
        ce = C.get("c_echarpe") or (200, 60, 60)
        _forme(img, _ellipse_pts((x, y_ep - 0.05 * hh), 0.42 * hh, 0.16 * hh), ce, -1, 0.3, ep=ep_)
        _forme(img, [(x + 0.1 * hh, y_ep), (x + 0.28 * hh, y_ep), (x + 0.3 * hh, y_ep + 0.75 * hh), (x + 0.12 * hh, y_ep + 0.75 * hh)], ce, -1, 0.2, ep=ep_)
    if "ceinture" in det and haut not in ("robe", "tablier", "blouse"):
        _ligne(img, (x - 0.62 * hh, y_ta + 0.62 * hh), (x + 0.62 * hh, y_ta + 0.62 * hh), (70, 45, 30), 0.08 * hh)
        _rond(img, (x, y_ta + 0.62 * hh), 0.05 * hh, (215, 185, 90))
    if "logo" in det and haut in ("tshirt", "capuche", "pull", "survetement"):
        _rond(img, (x, y_ep + 0.6 * hh), 0.14 * hh, _melange(c_tr, (255, 255, 255), 0.5))

def _main(img, poignet, direction, forme, hh, peau, lum, ep_, gauche):
    """Main à cinq doigts : ouverte, poing, index pointé, pouce levé, paume (« stop »)."""
    dx, dy = math.sin(direction), math.cos(direction); nx, ny = -dy, dx
    if gauche: nx, ny = -nx, -ny
    paume = (poignet[0] + dx * 0.16 * hh, poignet[1] + dy * 0.16 * hh); r = 0.13 * hh
    c_d = _fonce(peau, 0.96)
    def doigt(base, ang_off, long_, ep_d):
        a = direction + ang_off; bout = (base[0] + math.sin(a) * long_, base[1] + math.cos(a) * long_)
        _forme(img, _membre(base, bout, ep_d, ep_d * 0.85), c_d, lum, rondeur=0.3, ep=ep_ * 0.8)
    if forme in ("ouverte", "paume"):
        ecart = 0.22 if forme == "paume" else 0.1
        for k in range(4): doigt((paume[0] + dx * r * 0.6 + nx * r * (0.6 - 0.4 * k), paume[1] + dy * r * 0.6 + ny * r * (0.6 - 0.4 * k)), (k - 1.5) * ecart, 0.2 * hh * (1 - 0.12 * abs(k - 1.2)), 0.04 * hh)
        doigt((paume[0] + nx * r * 0.8, paume[1] + ny * r * 0.8), 1.0 if not gauche else -1.0, 0.16 * hh, 0.045 * hh)
    elif forme == "index":
        doigt((paume[0] + dx * r * 0.5 + nx * r * 0.45, paume[1] + dy * r * 0.5 + ny * r * 0.45), 0.0, 0.26 * hh, 0.042 * hh)
    elif forme == "pouce":
        a = math.pi if dy > 0 else 0.0; base = (paume[0] + nx * r * 0.5, paume[1] - r * 0.3)
        _forme(img, _membre(base, (base[0], base[1] - 0.2 * hh), 0.05 * hh, 0.042 * hh), c_d, lum, ep=ep_ * 0.8)
    _forme(img, _ellipse_pts(paume, r * (1.05 if forme != "poing" else 0.95), r * (1.1 if forme in ("ouverte", "paume") else 0.9), direction), peau, lum, rondeur=0.35, ep=ep_ * 0.8)
    if forme in ("poing", "index", "pouce"):
        for k in range(3): _ligne(img, (paume[0] + nx * r * (0.5 - 0.4 * k) + dx * r * 0.5, paume[1] + ny * r * (0.5 - 0.4 * k) + dy * r * 0.5),
                                  (paume[0] + nx * r * (0.5 - 0.4 * k) + dx * r * 0.85, paume[1] + ny * r * (0.5 - 0.4 * k) + dy * r * 0.85), _fonce(peau, 0.6), ep_ * 0.7)

# ------------------------------------------------------------------ visage
def _visage(img, F, t, rx, ry, tilt, p, lum, ep_, s):
    cx, cy = t
    def R(px, py): return M._rot(px, py, cx, cy, tilt)
    peau = F["peau"]; carre = 0.35 if F["visage"] == "carre" else (0.12 if F["genre"] == "h" else 0.0)
    pts = []
    for a in np.linspace(0, 2 * math.pi, 48, endpoint=False):              # visage : ovale, mâchoire plus carrée chez certains
        c_, s_ = math.cos(a), math.sin(a)
        if s_ > 0: c_ = math.copysign(abs(c_) ** (1 - carre), c_); yy = cy + ry * s_ * (1 - 0.06 * carre)
        else: yy = cy + ry * s_
        pts.append(R(cx + rx * c_, yy))
    for sg in (-1, 1):                                                     # oreilles
        _forme(img, _ellipse_pts(R(cx + sg * rx * 0.98, cy + ry * 0.08), rx * 0.14, ry * 0.2, tilt), _fonce(peau, 0.95), lum, rondeur=0.4, ep=ep_)
    _forme(img, pts, peau, lum, rondeur=0.32, ep=ep_)
    hz = float(p.get("sourcils_h", 0.0)); gx, gy = p.get("regard", (0.0, 0.0))
    yeux, pa = p.get("yeux", "ouverts"), float(p.get("paupiere", 0.0)); pl = float(p.get("plisse", 0.0)); pu = float(np.clip(p.get("pupille", 1.0), 0.6, 1.5))
    if yeux == "heureux": pl = max(pl, 0.7)
    if yeux == "plisses": pl = max(pl, 0.85)
    if yeux == "vides": pa = max(pa, 0.5)
    if yeux == "fermes": pa = 1.0
    ew, eh = rx * 0.27 * F["yeux"], ry * 0.12 * F["yeux"] * (1.35 if yeux in ("grands", "minuscules") else 1.0)
    for sg in (-1, 1):
        ox, oy = cx + sg * rx * 0.4, cy - ry * 0.02
        # œil : blanc en amande, iris coloré, pupille, reflet, paupières
        oeil = [R(ox + ew * math.cos(a), oy + eh * math.sin(a) * (1.0 if math.sin(a) < 0 else 0.85)) for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        if pa < 0.95:
            cv2.fillPoly(img, [_pts(oeil)], (248, 246, 242), AA, 2)
            ir = eh * 0.95; kx, ky = gx * ew * 0.45, gy * eh * 0.5 - (eh * 0.6 if yeux == "roule" else 0)
            if yeux == "louche": kx = sg * ew * 0.4
            ic = R(ox + kx, oy + ky)
            m = np.zeros(img.shape[:2], np.uint8) if False else None
            x0, y0 = int(ox - ew - 3), int(oy - eh * 2); x1, y1 = int(ox + ew + 3), int(oy + eh * 2)
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(img.shape[1], x1), min(img.shape[0], y1)
            if x1 > x0 and y1 > y0:                                        # iris et pupille découpés dans le blanc de l'œil
                zone = img[y0:y1, x0:x1].copy(); mk = np.zeros(zone.shape[:2], np.uint8)
                cv2.fillPoly(mk, [_pts([(a - x0, b - y0) for a, b in oeil])], 255, AA, 2)
                cv2.circle(zone, (int((ic[0] - x0) * 4), int((ic[1] - y0) * 4)), int(ir * 4), F["iris"], -1, AA, 2)
                cv2.circle(zone, (int((ic[0] - x0) * 4), int((ic[1] - y0) * 4)), int(ir * 4), _fonce(F["iris"], 0.55), max(1, int(ep_ * 0.6)), AA, 2)
                cv2.circle(zone, (int((ic[0] - x0) * 4), int((ic[1] - y0) * 4)), int(ir * (0.25 if yeux == "minuscules" else 0.45 * pu) * 4), (16, 14, 16), -1, AA, 2)
                cv2.circle(zone, (int((ic[0] - x0 + lum * ir * 0.35) * 4), int((ic[1] - y0 - ir * 0.35) * 4)), int(ir * 0.22 * 4), (255, 255, 255), -1, AA, 2)
                a_ = (mk.astype(np.float32) / 255)[..., None]; img[y0:y1, x0:x1] = (img[y0:y1, x0:x1] * (1 - a_) + zone * a_).astype(np.uint8)
            p_loc = M._fond(img, ox, oy - eh * 1.8); j_loc = M._fond(img, ox, oy + eh * 2.0)   # peau ombrée autour de l'œil
            if pa > 0.05:                                                  # paupière supérieure qui descend
                cv2.fillPoly(img, [_pts([R(ox - ew * 1.1, oy - eh * 1.3), R(ox + ew * 1.1, oy - eh * 1.3), R(ox + ew * 1.1, oy - eh + 2 * eh * pa), R(ox - ew * 1.1, oy - eh + 2 * eh * pa)])], _fonce(p_loc, 0.95), AA, 2)
                _ligne(img, R(ox - ew, oy - eh + 2 * eh * pa), R(ox + ew, oy - eh + 2 * eh * pa), (60, 40, 40), ep_ * 1.2)
            if pl > 0.1:                                                   # joue qui remonte (sourire)
                cv2.fillPoly(img, [_pts([R(ox - ew * 1.1, oy + eh * (1 - 1.6 * pl)), R(ox + ew * 1.1, oy + eh * (1 - 1.6 * pl)), R(ox + ew * 1.1, oy + eh * 1.6), R(ox - ew * 1.1, oy + eh * 1.6)])], j_loc, AA, 2)
                _courbe(img, [R(ox + ew * math.cos(a), oy + eh * (1 - 1.6 * pl) + eh * 0.25 * math.sin(a)) for a in np.linspace(math.pi * 1.1, math.pi * 1.9, 8)], _fonce(j_loc, 0.75), ep_)
            _courbe(img, [R(ox + ew * math.cos(a), oy + eh * math.sin(a) - eh * 2 * min(pa, 0.95) * (math.sin(a) < 0) * 0) for a in np.linspace(math.pi * 1.05, math.pi * 1.95, 10)], (40, 30, 30), ep_ * 1.4)   # cil supérieur
            if F.get("maquillage"): _courbe(img, [R(ox + sg * ew * 0.9, oy - eh * 0.4), R(ox + sg * ew * 1.25, oy - eh * 0.85)], (30, 25, 25), ep_)
        else:
            _courbe(img, [R(ox + ew * math.cos(a), oy + eh * 0.35 * math.sin(a)) for a in np.linspace(0.1, math.pi - 0.1, 10)], (50, 35, 35), ep_ * 1.3)
        if F["age"] > 45 and not p.get("dos"):                             # pattes d'oie
            for k in (-1, 0, 1): _ligne(img, R(ox + sg * ew * 1.15, oy + k * eh * 0.4), R(ox + sg * ew * 1.45, oy + k * eh * 0.7), _fonce(peau, 0.78), ep_ * 0.6)
        # sourcils (épaisseur et couleur des cheveux, forme selon l'expression, hauteur selon l'intonation)
        so = p.get("sourcils", "neutre"); by = oy - eh * 2.1 - hz * ry * 0.07 - (float(p.get("sourcil_leve", 0.0)) * ry * 0.09 if sg > 0 else 0)
        if so == "hausses": by -= ry * 0.07
        inn, ext = (ox - sg * ew * 0.95, by), (ox + sg * ew * 1.05, by)
        if so == "colere": inn = (inn[0], inn[1] + ry * 0.08); ext = (ext[0], ext[1] - ry * 0.03)
        elif so == "triste": inn = (inn[0], inn[1] - ry * 0.07); ext = (ext[0], ext[1] + ry * 0.04)
        elif so == "fronces": inn = (inn[0], inn[1] + ry * 0.05)
        elif so == "sceptique" and sg > 0: inn, ext = (inn[0], inn[1] - ry * 0.06), (ext[0], ext[1] - ry * 0.09)
        mi = ((inn[0] + ext[0]) / 2, min(inn[1], ext[1]) - ry * 0.035)
        c_s = _fonce(F["c_cheveux"], 0.75) if F["cheveux"] != "chauve" else (90, 80, 75)
        e1, e2 = ry * 0.055 * F["sourcils"], ry * 0.025 * F["sourcils"]
        cv2.fillPoly(img, [_pts([R(*inn), R(mi[0], mi[1] - e1), R(*ext), R(mi[0], mi[1] + e2 * 0.4), R(inn[0], inn[1] + e1 * 0.9)])], c_s, AA, 2)
    if so in ("colere", "fronces"):                                        # plis entre les sourcils
        for sg in (-1, 1): _ligne(img, R(cx + sg * rx * 0.07, cy - ry * 0.22), R(cx + sg * rx * 0.05, cy - ry * 0.1), _fonce(peau, 0.72), ep_)
    if (so in ("hausses", "sceptique") or yeux in ("grands", "minuscules") or hz > 0.6 or F["age"] > 55):   # rides du front
        for k in range(2 + (F["age"] > 55)): _courbe(img, [R(cx + rx * 0.5 * math.cos(a), cy - ry * (0.48 + 0.08 * k) - ry * 0.03 * math.sin(a)) for a in np.linspace(0.3, math.pi - 0.3, 9)], _fonce(peau, 0.8), ep_ * 0.8)
    # nez : ombre du côté opposé à la lumière, narines
    ny_ = cy + ry * 0.3; L = {"droit": 1.0, "rond": 0.9, "fort": 1.2, "fin": 0.85}[F["nez"]]
    _courbe(img, [R(cx - lum * rx * 0.08, cy + ry * 0.02), R(cx - lum * rx * 0.1 * L, ny_ - ry * 0.05), R(cx - lum * rx * 0.02, ny_ + ry * 0.03)], _fonce(peau, 0.72), ep_ * 1.1)
    for sg in (-1, 1): _rond(img, R(cx + sg * rx * 0.085 * L, ny_ + ry * 0.01), rx * 0.035 * L, _fonce(peau, 0.6))
    if F["age"] > 38:                                                      # plis du sourire
        for sg in (-1, 1): _courbe(img, [R(cx + sg * rx * 0.2, ny_ + ry * 0.02), R(cx + sg * rx * 0.3, ny_ + ry * 0.2), R(cx + sg * rx * 0.3, ny_ + ry * 0.3)], _fonce(peau, 0.82), ep_ * 0.8)
    if p.get("joues") or p.get("gene"):
        for sg in (-1, 1):
            m_ = _ellipse_pts(R(cx + sg * rx * 0.52, cy + ry * 0.25), rx * 0.18, ry * 0.08); cv2.fillPoly(img, [_pts(m_)], _melange(peau, (235, 120, 120), 0.45), AA, 2)
    if F.get("barbe") == "trois_jours" or F.get("barbe") == "courte":     # barbe
        b_pts = [R(cx + rx * 0.97 * math.cos(a), cy + ry * (0.08 + 0.9 * math.sin(a))) for a in np.linspace(0.08, math.pi - 0.08, 18)]
        b_pts += [R(cx - rx * 0.5, cy + ry * 0.45), R(cx, cy + ry * 0.4), R(cx + rx * 0.5, cy + ry * 0.45)]
        x0, y0 = int(max(0, min(q[0] for q in b_pts) - 2)), int(max(0, min(q[1] for q in b_pts) - 2))
        x1, y1 = int(min(img.shape[1], max(q[0] for q in b_pts) + 3)), int(min(img.shape[0], max(q[1] for q in b_pts) + 3))
        if x1 > x0 and y1 > y0:                                            # barbe fondue dans la peau (plus marquée si « courte »)
            mk = np.zeros((y1 - y0, x1 - x0), np.uint8); cv2.fillPoly(mk, [_pts([(a - x0, b - y0) for a, b in b_pts])], 255, AA, 2)
            mk = cv2.GaussianBlur(mk, (0, 0), max(1.0, rx * 0.04)).astype(np.float32)[..., None] / 255 * (0.35 if F["barbe"] == "trois_jours" else 0.85)
            img[y0:y1, x0:x1] = (img[y0:y1, x0:x1] * (1 - mk) + np.array(_fonce(F["c_cheveux"], 0.9), np.float32) * mk).astype(np.uint8)
    if F.get("barbe") in ("moustache", "courte"):
        _forme(img, [R(cx - rx * 0.3, ny_ + ry * 0.2), R(cx, ny_ + ry * 0.1), R(cx + rx * 0.3, ny_ + ry * 0.2), R(cx + rx * 0.25, ny_ + ry * 0.27), R(cx, ny_ + ry * 0.2), R(cx - rx * 0.25, ny_ + ry * 0.27)], _fonce(F["c_cheveux"], 0.9), lum, 0.2, contour=False)
    _bouche(img, F, R, cx, cy + ry * 0.58, rx, ry, p, ep_)

LEVRES = (196, 104, 104)

def _bouche(img, F, R, mx, my, rx, ry, p, ep_):
    """Bouche : lèvres colorées, dents, langue ; visèmes (syllabe prononcée), sourire, cri, moue, sourire en coin…"""
    o = float(np.clip(p.get("bouche", 0.0), 0, 1)); f = p.get("forme", "neutre"); v = p.get("viseme"); co = float(np.clip(p.get("coins", 0.0), -1, 1))
    lev = _melange(F["peau"], LEVRES if F.get("maquillage") else (185, 110, 105), 0.55 if F.get("maquillage") else 0.35)
    W_ = rx * 0.27 * F["levres"] ** 0.3; ep_l = ry * 0.026 * F["levres"]
    if f == "sourire": co = max(co, 0.8)
    if f == "triste": co = min(co, -0.8)
    def ouverte(w, h, dents=True):
        haut_ = [R(mx + w * math.cos(a), my + h * 0.55 * math.sin(a) - h * 0.15) for a in np.linspace(math.pi, 2 * math.pi, 12)]
        bas_ = [R(mx + w * math.cos(a), my + h * math.sin(a) - h * 0.15) for a in np.linspace(0, math.pi, 12)]
        cv2.fillPoly(img, [_pts(haut_ + bas_)], (70, 30, 35), AA, 2)
        if dents and h > ry * 0.05: cv2.fillPoly(img, [_pts([R(mx - w * 0.8, my - h * 0.55), R(mx + w * 0.8, my - h * 0.55), R(mx + w * 0.7, my - h * 0.2), R(mx - w * 0.7, my - h * 0.2)])], (246, 244, 236), AA, 2)
        if h > ry * 0.09: cv2.fillPoly(img, [_pts(_ellipse_pts(R(mx, my + h * 0.55), w * 0.5, h * 0.3))], (200, 90, 100), AA, 2)
        _courbe(img, haut_, lev, ep_l * 1.2); _courbe(img, bas_, lev, ep_l * 1.6)
    if v and f not in ("cri", "sourire") and o > 0.06:
        if v == "M": _courbe(img, [R(mx - W_, my), R(mx, my + ry * 0.01), R(mx + W_, my)], lev, ep_l * 2.6); return
        if v == "F": ouverte(W_ * 0.9, ry * 0.05); return
        w, h = {"A": (1.0, 0.16), "E": (1.15, 0.08), "I": (1.1, 0.05), "O": (0.65, 0.13), "U": (0.5, 0.08)}.get(v, (0.9, 0.11))
        ouverte(W_ * w * (0.8 + 0.3 * o), ry * h * (0.5 + 0.8 * o)); return
    if f == "cri" or (o > 0.75 and f not in ("sourire", "grand_sourire")): ouverte(W_ * (1.0 + 0.3 * o), ry * (0.14 + 0.12 * o)); return
    if f == "grand_sourire" or (f == "sourire" and o > 0.08):
        w = W_ * 1.25; h = ry * 0.13
        pts = [R(mx + w * math.cos(a), my - h * 0.2 + h * math.sin(a)) for a in np.linspace(0, math.pi, 14)] + [R(mx - w, my - h * 0.35), R(mx, my - h * 0.1), R(mx + w, my - h * 0.35)]
        cv2.fillPoly(img, [_pts(pts)], (70, 30, 35), AA, 2)
        cv2.fillPoly(img, [_pts([R(mx - w * 0.85, my - h * 0.2), R(mx + w * 0.85, my - h * 0.2), R(mx + w * 0.7, my + h * 0.15), R(mx - w * 0.7, my + h * 0.15)])], (246, 244, 236), AA, 2)
        _courbe(img, pts[:14], lev, ep_l * 1.5); return
    if f == "dents":
        w, h = W_ * 1.2, ry * 0.07
        cv2.fillPoly(img, [_pts([R(mx - w, my - h), R(mx + w, my - h), R(mx + w, my + h), R(mx - w, my + h)])], (240, 238, 228), AA, 2)
        _ligne(img, R(mx - w, my), R(mx + w, my), (120, 110, 110), ep_ * 0.8)
        for k in range(-3, 4): _ligne(img, R(mx + k * w / 3.5, my - h), R(mx + k * w / 3.5, my + h), (150, 140, 140), ep_ * 0.6)
        _courbe(img, [R(mx - w, my - h), R(mx + w, my - h)], lev, ep_l * 1.4); _courbe(img, [R(mx - w, my + h), R(mx + w, my + h)], lev, ep_l * 1.6); return
    if f == "o" or o > 0.08: ouverte(W_ * 0.5, ry * (0.08 + 0.08 * o), dents=False); return
    if f == "moue": co = -0.5; W2 = W_ * 0.6
    else: W2 = W_
    if f == "coin": pts = [R(mx - W2, my + ry * 0.01), R(mx, my + ry * 0.015), R(mx + W2, my - ry * 0.05)]
    elif f == "tordue": pts = [R(mx - W2 + k * W2 / 4, my + ry * 0.02 * math.sin(k * 1.6)) for k in range(9)]
    else: pts = [R(mx - W2 + 2 * W2 * k / 10, my - co * ry * 0.06 * ((k - 5) / 5) ** 2 + co * ry * 0.015) for k in range(11)]
    _courbe(img, pts, _fonce(lev, 0.7), ep_l * 1.1)                       # fente des lèvres
    c_l = [(a[0], a[1] + ep_l * 1.3) for a in pts]; _courbe(img, c_l, lev, ep_l * 1.7)                       # lèvre inférieure
    _courbe(img, [(a[0], a[1] - ep_l * 1.0) for a in pts], _melange(lev, F["peau"], 0.4), ep_l * 1.2)         # lèvre supérieure

def _lunettes(img, F, t, rx, ry, tilt, ep_):
    cx, cy = t
    def R(px, py): return M._rot(px, py, cx, cy, tilt)
    for sg in (-1, 1):
        c = R(cx + sg * rx * 0.4, cy - ry * 0.02)
        if F["lunettes"] == "rondes": cv2.ellipse(img, (int(c[0] * 4), int(c[1] * 4)), (int(rx * 0.28 * 4), int(rx * 0.26 * 4)), 0, 0, 360, (40, 35, 35), max(1, int(ep_ * 1.4)), AA, 2)
        else:
            pts = [R(cx + sg * rx * 0.4 + a * rx * 0.3, cy - ry * 0.02 + b * ry * 0.13) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            cv2.polylines(img, [_pts(pts)], True, (40, 35, 35), max(1, int(ep_ * 1.6)), AA, 2)
    _ligne(img, R(cx - rx * 0.12, cy - ry * 0.04), R(cx + rx * 0.12, cy - ry * 0.04), (40, 35, 35), ep_ * 1.2)

# ------------------------------------------------------------------ cheveux
def _cheveux_arriere(img, F, t, rx, ry, p, lum, dos):
    cx, cy = t; c = F["c_cheveux"]; st = F["cheveux"]; bal = p.get("balance", 0.0)
    if st == "long": _forme(img, [(cx - rx * 1.12, cy - ry * 0.4)] + _ellipse_pts((cx, cy - ry * 0.1), rx * 1.15, ry * 1.0, 0, 20, math.pi, 2 * math.pi) +
                            [(cx + rx * 1.12, cy - ry * 0.4), (cx + rx * 1.25 + bal * 6, cy + ry * 2.1), (cx - rx * 1.25 + bal * 6, cy + ry * 2.1)], c, lum, 0.35)
    elif st in ("carre", "mi_long"): _forme(img, [(cx - rx * 1.12, cy - ry * 0.3)] + _ellipse_pts((cx, cy - ry * 0.1), rx * 1.15, ry * 1.0, 0, 20, math.pi, 2 * math.pi) +
                                            [(cx + rx * 1.12, cy - ry * 0.3), (cx + rx * 1.18, cy + ry * (0.9 if st == "carre" else 1.35)), (cx - rx * 1.18, cy + ry * (0.9 if st == "carre" else 1.35))], c, lum, 0.35)
    elif st == "boucles":
        for k in range(16):
            a = math.pi * (0.85 + 1.3 * k / 15); _forme(img, _ellipse_pts((cx + math.cos(a) * rx * 1.05, cy - ry * 0.05 + math.sin(a) * ry * 1.02), rx * 0.24, rx * 0.24), c, lum, 0.4)
    elif st == "queue":
        q0 = (cx + rx * 0.2, cy - ry * 0.75); sw = 10 * bal + 6 * math.sin(p.get("t", 0) * 3)
        _forme(img, _membre((q0[0] + rx * 0.7, q0[1] - ry * 0.1), (q0[0] + rx * 1.1 + sw, q0[1] + ry * 1.4), rx * 0.22, rx * 0.1), c, lum, 0.4)
    elif st == "chignon":
        _forme(img, _ellipse_pts((cx, cy - ry * 1.05), rx * 0.42, ry * 0.32), c, lum, 0.45)

def _cheveux_avant(img, F, t, rx, ry, tilt, p, lum, dos, ep_):
    cx, cy = t; c = F["c_cheveux"]; st = F["cheveux"]
    def R(px, py): return M._rot(px, py, cx, cy, tilt)
    if st == "chauve":
        if F["age"] > 45:
            for sg in (-1, 1): _forme(img, _ellipse_pts(R(cx + sg * rx * 0.93, cy - ry * 0.12), rx * 0.1, ry * 0.26, tilt), c, lum, 0.3, contour=False)
        return
    if dos:
        _forme(img, [R(cx + rx * 1.03 * math.cos(a), cy - ry * 0.05 + ry * 1.0 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 30)], c, lum, 0.35, ep=ep_); return
    calotte = [R(cx + rx * 1.04 * math.cos(a), cy - ry * 0.12 + ry * 0.98 * math.sin(a)) for a in np.linspace(math.pi * 1.0, math.pi * 2.0, 20)]
    if st in ("rase",):
        cv2.fillPoly(img, [_pts(calotte + [R(cx + rx * 0.9, cy - ry * 0.45), R(cx - rx * 0.9, cy - ry * 0.45)])], _melange(c, F["peau"], 0.55), AA, 2); return
    if st in ("court", "raie", "boucles"):                                # front dégagé, raie sur le côté
        bord = [R(cx + rx * 0.95, cy - ry * 0.2), R(cx + rx * 0.6, cy - ry * 0.55), R(cx + rx * 0.1, cy - ry * 0.62), R(cx - rx * 0.5, cy - ry * 0.55), R(cx - rx * 0.95, cy - ry * 0.2)]
        _forme(img, calotte + bord, c, lum, 0.3, ep=ep_)
        if st == "raie": _courbe(img, [R(cx - rx * 0.35, cy - ry * 1.05), R(cx - rx * 0.3, cy - ry * 0.65)], _fonce(c, 0.6), ep_)
        for k in range(4): _courbe(img, [R(cx - rx * 0.6 + k * rx * 0.35, cy - ry * 1.0), R(cx - rx * 0.5 + k * rx * 0.33, cy - ry * 0.62)], _fonce(c, 0.78), ep_ * 0.7)
        if st == "boucles":
            for k in range(7): _forme(img, _ellipse_pts(R(cx - rx * 0.9 + k * rx * 0.3, cy - ry * (0.85 + 0.1 * (k % 2))), rx * 0.17, rx * 0.17), c, lum, 0.4)
        return
    # longs, carré, mi-longs, queue, chignon : frange ou cheveux tirés
    tire = st in ("queue", "chignon")
    bord = [R(cx + rx * 1.05, cy + ry * (0.15 if not tire else -0.25)), R(cx + rx * 0.75, cy - ry * 0.45)] + \
           ([R(cx + rx * (0.5 - 0.25 * k), cy - ry * (0.42 + (0.06 if k % 2 else 0))) for k in range(5)] if not tire else [R(cx, cy - ry * 0.68)]) + \
           [R(cx - rx * 0.75, cy - ry * 0.45), R(cx - rx * 1.05, cy + ry * (0.15 if not tire else -0.25))]
    _forme(img, calotte + bord, c, lum, 0.3, ep=ep_)
    for k in range(5): _courbe(img, [R(cx - rx * 0.7 + k * rx * 0.35, cy - ry * 1.02), R(cx - rx * 0.75 + k * rx * 0.36, cy - ry * 0.55)], _fonce(c, 0.75), ep_ * 0.7)
