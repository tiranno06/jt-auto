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
