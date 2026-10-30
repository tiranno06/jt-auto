"""Outils de la 2e série de visuels « croquis » : coiffures, âges, meubles, textes, décors et véhicules passés au style croquis."""
import math, sys, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
import croquis as C
sys.path.insert(0, "/home/user/jt-auto/moteur")

POL = "/home/user/jt-auto/polices/Poppins-Medium.ttf"; POLB = "/home/user/jt-auto/polices/Poppins-Bold.ttf"


def texte(img, t, x, y, taille=40, gras=False, centre=True, coul=C.ENCRE):
    pil = Image.fromarray(img); d = ImageDraw.Draw(pil); f = ImageFont.truetype(POLB if gras else POL, taille)
    w = d.textlength(t, font=f); d.text((x - w / 2 if centre else x, y), t, font=f, fill=coul); img[:] = np.array(pil)


def coiffure(style, coul=(70, 50, 40)):
    """Cheveux posés sur la tête ronde (appelés après la tête) : courts, longs, queue, chignon, carré, boucles, blancs, afro."""
    def f(img, c, R):
        ep = R * 0.04; x, y = c
        cap = C.cercle_pts(c, R * 1.04, R * 1.03, 207, 333, 30)
        if style in ("courts", "blancs", "carre", "longs", "queue", "chignon"):
            bas = R * (0.5 if style in ("courts", "blancs") else 0.4)       # assez haut : les sourcils restent visibles
            front = C.courbe((x + R * 0.92, y - bas), (x + R * 0.1, y - R * 0.68), (x - R * 0.92, y - bas), 16)
            C._forme(img, cap + front, coul, ep)
            for k in range(4):                                             # mèches au crayon
                a = math.radians(-150 + k * 22); p = (x + R * 0.8 * math.cos(a), y + R * 0.8 * math.sin(a))
                C.encre(img, C.courbe(p, (p[0] + R * 0.1, p[1] + R * 0.05), (p[0] + R * 0.22, p[1] + R * 0.12)), ep * 0.6)
        if style in ("longs", "carre"):
            L = R * (1.35 if style == "longs" else 0.75)
            for sg in (-1, 1):
                pts = [(x + sg * R * 0.95, y - R * 0.35), (x + sg * R * 1.12, y + L * 0.5), (x + sg * R * 1.05, y + L), (x + sg * R * 0.72, y + L * 0.92), (x + sg * R * 0.84, y + R * 0.1)]
                C._forme(img, pts, coul, ep)
        if style == "queue":
            pts = C.courbe((x + R * 0.85, y - R * 0.6), (x + R * 1.7, y - R * 0.5), (x + R * 1.35, y + R * 0.6), 12)
            pts += C.courbe((x + R * 1.2, y + R * 0.55), (x + R * 1.35, y - R * 0.2), (x + R * 0.8, y - R * 0.35), 10)
            C._forme(img, pts, coul, ep); C._forme(img, C.cercle_pts((x + R * 0.9, y - R * 0.5), R * 0.12), (210, 60, 80), ep * 0.7)
        if style == "chignon": C._forme(img, C.cercle_pts((x, y - R * 1.12), R * 0.32, R * 0.27), coul, ep)
        if style in ("boucles", "afro"):
            k_ = 1.25 if style == "afro" else 1.08
            for a in range(190, 355, 14):
                t = math.radians(a); C._forme(img, C.cercle_pts((x + R * k_ * 0.92 * math.cos(t), y + R * k_ * 0.92 * math.sin(t)), R * 0.2), coul, ep * 0.7)
    return f


def rides(img, c, R):
    for sg in (-1, 1): C.encre(img, C.courbe((c[0] + sg * R * 0.55, c[1] + R * 0.0), (c[0] + sg * R * 0.62, c[1] + R * 0.07), (c[0] + sg * R * 0.58, c[1] + R * 0.14), 6), R * 0.02)
    C.encre(img, [(c[0] - R * 0.25, c[1] - R * 0.52), (c[0] + R * 0.25, c[1] - R * 0.52)], R * 0.02)


def moustache(img, c, R):
    for sg in (-1, 1): C._forme(img, C.courbe((c[0], c[1] + R * 0.28), (c[0] + sg * R * 0.25, c[1] + R * 0.2), (c[0] + sg * R * 0.32, c[1] + R * 0.33), 8) + [(c[0] + sg * R * 0.05, c[1] + R * 0.34)], (225, 225, 228), R * 0.025)


AGES = {  # (rayon de tête, coiffure, extras) par âge et par silhouette
    "chibi": {"enfant": 100, "ado": 118, "adulte": 135, "senior": 130},
    "grand": {"enfant": 74, "ado": 90, "adulte": 104, "senior": 100},
}


def chaise(img, x, sol, R, coul=(170, 120, 80), sens=1, h=None):
    ep = R * 0.04; h = h or R * 0.95
    C._forme(img, [(x - R * 0.7, sol - h), (x + R * 0.7, sol - h), (x + R * 0.7, sol - h + R * 0.16), (x - R * 0.7, sol - h + R * 0.16)], coul, ep)
    for dx in (-0.6, 0.6): C.encre(img, [(x + dx * R, sol - h + R * 0.16), (x + dx * R, sol)], ep * 1.6, effile=False)
    C._forme(img, [(x - sens * R * 0.72, sol - h - R * 1.0), (x - sens * R * 0.56, sol - h - R * 1.0), (x - sens * R * 0.56, sol - h), (x - sens * R * 0.72, sol - h)], coul, ep)


def croquifier(rgb, papier, force=0.62, hach=True, graine=0):
    """Passe un dessin du robot (décor, véhicule) au style croquis : traits noirs gardés (encre), couleurs en aquarelle claire posées
    sur le grain du papier, ombres hachurées."""
    rgb = rgb.astype(np.float32); g = rgb.sum(2)
    trait = (g < 200).astype(np.float32)
    trait = cv2.GaussianBlur(trait, (0, 0), 0.6)
    past = rgb * force + 255 * (1 - force)
    hsv = cv2.cvtColor(np.clip(past, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32); hsv[..., 1] *= 0.8
    past = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
    rng = np.random.default_rng(graine)
    bruit = cv2.GaussianBlur(rng.normal(0, 1, rgb.shape[:2]).astype(np.float32), (0, 0), 6) * 10
    out = past * (papier.astype(np.float32) / np.array(C.PAPIER, np.float32)) + bruit[..., None]
    if hach:                                                               # hachures dans les zones sombres (ombres)
        som = ((g / 3 < 120) & (g >= 200)).astype(np.uint8) * 255
        m = np.zeros(rgb.shape[:2], np.uint8)
        h, w = m.shape
        for k in range(-h, w, 14): cv2.line(m, (k, h), (k + h, 0), 255, 2, cv2.LINE_AA)
        out = np.where((cv2.bitwise_and(som, m) > 0)[..., None], out * 0.8, out)
    out = out * (1 - trait[..., None]) + np.array(C.ENCRE, np.float32) * trait[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def poser(img, rgba, x0, y0, papier=None):
    h, w = rgba.shape[:2]; X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(img.shape[1], x0 + w), min(img.shape[0], y0 + h)
    sub = rgba[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]; a = sub[..., 3:4].astype(np.float32) / 255
    col = sub[..., :3] if papier is None else croquifier(sub[..., :3], papier[Y0:Y1, X0:X1])
    img[Y0:Y1, X0:X1] = (img[Y0:Y1, X0:X1] * (1 - a) + col * a).astype(np.uint8)


def bulle(img, x, y, t, taille=30, queue=(0, 60), largeur=None):
    pil = Image.fromarray(img); d = ImageDraw.Draw(pil); f = ImageFont.truetype(POLB, taille)
    w = largeur or d.textlength(t, font=f) * 1.18 + taille * 1.6; h = taille * 2.3
    img[:] = np.array(pil)
    pts = C.cercle_pts((x, y), w / 2, h / 2, n=60)
    tail = [(x - w * 0.12, y + h * 0.35), (x + queue[0], y + h / 2 + queue[1]), (x + w * 0.08, y + h * 0.4)]
    cv2.fillPoly(img, [C._pts(tail)], (253, 252, 248), C.AA, 2); C.encre(img, tail, 3, effile=False)
    cv2.fillPoly(img, [C._pts(pts)], (253, 252, 248), C.AA, 2); C.encre(img, pts, 3.2, ferme=True)
    texte(img, t, x, y - taille * 0.72, taille, True)


def scene(img, x0, y0, lieu, persos, titre, moment="jour", graine=3, bulles=(), vehicule=None, w=720, h=1280):
    """Une image de vidéo verticale (9:16) : décor du robot passé en croquis, personnages croquis, bulles."""
    import decor_dessin as D
    r = D.dessiner(lieu, {"moment": moment}, graine)
    fond = cv2.resize(r["fond"], (w, h), interpolation=cv2.INTER_AREA)
    pap = img[y0:y0 + h, x0:x0 + w].copy()
    img[y0:y0 + h, x0:x0 + w] = croquifier(fond, pap, graine=graine)
    k = w / 1080
    if vehicule:
        nom, l, vx, sens = vehicule
        import vehicules as V
        im = V.VEHICULES[nom](sens, int(l * k)) if nom != "voiture" else V.voiture((200, 50, 50), sens, int(l * k))
        hs = V.hauteur_sol(nom, int(l * k)) if nom != "voiture" else V.sol(int(l * k))
        poser(img, im, int(x0 + vx * k), int(y0 + 1335 * k - hs), img)
    for p in persos:
        taille = p.get("taille", "chibi"); R = AGES[taille][p.get("age", "adulte")] * k * p.get("k", 1.4)
        sol = y0 + p.get("sol", 1500) * k; x = x0 + p["x"] * k
        if p.get("chaise"): chaise(img, x + R * 0.1, sol, R * (1.0 if taille == "chibi" else 0.9), h=R * (1.25 if taille == "chibi" else 2.3) * 0.55 - R * 0.05)
        C.ombre_sol(img, (x, sol + 4), R * 0.9)
        C.bonhomme(img, x, sol, R, p.get("expr", "neutre"), bras=p.get("bras", ("ballants", "ballants")), jambes=p.get("jambes", ("debout", "debout")),
                   taille=taille, graine=p.get("g", 0), haut=p.get("haut", "tshirt"), c_haut=p.get("c_haut", (120, 160, 210)), c_bas=p.get("c_bas", (60, 80, 130)),
                   extras=p.get("extras", []), objet=p.get("objet"), chapeau=p.get("chapeau"), rayures=p.get("rayures"))
    if r.get("avant") is not None:
        av = cv2.resize(r["avant"], (w, h), interpolation=cv2.INTER_AREA)
        poser(img, av, x0, y0, img)
    for b in bulles: bulle(img, x0 + b[0] * k, y0 + b[1] * k, b[2], int(b[3] if len(b) > 3 else 30), b[4] if len(b) > 4 else (0, 60))
    C.encre(img, [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)], 4, ferme=True, effile=False)
    texte(img, titre, x0 + w / 2, y0 + h + 14, 40, True)
