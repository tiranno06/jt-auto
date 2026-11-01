"""Témoin VISAGES (choix de l'auteur, 1er novembre 2026, idées 2 et 3) : qui parle d'après les BOUCHES de la vidéo d'origine, et
suivi de chaque personnage d'un bout à l'autre, même quand UNE MÊME PERSONNE joue deux ou trois personnages.

MediaPipe Face Landmarker (Google, Apache 2.0, gratuit, sur la machine ; modèle de 4 Mo téléchargé une fois dans outils/) :
pour chaque visage, image par image (8 par seconde) : place à l'écran, ouverture de la bouche (« jawOpen »), tête tournée à
gauche ou à droite, et l'APPARENCE autour du visage (couleurs du haut porté, des cheveux / de la perruque, lunettes ou accessoire).
1. Dans un même plan, un visage est suivi d'une image à l'autre (une « piste ») ;
2. les pistes sont regroupées en PERSONNAGES d'après l'apparence et le regard : la même personne qui change de sweat, de perruque
   ou qui se tourne vers la gauche puis vers la droite pour jouer deux rôles (coupes alternées) donne deux personnages différents ;
   deux visages à l'écran en même temps sont toujours deux personnages ;
3. pour chaque phrase, celui dont la bouche bouge le plus pendant qu'elle est dite est celui qui parle.
Marche sur les vraies personnes ; sur un dessin animé (aucun visage humain trouvé), il se tait : Gemini (moteur/video_ia.py) et
le témoin des mouvements (moteur/regard.py) prennent le relais. VISAGES=0 pour couper."""
import os, urllib.request
import numpy as np

MODELE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outils", "face_landmarker.task")
URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
IPS, COUPE = 8.0, 28.0                                                     # images lues par seconde ; écart moyen = changement de plan


def _detecteur():
    if not os.path.exists(MODELE):
        os.makedirs(os.path.dirname(MODELE), exist_ok=True); urllib.request.urlretrieve(URL, MODELE)
    from mediapipe.tasks.python import BaseOptions, vision
    return vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODELE), running_mode=vision.RunningMode.IMAGE, num_faces=3,
        output_face_blendshapes=True, min_face_detection_confidence=0.5))


def _apparence(hsv, x0, y0, x1, y1):
    """Couleurs autour du visage : le haut porté (sous le menton) et les cheveux / chapeau (au-dessus) -> vecteur de 14 valeurs."""
    H, W = hsv.shape[:2]; h = y1 - y0; w = x1 - x0
    def hist(a, b, c, d):
        z = hsv[max(0, b):min(H, d), max(0, a):min(W, c)].reshape(-1, 3)
        if len(z) < 20: return np.zeros(7)
        sat = z[:, 1] > 50
        v = np.concatenate([np.histogram(z[sat, 0], bins=5, range=(0, 180))[0], np.histogram(z[~sat, 2], bins=2, range=(0, 256))[0]]).astype(float)
        return v / max(1.0, v.sum())
    return np.concatenate([hist(x0 - w // 2, y1 + h // 4, x1 + w // 2, y1 + h * 3 // 2),   # le haut (sweat, chemise…)
                           hist(x0, y0 - h // 3, x1, y0 + h // 8)])                       # cheveux, perruque, casquette


def lire(chemin, duree_max=200):
    """[(instant, coupe_avant, [visage…])] ; visage = dict(x, y, taille, bouche, regard (-1 gauche … 1 droite), app)."""
    if os.environ.get("VISAGES", "1") == "0" or not chemin or not os.path.exists(chemin): return []
    import cv2, mediapipe as mp
    cap = cv2.VideoCapture(chemin)
    if not cap.isOpened(): return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; pas = max(1, int(round(fps / IPS)))
    det = _detecteur(); out, k, prec = [], 0, None
    try:
        while k < duree_max * fps:
            ok, f = cap.read()
            if not ok: break
            k += 1
            if (k - 1) % pas: continue
            t = (k - 1) / fps
            petit = cv2.resize(f, (90, 160)).astype(np.int16)
            coupe = prec is not None and float(np.abs(petit - prec).mean()) > COUPE; prec = petit
            hgt = 640; img = cv2.resize(f, (int(f.shape[1] * hgt / f.shape[0]), hgt)); H, W = img.shape[:2]
            r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))))
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); vis = []
            for j, lm in enumerate(r.face_landmarks or []):
                P = np.array([[q.x, q.y] for q in lm])
                x0, y0 = (P.min(0) * [W, H]).astype(int); x1, y1 = (P.max(0) * [W, H]).astype(int)
                bs = {b.category_name: b.score for b in (r.face_blendshapes[j] if r.face_blendshapes and j < len(r.face_blendshapes) else [])}
                ouv = bs.get("jawOpen", 0.0) + 0.5 * bs.get("mouthFunnel", 0.0) + 0.3 * bs.get("mouthPucker", 0.0)
                if not bs:                                                 # (sans « blendshapes » : écart des lèvres / hauteur du visage)
                    ouv = float(abs(P[14, 1] - P[13, 1]) / max(1e-6, P[:, 1].max() - P[:, 1].min()))
                yeux = (P[33, 0] + P[263, 0]) / 2; l_ = abs(P[263, 0] - P[33, 0]) + 1e-6
                vis.append(dict(x=float(P[:, 0].mean()), y=float(P[:, 1].mean()), taille=float(P[:, 1].max() - P[:, 1].min()),
                                bouche=float(ouv), regard=float(np.clip((P[1, 0] - yeux) / l_ * 3, -1, 1)), app=_apparence(hsv, x0, y0, x1, y1)))
            out.append((t, coupe, vis))
    finally:
        det.close(); cap.release()
    return out


def pistes(images):
    """Un même visage suivi dans un plan : [{"ech": [(t, visage)], "plan": n°}]."""
    P, actives, plan = [], [], 0
    for t, coupe, vis in images:
        if coupe: plan += 1; actives = []
        libres = list(range(len(vis))); nouv = []
        for p in actives:
            _, v0 = p["ech"][-1]
            if not libres: continue
            j = min(libres, key=lambda j: abs(vis[j]["x"] - v0["x"]) + abs(vis[j]["y"] - v0["y"]))
            if abs(vis[j]["x"] - v0["x"]) + abs(vis[j]["y"] - v0["y"]) < 0.18:
                p["ech"].append((t, vis[j])); libres.remove(j); nouv.append(p)
        for j in libres:
            p = {"ech": [(t, vis[j])], "plan": plan}; P.append(p); nouv.append(p)
        actives = nouv
    return [p for p in P if len(p["ech"]) >= 3]


def _signature(p):
    """Apparence moyenne + regard (gauche / droite) + place à l'écran d'une piste."""
    app = np.mean([v["app"] for _, v in p["ech"]], axis=0)
    reg = float(np.mean([v["regard"] for _, v in p["ech"]])); x = float(np.mean([v["x"] for _, v in p["ech"]]))
    return np.concatenate([app * 2.0, [reg * 0.8, (x - 0.5) * 0.6]])


def personnages(P, k=None):
    """Regroupe les pistes en personnages (numéros 0, 1, 2…). k : nombre voulu (sinon choisi, 1 à 3). Deux pistes vues en même temps
    ne sont jamais le même personnage. Renvoie (étiquettes par piste, nombre de personnages)."""
    if not P: return [], 0
    X = np.array([_signature(p) for p in P])
    ens = np.zeros((len(P), len(P)), bool)                                 # pistes visibles en même temps
    for a in range(len(P)):
        ta = {round(t, 2) for t, _ in P[a]["ech"]}
        for b in range(a + 1, len(P)):
            if P[a]["plan"] == P[b]["plan"] and ta & {round(t, 2) for t, _ in P[b]["ech"]}: ens[a, b] = ens[b, a] = True
    kmin = max(1, int(ens.sum(1).max()) + 1 if ens.any() else 1)
    def grouper(kk):
        import warnings
        from scipy.cluster.vq import kmeans2
        if kk <= 1 or len(P) < kk: return np.zeros(len(P), int)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore"); _, lab = kmeans2(X, kk, minit="++", seed=3)
        for a in range(len(P)):                                            # vus ensemble : jamais le même
            for b in range(a + 1, len(P)):
                if ens[a, b] and lab[a] == lab[b]:
                    autres = [c for c in range(kk) if c != lab[a]]
                    if autres: lab[b] = autres[int(np.argmin([np.linalg.norm(X[b] - X[lab == c].mean(0)) if (lab == c).any() else 9 for c in autres]))]
        return lab
    if k: return list(grouper(max(k, kmin))), max(k, kmin)
    meilleur, best_k = grouper(kmin), kmin
    for kk in range(max(2, kmin), 4):                                      # 2 ou 3 personnages si l'apparence se sépare nettement
        if len(P) < kk: break
        lab = grouper(kk)
        intra = np.mean([np.linalg.norm(X[i] - X[lab == lab[i]].mean(0)) for i in range(len(P))])
        cent = [X[lab == c].mean(0) for c in range(kk) if (lab == c).any()]
        inter = min(np.linalg.norm(a - b) for i, a in enumerate(cent) for b in cent[i + 1:]) if len(cent) > 1 else 0
        if len(cent) == kk and inter > 2.2 * intra: meilleur, best_k = lab, kk
    return list(meilleur), best_k


def temoin(chemin, mots, ph, k=None):
    """(vue, nombre de personnages) : pour chaque phrase (personnage 0/1/2 ou None, certitude 0-1), comme regard.temoin.
    None si moins de 3 phrases lisibles (dessin animé, pas de visage, bouches illisibles)."""
    try: images = lire(chemin)
    except Exception as e:
        print(f"  témoin visages impossible ({str(e)[:100]})", flush=True); return None, 0
    P = pistes(images)
    if not P: return None, 0
    lab, n = personnages(P, k)
    out = []
    for p in ph:
        deb, fin = mots[p[0]]["s"], mots[p[-1]]["e"]
        act = {}
        for piste, c in zip(P, lab):
            z = [v["bouche"] for t, v in piste["ech"] if deb - 0.1 <= t <= fin + 0.1]
            if len(z) >= 2: act[c] = max(act.get(c, 0.0), float(np.std(z) + 0.5 * np.mean(np.abs(np.diff(z)))))
        if not act: out.append((None, 0.0)); continue
        tri = sorted(act.items(), key=lambda kv: -kv[1]); b = tri[0][1]; s = tri[1][1] if len(tri) > 1 else 0.0
        if b < 0.02: out.append((None, 0.0)); continue
        conf = 0.6 if len(tri) == 1 else float(min(1.0, (b - s) / (b + 1e-6) * 1.5))   # un seul visage : celui qui parle à l'écran (plan serré)
        out.append((int(tri[0][0]), conf) if conf >= 0.15 else (None, 0.0))
    lisibles = sum(1 for c, _ in out if c is not None)
    print(f"  témoin visages : {len(P)} piste(s), {n} personnage(s) d'après l'apparence et le regard, {lisibles}/{len(ph)} phrases lisibles", flush=True)
    return (out if lisibles >= 3 else None), n
