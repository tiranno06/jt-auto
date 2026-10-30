"""Postures des personnes de la vidéo TikTok d'origine (idée 29 de l'auteur) : MediaPipe Pose (Google, Apache 2.0, gratuit, sur la
machine) repère les épaules, coudes, poignets, hanches et le visage, image par image ; on en déduit le GESTE tenu (bras croisés,
mains sur les hanches, main au menton, téléphone à l'oreille, main sur la bouche ou le visage, bras levés, bras ouverts, doigt
pointé) pour que nos personnages le recopient au même moment (studio.realiser). POSTURES=0 pour couper.
Modèle « pose_landmarker_lite » (5 Mo), téléchargé une fois dans outils/."""
import os, urllib.request
import numpy as np

MODELE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outils", "pose_landmarker_lite.task")
URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
NEZ, BOUCHE_G, BOUCHE_D, OREILLE_G, OREILLE_D = 0, 9, 10, 7, 8
EPAULE, COUDE, POIGNET, HANCHE = (11, 12), (13, 14), (15, 16), (23, 24)   # (gauche, droite) de la personne


def classer(p, vis=None):
    """Geste tenu d'après les repères (x, y normalisés, y vers le bas) ; None si rien de net. p : tableau (33, 2)."""
    p = np.asarray(p, float); vis = np.ones(len(p)) if vis is None else np.asarray(vis, float)
    if min(vis[EPAULE[0]], vis[EPAULE[1]]) < 0.5: return None
    eg, ed = p[EPAULE[0]], p[EPAULE[1]]; l = float(np.hypot(*(eg - ed)))
    if l < 0.03: return None
    milieu = (eg + ed) / 2; nez = p[NEZ]; bouche = (p[BOUCHE_G] + p[BOUCHE_D]) / 2
    def d(a, b): return float(np.hypot(*(a - b))) / l
    mains = [(k, p[POIGNET[k]]) for k in (0, 1) if vis[POIGNET[k]] >= 0.5]
    if not mains: return None
    for k, m in mains:                                                      # une main près de la tête
        if d(m, p[(OREILLE_G, OREILLE_D)[k]]) < 0.45 and m[1] < milieu[1]: return "telephone"
        if m[1] > bouche[1] + 0.12 * l and d(m, bouche + np.array([0, 0.25 * l])) < 0.3: return "menton"   # main sous la bouche
        if d(m, bouche) < 0.35: return "facepalm"                           # main sur la bouche / le visage
    if len(mains) == 2:
        (_, mg), (_, md) = mains
        if mg[1] < nez[1] - 0.2 * l and md[1] < nez[1] - 0.2 * l: return "desespoir"    # deux bras levés
        hg, hd = p[HANCHE[0]], p[HANCHE[1]]
        if max(vis[HANCHE[0]], vis[HANCHE[1]]) >= 0.5 and d(mg, hg) < 0.45 and d(md, hd) < 0.45 \
                and abs(p[COUDE[0]][0] - milieu[0]) > 0.75 * l and abs(p[COUDE[1]][0] - milieu[0]) > 0.75 * l: return "mains_hanches"
        sens = np.sign(eg[0] - ed[0]) or 1.0                                # côté gauche de la personne à l'image
        torse = milieu[1] < mg[1] < milieu[1] + 1.6 * l and milieu[1] < md[1] < milieu[1] + 1.6 * l
        if torse and (mg[0] - milieu[0]) * sens < 0.1 * l and (md[0] - milieu[0]) * sens > -0.1 * l and d(mg, md) < 0.9: return "croises"
        if abs(mg[0] - milieu[0]) > 1.3 * l and abs(md[0] - milieu[0]) > 1.3 * l and mg[1] < milieu[1] + 1.4 * l: return "bras_ouverts"
    for k, m in mains:                                                      # un bras tendu sur le côté : il montre quelqu'un
        if abs(m[0] - milieu[0]) > 1.5 * l and abs(m[1] - p[EPAULE[k]][1]) < 0.6 * l: return "pointe_d" if m[0] > milieu[0] else "pointe_g"
    return None


def _detecteur():
    if not os.path.exists(MODELE):
        os.makedirs(os.path.dirname(MODELE), exist_ok=True); urllib.request.urlretrieve(URL, MODELE)
    from mediapipe.tasks.python import BaseOptions, vision
    return vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODELE), running_mode=vision.RunningMode.IMAGE, num_poses=2, min_pose_detection_confidence=0.5))


def lire(images, tenue=1.0):
    """images : [(instant, image RGB)] -> [[début, fin, place x (0-1), geste]] : gestes tenus au moins `tenue` seconde (deux images de suite)."""
    if os.environ.get("POSTURES", "1") == "0" or not images: return []
    import mediapipe as mp
    det = _detecteur(); vus = []
    try:
        for t, im in images:
            r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(im)))
            for pose in r.pose_landmarks or []:
                pts = np.array([[q.x, q.y] for q in pose]); vis = np.array([q.visibility if q.visibility is not None else 1.0 for q in pose])
                g = classer(pts, vis)
                if g: vus.append((float(t), float(np.clip(pts[[11, 12], 0].mean(), 0, 1)), g))
    finally:
        det.close()
    pas = (images[1][0] - images[0][0]) if len(images) > 1 else 0.5
    out = []
    for t, x, g in sorted(vus):
        c = next((o for o in reversed(out) if o[3] == g and abs(o[2] - x) < 0.2 and t - o[1] <= pas * 1.6), None)
        if c: c[1] = round(t + pas, 2)
        else: out.append([round(t, 2), round(t + pas, 2), round(x, 2), g])
    return [o for o in out if o[1] - o[0] >= tenue][:80]


def geste_pendant(postures, deb, fin):
    """Geste le plus tenu dans l'original pendant [deb, fin] (None si aucun)."""
    duree = {}
    for a, b, _, g in postures or []:
        c = min(fin, b) - max(deb, a)
        if c > 0: duree[g] = duree.get(g, 0) + c
    if not duree: return None
    g = max(duree, key=duree.get)
    return g if duree[g] >= min(0.8, 0.4 * (fin - deb)) else None
