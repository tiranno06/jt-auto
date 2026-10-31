"""Témoin image (équipe qualité, demande de l'auteur du 31 octobre 2026) : QUI BOUGE quand une phrase est dite dans la vidéo
d'origine. Dans les animations TikTok, celui qui parle bouge (bouche, tête, bras) et celui qui écoute reste presque immobile. On
compare le mouvement de la moitié gauche et de la moitié droite de l'image (zone des têtes et des bustes), seulement sur les images
sans coupure ni mouvement de caméra. Gratuit, sur la machine (OpenCV). Sert à départager deux voix presque identiques.
Essai sur « Fierté familiale » (même voix pour les deux copains) : le côté qui bouge suit le fil de l'histoire.
REGARD=0 pour couper."""
import os
import numpy as np

LARGEUR, HAUTEUR = 180, 320
SEUIL_PIXEL, SEUIL_COUPE, NET = 15, 0.05, 1.4


def images(chemin, duree_max=200):
    """Images de la vidéo en gris, petites (180×320), et images par seconde. ([], 0) si illisible."""
    if not chemin or not os.path.exists(chemin) or os.environ.get("REGARD", "1") == "0": return [], 0.0
    import cv2
    cap = cv2.VideoCapture(chemin)
    if not cap.isOpened(): return [], 0.0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; out = []
    while len(out) < duree_max * fps:
        ok, f = cap.read()
        if not ok: break
        out.append(cv2.cvtColor(cv2.resize(f, (LARGEUR, HAUTEUR), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.int16))
    return out, float(fps)


def cote(fr, fps, deb, fin):
    """Qui bouge entre deb et fin (s) : 0 = gauche, 1 = droite, None = on ne sait pas (pas assez d'images nettes, ou les deux
    bougent autant). Renvoie (côté, certitude 0-1)."""
    if not fr or fps <= 0: return None, 0.0
    a, b = int(deb * fps) + 1, min(len(fr), int(fin * fps) + 1)
    G = D = 0.0; n = 0
    for i in range(a, b):
        d = np.abs(fr[i] - fr[i - 1]) > SEUIL_PIXEL
        if d.mean() > SEUIL_COUPE: continue                                # coupe, plan qui change, caméra qui bouge
        h = d[int(HAUTEUR * 0.22):int(HAUTEUR * 0.53)]                     # têtes et bustes
        G += float(h[:, :LARGEUR // 2].sum()); D += float(h[:, LARGEUR // 2:].sum()); n += 1
    if n < 6 or G + D < 150: return None, 0.0
    if G > NET * D: return 0, min(1.0, (G / max(D, 1.0) - 1) / 3)
    if D > NET * G: return 1, min(1.0, (D / max(G, 1.0) - 1) / 3)
    return None, 0.0


def temoin(chemin, mots, ph):
    """Pour chaque phrase (listes d'indices de mots, locuteurs.phrases) : (côté 0/1 ou None, certitude)."""
    fr, fps = images(chemin)
    if not fr: return None
    out = [cote(fr, fps, mots[p[0]]["s"], mots[p[-1]]["e"]) for p in ph]
    return out if sum(1 for c, _ in out if c is not None) >= 3 else None
