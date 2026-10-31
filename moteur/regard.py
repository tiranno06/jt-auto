"""Témoin image (équipe qualité, demande de l'auteur du 31 octobre 2026) : QUI BOUGE quand une phrase est dite dans la vidéo
d'origine. Dans les animations TikTok, celui qui parle bouge (bouche, tête, bras) et celui qui écoute reste presque immobile. On
décrit ce qui bouge (couleurs des habits, de la peau, des cheveux autour du mouvement, et sa place à l'écran), seulement sur les
images sans coupure ni mouvement de caméra, puis on regroupe les phrases en deux personnes : marche aussi en gros plan. Gratuit, sur la machine (OpenCV). Sert à départager deux voix presque identiques.
Essai sur « Fierté familiale » (même voix pour les deux copains) : le côté qui bouge suit le fil de l'histoire.
REGARD=0 pour couper."""
import os
import numpy as np

LARGEUR, HAUTEUR = 180, 320
SEUIL_PIXEL, SEUIL_COUPE, NET = 15, 0.05, 1.4


def images(chemin, duree_max=200):
    """Images de la vidéo, petites (180×320) : [(gris, teintes HSV)], et images par seconde. ([], 0) si illisible."""
    if not chemin or not os.path.exists(chemin) or os.environ.get("REGARD", "1") == "0": return [], 0.0
    import cv2
    cap = cv2.VideoCapture(chemin)
    if not cap.isOpened(): return [], 0.0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; out = []
    while len(out) < duree_max * fps:
        ok, f = cap.read()
        if not ok: break
        f = cv2.resize(f, (LARGEUR, HAUTEUR), interpolation=cv2.INTER_AREA)
        out.append((cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.int16), cv2.cvtColor(f, cv2.COLOR_BGR2HSV)))
    return out, float(fps)


def signature(fr, fps, deb, fin):
    """Qui bouge entre deb et fin (s), décrit par ses COULEURS (habits, peau, cheveux autour de ce qui bouge) et sa place à
    l'écran : marche aussi en gros plan (une seule personne à l'image). None si pas assez d'images nettes."""
    import cv2
    a, b = int(deb * fps) + 1, min(len(fr), int(fin * fps) + 1)
    H = np.zeros(16); xs = []; n = 0
    for i in range(max(1, a), b):
        d = np.abs(fr[i][0] - fr[i - 1][0]) > SEUIL_PIXEL
        if d.mean() > SEUIL_COUPE: continue                                # coupe, plan qui change, caméra qui bouge
        d[:int(HAUTEUR * 0.12)] = False; d[int(HAUTEUR * 0.62):] = False   # visages, bustes, bras
        if d.sum() < 20: continue
        m = cv2.dilate(d.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        hsv = fr[i][1][m]; sat = hsv[:, 1] > 40
        H += np.concatenate([np.histogram(hsv[sat, 0], bins=12, range=(0, 180))[0], np.histogram(hsv[~sat, 2], bins=4, range=(0, 256))[0]])
        xs.append(float(np.nonzero(d)[1].mean()) / LARGEUR); n += 1
    if n < 4 or H.sum() <= 0: return None
    return np.concatenate([H / H.sum(), [float(np.mean(xs))]])


def cote(fr, fps, deb, fin):
    """Plan large : qui bouge entre deb et fin, la moitié gauche ou la moitié droite de l'image. (0 / 1 / None, certitude 0-1)."""
    a, b = int(deb * fps) + 1, min(len(fr), int(fin * fps) + 1)
    G = D = 0.0; n = 0
    for i in range(max(1, a), b):
        d = np.abs(fr[i][0] - fr[i - 1][0]) > SEUIL_PIXEL
        if d.mean() > SEUIL_COUPE: continue
        h = d[int(HAUTEUR * 0.22):int(HAUTEUR * 0.53)]                     # têtes et bustes
        G += float(h[:, :LARGEUR // 2].sum()); D += float(h[:, LARGEUR // 2:].sum()); n += 1
    if n < 6 or G + D < 150: return None, 0.0
    if G > NET * D: return 0, min(1.0, (G / max(D, 1.0) - 1) / 3)
    if D > NET * G: return 1, min(1.0, (D / max(G, 1.0) - 1) / 3)
    return None, 0.0


def temoin(chemin, mots, ph):
    """Pour chaque phrase (listes d'indices de mots, locuteurs.phrases) : (personne 0/1 ou None, certitude 0-1). Les phrases sont
    regroupées en deux personnes d'après la signature de ce qui bouge (k-moyennes) ; certitude = netteté du rattachement."""
    fr, fps = images(chemin)
    if not fr: return None
    cotes = [cote(fr, fps, mots[p[0]]["s"], mots[p[-1]]["e"]) for p in ph]   # 1) plans larges : gauche ou droite (le plus sûr)
    sig = [signature(fr, fps, mots[p[0]]["s"], mots[p[-1]]["e"]) for p in ph]   # 2) gros plans : les couleurs de ce qui bouge
    out = list(cotes)
    X = np.array([x for x in sig if x is not None])
    if len(X) >= 4:
        from scipy.cluster.vq import kmeans2
        cent, lab = kmeans2(X, 2, minit="++", seed=1)
        if len(set(lab.tolist())) == 2:
            coul, k = [], 0
            for x in sig:
                if x is None: coul.append((None, 0.0)); continue
                d0, d1 = np.linalg.norm(x - cent[0]), np.linalg.norm(x - cent[1])
                coul.append((int(lab[k]), float(min(1.0, abs(d0 - d1) / (d0 + d1 + 1e-9) * 2)))); k += 1
            communs = [(a[0], b[0]) for a, b in zip(cotes, coul) if a[0] is not None and b[0] is not None]
            if len(communs) >= 3:                                          # même numérotation que les côtés
                if sum(a == b for a, b in communs) < len(communs) / 2: coul = [(None if c is None else 1 - c, w) for c, w in coul]
                if sum(a == b for a, b in communs) >= 0.6 * len(communs) or sum(a != b for a, b in communs) >= 0.6 * len(communs):
                    out = [a if a[0] is not None else (c[0], 0.6 * c[1]) for a, c in zip(cotes, coul)]   # couleurs : seulement là où le côté manque
            elif not any(c is not None for c, _ in cotes): out = [(c, 0.6 * w) for c, w in coul]
    return out if sum(1 for c, _ in out if c is not None) >= 3 else None
