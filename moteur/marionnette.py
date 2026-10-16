"""Marionnettes 2D animées pour les sketchs libres et les gags éclair (moteur « cartoon », distinct du JT).

Personnages maison : petits bonshommes à grosse tête ronde, trait noir, chacun avec un signe distinctif (bonnet, casquette,
nœud, lunettes, mèche) et une coiffure. Tout est dessiné image par image (pas d'image fixe) : bouche synchronisée sur la voix,
clignements, regard, sourcils, rides d'expression, émotions, mains (index pointé, poing, pouce, paume), gestes des bras,
rebonds, effets (larmes, colère, fumée, cœurs…).

Garde-robe (studio.py la choisit pour chaque épisode) : haut (t-shirt, chemise, blouse, costume, sweat à capuche, survêtement,
tablier, pyjama, pull, débardeur, robe), motif (uni, rayures, carreaux, pois), bas (jean, pantalon, jogging, short, jupe),
chaussures, détails (cravate, badge, stéthoscope, stylos, montre, logo, lunettes de vue, moustache, barbe).
Ombrage façon dessin animé du côté opposé à la lumière de la scène ; mouvement secondaire du pompon et du nœud.
Vue de dos pour les plans « par-dessus l'épaule ».

dessiner(img, perso, pose) dessine un personnage dans l'image (RGB uint8) selon une « pose » (dict de paramètres).
Les clés de pose ajoutées (costume, lumiere, reflets, rides…) sont facultatives : sans elles, le dessin d'origine est inchangé."""
import math
import numpy as np, cv2

import garde_robe as GR

TRAIT = (26, 22, 30)
BLANC = (252, 252, 250)
PEAU_OMBRE = (196, 200, 226)                                               # teinte de l'ombre sur le blanc (froide, comme en animation)
AA = cv2.LINE_AA

# ------------------------------------------------------------------ distribution
PERSOS = {
    "bonnet":    dict(nom="Jojo", accessoire="bonnet", couleur=(240, 120, 40), cheveux=("meches", (110, 72, 40)), nez="rond"),    # bonnet orange à pompon
    "casquette": dict(nom="Kévin", accessoire="casquette", couleur=(50, 110, 220), cheveux=("nuque", (60, 44, 32)), nez="pointu"), # casquette bleue à l'envers
    "noeud":     dict(nom="Lila", accessoire="noeud", couleur=(240, 90, 150), cheveux=("carre", (120, 70, 45)), nez="petit", cils=True),  # nœud rose
    "lunettes":  dict(nom="Dédé", accessoire="lunettes", couleur=(30, 30, 30), cheveux=("couronne", (150, 150, 155)), nez="rond", moustache=True),
    "meche":     dict(nom="Momo", accessoire="meche", couleur=(30, 30, 30), cheveux=None, nez="petit"),        # mèche rebelle
}
ROLES = {"presentateur": "bonnet", "invite": "casquette", "envoyee": "noeud"}       # rôle du sketch -> personnage

# tenue habituelle de chacun (quand l'épisode n'en impose pas d'autre)
COSTUMES_DEFAUT = {
    "bonnet":    dict(haut="tshirt", c_haut=(120, 150, 110), motif="uni", bas="jean", c_bas=(70, 100, 150), chaussures="baskets", c_chaussures=(240, 240, 236), details=("logo",)),
    "casquette": dict(haut="capuche", c_haut=(60, 70, 110), motif="uni", bas="jogging", c_bas=(80, 84, 92), chaussures="baskets", c_chaussures=(230, 60, 60), details=()),
    "noeud":     dict(haut="pull", c_haut=(250, 196, 210), motif="uni", bas="jupe", c_bas=(70, 70, 110), chaussures="ballerines", c_chaussures=(200, 60, 100), details=()),
    "lunettes":  dict(haut="chemise", c_haut=(230, 220, 190), motif="carreaux", c_motif=(190, 120, 90), bas="pantalon", c_bas=(120, 100, 80), chaussures="ville", c_chaussures=(80, 50, 30), details=()),
    "meche":     dict(haut="tshirt", c_haut=(250, 210, 80), motif="rayures", c_motif=(240, 150, 40), bas="short", c_bas=(80, 120, 160), chaussures="baskets", c_chaussures=(250, 250, 250), details=()),
}

HAUTS = ("tshirt", "chemise", "blouse", "costume", "capuche", "survetement", "tablier", "pyjama", "pull", "debardeur", "robe", "polo", "gilet",
         "col_roule", "doudoune", "blouson", "redingote", "uniforme", "tunique", "hawai")
MOTIFS = ("uni", "rayures", "carreaux", "pois") + GR.MOTIFS
BAS = ("jean", "pantalon", "jogging", "short", "jupe")
CHAUSSURES = ("baskets", "ville", "ballerines", "bottes", "chaussons")
DETAILS = ("cravate", "noeud_pap", "badge", "stethoscope", "stylos", "montre", "logo", "lunettes_vue", "moustache", "barbe", "collier", "echarpe",
           "ceinture", "boucles_oreilles", "taches_rousseur", "bracelet", "sac_bandouliere", "casque_audio", "bretelles", "rouge_levres") + GR.BARBES
CHAPEAUX = GR.CHAPEAUX                                                     # couvre-chef de l'épisode (costume["chapeau"], couleur c_chapeau)
COIFFURES = ("carre", "long", "queue", "chignon", "boucles", "court", "meches", "nuque", "couronne", "aucune") + GR.COIFFURES   # coiffure de l'épisode (costume["cheveux"])
CHEVEUX_ARRIERE = ("carre", "long", "queue", "chignon", "boucles") + GR.ARRIERE

def pose_neutre():
    return dict(x=540, y=1500, s=1.0, sq=0.0, tilt=0.0, regard=(0.0, 0.0), yeux="ouverts", paupiere=0.0, sourcils="neutre",
                bouche=0.0, forme="neutre", bras_g=(-18, 8), bras_d=(18, -8), effets=(), rougeur=0.0, tremble=0.0, t=0.0,
                main_g=None, main_d=None, face=0.0)

# ------------------------------------------------------------------ géométrie
def _pt(x, y): return (int(round(x * 4)), int(round(y * 4)))           # coordonnées sous-pixel (shift=2)

def _ellipse(img, c, ax, ang, couleur, ep=-1):
    cv2.ellipse(img, _pt(*c), _pt(max(1, ax[0]), max(1, ax[1])), ang, 0, 360, couleur, ep if ep < 0 else max(1, int(ep)), AA, 2)

def _arc(img, c, ax, ang, a0, a1, couleur, ep):
    cv2.ellipse(img, _pt(*c), _pt(max(1, ax[0]), max(1, ax[1])), ang, a0, a1, couleur, max(1, int(ep)), AA, 2)

def _ligne(img, a, b, couleur, ep):
    cv2.line(img, _pt(*a), _pt(*b), couleur, max(1, int(ep)), AA, 2)
    r = ep / 2
    if r >= 2: _ellipse(img, a, (r, r), 0, couleur); _ellipse(img, b, (r, r), 0, couleur)

def _poly(img, pts, couleur, ferme=True, ep=-1):
    p = np.array([[x * 4, y * 4] for x, y in pts], np.int32).reshape(-1, 1, 2)
    if ep < 0: cv2.fillPoly(img, [p], couleur, AA, 2)
    else: cv2.polylines(img, [p], ferme, couleur, max(1, int(ep)), AA, 2)

def _rot(px, py, cx, cy, a):
    c, s = math.cos(a), math.sin(a); dx, dy = px - cx, py - cy
    return cx + dx * c - dy * s, cy + dx * s + dy * c

def _bras(epaule, angles, L, s):
    """Bras en deux segments : angles (épaule, coude) en degrés, 0 = vers le bas, positif = vers l'extérieur droit."""
    a1, a2 = math.radians(angles[0]), math.radians(angles[0] + angles[1])
    coude = (epaule[0] + math.sin(a1) * L * s, epaule[1] + math.cos(a1) * L * s)
    main = (coude[0] + math.sin(a2) * L * 0.9 * s, coude[1] + math.cos(a2) * L * 0.9 * s)
    return coude, main

def ik(epaule, cible, L, s, coude_bas=True):
    """Angles (épaule, coude) pour que la main atteigne `cible` (bras trop court : il se tend vers elle). Inverse de _bras."""
    l1, l2 = L * s, L * 0.9 * s
    dx, dy = cible[0] - epaule[0], cible[1] - epaule[1]; d = max(1e-3, math.hypot(dx, dy)); d_ = min(d, (l1 + l2) * 0.999)
    theta = math.atan2(dx, dy)                                              # 0 = vers le bas, positif = vers la droite
    alpha = math.acos(max(-1.0, min(1.0, (l1 * l1 + d_ * d_ - l2 * l2) / (2 * l1 * d_))))
    a1 = theta + (alpha if (dx < 0) == coude_bas else -alpha)               # coude vers le bas / l'extérieur
    coude = (epaule[0] + math.sin(a1) * l1, epaule[1] + math.cos(a1) * l1)
    tx, ty = epaule[0] + dx / d * d_, epaule[1] + dy / d * d_
    a2 = math.atan2(tx - coude[0], ty - coude[1])
    return math.degrees(a1), math.degrees(a2 - a1)

def _fonce(c, k=0.78): return tuple(int(v * k) for v in c)
def _clair(c, k=0.35): return tuple(int(v + (255 - v) * k) for v in c)

def _roi(img, cx, cy, ax, ay, marge=4):
    """Zone de l'image autour d'une forme : (x0, y0, x1, y1) bornée à l'image, ou None si hors champ."""
    x0, y0 = int(max(0, cx - ax - marge)), int(max(0, cy - ay - marge))
    x1, y1 = int(min(img.shape[1], cx + ax + marge + 1)), int(min(img.shape[0], cy + ay + marge + 1))
    return (x0, y0, x1, y1) if x1 > x0 + 1 and y1 > y0 + 1 else None

def _masque_ellipse(roi, c, ax, ang):
    x0, y0, x1, y1 = roi; m = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.ellipse(m, _pt(c[0] - x0, c[1] - y0), _pt(max(1, ax[0]), max(1, ax[1])), ang, 0, 360, 255, -1, AA, 2)
    return m

def _masque_poly(roi, pts, k=1.0, dx=0.0, dy=0.0):
    """Masque d'un polygone (buste adulte), agrandi de k autour de son centre et décalé de (dx, dy)."""
    x0, y0, x1, y1 = roi; m = np.zeros((y1 - y0, x1 - x0), np.uint8); a = np.array(pts, np.float32); c = a.mean(0)
    a = (a - c) * k + c + (dx - x0, dy - y0); cv2.fillPoly(m, [np.round(a * 4).astype(np.int32)], 255, AA, 2)
    return m

def _ombre(img, c, ax, ang, cote, force, teinte=PEAU_OMBRE, pts=None):
    """Ombre en croissant (dessin animé) : la partie de la forme qui n'est pas tournée vers la lumière (`cote` = côté d'où vient
    la lumière : -1 gauche, 1 droite). Multiplie les couleurs déjà peintes (costume, motif) : l'ombre suit tout ce qui est dessiné dessous."""
    if force <= 0: return
    roi = _roi(img, c[0], c[1], max(ax) * 1.1, max(ax) * 1.1)
    if roi is None: return
    if pts is not None: m1, m2 = _masque_poly(roi, pts, 0.99), _masque_poly(roi, pts, 1.03, cote * ax[0] * 0.32, -ax[1] * 0.16)
    else:
        m1 = _masque_ellipse(roi, c, (ax[0] - 1, ax[1] - 1), ang)
        m2 = _masque_ellipse(roi, (c[0] + cote * ax[0] * 0.32, c[1] - ax[1] * 0.16), (ax[0] * 1.02, ax[1] * 1.04), ang)
    m = (m1 > 128) & (m2 < 128)                                            # croissant net (aplat d'ombre façon cel-shading)
    if not m.any(): return
    x0, y0, x1, y1 = roi; z = img[y0:y1, x0:x1]
    k = (256 * (1 - force + force * np.array(teinte, np.float32) / 255)).astype(np.uint16)
    z[m] = ((z[m].astype(np.uint16) * k) >> 8).astype(np.uint8)

def _motif(img, c, ax, motif, couleur, s, haut=None, pts=None):
    """Motif du vêtement (rayures, carreaux, pois) peint à l'intérieur de l'ellipse du corps (au-dessous de `haut` seulement si donné)."""
    if motif not in MOTIFS or motif == "uni": return
    roi = _roi(img, c[0], c[1], ax[0] * 1.1, ax[1])
    if roi is None: return
    x0, y0, x1, y1 = roi; m = _masque_ellipse(roi, c, (ax[0] - 2, ax[1] - 2), 0) if pts is None else _masque_poly(roi, pts, 0.98)
    if haut is not None: m[:max(0, int(haut - y0))] = 0
    if motif in GR.MOTIFS: GR.motif(img, c, ax, motif, couleur, s, (x0, y0, m)); return
    z = img[y0:y1, x0:x1].copy(); pas = max(6, int(26 * s))
    if motif == "rayures":
        for y in range(0, y1 - y0, pas): cv2.line(z, (0, y), (x1 - x0, y), couleur, max(2, int(9 * s)), AA)
    elif motif == "carreaux":
        for y in range(0, y1 - y0, pas): cv2.line(z, (0, y), (x1 - x0, y), couleur, max(2, int(6 * s)), AA)
        for x in range(int((c[0] - x0) % pas), x1 - x0, pas): cv2.line(z, (x, 0), (x, y1 - y0), couleur, max(2, int(6 * s)), AA)
    else:
        for j, y in enumerate(range(pas // 2, y1 - y0, pas)):
            for x in range(pas // 2 + (pas // 2 if j % 2 else 0), x1 - x0, pas): cv2.circle(z, (x, y), max(2, int(5 * s)), couleur, -1, AA)
    a = (m.astype(np.float32) / 255)[..., None]
    img[y0:y1, x0:x1] = (img[y0:y1, x0:x1] * (1 - a) + z * a).astype(np.uint8)

# ------------------------------------------------------------------ mains
FORMES_MAIN = ("ouverte", "poing", "index", "pouce", "paume")

def _main(img, m, direction, forme, r, couleur, gonfle=0.0):
    """Main au bout du bras : `direction` = angle de l'avant-bras (radians, sens du bras), `gonfle` = épaisseur du contour.
    Appelée deux fois : en noir un peu plus grosse (contour), puis en couleur."""
    dx, dy = math.sin(direction), math.cos(direction)
    R_ = r + gonfle
    if forme == "index":                                                   # doigt pointé dans le prolongement du bras
        _ellipse(img, m, (R_ * 0.92, R_ * 0.92), 0, couleur)
        bout = (m[0] + dx * r * 2.0, m[1] + dy * r * 2.0); _ligne(img, m, bout, couleur, r * 0.72 + 2 * gonfle)
    elif forme == "pouce":                                                 # poing, pouce vers le ciel
        _ellipse(img, m, (R_ * 0.9, R_ * 0.9), 0, couleur)
        _ligne(img, (m[0], m[1] - r * 0.3), (m[0], m[1] - r * 1.65), couleur, r * 0.7 + 2 * gonfle)
    elif forme == "paume":                                                 # main ouverte face à l'autre (« stop »)
        _ellipse(img, (m[0] + dx * r * 0.3, m[1] + dy * r * 0.3), (R_ * 1.05, R_ * 1.25), math.degrees(-direction), couleur)
        for k in (-1, 0, 1):
            a = direction + k * 0.42; _ligne(img, m, (m[0] + math.sin(a) * r * 1.6, m[1] + math.cos(a) * r * 1.6), couleur, r * 0.55 + 2 * gonfle)
    elif forme == "poing":
        _ellipse(img, m, (R_ * 0.92, R_ * 0.92), 0, couleur)
    else:                                                                  # main ouverte détendue : la paume et le pouce
        _ellipse(img, m, (R_, R_), 0, couleur)
        a = direction + 1.3; _ellipse(img, (m[0] + math.sin(a) * r * 0.85, m[1] + math.cos(a) * r * 0.85), (R_ * 0.42, R_ * 0.42), 0, couleur)

def _jointures(img, m, forme, r, s):
    if forme in ("poing", "pouce"):
        for k in (-1, 1): _arc(img, (m[0] + k * r * 0.35, m[1] + r * 0.05), (r * 0.32, r * 0.25), 0, 200, 340, TRAIT, 3 * s)

# ------------------------------------------------------------------ dessin
ASSIS_BAISSE = 50                                                          # adulte assis : le buste descend de 95 × échelle
ADULTE_TETE = 0.9                                                          # version adulte : grosse tête ronde posée sur le col

def buste(x, cy, w, h):
    """Buste ADULTE (style « toons ») : vêtement aux épaules carrées arrondies, flancs presque droits, bas un peu évasé."""
    haut, bas = cy - h / 2, cy + h / 2; d = []
    for a in np.linspace(math.pi / 2, math.pi, 7):                         # épaule gauche : du col au bras
        d.append((x - 0.5 * w + math.cos(a) * 0.48 * w, haut + 0.3 * w - math.sin(a) * 0.3 * w))
    d += [(x - 0.97 * w, cy), (x - 1.03 * w, bas - 0.05 * h), (x - 0.96 * w, bas)]
    g = [(2 * x - px, py) for px, py in reversed(d)]
    return [(x - 0.3 * w, haut)] + d + g + [(x + 0.3 * w, haut)]

def squelette(p):
    """Proportions du personnage : marionnette d'origine (grosse tête, petit corps) ou version ADULTE (p["adulte"]) du même modèle :
    même tête ronde, même buste en œuf, mêmes bras et jambes en tubes, mais un corps plus grand, des jambes et des bras longs, un cou."""
    A = bool(p.get("adulte")); s = p["s"]; sq = p["sq"]; sx, sy = 1 - 0.55 * sq, 1 + sq
    x_pieds = p["x"]; hanche = float(p.get("hanche", 0.0))                # poids du corps : le bassin glisse sur la jambe d'appui
    x = p["x"] + hanche * 9 * s + (math.sin(p["t"] * 61) * 9 * p["tremble"] if p.get("tremble") else 0); pieds = p["y"]
    epaules = float(p.get("epaules", 0.0)); penche = float(p.get("penche", 0.0))
    if A:
        corps_h = 150 * s * sy * 1.6; corps_w = 92 * s * sx * 1.12; cy_corps = pieds - 235 * s * sy - corps_h * 0.35 + (ASSIS_BAISSE * s if p.get("assis") else 0)
        Rt = 150 * s * ADULTE_TETE; cou = 0.86
    else:
        corps_h = 150 * s * sy; corps_w = 92 * s * sx; cy_corps = pieds - 38 * s - corps_h / 2; Rt = 150 * s; cou = 0.78
    tete = (x + math.sin(math.radians(p["tilt"])) * 30 * s + penche * 16 * s, cy_corps - corps_h / 2 - Rt * cou * sy + epaules * 12 * s)
    rx, ry = Rt * (1 + 0.25 * sq) * (1 - 0.1 * sq), Rt * (1 - 0.18 * sq)
    h_ep = 0.34 if A else 0.22
    k_ep = (corps_w * 0.97 + 10 * s) if A else corps_w * 0.82             # adulte : les bras tombent le long du buste, sous l'épaule
    ep_g = (x - k_ep + penche * 8 * s, cy_corps - corps_h * h_ep - epaules * 22 * s); ep_d = (x + k_ep + penche * 8 * s, cy_corps - corps_h * h_ep - epaules * 22 * s)
    L = 92 if A else 64
    bras = [(e, *_bras(e, (a[0], a[1]), L, s)) for e, a in ((ep_g, p["bras_g"]), (ep_d, p["bras_d"]))]
    return dict(A=A, s=s, sx=sx, sy=sy, x=x, x_pieds=x_pieds, hanche=hanche, pieds=pieds, corps_h=corps_h, corps_w=corps_w, cy_corps=cy_corps, R=Rt, tete=tete, rx=rx, ry=ry,
                bras=bras, st=s * (ADULTE_TETE if A else 1.0), membre=(40 if A else 34) * s, r_m=(22 if A else 22) * s, epaules=epaules, penche=penche)

def dessiner(img, perso, p):
    """Dessine le personnage `perso` (clé de PERSOS ou dict) dans `img` selon la pose `p`. Renvoie la position de la tête."""
    P = PERSOS[perso] if isinstance(perso, str) else perso
    C = p.get("costume")                                                   # tenue de l'épisode (None : bonhomme blanc d'origine)
    if C and C.get("cheveux") in COIFFURES:                                # coiffure et couleur de cheveux de l'épisode
        c_ch = tuple(C.get("c_cheveux") or (P.get("cheveux") or ("", (95, 65, 40)))[1])
        P = dict(P, cheveux=None if C["cheveux"] == "aucune" else (C["cheveux"], c_ch))
    elif C and C.get("c_cheveux") and P.get("cheveux"): P = dict(P, cheveux=(P["cheveux"][0], tuple(C["c_cheveux"])))
    lum = p.get("lumiere", 0); f_omb = p.get("ombre", 0.0) if lum else 0.0
    K = squelette(p); A = K["A"]                                           # proportions : marionnette d'origine ou version adulte
    s, sx, sy, x, pieds = K["s"], K["sx"], K["sy"], K["x"], K["pieds"]; y = pieds
    corps_h, corps_w, cy_corps, tete, rx, ry = K["corps_h"], K["corps_w"], K["cy_corps"], K["tete"], K["rx"], K["ry"]
    epaules, penche = K["epaules"], K["penche"]; st = K["st"]; mb = K["membre"]
    ep = 8 * s                                                             # épaisseur du trait
    chair = tuple(p.get("peau") or BLANC)                                  # blanc (nos bonshommes) ou couleur de peau
    dos = bool(p.get("dos"))

    # ombre au sol (portée du côté opposé à la lumière)
    _ellipse(img, (x - lum * 22 * s, pieds + 4 * s), (120 * s * sx + abs(lum) * 18 * s, 16 * s), 0, tuple(int(c * 0.80) for c in _fond(img, x, pieds + 4 * s)))
    # capuche (derrière la tête) et cheveux longs (derrière la tête)
    if C and C.get("haut") == "capuche" and not dos:
        hc = (x, cy_corps - corps_h * 0.42); _ellipse(img, hc, (corps_w * 1.05 + ep, corps_h * 0.32 + ep), 0, TRAIT); _ellipse(img, hc, (corps_w * 1.05, corps_h * 0.32), 0, _fonce(C["c_haut"], 0.85))
    if P.get("cheveux") and P["cheveux"][0] in CHEVEUX_ARRIERE and p.get("coiffure", True):
        _cheveux_arriere(img, tete, rx, ry, st, p, P)
    # jambes (pantalon ou jambes nues) et chaussures
    bas = (C or {}).get("bas"); c_bas = (C or {}).get("c_bas", BLANC)
    pied = float(p.get("pied", 0.0))                                       # le pied droit tape (impatience) : 0 → 1
    baton = A and C and (bas == "jupe" or C.get("haut") in ("robe", "tunique"))           # adulte en robe ou jupe : jambes en simples traits
    assis = bool(p.get("assis")) and A; sens_a = 1 if float(p.get("tq", 0.0)) >= 0 else -1
    if assis:                                                              # chaise dessinée avec le personnage (elle est toujours au bon endroit)
        y_s = cy_corps + corps_h * 0.5 + 18 * s; c_ch = tuple(p.get("c_chaise") or (60, 100, 150))
        dossier = [(x - 124 * s, y_s - 290 * s), (x + 124 * s, y_s - 290 * s), (x + 116 * s, y_s), (x - 116 * s, y_s)]   # dossier derrière le buste (vu de face)
        _poly(img, dossier, c_ch); _poly(img, dossier, TRAIT, True, 4 * s)
        _ligne(img, (x - 108 * s, y_s - 245 * s), (x + 108 * s, y_s - 245 * s), _fonce(c_ch, 0.8), 5 * s)
        _poly(img, [(x - 95 * s, y_s), (x + 95 * s, y_s), (x + 95 * s, y_s + 22 * s), (x - 95 * s, y_s + 22 * s)], c_ch); _poly(img, [(x - 95 * s, y_s), (x + 95 * s, y_s), (x + 95 * s, y_s + 22 * s), (x - 95 * s, y_s + 22 * s)], TRAIT, True, 4 * s)
        for xx in (x - 85 * s, x + 75 * s): _ligne(img, (xx, y_s + 22 * s), (xx, pieds), TRAIT, 12 * s); _ligne(img, (xx, y_s + 22 * s), (xx, pieds), _fonce(c_ch, 0.85), 6 * s)
    marche = p.get("marche"); hanche = K["hanche"]; xp = K["x_pieds"]
    for k_j, dx in enumerate((-40, 40) if A else (-34, 34)):
        a = (x + dx * s * sx, cy_corps + corps_h * 0.35); b = (xp + dx * (1.0 if A else 1.25) * s * sx, pieds - (pied * 22 * s if dx > 0 else 0))
        genou = None
        if assis:                                                          # assis, vu de face comme le buste : la cuisse avance vers nous
            genou = (x + dx * 1.15 * s, cy_corps + corps_h * 0.5 + 40 * s); a = genou; b = (genou[0] + dx * 0.1 * s, pieds)   # tibia vertical
        elif marche is not None:                                           # marche : les jambes alternent, le pied se lève
            ph_ = marche + (math.pi if k_j else 0.0)
            b = (b[0] + math.sin(ph_) * 24 * s, b[1] - max(0.0, math.cos(ph_)) * 18 * s)
            genou = ((a[0] + b[0]) / 2 + math.sin(ph_) * 10 * s, (a[1] + b[1]) / 2 - max(0.0, math.cos(ph_)) * 8 * s)
        elif A and abs(hanche) > 0.15 and (dx > 0) == (hanche < 0):        # jambe libre : genou légèrement plié
            genou = ((a[0] + b[0]) / 2 + (1 if dx > 0 else -1) * 7 * s * abs(hanche), (a[1] + b[1]) / 2)
        seg = [(a, genou), (genou, b)] if genou else [(a, b)]
        if baton:
            for u_, v_ in seg: _ligne(img, u_, v_, TRAIT, 7 * s)
            _chaussure(img, (b[0] + dx * 0.2 * s, b[1] - 5 * s), s * 0.75, dx, C); continue
        for u_, v_ in seg: _ligne(img, u_, v_, TRAIT, mb)
        for u_, v_ in seg: _ligne(img, u_, v_, chair, mb - 2 * ep)
        if bas in ("jean", "pantalon", "jogging"):
            for u_, v_ in seg[:-1] + [(seg[-1][0], (b[0], b[1] - 8 * s))]: _ligne(img, u_, v_, c_bas, mb - 2 * ep)
            if A and p.get("reflets") and not genou: GR.finitions_jambe(img, a, (b[0], b[1] - 8 * s), mb - 2 * ep, s, bas, c_bas, 1 if dx > 0 else -1)
            if bas == "jogging": _ligne(img, (a[0] + dx / 34 * 9 * s, a[1]), (b[0] + dx / 34 * 9 * s, b[1] - 12 * s), (245, 245, 245), 4 * s)
            if bas == "jean": _ligne(img, (b[0] - 11 * s, b[1] - 16 * s), (b[0] + 11 * s, b[1] - 16 * s), _clair(c_bas, 0.3), 4 * s)
        elif bas == "short":
            v0 = genou or b; mi = (a[0] + (v0[0] - a[0]) * (0.8 if genou else 0.45), a[1] + (v0[1] - a[1]) * (0.8 if genou else 0.45)); _ligne(img, a, mi, c_bas, mb - 2 * ep + 4 * s)
        _chaussure(img, (b[0] + dx * 0.25 * s, b[1] - 6 * s), s, dx, C)
        if A and p.get("reflets"): GR.lacets(img, (b[0] + dx * 0.25 * s, b[1] - 6 * s), s, C)
    # jupe ou robe : trapèze sous le corps
    if C and (bas == "jupe" or C.get("haut") == "robe"):
        col = C["c_haut"] if C.get("haut") == "robe" else c_bas; y0j = cy_corps + corps_h * 0.18; y1j = cy_corps + corps_h * (0.62 if not A else 0.92)
        ev = 1.18 if not A else 1.35
        pts = [(x - corps_w * 0.85, y0j), (x + corps_w * 0.85, y0j), (x + corps_w * ev, y1j), (x - corps_w * ev, y1j)]
        _poly(img, pts, col); _poly(img, pts, TRAIT, True, ep * 0.8)
        for k in (-1, 0, 1): _ligne(img, (x + k * corps_w * 0.35, y0j + 10 * s), (x + k * corps_w * 0.5, y1j - 6 * s), _fonce(col, 0.82), 3 * s)   # plis
    # bras (épaules)
    bras = K["bras"]
    pts_b = buste(x + penche * 6 * s, cy_corps, corps_w, corps_h) if A else None    # adulte : buste aux épaules carrées
    haut = (C or {}).get("haut")
    manche = None                                                          # manches de la couleur du haut
    if C and haut not in ("debardeur", "tablier", "robe", "tunique"):
        manche = (C.get("c_manche") or (C.get("c_haut", BLANC) if haut != "blouse" else (246, 248, 252)), "courtes" if haut in ("tshirt", "polo") else "longues")
    if C and haut == "tablier": manche = (C.get("c_manche") or (235, 235, 230), "courtes")
    bras = K["bras"]
    if A:                                                                  # adulte : le haut du bras sort de dessous l'épaule (derrière le buste)
        for e_, c_, m_ in bras: _ligne(img, e_, c_, TRAIT, mb + 2 * ep)
        for e_, c_, m_ in bras: _ligne(img, e_, c_, manche[0] if manche else chair, mb)
    # contour d'abord (tout en noir, un peu plus gros), puis remplissage : le contour des formes se fond
    if A: _poly(img, pts_b, TRAIT, True, 2 * ep)
    else: _ellipse(img, (x, cy_corps), (corps_w + ep, corps_h / 2 + ep), 0, TRAIT)
    if not A: _ellipse(img, tete, (rx + ep, ry + ep), p["tilt"], TRAIT)
    haut = (C or {}).get("haut"); c_haut = (C or {}).get("c_haut", BLANC)
    if haut == "blouse": c_haut = (246, 248, 252)
    if A: _poly(img, pts_b, c_haut if C else BLANC)
    else: _ellipse(img, (x, cy_corps), (corps_w, corps_h / 2), 0, c_haut if C else BLANC)
    if C and not dos and haut not in ("blouse",):                            # plis du vêtement, du côté de l'ombre
        sg_p = -lum if lum else 1
        for k in range(2): _arc(img, (x + sg_p * corps_w * 0.55, cy_corps + (k - 0.3) * 26 * s), (16 * s, 8 * s), 0, 200 if sg_p > 0 else 20, 300 if sg_p > 0 else 120, _fonce(c_haut, 0.72), 3 * s)
    if C:
        _motif(img, (x, cy_corps), (corps_w, corps_h / 2), C.get("motif"), C.get("c_motif") or _fonce(c_haut, 0.8), s, pts=pts_b)
        _vetement(img, x, cy_corps, corps_w, corps_h, tete if not A else (tete[0], cy_corps - corps_h * 0.47 - ry * 0.94), ry, s, ep, C, dos)
        if A and not dos and p.get("reflets"): GR.finitions_buste(img, pts_b, x + penche * 6 * s, cy_corps, corps_w, corps_h, s, C)
        if not dos: _sacs(img, x, cy_corps, corps_w, corps_h, s, C)
    _ombre(img, (x, cy_corps), (corps_w, corps_h / 2), 0, lum, f_omb, pts=pts_b)
    if assis:                                                              # assis de face : siège, cuisses qui avancent, genoux
        y_b = cy_corps + corps_h * 0.5; y_s = y_b + 18 * s; c_ch = tuple(p.get("c_chaise") or (60, 100, 150))
        siege = [(x - 118 * s, y_s - 10 * s), (x + 118 * s, y_s - 10 * s), (x + 112 * s, y_s + 20 * s), (x - 112 * s, y_s + 20 * s)]
        _poly(img, siege, c_ch); _poly(img, siege, TRAIT, True, 4 * s)                    # bord du siège (dépasse de chaque côté)
        c_g = c_bas if bas in ("jean", "pantalon", "jogging", "short") else (C or {}).get("c_haut", BLANC) if (C or {}).get("haut") == "robe" or bas == "jupe" else chair
        for dx in (-46, 46):                                               # cuisse vue de face : courte (elle vient vers nous), plus large que le tibia
            gx = x + dx * s; cuisse = [(gx - 44 * s, y_b - 14 * s), (gx + 44 * s, y_b - 14 * s), (gx + 40 * s, y_b + 40 * s), (gx - 40 * s, y_b + 40 * s)]
            _poly(img, cuisse, c_g); _poly(img, cuisse, TRAIT, True, ep)
            _ellipse(img, (gx, y_b + 40 * s), (40 * s + ep, 17 * s + ep), 0, TRAIT); _ellipse(img, (gx, y_b + 40 * s), (40 * s, 17 * s), 0, c_g)   # genou
            _arc(img, (gx, y_b + 38 * s), (18 * s, 8 * s), 0, 200, 340, _fonce(c_g, 0.72), 3 * s)
        _ligne(img, (x, y_b - 10 * s), (x, y_b + 34 * s), _fonce(c_g, 0.6), 4 * s)                # entre les deux cuisses
    if A: _ellipse(img, tete, (rx + ep, ry + ep), p["tilt"], TRAIT)                 # adulte : la tête posée sur le col, avec son contour
    _ellipse(img, tete, (rx, ry), p["tilt"], chair)
    _ombre(img, tete, (rx, ry), p["tilt"], lum, f_omb * 0.8)
    for cle, teinte in (("rougeur", (235, 70, 60)), ("paleur", (150, 190, 235))):     # colère : rouge par le haut ; peur : bleu-vert pâle
        if p.get(cle, 0) > 0:
            roi = _roi(img, tete[0], tete[1], rx, ry)
            if roi is None: continue
            x0, y0, x1, y1 = roi; m = _masque_ellipse(roi, tete, (rx - ep / 2, ry - ep / 2), p["tilt"]).astype(np.float32) / 255
            yy = np.arange(y0, y1, dtype=np.float32)[:, None]
            g = np.clip((tete[1] - ry + 2 * ry * min(1, p[cle]) - yy) / (ry * 0.9), 0, 1)        # dégradé : depuis le haut
            a = (m * 0.6 * g)[..., None]; z = img[y0:y1, x0:x1].astype(np.float32)
            img[y0:y1, x0:x1] = (z * (1 - a) + np.array(teinte, np.float32) * a).astype(np.uint8)
    # bras (devant le corps, avec leur propre contour) ; manches de la couleur du haut
    formes = (p.get("main_forme_g") or "ouverte", p.get("main_forme_d") or "ouverte") if p.get("mains") else (None, None)
    r_m = K["r_m"]
    for (e_, c_, m_), fm in zip(bras, formes):
        e2 = (e_[0] + (x - e_[0]) * 0.25, e_[1] + 6 * s)
        if not A: _ligne(img, e2, c_, TRAIT, mb + 2 * ep)
        _ligne(img, c_, m_, TRAIT, mb + 2 * ep)
        if fm: _main(img, m_, math.atan2(m_[0] - c_[0], m_[1] - c_[1]), fm, r_m, TRAIT, ep)
        else: _ellipse(img, m_, (r_m + ep, r_m + ep), 0, TRAIT)
    for (e_, c_, m_), fm in zip(bras, formes):
        e2 = (e_[0] + (x - e_[0]) * 0.25, e_[1] + 6 * s)
        if A: e2 = (e_[0] + (c_[0] - e_[0]) * 0.6, e_[1] + (c_[1] - e_[1]) * 0.6)   # adulte : le haut du bras est déjà peint (on raccorde au coude)
        _ligne(img, e2, c_, chair, mb); _ligne(img, c_, m_, chair, mb)
        if manche:
            _ligne(img, e2, c_, manche[0], mb)
            if manche[1] == "longues":
                poignet = (c_[0] + (m_[0] - c_[0]) * 0.72, c_[1] + (m_[1] - c_[1]) * 0.72)
                _ligne(img, c_, poignet, manche[0], mb); _ligne(img, poignet, poignet, _fonce(manche[0], 0.7), mb + 2 * s)
                if p.get("reflets"):                                           # pli au creux du coude
                    dx_, dy_ = poignet[0] - e2[0], poignet[1] - e2[1]; n_ = math.hypot(dx_, dy_) or 1
                    _ligne(img, (c_[0] - dy_ / n_ * 9 * s, c_[1] + dx_ / n_ * 9 * s), (c_[0] + dy_ / n_ * 2 * s, c_[1] - dx_ / n_ * 2 * s), _fonce(manche[0], 0.68), 3 * s)
                if haut == "survetement": _ligne(img, e2, poignet, (250, 250, 250), 5 * s)
        if fm: _main(img, m_, math.atan2(m_[0] - c_[0], m_[1] - c_[1]), fm, r_m, chair); _jointures(img, m_, fm, r_m, s)
        else: _ellipse(img, m_, (r_m, r_m), 0, chair)
    if C and "bracelet" in C.get("details", ()):
        e_, c_, m_ = bras[1]; w_ = (c_[0] + (m_[0] - c_[0]) * 0.66, c_[1] + (m_[1] - c_[1]) * 0.66); _ellipse(img, w_, (15 * s, 7 * s), 0, (240, 200, 80))
    if C and "montre" in C.get("details", ()):
        e_, c_, m_ = bras[0]; w_ = (c_[0] + (m_[0] - c_[0]) * 0.62, c_[1] + (m_[1] - c_[1]) * 0.62)
        _ellipse(img, w_, (12 * s, 12 * s), 0, TRAIT); _ellipse(img, w_, (8 * s, 8 * s), 0, (240, 230, 200))
    # visage (ou nuque, de dos)
    tq = float(np.clip(p.get("tq", 0.0), -1, 1))                           # trois-quarts : le visage se tourne vers celui à qui on parle
    tete_f = (tete[0] + tq * rx * 0.17, tete[1])
    if not dos: _visage(img, tete_f, rx, ry, st, p, P)
    if P.get("cheveux") and p.get("coiffure", True): _cheveux_avant(img, tete, rx, ry, st, p, P, dos)
    if P.get("accessoire"): _accessoire(img, tete, rx, ry, st, p, P)
    if C and not dos: _details_tete(img, tete_f, rx, ry, st, p, C)
    if C and C.get("chapeau") in CHAPEAUX: GR.chapeau(img, tete, rx, ry, st, p, C["chapeau"], tuple(C.get("c_chapeau") or (60, 60, 70)))
    _effets(img, tete, rx, ry, st, p)
    for nom in ("main_g", "main_d"):                                       # objet tenu en main (calque RGBA)
        if p.get(nom) is not None:
            m_ = bras[0][2] if nom == "main_g" else bras[1][2]; _coller(img, p[nom], m_[0], m_[1])
    return tete, (rx, ry)

def _chaussure(img, c, s, dx, C):
    forme = (C or {}).get("chaussures"); col = (C or {}).get("c_chaussures")
    ax = (26 * s, 14 * s) if forme != "bottes" else (26 * s, 16 * s)
    _ellipse(img, c, (ax[0] + 2 * s, ax[1] + 1 * s), 0, TRAIT)
    if not forme or not col: return
    _ellipse(img, (c[0], c[1] - 1 * s), (ax[0] - 5 * s, ax[1] - 5 * s), 0, col)
    if forme == "baskets":                                                # semelle blanche et virgule de couleur
        _ligne(img, (c[0] - ax[0] * 0.75, c[1] + ax[1] * 0.45), (c[0] + ax[0] * 0.75, c[1] + ax[1] * 0.45), (250, 250, 250), 5 * s)
        _ligne(img, (c[0] - 8 * s, c[1] - 2 * s), (c[0] + 9 * s, c[1] - 5 * s), _fonce(col, 0.6) if sum(col) > 600 else (250, 250, 250), 4 * s)
    elif forme == "bottes":
        _ligne(img, (c[0], c[1] - 10 * s), (c[0], c[1] - 34 * s), TRAIT, 26 * s); _ligne(img, (c[0], c[1] - 10 * s), (c[0], c[1] - 32 * s), col, 18 * s)

def _vetement(img, x, cy, w, h, tete, ry, s, ep, C, dos):
    """Détails du haut : col, boutons, poches, cravate, capuche, fermeture éclair, tablier, badge, stéthoscope…"""
    haut = C.get("haut"); col = C.get("c_haut", BLANC); fonce = _fonce(col, 0.7); det = C.get("details", ())
    cou = tete[1] + ry * 0.94; bas_ = cy + h / 2
    def boutons(x0, n=3, c=None):
        for k in range(n): _ellipse(img, (x0, cou + 30 * s + k * 30 * s), (4.5 * s, 4.5 * s), 0, c or fonce)
    if dos:
        if haut == "capuche": _arc(img, (x, cou + 4 * s), (w * 0.55, 30 * s), 0, 0, 180, fonce, 6 * s)
        return
    if haut in ("chemise", "polo", "pyjama"):
        for sg in (-1, 1): _poly(img, [(x, cou + 14 * s), (x + sg * 34 * s, cou - 6 * s), (x + sg * 30 * s, cou + 22 * s)], _clair(col, 0.25) if haut != "pyjama" else fonce)
        for sg in (-1, 1): _poly(img, [(x, cou + 14 * s), (x + sg * 34 * s, cou - 6 * s), (x + sg * 30 * s, cou + 22 * s)], TRAIT, True, 3 * s)
        boutons(x, 3 if haut != "polo" else 1)
        if haut == "chemise": _poly(img, [(x - w * 0.62, cou + 34 * s), (x - w * 0.3, cou + 34 * s), (x - w * 0.3, cou + 64 * s), (x - w * 0.62, cou + 64 * s)], fonce, True, 3 * s)
    elif haut in ("blouse", "costume", "gilet"):
        inner = (C.get("c_dessous") or ((150, 190, 230) if haut == "blouse" else (248, 248, 248)))
        _poly(img, [(x - 26 * s, cou), (x + 26 * s, cou), (x + 6 * s, bas_ - h * 0.25), (x - 6 * s, bas_ - h * 0.25)], inner)
        for sg in (-1, 1):                                                  # revers de la veste
            _poly(img, [(x + sg * 26 * s, cou - 4 * s), (x + sg * 6 * s, bas_ - h * 0.25), (x + sg * 40 * s, cou + 40 * s)], _fonce(col, 0.88))
            _ligne(img, (x + sg * 26 * s, cou - 4 * s), (x + sg * 6 * s, bas_ - h * 0.25), TRAIT, 3.5 * s)
        if haut == "blouse":                                               # poches et stylos
            for sg in (-1, 1): _poly(img, [(x + sg * w * 0.32, bas_ - h * 0.36), (x + sg * w * 0.72, bas_ - h * 0.36), (x + sg * w * 0.68, bas_ - h * 0.12), (x + sg * w * 0.36, bas_ - h * 0.12)], (200, 205, 215), True, 3 * s)
        if haut == "costume": _ellipse(img, (x + 3 * s, bas_ - h * 0.2), (4.5 * s, 4.5 * s), 0, TRAIT)
    elif haut == "capuche":
        for sg in (-1, 1): _ligne(img, (x + sg * 14 * s, cou + 4 * s), (x + sg * 16 * s, cou + 52 * s), (245, 245, 245), 4 * s)
        _poly(img, [(x - w * 0.5, bas_ - h * 0.36), (x + w * 0.5, bas_ - h * 0.36), (x + w * 0.62, bas_ - h * 0.1), (x - w * 0.62, bas_ - h * 0.1)], fonce, True, 3.5 * s)
    elif haut == "survetement":
        _ligne(img, (x, cou), (x, bas_ - 6 * s), fonce, 4 * s); _ellipse(img, (x, cou + 18 * s), (5 * s, 7 * s), 0, (210, 210, 210))
        for sg in (-1, 1): _ligne(img, (x + sg * w * 0.78, cy - h * 0.25), (x + sg * w * 0.9, cy + h * 0.2), (250, 250, 250), 6 * s)
    elif haut == "tablier":
        ct = C.get("c_tablier") or (250, 250, 245)
        pts = [(x - w * 0.5, cou + 12 * s), (x + w * 0.5, cou + 12 * s), (x + w * 0.62, bas_ - 2 * s), (x - w * 0.62, bas_ - 2 * s)]
        _poly(img, pts, ct); _poly(img, pts, TRAIT, True, 4 * s)
        _poly(img, [(x - w * 0.3, cy + 6 * s), (x + w * 0.3, cy + 6 * s), (x + w * 0.3, cy + 36 * s), (x - w * 0.3, cy + 36 * s)], _fonce(ct, 0.8), True, 3 * s)
    elif haut == "pull":
        _arc(img, (x, cou + 2 * s), (36 * s, 16 * s), 0, 0, 180, fonce, 7 * s)
        y_bc = bas_ - 16 * s; dl = w * math.sqrt(max(0.0, 1 - ((y_bc - cy) / (h / 2)) ** 2)) * 0.9      # bord-côte en bas du pull
        _ligne(img, (x - dl, y_bc), (x + dl, y_bc), fonce, 2.5 * s)
        for xx in np.arange(x - dl * 0.85, x + dl * 0.85, 12 * s): _ligne(img, (xx, y_bc), (xx, y_bc + 9 * s), fonce, 2.5 * s)
    elif haut == "debardeur":
        for sg in (-1, 1): _ligne(img, (x + sg * 30 * s, cou), (x + sg * 44 * s, cou - 18 * s), col, 12 * s)
    elif haut == "tshirt":
        _arc(img, (x, cou + 2 * s), (30 * s, 12 * s), 0, 0, 180, fonce, 4 * s)
    elif haut == "robe":
        _arc(img, (x, cou + 2 * s), (30 * s, 14 * s), 0, 0, 180, fonce, 4 * s)
        _ligne(img, (x - w * 0.82, cy + h * 0.2), (x + w * 0.82, cy + h * 0.2), fonce, 6 * s)
    if "ceinture" in det and haut not in ("robe", "tablier", "blouse"):     # ceinture et boucle
        yb = cy + h * 0.3; dl = w * math.sqrt(max(0.0, 1 - ((yb - cy) / (h / 2)) ** 2))
        _ligne(img, (x - dl * 0.95, yb), (x + dl * 0.95, yb), (70, 45, 30), 11 * s)
        _poly(img, [(x - 11 * s, yb - 9 * s), (x + 11 * s, yb - 9 * s), (x + 11 * s, yb + 9 * s), (x - 11 * s, yb + 9 * s)], (220, 190, 90))
        _poly(img, [(x - 11 * s, yb - 9 * s), (x + 11 * s, yb - 9 * s), (x + 11 * s, yb + 9 * s), (x - 11 * s, yb + 9 * s)], TRAIT, True, 3 * s)
    if "logo" in det and haut in ("tshirt", "capuche", "debardeur", "survetement", "pull"):
        _ellipse(img, (x, cy - 4 * s), (20 * s, 20 * s), 0, _clair(col, 0.55)); _ellipse(img, (x, cy - 4 * s), (11 * s, 11 * s), 0, fonce)
    if "cravate" in det:
        _poly(img, [(x - 9 * s, cou + 4 * s), (x + 9 * s, cou + 4 * s), (x + 5 * s, cou + 16 * s), (x - 5 * s, cou + 16 * s)], C.get("c_cravate") or (200, 40, 60))
        pts = [(x - 6 * s, cou + 16 * s), (x + 6 * s, cou + 16 * s), (x + 13 * s, cou + 78 * s), (x, cou + 92 * s), (x - 13 * s, cou + 78 * s)]
        _poly(img, pts, C.get("c_cravate") or (200, 40, 60)); _poly(img, pts, TRAIT, True, 3 * s)
        for k in range(3): _ligne(img, (x - 8 * s, cou + 36 * s + k * 16 * s), (x + 8 * s, cou + 30 * s + k * 16 * s), _fonce(C.get("c_cravate") or (200, 40, 60), 0.7), 3 * s)
    if "noeud_pap" in det:
        for sg in (-1, 1): _poly(img, [(x, cou + 10 * s), (x + sg * 24 * s, cou - 2 * s), (x + sg * 24 * s, cou + 22 * s)], C.get("c_cravate") or (40, 40, 60))
        _ellipse(img, (x, cou + 10 * s), (6 * s, 6 * s), 0, TRAIT)
    if "echarpe" in det:
        ce = C.get("c_echarpe") or (220, 60, 60)
        _ligne(img, (x - w * 0.62, cou + 6 * s), (x + w * 0.62, cou + 6 * s), ce, 26 * s); _ligne(img, (x + w * 0.3, cou + 10 * s), (x + w * 0.4, cou + 74 * s), ce, 22 * s)
        for k in range(3): _ligne(img, (x + w * 0.4 - 8 * s + k * 8 * s, cou + 80 * s), (x + w * 0.4 - 8 * s + k * 8 * s, cou + 92 * s), ce, 4 * s)
    if "collier" in det:
        _arc(img, (x, cou + 4 * s), (34 * s, 24 * s), 0, 10, 170, (240, 200, 80), 4 * s); _ellipse(img, (x, cou + 28 * s), (6 * s, 6 * s), 0, (240, 200, 80))
    if "badge" in det:                                                     # badge d'entreprise / d'hôpital accroché à la poitrine
        bx, by = x + w * 0.42, cy - h * 0.12
        _poly(img, [(bx - 18 * s, by - 12 * s), (bx + 18 * s, by - 12 * s), (bx + 18 * s, by + 16 * s), (bx - 18 * s, by + 16 * s)], TRAIT)
        _poly(img, [(bx - 15 * s, by - 9 * s), (bx + 15 * s, by - 9 * s), (bx + 15 * s, by + 13 * s), (bx - 15 * s, by + 13 * s)], (250, 250, 250))
        _ellipse(img, (bx - 7 * s, by), (5 * s, 6 * s), 0, (150, 170, 200)); _ligne(img, (bx + 1 * s, by - 2 * s), (bx + 11 * s, by - 2 * s), (150, 150, 160), 2.5 * s)
        _ligne(img, (bx + 1 * s, by + 5 * s), (bx + 9 * s, by + 5 * s), (150, 150, 160), 2.5 * s)
    if "stylos" in det:
        for k, cc in enumerate(((40, 80, 200), (200, 40, 40))): _ligne(img, (x - w * 0.5 + k * 8 * s, cy - h * 0.1), (x - w * 0.5 + k * 8 * s, cy - h * 0.1 - 20 * s), cc, 5 * s)
    if "stethoscope" in det:                                               # tuyau autour du cou, pavillon sur la poitrine
        _arc(img, (x, cou + 6 * s), (40 * s, 34 * s), 0, 0, 180, (60, 60, 70), 6 * s)
        _ligne(img, (x + 38 * s, cou + 14 * s), (x + 30 * s, cy + 6 * s), (60, 60, 70), 6 * s)
        _ellipse(img, (x + 30 * s, cy + 14 * s), (11 * s, 11 * s), 0, TRAIT); _ellipse(img, (x + 30 * s, cy + 14 * s), (7 * s, 7 * s), 0, (190, 195, 205))

def _details_tete(img, t, rx, ry, s, p, C):
    det = C.get("details", ()); cx, cy = t; tilt = math.radians(p["tilt"])
    def R(px, py): return _rot(px, py, cx, cy, tilt)
    if "lunettes_vue" in det:
        for sg in (-1, 1): _ellipse(img, R(cx + sg * 52 * s, cy + 4 * s), (32 * s, 28 * s), math.degrees(tilt), TRAIT, 5 * s)
        _ligne(img, R(cx - 20 * s, cy), R(cx + 20 * s, cy), TRAIT, 4 * s)
    if "barbe" in det:                                                     # barbe de trois jours : points gris sur le menton
        rng = np.random.default_rng(3)
        for _ in range(40):
            a = rng.uniform(0.15 * math.pi, 0.85 * math.pi); r_ = rng.uniform(0.62, 0.92)
            _ellipse(img, R(cx + math.cos(a) * rx * r_, cy + math.sin(a) * ry * r_), (2.2 * s, 2.2 * s), 0, (150, 150, 155))
    if "moustache" in det: _moustache(img, R, cx, cy, s)
    for b_ in GR.BARBES:
        if b_ in det:
            GR.barbe(img, t, rx, ry, s, p, b_, tuple(C.get("c_barbe") or (90, 65, 45)))
            if b_ in ("barbe_courte", "barbe_pleine"): _bouche(img, R, cx, cy, s, p, True)   # la bouche reste visible dans la barbe
    if "casque_audio" in det:
        _arc(img, (cx, cy - ry * 0.05), (rx * 1.08, ry * 1.05), math.degrees(tilt), 200, 340, TRAIT, 14 * s); _arc(img, (cx, cy - ry * 0.05), (rx * 1.08, ry * 1.05), math.degrees(tilt), 202, 338, (60, 60, 70), 8 * s)
        for sg in (-1, 1): _ellipse(img, R(cx + sg * rx * 1.0, cy + 4 * s), (20 * s, 34 * s), math.degrees(tilt), TRAIT); _ellipse(img, R(cx + sg * rx * 1.0, cy + 4 * s), (14 * s, 28 * s), math.degrees(tilt), (230, 60, 60))
    if "taches_rousseur" in det:
        for sg in (-1, 1):
            for k in range(5): _ellipse(img, R(cx + sg * (60 + 9 * (k % 3)) * s, cy + (28 + 8 * (k // 2)) * s), (2.6 * s, 2.6 * s), 0, (200, 140, 100))
    if "boucles_oreilles" in det:
        for sg in (-1, 1): _ellipse(img, R(cx + sg * rx * 0.98, cy + ry * 0.2 + abs(math.sin(p.get("t", 0) * 4)) * 3 * s), (8 * s, 8 * s), 0, (240, 200, 80))

def _sacs(img, x, cy, w, h, s, C):
    """Sac en bandoulière et bretelles (devant le buste)."""
    det = C.get("details", ())
    if "bretelles" in det:
        for sg in (-1, 1): _ligne(img, (x + sg * w * 0.45, cy - h * 0.48), (x + sg * w * 0.4, cy + h * 0.48), (150, 40, 50), 9 * s)
    if "sac_bandouliere" in det:
        cs = tuple(C.get("c_sac") or (110, 70, 45))
        _ligne(img, (x - w * 0.6, cy - h * 0.46), (x + w * 0.85, cy + h * 0.28), TRAIT, 12 * s); _ligne(img, (x - w * 0.6, cy - h * 0.46), (x + w * 0.85, cy + h * 0.28), cs, 6 * s)
        pts = [(x + w * 0.55, cy + h * 0.2), (x + w * 1.15, cy + h * 0.2), (x + w * 1.15, cy + h * 0.52), (x + w * 0.55, cy + h * 0.52)]
        _poly(img, pts, cs); _poly(img, pts, TRAIT, True, 4 * s)
        _poly(img, [(x + w * 0.55, cy + h * 0.2), (x + w * 1.15, cy + h * 0.2), (x + w * 1.1, cy + h * 0.34), (x + w * 0.6, cy + h * 0.34)], _fonce(cs, 0.8)); _ellipse(img, (x + w * 0.85, cy + h * 0.33), (5 * s, 5 * s), 0, (220, 190, 90))

def _moustache(img, R, cx, cy, s):
    for sg in (-1, 1):
        pts = [R(cx + sg * 2 * s, cy + 44 * s), R(cx + sg * 30 * s, cy + 40 * s), R(cx + sg * 44 * s, cy + 52 * s), R(cx + sg * 26 * s, cy + 56 * s), R(cx + sg * 2 * s, cy + 52 * s)]
        _poly(img, pts, (90, 70, 60))

def _cheveux_arriere(img, t, rx, ry, s, p, P):
    """Cheveux derrière la tête (carré, longs, queue de cheval, chignon, boucles), qui balancent avec les mouvements."""
    cx, cy = t; style, col = P["cheveux"]; tilt = p["tilt"]; bal = p.get("balance", 0.0); ep = 8 * s
    if style in GR.COIFFURES: return GR.cheveux_arriere(img, t, rx, ry, s, p, style, col)
    def masse(c, ax, ang=tilt):
        _ellipse(img, c, (ax[0] + ep, ax[1] + ep), ang, TRAIT); _ellipse(img, c, ax, ang, col)
    if style == "carre":
        masse((cx, cy + ry * 0.18), (rx * 1.13, ry * 1.02))
        for sg in (-1, 1): _ellipse(img, (cx + sg * rx * 0.62, cy + ry * 0.98), (rx * 0.32, 16 * s), 0, _fonce(col, 0.85))
    elif style == "long":                                                  # cheveux longs jusqu'au milieu du dos
        masse((cx + bal * 10 * s, cy + ry * 0.55), (rx * 1.16, ry * 1.38), tilt + bal * 3)
        for k in range(-2, 3): _ligne(img, (cx + k * rx * 0.3, cy + ry * 1.1), (cx + k * rx * 0.34 + bal * 14 * s, cy + ry * 1.75), _fonce(col, 0.8), 3 * s)
    elif style == "boucles":                                               # volume bouclé
        masse((cx, cy + ry * 0.12), (rx * 1.22, ry * 1.1))
        for k in range(14):
            a = math.pi * (0.95 + 1.1 * k / 13); _ellipse(img, (cx + math.cos(a) * rx * 1.18, cy + ry * 0.12 + math.sin(a) * ry * 1.06), (22 * s, 22 * s), 0, TRAIT)
            _ellipse(img, (cx + math.cos(a) * rx * 1.18, cy + ry * 0.12 + math.sin(a) * ry * 1.06), (16 * s, 16 * s), 0, col)
    elif style == "queue":                                                 # queue de cheval qui se balance
        q0 = (cx - rx * 0.92, cy - ry * 0.45); sw = 18 * bal + 8 * math.sin(p.get("t", 0) * 3)   # attachée sur le côté, elle pend et se balance
        bout = (q0[0] - rx * 0.3 + sw * s, q0[1] + ry * 0.85)
        _ligne(img, q0, bout, TRAIT, 58 * s); _ligne(img, q0, bout, col, 42 * s)
        _ellipse(img, (bout[0], bout[1] + 18 * s), (26 * s, 34 * s), 0, TRAIT); _ellipse(img, (bout[0], bout[1] + 18 * s), (19 * s, 27 * s), 0, col)
        _ellipse(img, q0, (14 * s, 14 * s), 0, (230, 80, 120))                                 # élastique
    elif style == "chignon":
        c0 = (cx + bal * 6 * s, cy - ry * 1.02); _ellipse(img, c0, (46 * s + ep, 40 * s + ep), 0, TRAIT); _ellipse(img, c0, (46 * s, 40 * s), 0, col)
        _arc(img, c0, (30 * s, 24 * s), 0, 200, 340, _fonce(col, 0.75), 4 * s)

def _cheveux_avant(img, t, rx, ry, s, p, P, dos):
    cx, cy = t; style, col = P["cheveux"]; tilt = math.radians(p["tilt"])
    if style in GR.COIFFURES: return GR.cheveux_avant(img, t, rx, ry, s, p, style, col, dos)
    def R(px, py): return _rot(px, py, cx, cy, tilt)
    if style in ("carre", "long", "boucles", "queue", "chignon"):          # frange sur le front (ou cheveux vus de dos)
        if dos: _ellipse(img, t, (rx * 1.02, ry * 1.0), p["tilt"], col); return
        if style in ("queue", "chignon"):                                  # cheveux tirés en arrière
            pts = [R(cx + rx * 0.97 * math.cos(math.pi + math.pi * k / 16), cy - ry * 0.2 + ry * 0.98 * math.sin(math.pi + math.pi * k / 16)) for k in range(17)]
            _poly(img, pts, col); _poly(img, pts, TRAIT, True, 4 * s)
            for k in range(4): _arc(img, R(cx, cy + ry * 0.2), (rx * (0.4 + 0.15 * k), ry * 0.95), math.degrees(tilt), 235, 305, _fonce(col, 0.78), 3 * s)
            return
        pts = [R(cx - rx * 0.92, cy - ry * 0.25)] + [R(cx + rx * 0.97 * math.cos(math.pi + math.pi * k / 14), cy - ry * 0.22 + ry * 0.98 * math.sin(math.pi + math.pi * k / 14)) for k in range(15)] + \
              [R(cx + rx * 0.92, cy - ry * 0.25)] + [R(cx + rx * (0.75 - 0.3 * k), cy - ry * (0.42 - (0.08 if k % 2 else 0))) for k in range(6)]
        _poly(img, pts, col); _poly(img, pts, TRAIT, True, 4 * s)
        for k in range(3): _ligne(img, R(cx - rx * 0.2 + k * rx * 0.25, cy - ry * 0.85), R(cx - rx * 0.28 + k * rx * 0.25, cy - ry * 0.5), _fonce(col, 0.75), 3 * s)
    elif style == "meches":                                                # mèches qui dépassent du bonnet, pattes
        for sg in (-1, 1):
            for k in range(3):
                b = R(cx + sg * rx * (0.8 + 0.06 * k), cy - ry * (0.38 - 0.1 * k))
                _poly(img, [b, R(cx + sg * rx * (0.98 + 0.05 * k), cy - ry * (0.22 - 0.1 * k)), R(cx + sg * rx * (0.82 + 0.05 * k), cy - ry * (0.18 - 0.1 * k))], col)
            _ligne(img, R(cx + sg * rx * 0.9, cy - ry * 0.3), R(cx + sg * rx * 0.93, cy + ry * 0.05), col, 9 * s)
    elif style == "nuque":                                                 # cheveux courts sous la casquette
        for sg in (-1, 1): _ligne(img, R(cx + sg * rx * 0.88, cy - ry * 0.3), R(cx + sg * rx * 0.92, cy - ry * 0.02), col, 10 * s)
    elif style == "court":                                                 # cheveux courts : petite masse sur le dessus et les tempes
        pts = [R(cx + rx * 0.98 * math.cos(math.pi + math.pi * k / 16), cy - ry * 0.32 + ry * 0.92 * math.sin(math.pi + math.pi * k / 16)) for k in range(17)]
        pts += [R(cx + rx * (0.8 - 0.2 * k), cy - ry * (0.45 + (0.07 if k % 2 else 0))) for k in range(9)]
        _poly(img, pts, col); _poly(img, pts, TRAIT, True, 4 * s)
    elif style == "couronne":                                              # tour de tête dégarni (Dédé)
        for sg in (-1, 1): _ellipse(img, R(cx + sg * rx * 0.9, cy - ry * 0.12), (16 * s, 34 * s), math.degrees(tilt) + sg * 15, col)

def _fond(img, x, y):
    x, y = int(np.clip(x, 0, img.shape[1] - 1)), int(np.clip(y, 0, img.shape[0] - 1)); return tuple(int(v) for v in img[y, x])

def _coller(img, rgba, cx, cy):
    h, w = rgba.shape[:2]; x0, y0 = int(cx - w / 2), int(cy - h * 0.6)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(img.shape[1], x0 + w), min(img.shape[0], y0 + h)
    if xb <= xa or yb <= ya: return
    s = rgba[ya - y0:yb - y0, xa - x0:xb - x0].astype(np.float32); a = s[..., 3:4] / 255
    img[ya:yb, xa:xb] = (img[ya:yb, xa:xb] * (1 - a) + s[..., :3] * a).astype(np.uint8)

YEUX = ("ouverts", "fermes", "heureux", "plisses", "grands", "vides", "roule", "spirale", "coeur", "minuscules", "etoiles", "louche")
SOURCILS = ("neutre", "colere", "triste", "hausses", "sceptique", "fronces")
BOUCHES = ("neutre", "sourire", "triste", "o", "cri", "dents", "moue", "coin", "tordue", "grand_sourire")

def _visage(img, t, rx, ry, s, p, P):
    cx, cy = t; tilt = math.radians(p["tilt"]); gx, gy = p["regard"]
    def R(px, py): return _rot(px, py, cx, cy, tilt)
    ex = 52 * s * (1 - 0.16 * abs(float(p.get("tq", 0.0)))); ey = cy + 4 * s; er = 15 * s * float(p.get("yeux_k", 1.0))   # taille des yeux propre au personnage ; trois-quarts : yeux rapprochés
    yeux, pa = p["yeux"], p["paupiere"]
    detail = bool(p.get("reflets"))                                        # visage détaillé (moteur cartoon) ; le logo garde le dessin d'origine
    lum = p.get("lumiere", 0) or -1
    fond_ = tuple(p.get("peau") or BLANC)                                   # couleur de la peau (blanc pour nos marionnettes)
    so = p["sourcils"]
    for k, sg in enumerate((-1, 1)):
        ox, oy = R(cx + sg * ex + gx * 10 * s, ey + gy * 8 * s)
        if yeux in ("fermes",) or pa >= 0.95:
            if detail: _arc(img, (ox, oy - 2 * s), (er * 1.05, er * 0.6), math.degrees(tilt), 15, 165, TRAIT, 5.5 * s)
            else: _ligne(img, (ox - er, oy), (ox + er, oy), TRAIT, 6 * s)
        elif yeux == "heureux":                                            # ^ ^
            _poly(img, [(ox - er * 1.1, oy + 5 * s), (ox, oy - er * 0.9), (ox + er * 1.1, oy + 5 * s)], TRAIT, False, 6 * s)
        elif yeux == "plisses":                                            # > <
            _poly(img, [(ox - sg * er, oy - er * 0.8), (ox + sg * er * 0.6, oy), (ox - sg * er, oy + er * 0.8)], TRAIT, False, 6 * s)
        elif yeux in ("grands", "minuscules"):
            _ellipse(img, (ox, oy), (er * 2.0, er * 2.3), 0, TRAIT); _ellipse(img, (ox, oy), (er * 2.0 - 5 * s, er * 2.3 - 5 * s), 0, BLANC)
            k_p = 0.75 if yeux == "grands" else 0.32                       # choc : pupilles réduites à une tête d'épingle
            _ellipse(img, (ox + gx * 6 * s, oy + gy * 6 * s), (er * k_p, er * k_p), 0, TRAIT)
            if detail and yeux == "grands": _ellipse(img, (ox + gx * 6 * s + lum * er * 0.25, oy + gy * 6 * s - er * 0.3), (er * 0.22, er * 0.22), 0, BLANC)
        elif yeux == "vides":                                              # blasé : demi-paupière
            _ellipse(img, (ox, oy), (er * 1.05, er * 1.15), 0, TRAIT)
            _poly(img, [(ox - er * 1.6, oy - er * 1.7), (ox + er * 1.6, oy - er * 1.7), (ox + er * 1.6, oy - er * 0.05), (ox - er * 1.6, oy - er * 0.05)], fond_)
            _ligne(img, (ox - er * 1.2, oy - er * 0.05), (ox + er * 1.2, oy - er * 0.05), TRAIT, 5 * s)
        elif yeux == "roule":                                              # yeux au ciel : pupilles en haut, paupières mi-closes
            _ellipse(img, (ox, oy - er * 0.55), (er * 0.95, er * 0.75), 0, TRAIT)
            _poly(img, [(ox - er * 1.6, oy - er * 0.25), (ox + er * 1.6, oy - er * 0.25), (ox + er * 1.6, oy + er * 1.6), (ox - er * 1.6, oy + er * 1.6)], fond_)
            _ligne(img, (ox - er * 1.15, oy - er * 0.2), (ox + er * 1.15, oy - er * 0.2), TRAIT, 5 * s)
        elif yeux == "spirale":
            pts = [(ox + math.cos(a) * er * 1.4 * a / 12, oy + math.sin(a) * er * 1.4 * a / 12) for a in np.linspace(0, 12, 40)]
            _poly(img, pts, TRAIT, False, 4 * s)
        elif yeux == "coeur":
            c_ = (225, 50, 80); h_ = er * 1.25
            _ellipse(img, (ox - h_ * 0.45, oy - h_ * 0.2), (h_ * 0.55, h_ * 0.55), 0, c_); _ellipse(img, (ox + h_ * 0.45, oy - h_ * 0.2), (h_ * 0.55, h_ * 0.55), 0, c_)
            _poly(img, [(ox - h_ * 0.98, oy - h_ * 0.05), (ox + h_ * 0.98, oy - h_ * 0.05), (ox, oy + h_ * 1.05)], c_)
        elif yeux == "etoiles":                                            # émerveillé : étoiles dans les yeux
            _ellipse(img, (ox, oy), (er * 1.15, er * 1.3), 0, TRAIT)
            _poly(img, [(ox + er * 0.7 * math.cos(math.pi / 2 + j * 4 * math.pi / 5), oy - er * 0.7 * math.sin(math.pi / 2 + j * 4 * math.pi / 5)) for j in range(5)], (250, 220, 90))
        elif yeux == "louche":                                             # sonné : chaque œil regarde ailleurs
            _ellipse(img, (ox + sg * er * 0.5, oy + (er * 0.3 if k else -er * 0.3)), (er, er * 1.15), 0, TRAIT)
        else:
            pu = float(np.clip(p.get("pupille", 1.0), 0.6, 1.5))          # yeux qui s'agrandissent (surprise, intérêt) ou se rétrécissent
            _ellipse(img, (ox, oy), (er * pu, er * 1.15 * (1 - pa) * pu), 0, TRAIT)
            if detail and pa < 0.6:                                        # reflets de lumière dans l'œil
                _ellipse(img, (ox + lum * er * 0.35 * pu, oy - er * 0.42 * (1 - pa) * pu), (er * 0.33 * pu, er * 0.33 * (1 - pa) * pu), 0, BLANC)
                _ellipse(img, (ox - lum * er * 0.3 * pu, oy + er * 0.45 * (1 - pa) * pu), (er * 0.13 * pu, er * 0.13 * pu), 0, BLANC)
            pl = float(p.get("plisse", 0.0))
            if detail and pl > 0.15:                                       # yeux plissés par le sourire : la joue remonte sous l'œil
                y_cut = oy + er * 1.15 * pu * (1 - 1.5 * pl)
                _poly(img, [(ox - er * 1.6, y_cut), (ox + er * 1.6, y_cut), (ox + er * 1.6, oy + er * 1.7), (ox - er * 1.6, oy + er * 1.7)], fond_)
                _arc(img, (ox, y_cut + er * 0.55), (er * 1.15, er * 0.55), math.degrees(tilt), 200, 340, TRAIT, 4 * s)
            if detail and pa > 0.15:                                       # paupière tombante
                _ligne(img, (ox - er * 1.2, oy - er * 1.15 * (1 - pa)), (ox + er * 1.2, oy - er * 1.15 * (1 - pa)), TRAIT, 4.5 * s)
            if detail and P.get("cils"):
                for j in range(3):
                    a0 = (-0.25 - 0.3 * j) * sg; bx_, by_ = ox + sg * er * 0.75, oy - er * 0.8 * (1 - pa)
                    _ligne(img, (bx_ - sg * j * 5 * s, by_ + j * 3 * s), (bx_ - sg * j * 5 * s + sg * 11 * s, by_ + j * 3 * s - 10 * s), TRAIT, 3.5 * s)
        # sourcils : côté intérieur (vers le nez) = ox - sg * … : colère = intérieur bas (en V), tristesse = intérieur haut
        by = oy - 34 * s - float(p.get("sourcils_h", 0.0)) * 12 * s - (float(p.get("sourcil_leve", 0.0)) * 14 * s if sg > 0 else 0)   # l'intonation fait bouger les sourcils
        e_s = (7 if not P.get("moustache") else 10) * s * float(p.get("sourcil_ep", 1.0))
        if so == "colere": a, b = (ox - sg * 22 * s, by + 10 * s), (ox + sg * 20 * s, by - 10 * s)
        elif so == "triste": a, b = (ox - sg * 22 * s, by - 10 * s), (ox + sg * 20 * s, by + 8 * s)
        elif so == "hausses": a, b = (ox - 22 * s, by - 16 * s), (ox + 22 * s, by - 16 * s)
        elif so == "sceptique": a, b = ((ox - 22 * s, by - 22 * s), (ox + 22 * s, by - 12 * s)) if sg > 0 else ((ox - 22 * s, by + 4 * s), (ox + 22 * s, by + 4 * s))
        elif so == "fronces": a, b = (ox - sg * 22 * s, by + 6 * s), (ox + sg * 20 * s, by)
        else: a, b = ((ox - 20 * s, by - 2 * s), (ox + 20 * s, by - 2 * s)) if detail and yeux in ("ouverts", "louche") else (None, None)
        if a:
            if detail and so != "neutre": _poly(img, [R(*a), R((a[0] + b[0]) / 2, min(a[1], b[1]) - 4 * s), R(*b)], TRAIT, False, e_s)
            elif detail: _arc(img, R((a[0] + b[0]) / 2, a[1] + 6 * s), (22 * s, 8 * s), math.degrees(tilt), 200, 340, TRAIT, 5 * s * float(p.get("sourcil_ep", 1.0)))
            else: _ligne(img, R(*a), R(*b), TRAIT, 7 * s)
    if detail and p.get("rides", True):                                    # rides d'expression
        if so in ("hausses", "sceptique") or yeux in ("grands", "minuscules"):
            for j in range(3): _arc(img, R(cx, cy - ry * (0.45 + 0.09 * j)), (rx * (0.22 - 0.03 * j), 6 * s), math.degrees(tilt), 200, 340, TRAIT, 3 * s)
        if so in ("colere", "fronces"):
            for sg in (-1, 1): _ligne(img, R(cx + sg * 7 * s, cy - 38 * s), R(cx + sg * 5 * s, cy - 22 * s), TRAIT, 3 * s)
    age = float(p.get("age") or 0)
    if detail and age >= 38:                                               # l'âge : pattes d'oie, sillons, front, poches sous les yeux
        k_a = min(1.0, (age - 38) / 30); trait_r = _clair(TRAIT, 0.35)
        for sg in (-1, 1):
            for j in range(1 + int(2 * k_a)): _ligne(img, R(cx + sg * (ex + er * 1.5), cy + (j - 1) * 7 * s), R(cx + sg * (ex + er * 2.2), cy + (j - 1) * 11 * s), trait_r, 2.5 * s)
            if age >= 45: _arc(img, R(cx + sg * 26 * s, cy + 64 * s), (16 * s, 20 * s), math.degrees(tilt), (-50 if sg > 0 else 140), (40 if sg > 0 else 230), trait_r, 2.5 * s)   # plis autour de la bouche
            if age >= 55: _arc(img, R(cx + sg * ex, cy + er * 1.6), (er * 0.9, er * 0.4), math.degrees(tilt), 20, 160, trait_r, 2.5 * s)
        if age >= 55 and so not in ("hausses", "sceptique"):
            for j in range(2): _arc(img, R(cx, cy - ry * (0.5 + 0.1 * j)), (rx * (0.2 - 0.04 * j), 5 * s), math.degrees(tilt), 200, 340, trait_r, 2.5 * s)
    if detail and p.get("cernes"):                                         # fatigue, pleurs : cernes
        for sg in (-1, 1): _arc(img, R(cx + sg * ex, cy + er * 1.35), (er * 1.1, er * 0.55), math.degrees(tilt), 20, 160, (170, 150, 190), 5 * s)
    if detail and p.get("narines"):                                        # colère : narines dilatées
        for sg in (-1, 1): _ellipse(img, R(cx + sg * 7 * s, cy + 44 * s), (3.5 * s, 2.5 * s), 0, TRAIT)
    if detail and p.get("maquillage") and not (p.get("joues") or p.get("gene")):
        for sg in (-1, 1): _ellipse(img, R(cx + sg * 86 * s, cy + 44 * s), (18 * s, 9 * s), 0, (250, 214, 214))
    if p.get("joues") or p.get("gene"):                                    # joues roses (rire) ; gêne : grosses rougeurs hachurées
        for sg in (-1, 1):
            _ellipse(img, R(cx + sg * 88 * s, cy + 46 * s), ((26 if p.get("gene") else 20) * s, (14 if p.get("gene") else 11) * s), 0, (245, 160, 165))
            if p.get("gene"):
                for j in range(3): _ligne(img, R(cx + sg * 88 * s - 14 * s + j * 11 * s, cy + 52 * s), R(cx + sg * 88 * s - 8 * s + j * 11 * s, cy + 40 * s), (220, 90, 100), 3 * s)
    if detail and P.get("nez"):                                            # petit nez, éclairé du côté de la lumière
        nx, ny = R(cx + gx * 6 * s, cy + 34 * s + gy * 4 * s)
        if P["nez"] == "rond": _arc(img, (nx, ny), (10 * s, 8 * s), math.degrees(tilt), -50 if lum < 0 else 50, 110 if lum < 0 else 230, TRAIT, 4 * s)   # trait du côté de l'ombre
        elif P["nez"] == "pointu": _poly(img, [R(cx - lum * 2 * s, cy + 24 * s), R(cx + lum * 9 * s, cy + 40 * s), R(cx, cy + 42 * s)], TRAIT, False, 4 * s)
        else: _arc(img, (nx, ny), (6 * s, 5 * s), math.degrees(tilt), 0, 180, TRAIT, 3.5 * s)
    if detail and P.get("moustache"): _moustache(img, R, cx, cy, s)
    _bouche(img, R, cx, cy, s, p, detail)

def _bouche(img, R, cx, cy, s, p, detail):
    mx, my = R(cx, cy + 64 * s); o = float(np.clip(p["bouche"], 0, 1)); f = p["forme"]
    v = p.get("viseme"); dents = detail
    co = float(np.clip(p.get("coins", 0.0), -1, 1))                        # coins de la bouche : relevés (contentement) ou tombants
    def coins_(w, yc):
        if detail and abs(co) > 0.2:
            for sg in (-1, 1): _ligne(img, (mx + sg * w * 0.92, yc), (mx + sg * (w + 8 * s), yc - co * 10 * s), TRAIT, 4 * s)
    rouge = p.get("rouge")                                                 # rouge à lèvres
    def ouverte(w, h, yc):
        coins_(w, yc - h * 0.15)
        if rouge: _ellipse(img, (mx, yc), (w + 6 * s, h + 6 * s), 0, rouge)
        _ellipse(img, (mx, yc), (w, h), 0, TRAIT)
        if h > 13 * s: _ellipse(img, (mx, yc + h * 0.5), (w * 0.55, h * 0.35), 0, (220, 80, 90))      # langue
        if dents and h > 11 * s:                                          # rangée de dents du haut
            roi = _roi(img, mx, yc, w, h)
            if roi:
                x0, y0, x1, y1 = roi; m = _masque_ellipse(roi, (mx, yc), (w - 3 * s, h - 3 * s), 0); m[int(yc - h * 0.45 - y0):] = 0
                img[y0:y1, x0:x1][m > 128] = (250, 250, 250)
                if h > 26 * s:                                             # grande bouche ouverte : dents du bas aussi
                    m = _masque_ellipse(roi, (mx, yc), (w - 3 * s, h - 3 * s), 0); m[:int(yc + h * 0.62 - y0)] = 0
                    img[y0:y1, x0:x1][m > 128] = (245, 245, 242)
    if v and f not in ("cri", "sourire") and o > 0.06:                   # bouche calée sur le son prononcé (syllabe par syllabe)
        if v == "M":                                                       # m, b, p : lèvres fermées
            _ligne(img, (mx - 18 * s, my + 2 * s), (mx + 18 * s, my + 2 * s), TRAIT, 7 * s); return
        if v == "F":                                                       # f, v : lèvre sur les dents
            _ellipse(img, (mx, my + 6 * s), (24 * s, 9 * s), 0, TRAIT)
            _poly(img, [(mx - 15 * s, my), (mx + 15 * s, my), (mx + 15 * s, my + 6 * s), (mx - 15 * s, my + 6 * s)], BLANC); return
        w, h = {"A": (30, 30), "E": (38, 14), "I": (34, 9), "O": (19, 24), "U": (12, 14)}.get(v, (28, 22))
        w, h = w * s * (0.75 + 0.35 * o), h * s * (0.45 + 0.75 * o)
        ouverte(w, h, my + h * 0.45); return
    if f == "cri" or (o > 0.75 and f not in ("sourire", "grand_sourire")):
        w, h = 34 * s * (0.8 + 0.5 * o), 30 * s * (0.6 + 1.0 * o)
        ouverte(w, h, my + h * 0.3)
    elif f == "grand_sourire":                                             # sourire en D, dents visibles
        w = 44 * s; h = 30 * s + 10 * s * o
        pts = [(mx - w, my - 6 * s)] + [(mx + w * math.cos(math.pi * k / 12), my - 6 * s + h * math.sin(math.pi * k / 12)) for k in range(12, -1, -1)]
        _poly(img, pts, TRAIT)
        if dents: _poly(img, [(mx - w + 8 * s, my - 2 * s), (mx + w - 8 * s, my - 2 * s), (mx + w * 0.8, my + 8 * s), (mx - w * 0.8, my + 8 * s)], (250, 250, 250))
        _ellipse(img, (mx, my + h * 0.62), (w * 0.4, h * 0.25), 0, (220, 80, 90))
    elif f == "dents":                                                     # grimace, dents serrées
        w, h = 40 * s, 15 * s
        _poly(img, [(mx - w, my - h), (mx + w, my - h), (mx + w, my + h), (mx - w, my + h)], TRAIT)
        _poly(img, [(mx - w + 5 * s, my - h + 5 * s), (mx + w - 5 * s, my - h + 5 * s), (mx + w - 5 * s, my + h - 5 * s), (mx - w + 5 * s, my + h - 5 * s)], (250, 250, 250))
        _ligne(img, (mx - w + 5 * s, my), (mx + w - 5 * s, my), TRAIT, 3 * s)
        for k in range(-3, 4): _ligne(img, (mx + k * 11 * s, my - h + 5 * s), (mx + k * 11 * s, my + h - 5 * s), TRAIT, 2.5 * s)
    elif o > 0.08:
        w, h = 28 * s * (0.8 + 0.4 * o), 24 * s * o + 3 * s
        if f == "sourire":
            _poly(img, [(mx - w * 1.3, my - 4 * s)] + [(mx + w * 1.3 * math.cos(math.pi * k / 10), my - 4 * s + (h + 10 * s) * math.sin(math.pi * k / 10)) for k in range(10, -1, -1)], TRAIT)
        else: ouverte(w, h, my + h * 0.4)
    elif f == "sourire":
        if rouge: _poly(img, [(mx - 30 * s + k * 6 * s, my + 10 * s * math.sin(math.pi * k / 10)) for k in range(11)], rouge, False, 13 * s)
        _poly(img, [(mx - 30 * s + k * 6 * s, my + 10 * s * math.sin(math.pi * k / 10)) for k in range(11)], TRAIT, False, 6 * s)
        if detail:
            for sg in (-1, 1): _ligne(img, (mx + sg * 31 * s, my - 4 * s), (mx + sg * 36 * s, my + 4 * s), TRAIT, 4 * s)
    elif f == "triste":
        _poly(img, [(mx - 24 * s + k * 4.8 * s, my + 10 * s - 10 * s * math.sin(math.pi * k / 10)) for k in range(11)], TRAIT, False, 6 * s)
    elif f == "o":
        _ellipse(img, (mx, my + 4 * s), (10 * s, 12 * s), 0, TRAIT)
    elif f == "moue":                                                      # moue boudeuse
        _poly(img, [(mx - 14 * s, my + 6 * s), (mx - 4 * s, my - 2 * s), (mx + 4 * s, my - 2 * s), (mx + 14 * s, my + 6 * s)], TRAIT, False, 6 * s)
        _arc(img, (mx, my + 8 * s), (10 * s, 6 * s), 0, 0, 180, TRAIT, 4 * s)
    elif f == "coin":                                                      # sourire en coin (malin, sûr de lui)
        sg = p.get("coin", 1)
        _poly(img, [(mx - sg * 22 * s, my + 4 * s), (mx, my + 6 * s), (mx + sg * 18 * s, my + 2 * s), (mx + sg * 28 * s, my - 8 * s)], TRAIT, False, 6 * s)
    elif f == "tordue":                                                    # bouche qui hésite (gêne, mensonge)
        _poly(img, [(mx - 26 * s + k * 5.2 * s, my + 5 * s * math.sin(k * 1.4)) for k in range(11)], TRAIT, False, 5.5 * s)
    elif detail and abs(co) > 0.15:                                        # bouche au repos qui sourit ou fait la moue
        if rouge: _poly(img, [(mx - 22 * s + k * 4.4 * s, my - co * 9 * s * ((k - 5) / 5) ** 2) for k in range(11)], rouge, False, 13 * s)
        _poly(img, [(mx - 22 * s + k * 4.4 * s, my - co * 9 * s * ((k - 5) / 5) ** 2) for k in range(11)], TRAIT, False, 6 * s)
    else:
        if rouge:                                                          # lèvres fermées maquillées
            _ellipse(img, (mx, my - 3 * s), (20 * s, 6 * s), 0, rouge); _ellipse(img, (mx, my + 4 * s), (18 * s, 7 * s), 0, rouge)
        _ligne(img, (mx - 16 * s, my), (mx + 16 * s, my), TRAIT, 6 * s if not rouge else 4 * s)

def _accessoire(img, t, rx, ry, s, p, P):
    cx, cy = t; a = P["accessoire"]; col = P["couleur"]; tilt = math.radians(p["tilt"])
    def R(px, py): return _rot(px, py, cx, cy, tilt)
    el = p.get("balance", 0.0)                   # mouvement secondaire (pompon, nœud) : retard sur la tête
    if a == "bonnet":
        top = [R(cx + rx * 0.95 * math.cos(math.pi + math.pi * k / 16), cy - ry * 0.35 + ry * 0.95 * math.sin(math.pi + math.pi * k / 16) * 0.9) for k in range(17)]
        _poly(img, top, TRAIT); _poly(img, [(u + 0, v + 0) for u, v in top], TRAIT, True, 8 * s)
        top2 = [R(cx + (rx * 0.95 - 8 * s) * math.cos(math.pi + math.pi * k / 16), cy - ry * 0.35 + (ry * 0.95 - 8 * s) * math.sin(math.pi + math.pi * k / 16) * 0.9) for k in range(17)]
        _poly(img, top2, col)
        if p.get("reflets"):                                               # côtes du tricot
            for k in range(-3, 4): _ligne(img, R(cx + k * rx * 0.2, cy - ry * 0.55), R(cx + k * rx * 0.17, cy - ry * (1.1 - 0.02 * abs(k) ** 2)), _fonce(col, 0.88), 4 * s)
        bx0, by0 = R(cx - rx * 1.0, cy - ry * 0.42); bx1, by1 = R(cx + rx * 1.0, cy - ry * 0.42)
        _ligne(img, (bx0, by0), (bx1, by1), TRAIT, 46 * s); _ligne(img, (bx0, by0), (bx1, by1), tuple(int(c * 0.82) for c in col), 46 * s - 16 * s)
        px_, py_ = R(cx + el * 22 * s, cy - ry * 1.22 + abs(el) * 4 * s); _ellipse(img, (px_, py_), (30 * s, 30 * s), 0, TRAIT); _ellipse(img, (px_, py_), (22 * s, 22 * s), 0, (250, 240, 225))
    elif a == "casquette":
        pts = [R(cx + rx * 0.98 * math.cos(math.pi + math.pi * k / 16), cy - ry * 0.25 + ry * 0.9 * math.sin(math.pi + math.pi * k / 16)) for k in range(17)]
        _poly(img, pts, TRAIT); _poly(img, [R(cx + (rx * 0.98 - 9 * s) * math.cos(math.pi + math.pi * k / 16), cy - ry * 0.25 + (ry * 0.9 - 9 * s) * math.sin(math.pi + math.pi * k / 16)) for k in range(17)], col)
        if p.get("reflets"):                                               # coutures des panneaux et petit logo
            for k in (-1, 1): _arc(img, R(cx + k * rx * 0.1, cy - ry * 0.25), (rx * 0.38, ry * 0.86), math.degrees(tilt), 190, 350, _fonce(col, 0.8), 3 * s)
            _ellipse(img, R(cx + rx * 0.38, cy - ry * 0.6), (14 * s, 10 * s), 0, (250, 250, 250))
        sg_v = 1 if p.get("dos") else -1
        v0, v1 = R(cx + sg_v * rx * 0.6, cy - ry * 0.3), R(cx + sg_v * rx * 1.45, cy - ry * 0.05)               # visière vers l'arrière
        _ligne(img, v0, v1, TRAIT, 36 * s); _ligne(img, v0, v1, tuple(int(c * 0.8) for c in col), 22 * s)
        b = R(cx, cy - ry * 0.98); _ellipse(img, b, (12 * s, 9 * s), 0, TRAIT)
    elif a == "noeud":
        c0 = R(cx + rx * 0.55, cy - ry * 0.82); k_ = 1 + 0.12 * el
        for sg in (-1, 1):
            pts = [c0, (c0[0] + sg * 62 * s * k_, c0[1] - 40 * s - el * 6 * s), (c0[0] + sg * 62 * s * k_, c0[1] + 40 * s - el * 6 * s)]
            _poly(img, pts, TRAIT); cxx = sum(q[0] for q in pts) / 3; cyy = sum(q[1] for q in pts) / 3
            _poly(img, [(cxx + (q[0] - cxx) * 0.72, cyy + (q[1] - cyy) * 0.72) for q in pts], col)
            if p.get("reflets"): _ligne(img, (cxx, cyy), (cxx + sg * 14 * s, cyy - 6 * s), _clair(col, 0.45), 4 * s)
        _ellipse(img, c0, (17 * s, 17 * s), 0, TRAIT); _ellipse(img, c0, (11 * s, 11 * s), 0, col)
    elif a == "lunettes":
        if p.get("dos"): _ligne(img, R(cx - rx * 0.97, cy - 12 * s), R(cx + rx * 0.97, cy - 12 * s), TRAIT, 8 * s); return
        for sg in (-1, 1):
            o = R(cx + sg * 56 * s, cy + 4 * s); _ellipse(img, o, (46 * s, 40 * s), 0, TRAIT, 11 * s)
            if p.get("reflets"): _ligne(img, (o[0] - 26 * s, o[1] - 10 * s), (o[0] - 12 * s, o[1] - 24 * s), (255, 255, 255), 5 * s)
        _ligne(img, R(cx - 12 * s, cy - 4 * s), R(cx + 12 * s, cy - 4 * s), TRAIT, 9 * s)
        for sg in (-1, 1): _ligne(img, R(cx + sg * 100 * s, cy - 2 * s), R(cx + sg * rx * 0.97, cy - 12 * s), TRAIT, 8 * s)
    elif a == "meche":
        for dx, h, k in ((-30, 1.42, -40), (10, 1.55, 10), (50, 1.40, 60)):          # trois épis de cheveux noirs
            pts = [R(cx + dx * s - 22 * s, cy - ry * 0.95), R(cx + (dx + k + el * 18) * s, cy - ry * h), R(cx + dx * s + 22 * s, cy - ry * 0.95)]
            _poly(img, pts, TRAIT)

# ------------------------------------------------------------------ objets tenus en main
OBJETS = ("telephone", "billet", "portefeuille", "micro", "verre", "cafe", "livre", "cles", "carte", "facture", "bouteille", "haltere",
          "seringue", "parapluie", "telecommande", "fleur", "cadeau", "pizza", "croissant", "tablette", "lettre", "journal", "stylo", "valise")

def objet(nom, s=1.0):
    """Petit accessoire dessiné (calque RGBA) à tenir en main (liste OBJETS)."""
    w, h = int(140 * s), int(170 * s); im = np.zeros((h, w, 4), np.uint8)
    k = s
    def r(x0, y0, x1, y1, c):
        cv2.rectangle(im, (int(x0), int(y0)), (int(x1), int(y1)), tuple(c) + (255,), -1, AA)
    def rc(x0, y0, x1, y1, c, e=6):                                        # rectangle avec contour noir
        r(x0, y0, x1, y1, TRAIT); r(x0 + e * k, y0 + e * k, x1 - e * k, y1 - e * k, c)
    def cer(x, y, rr, c, e=-1): cv2.circle(im, (int(x * k), int(y * k)), max(1, int(rr * k)), tuple(c) + (255,), e if e < 0 else max(1, int(e * k)), AA)
    def lig(a, b, c, e): cv2.line(im, (int(a[0] * k), int(a[1] * k)), (int(b[0] * k), int(b[1] * k)), tuple(c) + (255,), max(1, int(e * k)), AA)
    def pol(pts, c): cv2.fillPoly(im, [np.array([[x * k, y * k] for x, y in pts], np.int32)], tuple(c) + (255,), AA)
    if nom == "telephone":
        r(30*k, 10*k, 110*k, 160*k, TRAIT); r(38*k, 20*k, 102*k, 140*k, (120, 200, 250))
        r(44*k, 30*k, 96*k, 44*k, (250, 250, 250)); r(44*k, 52*k, 84*k, 62*k, (250, 250, 250)); cer(70, 150, 5, (90, 90, 100))
    elif nom == "billet":
        r(5*k, 50*k, 135*k, 120*k, TRAIT); r(11*k, 56*k, 129*k, 114*k, (150, 210, 140)); cv2.circle(im, (int(70*k), int(85*k)), int(16*k), (90, 160, 90, 255), -1, AA)
    elif nom == "portefeuille":
        r(15*k, 50*k, 125*k, 140*k, TRAIT); r(21*k, 56*k, 119*k, 134*k, (150, 95, 60)); r(80*k, 80*k, 125*k, 110*k, TRAIT)
    elif nom == "micro":
        r(60*k, 70*k, 80*k, 165*k, TRAIT); cv2.circle(im, (int(70*k), int(55*k)), int(30*k), TRAIT + (255,), -1, AA); cv2.circle(im, (int(70*k), int(55*k)), int(24*k), (150, 150, 160, 255), -1, AA)
    elif nom == "verre":
        r(40*k, 40*k, 100*k, 160*k, TRAIT); r(46*k, 60*k, 94*k, 154*k, (245, 190, 60)); r(46*k, 46*k, 94*k, 64*k, (250, 250, 245))
        cer(58, 110, 4, (255, 230, 150)); cer(76, 130, 3, (255, 230, 150))
    elif nom == "cafe":
        r(40*k, 70*k, 100*k, 160*k, TRAIT); r(46*k, 76*k, 94*k, 154*k, (250, 250, 245)); cv2.circle(im, (int(108*k), int(110*k)), int(16*k), TRAIT + (255,), int(7*k), AA)
        r(46*k, 76*k, 94*k, 88*k, (120, 70, 40))
    elif nom == "livre":
        rc(15, 40, 125, 150, (60, 90, 170)); r(22*k, 140*k, 118*k, 146*k, (245, 240, 225)); lig((40, 70), (100, 70), (240, 210, 90), 5)
    elif nom == "cles":
        cer(50, 60, 22, TRAIT, 8); lig((64, 76), (110, 130), TRAIT, 10); lig((95, 112), (110, 100), TRAIT, 8); lig((105, 124), (118, 112), TRAIT, 8)
        lig((64, 76), (110, 130), (230, 190, 70), 4); cer(50, 60, 22, (230, 190, 70), 3)
    elif nom == "carte":
        rc(10, 60, 130, 135, (40, 110, 200)); r(22*k, 78*k, 48*k, 96*k, (240, 200, 90)); lig((22, 116), (110, 116), (220, 230, 245), 5)
    elif nom == "facture":
        pol([(25, 10), (115, 10), (115, 160), (100, 150), (85, 160), (70, 150), (55, 160), (40, 150), (25, 160)], TRAIT)
        pol([(31, 16), (109, 16), (109, 150), (100, 142), (85, 152), (70, 142), (55, 152), (40, 142), (31, 150)], (252, 252, 245))
        for yy in (40, 58, 76, 94): lig((42, yy), (98, yy), (170, 170, 180), 4)
        lig((60, 122), (98, 122), (220, 40, 40), 7)
    elif nom == "bouteille":
        rc(45, 60, 95, 165, (60, 150, 90)); rc(58, 15, 82, 66, (60, 150, 90)); r(51*k, 95*k, 89*k, 125*k, (245, 235, 210))
    elif nom == "haltere":
        lig((20, 90), (120, 90), TRAIT, 14); rc(5, 55, 35, 125, (70, 70, 80)); rc(105, 55, 135, 125, (70, 70, 80)); lig((35, 90), (105, 90), (170, 170, 180), 7)
    elif nom == "seringue":
        rc(30, 70, 110, 105, (220, 235, 250)); lig((110, 87), (138, 87), TRAIT, 4); lig((5, 87), (30, 87), TRAIT, 10); r(40*k, 78*k, 80*k, 97*k, (230, 60, 60))
    elif nom == "parapluie":
        pol([(10, 70), (70, 15), (130, 70)], TRAIT); pol([(18, 66), (70, 22), (122, 66)], (220, 60, 80)); lig((70, 70), (70, 155), TRAIT, 7); cer(60, 155, 10, TRAIT, 6)
    elif nom == "telecommande":
        rc(45, 20, 95, 165, (60, 60, 70)); cer(70, 45, 9, (230, 60, 60))
        for yy in (75, 98, 121, 144): cer(60, yy, 5, (200, 200, 210)); cer(80, yy, 5, (200, 200, 210))
    elif nom == "fleur":
        lig((70, 70), (70, 165), (60, 150, 70), 8)
        for a in range(6): cer(70 + 22 * math.cos(a * 1.047), 55 + 22 * math.sin(a * 1.047), 16, (240, 110, 150))
        cer(70, 55, 13, (250, 210, 70))
    elif nom == "cadeau":
        rc(15, 60, 125, 160, (200, 60, 70)); r(62*k, 60*k, 78*k, 160*k, (250, 210, 70)); r(15*k, 98*k, 125*k, 112*k, (250, 210, 70))
        cer(55, 50, 14, (250, 210, 70), 6); cer(85, 50, 14, (250, 210, 70), 6)
    elif nom == "pizza":
        pol([(10, 30), (130, 30), (70, 160)], TRAIT); pol([(18, 36), (122, 36), (70, 148)], (245, 200, 90)); r(14*k, 26*k, 126*k, 42*k, (200, 140, 70))
        for x_, y_ in ((50, 60), (85, 62), (68, 95)): cer(x_, y_, 9, (210, 60, 50))
    elif nom == "croissant":
        cv2.ellipse(im, (int(70 * k), int(100 * k)), (int(60 * k), int(38 * k)), 0, 180, 360, TRAIT + (255,), int(30 * k), AA)
        cv2.ellipse(im, (int(70 * k), int(100 * k)), (int(60 * k), int(38 * k)), 0, 185, 355, (225, 160, 70, 255), int(20 * k), AA)
    elif nom == "tablette":
        rc(10, 25, 130, 150, (40, 40, 48)); r(20*k, 35*k, 120*k, 140*k, (150, 210, 245)); r(30*k, 50*k, 80*k, 60*k, (250, 250, 250))
    elif nom == "lettre":
        rc(10, 50, 130, 135, (245, 240, 225)); pol([(16, 56), (124, 56), (70, 98)], (225, 215, 195)); cer(70, 96, 9, (200, 40, 50))
    elif nom == "journal":
        rc(15, 20, 125, 160, (240, 238, 230)); r(25*k, 32*k, 115*k, 50*k, TRAIT)
        for yy in range(64, 150, 14): lig((25, yy), (65, yy), (150, 150, 155), 4); lig((75, yy), (115, yy), (150, 150, 155), 4)
    elif nom == "stylo":
        lig((25, 140), (115, 30), TRAIT, 16); lig((25, 140), (115, 30), (40, 80, 200), 9); lig((25, 140), (36, 127), (240, 220, 200), 9)
    elif nom == "valise":
        rc(10, 55, 130, 160, (120, 80, 50)); lig((50, 55), (50, 35), TRAIT, 8); lig((90, 55), (90, 35), TRAIT, 8); lig((50, 35), (90, 35), TRAIT, 8)
        r(10*k, 100*k, 130*k, 110*k, (90, 60, 35))
    else:
        return None
    return im

# ------------------------------------------------------------------ effets
EFFETS = ("larmes", "larme", "sueur", "veine", "etoiles", "traits", "goutte", "fumee", "coeurs", "zzz", "interro", "exclam", "ampoule", "notes", "eclairs")

def _effets(img, t, rx, ry, s, p):
    cx, cy = t; tm = p["t"]
    for e in p["effets"]:
        if e == "larmes":                                                  # cascades de larmes
            for sg in (-1, 1):
                x0 = cx + sg * 52 * s
                for k in range(4):
                    ph = (tm * 2.2 + k / 4) % 1; yy = cy + 30 * s + ph * 140 * s
                    _ellipse(img, (x0 + sg * ph * 30 * s, yy), (9 * s, 13 * s), 0, (90, 170, 245))
        elif e == "larme":
            _ellipse(img, (cx + 70 * s, cy + 40 * s + (tm * 60 % 60) * s), (10 * s, 15 * s), 0, (90, 170, 245))
        elif e == "sueur":
            _ellipse(img, (cx + rx * 0.85, cy - ry * 0.35 + (tm * 40 % 30) * s), (11 * s, 17 * s), 0, (120, 200, 250))
        elif e == "goutte":                                                # grosse goutte de gêne sur la tempe (manga)
            gx_, gy_ = cx + rx * 0.72, cy - ry * 0.55 + math.sin(tm * 3) * 3 * s
            _poly(img, [(gx_, gy_ - 34 * s), (gx_ + 20 * s, gy_), (gx_ - 20 * s, gy_)], TRAIT); _ellipse(img, (gx_, gy_ + 6 * s), (22 * s, 22 * s), 0, TRAIT)
            _poly(img, [(gx_, gy_ - 27 * s), (gx_ + 15 * s, gy_), (gx_ - 15 * s, gy_)], (170, 220, 250)); _ellipse(img, (gx_, gy_ + 6 * s), (17 * s, 17 * s), 0, (170, 220, 250))
            _ellipse(img, (gx_ - 6 * s, gy_ + 2 * s), (4 * s, 6 * s), 0, (250, 250, 255))
        elif e == "veine":                                                 # veine de colère ╬
            v = (cx + rx * 0.55, cy - ry * 0.55); k = 14 * s
            for a, b in (((-k, -k * 0.4), (-k * 0.4, -k)), ((k * 0.4, -k), (k, -k * 0.4)), ((-k, k * 0.4), (-k * 0.4, k)), ((k * 0.4, k), (k, k * 0.4))):
                _ligne(img, (v[0] + a[0], v[1] + a[1]), (v[0] + b[0], v[1] + b[1]), (220, 40, 40), 7 * s)
        elif e == "fumee":                                                 # fumée qui sort des oreilles / nuage noir de colère
            for k in range(4):
                ph = (tm * 1.4 + k / 4) % 1; r_ = (14 + 22 * ph) * s
                for sg in (-1, 1):
                    _ellipse(img, (cx + sg * (rx * 1.05 + ph * 40 * s), cy - ry * 0.1 - ph * 90 * s), (r_, r_), 0, tuple(int(90 + 120 * ph) for _ in range(3)))
        elif e == "etoiles":
            for k in range(3):
                a = tm * 4 + k * 2.09; px_, py_ = cx + math.cos(a) * rx * 0.9, cy - ry * 1.1 + math.sin(a) * 20 * s
                _poly(img, [(px_ + 18 * s * math.cos(math.pi / 2 + j * 4 * math.pi / 5), py_ - 18 * s * math.sin(math.pi / 2 + j * 4 * math.pi / 5)) for j in range(5)], (250, 200, 40))
        elif e == "coeurs":
            for k in range(3):
                ph = (tm * 0.8 + k / 3) % 1; hx, hy = cx + (k - 1) * 70 * s + math.sin(tm * 3 + k) * 12 * s, cy - ry * 1.1 - ph * 120 * s; h_ = 16 * s * (1 - 0.4 * ph)
                _ellipse(img, (hx - h_ * 0.5, hy), (h_ * 0.6, h_ * 0.6), 0, (235, 70, 110)); _ellipse(img, (hx + h_ * 0.5, hy), (h_ * 0.6, h_ * 0.6), 0, (235, 70, 110))
                _poly(img, [(hx - h_ * 1.08, hy + h_ * 0.15), (hx + h_ * 1.08, hy + h_ * 0.15), (hx, hy + h_ * 1.2)], (235, 70, 110))
        elif e == "zzz":
            for k in range(3):
                ph = (tm * 0.6 + k / 3) % 1; zx, zy = cx + rx * 0.8 + ph * 60 * s, cy - ry * 0.9 - ph * 110 * s; z_ = (12 + 8 * k) * s * 0.8
                _poly(img, [(zx - z_, zy - z_), (zx + z_, zy - z_), (zx - z_, zy + z_), (zx + z_, zy + z_)], TRAIT, False, 5 * s)
        elif e in ("interro", "exclam"):                                   # « ? » ou « ! » au-dessus de la tête
            px_, py_ = cx + rx * 0.7, cy - ry * 1.25 - abs(math.sin(tm * 6)) * 10 * s
            if e == "exclam":
                _ligne(img, (px_, py_ - 40 * s), (px_, py_ + 8 * s), TRAIT, 16 * s); _ellipse(img, (px_, py_ + 30 * s), (9 * s, 9 * s), 0, TRAIT)
            else:
                _arc(img, (px_, py_ - 20 * s), (22 * s, 20 * s), 0, 180, 400, TRAIT, 11 * s); _ligne(img, (px_ + 2 * s, py_ + 0 * s), (px_, py_ + 12 * s), TRAIT, 11 * s)
                _ellipse(img, (px_, py_ + 32 * s), (8 * s, 8 * s), 0, TRAIT)
        elif e == "ampoule":                                               # idée !
            bx, by = cx, cy - ry * 1.45 - abs(math.sin(tm * 4)) * 6 * s
            for k in range(8):
                a = k * math.pi / 4; _ligne(img, (bx + math.cos(a) * 46 * s, by + math.sin(a) * 46 * s), (bx + math.cos(a) * 60 * s, by + math.sin(a) * 60 * s), (250, 200, 40), 5 * s)
            _ellipse(img, (bx, by), (30 * s, 32 * s), 0, TRAIT); _ellipse(img, (bx, by), (24 * s, 26 * s), 0, (255, 236, 120))
            _poly(img, [(bx - 14 * s, by + 26 * s), (bx + 14 * s, by + 26 * s), (bx + 12 * s, by + 46 * s), (bx - 12 * s, by + 46 * s)], (150, 150, 160))
        elif e == "notes":                                                 # il chantonne
            for k in range(2):
                ph = (tm * 0.7 + k / 2) % 1; nx, ny = cx + rx * (0.7 + 0.4 * ph), cy - ry * 0.8 - ph * 120 * s
                _ellipse(img, (nx, ny), (12 * s, 9 * s), -20, TRAIT); _ligne(img, (nx + 10 * s, ny), (nx + 10 * s, ny - 40 * s), TRAIT, 5 * s)
                _ligne(img, (nx + 10 * s, ny - 40 * s), (nx + 26 * s, ny - 30 * s), TRAIT, 5 * s)
        elif e == "eclairs":                                               # fureur : éclairs autour de la tête
            for k in range(3):
                a = -math.pi * 0.8 + k * math.pi * 0.3 + math.sin(tm * 9) * 0.05; r0 = rx * 1.2
                x0, y0 = cx + math.cos(a) * r0, cy + math.sin(a) * r0
                pts = [(x0, y0), (x0 + 16 * s, y0 - 24 * s), (x0 + 4 * s, y0 - 26 * s), (x0 + 18 * s, y0 - 52 * s)]
                _poly(img, pts, (250, 210, 40), False, 7 * s)
        elif e == "traits":                                                # traits d'énervement / de choc autour de la tête
            for k in range(5):
                a = -math.pi * 0.85 + k * math.pi * 0.17; r0, r1 = rx * 1.15, rx * 1.38
                _ligne(img, (cx + math.cos(a) * r0, cy + math.sin(a) * r0), (cx + math.cos(a) * r1, cy + math.sin(a) * r1), TRAIT, 6 * s)
