"""Objets de l'histoire dessinés en grand dans le décor (style toons : trait noir épais, aplats, reflets) : voiture garée.
Calque RGBA prêt à poser entre le décor et les personnages (il glisse avec le décor)."""
import numpy as np, cv2
import marionnette as M

TRAIT = (28, 24, 30)
FOND = (1, 2, 3)


def _clair(c, k): return tuple(int(v + (255 - v) * k) for v in c)
def _fonce(c, k): return tuple(int(v * k) for v in c)


def voiture(col=(40, 40, 46), sens=1, l=760):
    """Voiture de profil (berline), l = longueur en pixels. Renvoie une image RGBA (fond transparent)."""
    k = l / 760.0; h = int(260 * k); W_, H_ = l + 40, h + int(60 * k) + 20
    img = np.zeros((H_, W_, 3), np.uint8); img[:] = FOND
    x0, y_sol = 20, H_ - int(40 * k) - 10                                    # y_sol : bas de la caisse ; les pneus touchent le sol 34 px plus bas
    P = lambda pts: np.array([(x0 + (x if sens > 0 else 760 - x) * k, y_sol - y * k) for x, y in pts], np.int32)
    ep = max(3, int(8 * k))
    # carrosserie (bas) et habitacle (haut)
    caisse = P([(10, 40), (12, 120), (90, 140), (210, 150), (290, 225), (520, 228), (610, 150), (720, 132), (752, 100), (750, 40)])
    cv2.fillPoly(img, [caisse], col, cv2.LINE_AA); cv2.polylines(img, [caisse], True, TRAIT, ep, cv2.LINE_AA)
    vitres = [P([(232, 152), (300, 212), (392, 214), (392, 152)]), P([(408, 152), (408, 214), (512, 214), (582, 152)])]
    for v in vitres:
        cv2.fillPoly(img, [v], (150, 190, 215), cv2.LINE_AA); cv2.polylines(img, [v], True, TRAIT, max(2, ep - 2), cv2.LINE_AA)
    reflet = P([(312, 206), (340, 206), (300, 160), (272, 160)]); cv2.fillPoly(img, [reflet], (215, 235, 245), cv2.LINE_AA)
    # portières, poignées, ligne de caisse, bas de caisse
    for xa in (400, 540):
        a, b = P([(xa, 50), (xa, 150)]); cv2.line(img, tuple(a), tuple(b), _fonce(col, 0.55) if sum(col) > 150 else (90, 90, 100), max(2, ep // 2), cv2.LINE_AA)
    for xa in (360, 500):
        a, b = P([(xa, 128), (xa + 26, 128)]); cv2.line(img, tuple(a), tuple(b), (205, 205, 215), max(3, ep), cv2.LINE_AA)
    a, b = P([(30, 112), (735, 112)]); cv2.line(img, tuple(a), tuple(b), _clair(col, 0.35), max(2, ep // 2), cv2.LINE_AA)
    a, b = P([(120, 46), (640, 46)]); cv2.line(img, tuple(a), tuple(b), _fonce(col, 0.6), max(4, ep * 2), cv2.LINE_AA)
    # phares, feux, rétroviseur, pare-chocs
    ph_ = P([(722, 104), (748, 104), (748, 122), (720, 126)]); cv2.fillPoly(img, [ph_], (255, 240, 170), cv2.LINE_AA); cv2.polylines(img, [ph_], True, TRAIT, max(2, ep // 2), cv2.LINE_AA)
    fe = P([(12, 100), (30, 100), (30, 122), (14, 122)]); cv2.fillPoly(img, [fe], (220, 50, 50), cv2.LINE_AA); cv2.polylines(img, [fe], True, TRAIT, max(2, ep // 2), cv2.LINE_AA)
    rv = P([(586, 150), (606, 150), (604, 170), (588, 170)]); cv2.fillPoly(img, [rv], col, cv2.LINE_AA); cv2.polylines(img, [rv], True, TRAIT, max(2, ep // 2), cv2.LINE_AA)
    for xa, xb in ((0, 70), (690, 760)):
        pc = P([(xa, 36), (xb, 36), (xb, 62), (xa, 62)]); cv2.fillPoly(img, [pc], (70, 70, 78), cv2.LINE_AA); cv2.polylines(img, [pc], True, TRAIT, max(2, ep // 2), cv2.LINE_AA)
    # roues (pneu, jante, moyeu, ombre de l'aile)
    for xr in (150, 600):
        c = tuple(P([(xr, 40)])[0]); r = int(62 * k)
        cv2.circle(img, c, r + int(10 * k), _fonce(col, 0.4), -1, cv2.LINE_AA)
        cv2.circle(img, c, r, (35, 35, 40), -1, cv2.LINE_AA); cv2.circle(img, c, r, TRAIT, ep, cv2.LINE_AA)
        cv2.circle(img, c, int(r * 0.58), (190, 190, 200), -1, cv2.LINE_AA); cv2.circle(img, c, int(r * 0.58), TRAIT, max(2, ep // 2), cv2.LINE_AA)
        for a_ in range(5):
            ang = a_ * 2 * np.pi / 5
            cv2.line(img, c, (int(c[0] + np.cos(ang) * r * 0.5), int(c[1] + np.sin(ang) * r * 0.5)), (120, 120, 130), max(2, ep // 2), cv2.LINE_AA)
        cv2.circle(img, c, int(r * 0.14), (90, 90, 100), -1, cv2.LINE_AA)
    # reflet sur la carrosserie (vernis)
    rb = P([(250, 136), (560, 136), (560, 130), (250, 130)]); cv2.fillPoly(img, [rb], _clair(col, 0.45), cv2.LINE_AA)
    a = (np.abs(img.astype(np.int16) - FOND).sum(2) > 9).astype(np.uint8) * 255
    return np.dstack([img, a])


def sol(l=760):
    """Hauteur (en pixels depuis le haut du calque) où les pneus touchent le sol."""
    k = l / 760.0; H_ = int(260 * k) + int(60 * k) + 20
    return H_ - int(40 * k) - 10 + 32 * k


COULEURS = {"noire": (40, 40, 46), "noir": (40, 40, 46), "rouge": (200, 50, 50), "blanche": (235, 235, 238), "bleue": (60, 100, 190),
            "grise": (140, 142, 150), "jaune": (240, 200, 60), "verte": (70, 140, 90)}


def couleur_du_texte(t, defaut=(40, 40, 46)):
    import re
    m = re.search(r"\b(voiture|caisse|bagnole|berline|4x4)\s+(noire?|rouge|blanche|bleue|grise|jaune|verte)\b", (t or "").lower())
    return COULEURS.get(m.group(2), defaut) if m else defaut


# ------------------------------------------------------------------ véhicules des métiers (idée 18 de l'auteur)
def _toile(l, h_rel):
    k = l / 760.0; H_ = int(h_rel * k) + int(60 * k) + 20; W_ = l + 40
    img = np.zeros((H_, W_, 3), np.uint8); img[:] = FOND
    return img, k, 20, H_ - int(40 * k) - 10


def _rgba(img):
    a = (np.abs(img.astype(np.int16) - FOND).sum(2) > 9).astype(np.uint8) * 255
    return np.dstack([img, a])


def _outils(img, k, x0, y_sol, sens):
    P = lambda pts: np.array([(x0 + (x if sens > 0 else 760 - x) * k, y_sol - y * k) for x, y in pts], np.int32)
    ep = max(3, int(8 * k))
    def forme(pts, c, e=None):
        p = P(pts); cv2.fillPoly(img, [p], c, cv2.LINE_AA); cv2.polylines(img, [p], True, TRAIT, e or ep, cv2.LINE_AA)
    def roue(xr, r=62):
        c = tuple(P([(xr, 40)])[0]); r = int(r * k)
        cv2.circle(img, c, r, (35, 35, 40), -1, cv2.LINE_AA); cv2.circle(img, c, r, TRAIT, ep, cv2.LINE_AA)
        cv2.circle(img, c, int(r * 0.55), (190, 190, 200), -1, cv2.LINE_AA); cv2.circle(img, c, int(r * 0.55), TRAIT, max(2, ep // 2), cv2.LINE_AA)
        cv2.circle(img, c, int(r * 0.15), (90, 90, 100), -1, cv2.LINE_AA)
    def gyro(x, y, c=(40, 110, 230)):
        forme([(x - 22, y), (x + 22, y), (x + 18, y + 30), (x - 18, y + 30)], c, max(2, ep // 2))
        p = P([(x - 8, y + 24)])[0]; cv2.circle(img, tuple(p), max(2, int(5 * k)), (255, 255, 255), -1, cv2.LINE_AA)
    return P, ep, forme, roue, gyro


def police(sens=1, l=760):
    """Voiture de police : berline blanche à bandes bleues, gyrophares sur le toit, inscription POLICE."""
    im = voiture((240, 240, 244), sens, l)[..., :3].copy()
    k = l / 760.0; x0, y_sol = 20, im.shape[0] - int(40 * k) - 10
    P, ep, forme, roue, gyro = _outils(im, k, x0, y_sol, sens)
    forme([(40, 116), (720, 116), (720, 142), (40, 142)], (40, 70, 160), max(2, ep // 2))
    a, b = P([(280, 118)])[0], P([(500, 142)])[0]
    gyro(380, 228, (40, 110, 230)); gyro(440, 228, (220, 40, 40))
    try:
        import os
        from PIL import Image, ImageDraw, ImageFont
        pil = Image.fromarray(im); dr = ImageDraw.Draw(pil)
        f = ImageFont.truetype(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "polices", "Poppins-Bold.ttf"), max(12, int(30 * k)))
        dr.text((min(a[0], b[0]) + 8 * k, min(a[1], b[1]) - 9 * k), "POLICE", font=f, fill=(255, 255, 255)); im = np.array(pil)
    except Exception: pass
    return _rgba(im)


def ambulance(sens=1, l=760):
    """Ambulance : fourgon blanc, bandes jaunes et rouges, croix rouge, gyrophares bleus."""
    img, k, x0, y_sol = _toile(l, 330)
    P, ep, forme, roue, gyro = _outils(img, k, x0, y_sol, sens)
    forme([(10, 40), (10, 300), (520, 300), (560, 290), (640, 180), (740, 160), (752, 60), (750, 40)], (245, 245, 248))
    forme([(470, 280), (548, 280), (598, 212), (470, 212)], (150, 190, 215), max(2, ep - 2))
    for y, c in ((120, (250, 200, 40)), (100, (230, 60, 60))): forme([(12, y), (748, y), (748, y + 18), (12, y + 18)], c, max(2, ep // 3))
    forme([(220, 170), (270, 170), (270, 210), (310, 210), (310, 250), (270, 250), (270, 290), (220, 290), (220, 250), (180, 250), (180, 210), (220, 210)], (220, 40, 40), max(2, ep // 2))
    gyro(80, 300); gyro(480, 300)
    for xr in (150, 620): roue(xr)
    return _rgba(img)


def camion_pompier(sens=1, l=760):
    """Camion de pompiers : grand camion rouge, échelle sur le toit, bandes blanches, gyrophares, tuyaux enroulés."""
    img, k, x0, y_sol = _toile(l, 330)
    P, ep, forme, roue, gyro = _outils(img, k, x0, y_sol, sens)
    forme([(10, 40), (10, 230), (560, 230), (560, 40)], (210, 40, 40))       # caisse
    forme([(570, 40), (570, 270), (690, 270), (750, 190), (752, 40)], (210, 40, 40))   # cabine
    forme([(600, 180), (600, 250), (680, 250), (730, 185)], (150, 190, 215), max(2, ep - 2))
    forme([(10, 110), (752, 110), (752, 126), (10, 126)], (250, 250, 250), max(2, ep // 3))
    for x in range(40, 540, 120): forme([(x, 140), (x + 90, 140), (x + 90, 215), (x, 215)], (190, 30, 30), max(2, ep // 2))
    forme([(0, 240), (600, 240), (600, 262), (0, 262)], (200, 200, 210), max(2, ep // 2))   # échelle
    for x in range(20, 600, 46): forme([(x, 238), (x + 8, 238), (x + 8, 264), (x, 264)], (200, 200, 210), max(1, ep // 3))
    gyro(600, 270); gyro(660, 270, (220, 40, 40))
    c = tuple(P([(180, 175)])[0]); cv2.circle(img, c, int(34 * k), (250, 250, 250), max(3, int(10 * k)), cv2.LINE_AA)   # tuyau enroulé
    for xr in (130, 430, 640): roue(xr, 66)
    return _rgba(img)


def tracteur(sens=1, l=640):
    """Tracteur vert : grande roue arrière, petite roue avant, cabine vitrée, pot d'échappement."""
    img, k, x0, y_sol = _toile(l, 380)
    P, ep, forme, roue, gyro = _outils(img, k, x0, y_sol, sens)
    forme([(260, 90), (740, 90), (740, 200), (420, 220), (260, 220)], (60, 150, 70))   # capot
    forme([(120, 140), (120, 360), (330, 360), (350, 140)], (60, 150, 70))           # cabine
    forme([(150, 220), (150, 330), (310, 330), (320, 220)], (160, 200, 225), max(2, ep - 2))
    forme([(560, 200), (580, 200), (580, 290), (560, 290)], (60, 60, 66), max(2, ep // 2))   # pot d'échappement
    c = tuple(P([(200, 120)])[0]); r = int(125 * k)                           # grande roue arrière
    cv2.circle(img, c, r, (35, 35, 40), -1, cv2.LINE_AA); cv2.circle(img, c, r, TRAIT, ep, cv2.LINE_AA)
    for a_ in range(10):
        ang = a_ * np.pi / 5
        cv2.line(img, (int(c[0] + np.cos(ang) * r * 0.8), int(c[1] + np.sin(ang) * r * 0.8)), (int(c[0] + np.cos(ang) * r), int(c[1] + np.sin(ang) * r)), (70, 70, 76), max(3, ep), cv2.LINE_AA)
    cv2.circle(img, c, int(r * 0.5), (250, 200, 40), -1, cv2.LINE_AA); cv2.circle(img, c, int(r * 0.5), TRAIT, max(2, ep // 2), cv2.LINE_AA)
    c2 = tuple(P([(640, 60)])[0]); r2 = int(62 * k)
    cv2.circle(img, c2, r2, (35, 35, 40), -1, cv2.LINE_AA); cv2.circle(img, c2, r2, TRAIT, ep, cv2.LINE_AA)
    cv2.circle(img, c2, int(r2 * 0.5), (250, 200, 40), -1, cv2.LINE_AA); cv2.circle(img, c2, int(r2 * 0.5), TRAIT, max(2, ep // 2), cv2.LINE_AA)
    return _rgba(img)


def fusee(sens=1, l=360):
    """Fusée blanche et rouge debout sur son pas de tir, hublot, ailerons, flammes au décollage."""
    k = l / 360.0; W_, H_ = int(l * 1.0) + 40, int(l * 2.6)
    img = np.zeros((H_, W_, 3), np.uint8); img[:] = FOND
    P = lambda pts: np.array([(20 + x * k, H_ - 20 - y * k) for x, y in pts], np.int32); ep = max(3, int(8 * k))
    def forme(pts, c):
        p = P(pts); cv2.fillPoly(img, [p], c, cv2.LINE_AA); cv2.polylines(img, [p], True, TRAIT, ep, cv2.LINE_AA)
    forme([(40, 60), (110, 200), (110, 80)], (210, 40, 40)); forme([(320, 60), (250, 200), (250, 80)], (210, 40, 40))
    forme([(110, 60), (110, 700), (180, 900), (250, 700), (250, 60)], (245, 245, 248))
    forme([(130, 700), (180, 900), (230, 700)], (210, 40, 40))
    c = tuple(P([(180, 520)])[0]); cv2.circle(img, c, int(50 * k), (150, 190, 215), -1, cv2.LINE_AA); cv2.circle(img, c, int(50 * k), TRAIT, ep, cv2.LINE_AA)
    forme([(130, 60), (150, 20), (210, 20), (230, 60)], (60, 60, 66))
    forme([(60, 0), (300, 0), (300, 24), (60, 24)], (120, 120, 130))
    return _rgba(img)


VEHICULES = {"camion_pompier": camion_pompier, "police": police, "ambulance": ambulance, "tracteur": tracteur, "fusee": fusee}
MOTS = [("camion_pompier", r"camion (de|des) pompiers?|grande [ée]chelle|camion rouge"),
        ("police", r"voiture de police|les flics|la police|les keufs|la bac\b|gyrophare|contr[ôo]le de police|les condés"),
        ("ambulance", r"ambulance|\bsamu\b|ambulanci"),
        ("tracteur", r"tracteurs?"),
        ("fusee", r"fus[ée]es?\b")]
METIER_VEHICULE = {"pompier": "camion_pompier", "policier": "police", "agriculteur": "tracteur", "astronaute": "fusee"}


def vehicule_de(texte, metiers=(), lieu="rue"):
    """Véhicule à dessiner dans le décor : celui qu'on cite (« la voiture de police »), sinon celui du métier présent (pompier dans
    la rue -> camion ; agriculteur à la ferme -> tracteur), sinon None. Seulement dehors (rue, ferme)."""
    import re
    if lieu not in ("rue", "ferme"): return None
    t = (texte or "").lower()
    for nom, motif in MOTS:
        if re.search(motif, t): return nom
    for m in metiers:
        v = METIER_VEHICULE.get(m)
        if v and (v != "tracteur" or lieu == "ferme"): return v
    return None


def hauteur_sol(nom, l):
    """Distance du haut du calque au sol (pneus / pas de tir)."""
    if nom == "fusee": return int(l * 2.6) - 20
    h_rel = {"camion_pompier": 330, "ambulance": 330, "tracteur": 380}.get(nom, 260)
    k = l / 760.0; H_ = int(h_rel * k) + int(60 * k) + 20
    return H_ - int(40 * k) - 10 + 32 * k
