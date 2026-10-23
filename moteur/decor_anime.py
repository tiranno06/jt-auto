"""Décors dessinés qui vivent (idées 7 à 10 de l'auteur) : petits objets animés, animaux, météo, reflets.

placer(img, lieu, rng, res, moment) : dessine les parties fixes (tasse, ventilateur de plafond, bocal, télé du bar) et note leur
place dans `res` ; animer(img, info, tm, ecr, k, etat) : à chaque image, par-dessus le décor et derrière les personnages :
- trotteuse des horloges, vapeur des tasses, pales du ventilateur, poisson rouge et bulles, match de foot à la télé du bar,
  porte du hall qui s'ouvre quand quelqu'un arrive ;
- un chat qui traverse la pièce de temps en temps (ou la rue), des pigeons qui picorent sur le trottoir et s'envolent quand on crie ;
- météo : gouttes qui coulent sur les vitres, éclairs d'orage, essuie-glace de la voiture.
reflets(img, persos, info, ecr) : reflet discret des personnages dans le miroir, les vitrines et les vitres la nuit.
Coordonnées : celles du décor (1080 x 1920) ; `ecr(x, y)` les passe à l'écran, `k` = zoom du décor."""
import math
import numpy as np, cv2

TRAIT = (26, 22, 30)
AA = cv2.LINE_AA
SOL = 1210


def _i(v): return int(round(v))


def _rond(img, c, r, col, ep=3):
    cv2.circle(img, (_i(c[0]), _i(c[1])), max(1, _i(r)), col, -1, AA)
    if ep: cv2.circle(img, (_i(c[0]), _i(c[1])), max(1, _i(r)), TRAIT, max(1, _i(ep)), AA)


def _ell(img, c, ax, ang, col, ep=3):
    cv2.ellipse(img, (_i(c[0]), _i(c[1])), (max(1, _i(ax[0])), max(1, _i(ax[1]))), ang, 0, 360, col, -1, AA)
    if ep: cv2.ellipse(img, (_i(c[0]), _i(c[1])), (max(1, _i(ax[0])), max(1, _i(ax[1]))), ang, 0, 360, TRAIT, max(1, _i(ep)), AA)


def _ligne(img, a, b, col, ep):
    cv2.line(img, (_i(a[0]), _i(a[1])), (_i(b[0]), _i(b[1])), col, max(1, _i(ep)), AA)


def _poly(img, pts, col, ep=3):
    p = np.array([(_i(x), _i(y)) for x, y in pts], np.int32).reshape(-1, 1, 2)
    cv2.fillPoly(img, [p], col, AA)
    if ep: cv2.polylines(img, [p], True, TRAIT, max(1, _i(ep)), AA)


# ------------------------------------------------------------------ parties fixes, dessinées dans le décor
def tasse(img, x, y, col=(230, 90, 80)):
    """Tasse posée (y = dessus du meuble) : la vapeur est animée ensuite."""
    _poly(img, [(x - 26, y - 56), (x + 26, y - 56), (x + 22, y), (x - 22, y)], col, 4)
    cv2.ellipse(img, (x + 30, y - 30), (14, 16), 0, -90, 90, TRAIT, 9, AA); cv2.ellipse(img, (x + 30, y - 30), (14, 16), 0, -90, 90, col, 4, AA)
    cv2.ellipse(img, (x, y - 56), (26, 7), 0, 0, 360, (110, 70, 45), -1, AA); cv2.ellipse(img, (x, y - 56), (26, 7), 0, 0, 360, TRAIT, 3, AA)


def ventilo_fixe(img, x, y):
    """Ventilateur de plafond : tige et moyeu (les pales tournent ensuite)."""
    _ligne(img, (x, 0), (x, y - 14), TRAIT, 10); _ligne(img, (x, 0), (x, y - 14), (190, 190, 196), 5)


def bocal_fixe(img, x, y_bas, r=62):
    """Bocal à poisson rouge posé sur un meuble (eau, gravier, petite plante)."""
    c = (x, y_bas - r)
    _rond(img, c, r, (190, 225, 245), 5)
    cv2.ellipse(img, (x, _i(c[1] + r * 0.55)), (_i(r * 0.8), _i(r * 0.25)), 0, 0, 180, (200, 170, 120), -1, AA)
    for k in range(3): _ligne(img, (x - 20 + k * 18, c[1] + r * 0.6), (x - 26 + k * 20, c[1] + r * 0.05), (70, 160, 90), 6)
    cv2.ellipse(img, (x, _i(c[1] - r * 0.62)), (_i(r * 0.62), _i(r * 0.14)), 0, 0, 360, (225, 240, 250), -1, AA)
    cv2.ellipse(img, (x, _i(c[1] - r * 0.62)), (_i(r * 0.62), _i(r * 0.14)), 0, 0, 360, TRAIT, 3, AA)
    return (x, c[1], r)


def tele_murale(img, x0, y0, x1, y1):
    """Télé accrochée au mur (le match est animé ensuite)."""
    cv2.rectangle(img, (x0 - 8, y0 - 8), (x1 + 8, y1 + 8), TRAIT, -1)
    _ligne(img, ((x0 + x1) / 2, y0 - 8), ((x0 + x1) / 2, y0 - 60), TRAIT, 10)
    return (x0, y0, x1, y1)


def placer(img, lieu, rng, res, moment):
    """Objets qui bougeront, posés à des places libres de chaque décor dessiné."""
    res.setdefault("tasses", []); res.setdefault("ventilos", []); res.setdefault("bocaux", []); res.setdefault("teles", [])
    res.setdefault("miroirs", []); res.setdefault("vitrines", []); res.setdefault("portes", [])
    if lieu == "salon":
        tasse(img, 470, SOL + 140); res["tasses"].append((470, SOL + 84))
        res["bocaux"].append(bocal_fixe(img, 640, SOL + 140, 56))
    elif lieu == "cuisine":
        tasse(img, 570, 940, (90, 140, 210)); res["tasses"].append((570, 884))
    elif lieu == "bureau":
        ventilo_fixe(img, 300, 90); res["ventilos"].append((300, 90))
    elif lieu == "restaurant":
        ventilo_fixe(img, 540, 110); res["ventilos"].append((540, 110))
    elif lieu == "cabinet_medical":
        from decor_dessin import boite
        boite(img, 730, SOL - 210, 860, SOL + 40, (200, 205, 215), 5)
        res["bocaux"].append(bocal_fixe(img, 795, SOL - 210, 58))
    elif lieu == "bar":
        res["teles"].append(tele_murale(img, 640, 180, 1000, 380))
    elif lieu == "salle_sport":
        res["miroirs"].append((60, 300, 1020, 900))
    elif lieu == "hall":
        res["portes"].append((640, 940, SOL))


# ------------------------------------------------------------------ animation, image par image
def _chat(img, x, y, k, sens, ph, col=(240, 160, 70)):
    """Chat toon qui marche (x, y : pieds au sol à l'écran ; k : taille ; ph : phase de la marche)."""
    s = sens; L = 70 * k
    for j, dx in enumerate((-0.55, -0.35, 0.35, 0.55)):                    # pattes qui alternent
        a = math.sin(ph + (j % 2) * math.pi) * 0.35
        hx = x + dx * L * s; _ligne(img, (hx, y - 26 * k), (hx + math.sin(a) * 16 * k * s, y), TRAIT, 13 * k); _ligne(img, (hx, y - 26 * k), (hx + math.sin(a) * 16 * k * s, y), col, 7 * k)
    q0 = (x - 0.75 * L * s, y - 44 * k)                                    # queue relevée qui ondule
    pts = [(q0[0] - s * 18 * k * u + math.sin(ph * 0.5 + u * 3) * 10 * k * u, q0[1] - 60 * k * u) for u in np.linspace(0, 1, 7)]
    for a_, b_ in zip(pts[:-1], pts[1:]): _ligne(img, a_, b_, TRAIT, 14 * k)
    for a_, b_ in zip(pts[:-1], pts[1:]): _ligne(img, a_, b_, col, 8 * k)
    _ell(img, (x, y - 44 * k), (L * 0.8, 24 * k), 0, col, 3 * k)
    t = (x + 0.8 * L * s, y - 70 * k)                                      # tête, oreilles, yeux, moustaches
    for e in (-1, 1): _poly(img, [(t[0] + (e * 14 - 4) * k, t[1] - 14 * k), (t[0] + (e * 24 - 2) * k, t[1] - 44 * k), (t[0] + (e * 4 + 2) * k, t[1] - 24 * k)], col, 3 * k)
    _rond(img, t, 26 * k, col, 3 * k)
    for e in (-1, 1):
        _ell(img, (t[0] + (e * 9 + 6 * s) * k, t[1] - 4 * k), (4 * k, 7 * k), 0, TRAIT, 0)
        _ligne(img, (t[0] + 14 * s * k, t[1] + 8 * k), (t[0] + 40 * s * k, t[1] + (4 + e * 6) * k), TRAIT, 2 * k)
    _poly(img, [(t[0] + 8 * s * k, t[1] + 4 * k), (t[0] + 16 * s * k, t[1] + 4 * k), (t[0] + 12 * s * k, t[1] + 10 * k)], (230, 110, 130), 0)


def _pigeon(img, x, y, k, sens, picore, vol=0.0):
    """Pigeon gris : il picore (tête qui plonge) ou s'envole (ailes battantes)."""
    s = sens; c = (150, 155, 170)
    if vol <= 0:
        for dx in (-6, 6): _ligne(img, (x + dx * k, y - 14 * k), (x + dx * k, y), (220, 120, 90), 4 * k)
    _ell(img, (x, y - 30 * k), (30 * k, 18 * k), -12 * s, c, 3 * k)
    _poly(img, [(x - 26 * s * k, y - 34 * k), (x - 50 * s * k, y - 26 * k), (x - 28 * s * k, y - 22 * k)], (110, 115, 130), 3 * k)
    if vol > 0:                                                            # ailes
        a = math.sin(vol * 40) * 30 * k
        _poly(img, [(x - 10 * k, y - 34 * k), (x + 12 * k, y - 34 * k), (x - 4 * k * s, y - 34 * k - 26 * k - a)], (170, 175, 190), 3 * k)
    hy = picore * 22 * k
    t = (x + 26 * s * k, y - 46 * k + hy)
    _rond(img, t, 12 * k, (120, 130, 150), 3 * k)
    _ell(img, (t[0] - 2 * s * k, t[1] + 12 * k), (8 * k, 6 * k), 0, (120, 170, 150), 0)
    _rond(img, (t[0] + 4 * s * k, t[1] - 3 * k), 2.5 * k, TRAIT, 0)
    _poly(img, [(t[0] + 10 * s * k, t[1] - 2 * k), (t[0] + 20 * s * k, t[1] + 2 * k), (t[0] + 10 * s * k, t[1] + 4 * k)], (230, 190, 90), 2 * k)


def _poisson(img, c, k, ph):
    _ell(img, c, (16 * k, 9 * k), 0, (250, 130, 40), 2 * k)
    s = 1 if math.cos(ph) > 0 else -1; q = math.sin(ph * 6) * 5 * k
    _poly(img, [(c[0] - 14 * s * k, c[1]), (c[0] - 28 * s * k, c[1] - 9 * k + q), (c[0] - 28 * s * k, c[1] + 9 * k + q)], (250, 150, 60), 2 * k)
    _rond(img, (c[0] + 8 * s * k, c[1] - 2 * k), 2 * k, TRAIT, 0)


def animer(img, info, tm, ecr, k, etat):
    """Tout ce qui bouge dans le décor. etat : lieu, moment, ambiances, t_scene (depuis le début de la scène), entree (quelqu'un
    arrive), cri (quelqu'un crie), graine."""
    lieu = etat.get("lieu", ""); amb = etat.get("ambiances") or ()
    for (x, y, r) in info.get("horloges", []):                             # trotteuse : un pas par seconde
        a = math.radians(int(tm) * 6 - 90); c = ecr(x, y)
        _ligne(img, c, (c[0] + math.cos(a) * r * 0.78 * k, c[1] + math.sin(a) * r * 0.78 * k), (210, 50, 50), 2.5 * k)
    for (x, y) in info.get("tasses", []):                                  # vapeur de la tasse : deux volutes qui montent et ondulent
        for j in (-1, 1):
            pts = [ecr(x + j * 9 + math.sin(tm * 3 + u * 6 + j) * 7, y - 8 - u * 80) for u in np.linspace(0, 1, 8)]
            for a_, b_ in zip(pts[:-1], pts[1:]): _ligne(img, a_, b_, (252, 252, 252), 3.5 * k)
    for (x, y) in info.get("ventilos", []):                                # pales du ventilateur qui tournent
        c = ecr(x, y)
        for j in range(3):
            a = tm * 7.5 + j * 2 * math.pi / 3
            _ell(img, (c[0] + math.cos(a) * 80 * k, c[1] + math.sin(a) * 9 * k), (78 * k * abs(math.cos(a)) + 10 * k, 10 * k), 0, (150, 110, 70), 2.5 * k)
        _ell(img, c, (20 * k, 13 * k), 0, (200, 200, 206), 3 * k)
    for (x, y, r) in info.get("bocaux", []):                               # poisson rouge qui fait des allers-retours + bulles
        ph = tm * 0.9; c = ecr(x + math.sin(ph) * r * 0.5, y + math.sin(ph * 1.7) * r * 0.15)
        _poisson(img, c, k, ph)
        for j in range(3):
            u = (tm * 0.6 + j / 3) % 1; b = ecr(x + r * 0.2 + math.sin(tm * 3 + j) * 4, y + r * 0.4 - u * r * 1.0)
            cv2.circle(img, (_i(b[0]), _i(b[1])), max(1, _i(4 * k)), (250, 252, 255), max(1, _i(1.5 * k)), AA)
    for (x0, y0, x1, y1) in info.get("teles", []):                         # le match de foot à la télé du bar
        a, b = ecr(x0, y0); c, d = ecr(x1, y1); a, b, c, d = _i(a), _i(b), _i(c), _i(d)
        if c - a < 20 or d - b < 20: continue
        a_, b_, c_, d_ = max(0, a), max(0, b), min(img.shape[1], c), min(img.shape[0], d)
        if c_ <= a_ or d_ <= b_: continue
        img[b_:d_, a_:c_] = (70, 160, 80)
        cv2.line(img, ((a + c) // 2, b), ((a + c) // 2, d), (230, 240, 230), max(1, _i(2 * k)), AA)
        cv2.circle(img, ((a + c) // 2, (b + d) // 2), max(2, _i(28 * k)), (230, 240, 230), max(1, _i(2 * k)), AA)
        for j in range(6):                                                 # joueurs qui courent après le ballon
            px = a + (c - a) * (0.15 + 0.7 * ((math.sin(tm * (0.7 + j * 0.13) + j * 1.9) + 1) / 2)); py = b + (d - b) * (0.2 + 0.6 * ((j * 0.37) % 1))
            cv2.circle(img, (_i(px), _i(py)), max(2, _i(7 * k)), (220, 50, 50) if j % 2 else (60, 90, 200), -1, AA)
        bx = a + (c - a) * (0.5 + 0.38 * math.sin(tm * 1.3)); by = b + (d - b) * (0.5 + 0.3 * math.sin(tm * 2.1))
        cv2.circle(img, (_i(bx), _i(by)), max(2, _i(5 * k)), (250, 250, 250), -1, AA)
        cv2.rectangle(img, (a + 6, b + 6), (a + _i(110 * k), b + _i(34 * k)), (20, 20, 26), -1)
        cv2.putText(img, f"{int(tm // 7) % 3} - 1", (a + 10, b + _i(28 * k)), cv2.FONT_HERSHEY_SIMPLEX, 0.7 * k, (250, 250, 250), max(1, _i(2 * k)), AA)
    for (x0, x1, ys) in info.get("portes", []):                            # la porte s'ouvre quand quelqu'un arrive
        t_s = etat.get("t_scene", 9.0)
        if etat.get("entree") and 0 <= t_s < 1.6:
            u = math.sin(math.pi * min(1.0, t_s / 1.6)); y0 = ys - int((x1 - x0) * 2.25)
            a, b = ecr(x0, y0); c, d = ecr(x0 + (x1 - x0) * 0.8 * u, ys)
            if c - a > 2: cv2.rectangle(img, (_i(a), _i(b)), (_i(c), _i(d)), (40, 34, 38), -1)
    # animaux
    if lieu in ("salon", "cuisine", "chambre", "hall", "rue"):             # un chat traverse de temps en temps (≈ toutes les 17 s)
        per, dur = 17.0, 5.5; u = (tm + etat.get("graine", 0) % 7) % per
        if u < dur:
            sens = 1 if int((tm + etat.get("graine", 0) % 7) // per) % 2 == 0 else -1
            xc = -120 + (1080 + 240) * (u / dur); xc = xc if sens > 0 else 1080 - xc
            ys = SOL + (150 if lieu == "rue" else 70)
            c = ecr(xc, ys); col = ((240, 160, 70), (60, 60, 66), (235, 235, 230), (150, 150, 160))[etat.get("graine", 0) % 4]
            _chat(img, c[0], c[1], 0.85 * k, sens, tm * 9, col)
    if lieu == "rue":                                                      # pigeons sur le trottoir : ils s'envolent quand on crie
        for j, (px, sens) in enumerate(((490, 1), (600, -1))):
            vol = etat.get("t_cri", -1.0)
            ys = SOL + 205
            if vol >= 0:
                c = ecr(px + sens * vol * 420, ys - vol * 900)
                if c[1] > -60: _pigeon(img, c[0], c[1], 0.7 * k, sens, 0.0, vol + 0.01)
            else:
                pic = max(0.0, math.sin(tm * 3.1 + j * 2.3)) ** 3
                c = ecr(px + math.sin(tm * 0.4 + j) * 30, ys); _pigeon(img, c[0], c[1], 0.7 * k, sens if math.sin(tm * 0.4 + j) > -0.7 else -sens, pic)
    # météo
    zone = info.get("fenetre")
    if zone and lieu != "rue" and ("pluie" in amb or "orage" in amb):      # gouttes qui coulent sur la vitre (pas dehors)
        fx0, fy0, fx1, fy1 = zone
        for j in range(14):
            g = ((j * 0.618) % 1, (j * 0.377) % 1); per = 3 + (j % 4)
            u = ((tm + j * 0.7) % per) / per
            x = fx0 + (fx1 - fx0) * g[0]; y = fy0 + (fy1 - fy0) * ((g[1] + u * 0.9) % 1)
            c = ecr(x, y); t0 = ecr(x, y - 30)
            _ligne(img, t0, c, (215, 228, 245), 3 * k)
            cv2.circle(img, (_i(c[0]), _i(c[1])), max(2, _i(6 * k)), (225, 236, 250), -1, AA)
            cv2.circle(img, (_i(c[0] - 2 * k), _i(c[1] - 2 * k)), max(1, _i(2 * k)), (255, 255, 255), -1, AA)
        if lieu == "voiture":                                              # essuie-glace arrière
            a = math.radians(-160 + 140 * (0.5 - 0.5 * math.cos(tm * 2.4)))
            p0 = ((fx0 + fx1) / 2, fy1 - 10); p1 = (p0[0] + math.cos(a) * 360, p0[1] + math.sin(a) * 360)
            _ligne(img, ecr(*p0), ecr(*p1), TRAIT, 10 * k); _ligne(img, ecr(*p0), ecr(*p1), (60, 60, 66), 5 * k)
    if "orage" in amb:                                                     # éclair : flash blanc bref (≈ toutes les 6,5 s)
        u = (tm + 1.3) % 6.5
        if u < 0.09 or 0.16 < u < 0.22: img[:] = cv2.addWeighted(img, 0.45, np.full_like(img, 255), 0.55, 0)


def reflets(img, persos, info, ecr, nuit):
    """Reflet des personnages dans le miroir, les vitrines et (la nuit) les vitres : copie inversée gauche-droite, discrète,
    seulement dans ces zones et jamais sur les personnages eux-mêmes. persos : masque booléen des personnages à l'écran."""
    zones = [(z, 0.30) for z in info.get("miroirs", [])] + [(z, 0.13) for z in info.get("vitrines", [])]
    if nuit and info.get("fenetre") and info.get("lieu") not in ("rue", "voiture"): zones.append((info["fenetre"], 0.18))
    if not zones or not persos.any(): return
    H, W = persos.shape
    n, lab, st, _ = cv2.connectedComponentsWithStats(persos.astype(np.uint8), 8)
    ref = np.zeros_like(img); m = np.zeros((H, W), bool)
    for j in range(1, n):                                                  # chaque personnage, retourné sur lui-même, un peu plus
        x, y, w, h, aire = st[j]                                           # petit et plus haut (il est « plus loin » dans le miroir)
        if aire < 400: continue
        cxp, yb = x + w / 2, y + h
        Mx = np.float32([[-0.86, 0, cxp * 1.86], [0, 0.86, yb * 0.14 - 0.06 * h]])
        sub = np.where((lab == j)[..., None], img, 0).astype(np.uint8)
        r_ = cv2.warpAffine(sub, Mx, (W, H), flags=cv2.INTER_LINEAR); m_ = cv2.warpAffine((lab == j).astype(np.uint8) * 255, Mx, (W, H)) > 128
        ref[m_] = r_[m_]; m |= m_
    for (x0, y0, x1, y1), a in zones:
        p0, p1 = ecr(x0, y0), ecr(x1, y1)
        a0, b0, a1, b1 = max(0, _i(p0[0])), max(0, _i(p0[1])), min(W, _i(p1[0])), min(H, _i(p1[1]))
        if a1 - a0 < 8 or b1 - b0 < 8: continue
        z = m[b0:b1, a0:a1] & ~persos[b0:b1, a0:a1]
        if z.any():
            sub = img[b0:b1, a0:a1]; sub[z] = (sub[z].astype(np.float32) * (1 - a) + ref[b0:b1, a0:a1][z].astype(np.float32) * a).astype(np.uint8)
