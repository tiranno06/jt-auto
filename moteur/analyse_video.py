"""Analyse de l'IMAGE de la vidéo TikTok d'origine (gratuite, sans IA : OpenCV), pour construire notre scène à son image.

On regarde 2 images par seconde et on mesure :
- le montage : coupes (changements de plan), nombre et durée moyenne des plans ;
- les cadrages : taille des visages à l'écran -> très serré, serré, moyen, large (proportion de chacun) ;
- les personnes : combien à l'écran, leur place (gauche, centre, droite), la couleur de leurs HABITS (sous le visage) et de leurs
  CHEVEUX (au-dessus), s'ils sourient (mimique), leur agitation (gestes) ;
- le décor : la couleur du fond (hors personnes), la palette de l'image, la lumière (luminosité, chaleur, saturation)
  -> l'heure probable (jour, soir, nuit) ;
- la caméra : fixe, avancée (zoom avant), recul, travelling, caméra à l'épaule (tremblement) ;
- des images clés (une par plan, 8 au plus) : quand le crédit Claude le permet, elles lui sont montrées pour qu'il reprenne
  tout ce qu'un calcul ne sait pas nommer (lieu, objets, type de vêtements, coiffures, expressions, premier plan / arrière-plan).

analyser(chemin) -> (resume JSON-able, [images clés JPEG]) ; resume vide si la vidéo n'a pas d'image lisible.
Visages : détecteur YuNet (OpenCV Zoo, licence MIT, moteur/modeles/) qui donne aussi les yeux, le nez et les coins de la bouche
-> sourire (bouche élargie), tête penchée, regard de côté ; repli : cascades de Haar d'OpenCV si elles sont installées."""
import os
import numpy as np, cv2

ECH = 2.0                                                                  # images analysées par seconde
YUNET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modeles", "face_detection_yunet_2023mar.onnx")

def _yunet():
    try:
        if os.path.exists(YUNET) and hasattr(cv2, "FaceDetectorYN"): return cv2.FaceDetectorYN.create(YUNET, "", (320, 320), 0.75)
    except Exception: pass
    return None

def _cascade(nom):
    for d in (os.environ.get("CASCADES_DIR"), getattr(getattr(cv2, "data", None), "haarcascades", None)):
        if d and os.path.exists(os.path.join(d, nom)) and hasattr(cv2, "CascadeClassifier"):
            c = cv2.CascadeClassifier(os.path.join(d, nom))
            if not c.empty(): return c
    return None

def _dominante(px, k=3):
    """Couleur dominante d'un lot de pixels RGB (la plus fréquente parmi k groupes)."""
    px = np.asarray(px, np.float32).reshape(-1, 3)
    if len(px) < 12: return None
    if len(px) > 4000: px = px[np.random.default_rng(0).choice(len(px), 4000, replace=False)]
    _, lab, cen = cv2.kmeans(px, min(k, len(px)), None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 2, cv2.KMEANS_PP_CENTERS)
    n = np.bincount(lab.ravel(), minlength=len(cen)); return [int(v) for v in cen[int(np.argmax(n))]]

def _palette(px, k=6):
    px = np.asarray(px, np.float32).reshape(-1, 3)
    if len(px) < k * 4: return []
    if len(px) > 20000: px = px[np.random.default_rng(1).choice(len(px), 20000, replace=False)]
    _, lab, cen = cv2.kmeans(px, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 2, cv2.KMEANS_PP_CENTERS)
    n = np.bincount(lab.ravel(), minlength=k) / len(lab)
    return [[int(c[0]), int(c[1]), int(c[2]), round(float(f), 3)] for f, c in sorted(zip(n, cen), key=lambda x: -x[0])]

def _mouvement(g0, g1):
    """Mouvement de la caméra entre deux images : (zoom, déplacement en fraction de largeur) ; None si on ne sait pas."""
    pts = cv2.goodFeaturesToTrack(g0, 150, 0.01, 8)
    if pts is None or len(pts) < 12: return None
    p1, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, pts, None)
    ok = st.ravel() == 1
    if ok.sum() < 10: return None
    M, _ = cv2.estimateAffinePartial2D(pts[ok], p1[ok])
    if M is None: return None
    return float(np.hypot(M[0, 0], M[1, 0])), float(np.hypot(M[0, 2], M[1, 2]) / g0.shape[1])

def analyser(chemin, duree_max=200):
    cap = cv2.VideoCapture(chemin)
    if not cap.isOpened(): return {}, []
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; pas = max(1, int(round(fps / ECH)))
    yn = _yunet()
    visage = None if yn else _cascade("haarcascade_frontalface_default.xml"); sourire = None if yn else _cascade("haarcascade_smile.xml")
    ech, k = [], 0
    while True:
        ok = cap.grab()
        if not ok or k / fps > duree_max: break
        if k % pas == 0:
            ok, im = cap.retrieve()
            if ok and im is not None:
                h, w = im.shape[:2]; l = 360; im = cv2.resize(im, (l, max(2, int(h * l / w))), interpolation=cv2.INTER_AREA)
                ech.append((k / fps, cv2.cvtColor(im, cv2.COLOR_BGR2RGB)))
        k += 1
    cap.release()
    if len(ech) < 2: return {}, []
    H_, W_ = ech[0][1].shape[:2]
    coupes, plans_tailles, obs, mvt, energie, fond_px, pal_px = [], [], [], [], [], [], []
    corps_mvt = []                                                         # P4 : ce qui bouge sous les visages (bras, mains) image par image
    lum, chal, sat = [], [], []
    prec_hist = prec_gris = None; debut_plan = [0]; difs = []
    for j, (t, im) in enumerate(ech):
        hsv = cv2.cvtColor(im, cv2.COLOR_RGB2HSV); gris = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY)
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 4], [0, 180, 0, 256, 0, 256]); cv2.normalize(hist, hist)
        petit = cv2.GaussianBlur(cv2.resize(gris, (36, 64), interpolation=cv2.INTER_AREA), (3, 3), 0).astype(np.float32)
        if prec_hist is not None:                                          # coupe : couleurs très différentes, ou image entièrement changée
            cor = cv2.compareHist(prec_hist, hist, cv2.HISTCMP_CORREL); dif = float(np.mean(np.abs(petit - prec_petit)))
            habituel = float(np.median(difs[-6:])) if difs else 8.0      # changement habituel d'une image à l'autre dans ce plan
            coupe = cor < 0.55 or (dif > max(20.0, 3 * habituel) and cor < 0.95)
            difs.append(dif)
        else: coupe = False
        if coupe: coupes.append(round(t, 2)); debut_plan.append(j)
        elif prec_gris is not None:
            m = _mouvement(prec_gris, gris)
            if m: mvt.append(m)
        lum.append(float(hsv[..., 2].mean())); sat.append(float(hsv[..., 1].mean())); chal.append(float(im[..., 0].mean()) - float(im[..., 2].mean()))
        faces, reperes = [], []
        if yn is not None:
            yn.setInputSize((W_, H_)); _, det = yn.detect(cv2.cvtColor(im, cv2.COLOR_RGB2BGR))
            for d_ in (det if det is not None else []):
                faces.append(tuple(int(v) for v in d_[:4])); reperes.append(d_[4:14].reshape(5, 2))
        elif visage is not None:
            faces = [tuple(int(v) for v in f) for f in visage.detectMultiScale(gris, 1.15, 5, minSize=(max(18, W_ // 18),) * 2)]
        masque = np.ones((H_, W_), bool)
        grand = 0.0
        for kf, (x, y, w, h) in enumerate(faces):
            x, y, w, h = max(0, x), max(0, y), max(2, w), max(2, h)
            grand = max(grand, h / H_)
            habit = im[min(H_, y + int(1.25 * h)):min(H_, y + int(3.0 * h)), max(0, x - w // 4):min(W_, x + w + w // 4)]
            cheveux = im[max(0, y - int(0.22 * h)):max(0, y + int(0.08 * h)), x + w // 5:x + w - w // 5]
            sour, penche, cote = False, 0.0, 0.0
            if reperes:                                                    # œil droit, œil gauche, nez, coin droit, coin gauche de la bouche
                oe_d, oe_g, nez, bo_d, bo_g = reperes[kf]; e_ = float(np.hypot(*(oe_g - oe_d))) or 1.0
                sour = float(np.hypot(*(bo_g - bo_d))) / e_ > 0.93           # bouche nettement élargie : sourire
                penche = float(np.degrees(np.arctan2(oe_g[1] - oe_d[1], oe_g[0] - oe_d[0])))          # tête penchée (degrés)
                cote = float((nez[0] - (oe_d[0] + oe_g[0]) / 2) / e_)                                  # tête tournée / regard de côté
            elif sourire is not None:
                bas = gris[y + h // 2:y + h, x:x + w]
                if bas.size: sour = len(sourire.detectMultiScale(bas, 1.6, 18, minSize=(max(8, w // 5), max(5, h // 10)))) > 0
            obs.append(dict(t=t, x=(x + w / 2) / W_, taille=h / H_, habit=_dominante(habit) if habit.size else None,
                            cheveux=_dominante(cheveux, 2) if cheveux.size else None, sourire=sour, penche=penche, cote=cote))
            masque[max(0, y - h // 3):min(H_, y + int(3.0 * h)), max(0, x - w // 3):min(W_, x + w + w // 3)] = False
            if prec_gris is not None and not coupe:                        # mouvement du buste et des bras de cette personne
                zc = (slice(min(H_ - 1, y + h), min(H_, y + int(3.2 * h))), slice(max(0, x - w), min(W_, x + 2 * w)))
                a_, b_ = gris[zc], prec_gris[zc]
                if a_.size > 20: corps_mvt.append((t, (x + w / 2) / W_, float(np.mean(cv2.absdiff(a_, b_))) / 255))
        plans_tailles.append(grand)
        fond_px.append(im[masque][::7]); pal_px.append(im[::6, ::6].reshape(-1, 3))
        if prec_gris is not None and not coupe:                            # agitation : ce qui bouge d'une image à l'autre
            energie.append(float(np.mean(cv2.absdiff(prec_gris, gris))) / 255)
        prec_hist, prec_gris, prec_petit = hist, gris, petit
    duree = ech[-1][0] + 1 / ECH
    def valeur(g): return "tres_serre" if g > 0.30 else ("serre" if g > 0.16 else ("moyen" if g > 0.07 else "large"))
    vals = [valeur(g) for g in plans_tailles]
    plans = {v: round(vals.count(v) / len(vals), 3) for v in ("tres_serre", "serre", "moyen", "large")}
    cam = {"fixe": 0, "avance": 0, "recul": 0, "travelling": 0, "epaule": 0}
    for z, d in mvt:
        if z > 1.015: cam["avance"] += 1
        elif z < 0.985: cam["recul"] += 1
        elif d > 0.03: cam["travelling"] += 1
        elif d > 0.006: cam["epaule"] += 1
        else: cam["fixe"] += 1
    n_m = max(1, sum(cam.values())); cam = {c: round(v / n_m, 3) for c, v in cam.items()}
    # personnes : regroupées par place à l'écran (gauche, centre, droite)
    personnes = []
    for nom, a, b in (("gauche", 0, 0.4), ("centre", 0.4, 0.6), ("droite", 0.6, 1.01)):
        o = [x for x in obs if a <= x["x"] < b]
        if len(o) < max(2, len(ech) // 12): continue
        hab = [x["habit"] for x in o if x["habit"]]; chv = [x["cheveux"] for x in o if x["cheveux"]]
        personnes.append(dict(place=nom, presence=round(len(o) / len(ech), 3), habit=[int(v) for v in np.median(hab, 0)] if hab else None,
                              cheveux=[int(v) for v in np.median(chv, 0)] if chv else None, sourire=round(sum(x["sourire"] for x in o) / len(o), 3),
                              taille=round(float(np.median([x["taille"] for x in o])), 3),
                              tete_penchee=round(float(np.mean([abs(x["penche"]) for x in o])), 1),
                              regard_cote=round(float(np.mean([abs(x["cote"]) > 0.25 for x in o])), 3)))
    personnes.sort(key=lambda p_: -p_["presence"])
    par_image = {}
    for x in obs: par_image[x["t"]] = par_image.get(x["t"], 0) + 1
    nb = int(np.percentile(list(par_image.values()), 75)) if par_image else 0
    L, Ch = float(np.mean(lum)), float(np.mean(chal))
    moment = "nuit" if L < 70 else ("soir" if Ch > 18 and L < 165 else "jour")
    fp = np.concatenate([f for f in fond_px if len(f)] or [np.zeros((0, 3))])
    gestes = []                                                            # P4 : instants où quelqu'un fait un geste dans l'original
    if len(corps_mvt) >= 6:
        seuil = max(0.02, 2.2 * float(np.median([c[2] for c in corps_mvt])))
        for tc, xc, f in corps_mvt:
            if f < seuil: continue
            if gestes and tc - gestes[-1][0] < 0.6: gestes[-1][2] = max(gestes[-1][2], round(min(1.0, f / seuil / 3), 2)); continue
            gestes.append([round(tc, 2), round(xc, 2), round(min(1.0, f / seuil / 3), 2)])
    resume = dict(gestes=gestes[:120], duree=round(duree, 1), nb_plans=len(coupes) + 1, duree_plan=round(duree / (len(coupes) + 1), 2), coupes=coupes[:60],
                  plans=plans, camera=cam, nb_personnes=nb, personnes=personnes[:3], visages=bool(obs),
                  sourires=round(sum(x["sourire"] for x in obs) / len(obs), 3) if obs else 0.0,
                  energie=round(float(np.clip(np.mean(energie) * 12, 0, 1)) if energie else 0.0, 3),
                  mur=_dominante(fp, 4) if len(fp) else None, palette=_palette(np.concatenate(pal_px)),
                  lumiere=dict(luminosite=round(L, 1), chaleur=round(Ch, 1), saturation=round(float(np.mean(sat)), 1)), moment=moment)
    # images clés : le milieu de chaque plan (8 au plus), pour Claude
    bornes = debut_plan + [len(ech)]; cles = []
    for a, b in zip(bornes[:-1], bornes[1:]):
        if b > a: cles.append(ech[(a + b) // 2][1])
    if len(cles) > 8: cles = [cles[int(i)] for i in np.linspace(0, len(cles) - 1, 8)]
    jpeg = [cv2.imencode(".jpg", cv2.cvtColor(c, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes() for c in cles]
    return resume, jpeg

def texte(resume):
    """Résumé lisible (journal du robot et consigne de Claude)."""
    if not resume: return "image de la vidéo non analysée"
    p = resume["plans"]; c = resume["camera"]
    pers = "; ".join(f"{x['place']} (habit {x['habit']}, cheveux {x['cheveux']}, sourit {int(100 * x['sourire'])} %)" for x in resume["personnes"]) or "aucun visage repéré"
    return (f"{resume['nb_plans']} plans (≈ {resume['duree_plan']} s chacun) ; cadrages : très serré {int(100 * p['tres_serre'])} %, serré {int(100 * p['serre'])} %, "
            f"moyen {int(100 * p['moyen'])} %, large {int(100 * p['large'])} % ; caméra : " + ", ".join(f"{k} {int(100 * v)} %" for k, v in c.items() if v) +
            f" ; {resume['nb_personnes']} personne(s) à l'écran : {pers} ; agitation {resume['energie']} ; lumière {resume['moment']} ; fond {resume['mur']}")
