"""Décors de saison et sons du calendrier (choix de l'auteur, 1er novembre 2026, idées 8 et 11).

- `decorer` : le décor suit la date (heure de Paris) : Noël (1er décembre – 6 janvier : sapin décoré, guirlande lumineuse, neige
  à la fenêtre ou dans la rue), Halloween (15 – 31 octobre : citrouilles sculptées, toiles d'araignée), Saint-Valentin (7 – 14
  février : guirlande de cœurs), été (juillet – août : soleil dehors, plante verte dedans). Tout est posé sur les BORDS du décor
  (jamais derrière les personnages), avant le passage à l'encre et à l'aquarelle. SAISON=0 pour couper ; SAISON=noel (etc.) pour
  forcer une saison (essais).
- `mots_du_moment` : les mots d'un événement proche (Noël, nouvel an, Saint-Valentin, Halloween, rentrée, été, fête des mères /
  pères) ; le tirage des sons TikTok préfère les vidéos qui en parlent (profils_tiktok.choisir). SONS_CALENDRIER=0 pour couper."""
import datetime, math, os
import numpy as np
import cv2

DEHORS = {"rue", "parc", "plage", "jardin", "camping", "montagne", "stade", "parking", "arret_bus", "cour_recre", "ferme", "balcon",
          "piscine", "mariage", "espace"}
AA = cv2.LINE_AA


def aujourdhui():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Europe/Paris")).date()
    except Exception: return datetime.date.today()


def saison(jour=None):
    f = (os.environ.get("SAISON") or "").strip().lower()
    if f == "0": return None
    if f in ("noel", "halloween", "valentin", "ete"): return f
    d = jour or aujourdhui(); m, j = d.month, d.day
    if m == 12 or (m == 1 and j <= 6): return "noel"
    if m == 10 and j >= 15: return "halloween"
    if m == 2 and 7 <= j <= 14: return "valentin"
    if m in (7, 8): return "ete"
    return None


def _sapin(img, x, sol, h):
    c = (40, 120, 60)
    cv2.rectangle(img, (int(x - h * 0.05), int(sol - h * 0.12)), (int(x + h * 0.05), int(sol)), (110, 70, 40), -1, AA)
    for k in range(3):                                                     # trois étages de branches
        y0 = sol - h * (0.12 + 0.28 * k); y1 = y0 - h * 0.42; l = h * (0.36 - 0.09 * k)
        pts = np.array([[x - l, y0], [x + l, y0], [x, y1]], np.int32)
        cv2.fillPoly(img, [pts], c, AA); cv2.polylines(img, [pts], True, (25, 70, 35), 4, AA)
    rng = np.random.default_rng(int(x))
    for _ in range(14):                                                    # boules et guirlande
        yy = sol - h * rng.uniform(0.15, 0.8); ll = h * 0.36 * (1 - (sol - yy) / h) * 0.85
        xx = x + rng.uniform(-ll, ll)
        cv2.circle(img, (int(xx), int(yy)), max(4, int(h * 0.025)), [(220, 40, 40), (240, 200, 40), (60, 120, 230), (240, 240, 240)][_ % 4], -1, AA)
    e = (x, sol - h * 0.98); r = h * 0.06                                  # étoile
    pts = np.array([[e[0] + (r if k % 2 == 0 else r * 0.45) * math.sin(k * math.pi / 5), e[1] - (r if k % 2 == 0 else r * 0.45) * math.cos(k * math.pi / 5)] for k in range(10)], np.int32)
    cv2.fillPoly(img, [pts], (250, 210, 50), AA)


def _guirlande(img, y, couleurs, coeurs=False):
    W = img.shape[1]; prev = None
    for k in range(0, W + 1, 12):
        p = (k, int(y + 40 * math.sin(k / W * math.pi * 3) ** 2));
        if prev: cv2.line(img, prev, p, (60, 50, 40), 3, AA)
        prev = p
    for j, k in enumerate(range(40, W, 90)):
        p = (k, int(y + 40 * math.sin(k / W * math.pi * 3) ** 2) + 14); c = couleurs[j % len(couleurs)]
        if coeurs:
            cv2.circle(img, (p[0] - 9, p[1]), 11, c, -1, AA); cv2.circle(img, (p[0] + 9, p[1]), 11, c, -1, AA)
            cv2.fillPoly(img, [np.array([[p[0] - 19, p[1] + 4], [p[0] + 19, p[1] + 4], [p[0], p[1] + 26]], np.int32)], c, AA)
        else:
            cv2.ellipse(img, p, (9, 14), 0, 0, 360, c, -1, AA); cv2.circle(img, (p[0] - 3, p[1] - 4), 3, (255, 255, 255), -1, AA)


def _citrouille(img, x, sol, r):
    for dx in (-0.45, 0.45, 0.0):
        cv2.ellipse(img, (int(x + dx * r), int(sol - r)), (int(r * 0.62), int(r)), 0, 0, 360, (235, 120, 25), -1, AA)
        cv2.ellipse(img, (int(x + dx * r), int(sol - r)), (int(r * 0.62), int(r)), 0, 0, 360, (150, 70, 20), 3, AA)
    cv2.rectangle(img, (int(x - r * 0.1), int(sol - r * 2.25)), (int(x + r * 0.1), int(sol - r * 1.9)), (80, 110, 40), -1, AA)
    for dx in (-0.4, 0.4):                                                 # yeux et bouche sculptés
        cv2.fillPoly(img, [np.array([[x + dx * r - r * 0.15, sol - r * 1.15], [x + dx * r + r * 0.15, sol - r * 1.15], [x + dx * r, sol - r * 1.45]], np.int32)], (60, 30, 10), AA)
    cv2.ellipse(img, (int(x), int(sol - r * 0.65)), (int(r * 0.5), int(r * 0.22)), 0, 0, 180, (60, 30, 10), -1, AA)


def _toile(img, coin, r):
    cx, cy = coin; sx = 1 if cx == 0 else -1
    for a in np.linspace(0, math.pi / 2, 5):
        cv2.line(img, (cx, cy), (int(cx + sx * r * math.cos(a)), int(cy + r * math.sin(a))), (235, 235, 235), 2, AA)
    for k in (0.35, 0.6, 0.85):
        pts = np.array([[cx + sx * r * k * math.cos(a), cy + r * k * math.sin(a)] for a in np.linspace(0, math.pi / 2, 6)], np.int32)
        cv2.polylines(img, [pts], False, (235, 235, 235), 2, AA)


def _neige(img, x0, y0, x1, y1, graine=1, sol=None):
    rng = np.random.default_rng(graine)
    for _ in range(int((x1 - x0) * (y1 - y0) / 2500)):
        cv2.circle(img, (int(rng.uniform(x0, x1)), int(rng.uniform(y0, y1))), int(rng.integers(2, 6)), (250, 250, 252), -1, AA)
    if sol is not None:                                                    # tapis de neige au sol
        cv2.rectangle(img, (int(x0), int(sol)), (int(x1), int(min(img.shape[0], sol + 26))), (246, 248, 252), -1, AA)


def decorer(img, lieu, info=None, moment="jour"):
    """Décor (image RGB, 1080×1920 ou autre) habillé pour la saison. Renvoie une copie (ou l'image telle quelle hors saison)."""
    s = saison()
    if s is None or img is None or getattr(img, "ndim", 0) != 3: return img
    alpha = img[..., 3:] if img.shape[2] == 4 else None
    out = np.ascontiguousarray(img[..., :3].copy()); H, W = out.shape[:2]; k = H / 1920
    sol = (info or {}).get("sol") or int(1210 * k) if H >= 1000 else int(H * 0.63)
    pieds = int(1500 * k) if H >= 1000 else int(H * 0.78)
    dehors = lieu in DEHORS; fen = (info or {}).get("fenetre")
    if s == "noel":
        if dehors:
            _neige(out, 0, 0, W, sol, 3, sol=sol); _guirlande(out, int(60 * k), [(240, 60, 60), (250, 210, 60), (70, 160, 240), (90, 200, 90)])
        else:
            if fen and fen[2] - fen[0] < W * 0.95: _neige(out, fen[0] + 8, fen[1] + 8, fen[2] - 8, fen[3] - 8, 5)
            _sapin(out, int(W * 0.08), pieds, int(560 * k)); _guirlande(out, int(40 * k), [(240, 60, 60), (250, 210, 60), (70, 160, 240), (90, 200, 90)])
    elif s == "halloween":
        _citrouille(out, int(W * 0.07), pieds, int(55 * k)); _citrouille(out, int(W * 0.93), pieds, int(45 * k))
        _toile(out, (0, 0), int(220 * k)); _toile(out, (W - 1, 0), int(180 * k))
    elif s == "valentin":
        _guirlande(out, int(50 * k), [(230, 50, 80), (250, 140, 170), (200, 30, 60)], coeurs=True)
    elif s == "ete":
        if not dehors:                                                     # plante verte en pot sur le côté (dehors : le soleil y est déjà)
            x = int(W * 0.93); cv2.rectangle(out, (x - int(40 * k), pieds - int(90 * k)), (x + int(40 * k), pieds), (190, 100, 60), -1, AA)
            for a in np.linspace(-1.2, 1.2, 7):
                cv2.ellipse(out, (int(x + 70 * k * math.sin(a)), int(pieds - 90 * k - 60 * k * math.cos(a))), (int(16 * k), int(70 * k)), math.degrees(a), 0, 360, (60, 150, 70), -1, AA)
    return np.dstack([out, alpha]) if alpha is not None else out


# ------------------------------------------------------------------ sons du calendrier
EVENEMENTS = (  # (mois, jour de début, mois, jour de fin, mots)
    (12, 1, 12, 25, r"no[ëe]l|sapin|cadeau|p[èe]re no[ëe]l|r[ée]veillon|f[êe]tes"),
    (12, 26, 1, 2, r"nouvel an|r[ée]veillon|bonne ann[ée]e|r[ée]solution|minuit"),
    (2, 1, 2, 14, r"saint[- ]valentin|valentin|amoureu|bisou|couple|c[œo]eur"),
    (10, 15, 10, 31, r"halloween|citrouille|bonbon|d[ée]guis|sorci[èe]re|fant[ôo]me|zombie|peur"),
    (8, 20, 9, 10, r"rentr[ée]e|[ée]cole|coll[èe]ge|lyc[ée]e|prof|cartable|devoirs"),
    (6, 20, 8, 20, r"vacances|plage|piscine|[ée]t[ée]|bronz|camping|chaleur|canicule"),
    (5, 15, 5, 31, r"f[êe]te des m[èe]res|maman|ma m[èe]re"),
    (6, 5, 6, 21, r"f[êe]te des p[èe]res|papa|mon p[èe]re"),
)


def mots_du_moment(jour=None):
    """Motif (regex) des événements en cours ou tout proches, ou None."""
    if os.environ.get("SONS_CALENDRIER", "1") == "0": return None
    d = jour or aujourdhui(); t = (d.month, d.day); out = []
    for m0, j0, m1, j1, mots in EVENEMENTS:
        if (m0, j0) <= (m1, j1): dedans = (m0, j0) <= t <= (m1, j1)
        else: dedans = t >= (m0, j0) or t <= (m1, j1)                     # à cheval sur deux années
        if dedans: out.append(mots)
    return "|".join(f"(?:{m})" for m in out) or None
