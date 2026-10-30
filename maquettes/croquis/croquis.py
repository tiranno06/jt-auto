"""Prototype du style « croquis » (planches de l'auteur) : tête ronde blanche à l'encre, ombre aquarelle hachurée, yeux ronds à
reflet, petit nez en c, joues roses hachurées, corps en bâtons (grand) ou petit corps habillé (chibi), papier crème.
Rien n'est branché au robot : sert à faire les visuels de validation."""
import math, numpy as np, cv2

AA = cv2.LINE_AA
ENCRE = (32, 30, 34)
PEAU = (246, 244, 239)
PAPIER = (238, 232, 216)


# ------------------------------------------------------------------ papier, encre, aquarelle, hachures
def papier(w, h, graine=1):
    rng = np.random.default_rng(graine)
    base = np.zeros((h, w, 3), np.float32) + np.array(PAPIER, np.float32)
    bruit = cv2.GaussianBlur(rng.normal(0, 1, (h // 4 + 1, w // 4 + 1)).astype(np.float32), (0, 0), 3)
    bruit = cv2.resize(bruit, (w, h)) * 5 + cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 0.8) * 2.5
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    vign = 1 - 0.10 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    img = (base + bruit[..., None]) * vign[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def _pts(pts): return np.array([[int(round(x * 4)), int(round(y * 4))] for x, y in pts], np.int32)


def encre(img, pts, ep, ferme=False, coul=ENCRE, rng=None, effile=True):
    """Trait d'encre : épaisseur qui varie le long du trait (plus fin aux bouts), léger doublé « croquis »."""
    pts = [tuple(map(float, p)) for p in pts]
    if len(pts) < 2: return
    if ferme: pts = pts + [pts[0]]
    n = len(pts) - 1
    for i in range(n):
        u = (i + 0.5) / n
        e = ep * (0.55 + 0.45 * math.sin(math.pi * u)) if (effile and not ferme) else ep * (0.85 + 0.25 * math.sin(2 * math.pi * u * 1.3 + 1))
        cv2.line(img, _pts([pts[i]])[0], _pts([pts[i + 1]])[0], coul, max(1, int(round(e))), AA, 2)
    if rng is not None:                                                    # 2e passage léger, un peu décalé (main de dessinateur)
        dx, dy = rng.normal(0, ep * 0.18, 2)
        cv2.polylines(img, [_pts([(x + dx, y + dy) for x, y in pts])], False, coul, max(1, int(ep * 0.35)), AA, 2)


def courbe(a, b, c, n=16):
    return [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * b[0] + t * t * c[0], (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * b[1] + t * t * c[1]) for t in np.linspace(0, 1, n)]


def cercle_pts(c, rx, ry=None, a0=0, a1=360, n=72, rot=0):
    ry = rx if ry is None else ry; r = math.radians(rot)
    out = []
    for t in np.linspace(math.radians(a0), math.radians(a1), n):
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((c[0] + x * math.cos(r) - y * math.sin(r), c[1] + x * math.sin(r) + y * math.cos(r)))
    return out


def masque(shape, pts):
    m = np.zeros(shape[:2], np.uint8); cv2.fillPoly(m, [_pts(pts)], 255, AA, 2); return m


def lavis(img, m, coul, force=0.85, graine=0, bord=True):
    """Aquarelle : couleur posée en transparence, grain du papier, bord un peu plus foncé (pigment qui s'accumule)."""
    if m.max() == 0: return
    rng = np.random.default_rng(graine)
    a = cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), 1.2)
    grain = 1 + cv2.resize(cv2.GaussianBlur(rng.normal(0, 1, (m.shape[0] // 6 + 1, m.shape[1] // 6 + 1)).astype(np.float32), (0, 0), 1.5), (m.shape[1], m.shape[0])) * 0.12
    a = a * force * grain
    if bord:
        er = cv2.erode(m, np.ones((5, 5), np.uint8)); b = cv2.GaussianBlur((m.astype(np.float32) - er) / 255, (0, 0), 2)
        c2 = np.array(coul, np.float32) * 0.82
    a = np.clip(a, 0, 1)[..., None]
    out = img.astype(np.float32) * (1 - a) + np.array(coul, np.float32) * a
    if bord: bb = np.clip(b * 0.5, 0, 1)[..., None]; out = out * (1 - bb) + c2 * bb
    img[:] = np.clip(out, 0, 255).astype(np.uint8)


def hachures(img, m, angle=-55, pas=7, ep=1.4, coul=(120, 115, 115), force=0.55, graine=0):
    """Hachures au crayon dans la zone m (ombres)."""
    if m.max() == 0: return
    ys, xs = np.where(m > 0); x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    cal = np.zeros(m.shape, np.uint8); rng = np.random.default_rng(graine)
    a = math.radians(angle); L = (x1 - x0) + (y1 - y0)
    for k in np.arange(-L, L, pas):
        cx, cy = (x0 + x1) / 2 + k * math.cos(a + math.pi / 2), (y0 + y1) / 2 + k * math.sin(a + math.pi / 2)
        p0 = (cx - L * math.cos(a), cy - L * math.sin(a)); p1 = (cx + L * math.cos(a), cy + L * math.sin(a))
        cv2.line(cal, (int(p0[0] * 4), int(p0[1] * 4)), (int(p1[0] * 4), int(p1[1] * 4)), 255, max(1, int(ep + rng.normal(0, 0.3))), AA, 2)
    cal = (cal.astype(np.float32) / 255) * (m.astype(np.float32) / 255) * force
    out = img.astype(np.float32) * (1 - cal[..., None]) + np.array(coul, np.float32) * cal[..., None]
    img[:] = np.clip(out, 0, 255).astype(np.uint8)


def croissant(shape, c, r, cote=(-0.45, 0.4), largeur=0.42):
    """Zone d'ombre en croissant dans un disque (côté bas-gauche par défaut)."""
    m1 = np.zeros(shape[:2], np.uint8); cv2.circle(m1, (int(c[0] * 4), int(c[1] * 4)), int(r * 4), 255, -1, AA, 2)
    m2 = np.zeros(shape[:2], np.uint8)
    cv2.circle(m2, (int((c[0] - cote[0] * r * largeur) * 4), int((c[1] - cote[1] * r * largeur) * 4)), int(r * 1.02 * 4), 255, -1, AA, 2)
    return cv2.subtract(m1, m2)


# ------------------------------------------------------------------ visage
EXPRESSIONS = ("neutre", "heureux", "triste", "surpris", "colere", "fache", "etonne", "joie", "serein", "honteux", "soucieux", "douteux",
               "fatigue", "satisfait", "reveur", "malicieux", "peur", "degout", "amour", "anxiete", "stress", "fierte", "culpabilite",
               "espoir", "solitude", "excitation", "emerveillement", "ennui", "frustration", "gratitude", "inquiet", "parle")


def oeil(img, c, r, regard=(0, 0), ferme=None, rng=None, ep=2.2, forme="rond", haut=1.0):
    """Œil rond blanc cerclé d'encre, grosse pupille noire à reflet. ferme : 'joie' (∩), 'doux' (∪), 'trait', 'clin'."""
    if ferme == "joie": encre(img, cercle_pts(c, r * 0.95, r * 0.75, 200, 340, 18), ep * 1.15, rng=rng); return
    if ferme == "doux": encre(img, cercle_pts((c[0], c[1] - r * 0.35), r * 0.9, r * 0.6, 20, 160, 18), ep * 1.1, rng=rng); return
    if ferme == "trait": encre(img, [(c[0] - r * 0.8, c[1] + r * 0.1), (c[0] + r * 0.8, c[1] + r * 0.1)], ep, rng=rng); return
    if forme == "etoile":
        pts = [(c[0] + (r * 1.05 if k % 2 == 0 else r * 0.45) * math.cos(math.radians(-90 + 36 * k)), c[1] + (r * 1.05 if k % 2 == 0 else r * 0.45) * math.sin(math.radians(-90 + 36 * k))) for k in range(10)]
        cv2.fillPoly(img, [_pts(pts)], (250, 215, 70), AA, 2); encre(img, pts, ep * 0.9, ferme=True); return
    if forme == "coeur":
        pts = [(c[0] + r * 1.1 * 16 * math.sin(t) ** 3 / 16, c[1] - r * 1.1 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 17) for t in np.linspace(0, 2 * math.pi, 40)]
        cv2.fillPoly(img, [_pts(pts)], (220, 70, 80), AA, 2); encre(img, pts, ep * 0.8, ferme=True); return
    pts = cercle_pts(c, r, r * haut)
    cv2.fillPoly(img, [_pts(pts)], (252, 252, 250), AA, 2)
    pr = r * 0.5; pc = (c[0] + regard[0] * r * 0.38, c[1] + regard[1] * r * 0.38 * haut)
    cv2.circle(img, _pts([pc])[0], int(pr * 4), ENCRE, -1, AA, 2)
    cv2.circle(img, _pts([(pc[0] + pr * 0.35, pc[1] - pr * 0.38)])[0], int(pr * 0.32 * 4), (255, 255, 255), -1, AA, 2)
    encre(img, pts, ep, ferme=True, rng=rng)
    if haut < 0.8:                                                         # paupière lourde (fatigué, douteux)
        encre(img, [(c[0] - r, c[1] - r * haut * 0.2), (c[0] + r, c[1] - r * haut * 0.35)], ep * 1.1)


def visage(img, c, R, expr="neutre", regard=(0, 0), rng=None, profil=0.0, nez_vu=True, ouv=None, cligne=0.0, fx=None):
    fx = fx or {}
    """Yeux, sourcils, nez, bouche, joues pour une expression. profil : -1..1 (tourné)."""
    ep = R * 0.045; dx = profil * R * 0.18
    ex, ey, er = R * 0.42, R * 0.0, R * 0.23                              # écart, hauteur, rayon des yeux
    oL, oR = (c[0] - ex + dx, c[1] + ey), (c[0] + ex + dx, c[1] + ey)
    nez = (c[0] + dx * 1.3, c[1] + R * 0.3); bouche = (c[0] + dx * 1.2, c[1] + R * 0.52)
    E = expr
    # -- sourcils (petits arcs épais) : (inclinaison intérieure, hauteur)
    sourc = {"triste": (-0.35, 0.0), "soucieux": (-0.35, 0.0), "anxiete": (-0.4, 0.0), "culpabilite": (-0.3, 0.05), "solitude": (-0.3, 0.0), "inquiet": (-0.4, 0.0),
             "peur": (-0.45, -0.1), "stress": (-0.45, 0.0), "honteux": (-0.3, 0.0), "colere": (0.55, 0.12), "fache": (0.5, 0.1), "frustration": (0.5, 0.1),
             "surpris": (0.0, -0.22), "etonne": (0.0, -0.2), "emerveillement": (0.0, -0.22), "douteux": (0.3, 0.05), "malicieux": (0.25, 0.0),
             "degout": (0.35, 0.05), "fierte": (0.1, -0.05), "ennui": (-0.1, 0.12)}.get(E, (0.0, 0.0))
    # -- yeux
    ferme = {"heureux": "joie", "joie": "joie", "excitation": "joie", "serein": "doux", "satisfait": "doux", "amour": "doux", "gratitude": "doux", "fierte": "doux"}.get(E)
    haut = {"fatigue": 0.55, "ennui": 0.6, "douteux": 0.7}.get(E, 1.0) * (1 - 0.92 * cligne)   # paupière qui descend (clignement doux)
    if cligne > 0.85 and ferme is None: ferme = "doux"
    rg = {"triste": (0, 0.5), "culpabilite": (0.3, 0.7), "solitude": (0, 0.6), "honteux": (0.2, 0.6), "soucieux": (0.6, 0.2), "reveur": (0.5, -0.7),
          "espoir": (0.2, -0.8), "douteux": (0.6, 0.1), "malicieux": (-0.5, 0.1), "inquiet": (0.5, 0.2)}.get(E, regard)
    if fx.get("regard") is not None: rg = fx["regard"]                     # regard dirigé (vers celui qui parle, au ciel, au sol)
    er2 = er * (1.18 if E in ("surpris", "etonne", "peur", "stress") else 1.0)
    for sg, o in ((-1, oL), (1, oR)):
        if E == "malicieux" and sg == 1: oeil(img, o, er, ferme="joie", rng=rng, ep=ep); continue
        oeil(img, o, er2, rg, ferme, rng, ep, forme="etoile" if E == "emerveillement" else "coeur" if E == "amour_x" else "rond", haut=haut)
        if E in ("peur", "stress") and ferme is None:                      # petite pupille effrayée
            cv2.circle(img, _pts([o])[0], int(er2 * 0.55 * 4), (252, 252, 250), -1, AA, 2); cv2.circle(img, _pts([o])[0], int(er2 * 0.22 * 4), ENCRE, -1, AA, 2)
            encre(img, cercle_pts(o, er2), ep, ferme=True)
    if E not in ("serein", "satisfait", "amour", "gratitude"):
        for sg, o in ((-1, oL), (1, oR)):
            if E == "douteux" and sg == -1: inc, h = (-0.1, -0.08)
            else: inc, h = sourc
            h = h - fx.get("leve", 0.0) * 0.25                             # sourcils qui montent sur un mot appuyé
            y0 = o[1] - er * (1.55 - h * 2.2)
            a = (o[0] - sg * er * 0.85, y0 + inc * er * 0.9); b = (o[0] + sg * er * 0.85, y0 - inc * er * 0.9)
            if E in ("colere", "fache", "frustration"): a, b = (a[0], a[1] + er * 0.55), (b[0], b[1] + er * 0.55)
            encre(img, courbe(a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - er * 0.25), b), ep * (2.3 if E in ("colere", "fache", "frustration") else 1.35), rng=rng)
    # -- nez : petit c
    if nez_vu: encre(img, cercle_pts((nez[0] - R * 0.02, nez[1]), R * 0.045, R * 0.05, 300, 470, 12), ep * 0.7, rng=rng)
    # -- bouche
    bw = R * 0.3
    def ouverte(w, h, rire=True, dents=True, langue=True, ang=0):
        pts = courbe((bouche[0] - w, bouche[1] - h * 0.15), (bouche[0], bouche[1] + h * 1.7), (bouche[0] + w, bouche[1] - h * 0.15), 24)
        if rire: pts = pts + courbe((bouche[0] + w, bouche[1] - h * 0.15), (bouche[0], bouche[1] - h * 0.5), (bouche[0] - w, bouche[1] - h * 0.15), 12)
        cv2.fillPoly(img, [_pts(pts)], (95, 35, 40), AA, 2)
        mm = masque(img.shape, pts)
        if langue:
            l_ = np.zeros_like(mm); cv2.ellipse(l_, _pts([(bouche[0] + w * 0.15, bouche[1] + h * 0.75)])[0], (int(w * 0.62 * 4), int(h * 0.45 * 4)), 0, 0, 360, 255, -1, AA, 2)
            z = cv2.bitwise_and(l_, mm); img[z > 0] = (225, 110, 120)
        if dents:
            d_ = np.zeros_like(mm); cv2.rectangle(d_, _pts([(bouche[0] - w, bouche[1] - h)])[0], _pts([(bouche[0] + w, bouche[1] + h * 0.02)])[0], 255, -1, AA, 2)
            z = cv2.bitwise_and(d_, mm); img[z > 0] = (252, 252, 250)
        encre(img, pts, ep * 1.1, ferme=True, rng=rng)
    son = fx.get("son", "a"); micro = fx.get("micro")
    if micro == "mord":                                                    # lèvre mordue (gêne)
        encre(img, courbe((bouche[0] - bw * 0.7, bouche[1]), (bouche[0], bouche[1] - R * 0.05), (bouche[0] + bw * 0.7, bouche[1])), ep * 1.2, rng=rng)
        cv2.rectangle(img, _pts([(bouche[0] - bw * 0.3, bouche[1] - R * 0.01)])[0], _pts([(bouche[0] + bw * 0.3, bouche[1] + R * 0.07)])[0], (252, 252, 250), -1, AA, 2)
        encre(img, [(bouche[0] - bw * 0.3, bouche[1] + R * 0.07), (bouche[0] + bw * 0.3, bouche[1] + R * 0.07)], ep * 0.8)
        for kk in (-1, 0, 1): encre(img, [(bouche[0] + kk * bw * 0.15, bouche[1]), (bouche[0] + kk * bw * 0.15, bouche[1] + R * 0.07)], ep * 0.4, effile=False)
    elif micro == "joues":                                                 # joues gonflées (soupir retenu)
        for sg in (-1, 1):
            m = np.zeros(img.shape[:2], np.uint8); cv2.circle(m, _pts([(bouche[0] + sg * bw * 1.25, bouche[1] - R * 0.05)])[0], int(R * 0.2 * 4), 255, -1, AA, 2)
            lavis(img, m, (240, 170, 170), 0.35, bord=False); encre(img, cercle_pts((bouche[0] + sg * bw * 1.25, bouche[1] - R * 0.05), R * 0.2, a0=90 - sg * 70, a1=270 - sg * 70, n=14), ep * 0.8)
        cv2.ellipse(img, _pts([bouche])[0], (int(bw * 0.18 * 4), int(R * 0.05 * 4)), 0, 0, 360, (95, 35, 40), -1, AA, 2)
    elif micro == "rictus":
        encre(img, [(bouche[0] - bw * 0.8, bouche[1] + R * 0.02), (bouche[0] + bw * 0.2, bouche[1]), (bouche[0] + bw * 0.85, bouche[1] - R * 0.1)], ep * 1.2, rng=rng)
    elif ouv is not None and (ouv > 0.04 or son == "m"):                  # il parle : forme de la bouche selon le son, ouverture selon la voix
        rieur = E in ("heureux", "joie", "excitation", "malicieux", "fierte")
        if son == "m":                                                     # m, b, p : lèvres fermées
            encre(img, courbe((bouche[0] - bw * 0.55, bouche[1]), (bouche[0], bouche[1] + R * 0.03), (bouche[0] + bw * 0.55, bouche[1])), ep * 1.4, rng=rng)
        elif son == "o":                                                   # o, ou, u : bouche ronde
            ww, hh = bw * (0.28 + 0.12 * ouv), R * (0.08 + 0.18 * ouv)
            cv2.ellipse(img, _pts([(bouche[0], bouche[1] + hh * 0.3)])[0], (int(ww * 4), int(hh * 4)), 0, 0, 360, (95, 35, 40), -1, AA, 2)
            encre(img, cercle_pts((bouche[0], bouche[1] + hh * 0.3), ww, hh), ep, ferme=True)
        elif son == "i":                                                   # i, é : bouche large et fine, dents
            ouverte(bw * (0.95 + 0.25 * ouv), R * (0.04 + 0.12 * ouv), rire=True, dents=True, langue=False)
        else:
            ouverte(bw * (0.55 + 0.45 * ouv + (0.3 if rieur else 0)), R * (0.06 + 0.3 * ouv), rire=rieur, dents=ouv > 0.35, langue=ouv > 0.5)
    elif E in ("heureux", "joie", "excitation"): ouverte(bw * (1.15 if E == "heureux" else 1.35), R * (0.42 if E == "heureux" else 0.5))
    elif E in ("surpris",): ouverte(bw * 0.45, R * 0.16, rire=False, dents=False, langue=E == "surpris") if False else (
        cv2.ellipse(img, _pts([bouche])[0], (int(bw * 0.45 * 4), int(R * 0.15 * 4)), 0, 0, 360, (95, 35, 40), -1, AA, 2),
        cv2.ellipse(img, _pts([(bouche[0], bouche[1] + R * 0.07)])[0], (int(bw * 0.3 * 4), int(R * 0.06 * 4)), 0, 0, 360, (225, 110, 120), -1, AA, 2),
        encre(img, cercle_pts(bouche, bw * 0.45, R * 0.15), ep * 1.1, ferme=True, rng=rng))
    elif E in ("etonne", "emerveillement", "parle"):
        cv2.ellipse(img, _pts([bouche])[0], (int(bw * 0.3 * 4), int(R * 0.1 * 4)), 0, 0, 360, (95, 35, 40), -1, AA, 2); encre(img, cercle_pts(bouche, bw * 0.3, R * 0.1), ep, ferme=True)
    elif E == "colere":                                                    # bouche ouverte de rage : dents du haut et du bas
        w, h = bw * 1.1, R * 0.26
        pts = [(bouche[0] - w, bouche[1] - h * 0.1), (bouche[0] - w * 0.3, bouche[1] - h * 0.55), (bouche[0] + w * 0.4, bouche[1] - h * 0.5), (bouche[0] + w, bouche[1] - h * 0.05),
               (bouche[0] + w * 0.7, bouche[1] + h * 0.75), (bouche[0], bouche[1] + h * 0.9), (bouche[0] - w * 0.7, bouche[1] + h * 0.7)]
        cv2.fillPoly(img, [_pts(pts)], (95, 35, 40), AA, 2); mm = masque(img.shape, pts)
        for y0, y1 in ((bouche[1] - h * 0.6, bouche[1] - h * 0.18), (bouche[1] + h * 0.42, bouche[1] + h)):
            d_ = np.zeros_like(mm); cv2.rectangle(d_, _pts([(bouche[0] - w, y0)])[0], _pts([(bouche[0] + w, y1)])[0], 255, -1, AA, 2)
            img[cv2.bitwise_and(d_, mm) > 0] = (250, 250, 246)
            for k in range(-2, 3): encre(img, [(bouche[0] + k * w * 0.36, y0), (bouche[0] + k * w * 0.36, y1)], ep * 0.45, effile=False)
        encre(img, pts, ep * 1.1, ferme=True, rng=rng)
    elif E in ("peur",):                                                   # bouche ouverte tremblante
        w, h = bw * 0.95, R * 0.24
        pts = courbe((bouche[0] - w, bouche[1] + h * 0.2), (bouche[0], bouche[1] - h * 0.9), (bouche[0] + w, bouche[1] + h * 0.1), 12) +               [(bouche[0] + w * 0.5, bouche[1] + h * 0.8), (bouche[0], bouche[1] + h * 0.65), (bouche[0] - w * 0.5, bouche[1] + h * 0.85)]
        cv2.fillPoly(img, [_pts(pts)], (95, 35, 40), AA, 2)
        cv2.ellipse(img, _pts([(bouche[0], bouche[1] + h * 0.45)])[0], (int(w * 0.5 * 4), int(h * 0.3 * 4)), 0, 0, 360, (225, 110, 120), -1, AA, 2)
        d_ = np.zeros(img.shape[:2], np.uint8); cv2.rectangle(d_, _pts([(bouche[0] - w, bouche[1] - h)])[0], _pts([(bouche[0] + w, bouche[1] - h * 0.25)])[0], 255, -1, AA, 2)
        img[cv2.bitwise_and(d_, masque(img.shape, pts)) > 0] = (250, 250, 246)
        encre(img, pts, ep * 1.1, ferme=True, rng=rng)
    elif E in ("frustration", "stress"):                                   # dents serrées en grille
        w, h = bw * (1.15 if E == "colere" else 0.95), R * (0.16 if E == "colere" else 0.12)
        pts = [(bouche[0] - w, bouche[1] - h * 0.3), (bouche[0] + w, bouche[1] - h * 0.6), (bouche[0] + w * 0.9, bouche[1] + h), (bouche[0] - w * 0.9, bouche[1] + h * 1.1)]
        cv2.fillPoly(img, [_pts(pts)], (252, 252, 250), AA, 2)
        encre(img, [(bouche[0] - w, bouche[1] + h * 0.35), (bouche[0] + w, bouche[1] + h * 0.2)], ep * 0.7)
        for k in range(-2, 3): encre(img, [(bouche[0] + k * w * 0.36, bouche[1] - h * 0.5), (bouche[0] + k * w * 0.36, bouche[1] + h * 1.05)], ep * 0.6, effile=False)
        encre(img, pts, ep * 1.1, ferme=True, rng=rng)
    elif E == "degout":
        encre(img, courbe((bouche[0] - bw, bouche[1] + R * 0.05), (bouche[0], bouche[1] - R * 0.1), (bouche[0] + bw, bouche[1] + R * 0.05)), ep * 1.2, rng=rng)
        lg = cercle_pts((bouche[0] + bw * 0.1, bouche[1] + R * 0.08), bw * 0.32, R * 0.14, 0, 180, 16)
        cv2.fillPoly(img, [_pts(lg)], (225, 110, 120), AA, 2); encre(img, lg, ep * 0.9)
    elif E in ("triste", "culpabilite", "solitude", "fache", "inquiet", "soucieux", "anxiete", "ennui", "honteux", "fatigue"):
        k_ = {"fache": 0.5, "ennui": 0.15, "fatigue": 0.2, "honteux": 0.35, "soucieux": 0.4}.get(E, 0.7)
        w = bw * (0.7 if E in ("honteux", "anxiete") else 0.85)
        encre(img, courbe((bouche[0] - w, bouche[1] + R * 0.06 * k_), (bouche[0], bouche[1] - R * 0.12 * k_), (bouche[0] + w, bouche[1] + R * 0.06 * k_)), ep * 1.2, rng=rng)
        if E == "anxiete": encre(img, [(bouche[0] - w, bouche[1]), (bouche[0] - w * 0.4, bouche[1] - R * 0.04), (bouche[0] + w * 0.2, bouche[1] + R * 0.03), (bouche[0] + w, bouche[1] - R * 0.02)], ep * 1.1)
    elif E == "malicieux":
        encre(img, courbe((bouche[0] - bw * 0.6, bouche[1] - R * 0.01), (bouche[0] + bw * 0.2, bouche[1] + R * 0.1), (bouche[0] + bw * 0.95, bouche[1] - R * 0.08)), ep * 1.2, rng=rng)
    elif E == "douteux":
        encre(img, [(bouche[0] - bw * 0.8, bouche[1] + R * 0.03), (bouche[0] + bw * 0.8, bouche[1] - R * 0.02)], ep * 1.2, rng=rng)
    else:                                                                  # sourire (neutre, serein, satisfait, rêveur, amour, fierté, espoir, gratitude)
        k_ = {"neutre": 0.6, "reveur": 0.4, "espoir": 0.3, "fierte": 1.1, "satisfait": 1.0, "serein": 0.7, "amour": 0.9, "gratitude": 0.8}.get(E, 0.7)
        encre(img, courbe((bouche[0] - bw * 1.05, bouche[1] - R * 0.03), (bouche[0], bouche[1] + R * 0.13 * k_), (bouche[0] + bw * 1.05, bouche[1] - R * 0.03)), ep * 1.25, rng=rng)
    # -- joues roses hachurées
    rose = E in ("neutre", "heureux", "joie", "honteux", "amour", "excitation", "satisfait", "serein", "fierte", "gratitude", "reveur", "malicieux", "espoir", "parle") or fx.get("rouge", 0) > 0.05
    if rose:
        f = (0.75 if E in ("honteux", "amour") else 0.45) + 1.1 * fx.get("rouge", 0.0)   # rougissement qui monte en douceur
        for o in (oL, oR):
            jc = (o[0] + (o[0] - c[0]) * 0.55, o[1] + er * 1.35)
            m = np.zeros(img.shape[:2], np.uint8); cv2.ellipse(m, _pts([jc])[0], (int(er * 0.95 * 4), int(er * 0.5 * 4)), 0, 0, 360, 255, -1, AA, 2)
            lavis(img, m, (235, 140, 150), f * 0.55, bord=False)
            for k in range(3): encre(img, [(jc[0] - er * 0.5 + k * er * 0.38, jc[1] + er * 0.22), (jc[0] - er * 0.3 + k * er * 0.38, jc[1] - er * 0.22)], ep * 0.55, coul=(200, 90, 100), effile=False)
    # -- extras (larmes, sueur, marques de colère, vapeur…)
    if E in ("triste", "solitude", "culpabilite", "peur", "frustration"):
        if E in ("pleure",):
            for o in (oL, oR): goutte(img, (o[0] + er * 0.3, o[1] + er * 1.5), er * 0.4, ep)
    if E in ("anxiete", "stress", "soucieux", "peur", "honteux", "inquiet") and "sueur" not in fx: goutte(img, (c[0] + R * 0.78, c[1] - R * 0.35), R * 0.08, ep)
    if fx.get("sueur", 0) > 0.05:                                          # sueur qui perle puis coule (dosée 0..1)
        su = fx["sueur"]; goutte(img, (c[0] + R * 0.78, c[1] - R * 0.45 + R * 0.3 * su), R * 0.1 * min(1, su * 1.5), ep)
        if su > 0.5: goutte(img, (c[0] - R * 0.72, c[1] - R * 0.5 + R * 0.2 * su), R * 0.07, ep)
    if fx.get("larmes", 0) > 0.05:                                         # larmes (de rire ou de tristesse) qui coulent
        la = fx["larmes"]
        for o in (oL, oR):
            x_ = o[0] + (o[0] - c[0]) * 0.35                                  # au coin extérieur de l'œil
            m = np.zeros(img.shape[:2], np.uint8); cv2.line(m, _pts([(x_, o[1] + er * 0.8)])[0], _pts([(x_ + er * 0.08, o[1] + er * (0.9 + 1.6 * la))])[0], 255, int(er * 0.16 * 4), AA, 2)
            lavis(img, m, (120, 185, 240), 0.5, bord=False); goutte(img, (x_ + er * 0.08, o[1] + er * (1.0 + 1.6 * la)), er * 0.2, ep * 0.6)
    if E == "degout":                                                      # teint verdâtre
        pass
    if E == "colere":
        for (u, v) in ((0.55, -0.72), (-0.6, -0.68)): veine(img, (c[0] + u * R, c[1] + v * R), R * 0.12, ep)


def goutte(img, c, r, ep):
    pts = [(c[0], c[1] - r * 1.6)] + cercle_pts(c, r, r, -30, 210, 18)
    cv2.fillPoly(img, [_pts(pts)], (165, 215, 245), AA, 2); encre(img, pts, ep * 0.8, ferme=True)
    cv2.circle(img, _pts([(c[0] - r * 0.3, c[1] - r * 0.2)])[0], int(r * 0.25 * 4), (250, 252, 255), -1, AA, 2)


def veine(img, c, r, ep):
    for a in (45, 135, 225, 315):
        t = math.radians(a); p = (c[0] + r * math.cos(t), c[1] + r * math.sin(t))
        encre(img, courbe((c[0] + r * 0.3 * math.cos(t), c[1] + r * 0.3 * math.sin(t)), (p[0] + r * 0.2, p[1] - r * 0.2), p), ep * 0.9, coul=(180, 30, 30))


def tete(img, c, R, expr="neutre", teint=None, regard=(0, 0), graine=0, profil=0.0, cheveux=None, ombre=True, nez=True, ouv=None, cligne=0.0, fx=None):
    """Tête ronde : blanc cassé, ombre aquarelle grise en bas à gauche + hachures croisées, contour d'encre épais."""
    rng = np.random.default_rng(graine)
    pts = cercle_pts(c, R, R * 0.99, n=96)
    peau = teint or ({"colere": (236, 118, 100), "frustration": (232, 135, 118), "degout": (205, 220, 170), "stress": (232, 228, 218)}.get(expr, PEAU))
    cv2.fillPoly(img, [_pts(pts)], peau, AA, 2)
    if ombre:
        m = croissant(img.shape, c, R, (-0.75, 0.45), 0.5)
        lavis(img, cv2.GaussianBlur(m, (0, 0), R * 0.12), tuple(int(v * 0.78) for v in peau), 0.6, graine, bord=False)
        m2 = croissant(img.shape, c, R, (-0.7, 0.55), 0.24)
        hachures(img, m2, -50, R * 0.07, R * 0.018, (95, 88, 88), 0.6, graine)
        hachures(img, m2, 35, R * 0.1, R * 0.016, (95, 88, 88), 0.4, graine + 1)
    if expr == "colere":                                                   # rougeur plus forte sur le dessus
        m = np.zeros(img.shape[:2], np.uint8); cv2.circle(m, _pts([(c[0], c[1] - R * 0.25)])[0], int(R * 0.75 * 4), 255, -1, AA, 2)
        lavis(img, cv2.bitwise_and(m, masque(img.shape, pts)), (205, 70, 60), 0.3, bord=False)
        hachures(img, croissant(img.shape, c, R, (-0.6, 0.5), 0.3), -50, R * 0.07, R * 0.02, (170, 50, 45), 0.5)
    visage(img, c, R, expr, regard, rng, profil, nez_vu=nez, ouv=ouv, cligne=cligne, fx=fx)
    if cheveux: cheveux_(img, c, R, cheveux, rng)
    encre(img, pts, R * 0.05, ferme=True, rng=rng)                         # contour épais
    # marques de mouvement / d'émotion autour
    if expr in ("joie", "excitation", "surpris", "peur", "colere", "stress", "frustration"):
        for k, a in enumerate((-60, -35, 215, 240) if expr not in ("colere", "frustration") else (-70, -40, -110, -140)):
            t = math.radians(a); p0 = (c[0] + R * 1.18 * math.cos(t), c[1] + R * 1.18 * math.sin(t)); p1 = (c[0] + R * 1.38 * math.cos(t), c[1] + R * 1.38 * math.sin(t))
            encre(img, [p0, p1], R * 0.03, coul=(200, 40, 40) if expr in ("colere", "frustration") else ENCRE)


def cheveux_(img, c, R, style, rng):
    """Quelques mèches au crayon sur le dessus (comme les planches), ou casquette / béret posés."""
    if style == "meches":
        for k in range(5):
            a = math.radians(-115 + k * 12); p = (c[0] + R * 0.95 * math.cos(a), c[1] + R * 0.95 * math.sin(a))
            encre(img, courbe(p, (p[0] + R * 0.05, p[1] - R * 0.2), (p[0] + R * 0.18, p[1] - R * 0.12)), R * 0.03, rng=rng)
    elif style == "herisse":
        for k in range(9):
            a = math.radians(-150 + k * 15); p = (c[0] + R * 0.97 * math.cos(a), c[1] + R * 0.97 * math.sin(a))
            encre(img, [p, (p[0] + R * 0.12 * math.cos(a), p[1] + R * 0.12 * math.sin(a))], R * 0.03)
        for k in range(30): x_, y_ = rng.normal(0, 0.35), rng.uniform(-0.95, -0.55); cv2.circle(img, _pts([(c[0] + x_ * R, c[1] + y_ * R)])[0], int(R * 0.012 * 4), ENCRE, -1, AA, 2)


# ------------------------------------------------------------------ corps
def membre(img, pts, larg, coul=(252, 252, 250), ep=2.0, rng=None):
    """Bras / jambe en bâton : tube fin blanc cerné d'encre (courbe lissée)."""
    P = np.array(pts, np.float32)
    if len(P) == 3: P = np.array(courbe(P[0], P[1], P[2], 14), np.float32)
    for e, cc in ((larg + ep * 2, ENCRE), (larg, coul)):
        cv2.polylines(img, [(P * 4).astype(np.int32)], False, cc, max(1, int(e)), AA, 2)


def main(img, c, r, ang=0, forme="ouverte", ep=2.0, coul=(252, 252, 250)):
    """Main façon planches : UN seul contour (paume + 4 doigts courts arrondis + pouce), blanche, doigts un peu écartés."""
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    rot = lambda x, y: (c[0] + x * ca - y * sa, c[1] + x * sa + y * ca)
    caps = [(rot(0, 0), rot(0, r * 0.15), r * 0.62)]                      # paume
    if forme == "ouverte":
        for a_, L in ((-32, 1.15), (-11, 1.3), (10, 1.28), (30, 1.08)):
            t = math.radians(a_ + 90); caps.append((rot(0, r * 0.2), rot(L * r * math.cos(t), L * r * math.sin(t)), r * 0.2))
        caps.append((rot(-r * 0.2, -r * 0.1), rot(-r * 0.95, r * 0.25), r * 0.21))   # pouce
    else: caps = [(rot(0, 0), rot(0, r * 0.25), r * 0.72)]                  # poing fermé
    for e_, coul in ((r * 0.0 + ep * 2, ENCRE), (0, coul)):
        for a_, b_, w in caps:
            cv2.line(img, _pts([a_])[0], _pts([b_])[0], coul, max(1, int((w * 2 + e_) * 1)), AA, 2) if a_ != b_ else None
            cv2.circle(img, _pts([a_])[0], int((w + e_ / 2) * 4), coul, -1, AA, 2); cv2.circle(img, _pts([b_])[0], int((w + e_ / 2) * 4), coul, -1, AA, 2)


def pied(img, c, r, sens=1, coul=(60, 58, 62), ep=2.0):
    pts = cercle_pts((c[0] + sens * r * 0.5, c[1]), r * 1.15, r * 0.48, 0, 360, 30)
    cv2.fillPoly(img, [_pts(pts)], coul, AA, 2); encre(img, pts, ep, ferme=True)


def ombre_sol(img, c, w):
    m = np.zeros(img.shape[:2], np.uint8); cv2.ellipse(m, _pts([c])[0], (int(w * 4), int(w * 0.18 * 4)), 0, 0, 360, 255, -1, AA, 2)
    lavis(img, m, (150, 145, 140), 0.35, bord=False); hachures(img, m, -15, w * 0.07, w * 0.012, (90, 85, 85), 0.5)


POSES_BRAS = {   # (coude, main) en unités de bras, depuis l'épaule ; y vers le bas
    "ballants": ((-0.25, 0.55), (-0.32, 1.05)), "hanches": ((-0.62, 0.5), (-0.25, 0.92)), "salut": ((-0.65, -0.25), (-0.8, -0.95)),
    "en_lair": ((-0.75, -0.3), (-1.15, -0.85)), "croises": ((-0.35, 0.5), (0.25, 0.45)), "menton": ((0.25, 0.45), (0.05, -0.15)),
    "tete": ((-0.75, -0.25), (-0.45, -0.75)), "joues": ((-0.45, 0.25), (-0.25, -0.38)), "bouche": ((-0.35, 0.35), (-0.05, -0.12)),
    "coeur": ((-0.3, 0.45), (0.12, 0.38)), "poing": ((-0.62, 0.32), (-0.55, 0.78)), "joint": ((-0.3, 0.45), (0.0, 0.15)),
    "genoux": ((-0.45, 0.5), (-0.05, 0.42)), "devant": ((0.45, 0.3), (0.95, 0.45)), "tenir": ((-0.3, 0.55), (-0.05, 0.62)),
    "course_av": ((-0.5, 0.2), (-0.9, -0.05)), "course_ar": ((-0.45, 0.4), (-0.8, 0.65)), "tremble": ((-0.4, 0.4), (-0.1, 0.2)), "telephone": ((-0.4, 0.3), (-0.2, -0.3)),
}
POSES_JAMBES = {  # (genou, pied) en unités de jambe depuis la hanche
    "debout": ((0.03, 0.5), (0.06, 1.0)), "ecart": ((0.2, 0.5), (0.38, 1.0)), "saut": ((0.35, 0.3), (0.12, 0.7)),
    "course_av": ((0.32, 0.42), (0.18, 0.92)), "course_ar": ((-0.12, 0.55), (-0.5, 0.82)), "assis": ((0.75, 0.05), (0.8, 0.6)),
    "replie": ((0.45, -0.25), (0.25, 0.25)), "a_genoux": ((0.1, 0.55), (-0.55, 0.62)), "accroupi": ((0.3, -0.38), (0.28, 0.12)),
    "marche_av": ((0.14, 0.5), (0.26, 0.97)), "marche_ar": ((-0.04, 0.52), (-0.22, 0.97)),
}


VISAGE_MAIN = {"bouche": (0.02, 0.42), "menton": (0.12, 0.88), "joues": (0.92, 0.12), "telephone": (0.92, 0.12)}   # main -> point du visage (unités de R)


def bonhomme(img, x, sol, R, expr="neutre", bras=("ballants", "ballants"), jambes=("debout", "debout"), taille="chibi", graine=0,
             haut="tshirt", c_haut=(120, 160, 210), bas="pantalon", c_bas=(70, 95, 150), chaussures=(55, 52, 58), cheveux=None,
             rayures=None, teint=None, profil=0.0, extras=(), objet=None, chapeau=None, ouv=None, cligne=0.0, penche=0.0, fx=None, sens=1, ecrase=1.0):
    """Personnage complet. taille 'grand' : stickman géant (longues jambes fines, petit maillot, slip) ; 'chibi' : grosse tête, petit
    corps habillé (t-shirt à manches courtes, pantalon de couleur), comme les planches Émotions et Métiers."""
    rng = np.random.default_rng(graine)
    G = taille == "grand"
    ep = R * (0.028 if G else 0.035)
    L_j = R * (2.3 if G else 1.25) * ecrase; L_b = R * (1.2 if G else 0.95); h_tr = R * (1.2 if G else 0.95) * ecrase; l_tr = R * (0.38 if G else 0.5) / ecrase ** 0.5
    w_j = R * (0.045 if G else 0.13); w_b = R * (0.04 if G else 0.05)
    def _nom(p):
        if isinstance(p, str): return p
        if p[0] == "cible": return "cible"
        q = p[1] if p[2] >= 0.5 else p[0]
        return q if isinstance(q, str) else "cible"
    def _haut(n): return (L_j * (0.12 if n == "accroupi" else 0.55 if n == "assis" else 1.0)) + (R * 0.3 if n == "saut" else 0)
    j0 = jambes[0]
    hy_ = _haut(j0) if isinstance(j0, str) else _haut(j0[0]) + (_haut(j0[1]) - _haut(j0[0])) * j0[2]
    jambes_n = tuple(_nom(j) for j in jambes)
    assis = jambes_n[0] == "assis"; accr = jambes_n[0] == "accroupi"
    hanche_y = sol - hy_
    cou_y = hanche_y - h_tr
    tc = (x + penche * R, cou_y - R * (0.9 if G else 0.86))
    # --- jambes (genoux remontés : dessinées après le buste)
    def dessine_jambes():
     def _jambe(sg, nom):
        k_, f_ = POSES_JAMBES[nom]
        h = (x + sg * l_tr * (0.3 if nom == "accroupi" else 0.22), hanche_y)
        abs_ = nom in ("assis", "course_av", "course_ar", "replie", "a_genoux", "marche_av", "marche_ar")
        g = (h[0] + (sens * k_[0] if abs_ else sg * k_[0]) * L_j, h[1] + k_[1] * L_j)   # sens : vers où il marche / court
        f = (h[0] + (sens * f_[0] if abs_ else sg * f_[0]) * L_j, h[1] + f_[1] * L_j)
        return h, g, f
     for sg, jp in zip((-1, 1), jambes):
        if isinstance(jp, str): h, g, f = _jambe(sg, jp)
        else:
            a_, b_ = _jambe(sg, jp[0]), _jambe(sg, jp[1]); u_ = jp[2]
            h, g, f = [(p[0] + (q[0] - p[0]) * u_, p[1] + (q[1] - p[1]) * u_) for p, q in zip(a_, b_)]
        cj = (252, 252, 250) if (G or bas in ("short", "slip")) else c_bas
        membre(img, [h, g, f], w_j, cj, ep)
        if not G and bas == "short":
            membre(img, [h, ((h[0] + g[0]) / 2, (h[1] + g[1]) / 2)], R * 0.2, c_bas, ep)
        pied(img, (f[0], f[1] + R * 0.02), R * (0.15 if G else 0.15), 1 if (f[0] >= h[0]) else -1, chaussures, ep)
    if not accr: dessine_jambes()
    # --- bras (sous le buste), puis manches
    epaules = [(x - l_tr * (0.42 if not G else 0.5), cou_y + R * 0.1), (x + l_tr * (0.42 if not G else 0.5), cou_y + R * 0.1)]
    mains = []
    def _bras(i, nom):
        if not isinstance(nom, str):                                       # ("cible", (x, y)) : la main va à un point précis (toucher l'autre)
            mn = nom[1]; e_ = epaules[i]; d_ = max(1.0, math.hypot(mn[0] - e_[0], mn[1] - e_[1]))
            mid = ((e_[0] + mn[0]) / 2, (e_[1] + mn[1]) / 2); pl = max(0.0, (L_b * 2 - d_)) * 0.35
            sg_ = -1 if i == 0 else 1
            return (mid[0] + sg_ * pl * 0.3, mid[1] + pl), mn
        k_, m_ = POSES_BRAS[nom]
        if i == 0: co = (epaules[0][0] + k_[0] * L_b, epaules[0][1] + k_[1] * L_b); mn = (epaules[0][0] + m_[0] * L_b, epaules[0][1] + m_[1] * L_b)
        else:      co = (epaules[1][0] - k_[0] * L_b, epaules[1][1] + k_[1] * L_b); mn = (epaules[1][0] - m_[0] * L_b, epaules[1][1] + m_[1] * L_b)
        sg_ = -1 if i == 0 else 1
        if nom in VISAGE_MAIN:                                             # main posée sur le visage : visée sur la tête (passe devant)
            dx, dy = VISAGE_MAIN[nom]; mn = (tc[0] + sg_ * dx * R, tc[1] + dy * R)
            co = (epaules[i][0] + sg_ * L_b * (0.55 if G else 0.5), (epaules[i][1] + mn[1]) / 2 + R * 0.35)
        return co, mn
    bras_p = bras; bras = tuple(_nom(b) for b in bras_p)                   # nom dominant (dessin devant / derrière la tête)
    for i, (sg, bp) in enumerate(zip((-1, 1), bras_p)):
        nom = bras[i]
        if isinstance(bp, str): co, mn = _bras(i, bp)
        else:                                                              # fondu entre deux poses (mouvement continu)
            (c0, m0), (c1, m1), u_ = _bras(i, bp[0]), _bras(i, bp[1]), bp[2]
            co = (c0[0] + (c1[0] - c0[0]) * u_, c0[1] + (c1[1] - c0[1]) * u_); mn = (m0[0] + (m1[0] - m0[0]) * u_, m0[1] + (m1[1] - m0[1]) * u_)
        mains.append((epaules[i], co, mn))
        if nom in VISAGE_MAIN: continue                                    # dessiné après la tête
        if G: membre(img, [epaules[i], co, mn], w_b, (252, 252, 250), ep)
        else: encre(img, courbe(epaules[i], co, mn, 14), w_b, rng=rng, effile=False)   # chibi : bras = trait d'encre
    # --- buste
    if G:
        tr = [(x - l_tr * 0.5, cou_y), (x + l_tr * 0.5, cou_y), (x + l_tr * 0.55, hanche_y + R * 0.05), (x - l_tr * 0.55, hanche_y + R * 0.05)]
    else:
        tr = [(x - l_tr * 0.45, cou_y - R * 0.02), (x + l_tr * 0.45, cou_y - R * 0.02), (x + l_tr * 0.55, cou_y + h_tr * 0.35), (x + l_tr * 0.6, hanche_y + R * 0.06), (x - l_tr * 0.6, hanche_y + R * 0.06), (x - l_tr * 0.55, cou_y + h_tr * 0.35)]
        if haut in ("tshirt", "polo", "pull"):                             # manches (courtes : t-shirt)
            for (e_, co, mn) in mains:
                bout = (e_[0] + (co[0] - e_[0]) * (0.55 if haut == "tshirt" else 1.0), e_[1] + (co[1] - e_[1]) * (0.55 if haut == "tshirt" else 1.0))
                if haut == "pull": membre(img, [e_, co, mn], R * 0.16, c_haut, ep)
                else: membre(img, [e_, bout], R * 0.2, c_haut, ep)
    cv2.fillPoly(img, [_pts(tr)], (250, 249, 246), AA, 2)
    if haut:
        lavis(img, masque(img.shape, tr), c_haut, 0.85, graine)
        if rayures:
            for k in range(1, 9):
                yy = cou_y + k * h_tr / 9
                m = masque(img.shape, tr); b_ = np.zeros_like(m); cv2.rectangle(b_, _pts([(x - R, yy - h_tr * 0.03)])[0], _pts([(x + R, yy + h_tr * 0.03)])[0], 255, -1, AA, 2)
                lavis(img, cv2.bitwise_and(m, b_), rayures[k % len(rayures)], 0.9, bord=False)
    else:
        m = masque(img.shape, tr); m_om = np.zeros_like(m); cv2.rectangle(m_om, _pts([(x - R, cou_y)])[0], _pts([(x - l_tr * 0.05, hanche_y)])[0], 255, -1, AA, 2)
        lavis(img, cv2.bitwise_and(m, m_om), (150, 185, 225), 0.45, graine, bord=False)
    om = croissant(img.shape, (x - l_tr * 0.9, cou_y + h_tr * 0.5), l_tr * 0.9, (0.4, 0), 0.3); hachures(img, cv2.bitwise_and(om, masque(img.shape, tr)), -50, R * 0.06, R * 0.012, (80, 75, 80), 0.35)
    encre(img, tr, ep, ferme=True, rng=rng)
    if not G and haut == "tshirt": encre(img, cercle_pts((x, cou_y - R * 0.02), l_tr * 0.22, R * 0.07, 0, 180, 12), ep * 0.8)
    # --- bas : slip (géant), ceinture du pantalon (chibi)
    if G or bas == "slip":
        sl = [(x - l_tr * 0.6, hanche_y - R * 0.05), (x + l_tr * 0.6, hanche_y - R * 0.05), (x + l_tr * 0.55, hanche_y + R * 0.2), (x, hanche_y + R * 0.3), (x - l_tr * 0.55, hanche_y + R * 0.2)]
        cv2.fillPoly(img, [_pts(sl)], (250, 248, 244), AA, 2); lavis(img, masque(img.shape, sl), c_bas, 0.75, graine + 3); encre(img, sl, ep, ferme=True)
    elif bas in ("pantalon", "short"):
        bl = [(x - l_tr * 0.6, hanche_y - R * 0.02), (x + l_tr * 0.6, hanche_y - R * 0.02), (x + l_tr * 0.6, hanche_y + R * 0.2), (x - l_tr * 0.6, hanche_y + R * 0.2)]
        cv2.fillPoly(img, [_pts(bl)], c_bas, AA, 2); lavis(img, masque(img.shape, bl), c_bas, 0.5, graine + 3)
        encre(img, [bl[3], bl[0]], ep); encre(img, [bl[1], bl[2]], ep)
    if accr: dessine_jambes()
    # --- objet tenu, mains
    if objet and bras[1] not in VISAGE_MAIN: objet(img, mains[1][2], R)
    for (e_, co, mn), nom in zip(mains, bras):
        if nom in VISAGE_MAIN: continue
        ang = math.degrees(math.atan2(mn[1] - co[1], mn[0] - co[0])) - 90
        main(img, mn, R * (0.085 if G else 0.11), ang, "poing" if nom in ("poing",) else "ouverte", ep * (1.0 if G else 0.8), (235, 140, 130) if (expr in ("colere", "frustration") and nom == "poing") else (252, 252, 250))
    tete(img, tc, R, expr, teint, graine=graine, profil=profil, cheveux=cheveux, ouv=ouv, cligne=cligne, fx=fx)
    if chapeau: chapeau(img, tc, R)
    for ex in extras: ex(img, tc, R)
    for (e_, co, mn), nom in zip(mains, bras):                             # main sur le visage : l'avant-bras passe devant la tête
        if nom not in VISAGE_MAIN: continue
        if G: membre(img, [e_, co, mn], w_b, (252, 252, 250), ep)
        else: encre(img, courbe(e_, co, mn, 14), w_b, rng=rng, effile=False)
        if objet and nom == bras[1]: objet(img, mn, R)
        ang = math.degrees(math.atan2(mn[1] - co[1], mn[0] - co[0])) - 90
        main(img, mn, R * (0.085 if G else 0.11) * (1.25 if G else 1.0), ang, "ouverte", ep * (1.0 if G else 0.8))
    if expr in ("peur", "stress"):                                         # traits de tremblement autour du corps
        for sg in (-1, 1):
            for k in range(2):
                y0 = cou_y + h_tr * (0.2 + 0.5 * k); x0 = x + sg * (l_tr * 1.05 + R * 0.25)
                encre(img, [(x0, y0), (x0 + sg * R * 0.06, y0 + R * 0.08), (x0, y0 + R * 0.16), (x0 + sg * R * 0.06, y0 + R * 0.24)], ep * 0.8)
    return tc


# ------------------------------------------------------------------ chapeaux, lunettes, objets (style croquis)
def _forme(img, pts, coul, ep, force=0.9, graine=0):
    m = masque(img.shape, pts); cv2.fillPoly(img, [_pts(pts)], (250, 249, 246), AA, 2); lavis(img, m, coul, force, graine); encre(img, pts, ep, ferme=True)


def chapeau(nom, coul=None):
    """Renvoie une fonction (img, tc, R) qui pose le couvre-chef sur la tête ronde."""
    def f(img, c, R):
        ep = R * 0.045
        dome = lambda k, bas: cercle_pts((c[0], c[1] - R * bas), R * k, R * k * 0.9, 180, 360, 40)
        if nom == "casque_pompier":
            _forme(img, [(c[0] - R * 1.2, c[1] - R * 0.45), (c[0] + R * 1.25, c[1] - R * 0.35), (c[0] + R * 1.05, c[1] - R * 0.2), (c[0] - R * 1.0, c[1] - R * 0.3)], (170, 30, 30), ep)
            _forme(img, dome(1.02, 0.42), coul or (205, 40, 40), ep)
            _forme(img, [(c[0] - R * 0.18, c[1] - R * 1.12), (c[0] + R * 0.18, c[1] - R * 1.12), (c[0] + R * 0.2, c[1] - R * 0.62), (c[0], c[1] - R * 0.5), (c[0] - R * 0.2, c[1] - R * 0.62)], (240, 195, 70), ep * 0.8)
        elif nom in ("casquette_officier",):
            _forme(img, cercle_pts((c[0], c[1] - R * 0.98), R * 1.05, R * 0.28), coul or (40, 55, 100), ep)
            _forme(img, [(c[0] - R * 0.85, c[1] - R * 0.95), (c[0] + R * 0.85, c[1] - R * 0.95), (c[0] + R * 0.82, c[1] - R * 0.55), (c[0] - R * 0.82, c[1] - R * 0.55)], coul or (40, 55, 100), ep)
            _forme(img, [(c[0] - R * 0.75, c[1] - R * 0.56), (c[0] + R * 0.75, c[1] - R * 0.56), (c[0] + R * 0.5, c[1] - R * 0.38), (c[0] - R * 0.5, c[1] - R * 0.38)], (30, 30, 34), ep)
            cv2.circle(img, _pts([(c[0], c[1] - R * 0.78)])[0], int(R * 0.12 * 4), (240, 200, 70), -1, AA, 2)
        elif nom in ("casquette",):
            _forme(img, dome(0.98, 0.38), coul or (60, 100, 190), ep)
            _forme(img, [(c[0] - R * 0.2, c[1] - R * 0.42), (c[0] + R * 1.25, c[1] - R * 0.45), (c[0] + R * 1.15, c[1] - R * 0.28), (c[0] - R * 0.2, c[1] - R * 0.3)], coul or (60, 100, 190), ep)
        elif nom == "toque":
            _forme(img, [(c[0] - R * 0.7, c[1] - R * 0.62), (c[0] + R * 0.7, c[1] - R * 0.62), (c[0] + R * 0.72, c[1] - R * 1.05), (c[0] - R * 0.72, c[1] - R * 1.05)], (250, 250, 248), ep, 0.2)
            pts = []
            for k in range(4): pts += cercle_pts((c[0] - R * 0.6 + k * R * 0.4, c[1] - R * 1.35), R * 0.38, R * 0.4, 180 if k == 0 else 210, 360 if k == 3 else 330, 10)
            pts = [(c[0] - R * 0.72, c[1] - R * 1.05)] + pts + [(c[0] + R * 0.72, c[1] - R * 1.05)]
            _forme(img, pts, (250, 250, 248), ep, 0.2)
        elif nom in ("calot", "calot_croix"):
            _forme(img, [(c[0] - R * 0.55, c[1] - R * 0.8), (c[0] + R * 0.55, c[1] - R * 0.8), (c[0] + R * 0.42, c[1] - R * 1.15), (c[0] - R * 0.42, c[1] - R * 1.15)], (250, 250, 248), ep, 0.2)
            if nom == "calot_croix":
                for a, b in (((-0.1, -0.98), (0.1, -0.98)), ((0, -1.08), (0, -0.88))): encre(img, [(c[0] + a[0] * R, c[1] + a[1] * R), (c[0] + b[0] * R, c[1] + b[1] * R)], ep * 1.6, coul=(210, 40, 50), effile=False)
        elif nom == "beret":
            _forme(img, cercle_pts((c[0] + R * 0.15, c[1] - R * 0.78), R * 0.95, R * 0.38, rot=-8), coul or (50, 70, 150), ep)
            encre(img, [(c[0] + R * 0.1, c[1] - R * 1.15), (c[0] + R * 0.14, c[1] - R * 1.3)], ep * 1.4)
        elif nom == "casque_chantier":
            _forme(img, [(c[0] - R * 1.15, c[1] - R * 0.42), (c[0] + R * 1.15, c[1] - R * 0.42), (c[0] + R * 1.1, c[1] - R * 0.3), (c[0] - R * 1.1, c[1] - R * 0.3)], (235, 185, 40), ep)
            _forme(img, dome(1.0, 0.42), (245, 200, 50), ep)
            encre(img, [(c[0], c[1] - R * 1.3), (c[0], c[1] - R * 0.5)], ep * 2.2, coul=(220, 165, 30), effile=False)
        elif nom == "chapeau_paille":
            _forme(img, cercle_pts((c[0], c[1] - R * 0.55), R * 1.55, R * 0.3), (225, 190, 115), ep)
            _forme(img, [(c[0] - R * 0.75, c[1] - R * 0.58), (c[0] - R * 0.7, c[1] - R * 1.18), (c[0] + R * 0.7, c[1] - R * 1.18), (c[0] + R * 0.75, c[1] - R * 0.58)], (225, 190, 115), ep)
            encre(img, [(c[0] - R * 0.74, c[1] - R * 0.75), (c[0] + R * 0.74, c[1] - R * 0.75)], ep * 2.5, coul=(200, 70, 50), effile=False)
        elif nom == "casque_audio":
            encre(img, cercle_pts(c, R * 1.08, R * 1.08, 195, 345, 30), ep * 2.2, effile=False)
            for sg in (-1, 1): _forme(img, cercle_pts((c[0] + sg * R * 1.02, c[1] - R * 0.05), R * 0.2, R * 0.32), (60, 60, 70), ep)
        elif nom == "casque_astronaute":
            encre(img, cercle_pts((c[0], c[1] + R * 0.05), R * 1.3, R * 1.28), R * 0.12, ferme=True, coul=(230, 232, 240))
            encre(img, cercle_pts((c[0], c[1] + R * 0.05), R * 1.38, R * 1.36), ep, ferme=True)
            encre(img, cercle_pts((c[0], c[1] + R * 0.05), R * 1.22, R * 1.2), ep * 0.7, ferme=True)
            encre(img, cercle_pts((c[0] - R * 0.2, c[1] - R * 0.2), R * 0.9, R * 0.85, 200, 250, 12), ep * 2, coul=(255, 255, 255))
        elif nom == "lunettes":
            for sg in (-1, 1): encre(img, cercle_pts((c[0] + sg * R * 0.36, c[1] + R * 0.04), R * 0.3), ep * 0.9, ferme=True)
            encre(img, [(c[0] - R * 0.07, c[1]), (c[0] + R * 0.07, c[1])], ep * 0.9)
        elif nom == "lunettes_soleil":
            for sg in (-1, 1): _forme(img, cercle_pts((c[0] + sg * R * 0.36, c[1] + R * 0.06), R * 0.3, R * 0.24), (30, 30, 36), ep, 1.0)
            encre(img, [(c[0] - R * 0.08, c[1]), (c[0] + R * 0.08, c[1])], ep)
    return f


def tenir(nom_outil, echelle=1.0):
    """Objet tenu (dessins de moteur/metiers.py, même trait noir) collé dans la main droite du personnage."""
    import sys; sys.path.insert(0, "/home/user/jt-auto/moteur"); import metiers, marionnette as M
    def f(img, main_, R):
        o = metiers.outil(nom_outil, R / 140 * echelle) if nom_outil in metiers.OUTILS else M.objet(nom_outil, R / 120 * echelle)
        if o is None: return
        h, w = o.shape[:2]; x0, y0 = int(main_[0] - w / 2), int(main_[1] - h / 2)
        X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(img.shape[1], x0 + w), min(img.shape[0], y0 + h)
        if X1 <= X0 or Y1 <= Y0: return
        sub = o[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]; a = sub[..., 3:4].astype(np.float32) / 255
        img[Y0:Y1, X0:X1] = (img[Y0:Y1, X0:X1] * (1 - a) + sub[..., :3] * a).astype(np.uint8)
    return f


def deco_buste(nom):
    """Détails sur le t-shirt / la veste (dessinés par-dessus le buste) : extras(img, tc, R) appelés après la tête."""
    def f(img, c, R):
        cou = (c[0], c[1] + R * 0.92); ep = R * 0.035
        if nom == "blouse":                                                # col de blouse blanche + stéthoscope
            for sg in (-1, 1): encre(img, [(cou[0] + sg * R * 0.08, cou[1] + R * 0.02), (cou[0] + sg * R * 0.22, cou[1] + R * 0.35), (cou[0] + sg * R * 0.05, cou[1] + R * 0.55)], ep)
        if nom == "stetho":
            encre(img, courbe((cou[0] - R * 0.2, cou[1] + R * 0.05), (cou[0] - R * 0.25, cou[1] + R * 0.55), (cou[0] + R * 0.05, cou[1] + R * 0.55)), ep * 1.3, coul=(70, 75, 85))
            cv2.circle(img, _pts([(cou[0] + R * 0.08, cou[1] + R * 0.55)])[0], int(R * 0.06 * 4), (190, 195, 205), -1, AA, 2)
        if nom == "badge": cv2.circle(img, _pts([(cou[0] + R * 0.18, cou[1] + R * 0.25)])[0], int(R * 0.07 * 4), (240, 200, 70), -1, AA, 2)
        if nom == "noeud":
            for sg in (-1, 1): _forme(img, [(cou[0], cou[1] + R * 0.06), (cou[0] + sg * R * 0.15, cou[1] - R * 0.02), (cou[0] + sg * R * 0.15, cou[1] + R * 0.14)], (25, 25, 30), ep * 0.7, 1.0)
        if nom == "boutons":
            for k in range(4): cv2.circle(img, _pts([(cou[0] + (k % 2 - 0.5) * R * 0.22, cou[1] + R * (0.18 + 0.12 * (k // 2) * 2))])[0], int(R * 0.035 * 4), (60, 60, 70), -1, AA, 2)
        if nom == "bandes":
            for yy in (0.35, 0.65): encre(img, [(cou[0] - R * 0.28, cou[1] + R * yy), (cou[0] + R * 0.28, cou[1] + R * yy)], R * 0.05, coul=(245, 210, 60), effile=False)
        if nom == "salopette":
            for sg in (-1, 1): encre(img, [(cou[0] + sg * R * 0.22, cou[1] - R * 0.02), (cou[0] + sg * R * 0.16, cou[1] + R * 0.4)], R * 0.06, coul=(60, 90, 150), effile=False)
            _forme(img, [(cou[0] - R * 0.24, cou[1] + R * 0.38), (cou[0] + R * 0.24, cou[1] + R * 0.38), (cou[0] + R * 0.3, cou[1] + R * 0.9), (cou[0] - R * 0.3, cou[1] + R * 0.9)], (60, 90, 150), ep, 0.95)
        if nom == "taches":
            for k, cc in enumerate(((220, 60, 60), (60, 120, 220), (245, 200, 50), (80, 170, 90))):
                cv2.circle(img, _pts([(cou[0] + (k % 2 - 0.5) * R * 0.3, cou[1] + R * (0.25 + 0.17 * k))])[0], int(R * 0.05 * 4), cc, -1, AA, 2)
    return f
