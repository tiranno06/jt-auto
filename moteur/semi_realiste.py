"""Décors « semi-réalistes » (choix de l'auteur, 1er novembre 2026 : réglage STYLE_DECOR, « Semi-réaliste » par défaut, « Croquis » au choix).

Le décor est une PEINTURE semi-réaliste (fond de film d'animation : vrai lieu, couleurs chaudes, coups de pinceau doux), faite par la
même IA que les autres décors (Stable Diffusion XL sur Modal), sans aquarelle ni aplats ; les personnages restent en croquis.
Les pieds doivent être VRAIMENT posés au sol (demande de l'auteur) :
1. on demande à l'IA un grand sol libre au premier plan (meubles contre le mur du fond) — 2 tirages par lieu ;
2. la carte de profondeur (Depth Anything, déjà calculée sur Modal) dit où est le sol : sur chaque ligne de l'image, le sol est ce
   qu'on voit le plus ; une chaise, une table, un canapé (plus près) ou un mur (plus loin) s'en écartent (`obstacles`) ;
3. on cherche le cadrage 9:16 (zoom le plus faible) qui met les pieds de chaque personnage (places fixes du moteur, `PIEDS`) sur ce
   sol, sans aucun obstacle autour ni devant eux (`libre`, `cadrer`).
Aucun cadrage possible -> décor dessiné habituel (passé en croquis) : jamais de pieds qui flottent ou de personnage debout sur un meuble."""
import os, re
import numpy as np, cv2

W, H = 1080, 1920
PIED_Y = 1500                                                              # ligne des pieds du moteur (cartoon.position)
PIEDS_X = (190, 285, 540, 795, 890)                                        # places des personnages (1, 2 ou 3 à l'image)


def actif():
    return (os.environ.get("STYLE_DECOR") or "semi_realiste").strip().lower().replace("-", "_") in ("semi_realiste", "semi", "peinture")


DEHORS = {"rue", "parc", "plage", "jardin", "camping", "montagne", "stade", "parking", "arret_bus", "cour_recre", "ferme", "balcon",
          "piscine", "espace", "gare"}


LIEUX_EN = {                                                               # lieux sans description anglaise dans studio.DECOR_EN
    "cuisine": "cozy apartment kitchen, cabinets, fridge, stove, small table with chairs against the wall, window",
    "cabinet_medical": "doctor's office, examination table against the wall, desk with computer, medical posters",
    "salle_sport": "gym, weight machines and dumbbells along the walls, mirrors, rubber floor",
    "classe": "school classroom, blackboard, rows of desks at the back, windows",
    "administration": "administration office counter, waiting chairs along the wall, notice board",
    "hall": "apartment building entrance hall, mailboxes, staircase, front door",
    "caverne": "prehistoric cave, rocky walls, cave paintings, campfire in the back",
    "palais": "royal palace hall, columns, red carpet, throne at the back, chandeliers",
}


def description(lieu, decor="", lumiere=""):
    """Description anglaise du lieu pour la peinture : celle de la mise en scène, sinon celle du lieu reconnu (studio.DECOR_EN)."""
    d = (decor or "").strip()
    if d and (re.search(r"[àâçéèêëîïôûùœ]", d.lower()) or not re.search(r"\b(with|the|and|a|an|of|on)\b", d.lower())):
        d = ""                                                             # description en français : l'IA des décors la comprend mal
    if not d:
        try:
            import studio
            d = studio.DECOR_EN.get(lieu) or LIEUX_EN.get(lieu) or (lieu or "living room").replace("_", " ")
        except Exception: d = LIEUX_EN.get(lieu) or (lieu or "living room").replace("_", " ")
    sol = "large empty pavement in the foreground" if lieu in DEHORS else "large empty floor in the foreground"
    return f"[semi] {d}, {sol}" + (f", {lumiere}" if lumiere else "")


def obstacles(prof, tol=None):
    """prof : carte de profondeur (0 loin … 255 près). Le sol est un plan : sa profondeur (inverse) monte en ligne droite vers le bas
    de l'image ; on la mesure tout en bas (bas de l'image = sol, presque toujours) puis on la prolonge vers le haut. Tout ce qui s'en
    écarte nettement, ou qui s'écarte de ce qu'on voit le plus sur sa ligne, est un obstacle (plus près : chaise, table, lit, canapé ;
    plus loin : mur, porte). Renvoie un masque booléen de la taille de prof."""
    p = cv2.GaussianBlur(prof.astype(np.float32), (0, 0), max(1.0, prof.shape[0] / 400))
    h = p.shape[0]; med = np.median(p, axis=1)
    tol = tol if tol is not None else max(8.0, float(np.std(p)) * 0.18)
    y = np.arange(h); bas = y >= int(h * 0.9)
    a, b = np.polyfit(y[bas], med[bas], 1)                                 # le plan du sol, mesuré tout en bas
    obstacles.pente = float(a * h)                                         # un vrai sol se rapproche nettement vers le bas (> 0)
    plan = (a * y + b)[:, None]
    m = ((np.abs(p - med[:, None]) > tol) | (np.abs(p - plan) > tol * 1.5)).astype(np.uint8)
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)


def libre(obs, x0, y0, ww, hh, xs):
    """Vrai si, dans la fenêtre (x0, y0, ww, hh) de l'image source, la zone autour des pieds de chaque personnage (largeur du corps,
    d'un peu au-dessus des pieds jusqu'en bas de l'image) ne contient aucun obstacle."""
    h, w = obs.shape
    for xp in xs:
        a = int(x0 + (xp - 90) / W * ww); b = int(x0 + (xp + 90) / W * ww)
        c = int(y0 + (PIED_Y - 160) / H * hh)
        z = obs[max(0, c):h, max(0, a):min(w, b)]
        if z.size == 0 or z.mean() > 0.02: return False
    return True


def cadrer(im, prof, n_persos=2):
    """Cadrage 9:16 (1080x1920) où chaque personnage a les pieds sur le sol libre. Renvoie (image, profondeur, zoom) ou None.
    On essaie du zoom le plus faible (tout le décor) au plus fort (×1,7), et de gauche à droite ; la fenêtre touche le bas de l'image."""
    if im is None or prof is None: return None
    h, w = im.shape[:2]
    if prof.shape[:2] != (h, w): prof = cv2.resize(prof, (w, h), interpolation=cv2.INTER_LINEAR)
    obs = obstacles(prof)
    if obstacles.pente < 20: return None                                   # pas de sol en bas de l'image (meuble, mur, gros plan)
    xs = {1: (540,), 2: (285, 795), 3: (190, 540, 890)}.get(n_persos, PIEDS_X)
    ww0 = min(w, h * W / H)                                                # plus grande fenêtre 9:16
    for z in np.arange(1.0, 1.71, 0.05):
        ww = ww0 / z; hh = ww * H / W
        for x0 in sorted(np.linspace(0, w - ww, 9), key=lambda v: abs(v - (w - ww) / 2)):   # du centre vers les bords
            y0 = h - hh; ok = libre(obs, x0, y0, ww, hh, xs)
            if ok:
                x0i, y0i, wwi, hhi = int(round(x0)), int(round(y0)), int(round(ww)), int(round(hh))
                c = cv2.resize(im[y0i:y0i + hhi, x0i:x0i + wwi], (W, H), interpolation=cv2.INTER_LANCZOS4)
                pr = cv2.resize(prof[y0i:y0i + hhi, x0i:x0i + wwi], (W, H), interpolation=cv2.INTER_LINEAR)
                return c, pr, float(z)
    return None
