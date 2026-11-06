"""Sous-titres incrustés de la vidéo d'origine (choix de l'auteur du 6 novembre 2026, idée 21). Réglage OCR=0 pour couper.

Beaucoup de créateurs écrivent leurs répliques à l'écran, souvent d'une couleur par personnage. Le robot les lit (RapidOCR, gratuit,
sur la machine : une image toutes les 0,6 s) et s'en sert de deux façons, seulement si ces textes sont bien les sous-titres du
dialogue (assez de mots en commun avec ce qu'on entend) :
1. les MOTS : là où Whisper et le texte écrit ne disent pas la même chose, l'IA choisit d'après le sens (le texte du créateur
   est souvent le bon : prénoms, argot), les instants ne changent pas (`corriger_mots`) ;
2. QUI PARLE : si chaque couleur de sous-titre correspond nettement à une voix, une phrase écrite de la couleur de A mais rangée
   sur la voix de B revient à A (jamais une voix « sûre », reconnue mot par mot : `couleurs_voix`).
La lecture de texte perd parfois les accents (« telephone ») : on compare les mots sans accents."""
import difflib, os, re, unicodedata

PAS = 0.6
_OCR = {}


def actif(): return os.environ.get("OCR", "1") != "0"


def _sans_accents(w):
    return "".join(c for c in unicodedata.normalize("NFD", str(w).lower()) if unicodedata.category(c) != "Mn")


def _nu(w): return re.sub(r"[^\w']", "", _sans_accents(w).replace("’", "'"))


def _moteur():
    if "m" not in _OCR:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _OCR["m"] = RapidOCR()
        except Exception: _OCR["m"] = None
    return _OCR["m"]


COULEURS = (("blanc", None), ("jaune", 30), ("orange", 18), ("rouge", 0), ("rose", 165), ("violet", 140), ("bleu", 110), ("cyan", 90), ("vert", 60))


def couleur(zone_bgr):
    """Couleur du texte d'une zone (le remplissage des lettres : la couleur claire la plus présente, pas le contour noir)."""
    import cv2, numpy as np
    if zone_bgr.size == 0: return None
    hsv = cv2.cvtColor(zone_bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.int32)
    vif = hsv[hsv[:, 2] > 150]                                             # lettres claires (le contour et le fond foncé sont écartés)
    if len(vif) < 20: return None
    sat = vif[vif[:, 1] > 90]
    if len(sat) < 0.35 * len(vif): return "blanc"
    h = int(np.median(sat[:, 0]))                                          # teinte OpenCV : 0-180
    best = min((c for c in COULEURS if c[1] is not None), key=lambda c: min(abs(h - c[1]), 180 - abs(h - c[1])))
    return best[0]


def lire(video, journal=print, pas=PAS):
    """Lignes de texte vues à l'écran : [{deb, fin, t, couleur, n}] (n = nombre d'images où la ligne est vue)."""
    if not actif() or not video or not os.path.exists(video): return []
    m = _moteur()
    if m is None: journal("  sous-titres de l'original : lecture de texte indisponible (RapidOCR absent)"); return []
    import cv2
    cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS) or 30; n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    vus, k = [], 0
    while k < n:
        cap.set(cv2.CAP_PROP_POS_FRAMES, k); ok, im = cap.read()
        if not ok: break
        t = k / fps; h, w = im.shape[:2]
        if w > 720: im = cv2.resize(im, (720, int(h * 720 / w)), interpolation=cv2.INTER_AREA); h, w = im.shape[:2]
        try: res, _ = m(im)
        except Exception: res = None
        for b, txt, sc in res or []:
            txt = str(txt).strip(); xs = [p[0] for p in b]; ys = [p[1] for p in b]
            if float(sc) < 0.8 or len(re.findall(r"[^\W\d_]", txt)) < 3 or re.search(r"tiktok|@\w", txt, re.I): continue
            if min(ys) < 0.06 * h: continue                                # haut de l'image : pseudo, filigrane
            z = im[int(max(0, min(ys))):int(max(ys)), int(max(0, min(xs))):int(max(xs))]
            vus.append(dict(t=round(t, 2), txt=txt, y=(min(ys) + max(ys)) / 2 / h, couleur=couleur(z)))
        k += max(1, int(round(pas * fps)))
    cap.release()
    lignes = []                                                            # même texte sur des images qui se suivent = une ligne
    for v in sorted(vus, key=lambda v: (v["t"], v["y"])):
        prec = next((l for l in reversed(lignes) if v["t"] - l["fin"] <= pas * 1.6 and difflib.SequenceMatcher(None, _nu(l["t"]), _nu(v["txt"])).ratio() > 0.85), None)
        if prec: prec["fin"] = v["t"]; prec["n"] += 1; prec["couleurs"].append(v["couleur"])
        else: lignes.append(dict(deb=v["t"], fin=v["t"], t=v["txt"], n=1, couleurs=[v["couleur"]]))
    for l in lignes:
        c = [x for x in l.pop("couleurs") if x]; l["couleur"] = max(set(c), key=c.count) if c else None
        l["deb"] = round(max(0.0, l["deb"] - pas / 2), 2); l["fin"] = round(l["fin"] + pas / 2, 2)
    return lignes


def _lettres(w): return re.sub(r"[^a-z0-9]", "", _sans_accents(w))


def aligner(mots, lignes):
    """Chaque mot entendu face au texte écrit à l'écran, LETTRE PAR LETTRE (la lecture de texte colle souvent les mots :
    « SalutMauricetuvas… »). Renvoie (accord, [(i, morceau écrit ou None, ligne)]) : accord = part des lettres retrouvées."""
    lw = [_lettres(m["w"]) for m in mots]; A = "".join(lw)
    O, src, lig = "", [], []                                               # texte écrit (sans espaces), lettre d'origine, n° de ligne
    for k, l in enumerate(sorted(lignes, key=lambda l: l["deb"])):
        for c in str(l["t"]):
            x = _lettres(c)
            if x: O += x; src.append(c); lig.append(k)
    if not A or not O: return 0.0, []
    ls = sorted(lignes, key=lambda l: l["deb"])
    sm = difflib.SequenceMatcher(None, A, O, autojunk=False)
    vers = [None] * (len(A) + 1)                                           # position de chaque lettre entendue dans le texte écrit
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        for i in range(i1, i2 + 1):
            if op == "delete": vers[i] = j1
            else: vers[i] = j1 + round((i - i1) * (j2 - j1) / max(1, i2 - i1))
    egal = sum(b.size for b in sm.get_matching_blocks())
    out, pos = [], 0
    for i, w in enumerate(lw):
        a0, a1 = pos, pos + len(w); pos = a1
        if not w or vers[a0] is None or vers[a1] is None or vers[a1] <= vers[a0]: out.append((i, None, None)); continue
        j0, j1 = vers[a0], vers[a1]
        out.append((i, "".join(src[j0:j1]), ls[lig[min(j0, len(lig) - 1)]]))
    return egal / max(1, len(A)), out


def sous_titres(mots, lignes):
    """Ces textes sont-ils les sous-titres du dialogue ? (part des lettres entendues qu'on retrouve écrites, dans l'ordre)."""
    if not mots or not lignes: return 0.0
    return aligner(mots, lignes)[0]


def corriger_mots(mots, lignes, B=None, journal=print):
    """Mots entendus différemment de ce qui est écrit à l'écran : l'IA choisit d'après le sens (instants inchangés)."""
    if not mots or not lignes: return mots
    accord, paires = aligner(mots, lignes)
    if accord < 0.6:
        journal(f"  textes à l'écran de l'original : pas des sous-titres du dialogue ({round(100 * accord)} % de lettres en commun)"); return mots
    doutes = []
    for i, ecrit, l in paires:
        if not ecrit or l is None or l["n"] < 2: continue                  # vu sur au moins 2 images (lecture fiable)
        if _lettres(ecrit) == _lettres(mots[i]["w"]): continue
        if abs(float(mots[i]["s"]) - (l["deb"] + l["fin"]) / 2) > 6: continue   # trop loin dans le temps : mauvais alignement
        r = difflib.SequenceMatcher(None, _lettres(ecrit), _lettres(mots[i]["w"])).ratio()
        if r >= 0.4 and 2 <= len(_lettres(ecrit)) <= 20: doutes.append(([i], [ecrit]))
    corr = 0
    if doutes:
        import equipe
        choix = equipe._arbitrer(mots, doutes)
        for k, (idx, alt) in enumerate(doutes):
            if choix.get(k) != "B": continue
            for i, w in zip(idx, alt):
                fin = re.search(r"[.,!?…;:]*$", mots[i]["w"]).group()
                mots[i] = dict(mots[i], w=re.sub(r"[.,!?…;:]+$", "", w.strip()) + fin); corr += 1
    if B is not None:
        B.note("ingé son", "sous-titres écrits par le créateur relus", True,
               f"{round(100 * accord)} % des lettres entendues écrites à l'écran, {len(doutes)} doute(s), {corr} mot(s) corrigé(s)")
    return mots


def couleurs_voix(mots, lignes, B=None, journal=print):
    """Une couleur de sous-titre par personnage : les phrases écrites de la couleur de A mais rangées sur la voix de B reviennent à A."""
    if not mots or not lignes: return mots
    accord, paires = aligner(mots, lignes)
    if accord < 0.6: return mots
    coul = {i: l.get("couleur") for i, _, l in paires if l is not None and l.get("couleur")}
    compte = {}
    for i, c in coul.items(): compte.setdefault(c, {}).setdefault(mots[i]["voix"], 0); compte[c][mots[i]["voix"]] += 1
    lien = {}
    for c, vs in compte.items():                                           # couleur -> voix, seulement si c'est net (75 %)
        v, n = max(vs.items(), key=lambda x: x[1])
        if n >= 0.75 * sum(vs.values()) and sum(vs.values()) >= 6: lien[c] = v
    if len(lien) < 2 or len(set(lien.values())) < len(lien): return mots    # une seule couleur, ou deux couleurs pour la même voix
    chg = 0
    for i, c in coul.items():
        if c in lien and mots[i]["voix"] != lien[c] and float(mots[i].get("sure") or 0) < 0.5:
            mots[i] = dict(mots[i], voix=lien[c]); chg += 1
    if B is not None:
        B.note("casting voix", "couleurs des sous-titres de l'original", True,
               ", ".join(f"{c} = {v}" for c, v in lien.items()) + f" ; {chg} mot(s) remis sur la voix de leur couleur")
    return mots
