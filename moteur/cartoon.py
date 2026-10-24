"""Moteur vidéo « cartoon » : uniquement pour les sketchs libres et les gags éclair (le JT garde jt.py).

Les personnages (marionnette.py) sont animés image par image : bouche synchronisée sur la voix, clignements, regard vers
celui qui parle, émotions lues dans les indications de jeu ([laughs], [angry], [cries]…), gestes, réactions aux chutes.
Mise en scène façon TikTok : décor du quotidien, plans serrés qui alternent sur celui qui parle, plan large à chaque scène,
titre « POV » en haut dans un cadre blanc, sous-titres mot par mot, bruitages.

Rendu détaillé (réglage RENDU_DETAILLE, activé par défaut) : le « studio » (studio.py) fixe la bible de l'épisode (lieu, heure,
lumière, garde-robe, figurants, gags écrits dans le décor, ambiances) et le storyboard (plan, mouvement de caméra, geste, réaction).
Le moteur l'exécute : plans larges / moyens / serrés / très serrés, plongée et contre-plongée, plan par-dessus l'épaule (l'autre
personnage de dos, flou, au premier plan), avancée lente, travelling, caméra à l'épaule, zoom choc ; profondeur (le décor glisse
moins vite que les personnages, le comptoir du premier plan plus vite), flou d'arrière-plan sur les plans serrés, figurants qui
vivent au fond, regard caméra sur les silences gênants, vapeur, poussière dans la lumière, pluie, neige, néon qui grésille,
étalonnage selon l'heure et vignettage.

rendre(sk, sortie, audios, mots=None, decors=None, mini=False) -> durée (s)
  decors : {indice de scène: image RGB 1080x1920} (générées par Stable Diffusion XL) ; sinon décors dessinés par le robot
  (decor_dessin.py ; fond uni pastel si le rendu détaillé est coupé)."""
import bisect, math, os, re, subprocess, sys, tempfile, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ICI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ICI)
import marionnette as M, sons_modernes as SM, bruitages as BR, marque, studio, decor_dessin as DD, humain as HU, levres, decor_anime as DA
from jt import minutage, carton, son, vers_mix, enveloppe, poser, pop, W, H, FPS, SR, SRM, FB

CAP_Y = 1700
MINUTAGE = []                                                              # (début, fin, texte, qui) de la dernière vidéo : contrôle qualité
PH = []                                                                    # répliques de la dernière vidéo avec leur plan (mémoire du studio)
BRUITAGES = []                                                             # (nom, instant, gain) des bruitages de la dernière vidéo
RENDU = {}                                                                 # ce qui a été monté (contrôle qualité : moteur/qualite.py)
COUVERTURE = None                                                          # instant (s) choisi pour l'image de couverture TikTok
COUVERTURE_MS = [2500]                                                     # instant de l'image de couverture (millisecondes)
DETAIL = (os.environ.get("RENDU_DETAILLE") or "1") != "0"                 # réglage de la régie : rendu détaillé (studio) ou simple
HUMAINS = DETAIL and (os.environ.get("PERSONNAGES") or "humains") == "humains"   # personnages adultes (casting libre) ou marionnettes
PASTELS = [(246, 228, 214), (226, 236, 246), (236, 246, 226), (248, 232, 240), (250, 242, 214)]

# ------------------------------------------------------------------ émotions lues dans les indications de jeu
EMOTIONS = [("gene", r"awkward|embarrass|sheepish|g[eê]n[eé]"), ("sceptique", r"skeptic|suspicio|doubt|unconvinc|sceptique"),
            ("amour", r"love|tender|dreamy|amoureu|flirt"), ("fatigue", r"tired|sleepy|yawn|drows|fatigu"),
            ("reflechit", r"think|pensive|ponder|hmm|r[eé]fl[eé]ch"), ("idee", r"eureka|idea|realiz|id[eé]e"), ("chante", r"sing|humm|chant"),
            ("rire", r"laugh|giggl|chuckl|rire"), ("cri", r"shout|yell|scream|cri"), ("colere", r"angr|annoy|furious|irrit|mad|col[eè]re"),
            ("pleurs", r"cry|crie?s|sob|tear|pleur"), ("soupir", r"sigh|tired|exhaust|soupir|weary"), ("panique", r"panic|nervous|scared|afraid|stress"),
            ("choc", r"gasp|shock|surpris|stunned"), ("blase", r"deadpan|sarcas|flat|bored|monoton|ironic"), ("joie", r"excit|happy|cheer|joy|enthous"),
            ("fier", r"confident|smug|proud|cocky"), ("chuchote", r"whisper|chuchot")]

def emotion(d):
    tags = " ".join(re.findall(r"\[([^\]]{1,40})\]", d or "")).lower()
    for nom, motif in EMOTIONS:
        if re.search(motif, tags): return nom
    return "neutre"

STYLE_RENDU = (os.environ.get("STYLE_RENDU") or "cel").lower()           # cel (aplats pro) | volume (effet 3D doux) | 3d (3D toon brillant)
SSAA = (os.environ.get("SSAA") or "1") != "0"                             # personnages dessinés en double résolution puis réduits
APPEL_ON = (os.environ.get("APPEL_PARTAGE") or "1") != "0"               # appels : écran partagé, plans d'écoute, voix au téléphone
REMB_ON = (os.environ.get("REMBOBINAGE") or "1") != "0"                  # « revenons 5 minutes avant » : rembobinage façon cassette
OMBRES = (os.environ.get("OMBRES") or "1") != "0"                         # ombres portées des personnages (sol, mur le soir)
DECOR_VIVANT = (os.environ.get("DECOR_VIVANT") or "1") != "0"             # la rue vit : voitures qui passent au loin
CEL = (os.environ.get("CEL") or ("0" if (os.environ.get("STYLE_PERSO") or "toon").lower() == "toon" else "1")) != "0"   # ombrage en aplat + contour épais
# (coupé par défaut avec le nouveau style « toon » : trait fin et ombres déjà dessinés comme la référence)
LUMIERES_VIVES = (os.environ.get("LUMIERES_VIVES") or "1") != "0"
MANGA = (os.environ.get("MANGA") or "1") != "0"                           # effets manga : fond qui explose, traits de vitesse
SIGNATURE = (os.environ.get("SIGNATURE") or "1") != "0"                   # signature visuelle de la chaîne (logo, couleurs)
_a = np.arange(256) / 255.0
LUT_CHAINE = np.clip(255 * (_a - 0.30 * np.sin(2 * np.pi * _a) / (2 * np.pi)), 0, 255).astype(np.uint8)[:, None].repeat(3, 1)[:, None, :]   # courbe en S douce       # phares, télé, néon qui vivent pendant la scène
PARALLAXE = (os.environ.get("PARALLAXE") or "1") != "0"                 # décors IA en profondeur (premier plan / fond)
LUMIERE_DECOR = (os.environ.get("LUMIERE_DECOR") or "1") != "0"         # personnages éclairés par la lumière du lieu
EXAGERE = float(os.environ.get("EXAGERE") or 1.25)                     # jeu des personnages : 1 = sobre, 1.25 = toons (défaut), 1.6 = très exagéré
STYLE = {  # yeux, sourcils, forme de bouche au repos, bras gauche, bras droit, effets, rougeur, tremblement
    "neutre":   ("ouverts", "neutre", "neutre", None, None, (), 0, 0),
    "rire":     ("heureux", "neutre", "sourire", (-35, 70), (35, -70), (), 0, 0),
    "cri":      ("plisses", "colere", "cri", (-120, -30), (120, 30), ("traits",), 0.5, 0.6),
    "colere":   ("ouverts", "colere", "triste", (-60, -75), (60, 75), ("veine",), 0.35, 0.25),
    "pleurs":   ("fermes", "triste", "triste", (-150, -55), (150, 55), ("larmes",), 0, 0.1),
    "soupir":   ("vides", "triste", "triste", (-8, 4), (8, -4), (), 0, 0),
    "panique":  ("grands", "hausses", "o", (-140, -20), (140, 20), ("sueur", "traits"), 0, 0.35),
    "choc":     ("grands", "hausses", "o", (-100, -60), (100, 60), ("traits",), 0, 0),
    "blase":    ("vides", "neutre", "neutre", (-15, 5), (75, -95), (), 0, 0),
    "joie":     ("heureux", "hausses", "sourire", (-165, 20), (165, -20), ("etoiles",), 0, 0),
    "fier":     ("vides", "hausses", "sourire", (-60, 120), (60, -120), (), 0, 0),
    "chuchote": ("ouverts", "hausses", "o", (-20, 10), (110, -120), (), 0, 0),
    "gene":     ("ouverts", "triste", "tordue", None, None, ("goutte",), 0, 0),
    "sceptique": ("vides", "sceptique", "coin", None, None, (), 0, 0),
    "amour":    ("coeur", "hausses", "sourire", (-60, 100), (60, -100), ("coeurs",), 0, 0),
    "fatigue":  ("vides", "triste", "neutre", (-8, 4), (8, -4), ("zzz",), 0, 0),
    "reflechit": ("ouverts", "fronces", "moue", None, None, ("interro",), 0, 0),
    "idee":     ("grands", "hausses", "grand_sourire", (-18, 8), (165, -10), ("ampoule",), 0, 0),
    "chante":   ("fermes", "hausses", "o", (-60, -40), (60, 40), ("notes",), 0, 0),
}
# rendu détaillé : jeu d'acteur continu (sourcils, pupilles, yeux plissés, coins de la bouche, épaules, buste, pied)
EXPRESSIF = {
    "rire": dict(plisse=0.6, coins=0.9, sourcils_h=0.5), "joie": dict(plisse=0.4, coins=1.0, pupille=1.2, sourcils_h=0.7),
    "amour": dict(coins=0.7, sourcils_h=0.5), "fier": dict(coins=0.6, penche=-0.3), "colere": dict(coins=-0.7, pupille=0.8, penche=0.6, narines=True),
    "cri": dict(penche=0.8, narines=True), "pleurs": dict(coins=-0.9, penche=-0.2, cernes=True), "soupir": dict(coins=-0.6, epaules=0.3), "triste": dict(coins=-0.8, cernes=True),
    "blase": dict(coins=-0.2, paupiere=0.35), "sceptique": dict(sourcil_leve=0.9, coins=-0.3), "gene": dict(epaules=0.6, coins=-0.3, pupille=0.9),
    "choc": dict(pupille=1.4, sourcils_h=1.2, penche=-0.5), "panique": dict(epaules=0.8, sourcils_h=1.0), "reflechit": dict(sourcil_leve=0.6, coins=-0.2),
    "idee": dict(sourcils_h=1.0, pupille=1.3, coins=0.8), "fatigue": dict(epaules=0.2, coins=-0.3, sourcils_h=-0.4, cernes=True, paupiere=0.45), "chuchote": dict(penche=0.5),
}
# rendu détaillé : visage plus expressif pour chaque émotion (yeux, bouche au repos, effets, teint)
DETAILS_EMO = {
    "rire": dict(forme="grand_sourire"), "cri": dict(effets=("traits", "eclairs")), "colere": dict(forme="dents", effets=("veine", "fumee")),
    "panique": dict(yeux="minuscules", paleur=0.55, effets=("sueur", "goutte")), "choc": dict(yeux="minuscules", effets=("traits", "exclam")),
    "blase": dict(forme="coin"), "fier": dict(forme="coin"), "joie": dict(yeux="etoiles", forme="grand_sourire"),
    "pleurs": dict(forme="triste"), "soupir": dict(forme="moue"), "gene": dict(gene=True),
}

GESTES = [((-20, 10), (100, -40)), ((-100, 40), (20, -10)), ((-110, -30), (110, 30)), ((-20, 10), (150, -10)), ((-40, 80), (40, -80))]
MAINS_CONV = [("ouverte", "paume"), ("paume", "ouverte"), ("paume", "paume"), ("ouverte", "index"), ("ouverte", "ouverte")]   # mains des gestes de conversation
# poses expressives (bras gauche, bras droit) : angles épaule / coude en degrés, 0 = vers le bas — catalogue complet dans studio.GESTES
POSES = studio.POSES
TEL_OREILLE = (105, 120) if (os.environ.get("STYLE_PERSO") or "toon").lower() == "toon" else (140, 95)   # téléphone contre l'oreille (bord de la tête)
NEUTRE_BRAS = ((-18, 8), (18, -8))
TOON = (os.environ.get("STYLE_PERSO") or "toon").lower() == "toon"
# style toon : gestes de conversation NATURELS (copiés sur les vidéos de référence) — un bras qui explique, coude près du
# corps, l'autre au repos ; gestes tenus 2,5 à 3,5 s (pas de bras qui moulinent) ; amplitude bornée
GESTES_TOON = [((-12, 6), (14, 100)), ((-14, -100), (12, -6)), ((-22, -88), (22, 88)), ((-12, 6), (12, -6)), ((-12, 6), (24, 112)), ((-24, -112), (12, -6))]
# gestes expressifs en version naturelle (coudes pliés près du corps, avant-bras vers l'avant), comme dans les vidéos de référence
POSES_TOON = {"explique": ((-12, 6), (12, 98)), "bras_ouverts": ((-26, -86), (26, 86)), "haussement": ((-30, -96), (30, 96)),
              "pointe_d": ((-12, 6), (62, 12)), "pointe_g": ((-62, -12), (12, -6)), "stop": ((-12, 6), (38, 112)),
              "compte": ((-30, -92), (30, 102)), "poing": ((-12, 6), (40, 120)),
              "poches": ((-22, 40), (22, -40)), "appuye": ((-12, 6), (22, -40)), "pianote": ((-8, 100), (8, -100)), "volant": ((-32, 80), (32, -80))}
MAINS_TOON = [("ouverte", "paume"), ("paume", "ouverte"), ("paume", "paume"), ("ouverte", "ouverte"), ("ouverte", "index"), ("index", "ouverte")]
GESTES_TETE = ("facepalm", "gratte_tete", "menton", "telephone", "desespoir", "pouce")   # gestes qui montent vraiment près du visage


def bras_naturel(b, g=None):
    """Style toon : bras ramené dans une amplitude naturelle (pas de bras tendus à l'horizontale ni levés derrière la tête),
    sauf pour les gestes qui vont vraiment vers le visage ou au-dessus."""
    if not TOON or g in GESTES_TETE: return b
    a1, a2 = b; s1 = 1 if a1 >= 0 else -1; m1 = abs(a1)
    if m1 > 45: m1 = 45 + (m1 - 45) * 0.35                                 # épaule : on lève peu le bras, le coude reste bas
    a2 = max(-110, min(110, a2))
    return (s1 * m1, a2)

def geste_texte(texte, emo, k=0):
    """Geste choisi d'après la réplique (ponctuation, mots) quand l'émotion n'impose rien (voir studio.geste)."""
    g = studio.geste(texte, emo, k)
    return g if (DETAIL or g in ("croises", "haussement", "desespoir", "pointe", "poing")) else None

def _ease(u): u = min(1, max(0, u)); return u * u * (3 - 2 * u)

def _ressort(u):
    """Mouvement « dessin animé » : petit élan en sens inverse, départ, léger dépassement puis stabilisation (de 0 à 1)."""
    if u <= 0: return 0.0
    if u < 0.15: return -0.1 * math.sin(math.pi * u / 0.15)               # anticipation
    v = (u - 0.15) / 0.85
    return min(1.22, 1 - math.exp(-4.5 * v) * math.cos(6.5 * v))           # dépassement amorti

BOUCHE_ECOUTE = {"o": "moue", "cri": "dents", "grand_sourire": "sourire"}   # bouche fermée de celui qui écoute (même émotion)

def viseme(c):
    """Forme de bouche d'une lettre (français simplifié)."""
    c = c.lower()
    if c in "aàâ": return "A"
    if c in "eéèêëœ": return "E"
    if c in "iîïyj": return "I"
    if c in "oôö": return "O"
    if c in "uùûüwq": return "U"
    if c in "mbp": return "M"
    if c in "fv": return "F"
    return None

def viseme_a(groupes, tm):
    """Lettre en cours de prononciation : position dans le groupe de mots affiché à cet instant."""
    g = next((x for x in groupes if x[1] <= tm < x[2]), None)
    if not g: return None
    lettres = [c for c in g[0] if c.isalpha()]
    if not lettres: return None
    k = min(len(lettres) - 1, int((tm - g[1]) / max(0.05, g[2] - g[1]) * len(lettres)))
    for j in (k, k + 1, k - 1):                                            # consonne neutre : la voyelle voisine donne la forme
        if 0 <= j < len(lettres) and viseme(lettres[j]): return viseme(lettres[j])
    return None

def _mel(a, b, u):
    if a is None or b is None: return b if u > 0.5 else a
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)

def volume3d(sub, mm, lum=-1, force=1.0, brillance=0.6, contour_lum=0.5):
    """« Effet 3D » sans moteur 3D : chaque partie du personnage (séparée par le trait noir) reçoit un relief bombé (carte de
    distance), éclairé comme un objet en volume : ombre douce, reflet brillant, liseré de lumière, ombre de contact près des traits.
    Le trait noir et les détails restent nets. sub : image RGB (modifiée), mm : masque du personnage."""
    g = cv2.cvtColor(sub, cv2.COLOR_RGB2GRAY)
    clair = mm & (g > 70)
    if not clair.any(): return
    sombre = (mm & ~clair).astype(np.uint8)                                # traits et petits détails sombres (yeux, barbe, bouche…)
    k_, lab_, st_, _c = cv2.connectedComponentsWithStats(sombre, connectivity=8)
    seuil = max(400, int(0.004 * mm.sum()))
    petits = np.zeros(k_, bool); petits[1:] = st_[1:, cv2.CC_STAT_AREA] < seuil
    zone = (clair | petits[lab_]).astype(np.uint8)                         # les détails ne cassent pas le relief : seuls les grands traits séparent les parties
    zone = cv2.erode(zone, np.ones((3, 3), np.uint8))
    d = cv2.distanceTransform(zone, cv2.DIST_L2, 5)
    zf = zone.astype(np.float32); taille = max(8.0, float(np.sqrt(zone.sum())) * 0.05)
    h = sum(cv2.GaussianBlur(zf, (0, 0), taille * k_s) for k_s in (0.35, 0.8, 1.6)) / 3 * zf   # « gonflé » comme un coussin (sans pli)
    kz, labz = cv2.connectedComponents(zone, connectivity=4)
    hmax = np.full(kz, 1e-3, np.float32); np.maximum.at(hmax, labz.ravel(), h.ravel())
    h = np.clip(h / hmax[labz], 0, 1) ** 0.7                               # chaque partie (tête, buste, bras…) a son propre volume
    h = cv2.GaussianBlur(h, (0, 0), 1.5)                                   # (carte de relief, pas l'image : rien n'est flou)
    gx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=5); gy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=5)
    k = 6.0; nx, ny, nz = -gx * k, -gy * k, np.ones_like(h); n = np.sqrt(nx * nx + ny * ny + nz * nz); nx, ny, nz = nx / n, ny / n, nz / n
    L = np.array([0.55 * (1 if lum > 0 else -1), -0.6, 0.58], np.float32); L /= np.linalg.norm(L)
    diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    ombre = 0.62 + 0.48 * diff                                             # côté à l'ombre plus sombre, côté lumière plus clair
    Hv = L + np.array([0, 0, 1], np.float32); Hv /= np.linalg.norm(Hv)
    spec = np.clip(nx * Hv[0] + ny * Hv[1] + nz * Hv[2], 0, 1) ** 40 * brillance
    rim = np.clip(1 - nz, 0, 1) ** 2 * np.clip(nx * (1 if lum > 0 else -1), 0, 1) * contour_lum
    ao = 1 - 0.35 * np.exp(-d / 6.0)                                       # ombre de contact contre les traits (occlusion)
    m3 = clair & zone.astype(bool)                                         # on n'éclaire que les couleurs (les détails sombres restent nets)
    f = sub.astype(np.float32)
    fac = (1 + (ombre * ao - 1) * force)[..., None]
    out = f * fac + (spec[..., None] * 255 + rim[..., None] * np.array([255, 240, 215], np.float32)) * force
    sub[m3] = np.clip(out[m3], 0, 255).astype(np.uint8)

def lisse(lv):
    """Bouche lissée (pas de clignotement), sur ~0,17 s quelle que soit la cadence (30 ou 60 images/s)."""
    n = max(2, int(round(FPS / 15)))
    k = np.hanning(2 * n + 3)[1:-1]; k = k / k.sum()
    return np.convolve(np.pad(lv, n, mode="edge"), k, "valid")

def controle_image(tetes):
    """Défauts visibles à un instant, d'après la position des têtes à l'écran : tête coupée par le bord, deux personnages l'un
    sur l'autre, sous-titre posé sur le visage de celui qui parle."""
    out = []
    for h in tetes:
        hors = max(0.0, -(h["x"] - h["rx"])) + max(0.0, h["x"] + h["rx"] - W)
        haut = max(0.0, -(h["y"] - h["ry"]))
        if (hors > 0.35 * h["rx"] or haut > 0.45 * h["ry"]) and -h["rx"] < h["x"] < W + h["rx"]:
            out.append(dict(t=h["t"], type="tete_coupee", role=h["role"], i=h["i"], plan=h["plan"]))
        if h["parle"] and h["sous_titre"] and h["y"] + 0.75 * h["ry"] > CAP_Y - 70 and h["y"] - h["ry"] < CAP_Y + 70:
            out.append(dict(t=h["t"], type="sous_titre_visage", role=h["role"], i=h["i"], plan=h["plan"]))
    for a in range(len(tetes)):
        for b in range(a + 1, len(tetes)):
            A_, B_ = tetes[a], tetes[b]
            if abs(A_["x"] - B_["x"]) < 0.9 * max(A_["rx"], B_["rx"]) and abs(A_["y"] - B_["y"]) < 1.5 * max(A_["ry"], B_["ry"]):
                out.append(dict(t=A_["t"], type="chevauchement", role=f"{A_['role']}+{B_['role']}", i=A_["i"], plan=A_["plan"]))
    return out

# ------------------------------------------------------------------ habillage
F_TIT = ImageFont.truetype(FB, 54)
def titre(txt):
    """Titre façon TikTok : texte noir gras dans un cadre blanc arrondi, centré en haut."""
    if not txt: return None
    txt = re.sub(r"\s+", " ", str(txt)).strip()[:60]
    d0 = ImageDraw.Draw(Image.new("RGB", (1, 1))); mots, lignes, cur = txt.split(), [], ""
    for m in mots:
        if d0.textlength((cur + " " + m).strip(), font=F_TIT) > 880: lignes.append(cur); cur = m
        else: cur = (cur + " " + m).strip()
    lignes.append(cur); lignes = lignes[:3]; hl = 70
    larg = int(max(d0.textlength(l, font=F_TIT) for l in lignes)) + 70
    img = Image.new("RGBA", (larg, hl * len(lignes) + 44), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, larg - 1, img.height - 1), 26, fill=(255, 255, 255, 245))
    for k, l in enumerate(lignes):
        w = d.textlength(l, font=F_TIT); d.text(((larg - w) / 2, 18 + k * hl), l, font=F_TIT, fill=(20, 20, 24))
    return np.array(img).astype(np.float32)

F_CARTE = ImageFont.truetype(FB, 104)
def carte(txt):
    """Carton plein écran entre deux scènes (« Deux heures plus tard… »)."""
    img = Image.new("RGB", (W, H), (255, 208, 40)); d = ImageDraw.Draw(img)
    for k in range(24):                                                    # rayons qui partent du centre
        a = k * math.pi / 12; d.polygon([(W / 2, H / 2), (W / 2 + 2400 * math.cos(a), H / 2 + 2400 * math.sin(a)),
                                         (W / 2 + 2400 * math.cos(a + 0.13), H / 2 + 2400 * math.sin(a + 0.13))], fill=(255, 196, 20))
    mots, lignes, cur = str(txt).upper().split(), [], ""
    for m in mots:
        if d.textlength((cur + " " + m).strip(), font=F_CARTE) > 920: lignes.append(cur); cur = m
        else: cur = (cur + " " + m).strip()
    lignes.append(cur); hl = 128; y0 = H / 2 - hl * len(lignes) / 2
    for k, l in enumerate(lignes):
        w = d.textlength(l, font=F_CARTE)
        d.text(((W - w) / 2, y0 + k * hl), l, font=F_CARTE, fill=(255, 255, 255), stroke_width=12, stroke_fill=(20, 20, 24))
    return np.array(img)

F_VO = ImageFont.truetype(FB, 84)
def carte_titre(txt):
    """Titre lu par la voix off au début : gros texte noir dans un cadre blanc, au centre de l'écran."""
    d0 = ImageDraw.Draw(Image.new("RGB", (1, 1))); mots, lignes, cur = str(txt).split(), [], ""
    for m in mots:
        if d0.textlength((cur + " " + m).strip(), font=F_VO) > 860: lignes.append(cur); cur = m
        else: cur = (cur + " " + m).strip()
    lignes.append(cur); lignes = lignes[:4]; hl = 104
    larg = int(max(d0.textlength(l, font=F_VO) for l in lignes)) + 90
    img = Image.new("RGBA", (larg, hl * len(lignes) + 60), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, larg - 1, img.height - 1), 34, fill=(255, 255, 255, 250), outline=(20, 20, 24, 255), width=6)
    for k, l in enumerate(lignes):
        w = d.textlength(l, font=F_VO); d.text(((larg - w) / 2, 26 + k * hl), l, font=F_VO, fill=(20, 20, 24))
    return np.array(img).astype(np.float32)

def decor_uni(k):
    img = np.zeros((H, W, 3), np.uint8); img[:] = PASTELS[k % len(PASTELS)]; return img

def _pluie(img, tm, t0, graine):
    """Pluie de billets (effet « pluie_billets »)."""
    rng = np.random.default_rng(graine); n = 26; dt = tm - t0
    for k in range(n):
        x = rng.uniform(40, W - 40); v = rng.uniform(380, 650); y = -120 + (dt - rng.uniform(0, 1.2)) * v
        if not -150 < y < H + 50: continue
        a = rng.uniform(0, 6.28) + dt * rng.uniform(-3, 3); c, s_ = math.cos(a), math.sin(a)
        pts = np.array([[x + c * dx - s_ * dy, y + s_ * dx + c * dy] for dx, dy in ((-46, -24), (46, -24), (46, 24), (-46, 24))], np.int32)
        cv2.fillPoly(img, [pts], M.TRAIT, cv2.LINE_AA); cv2.fillPoly(img, [((pts - [x, y]) * 0.82 + [x, y]).astype(np.int32)], (150, 210, 140), cv2.LINE_AA)

# ------------------------------------------------------------------ redessin partiel (2e version du jury)
def _sig(x):
    """Empreinte courte d'un élément (plan, réplique, réglages) : sert à savoir si une image change d'une version à l'autre."""
    import hashlib, json
    def norm(v):
        if isinstance(v, np.ndarray): return "nd:" + hashlib.md5(np.ascontiguousarray(v).tobytes()).hexdigest()
        if isinstance(v, dict): return {str(k): norm(w) for k, w in sorted(v.items(), key=lambda kv: str(kv[0]))}
        if isinstance(v, (list, tuple)): return [norm(w) for w in v]
        if isinstance(v, (np.integer, np.floating)): return v.item()
        return v if isinstance(v, (int, float, str, bool, type(None))) else str(v)
    return hashlib.md5(json.dumps(norm(x), sort_keys=True).encode()).hexdigest()[:16]


def images_a_refaire(ancien, neuf, nf, fps, marge=1.0):
    """Images de la nouvelle version qui diffèrent de l'ancienne : celles dont un plan ou une réplique proche (± marge s) a changé.
    None = tout est à refaire (réglages généraux, durée ou cadence différents)."""
    if not ancien or ancien.get("sig_global") != neuf.get("sig_global") or ancien.get("nf") != nf or ancien.get("fps") != fps: return None
    def autour(liste, t): return tuple(sig for a, b, sig in liste if a - marge <= t <= b + marge)
    refaire = []
    for fi in range(nf):
        t = fi / fps
        if autour(ancien["sig_plans"], t) != autour(neuf["sig_plans"], t) or autour(ancien["sig_ph"], t) != autour(neuf["sig_ph"], t): refaire.append(fi)
    return refaire


def _images_cles(video, fps):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey", "-show_entries", "frame=pts_time",
                        "-of", "csv=p=0", video], capture_output=True, text=True, timeout=300)
    return sorted({int(round(float(x) * fps)) for x in re.findall(r"\d+(?:\.\d+)?", r.stdout)})


def plages(refaire, cles, nf):
    """Morceaux à redessiner, élargis aux images clés de l'ancienne vidéo (pour recoller sans réencoder le reste)."""
    if not refaire: return []
    cles = [c for c in cles if 0 <= c <= nf] + [nf]
    out = []
    for fi in refaire:
        a = max([c for c in cles if c <= fi] or [0]); b = min(c for c in cles if c > fi)
        if out and a <= out[-1][1]: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return [tuple(x) for x in out]


# ------------------------------------------------------------------ rendu
class TempsDepasse(RuntimeError):
    """La 2e version du jury n'aurait pas le temps de finir avant la limite de GitHub : on garde la 1re."""


def rendre(sk, sortie, audios, mots=None, decors=None, mini=False, apercu=False, reprise=None, limite=None):
    tmp = tempfile.mkdtemp(); reps = sk["repliques"]; decors = decors or {}; rng = np.random.default_rng(11)
    roles = sorted({r["p"] for r in reps if r["p"] != "narrateur"}, key=lambda r: [x["p"] for x in reps].index(r))   # la voix off n'est pas dessinée
    # scènes : découpage de l'auteur (sinon une seule scène)
    studio.separer_lieux(sk)                                               # personnages dans des lieux différents : un décor chacun
    SEPARES = bool(sk.get("_separes"))
    dec = [sc for sc in (sk.get("decoupage") or []) if sc.get("repliques")]
    scene_de = {}
    for k, sc in enumerate(dec):
        for i in sc["repliques"]: scene_de.setdefault(i, k)
    # chronologie
    teaser = reps[0].get("teaser") if reps else None                       # accroche choc : réplique rejouée en ouverture
    if teaser is not None: scene_de[0] = scene_de.get(teaser, 0)
    for i, r in enumerate(reps):                                           # la voix off prend la scène de la réplique qui suit
        if r["p"] == "narrateur" and i not in scene_de:
            scene_de[i] = next((scene_de[j] for j in range(i + 1, len(reps)) if j in scene_de), 0)
    t = 0.15; ph = []; transitions = []                                 # (début, fin, type, scène d'arrivée, texte du carton)
    DOUB = sk.get("doublage") or None                                      # vidéo construite sur la bande son d'une autre vidéo : minutage imposé
    rms = [float(np.sqrt(np.mean(np.square(a)))) if len(a) else 0.0 for a in audios]; rms_ref = float(np.median([x for x in rms if x > 0] or [1.0]))
    TON = {}                                                               # intonation de chaque réplique (hauteur relative à la voix du personnage)
    if DETAIL:
        f0s = [studio.prosodie(a)[0] if len(a) else np.zeros(1, np.float32) for a in audios]
        for role in {r["p"] for r in reps}:
            v = np.concatenate([f0s[i][f0s[i] > 0] for i, r in enumerate(reps) if r["p"] == role and i < len(f0s)] or [np.zeros(0)])
            ref = float(np.median(v)) if len(v) > 10 else None
            if ref: sk.setdefault("_voix_hz", {})[role] = round(ref)       # le casting devine homme / femme d'après la voix
            vote = {"h": 0.0, "f": 0.0}                                    # vote réplique par réplique (un cri d'homme monte vers 200 Hz)
            for i, r in enumerate(reps):
                if r["p"] != role or i >= len(f0s): continue
                v_ = f0s[i][f0s[i] > 0]
                if len(v_) < 8: continue
                m_ = float(np.percentile(v_, 35))
                if m_ < 165: vote["h"] += len(v_)
                elif m_ > 220: vote["f"] += len(v_)
            if sum(vote.values()) and max(vote.values()) >= 0.7 * sum(vote.values()):
                sk.setdefault("_voix_genre", {})[role] = max(vote, key=vote.get)
            for i, r in enumerate(reps):
                if r["p"] == role and i < len(f0s): TON[i] = studio.intonation(f0s[i], ref)
    def emo_de(i, r):
        e = emotion(r.get("d"))
        if DETAIL and e == "neutre" and not re.search(r"\[[^\]]+\]", r.get("d") or ""):     # pas d'indication de jeu : on devine
            e = studio.emotion_texte(r["t"], min(1.0, rms[i] / (2 * rms_ref + 1e-9)) if i < len(rms) else 0.5, TON.get(i, (None, None))[1])
        return e
    for i, (r, a) in enumerate(zip(reps, audios)):
        niv, lv = enveloppe(a); dur = len(a) / SR; att = float(r.get("attente", 0))
        if DOUB:                                                           # chaque réplique démarre à l'instant exact où elle est dite
            t = float(r["_deb"]); lv = lisse(lv)
            sc = scene_de.get(i, ph[-1]["scene"] if ph else 0)
            if ph and sc != ph[-1]["scene"] and not SEPARES:               # changement de scène : panoramique dans le blanc entre deux répliques
                d0 = max(ph[-1]["fin"] + 0.05, t - 0.45)
                if t - d0 >= 0.2: transitions.append((d0, t - 0.02, "panoramique", sc, ""))
            emo_q = emo_de(i, r)
            rires = any(re.search(r"laugh|rire|giggl|chuckl", str(e_[2])) and e_[0] < t + dur + 0.6 and e_[1] > t for e_ in (DOUB.get("evenements") or []))
            ph.append(dict(i=i, p=r["p"], deb=t, fin=t + dur, lv=lv, emo=emo_q, chute=bool(r.get("chute")) or i == len(reps) - 1, rires=rires,
                           scene=sc, objet=r.get("objet"), teaser=False, texte=r["t"], geste=geste_texte(r["t"], emo_q, i),
                           groupes=minutage(r["t"], a, t, (mots or [None] * len(reps))[i])))
            ph[-1]["lev"] = levres.chronologie(ph[-1]["groupes"], (mots or [None] * len(reps))[i], t)   # lèvres calées sur chaque son
            continue
        if i == len(reps) - 1 and not att and i: att = 0.45                # un temps avant la chute finale
        t += att
        lv = lisse(lv)         # bouche lissée : pas de clignotement
        sc = scene_de.get(i, ph[-1]["scene"] if ph else 0)
        if ph and ph[-1].get("teaser"):                                     # après l'accroche : retour au début de l'histoire
            transitions.append((t, t + 0.9, "carton", sc, "Un peu plus tôt…")); t += 0.9
        elif ph and sc != ph[-1]["scene"] and SEPARES: pass                # lieux séparés : coupe franche de l'un à l'autre
        elif ph and sc != ph[-1]["scene"]:                                 # changement de scène : carton ou panoramique rapide
            # vidéo longue : chaque nouveau gag est TOUJOURS annoncé par un carton plein écran (« Plus tard… » par défaut)
            d_tr = 0.45 if mini else 1.35
            transitions.append((t, t + d_tr, "panoramique" if mini else "carton", sc,
                                (dec[sc].get("titre") if sc < len(dec) else "") or "Plus tard…")); t += d_tr
        elif ph and r.get("chevauche") and ph[-1]["p"] != r["p"]:          # coupe la parole : démarre par-dessus la fin de l'autre
            t = max(ph[-1]["deb"] + 0.45, ph[-1]["fin"] - 0.35)
        emo_q = emo_de(i, r)
        q = dict(i=i, p=r["p"], deb=t, fin=t + dur, lv=lv, emo=emo_q, chute=(bool(r.get("chute")) or i == len(reps) - 1) and not r.get("teaser"),
                 scene=sc, objet=r.get("objet"), teaser=r.get("teaser") is not None, texte=r["t"], geste=geste_texte(r["t"], emo_q, i),
                 groupes=minutage(r["t"], a, t, (mots or [None] * len(reps))[i]))
        q["lev"] = levres.chronologie(q["groupes"], (mots or [None] * len(reps))[i], t)
        ph.append(q)
        vif = emo_q in ("cri", "colere", "panique")                         # dispute : les répliques s'enchaînent sans blanc
        t += dur + (0.5 if q["chute"] and i < len(reps) - 1 else 0.05 if (vif or r["p"] == "narrateur") else 0.16)
    FIN = ph[-1]["fin"]
    GEL = FIN + 1.15                                                       # arrêt sur image après la réaction finale
    if DOUB: GEL = max(GEL, min(float(DOUB.get("duree") or 0), FIN + 4.0))   # la bande son continue (musique) : on la laisse finir
    total = GEL + 1.1
    FIN_CARTE = None
    if DOUB:                                                               # pas d'allongement artificiel : signature puis fin
        FIN_CARTE = total; total += 1.3
    elif not mini and total < 61.5:                                          # vidéo longue : plus d'une minute (rémunération TikTok)
        FIN_CARTE = total; total = 61.5
    elif mini:                                                             # gag éclair : signature de la chaîne (1,3 s)
        FIN_CARTE = total; total += 1.3
    MINUTAGE[:] = [(q["deb"], q["fin"], q["texte"], {"presentateur": "Jojo", "invite": "Kévin", "envoyee": "Lila"}.get(q["p"], "voix off"))
                   for q in ph if not q["teaser"] and q["p"] != "narrateur"]
    PH[:] = ph
    if (os.environ.get("APERCU_RAPIDE") or "") == "1":                     # aperçu rapide : les 10 premières secondes seulement
        total = min(total, 10.0); FIN_CARTE = None
    nf = int(total * FPS)
    # placement : qui est dans chaque scène, à quelle place
    places = {}
    for q in ph: places.setdefault(q["scene"], [])
    for q in ph:
        if q["p"] != "narrateur" and q["p"] not in places[q["scene"]]: places[q["scene"]].append(q["p"])
    for k in places: places[k].sort(key=roles.index)                     # chacun garde son côté d'une scène à l'autre
    COMP = {}                                                              # personnages muets voulus par l'histoire, par scène (bible)
    def position(scene, role):
        ps = places[scene] + [f"@{j}" for j in range(len(COMP.get(scene, [])))]; n = len(ps); k = ps.index(role) if role in ps else 0
        if n == 1: return (540, 1500, 1.35)
        if n == 2: return ((285, 795)[k], 1500, 1.08)
        return ((190, 540, 890)[min(k, 2)], 1500, 0.86)
    # caméra : plan large au début de chaque scène, puis plans serrés alternés sur celui qui parle (comme sur TikTok)
    for j, q in enumerate(ph):
        nouvelle = j == 0 or ph[j - 1]["scene"] != q["scene"]
        q["cam"] = "large" if (nouvelle or q["p"] == "narrateur" or len(places[q["scene"]]) <= 1 or q["chute"] and j == len(ph) - 1
                               or (j and ph[j - 1]["p"] == "narrateur")) else "serre"
    # studio : bible de l'épisode et storyboard (plans, mouvements, réactions), décors dessinés là où l'IA n'en a pas fourni
    B = studio.bible(sk, roles) if DETAIL else None
    AVANT, INFOS = {}, {}; FICHES = None; DECOUPE = []; ERREURS_ANIM = []; SC_COURANT = [0]; TETES_Y = {}
    PROF = {}                                                              # décors IA : profondeur (le premier plan glisse plus vite que le fond)
    if B and PARALLAXE:
        try:
            import decors as DEC_
            for sc_, im_ in list(decors.items()):
                pr_ = DEC_.PROFONDEURS.get(sc_)
                if pr_ is None:                                            # pas de carte : le bas de l'image (sol) est plus près
                    pr_ = np.repeat(np.clip((np.arange(H, dtype=np.float32) / H - 0.35) / 0.65, 0, 1)[:, None] * 255, W, 1)
                PROF[sc_] = cv2.resize(np.asarray(pr_, np.float32) / 255.0, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        except Exception as e: print(f"profondeur des décors indisponible : {e}", flush=True)
    if B:                                                                  # panneaux vidés des décors IA : un vrai gag écrit, lisible
        try:
            import decors as DEC_
            gags_ = [g for g in (B.get("gags") or []) if g] or ["Home sweet home", "Ici, on ne juge pas", "Wifi : demande à maman"]
            k_g = 0
            for sc_, rects in DEC_.PANNEAUX.items():
                if sc_ not in decors: continue
                im_ = Image.fromarray(decors[sc_]); dr = ImageDraw.Draw(im_)
                for (x_, y_, w_, h_) in rects:
                    txt = str(gags_[k_g % len(gags_)]); k_g += 1
                    for taille in range(int(h_ * 0.42), 12, -2):           # plus grande taille qui tient dans le panneau
                        f_ = ImageFont.truetype(FB, taille); mots = txt.split(); lignes, cur = [], ""
                        for m_ in mots:
                            essai = (cur + " " + m_).strip()
                            if dr.textlength(essai, font=f_) <= w_ * 0.9: cur = essai
                            else: lignes.append(cur); cur = m_
                        lignes.append(cur)
                        if len(lignes) * taille * 1.15 <= h_ * 0.85 and all(dr.textlength(l_, font=f_) <= w_ * 0.92 for l_ in lignes): break
                    y0_ = y_ + (h_ - len(lignes) * taille * 1.15) / 2
                    for j_, l_ in enumerate(lignes):
                        dr.text((x_ + (w_ - dr.textlength(l_, font=f_)) / 2, y0_ + j_ * taille * 1.15), l_, font=f_, fill=(40, 34, 44))
                decors[sc_] = np.array(im_)
        except Exception as e: print(f"gags des panneaux impossibles : {e}", flush=True)
    GRILLE = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)[::-1] * 4 + 2  # (x, y) au quart de la résolution
    VOIT = {}                                                              # objets de l'histoire en grand dans le décor (voiture garée)
    PASSE = {}                                                             # décor vivant : voiture qui passe au loin
    if B:
        studio.realiser(ph, places, B); sk["_bible"] = B
        DECOUPE = studio.decouper(ph, places, B, FPS) if os.environ.get("MONTAGE", "dynamique") != "simple" else []   # plusieurs plans par réplique
        if DECOUPE: print(f"montage : {len(DECOUPE)} plans (" + " ".join(f"{x['t0']:.1f}:{x['plan']}>{x['cible'][:3]}/{x['passage']}" for x in DECOUPE) + ")", flush=True)
        FICHES = B.get("fiches") if HUMAINS else None
        for sc_ in places:
            lieu = B["lieux"][min(sc_, len(B["lieux"]) - 1)]
            dd = DD.dessiner(lieu, B, graine=B["graine"] % 9973 + sc_ + int(os.environ.get("DECOR_GRAINE") or 0))   # « juste le décor » : tirage neuf
            if dd.get("avant") is not None: AVANT[sc_] = dd["avant"]          # premier plan (comptoir, bureau, guichet) : aussi devant un décor IA
            if sc_ in decors: continue                                     # décor IA (mode payant) : gardé tel quel
            decors[sc_] = dd["fond"]; INFOS[sc_] = dd
        try:
            import vehicules as VH
            for sc_ in places:
                lieu_ = B["lieux"][min(sc_, len(B["lieux"]) - 1)]
                tx_ = " ".join(r["t"] for r in reps).lower()
                if lieu_ in ("rue",) and re.search(r"\b(voiture|caisse|bagnole|berline|parking|4x4|monte dedans|monte dans)\b", tx_):
                    qui_ = [r2 for r2 in places[sc_] if r2 != "narrateur"]
                    xr_ = position(sc_, qui_[0])[0] if qui_ else W / 2
                    l_ = 820; im_ = VH.voiture(VH.couleur_du_texte(tx_), 1 if xr_ > W / 2 else -1, l_)
                    X0 = (W * 0.06 if xr_ > W / 2 else W * 0.94 - im_.shape[1]); Y0 = 1335 - VH.sol(l_)   # garée derrière, de l'autre côté
                    VOIT[sc_] = (im_, X0, Y0)
            if VOIT: print(f"objets de l'histoire : voiture garée dans {len(VOIT)} décor(s)", flush=True)
            for sc_ in places:                                             # décor vivant : une voiture passe au loin de temps en temps
                if B["lieux"][min(sc_, len(B["lieux"]) - 1)] == "rue" and DECOR_VIVANT:
                    col_ = [(200, 50, 50), (60, 100, 190), (240, 200, 60), (235, 235, 238)][sc_ % 4]
                    PASSE[sc_] = (VH.voiture(col_, 1, 340), VH.voiture(col_, -1, 340), VH.sol(340))
        except Exception as e: print(f"voiture impossible : {e}", flush=True)
        print(f"studio : {B['moment']}, lieux {B['lieux']}, tenues " + ", ".join(f"{r}={c['haut']}" for r, c in B["costumes"].items())
              + f", {len(B['figurants'])} figurant(s), ambiances {B['ambiances']} ; plans " + " ".join(f"{q['plan']}/{q['mouvement']}" for q in ph), flush=True)
        GRADE = None                                                       # étalonnage (teinte de l'heure) × vignettage, calculé une fois
        yy_, xx_ = np.mgrid[0:H, 0:W].astype(np.float32)
        vig = 1 - 0.20 * np.clip(((xx_ - W / 2) / (W * 0.75)) ** 2 + ((yy_ - H * 0.48) / (H * 0.62)) ** 2, 0, 1)
        teinte = np.array(B["etalonnage"], np.float32); teinte = teinte / teinte.max()
        GRADE = np.clip(vig[..., None] * teinte[None, None, :] * 255, 0, 255).astype(np.uint8); del yy_, xx_, vig   # multiplicateur (÷255)
        SILENCES = []                                                      # regard caméra pendant un silence gênant (celui qui vient d'écouter)
        for j, q in enumerate(ph):
            if j and q.get("regard_camera") and ph[j - 1]["p"] != "narrateur":
                qui = next((r2 for r2 in places.get(ph[j - 1]["scene"], []) if r2 != ph[j - 1]["p"]), None)
                if qui: SILENCES.append((ph[j - 1]["fin"] + 0.1, q["deb"] - 0.05, qui, ph[j - 1]["scene"]))
        for sc_ in places:                                                 # figurants dans les espaces libres entre les personnages
            libres = {1: [170, 910], 2: [540, 1010], 3: [365, 715]}.get(len(places[sc_]), [540]); k_ = 0
            for f_ in B["figurants"]:
                if f_["scene"] != sc_ or f_.get("compagnon"): continue
                f_["_x"] = libres[k_ % len(libres)]; f_["_s"] = 0.4 if len(places[sc_]) >= 3 else 0.46; k_ += 1
        for f_ in B["figurants"]:                                          # compagnons : à côté du personnage, à sa taille
            if f_.get("compagnon") and f_["scene"] in places: COMP.setdefault(f_["scene"], []).append(f_)
        for sc_, l_ in COMP.items():
            for j_, f_ in enumerate(l_):
                f_["_x"], f_["_y"], f_["_s"] = position(sc_, f"@{j_}"); f_["_s"] *= 0.95
        rng_p = np.random.default_rng(B["graine"] % 99991)
        PARTICULES = rng_p.uniform(0, 1, (60, 4))                          # positions et vitesses (poussière, pluie, neige, vapeur)
    # animation des personnages : état par rôle
    clign = {r: sorted(rng.uniform(0.5, total, int(total / 2.6))) for r in roles}
    DEBUT_SCENE = {}
    for q in ph: DEBUT_SCENE.setdefault(q["scene"], q["deb"] - 0.1)
    COUVERTURE_MS[0] = int(max(0.5, ph[-1]["deb"] + 0.4) * 1000)           # image de couverture TikTok : la chute finale
    SANS_ENTREE = {ph[0]["scene"]}                                         # 1re scène : déjà là dès la première image (l'accroche compte)
    # appel (lieux séparés) : écran partagé sur une réplique sur trois, plan d'écoute (on voit celui qui écoute, la voix sort
    # du téléphone) sur la fin des longues répliques (idées 16 et 21)
    APPEL = []                                                             # (t0, t1, "partage" | "ecoute", scène de l'autre)
    sc_parl = sorted({z2["scene"] for z2 in ph if z2["p"] != "narrateur"})
    if SEPARES and APPEL_ON and len(sc_parl) >= 2:
        for j, q in enumerate(ph):
            if q["p"] == "narrateur" or j == 0 or q is ph[-1]: continue
            autre_sc = next((s_ for s_ in sc_parl if s_ != q["scene"]), None)
            if autre_sc is None: continue
            d_ = q["fin"] - q["deb"]
            deja = all(DEBUT_SCENE.get(s_, 1e9) < q["deb"] - 0.9 for s_ in (q["scene"], autre_sc))   # les deux sont déjà en scène
            if j % 3 == 1 and d_ >= 0.8 and deja: APPEL.append((q["deb"] - 0.05, q["fin"] + 0.1, "partage", autre_sc))
            elif j % 3 == 2 and d_ >= 2.2 and deja: APPEL.append((q["deb"] + 0.55 * d_, q["fin"], "ecoute", autre_sc))
        if APPEL: print(f"appel : {sum(a[2] == 'partage' for a in APPEL)} écran(s) partagé(s), {sum(a[2] == 'ecoute' for a in APPEL)} plan(s) d'écoute", flush=True)
    SC_HAUT = sc_parl[0] if sc_parl else 0
    # rembobinage (idée 22) : « revenons 5 minutes avant », « deux heures plus tôt »… → l'image repart en arrière façon cassette
    REMB = []
    for j, q in enumerate(ph):
        if j and REMB_ON and re.search(r"revenons|retour en arri[èe]re|rembobin|flash-?back|(minutes?|heures?|jours?|semaines?|mois|ans?) (plus t[ôo]t|avant)\b|la veille|hier soir,", reps[q["i"]]["t"].lower()):
            t0_ = q["fin"] + 0.02; REMB.append((t0_, t0_ + 0.85, max(0.0, ph[max(0, j - 3)]["deb"] + 0.2)))   # on remonte 3 répliques
    if REMB: print(f"rembobinage : {len(REMB)} fois", flush=True)
    TITRE_FIXE = titre(sk.get("titre_accroche")) if not mini else None
    FILIGRANE = marque.filigrane(52)
    TRAITS_VITESSE = []                                                    # traits de vitesse (manga) : du bord vers le centre
    for k_t in range(2):
        tv = np.zeros((H, W, 3), np.uint8); rg_t = np.random.default_rng(40 + k_t)
        for _ in range(70):
            a_t = rg_t.uniform(0, 2 * math.pi); r0 = rg_t.uniform(0.62, 0.8) * H * 0.55; r1 = H * 0.75
            p0 = (int(W / 2 + math.cos(a_t) * r0), int(H * 0.42 + math.sin(a_t) * r0)); p1 = (int(W / 2 + math.cos(a_t) * r1), int(H * 0.42 + math.sin(a_t) * r1))
            cv2.line(tv, p0, p1, (235, 235, 235), int(rg_t.integers(2, 6)), cv2.LINE_AA)
        TRAITS_VITESSE.append(tv)
    TITRES = {k: titre(sc.get("titre")) for k, sc in enumerate(dec) if sc.get("titre")}
    VOIX_OFF = {q["i"]: carte_titre(reps[q["i"]]["t"]) for q in ph if q["p"] == "narrateur"}
    objets = {}
    print(f"cartoon : durée {total:.1f} s, {len(ph)} répliques, {len(places)} scène(s), personnages {roles}", flush=True)

    def actif(tm):
        return next((x for x in reversed(ph) if x["deb"] - 0.25 <= tm), ph[0])

    ASSIS = (B or {}).get("assis") or {}
    GESTES_ORIG = []                                                       # P4 : instants des gestes dans la vidéo d'origine (tenus 2 s au moins)
    for t_ in sorted((B or {}).get("gestes_origine") or []):
        if not GESTES_ORIG or t_ - GESTES_ORIG[-1] >= 2.0: GESTES_ORIG.append(t_)
    CINE = dict((B or {}).get("cine") or {})                               # effets « cinéma » de l'épisode (varient d'une vidéo à l'autre)
    CINE.update(focus=False, profondeur=False)                             # image toujours nette : aucun flou de mise au point ni de premier plan
    TEINTES = {"cri": (1.07, 0.97, 0.94), "colere": (1.07, 0.97, 0.94), "pleurs": (0.94, 0.98, 1.07), "triste": (0.94, 0.98, 1.07),
               "soupir": (0.97, 0.99, 1.04), "joie": (1.05, 1.03, 0.95), "rire": (1.04, 1.02, 0.96), "amour": (1.06, 1.0, 1.0),
               "choc": (0.97, 0.98, 1.04), "panique": (0.96, 1.0, 1.05)}
    GRAIN = []
    if CINE.get("grain"):                                                  # grain de film très léger (3 trames qui alternent)
        rg_ = np.random.default_rng(3)
        GRAIN = [np.clip(rg_.normal(4, 2.2, (H, W, 1)), 0, 9).astype(np.uint8).repeat(3, 2) for _ in range(3)]
    yy_, xx_ = np.mgrid[0:H, 0:W].astype(np.float32)
    REFLET = (np.exp(-(((xx_ + 80) / 520) ** 2 + ((yy_ - H * 0.35) / 900) ** 2))[..., None] * np.array([70, 45, 15], np.float32)) if CINE.get("reflets") else None
    del yy_, xx_
    AVANT_FLOU = {}
    if CINE.get("profondeur") and B:                                       # 3e couche : une plante floue au tout premier plan (plans serrés)
        import decor_details as DX
        for sc_ in places:
            c_ = np.zeros((H, W, 3), np.uint8); c_[:] = (1, 2, 3); g_ = np.random.default_rng(B["graine"] + sc_)
            DX.plante_haute(c_, (60 if g_.random() < 0.5 else W - 60), H + 60, 1.6)
            m_ = (np.abs(c_.astype(np.int16) - (1, 2, 3)).sum(2) > 9).astype(np.float32)
            AVANT_FLOU[sc_] = (cv2.GaussianBlur(c_, (0, 0), 9), cv2.GaussianBlur(m_, (0, 0), 9)[..., None])

    def teinte_lut(t3):
        r_, v_, b_ = t3; a_ = np.arange(256, dtype=np.float32)
        return np.clip(np.stack([a_ * r_, a_ * v_, a_ * b_], 1), 0, 255).astype(np.uint8)[:, None, :]
    T_REAC, OBJ_DUO = {}, {}

    def t_reaction(q):
        """Instant où celui qui écoute réagit : 0,2 s après le mot le plus appuyé de la réplique (et pas au hasard)."""
        if q["i"] not in T_REAC:
            lv = np.asarray(q["lv"], np.float32); n_ = max(4, int(len(lv) * 0.85))
            k_ = int(np.argmax(np.diff(lv[:n_]))) if len(lv) > 4 else 0
            T_REAC[q["i"]] = float(np.clip(q["deb"] + k_ / FPS + 0.2, q["deb"] + 0.25, max(q["deb"] + 0.25, q["fin"] - 0.1)))
        return T_REAC[q["i"]]

    def _sq(role, xo, yo, so):
        t_ = FICHES[role]["taille"] if FICHES and role in FICHES else 1.0
        return M.squelette(dict(M.pose_neutre(), x=xo, y=yo, s=so * t_, adulte=bool(FICHES), t=0.0))

    def duo(p, role, tm, q, scene, parle):
        """Gestes à deux : le personnage s'approche et sa main atteint vraiment l'autre (épaule, main levée, objet, poitrine)."""
        if q["p"] == "narrateur" or len(places[scene]) < 2 or q["scene"] != scene: return
        nom = q.get("duo", "?")
        if nom == "?": nom = q["duo"] = studio.geste_duo(q.get("texte", ""))
        if not nom: return
        autre = next((r2 for r2 in places[scene] if r2 != q["p"]), None) if parle else q["p"]
        if not autre or (not parle and role != next((r2 for r2 in places[scene] if r2 != q["p"]), None)): return
        u = _ressort((tm - q["deb"] - 0.15) / 0.5) * (1 - _ease((tm - q["fin"] - 0.25) / 0.35))
        if u <= 0.01: return
        x0, y0, s0 = position(scene, role); xo, yo, so = position(scene, autre); sens = 1 if xo > x0 else -1
        t_ = FICHES[role]["taille"] if FICHES and role in FICHES else 1.0; seff = s0 * t_
        portee = 230 * seff; ecart = abs(xo - x0)
        symetrique = nom in ("tope", "donne")
        if parle or symetrique:                                            # il s'approche (à deux pour « tope » et « donner »)
            app = max(0.0, ecart - portee) * (0.5 if symetrique else 1.0) * min(1.0, u)
            p["x"] += sens * app
        app_o = max(0.0, ecart - portee) * (0.5 if symetrique else (1.0 if not parle else 0.0)) * min(1.0, u)
        xo_eff = xo - sens * app_o if (symetrique or not parle) else xo
        K = M.squelette(dict(p, adulte=bool(FICHES), s=p["s"] * t_)); Ko = _sq(autre, xo_eff, yo, so)
        i_b = 1 if sens > 0 else 0; nom_b = "bras_d" if sens > 0 else "bras_g"; L_ = 92 if FICHES else 64
        epaule = K["bras"][i_b][0]
        if nom == "epaule":
            if not parle: return
            cible = Ko["bras"][0 if sens > 0 else 1][0]; forme = "ouverte"
        elif nom == "pousse":
            if not parle:
                p["x"] -= sens * 30 * s0 * u; p["tilt"] -= sens * 6 * u; return   # celui qui se fait pousser recule
            cible = (Ko["x"] - sens * Ko["corps_w"] * 0.7, Ko["cy_corps"] - Ko["corps_h"] * 0.1); forme = "paume"
        else:                                                              # tope / donner : les deux mains se rejoignent entre eux
            Ka = M.squelette(dict(M.pose_neutre(), x=x0 + sens * (max(0.0, ecart - portee) * 0.5 * min(1.0, u)), y=y0, s=seff, adulte=bool(FICHES), t=0.0))
            mid_x = (Ka["bras"][1 if sens > 0 else 0][0][0] + Ko["bras"][0 if sens > 0 else 1][0][0]) / 2
            cible = (mid_x, (Ka["tete"][1] - Ka["ry"] * 0.6) if nom == "tope" else (Ka["cy_corps"] - Ka["corps_h"] * 0.05)); forme = "paume" if nom == "tope" else "poing"
        a_ = M.ik(epaule, cible, L_, K["s"], coude_bas=True)
        cur = p[nom_b]; p[nom_b] = (cur[0] + (a_[0] - cur[0]) * min(1.0, u), cur[1] + (a_[1] - cur[1]) * min(1.0, u))
        p["main_forme_" + ("d" if sens > 0 else "g")] = forme
        if nom == "donne":                                                 # l'objet passe de main en main
            o = OBJ_DUO.get(round(s0, 2))
            if o is None: o = OBJ_DUO[round(s0, 2)] = M.objet("cadeau", s0 * (0.5 if FICHES else 1.0))
            donne = (tm - q["deb"]) / max(0.3, q["fin"] - q["deb"]) < 0.65
            if (parle and donne) or (not parle and not donne): p["main_" + ("d" if sens > 0 else "g")] = o

    def pose(role, tm, q, scene):
        p = M.pose_neutre(); x, y, s = position(scene, role); p.update(x=x, y=y, s=s, t=tm)
        z_parle = next((z for z in ph if z["p"] == role and z["scene"] == scene and z["deb"] <= tm <= z["fin"]), None)
        parle = z_parle is not None                                         # deux personnages peuvent parler en même temps
        if parle: q = z_parle
        mien = next((z for z in reversed(ph) if z["p"] == role and z["deb"] - 0.25 <= tm and z["scene"] == scene), None)
        emo = mien["emo"] if (mien and tm <= mien["fin"] + 0.6) else "neutre"
        # entrée et sortie en douceur de l'émotion (bras) : pas de saut d'une pose à l'autre
        u_emo = min(_ease((tm - mien["deb"] + 0.15) / 0.35), 1 - _ease((tm - mien["fin"] - 0.25) / 0.4)) if mien else 0.0
        # réaction de celui qui écoute après une chute de l'autre
        prev = next((z for z in reversed(ph) if z["fin"] <= tm and z["p"] != role), None)
        if not parle and prev and prev["chute"] and tm - prev["fin"] < 1.0 and (not mien or mien["fin"] < prev["deb"]):
            emo = "choc" if (prev["i"] * 7 + len(role)) % 3 else "rire"
        # celui qui écoute réagit à l'émotion de celui qui parle, juste après le mot qui frappe
        recule = 0.0; t_r = t_reaction(q)
        if not parle and q["p"] != role and q["p"] in places[scene] and t_r <= tm <= q["fin"] + 0.4 and emo == "neutre":
            if q["emo"] in ("cri", "colere"): emo = "panique" if (len(role) + q["i"]) % 2 else "choc"; recule = 1.0
            elif q["emo"] == "pleurs": emo = "blase"
            elif q["emo"] in ("rire", "joie") and (len(role) + q["i"]) % 2: emo = "rire"
        # storyboard : réaction prévue pour celui qui écoute, regard caméra pendant un silence gênant
        reac_geste, cam_regard, roule = None, False, False
        if B and not parle and emo == "neutre":
            if any(a_ <= tm <= b_ and qui == role and sc2 == scene for a_, b_, qui, sc2 in SILENCES): cam_regard, emo = True, "blase"
            elif q["p"] != role and q["p"] in places[scene] and q.get("reaction", "aucune") != "aucune" and t_r + 0.05 <= tm <= q["fin"] + 0.5:
                rc = q["reaction"]
                if rc == "regard_camera": cam_regard, emo = True, "blase"
                elif rc == "yeux_au_ciel": roule = True
                elif rc in ("facepalm", "bras_croises"): reac_geste = "facepalm" if rc == "facepalm" else "croises"
                elif rc in ("sceptique", "choc", "rire", "gene", "soupir"): emo = rc
        yeux, sour, forme, bg, bd, eff, roug, trem = STYLE.get(emo, STYLE["neutre"])
        p.update(yeux=yeux, sourcils=sour, forme=forme, effets=eff, rougeur=roug, tremble=trem, joues=emo in ("rire", "joie"))
        if B:                                                              # rendu détaillé : costume, lumière, visage, mains
            p.update(costume=B["costumes"].get(role), reflets=True, lumiere=B["lumiere"], ombre=B["ombre"], mains=True,
                     balance=0.7 * math.sin(tm * 2.3 + len(role)) + (0.5 * math.sin(tm * 9) if emo in ("rire", "joie", "cri") else 0))
            p.update(DETAILS_EMO.get(emo, {})); p.update(EXPRESSIF.get(emo, {}))
            if p.get("penche"):                                            # on se penche vers l'autre (ou on recule, si négatif)
                autre_ = q["p"] if q["p"] != role else next((r2 for r2 in places[scene] if r2 != role), None)
                if autre_ in places[scene]: p["penche"] *= 1 if position(scene, autre_)[0] > x else -1
            if emo == "blase" and not parle: p["pied"] = abs(math.sin(tm * 5.5))   # il tape du pied, impatient
            if roule: p.update(yeux="roule", sourcils="neutre", forme="moue")
            if TOON:                                                       # idée 13 : le teint change peu à peu pendant la réplique
                u_t = float(np.clip((tm - q["deb"] + 0.2) / 2.2, 0, 1))
                if emo in ("colere", "cri"): p["rougeur"] = max(p.get("rougeur", 0.0), 0.25 + 0.75 * u_t)
                elif emo == "panique": p["paleur"] = max(p.get("paleur", 0.0), 0.2 + 0.7 * u_t)
                elif emo == "gene": p["gene"] = 0.25 + 0.75 * u_t
            if TOON:                                                       # P1 : gros plans plus expressifs (larmes, sueur)
                ex_ = tuple(p.get("effets") or ())
                if emo in ("triste", "soupir") and q.get("intensite", 1) >= 2: ex_ += ("larme",)
                if emo == "gene" or (emo == "choc" and q.get("intensite", 1) >= 3): ex_ += ("sueur",)
                p["effets"] = ex_
            if cam_regard: p.update(forme="coin" if (len(role) + int(tm)) % 2 else "neutre", sourcils="neutre")
        if recule:                                                         # recul face à quelqu'un qui crie
            xa = position(scene, q["p"])[0]; u_r = _ressort((tm - t_r) / 0.35) * (1 - _ease((tm - q["fin"] - 0.1) / 0.3))
            p["x"] += (-1 if xa > x else 1) * 26 * s * u_r; p["tilt"] += (-1 if xa > x else 1) * 6 * u_r
        if not parle:                                                      # celui qui écoute garde la bouche fermée : il ne doit
            p["forme"] = BOUCHE_ECOUTE.get(p.get("forme"), p.get("forme"))  # jamais avoir l'air de parler avec la voix d'un autre
            p["bouche"] = 0.0; p.pop("viseme", None)
            if TOON and B and emo == "choc" and q.get("intensite", 1) >= 2: p["forme"] = "machoire"; p["bouche"] = 0.3   # P1 : mâchoire qui tombe (figée)
        # bouche synchronisée sur la voix
        if parle:
            k = int((tm - q["deb"]) * FPS); lv = float(q["lv"][k]) if 0 <= k < len(q["lv"]) else 0.0
            p["bouche"] = min(1.0, lv * 0.9) if emo != "cri" else 0.55 + 0.45 * min(1, lv)
            if emo == "rire": p["bouche"] = 0.4 + 0.4 * abs(math.sin(tm * 14))
            elif emo != "cri":
                v_ = levres.forme(q.get("lev"), tm) if q.get("lev") else viseme_a(q["groupes"], tm)
                p["viseme"] = v_
                if v_ in ("M",): p["bouche"] = max(p["bouche"], 0.1)          # lèvres fermées même si la voix est forte (m, b, p)
                elif v_ and lv < 0.12: p["bouche"] = max(p["bouche"], 0.18)    # un son prononcé doucement reste visible
            p["sq"] = 0.03 * lv + 0.008 * math.sin(tm * 7)
            if emo == "neutre" and lv > 0.72: p["sourcils"] = "hausses"         # sourcils qui appuient les mots forts
            ix = 1 + 0.45 * (q.get("intensite", 1) - 1) * EXAGERE              # jeu marqué ou très exagéré : la tête bouge plus
            p["tilt"] = (5 * math.sin(tm * 1.9 + len(role)) + 3 * lv) * ix + (8 * math.sin(tm * 15) if emo == "rire" else 0)
            k_p = max(0, k - int(0.17 * FPS)); lv_p = float(q["lv"][k_p]) if k_p < len(q["lv"]) else lv     # la tête 0,17 s plus tôt :
            t_p = (5 * math.sin((tm - 0.17) * 1.9 + len(role)) + 3 * lv_p) * ix              # cheveux, boucles d'oreilles, écharpe
            p["balance"] = p.get("balance", 0.0) + 0.09 * (t_p - p["tilt"]) + 0.5 * (lv - lv_p)   # suivent avec du retard
            if q.get("intensite", 1) >= 2 and B:                               # grimace : yeux et sourcils poussés
                p["pupille"] = p.get("pupille", 1.0) * (1 + 0.12 * (q["intensite"] - 1)); p["sourcils_h"] = p.get("sourcils_h", 0.0) + 0.25 * (q["intensite"] - 1)
            u_d = (tm - q["deb"]) / 0.3
            if 0 <= u_d < 1: p["y"] -= 16 * s * math.sin(math.pi * u_d)            # petit élan quand il prend la parole
            if B and q["i"] in TON:                                        # l'intonation pilote sourcils, yeux et tête
                zc = TON[q["i"]][0]; zf = float(zc[k]) if 0 <= k < len(zc) else 0.0
                p["sourcils_h"] = float(np.clip(p.get("sourcils_h", 0.0) + 0.55 * zf, -0.7, 1.5))
                p["pupille"] = float(np.clip(p.get("pupille", 1.0) + 0.1 * max(0.0, zf), 0.7, 1.45))
                p["tilt"] += 3.5 * zf
                if k >= 3 and 0 <= k < len(q["lv"]) and q["lv"][k] - q["lv"][k - 3] > 0.45: p["y"] += 10 * s     # hochement sur les syllabes appuyées
                res = TON[q["i"]][1]; u_f = (tm - (q["fin"] - 0.6)) / 0.6     # la fin de la phrase
                if 0 <= u_f <= 1.2 and (res.get("fin", 0) > 0.5 or q.get("texte", "").rstrip().endswith("?")):   # question : sourcil levé, tête penchée
                    u_q = min(1.0, u_f); p["sourcil_leve"] = max(p.get("sourcil_leve", 0.0), 0.9 * u_q); p["tilt"] += 7 * u_q; p["pupille"] = max(p.get("pupille", 1.0), 1.1)
                elif 0 <= u_f <= 1.0 and res.get("fin", 0) < -0.5: p["tilt"] -= 3 * u_f; p["y"] += 6 * s * u_f    # affirmation : la tête descend
                if zf < -0.5 and lv < 0.5: p["paupiere"] = max(p.get("paupiere", 0.0), 0.3)    # voix grave et molle : paupières lourdes
                if zf > 1.2 and lv > 0.6: p["sourcils_h"] = max(p.get("sourcils_h", 0.0), 1.1); p["pupille"] = max(p.get("pupille", 1.0), 1.3)   # voix qui monte fort
            if B and q["emo"] in ("colere", "cri"): p["rougeur"] = max(p.get("rougeur", 0.0), 0.65 * lv)   # le rouge monte avec la voix
        else:
            if B and q["p"] != role and q["i"] in TON and q["fin"] - 0.35 <= tm <= q["fin"] + 0.25 and TON[q["i"]][1].get("fin", 0) < -0.3:
                p["y"] += 7 * s * math.sin(math.pi * (tm - q["fin"] + 0.35) / 0.6)   # celui qui écoute acquiesce quand la phrase se pose
            p["bouche"] = 0.0 if emo not in ("choc", "panique") else 0.25
            p["sq"] = 0.012 * math.sin(tm * 2.4 + len(role))                  # respiration
            p["tilt"] = 3 * math.sin(tm * 0.9 + len(role))
        p["x"] += 7 * s * math.sin(tm * 1.1 + len(role) * 1.7)                # balancement continu : le personnage vit
        t_sc = DEBUT_SCENE.get(scene)                                      # entrée en scène : il arrive du bord en trottinant
        if t_sc is not None and scene not in SANS_ENTREE and tm < t_sc + 0.75:
            u_e = _ease((tm - t_sc + 0.05) / 0.7); bord = -260 if x < W / 2 else W + 260
            p["x"] = bord + (p["x"] - bord) * u_e; p["y"] -= abs(math.sin(tm * 14)) * 8 * s * (1 - u_e)
            if u_e < 0.98: p["marche"] = tm * 14; p["balance"] = p.get("balance", 0.0) + 0.6 * math.sin(tm * 14)   # vraie marche : les jambes alternent
        if parle and q["emo"] in ("colere", "cri"):                         # il s'avance vers celui qu'il engueule
            cible = next((r2 for r2 in places[scene] if r2 != role), None)
            if cible: p["x"] += (1 if position(scene, cible)[0] > x else -1) * 30 * s * _ease((tm - q["deb"]) / 0.3)
        if emo == "rire": p["y"] -= abs(math.sin(tm * 12)) * 18 * s
        if emo == "joie": p["y"] -= abs(math.sin(tm * 8)) * 40 * s
        if emo == "soupir": p["sq"] -= 0.05
        # gestes : ceux de l'émotion, sinon gestes de conversation qui changent toutes les ~1,2 s
        g_txt = (q["geste"] if parle else None) or (mien["geste"] if (mien and mien["geste"] in ("croises",) and tm <= mien["fin"] + 0.6) else None)
        mains = ("ouverte", "ouverte"); elan = 0.0
        if reac_geste and not g_txt: g_txt = reac_geste
        if g_txt:                                                          # geste expressif tiré de la réplique (bras croisés, doigt pointé…)
            if g_txt == "pointe":
                cible = next((r2 for r2 in places[scene] if r2 != role), None)
                g_txt = "pointe_d" if cible and position(scene, cible)[0] > x else "pointe_g"
            mains = studio.GESTES[g_txt][1] if g_txt in studio.GESTES else mains
            src = q if (reac_geste == g_txt or not mien) else mien; u_g = _ressort((tm - src["deb"] + 0.1) / 0.45) * (1 - _ease((tm - src["fin"] - 0.35) / 0.35))
            elan = u_g - _ease((tm - src["deb"] + 0.1) / 0.45)              # dépassement : les cheveux et vêtements suivent
            pg, pd = (POSES_TOON.get(g_txt) or POSES[g_txt]) if TOON else POSES[g_txt]; bg, bd = _mel(NEUTRE_BRAS[0], pg, u_g), _mel(NEUTRE_BRAS[1], pd, u_g)
            if g_txt == "haussement": p["y"] -= 10 * s * u_g; p["tilt"] += 7 * u_g; p["epaules"] = max(p.get("epaules", 0.0), u_g)
            if g_txt.startswith("pointe"): p["tilt"] += (5 if g_txt == "pointe_d" else -5) * u_g
        elif bg is None:
            if parle:
                per = 1.6 - 0.7 * float(((B or {}).get("rythme") or {}).get("energie", 0.3))   # vidéo d'origine agitée : gestes plus fréquents
                if TOON: per = 3.2 - 0.8 * float(((B or {}).get("rythme") or {}).get("energie", 0.3))   # toon : gestes tenus, comme dans les vidéos
                k_ = int((tm - q["deb"]) / per + q["i"] * 7); trans = 0.7 if TOON else 0.55
                u = (_ease if TOON else _ressort)(((tm - q["deb"]) % per) / trans); elan = 0.0 if TOON else u - _ease(((tm - q["deb"]) % per) / 0.55)
                g_o = [t_ for t_ in GESTES_ORIG if q["deb"] - 0.2 <= t_ <= tm]       # P4 : le geste change quand l'acteur de l'original bouge
                if TOON and g_o and len([t_ for t_ in GESTES_ORIG if q["deb"] - 0.2 <= t_ <= q["fin"]]) >= 1:
                    k_ = len(g_o) + q["i"] * 7; u = _ease((tm - g_o[-1]) / trans)
                    if tm - q["deb"] < trans and len(g_o) == 1: u = _ease((tm - q["deb"]) / trans)
                GS, MS = (GESTES_TOON, MAINS_TOON) if TOON else (GESTES, MAINS_CONV)
                g = GS[k_ % len(GS)]; g0 = GS[(k_ - 1) % len(GS)] if tm - q["deb"] >= per else ((-18, 8), (18, -8))
                mains = MS[k_ % len(MS)]
                if FICHES and not TOON:                                    # adultes : gestes plus mesurés, sauf jeu exagéré (style toons)
                    kx = min(1.15, 0.6 * (1 + EXAGERE * (q.get("intensite", 1) - 1) * 0.45) * (1 + 0.25 * (EXAGERE - 1)))
                    g, g0 = tuple((v[0] * kx, v[1] * 0.8) for v in g), tuple((v[0] * kx, v[1] * 0.8) for v in g0)
                bg, bd = _mel(g0[0], g[0], u), _mel(g0[1], g[1], u)
                fin_u = _ease((tm - q["fin"] + 0.3) / 0.3)                     # retour au repos en douceur à la fin de la phrase
                bg, bd = _mel(bg, (-18, 8), fin_u), _mel(bd, (18, -8), fin_u)
            else: bg, bd = (-18, 8), (18, -8)
        else:
            bg, bd = _mel((-18, 8), bg, u_emo), _mel((18, -8), bd, u_emo)
            if emo == "colere": bg, bd = (bg[0] + 10 * math.sin(tm * 18), bg[1]), (bd[0] - 10 * math.sin(tm * 18), bd[1])
        if parle and B and not g_txt:                                       # les mains « battent » sur les mots appuyés de la voix
            k_ = int((tm - q["deb"]) * FPS)
            f3, f9 = max(3, FPS // 10), max(9, int(0.3 * FPS))
            for j_ in range(min(k_, len(q["lv"]) - 1), max(f3, k_ - f9), -1):
                if q["lv"][j_] - q["lv"][j_ - f3] > 0.32:
                    b_ = math.sin(math.pi * min(1.0, (k_ - j_) / FPS / 0.3)) * (0.45 if TOON else 1.0); bd = (bd[0], bd[1] - 28 * b_); bg = (bg[0], bg[1] + 14 * b_); break
        if TOON and B and ASSIS.get(scene) == role and B.get("lieux") and B["lieux"][min(scene, len(B["lieux"]) - 1)] == "voiture" and g_txt not in GESTES_TETE:
            bg = POSES_TOON["volant"][0]; mains = ("ouverte", mains[1])            # P2 : au volant, une main reste sur le volant
            if not parle: bd = POSES_TOON["volant"][1]; mains = ("ouverte", "ouverte")
        if g_txt == "pianote": bd = (bd[0], bd[1] + 5 * math.sin(tm * 19))         # le pouce tape sur l'écran
        if g_txt == "appuye": p["hanche"] = 0.9; p["tilt"] += 4                 # déhanché
        p["bras_g"], p["bras_d"] = bras_naturel(bg, g_txt), bras_naturel(bd, g_txt)
        p["main_forme_g"], p["main_forme_d"] = mains
        if B: duo(p, role, tm, q, scene, parle)                            # gestes à deux (tope, main sur l'épaule, donner, pousser)
        if B:                                                              # corps vivant : poids du corps, trois-quarts, cheveux et vêtements qui suivent
            autre_ = q["p"] if q["p"] != role else next((r2 for r2 in places[scene] if r2 != role), None)
            if autre_ in places[scene] and not cam_regard:                 # il tourne la tête vers l'autre (trois-quarts, profil sur une réaction)
                k_tq = 0.5 if parle else (0.75 if (not parle and emo in ("choc", "sceptique", "blase")) else 0.4 if q["p"] != role else 0.25)
                p["tq"] = k_tq * (1 if position(scene, autre_)[0] > x else -1)
            p["hanche"] = (0.35 if parle else 0.55) * math.sin(tm * (0.8 if parle else 0.45) + len(role) * 1.3)
            p["balance"] = p.get("balance", 0.0) + 2.4 * elan
            p["etire"] = max(0.0, 2.2 * elan)                              # geste vif : le bras s'étire un instant (étirement « toons »)
            p["sourcils_h"] = p.get("sourcils_h", 0.0) + 0.1 * math.sin(tm * 2.7 + len(role) * 2) + 0.05 * math.sin(tm * 6.1)
            if FICHES and ASSIS.get(scene) == role:                        # assis : il reste sur sa chaise
                p.update(assis=True, x=x + 4 * s * math.sin(tm * 0.6), y=y, hanche=0.0, marche=None)
        # regard vers celui qui parle (ou vers celui à qui on parle), petites saccades, clignements
        autre = q["p"] if q["p"] != role else next((r2 for r2 in places[scene] if r2 != role), None)
        if autre and autre in places[scene]:
            xa = position(scene, autre)[0]
            k_s = math.floor(tm * 1.7 + len(role) * 3.1)                  # saccades : le regard SAUTE d'un point à l'autre (vrais yeux)
            sx_ = (math.sin(k_s * 12.9898) * 43758.5453) % 1 - 0.5; sy_ = (math.sin(k_s * 78.233) * 12543.21) % 1 - 0.5
            p["regard"] = ((0.8 if xa > x else -0.8) + 0.22 * sx_, 0.14 * sy_)
            if emo == "reflechit": p["regard"] = (0.45 * (1 if xa > x else -1), -0.65)          # il cherche en l'air
            elif emo == "gene": p["regard"] = (0.35 * (1 if xa > x else -1) * (0.5 + sx_), 0.55)  # il fuit le regard, yeux baissés
        if B and cam_regard: p["regard"] = (0.0, 0.05); p["tilt"] *= 0.3   # il fixe la caméra
        # clignements : réguliers, plus rapides sous le stress (double clignement), paupière à demi pendant le geste
        dt_c = min((tm - c for c in clign[role] if 0 <= tm - c < 0.16), default=None)
        if emo in ("panique", "gene", "choc", "sceptique") and dt_c is None:
            ph_ = (tm * (1.4 if emo == "panique" else 0.9) + len(role) * 0.37) % 1.0
            if ph_ < 0.16: dt_c = ph_
            elif emo == "panique" and 0.24 <= ph_ < 0.40: dt_c = ph_ - 0.24
        if dt_c is not None and p["yeux"] == "ouverts": p["yeux"] = "fermes" if 0.035 <= dt_c < 0.11 else "vides"
        if g_txt == "pianote":                                             # téléphone tenu devant lui, il regarde l'écran
            o = objets.get(("telephone", round(s, 2)))
            if o is None: o = objets[("telephone", round(s, 2))] = M.objet("telephone", s * ((0.8 if TOON else 0.5) if FICHES else 1.0))
            if o is not None: p["main_d"] = o
            p["regard"] = (0.15 * (p.get("tq") or 0), 0.7)
        # objet en main pendant la réplique
        if mien and mien.get("objet") and tm <= mien["fin"] + 0.3:
            o = objets.get((mien["objet"], round(s, 2)))
            if o is None: o = objets[(mien["objet"], round(s, 2))] = M.objet(mien["objet"], s * ((0.8 if TOON else 0.5) if FICHES else 1.0))
            if o is not None:
                if TOON and mien["objet"] == "telephone" and (p.get("tq") or 0) > 0.15:   # tourné vers la droite : l'oreille visible
                    p["main_g"] = o; p["main_forme_g"] = "poing"; p["bras_g"] = (-TEL_OREILLE[0], -TEL_OREILLE[1])   # est à gauche
                else:
                    p["main_d"] = o; p["main_forme_d"] = "poing"
                    p["bras_d"] = TEL_OREILLE if mien["objet"] == "telephone" else (120, -100)   # téléphone : tenu à l'oreille
        return p

    global COUVERTURE                                                      # couverture : titre visible et visage le plus expressif
    fortes = [z for z in ph if z["emo"] in ("choc", "cri", "colere", "panique", "rire", "joie") and z["p"] != "narrateur"]
    if ph and ph[0]["p"] == "narrateur" and mini: COUVERTURE = ph[0]["deb"] + 0.6
    elif fortes: COUVERTURE = t_reaction(fortes[0]) + 0.15
    else: COUVERTURE = (ph[-1]["fin"] + 0.45) if ph else 1.0
    COUVERTURE = round(float(COUVERTURE), 2)
    CARTES = {k: carte(tr[4]) for k, tr in enumerate(transitions) if tr[2] == "carton"}
    GELEE = {}

    def partage(haut, bas, u, sc_h=None, sc_b=None):
        """Écran partagé : une bande de chaque plan, centrée sur la tête du personnage, l'une au-dessus de l'autre, séparées par
        un trait blanc ; la moitié du bas glisse en place au début (u : 0 → 1)."""
        h2 = H // 2
        def y0_(sc_): return int(np.clip(TETES_Y.get(sc_, H * 0.4) - 0.38 * h2, 0, H - h2))
        fr = np.empty_like(haut); y_h, y_b = y0_(sc_h), y0_(sc_b); fr[:h2] = haut[y_h:y_h + h2]; fr[h2:] = bas[y_b:y_b + H - h2]
        if u < 1:
            dx = int(W * (1 - _ease(max(0.0, u)))); fr[h2:] = np.roll(fr[h2:], dx, 1)
            if dx: fr[h2:, :dx] = (30, 30, 36)
        cv2.rectangle(fr, (0, h2 - 5), (W, h2 + 5), (250, 250, 250), -1)
        return fr

    def rembobine(fr, tm, u):
        """Effet cassette qui rembobine : lignes qui ondulent, couleurs décalées, bande de bruit, « ◀◀ » qui clignote."""
        fr = fr.copy(); rg = np.random.default_rng(int(tm * 1000))
        for y in range(0, H, 6):                                           # lignes décalées (tracking VHS)
            d_ = int(10 * math.sin(y * 0.03 + tm * 40) + rg.integers(-3, 4))
            if d_: fr[y:y + 6] = np.roll(fr[y:y + 6], d_, 1)
        fr[..., 0] = np.roll(fr[..., 0], 6, 1); fr[..., 2] = np.roll(fr[..., 2], -6, 1)   # couleurs décalées
        yb = int((tm * 2400) % H); fr[yb:yb + 50] = np.clip(fr[yb:yb + 50].astype(np.int16) + rg.integers(-60, 60, fr[yb:yb + 50].shape), 0, 255).astype(np.uint8)
        fr = cv2.addWeighted(fr, 0.85, np.full_like(fr, (40, 60, 120)), 0.15, 0)
        if int(tm * 6) % 2 == 0:
            for k in range(2):                                             # « ◀◀ »
                x0 = 80 + k * 70
                pts = np.array([(x0 + 60, 260), (x0, 300), (x0 + 60, 340)], np.int32)
                cv2.fillPoly(fr, [pts], (250, 250, 250), cv2.LINE_AA)
        cv2.putText(fr, "REMBOBINAGE", (230, 318), cv2.FONT_HERSHEY_DUPLEX, 1.6, (250, 250, 250), 3, cv2.LINE_AA)
        return fr

    def image(fi):
        tm = fi / FPS
        k_tr = next((k for k, x in enumerate(transitions) if x[0] <= tm < x[1]), None); tr = transitions[k_tr] if k_tr is not None else None
        if tr and tr[2] == "carton":                                       # carton plein écran qui « pop »
            u = (tm - tr[0]) / (tr[1] - tr[0]); z = 1 + 0.25 * (1 - _ease(u / 0.18)) if u < 0.18 else 1 + 0.03 * (u - 0.18)
            c = CARTES[k_tr]; M_ = np.float32([[z, 0, W / 2 - z * W / 2], [0, z, H / 2 - z * H / 2]])
            return cv2.warpAffine(c, M_, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        if tr:                                                             # panoramique rapide avec flou de mouvement
            u = _ease((tm - tr[0]) / (tr[1] - tr[0]))
            avant = vue(tr[0] - 0.01); apres = vue(tr[1] + 0.01); dx = int(u * W)
            fr = np.concatenate([avant[:, dx:], apres[:, :dx]], 1) if 0 < dx < W else (apres if dx >= W else avant)
            k = int(9 + 140 * math.sin(math.pi * u)); return cv2.blur(fr, (k | 1, 1))
        if FIN_CARTE is not None and tm >= FIN_CARTE:                       # signature de la chaîne (identique sur toutes les vidéos)
            if "fin" not in CARTES: CARTES["fin"] = marque.signature(W, H, sk.get("suite") or ("Abonne-toi pour la suite !" if not mini else "Abonne-toi !"))
            u = (tm - FIN_CARTE) / 0.25; z = 1 + 0.2 * (1 - _ease(u)) if u < 1 else 1 + 0.01 * (tm - FIN_CARTE)
            M_ = np.float32([[z, 0, W / 2 - z * W / 2], [0, z, H / 2 - z * H / 2]])
            return cv2.warpAffine(CARTES["fin"], M_, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        if tm >= GEL:                                                      # arrêt sur image : la réaction finale figée, zoom lent, couleurs passées
            if "img" not in GELEE: GELEE["img"] = vue(GEL - 0.01).astype(np.float32)
            u = tm - GEL; z = 1.0 + 0.05 * _ease(u / 0.25) + 0.02 * u
            M_ = np.float32([[z, 0, W / 2 - z * W / 2], [0, z, H * 0.45 - z * H * 0.45]])
            g = cv2.warpAffine(GELEE["img"], M_, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            gris = g.mean(2, keepdims=True); g = g * 0.8 + gris * 0.2
            if "vig" not in GELEE:
                yy, xx = np.mgrid[0:H, 0:W]; GELEE["vig"] = (1 - 0.22 * np.clip(((xx - W / 2) / (W * 0.7)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2, 0, 1))[..., None].astype(np.float32)
            g = g * GELEE["vig"]
            if u < 0.08: g = g + (255 - g) * (0.3 * (1 - u / 0.08))            # petit flash au moment du gel
            return np.clip(g, 0, 255).astype(np.uint8)
        rb = next((r_ for r_ in REMB if r_[0] <= tm < r_[1]), None)
        if rb is not None:                                                 # rembobinage : les images d'avant défilent à l'envers
            u = (tm - rb[0]) / (rb[1] - rb[0]); t_src = max(0.0, rb[0] - (rb[0] - rb[2]) * min(1.0, 1.25 * u) - 0.02)
            return rembobine(vue(t_src), tm, u)
        ap = next((a_ for a_ in APPEL if a_[0] <= tm < a_[1]), None)
        if ap is not None and ap[2] == "partage":                          # écran partagé : les deux personnages de l'appel
            q_ = actif(tm); haut = vue(tm, SC_HAUT if q_["scene"] != SC_HAUT else None, False)
            bas = vue(tm, ap[3] if q_["scene"] == SC_HAUT else None, False)
            fr = partage(haut, bas, (tm - ap[0]) / 0.25, SC_HAUT, ap[3] if q_["scene"] == SC_HAUT else q_["scene"])
            return habiller(fr, tm, q_, q_["scene"])
        if ap is not None and ap[2] == "ecoute":                           # plan d'écoute : on voit l'autre, la voix sort du téléphone
            return habiller(vue(tm, ap[3], False), tm, actif(tm), actif(tm)["scene"])
        fr = vue(tm)
        if tm > FIN and not DOUB:                                          # impact final : secousse qui s'amortit
            v = math.exp(-(tm - FIN) * 5) * 22
            fr = np.roll(fr, (int(v * math.sin(tm * 61)), int(v * math.cos(tm * 53))), (0, 1))
        return fr

    def cadre(q):
        if B and q["p"] in places[q["scene"]]:                             # valeur de plan choisie par le storyboard
            x_, _, s_ = position(q["scene"], q["p"]); tete_y = 1500 - 305 * s_; pl = q.get("plan", "large")
            if FICHES and q["p"] in FICHES:                                # humains : la tête est plus petite et plus haute
                tl = FICHES[q["p"]]["taille"]; ty, hh = HU.tete_y(s_, tl), HU.hauteur_tete(s_, tl)
                if ASSIS.get(q["scene"]) == q["p"]: ty += M.ASSIS_BAISSE * s_ * tl            # assis : la tête est plus basse
                def vise(z, f): return z, ty + (0.5 - f) * H / z               # centre de la tête à la fraction f du haut de l'écran
                if pl == "moyen":
                    xs = [position(q["scene"], r2)[0] for r2 in places[q["scene"]]]; z, cy = vise(1.3, 0.27); return z, (2 * x_ + sum(xs) / len(xs)) / 3, cy
                if pl == "serre": z, cy = vise(min(2.3, max(1.5, 430 / hh)), 0.3); return z, x_, cy
                if pl == "epaule":
                    ec = ecoutant(q); sens = 1 if (ec and position(q["scene"], ec)[0] < x_) else -1
                    z, cy = vise(min(2.3, max(1.5, 430 / hh)), 0.3); return z, x_ - sens * 110, cy
                if pl == "tres_serre": z, cy = vise(min(3.6, 820 / hh), 0.4); return z, x_, cy
                if pl == "plongee": z, cy = vise(1.7, 0.36); return z, x_, cy
                if pl == "contre_plongee": z, cy = vise(1.75, 0.3); return z, x_, cy
                return 1.0, W / 2, H / 2
            if pl == "moyen":
                xs = [position(q["scene"], r2)[0] for r2 in places[q["scene"]]]; return 1.22, (2 * x_ + sum(xs) / len(xs)) / 3, 1190.0
            if pl == "serre": return 1.5, x_, 1130.0
            if pl == "epaule":                                             # l'autre est de dos au premier plan : celui qui parle est décalé
                ec = ecoutant(q); sens = 1 if (ec and position(q["scene"], ec)[0] < x_) else -1
                return 1.5, x_ - sens * 120, 1150.0
            if pl == "tres_serre": return min(2.8, 2.15 * 1.08 / s_), x_, tete_y + 30     # le visage remplit l'écran
            if pl == "plongee": return 1.4, x_, tete_y + 150
            if pl == "contre_plongee": return 1.45, x_, tete_y + 120
            return 1.0, W / 2, H / 2
        if q["cam"] == "serre" and q["p"] in places[q["scene"]]: return 1.5, position(q["scene"], q["p"])[0], 1130.0
        return 1.0, W / 2, H / 2

    def dessine(img, role, p):
        """Personnage du rôle : humain adulte (fiche du casting) ou marionnette."""
        if FICHES and role in FICHES: return HU.dessiner(img, FICHES[role], p)
        return M.dessiner(img, M.ROLES.get(role, "bonnet"), p)

    def ecoutant(q):
        """Celui qui écoute la réplique (le plus proche de celui qui parle)."""
        autres = [r2 for r2 in places.get(q["scene"], []) if r2 != q["p"]]
        if not autres or q["p"] not in places.get(q["scene"], []): return None
        x_ = position(q["scene"], q["p"])[0]; return min(autres, key=lambda r2: abs(position(q["scene"], r2)[0] - x_))

    def figurant(f, tm, img, zb, cxb, cyb):
        """Figurant qui vit au fond de la scène (boit, tape au clavier, téléphone, marche…), à l'échelle du décor."""
        p = M.pose_neutre(); x0 = f.get("_x", f["x"]); k = x0 * 0.013; act = f["activite"]
        x = x0 + (math.sin(tm * 0.25 + k) * 60 if act == "marche" else 6 * math.sin(tm * 0.9 + k)); y = f.get("_y", 1265)
        if act == "danse": x += 18 * math.sin(tm * 4.2 + k)
        p.update(x=W / 2 + (x - cxb) * zb, y=H / 2 + (y - cyb) * zb, s=f.get("_s", 0.5) * zb, t=tm, costume=f["costume"], reflets=True, lumiere=B["lumiere"],
                 ombre=B["ombre"], mains=True, tilt=4 * math.sin(tm * 0.7 + k), regard=(math.sin(tm * 0.4 + k) * 0.8, 0.1),
                 balance=0.5 * math.sin(tm * 2 + k))
        cyc = (tm * 0.35 + k) % 1
        if act in ("boit", "mange"):
            lev = _ease(min(1, cyc / 0.15)) * (1 - _ease(max(0, cyc - 0.35) / 0.15)) if cyc < 0.5 else 0.0
            p["bras_d"] = _mel((60, 80), (150, 75), lev); p["main_d"] = objets.setdefault((act, round(p["s"], 2)), M.objet("verre" if act == "boit" else "croissant", p["s"] * ((0.8 if TOON else 0.6) if FICHES else 1.0)))
            p["main_forme_d"] = "poing"; p["bouche"] = 0.3 * lev
        elif act == "telephone":
            p["bras_d"] = POSES["telephone"][1]; p["main_forme_d"] = "poing"; p["bouche"] = 0.4 * abs(math.sin(tm * 7 + k)) if (tm + k) % 4 < 2.5 else 0.0
            p["viseme"] = "A" if p["bouche"] > 0.2 else None
        elif act == "tape":
            p["bras_g"], p["bras_d"] = (-40, 90 + 8 * math.sin(tm * 17)), (40, -90 + 8 * math.sin(tm * 19 + 1)); p["regard"] = (0.0, 0.6)
        elif act == "souleve":
            u = abs(math.sin(tm * 1.6 + k)); p["bras_g"], p["bras_d"] = (-60 - 100 * u, -40), (60 + 100 * u, 40)
            p["main_g"] = p["main_d"] = objets.setdefault(("haltere", round(p["s"], 2)), M.objet("haltere", p["s"] * (0.45 if FICHES else 0.7))); p["sq"] = -0.05 * u
        elif act == "coucou":                                              # elle fait coucou de la main
            u = math.sin(tm * 9 + k); p["bras_d"] = (150 + 18 * u, -120 - 10 * u); p["main_forme_d"] = "paume"; p["forme"] = "sourire"
        elif act == "signe":                                               # « viens ! » : bras tendu, l'index qui appelle
            u = abs(math.sin(tm * 5 + k)); p["bras_d"] = (95 - 25 * u, -20); p["main_forme_d"] = "index"; p["forme"] = "coin"; p["tilt"] = 8
        elif act == "danse":
            u = math.sin(tm * 4.2 + k); p["bras_g"], p["bras_d"] = (-120 - 30 * u, -40), (120 - 30 * u, 40); p["balance"] = 1.2 * u; p["forme"] = "sourire"
        elif act == "rit":
            p["forme"] = "grand_sourire"; p["yeux"] = "plisses"; p["tilt"] = 6 * math.sin(tm * 12 + k)
        elif act == "attend":
            p["bras_g"], p["bras_d"] = POSES["croises"]; p["main_forme_g"] = p["main_forme_d"] = "poing"
        elif act == "cherche":
            p["regard"] = (math.sin(tm * 0.8 + k), -0.3); p["tilt"] = 10 * math.sin(tm * 0.8 + k); p["bras_d"] = (60, 40); p["main_forme_d"] = "index"
        if any(0 <= ((tm + k * 3) % 3.7) < 0.12 for _ in (0,)): p["yeux"] = "fermes"
        if f.get("compagnon"): p.update(costume=f["costume"], regard=(0.7 if x0 < 540 else -0.7, 0.0), bouche=0.0)
        if FICHES and f.get("fiche"): p["s"] *= (1.0 if f.get("compagnon") else 1.15); HU.dessiner(img, f["fiche"], p)
        else: M.dessiner(img, f["perso"], p)

    def tache(img, x, y, r, col, a):
        """Petite tache de lumière / de vapeur, fondue dans l'image (zone locale seulement)."""
        x0, y0, x1, y1 = int(max(0, x - r)), int(max(0, y - r)), int(min(W, x + r + 1)), int(min(H, y + r + 1))
        if x1 <= x0 or y1 <= y0 or a <= 0: return
        yy, xx = np.ogrid[y0:y1, x0:x1]; m = np.clip(1 - np.sqrt((xx - x) ** 2 + (yy - y) ** 2) / r, 0, 1)[..., None] * a
        img[y0:y1, x0:x1] = (img[y0:y1, x0:x1] * (1 - m) + np.array(col, np.float32) * m).astype(np.uint8)

    def ambiances(img, tm, sc, zb, cxb, cyb):
        info = INFOS.get(sc, {}); amb = B["ambiances"]; P_ = PARTICULES
        def ecr(x, y): return W / 2 + (x - cxb) * zb, H / 2 + (y - cyb) * zb
        if "vapeur" in amb:
            for (vx, vy) in info.get("vapeur", []):
                for k in range(7):
                    ph_ = (tm * 0.3 + k / 7) % 1; x, y = ecr(vx + math.sin(tm * 1.3 + k) * 26 * ph_, vy - ph_ * 300)
                    tache(img, x, y, (18 + 34 * ph_) * zb, (250, 250, 250), 0.35 * (1 - ph_))
        if "poussiere" in amb:                                             # poussière qui flotte dans la lumière
            for k in range(22):
                x = (P_[k, 0] * W + math.sin(tm * 0.3 + k) * 40) % W; y = (P_[k, 1] * H * 0.7 + tm * 10 * (0.5 + P_[k, 2])) % (H * 0.75)
                tache(img, x, y, 4 + 3 * P_[k, 3], (255, 244, 210), 0.45 * (0.5 + 0.5 * math.sin(tm * 2 + k)))
        zone = (0, 0, W, H) if B["lieux"][min(sc, len(B["lieux"]) - 1)] == "rue" else None
        if zone is None and info.get("fenetre"):
            fx0, fy0, fx1, fy1 = info["fenetre"]; a, b = ecr(fx0, fy0); c, d = ecr(fx1, fy1); zone = (int(a), int(b), int(c), int(d))
        if zone and ("pluie" in amb or "neige" in amb):
            x0, y0, x1, y1 = [int(v) for v in zone]; x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
            if x1 > x0 and y1 > y0:
                sub = img[y0:y1, x0:x1]; w_, h_ = x1 - x0, y1 - y0
                for k in range(60 if "pluie" in amb else 45):
                    if "pluie" in amb:
                        x = (P_[k, 0] * w_ + tm * 140) % w_; y = (P_[k, 1] * h_ + tm * 1500 * (0.8 + 0.4 * P_[k, 2])) % h_
                        cv2.line(sub, (int(x), int(y)), (int(x - 8), int(y + 34)), (205, 215, 235), 2, cv2.LINE_AA)
                    else:
                        x = (P_[k, 0] * w_ + math.sin(tm + k) * 30) % w_; y = (P_[k, 1] * h_ + tm * 120 * (0.6 + 0.6 * P_[k, 2])) % h_
                        cv2.circle(sub, (int(x), int(y)), int(3 + 4 * P_[k, 3]), (252, 252, 255), -1, cv2.LINE_AA)
        if "neon" in amb and info.get("neons") and (tm % 5.3) < 0.22 and int(tm * 30) % 2:   # le néon grésille
            for nx0, ny0, nx1, ny1 in info["neons"]:
                a, b = ecr(nx0, ny0); c, d = ecr(nx1, ny1); a, b, c, d = max(0, int(a)), max(0, int(b)), min(W, int(c)), min(H, int(d))
                if c > a and d > b: img[b:d, a:c] = (img[b:d, a:c] * 0.7).astype(np.uint8)

    def keystone(img, plan):
        """Plongée / contre-plongée : les verticales fuient vers le bas (plongée) ou vers le haut (contre-plongée)."""
        k = 0.075 * W
        if plan == "contre_plongee": src = np.float32([[-k, 0], [W + k, 0], [W, H], [0, H]])
        else: src = np.float32([[0, 0], [W, 0], [W + k, H], [-k, H]])
        Mp = cv2.getPerspectiveTransform(src, np.float32([[0, 0], [W, 0], [W, H], [0, H]]))
        return cv2.warpPerspective(img, Mp, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def reaction(tm):
        """Plan de réaction : juste après une vanne, la caméra coupe sur la tête de celui qui l'encaisse."""
        for j, z in enumerate(ph):
            if not z["chute"] or z["p"] == "narrateur" or z["teaser"]: continue
            fin_r = z["fin"] + 0.9 if j == len(ph) - 1 else min(z["fin"] + 0.85, ph[j + 1]["deb"] - 0.15)
            if z["fin"] + 0.05 <= tm < fin_r:
                cible = next((r2 for r2 in places[z["scene"]] if r2 != z["p"]), None)
                if cible: return z, cible
        return None, None

    def chute_au_sol(role, tm, scene):
        """Sur la chute finale, celui qui l'encaisse s'effondre, KO : il s'affaisse en penchant vers l'extérieur, étoiles autour
        de la tête (renvoie (angle, avancement 0→1) ; il reste dans le cadre et ne cache jamais les autres)."""
        z = ph[-1]
        if scene != z["scene"] or role == z["p"] or tm < z["fin"] + 0.25: return 0.0, 0.0
        victime = next((r2 for r2 in places[scene] if r2 != z["p"]), None)
        if role != victime: return 0.0, 0.0
        u = (tm - z["fin"] - 0.25) / 0.3; sens = -1 if position(scene, role)[0] < W / 2 else 1
        v = u * u if u < 1 else 1 - 0.12 * math.exp(-(u - 1) * 6) * abs(math.sin((u - 1) * 14))   # petit rebond
        return sens * 22 * min(1, v), min(1, v)

    T0_DECOUPE = [x["t0"] for x in DECOUPE]

    def plan_a(tm):
        k = bisect.bisect_right(T0_DECOUPE, tm) - 1
        return (k, DECOUPE[k]) if 0 <= k < len(DECOUPE) and tm < DECOUPE[k]["t1"] + 0.5 else (None, None)

    def cadre_plan(x, tm):
        """Cadre d'un plan du découpage à l'instant tm, avec son mouvement de caméra (dosé par l'énergie de la voix)."""
        q_ = ph[x["j"]]; z, cx, cy = cadre(dict(q_, p=x["cible"], plan=x["plan"]))
        u = min(1.3, max(-0.2, (tm - x["t0"]) / max(0.4, x["t1"] - x["t0"]))); f_ = x["force"]; mv = x["mouvement"]
        if mv == "avance": z *= 1 + 0.09 * f_ * _ease(u)
        elif mv == "recul": z *= 1 + 0.09 * f_ * (1 - _ease(u))
        elif mv == "travelling": cx += 70 * f_ * (u - 0.5) / z
        elif mv == "zoom_choc": z *= 1 + 0.14 * f_ * (1 - math.exp(-max(0.0, tm - x["t0"]) * 10))
        elif mv == "epaule": cx += 6 * f_ * math.sin(tm * 1.7) + 4 * math.sin(tm * 3.3); cy += 5 * f_ * math.sin(tm * 2.1)
        elif mv == "vertige": z *= 1 + 0.22 * _ease(u)                     # le personnage grandit pendant que le décor s'éloigne
        else: z *= 1 + 0.005 * (tm - x["t0"])
        if x.get("tiers"):                                                 # règle des tiers : de l'espace dans la direction du regard
            autre = next((r2 for r2 in places[x["scene"]] if r2 != x["cible"]), None)
            if autre: cx += (1 if position(x["scene"], autre)[0] > position(x["scene"], x["cible"])[0] else -1) * W * 0.13 / z
        return z, cx, cy

    PASSAGE = {"glisse": 0.38, "zoom": 0.2, "file": 0.24, "coupe": 0.0}
    AMB = {}
    SONDE = {"on": False, "res": []}

    LUM_SC = {}
    TOILE = {}
    SENT, MARQ = np.array((1, 2, 3), np.uint8), np.array((3, 1, 2), np.uint8)

    def ombres_portees(img, a_c, box, liste, sol_y):
        """Ombre portée de chaque personnage (idée 6) : sa silhouette couchée sur le sol, à l'opposé de la lumière du lieu ; le soir,
        une deuxième ombre plus pâle se projette aussi sur le mur derrière lui (lampes allumées). Ombre nette (style aplat)."""
        x0, y0, x1, y1 = box; h2, w2 = H // 2, W // 2
        Mf = np.zeros((h2, w2), np.float32)
        zf = Mf[y0 // 2:y1 // 2, x0 // 2:x1 // 2]
        if zf.size == 0: return
        zf[:] = cv2.resize(a_c[..., 0], (zf.shape[1], zf.shape[0]), interpolation=cv2.INTER_AREA)
        sens = 1 if float((B or {}).get("lumiere", -1)) > 0 else -1
        sol_ = np.zeros_like(Mf); mur_ = np.zeros_like(Mf)
        soir = (B or {}).get("moment") in ("soir", "nuit") and INFOS.get(SC_COURANT[0], {}).get("lieu") not in ("rue", None)   # dehors : pas de mur proche
        for role, p in liste:
            if p.get("assis") or p.get("dos"): continue
            xf, yf, s_ = p["x"] / 2, p["y"] / 2, p["s"]
            src = np.zeros_like(Mf); a_, b_ = int(max(0, xf - 230 * s_ / 2)), int(min(w2, xf + 230 * s_ / 2)); yb = int(min(h2, yf + 2))
            if b_ <= a_ or yb <= 0: continue
            src[:yb, a_:b_] = Mf[:yb, a_:b_]
            k_ = -sens * 0.55                                              # x' = x + k (yf - y) ; y' = yf + 0.18 (yf - y)
            Ms = np.float32([[1, -k_, k_ * yf], [0, -0.18, 1.18 * yf]])
            sol_ = np.maximum(sol_, cv2.warpAffine(src, Ms, (w2, h2), flags=cv2.INTER_LINEAR))
            if soir and sol_y is not None:
                Mm = np.float32([[1, 0, -sens * 34 * s_], [0, 1, -14 * s_]])
                mur_ = np.maximum(mur_, cv2.warpAffine(src, Mm, (w2, h2), flags=cv2.INTER_LINEAR))
        if sol_y is not None:                                              # chaque ombre reste sur sa surface (sol / mur)
            ys = int(np.clip(sol_y / 2, 0, h2)); mur_[ys:] = 0
        f_ = np.maximum(0.17 * (sol_ > 0.5), 0.11 * (mur_ > 0.5)).astype(np.float32)
        if not f_.any(): return
        f_ = cv2.resize(f_, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
        img[:] = (img.astype(np.float32) * (1 - f_)).astype(np.uint8)

    def composer_ssaa(img, liste, sol_y=None):
        """Super-échantillonnage : les personnages sont dessinés sur une toile deux fois plus grande, puis réduits (moyenne des
        pixels) : traits parfaitement lisses, détails fins (cheveux, barbe, coutures) nets, comme un rendu 4K ramené en 1080p."""
        if "t" not in TOILE: TOILE["t"] = np.empty((2 * H, 2 * W, 3), np.uint8); TOILE["t"][:] = SENT; TOILE["sale"] = None
        T = TOILE["t"]
        if TOILE["sale"] is not None:                                      # vitesse : on ne remet à zéro que la zone dessinée la fois d'avant
            a_, b_, c_, d_ = TOILE["sale"]; T[b_:d_, a_:c_] = SENT
        TOILE["sale"] = (0, 0, 2 * W, 2 * H)                               # si un dessin plante en route : tout sera remis à zéro
        for role, p in liste:
            p2 = dict(p, x=p["x"] * 2, y=p["y"] * 2, s=p["s"] * 2, couleur_ombre=tuple(int(v) for v in MARQ))
            dessine(T, role, p2)
        vide = cv2.inRange(T, SENT, SENT)                                  # vitesse : comparaison des 3 couleurs d'un coup (OpenCV)
        x, y, w, h = cv2.boundingRect(cv2.bitwise_not(vide))
        TOILE["sale"] = (x, y, x + w, y + h) if w and h else None
        if not (w and h): return
        x0, y0 = (x // 2) * 2, (y // 2) * 2; x1, y1 = min(2 * W, x + w + 2) // 2 * 2, min(2 * H, y + h + 2) // 2 * 2
        if x1 <= x0 or y1 <= y0: return
        Tz, dz = T[y0:y1, x0:x1], vide[y0:y1, x0:x1] == 0
        ombre = cv2.inRange(Tz, MARQ, MARQ) > 0; corps = dz & ~ombre
        taille = ((x1 - x0) // 2, (y1 - y0) // 2)
        a_c = cv2.resize(corps.astype(np.float32), taille, interpolation=cv2.INTER_AREA)[..., None]
        a_o = cv2.resize(ombre.astype(np.float32), taille, interpolation=cv2.INTER_AREA)[..., None]
        coul = cv2.resize(cv2.bitwise_and(Tz, Tz, mask=corps.view(np.uint8)).astype(np.float32), taille, interpolation=cv2.INTER_AREA)   # couleurs prémultipliées
        if B and OMBRES:
            try: ombres_portees(img, a_c, (x0 // 2, y0 // 2, x1 // 2, y1 // 2), liste, sol_y)
            except Exception as e_: print(f"ombre portée impossible : {e_}", flush=True)
        Z = img[y0 // 2:y1 // 2, x0 // 2:x1 // 2].astype(np.float32)
        Z = Z * (1 - 0.2 * a_o)                                            # ombre au sol : le décor assombri de 20 %
        img[y0 // 2:y1 // 2, x0 // 2:x1 // 2] = np.clip(Z * (1 - a_c) + coul, 0, 255).astype(np.uint8)
    FM = {}
    FOND_MANGA = {"choc": ((255, 214, 40), (255, 150, 30)), "panique": ((150, 90, 220), (90, 50, 160)), "cri": ((240, 70, 60), (255, 160, 60)),
                  "colere": ((200, 30, 40), (120, 10, 20)), "joie": ((255, 225, 80), (255, 170, 200)), "amour": ((255, 150, 190), (255, 210, 225)),
                  "idee": ((255, 240, 120), (255, 255, 230))}

    def fond_manga(emo, k):
        """Fond qui explose en rayons de couleur derrière le personnage (choc, colère, panique…), comme dans les mangas."""
        if (emo, k) not in FM:
            c1, c2 = FOND_MANGA[emo]; yy, xx = np.mgrid[0:H // 2, 0:W // 2].astype(np.float32) * 2
            ang = np.arctan2(yy - H * 0.36, xx - W / 2) + k * math.pi / 24
            ray = (np.floor(ang / (math.pi / 12)) % 2)[..., None]
            im_ = (ray * np.array(c1, np.float32) + (1 - ray) * np.array(c2, np.float32)).astype(np.uint8)
            FM[(emo, k)] = cv2.resize(im_, (W, H), interpolation=cv2.INTER_NEAREST)
        return FM[(emo, k)]

    def lumieres(img, tm, sc):
        """Éclairage qui vit pendant la scène, selon le lieu et l'heure (lumière ajoutée, rien n'est flou)."""
        lieu_ = B["lieux"][min(sc, len(B["lieux"]) - 1)] if B.get("lieux") else ""
        nuit = B.get("moment") in ("soir", "nuit")
        if sc not in LUM_SC:
            yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32) * 4
            tele = np.exp(-(((xx - W * 0.1) / 420) ** 2 + ((yy - H * 0.55) / 700) ** 2)) if lieu_ == "salon" else None
            neon = np.exp(-(((yy - H * 0.12) / 380) ** 2)) if (lieu_ in ("bar", "restaurant") or "neon" in (B.get("ambiances") or [])) else None
            up = lambda m, c, k: None if m is None else np.clip(cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)[..., None] * np.array(c, np.float32) * k, 0, 255).astype(np.uint8)
            LUM_SC[sc] = (up(tele, (0.55, 0.7, 1.0), 30), up(neon, (1.0, 0.45, 0.8), 22))
        tele, neon = LUM_SC[sc]
        if lieu_ == "rue" and nuit:                                        # phares d'une voiture qui passe : bande de lumière qui balaie
            per = 7.3; u = (tm + sc * 2.1) % per
            if u < 1.4:
                xc = -300 + (W + 600) * (u / 1.4); col_ = np.exp(-((np.arange(W, dtype=np.float32) - xc) / 260) ** 2) * 70 * math.sin(math.pi * u / 1.4)
                bande = np.clip(col_[None, :, None] * np.array([1.0, 0.92, 0.7], np.float32), 0, 255).astype(np.uint8)
                img[:] = cv2.add(img, np.broadcast_to(bande, img.shape).copy())
        if tele is not None:                                               # télé allumée : lueur bleue qui change à chaque plan d'émission
            pas = math.floor(tm * 3.2); v = 0.6 + 0.4 * ((math.sin(pas * 91.7) * 43758.5) % 1)
            img[:] = cv2.add(img, cv2.convertScaleAbs(tele, alpha=v))
        if neon is not None and (tm * 9.0 + sc) % 13.0 >= 0.35:            # néon : léger grésillement de temps en temps
            img[:] = cv2.add(img, neon)

    def profond(fond, P, z, cx, cy):
        """Décor en profondeur (sans 3D) : le fond (loin) suit 80 % du mouvement de caméra, le premier plan (près) 97 %, comme les
        couches d'un vrai dessin animé. Cartes de déplacement calculées au quart de la résolution puis agrandies : l'image reste nette."""
        u, v = GRILLE
        def cam(k):
            zk = 1 + (z - 1) * k; cxk = W / 2 + (cx - W / 2) * k; cyk = H / 2 + (cy - H / 2) * k
            cxk = np.clip(cxk, W / (2 * zk), W - W / (2 * zk)); cyk = np.clip(cyk, H / (2 * zk), H - H / (2 * zk))
            return (u - W / 2) / zk + cxk, (v - H / 2) / zk + cyk
        sx, sy = cam(0.86)
        d = cv2.remap(P, (sx / 4).astype(np.float32), (sy / 4).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        mx, my = cam(0.72 + 0.26 * d)                                      # fond loin (72 %) … premier plan (98 %)
        mx = cv2.resize(mx.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR); my = cv2.resize(my.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
        return cv2.remap(fond, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def eclairer(img, avant, sc, fond, z=1.0):
        """Les personnages prennent la lumière du lieu : teinte de l'ambiance du décor (orangée le soir dans la rue, bleutée devant
        la télé) et liseré de lumière du côté de la source (ils sont DANS le décor, pas collés dessus). Image toujours nette."""
        if sc not in AMB:
            moy = fond.reshape(-1, 3).astype(np.float32).mean(0); amb = moy / max(1.0, float(moy.mean()))
            AMB[sc] = (np.clip(1 + 0.20 * (amb - 1), 0.86, 1.12).astype(np.float32),
                       np.clip(np.array([255, 236, 200], np.float32) * (0.9 if (B or {}).get("moment") in ("soir", "nuit") else 0.6), 0, 255))
        teinte, c_lis = AMB[sc]
        d_ = cv2.absdiff(img, avant); m = (d_[..., 0] | d_[..., 1] | d_[..., 2]) > 0   # vitesse : sans np.any sur toute l'image
        x0, y0, w_, h_ = cv2.boundingRect(m.astype(np.uint8))
        if not (w_ and h_): return
        y1, x1 = y0 + h_, x0 + w_
        sub, mm = img[y0:y1, x0:x1], m[y0:y1, x0:x1]
        mm = cv2.morphologyEx(mm.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))) > 0   # sans trous
        sub[mm] = np.clip(sub[mm].astype(np.float32) * teinte, 0, 255).astype(np.uint8)
        sens = 1 if float((B or {}).get("lumiere", -1)) > 0 else -1          # la lumière vient de ce côté (l'ombre au sol part à l'opposé)
        d = 7
        dec_ = np.zeros_like(mm); (dec_[:, :-d] if sens > 0 else dec_[:, d:])[:] = (mm[:, d:] if sens > 0 else mm[:, :-d])
        bord = mm & ~dec_                                                  # bord du personnage tourné vers la lumière
        clair = sub.astype(np.int16).sum(2) > 330                          # sur les parties claires (pas sur le trait noir ni l'ombre)
        z_ = bord & clair
        if z_.any(): sub[z_] = np.clip(sub[z_].astype(np.float32) * 0.55 + c_lis * 0.45, 0, 255).astype(np.uint8)
        if STYLE_RENDU in ("volume", "3d"):                                 # style « effet 3D » (maquettes de l'auteur)
            volume3d(sub, mm, sens, force=0.8 if STYLE_RENDU == "volume" else 1.0, brillance=0.25 if STYLE_RENDU == "volume" else 0.7,
                     contour_lum=0.3 if STYLE_RENDU == "volume" else 0.6)
        elif CEL:                                                          # ombrage en aplat (cel-shading) : bande d'ombre du côté opposé
            d2 = int(min(60, max(8, 20 * z)))                              # à la lumière → les personnages prennent du volume
            ombre = np.zeros_like(mm); (ombre[:, d2:] if sens > 0 else ombre[:, :-d2])[:] = (mm[:, :-d2] if sens > 0 else mm[:, d2:])
            zone_o = mm & ~ombre & clair & ~bord
            if zone_o.any(): sub[zone_o] = (sub[zone_o].astype(np.float32) * np.array([0.84, 0.84, 0.9], np.float32)).astype(np.uint8)
            ep_ = int(min(7, max(2, 2.5 * z)))                             # contour extérieur épais et net autour de toute la silhouette
            av_ = avant[y0:y1, x0:x1].astype(np.int16)                     # l'ombre au sol (décor assombri) n'a pas de contour
            sol_ = np.all(np.abs(sub.astype(np.int16) - (av_ * 0.8).astype(np.int16)) <= 6, axis=2)
            corps = (mm & ~sol_).astype(np.uint8)
            corps = cv2.morphologyEx(corps, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))   # sans les petits points isolés (pluie, poussière)
            cont = (cv2.dilate(corps, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ep_ + 1, 2 * ep_ + 1))) > 0) & ~mm
            if cont.any(): sub[cont] = M.TRAIT

    def vue(tm, force_sc=None, textes=True):
        """Image du plan à l'instant tm. force_sc : montrer une autre scène (appel : celui qui écoute, écran partagé) ;
        textes=False : sans sous-titres ni logo (posés ensuite sur l'image composée)."""
        q = actif(tm); q_reel = q
        if force_sc is not None and force_sc != q["scene"]:
            zs = [z2 for z2 in ph if z2["scene"] == force_sc]
            q = next((z2 for z2 in reversed(zs) if z2["deb"] <= tm), zs[0]) if zs else q
        sc = q["scene"]; SC_COURANT[0] = sc
        fond = decors.get(sc)
        if fond is None: fond = decors[sc] = decor_uni(sc)
        k_sh, sh = plan_a(tm) if DECOUPE else (None, None)
        if sh is not None and sh["scene"] != sc: sh = None
        flou_h = 0.0
        if sh is not None:                                                 # montage dynamique : le plan du découpage et son passage
            z, cx, cy = cadre_plan(sh, tm)
            pr = DECOUPE[k_sh - 1] if k_sh and DECOUPE[k_sh - 1]["scene"] == sc else None
            d_p = PASSAGE.get(sh["passage"], 0.0); u_p = (tm - sh["t0"]) / d_p if d_p else 1.0
            if pr is not None and u_p < 1:
                z0, cx0, cy0 = cadre_plan(pr, tm); e = _ease(u_p) if sh["passage"] != "file" else 0.5 - 0.5 * math.cos(math.pi * u_p)
                z, cx, cy = z0 + (z - z0) * e, cx0 + (cx - cx0) * e, cy0 + (cy - cy0) * e
                if sh["passage"] == "file": flou_h = math.sin(math.pi * u_p) * min(1.0, abs(cx - cx0) / 200 + 0.4)
                # passage zoom : AUCUN flou (il dédoublait les contours des personnages)
            elif sh["passage"] == "coupe" and pr is not None:              # coupe franche : petit punch-in pour garder l'élan
                u0 = min(1.0, (tm - sh["t0"]) / 0.25); z *= 1 + 0.035 * (1 - u0) ** 2
        else:
            # caméra : glisse en douceur d'un plan au suivant dans la même scène (pas de coupe sèche)
            z, cx, cy = cadre(q)
            j = ph.index(q)
            if j and ph[j - 1]["scene"] == sc:
                z0, cx0, cy0 = cadre(ph[j - 1]); u = _ease((tm - (q["deb"] - 0.3)) / 0.45)
                z, cx, cy = z0 + (z - z0) * u, cx0 + (cx - cx0) * u, cy0 + (cy - cy0) * u
            u0 = min(1, (tm - max(q["deb"] - 0.25, 0)) / 0.3); z *= 1 + 0.04 * (1 - u0) ** 2 + 0.006 * (tm - q["deb"])   # punch-in puis lente dérive
        plan_courant = sh["plan"] if sh is not None else q.get("plan")
        # plan serré : SEUL le personnage filmé est à l'image (personne coupé en deux sur le bord), dès la moitié du passage
        cible_seule = None
        if plan_courant in studio.SERRES:
            if sh is not None:                                             # pendant le passage : seuls l'ancien et le nouveau sujet
                cible_seule = sh["cible"] if (not d_p or u_p >= 0.5 or pr is None or pr["cible"] == sh["cible"]) else None
            else: cible_seule = q["p"]
        if q is ph[-1]:                                                    # chute finale : lent zoom dramatique pendant toute la réplique
            z *= 1 + 0.16 * _ease((tm - q["deb"]) / max(0.5, q["fin"] - q["deb"]))
            if tm > q["fin"]: z *= 1 + 0.08 * _ease((tm - q["fin"]) / 0.12)                            # punch final
            if tm > q["fin"] + 0.2 and len(places[sc]) > 1:                # puis plan large pour voir la réaction (chute à la renverse)
                u_l = _ease((tm - q["fin"] - 0.2) / 0.35); z = z + (1.0 - z) * u_l; cx = cx + (W / 2 - cx) * u_l; cy = cy + (H / 2 - cy) * u_l
                if u_l > 0.3: cible_seule = None                           # plan large : tout le monde revient à l'image
        elif q["chute"] and tm > q["fin"] - 0.6: z *= 1 + 0.12 * _ease((tm - q["fin"] + 0.6) / 0.2)
        dans_q = q["deb"] - 0.3 <= tm <= q["fin"] + 0.3
        if B and dans_q and q is not ph[-1] and sh is None:                # mouvement de caméra prévu par le storyboard
            u_q = (tm - q["deb"]) / max(0.4, q["fin"] - q["deb"]); mv = q.get("mouvement")
            if mv == "avance": z *= 1 + 0.10 * _ease(u_q)
            elif mv == "recul": z *= 1.10 - 0.10 * _ease(u_q)
            elif mv == "travelling": cx += 80 * (min(1.2, max(-0.2, u_q)) - 0.5) / z
            elif mv == "zoom_choc": z *= 1 + 0.16 * (1 - math.exp(-max(0.0, tm - q["deb"]) * 10))
            if mv == "epaule" or plan_courant == "epaule":                 # caméra tenue à l'épaule : léger flottement
                cx += 5 * math.sin(tm * 1.7) + 3 * math.sin(tm * 3.3); cy += 4 * math.sin(tm * 2.1)
        zr, cible = reaction(tm)
        if cible and zr["scene"] == sc and len(places[sc]) > 1 and zr is not ph[-1]:   # coupe sèche sur la réaction
            z, cx, cy = 1.55, position(sc, cible)[0], 1120.0
            if B: z, cy = 1.75, 1500 - 305 * position(sc, cible)[2] + 90
            if FICHES and cible in FICHES:
                s_c = position(sc, cible)[2]; z = min(2.6, 470 / HU.hauteur_tete(s_c, FICHES[cible]["taille"])); cy = HU.tete_y(s_c, FICHES[cible]["taille"]) + 0.2 * H / z
                if ASSIS.get(sc) == cible: cy += M.ASSIS_BAISSE * s_c * FICHES[cible]["taille"]
        cx = min(max(cx, W / (2 * z)), W - W / (2 * z)); cy = min(max(cy, H / (2 * z)), H - H / (2 * z))
        if B:                                                              # profondeur : le décor glisse moins vite que les personnages
            zb = 1 + (z - 1) * 0.86; cxb, cyb = W / 2 + (cx - W / 2) * 0.86, H / 2 + (cy - H / 2) * 0.86
            cxb = min(max(cxb, W / (2 * zb)), W - W / (2 * zb)); cyb = min(max(cyb, H / (2 * zb)), H - H / (2 * zb))
        else: zb, cxb, cyb = z, cx, cy
        zm, cxm, cym = zb, cxb, cyb
        if B and sh is not None and sh["mouvement"] == "vertige":          # effet vertige : le décor recule pendant que le personnage avance
            zb = max(1.0, zb * (1 - 0.2 * _ease((tm - sh["t0"]) / max(0.4, sh["t1"] - sh["t0"]))))
            cxb = min(max(cxb, W / (2 * zb)), W - W / (2 * zb)); cyb = min(max(cyb, H / (2 * zb)), H - H / (2 * zb))
        if B and CINE.get("profondeur"):                                   # couche du milieu : figurants entre le décor et les personnages
            zm = 1 + (z - 1) * 0.93; cxm, cym = W / 2 + (cx - W / 2) * 0.93, H / 2 + (cy - H / 2) * 0.93
            cxm = min(max(cxm, W / (2 * zm)), W - W / (2 * zm)); cym = min(max(cym, H / (2 * zm)), H - H / (2 * zm))
        if sc in PROF and not (sh is not None and sh["mouvement"] == "vertige") and (abs(z - 1) > 0.01 or abs(cx - W / 2) > 2 or abs(cy - H / 2) > 2):
            img = profond(fond, PROF[sc], z, cx, cy)                       # parallaxe : chaque point du décor suit la caméra selon sa distance
        else:
            Mx = np.float32([[zb, 0, W / 2 - zb * cxb], [0, zb, H / 2 - zb * cyb]])
            img = cv2.warpAffine(fond, Mx, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        if B and sc in PASSE:                                              # au loin, une voiture traverse la rue (toutes les ~11 s)
            per_, d_ = 11.0, 3.2; u_ = (tm + 4.0 * sc) % per_
            if u_ < d_:
                g_, dr_, sol_ = PASSE[sc]; sens_ = 1 if int((tm + 4.0 * sc) // per_) % 2 == 0 else -1; im_ = g_ if sens_ > 0 else dr_
                X0 = (-im_.shape[1] + (W + im_.shape[1]) * u_ / d_) if sens_ > 0 else (W - (W + im_.shape[1]) * u_ / d_); Y0 = 1265 - sol_
                zp = 1 + (z - 1) * 0.8; cxp = W / 2 + (cx - W / 2) * 0.8; cyp = H / 2 + (cy - H / 2) * 0.8
                Mv = np.float32([[zp, 0, W / 2 + (X0 - cxp) * zp], [0, zp, H / 2 + (Y0 - cyp) * zp]])
                cv_ = cv2.warpAffine(im_, Mv, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0)); a_ = cv_[..., 3:4].astype(np.float32) / 255
                if a_.any(): img[:] = (img * (1 - a_) + cv_[..., :3] * a_).astype(np.uint8)
        if B and sc in VOIT:                                               # voiture garée : elle glisse avec le décor
            im_, X0, Y0 = VOIT[sc]
            Mv = np.float32([[zb, 0, W / 2 + (X0 - cxb) * zb], [0, zb, H / 2 + (Y0 - cyb) * zb]])
            cv_ = cv2.warpAffine(im_, Mv, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
            a_ = cv_[..., 3:4].astype(np.float32) / 255
            if a_.any(): img[:] = (img * (1 - a_) + cv_[..., :3] * a_).astype(np.uint8)
        if B:
            for f_ in B["figurants"]:
                if f_["scene"] == sc and not cible_seule and not f_.get("compagnon"): figurant(f_, tm, img, zm, cxm, cym)
        if B and sc in INFOS and DECOR_VIVANT:                             # le décor vit : horloge, tasse, ventilateur, chat, pigeons, météo
            try:
                cris_ = [z2["deb"] for z2 in ph if z2["scene"] == sc and z2["emo"] in ("cri", "colere") and z2["deb"] <= tm]
                DA.animer(img, INFOS[sc], tm, lambda x_, y_: (W / 2 + (x_ - cxb) * zb, H / 2 + (y_ - cyb) * zb), zb,
                          dict(lieu=INFOS[sc].get("lieu", ""), ambiances=B.get("ambiances") or (), t_scene=tm - DEBUT_SCENE.get(sc, 0.0),
                               entree=sc not in SANS_ENTREE, t_cri=(tm - cris_[0]) if cris_ else -1.0, graine=B.get("graine", 0) + sc))
            except Exception as e_:
                if not ERREURS_ANIM: print(f"décor animé impossible : {e_}", flush=True)
                ERREURS_ANIM.append(1)
        sce = dec[sc] if sc < len(dec) else {}
        if sce.get("effet") == "tremblement" or (q["emo"] in ("cri", "colere") and q["deb"] <= tm <= q["fin"]):
            img = np.roll(img, (int(6 * math.sin(tm * 53)), int(6 * math.cos(tm * 47))), (0, 1))
        if B and MANGA and plan_courant in studio.SERRES and q["p"] != "narrateur" and q["deb"] - 0.05 <= tm <= q["fin"] + 0.1 \
                and q["emo"] in FOND_MANGA and (q.get("intensite", 1) >= 2 or q.get("chute")):
            u_m = _ease((tm - q["deb"] + 0.05) / 0.18) * (1 - _ease((tm - q["fin"]) / 0.1))
            fm = fond_manga(q["emo"], int(tm * 6) % 2)                     # rayons qui tournent un peu (2 dessins en alternance)
            img[:] = cv2.addWeighted(img, 1 - 0.82 * u_m, fm, 0.82 * u_m, 0)
        reflet_ = B and sc in INFOS and (INFOS[sc].get("miroirs") or INFOS[sc].get("vitrines") or (B.get("moment") in ("soir", "nuit") and INFOS[sc].get("fenetre")))
        avant_persos = img.copy() if (B and (LUMIERE_DECOR or reflet_)) else None   # pour retrouver les pixels des personnages (lumière, reflets)
        ssaa = []
        for role in places[sc]:                                            # personnages dessinés nets à l'échelle du plan
            if cible_seule and role != cible_seule and cible_seule in places[sc]: continue
            p = pose(role, tm, q, sc)
            p["x"], p["y"], p["s"] = W / 2 + (p["x"] - cx) * z, H / 2 + (p["y"] - cy) * z, p["s"] * z
            ang, ko = chute_au_sol(role, tm, sc)
            if ko:                                                         # KO : écrasé, yeux en croix, étoiles
                p["sq"] = max(p["sq"], 0.28 * ko); p["yeux"] = "plisses"; p["forme"] = "o"; p["bouche"] = 0.2
                p["effets"] = tuple(set(p["effets"]) | {"etoiles"}); p["bras_g"], p["bras_d"] = (-60, 20), (60, -20)
            if not -400 < p["x"] < W + 400: continue
            if FICHES and role in FICHES:                                  # hauteur de la tête à l'écran (écran partagé)
                TETES_Y[sc] = p["y"] - (1500 - HU.tete_y(p["s"], FICHES[role]["taille"]))
            if SONDE["on"]:                                                # contrôle image : où est la tête de chacun à l'écran
                try:
                    if FICHES and role in FICHES: (hx, hy), (hrx, hry), _m = HU.reperes(FICHES[role], p)
                    else: K_ = M.squelette(p); (hx, hy), hrx, hry = K_["tete"], K_["rx"], K_["ry"]
                    SONDE["res"].append(dict(t=round(tm, 2), role=role, x=float(hx), y=float(hy), rx=float(hrx), ry=float(hry),
                                             plan=plan_courant, seul=cible_seule, parle=(role == q["p"]), i=q["i"],
                                             sous_titre=bool(q["deb"] <= tm < q["fin"] + 0.2 and q["p"] != "narrateur")))
                except Exception: pass
            flou_p = 0.0
            if B and CINE.get("focus") and len(places[sc]) > 1 and plan_courant in ("moyen", "large") and not ang and q["p"] in places[sc] and role != q["p"]:
                flou_p = 3.2 * _ease((tm - q["deb"] + 0.05) / 0.35)                # mise au point sur celui qui parle : l'autre devient flou
            if flou_p > 0.3:
                calque = np.empty_like(img); calque[:] = (1, 2, 3); dessine(calque, role, p)
                m_ = cv2.GaussianBlur((np.abs(calque.astype(np.int16) - (1, 2, 3)).sum(2) > 9).astype(np.float32), (0, 0), flou_p)[..., None]
                calque = cv2.GaussianBlur(calque, (0, 0), flou_p).astype(np.float32)
                img[:] = (img * (1 - m_) + calque * m_).astype(np.uint8); continue
            if not ang:
                if SSAA: ssaa.append((role, p))                            # dessiné en double résolution puis réduit (traits lisses)
                else: dessine(img, role, p)
                continue
            calque = np.empty_like(img); calque[:] = (1, 2, 3); dessine(calque, role, p)
            R_ = cv2.getRotationMatrix2D((p["x"], p["y"]), -ang, 1.0)
            calque = cv2.warpAffine(calque, R_, (W, H), flags=cv2.INTER_LINEAR, borderValue=(1, 2, 3))
            m_ = (np.abs(calque.astype(np.int16) - (1, 2, 3)).sum(2) > 9)[..., None]; img[:] = np.where(m_, calque, img)
        if ssaa: composer_ssaa(img, ssaa, (H / 2 + (DD.SOL - cyb) * zb) if (B and not (INFOS.get(sc, {}).get("lieu") == "voiture")) else None)
        if B and not cible_seule:                                          # compagnons (muets) : même échelle que les personnages
            for f_ in COMP.get(sc, []): figurant(f_, tm, img, z, cx, cy)
        if avant_persos is not None and LUMIERE_DECOR: eclairer(img, avant_persos, sc, fond, z)
        if reflet_ and avant_persos is not None and z < 1.3:             # plans larges seulement (en gros plan : tête fantôme)                           # reflet dans le miroir, les vitrines, la vitre le soir
            try: DA.reflets(img, np.any(img != avant_persos, axis=2), INFOS[sc], lambda x_, y_: (W / 2 + (x_ - cxb) * zb, H / 2 + (y_ - cyb) * zb), B.get("moment") in ("soir", "nuit"))
            except Exception as e_: print(f"reflet impossible : {e_}", flush=True)
        if False:                                                          # (amorce floue de l'autre, de dos : retirée, elle dédoublait l'image)
            ec = ecoutant(q); sens = -1 if position(sc, ec)[0] < position(sc, q["p"])[0] else 1
            y0_, x0_, x1_ = 1060, (0 if sens < 0 else W // 4), (W * 3 // 4 if sens < 0 else W)
            sub = np.empty((H - y0_, x1_ - x0_, 3), np.uint8); sub[:] = (1, 2, 3)
            y_dos = H + 420 - y0_
            if FICHES and ec in FICHES: y_dos = (H - 140 - y0_) + 1500 - HU.tete_y(2.4, FICHES[ec]["taille"])   # sa tête en bas de l'image
            p = pose(ec, tm, q, sc); p.update(dos=True, s=2.5 if not (FICHES and ec in FICHES) else 2.4, x=W / 2 + sens * 0.40 * W - x0_, y=y_dos, tremble=0, effets=(), main_g=None, main_d=None,
                                              bras_g=(-18, 8), bras_d=(18, -8))
            dessine(sub, ec, p)
            m_ = (np.abs(sub.astype(np.int16) - (1, 2, 3)).sum(2) > 9).astype(np.float32)
            m_ = cv2.GaussianBlur(m_, (0, 0), 6)[..., None]; sub = cv2.GaussianBlur(sub, (0, 0), 6).astype(np.float32) * 0.86
            zone = img[y0_:, x0_:x1_]; img[y0_:, x0_:x1_] = (zone * (1 - m_) + sub * m_).astype(np.uint8)
        if B and sc in AVANT:                                              # premier plan (comptoir, bureau) : glisse plus vite que le reste
            za = z * 1.06; cxa, cya = W / 2 + (cx - W / 2) * 1.1, H / 2 + (cy - H / 2) * 1.04
            Ma = np.float32([[za, 0, W / 2 - za * cxa], [0, za, H / 2 - za * cya]])
            av = cv2.warpAffine(AVANT[sc], Ma, (W, H), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE)
            np.copyto(img, av[..., :3], where=av[..., 3:4] > 127)
        if sce.get("effet") == "pluie_billets":
            t0 = min(z2["deb"] for z2 in ph if z2["scene"] == sc); _pluie(img, tm, t0, sc)
        if B:
            ambiances(img, tm, sc, zb, cxb, cyb)
            if plan_courant in ("plongee", "contre_plongee") and dans_q and q["p"] in places[sc]: img = keystone(img, plan_courant)
            if flou_h > 0.05:                                              # passage filé / zoom : flou de mouvement
                sig = 1.0 + 14 * flou_h                                    # flou gaussien horizontal : filé doux, jamais de double contour
                img = cv2.GaussianBlur(img, (int(6 * sig) | 1, 1), sigmaX=sig, sigmaY=0.1)
        if B and sc in AVANT_FLOU and z > 1.25:                            # 3e couche : feuillage flou au tout premier plan
            za = z * 1.15; cxa, cya = W / 2 + (cx - W / 2) * 1.15, H / 2 + (cy - H / 2) * 1.05
            Ma = np.float32([[za, 0, W / 2 - za * cxa], [0, za, H / 2 - za * cya]])
            c_, m_ = AVANT_FLOU[sc]; ca = cv2.warpAffine(c_, Ma, (W, H)); ma = cv2.warpAffine(m_, Ma, (W, H))[..., None] * 0.95
            img = (img * (1 - ma) + ca * ma).astype(np.uint8)
        if B and MANGA:                                                    # zoom choc : traits de vitesse sur les bords (style manga)
            mv_ = sh["mouvement"] if sh is not None else (q.get("mouvement") if dans_q else None)
            t0_ = sh["t0"] if sh is not None else q["deb"]
            if mv_ == "zoom_choc" and 0 <= tm - t0_ < 0.45:
                img[:] = cv2.add(img, cv2.convertScaleAbs(TRAITS_VITESSE[int(tm * 15) % 2], alpha=1 - (tm - t0_) / 0.45))
        if B and LUMIERES_VIVES: lumieres(img, tm, sc)                      # phares qui passent, télé qui scintille, néon qui grésille
        if B: img = cv2.multiply(img, GRADE, scale=1 / 255)                 # étalonnage de l'heure + vignettage (avant les textes)
        if B and SIGNATURE: img = cv2.LUT(img, LUT_CHAINE)                  # « look » de la chaîne : contraste et couleurs vives
        if B and CINE.get("etalonnage"):                                    # couleur de l'émotion (chaude, froide, rouge), en fondu
            j_ = ph.index(q); t_a = TEINTES.get(q["emo"], (1.0, 1.0, 1.0))
            t_p = TEINTES.get(ph[j_ - 1]["emo"], (1.0, 1.0, 1.0)) if j_ else (1.0, 1.0, 1.0); u_t = _ease((tm - q["deb"] + 0.2) / 0.5)
            t3 = tuple(a + (b - a) * u_t for a, b in zip(t_p, t_a))
            if max(abs(v - 1) for v in t3) > 0.005: img = cv2.LUT(img, teinte_lut(t3))
        if REFLET is not None and sh is not None and sh["passage"] == "coupe" and int(sh["t0"] * 7) % 3 == 0 and tm - sh["t0"] < 0.7:
            img = cv2.add(img, (REFLET * math.sin(math.pi * (tm - sh["t0"]) / 0.7)).astype(np.uint8))   # reflet de lumière chaude
        if GRAIN: img = cv2.subtract(cv2.add(img, GRAIN[int(tm * FPS) % 3]), (4, 4, 4, 0))
        if not textes: return img
        return habiller(img, tm, q_reel, q_reel["scene"])

    def habiller(img, tm, q, sc):
        """Textes par-dessus l'image : titre, voix off, signature de la chaîne, sous-titres de la réplique en cours."""
        fr = img.astype(np.float32)
        if q["p"] == "narrateur" and tm <= q["fin"] + 0.3:                 # voix off : le titre en grand au centre à l'ouverture,
            V = VOIX_OFF[q["i"]]; a2 = pop(V, (tm - q["deb"] + 0.2) / 0.3)   # en haut de l'image ensuite (jamais sur les têtes)
            poser(fr, a2, (W - a2.shape[1]) / 2, (H * 0.36 - a2.shape[0] / 2) if q is ph[0] else 300)
            if q is not ph[0]: poser(fr, FILIGRANE, 28, 118)
            return np.clip(fr, 0, 255).astype(np.uint8)
        if SIGNATURE and tm < 0.75:                                        # signature de la chaîne : le logo « pop » puis file dans le coin
            u_s = _ease(max(0.0, tm - 0.25) / 0.5); k_s = 2.4 - 1.4 * u_s
            Fg = cv2.resize(FILIGRANE, (max(1, int(FILIGRANE.shape[1] * k_s)), max(1, int(FILIGRANE.shape[0] * k_s))), interpolation=cv2.INTER_AREA)
            poser(fr, pop(Fg, (tm + 0.05) / 0.2), (W - Fg.shape[1]) / 2 * (1 - u_s) + 28 * u_s, 300 * (1 - u_s) + 118 * u_s)
        else: poser(fr, FILIGRANE, 28, 118)                               # signature discrète de la chaîne
        T = TITRES.get(sc) if mini else TITRE_FIXE
        if T is not None:
            t0 = min(z2["deb"] for z2 in ph if z2["scene"] == sc) if mini else 0
            d_t = tm - t0
            d_max = 3.2 if mini else 4.5                                   # le titre s'efface : il ne cache jamais les visages
            if d_t < d_max:
                a2 = pop(T, (d_t + 0.25) / 0.25)
                if d_t > d_max - 0.5: a2 = a2.copy(); a2[..., 3] *= max(0.0, (d_max - d_t) / 0.5)
                poser(fr, a2, (W - a2.shape[1]) / 2, 190)
        g = next((x for x in q["groupes"] if x[1] <= tm < x[2] + (0.2 if x is q["groupes"][-1] else 0)), None)
        if g and q["deb"] <= tm < q["fin"] + 0.2:
            age = tm - g[1]; cc = pop(carton(g[0]), age / 0.12)
            if B and 0.12 < age < 0.42:                                    # sous-titre animé : petit rebond à l'apparition
                k_r = 1 + 0.07 * math.sin(math.pi * (age - 0.12) / 0.3); cc = cv2.resize(cc, (int(cc.shape[1] * k_r), int(cc.shape[0] * k_r)))
            dx_c = 5 * math.sin(tm * 47) if (B and q["emo"] in ("cri", "colere")) else 0          # il tremble quand on crie
            poser(fr, cc, (W - cc.shape[1]) / 2 + dx_c, CAP_Y - cc.shape[0] / 2)
        return np.clip(fr, 0, 255).astype(np.uint8)

    if apercu:
        os.makedirs(sortie, exist_ok=True)
        for q in ph:
            for j, tm in enumerate((q["deb"] + 0.4, q["fin"] + 0.3) + ((q["fin"] + 1.0, GEL + 0.5) if q is ph[-1] else ())):
                cv2.imwrite(f"{sortie}/{q['i']:02d}{'abcd'[j]}.png", cv2.cvtColor((image(int(tm * FPS)) if os.environ.get("APERCU_PLEIN") == "1" else cv2.resize(image(int(tm * FPS)), (360, 640))), cv2.COLOR_RGB2BGR))
        return total

    # ---- son : voix, bruitages (woosh à chaque scène, rimshot à la chute finale)
    n = int(SRM * (total + 1)); mix = np.zeros((n, 2))
    if DOUB:                                                               # la bande son d'origine telle quelle (voix + musique)
        with wave.open(DOUB["piste"]) as w_:
            assert w_.getframerate() == SRM and w_.getnchannels() == 2, "piste de doublage : 2 canaux au bon échantillonnage attendus"
            b = np.frombuffer(w_.readframes(w_.getnframes()), np.int16).reshape(-1, 2).astype(np.float64) / 32768
        b = b[:int(SRM * (GEL + 1.1))]; f_ = int(0.6 * SRM)                 # fondu sur la fin (arrêt sur image puis signature)
        if len(b) > f_: b[-f_:] *= np.linspace(1, 0, f_)[:, None]
        mix[:len(b)] += b[:n]
    else:
        for q, a in zip(ph, audios):
            s0 = int(q["deb"] * SRM)
            if s0 >= n: continue                                           # aperçu 10 s : réplique après la coupure
            b = vers_mix(a)[:n - s0]; mix[s0:s0 + len(b)] += b
    for t0_, t1_, mode_, _sc in APPEL:                                     # voix au téléphone pendant les plans d'écoute (idée 16)
        if mode_ != "ecoute": continue
        a_, b_ = int(t0_ * SRM), min(n, int(t1_ * SRM))
        if b_ - a_ > SRM // 10:
            seg = mix[a_:b_].copy(); tel = SM.telephone(seg, SRM)
            f_ = min(len(seg) // 4, int(0.04 * SRM)); w_ = np.ones(len(seg)); w_[:f_] = np.linspace(0, 1, f_); w_[-f_:] = np.linspace(1, 0, f_)
            mix[a_:b_] = seg * (1 - w_[:, None]) + tel * w_[:, None]
    fx = np.zeros((n, 2))
    for t0_, t1_, _src in REMB:                                            # bruit de cassette qui rembobine (idée 22)
        a_ = int(t0_ * SRM); r_ = SM.rembobinage(t1_ - t0_, SRM); fx[a_:a_ + len(r_)] += r_[:max(0, n - a_)]
    def ajoute(nom, t_, g):
        x = SM.son(nom); s0 = int(max(0, t_) * SRM); e = min(n, s0 + len(x))
        if e > s0: fx[s0:e] += x[:e - s0] * g
    for tr in (() if DOUB else transitions):                              # changements de scène / de gag bien marqués
        ajoute("transition", tr[0] - 0.25, 0.8)
        if tr[2] == "carton": ajoute("pop", tr[0] + 0.05, 0.7)
    if mini:
        for k in TITRES: ajoute("pop", min(z2["deb"] for z2 in ph if z2["scene"] == k) - 0.2, 0.6)
    if not DOUB:                                                           # doublage : la bande son d'origine a déjà ses effets
        # bruitages « tendance » (vine boom, dun dun dun, klaxon, criquets, caisse…) : catalogue moteur/bruitages.py
        imposes = {}
        for b_ in ((sk.get("studio") or {}).get("bruitages") or []) if isinstance(sk.get("studio"), dict) else []:
            try: imposes[int(b_.get("replique"))] = str(b_.get("son"))
            except (AttributeError, TypeError, ValueError): pass
        BRUITAGES[:] = BR.choisir(ph, SILENCES if B else (), (B or {}).get("graine", len(sk.get("sujet", ""))), imposes, total, BR.densite_apprise())
        for nom, t_, g in BRUITAGES: ajoute(nom, t_, g)
    if not DOUB:
        d_m = len(SM.son("montee")) / SRM
        ajoute("montee", ph[-1]["deb"] - d_m, 0.5)                        # tension juste avant la chute finale
        ajoute("boom_fin", ph[-1]["fin"] + 0.02, 1.0)                     # gros impact sur la chute finale
        if len(places[ph[-1]["scene"]]) > 1: ajoute("boom_leger", ph[-1]["fin"] + 0.57, 0.5)   # celui qui encaisse tombe à la renverse
    amb = np.zeros((n, 2))                                                 # son « cinéma » : ambiance du lieu, pas, whoosh, musique
    def ajoute_x(x, t_, g, piste):
        s0 = int(max(0, t_) * SRM); e = min(n, s0 + len(x))
        if e > s0: piste[s0:e] += x[:e - s0] * g
    if B and CINE.get("son"):
        for sh_ in DECOUPE:                                                # passages rapides entre plans
            if sh_["passage"] == "file": ajoute_x(SM.swipe(), sh_["t0"] - 0.08, 0.3 if not DOUB else 0.15, fx)
            elif sh_["passage"] == "zoom": ajoute_x(SM.whoosh(0.35), sh_["t0"] - 0.12, 0.2 if not DOUB else 0.1, fx)
        for sc_, t_sc in DEBUT_SCENE.items():                              # bruits de pas quand ils entrent
            if sc_ not in SANS_ENTREE: ajoute_x(SM.pas(graine=sc_), t_sc, 0.3, fx)
        if not DOUB:                                                       # la bande son d'origine a déjà son ambiance et sa musique
            for sc_ in places:
                zs = [z2 for z2 in ph if z2["scene"] == sc_]
                if not zs: continue
                t0_, t1_ = min(z2["deb"] for z2 in zs) - 0.3, max(z2["fin"] for z2 in zs) + 0.8
                a_ = SM.ambiance(B["lieux"][min(sc_, len(B["lieux"]) - 1)], max(0.5, t1_ - t0_), graine=B["graine"] % 997 + sc_)
                f_ = min(len(a_) // 3, int(0.3 * SRM)); a_[:f_] *= np.linspace(0, 1, f_)[:, None]; a_[-f_:] *= np.linspace(1, 0, f_)[:, None]
                ajoute_x(a_, t0_, 1.0, amb)
            if {"pluie", "orage"} & set(B.get("ambiances") or ()):            # pluie et tonnerre (calé sur les éclairs)
                try: ajoute_x(SM.meteo(total, "orage" in B["ambiances"], graine=B["graine"] % 997), 0.0, 1.0, amb)
                except Exception as e_: print(f"son de pluie impossible : {e_}", flush=True)
            emos = [z2["emo"] for z2 in ph]
            humeur = ("tension" if sum(e in ("cri", "colere", "panique") for e in emos) >= 2 else "triste" if sum(e in ("pleurs", "triste", "soupir") for e in emos) >= 2
                      else "joie" if sum(e in ("rire", "joie", "amour") for e in emos) >= 2 else "neutre")
            ajoute_x(SM.musique(total, humeur, graine=B["graine"] % 997), 0.0, 0.5, amb)
    ajoute("pop", GEL, 0.5)                                                # arrêt sur image
    if FIN_CARTE is not None: ajoute("pop", FIN_CARTE, 0.6)
    voix_env = np.convolve(np.abs(mix[:, 0]), np.ones(int(0.15 * SRM)) / int(0.15 * SRM), "same")
    voix_env = np.clip(voix_env / (np.percentile(voix_env[voix_env > 1e-4], 90) + 1e-6) if (voix_env > 1e-4).any() else voix_env, 0, 1)
    mix = mix + fx * (1 - 0.5 * voix_env)[:, None] + amb * (1 - 0.6 * voix_env)[:, None]   # l'ambiance et la musique s'effacent quand on parle
    mix = np.clip(mix / max(1.0, np.abs(mix).max() / 0.95), -0.99, 0.99)
    brut, wav = f"{tmp}/mix.wav", f"{tmp}/mix_norm.wav"
    with wave.open(brut, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SRM); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", brut, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "2", wav], check=True)
    defauts_img = []
    try:                                                                   # contrôle image par image (gratuit) : têtes coupées,
        SONDE["on"] = True                                                 # personnages qui se chevauchent, sous-titre sur un visage
        for k_ in range(int(FIN / 0.5)):
            tm_ = 0.25 + 0.5 * k_
            if any(x[0] <= tm_ < x[1] for x in transitions): continue
            SONDE["res"] = []; vue(tm_); defauts_img += controle_image(SONDE["res"])
    except Exception as e: print(f"contrôle image impossible : {e}", flush=True)
    finally: SONDE["on"] = False
    if defauts_img: print(f"Contrôle image : {len(defauts_img)} défaut(s) — " + ", ".join(f"{d['t']} s {d['type']} ({d['role']})" for d in defauts_img[:8]), flush=True)
    RENDU.clear(); RENDU.update(defauts_image=defauts_img, ph=[{k: q.get(k) for k in ("i", "p", "deb", "fin", "texte", "emo", "chute", "scene", "plan", "mouvement", "reaction")} for q in ph],
                                plans=[{k: x.get(k) for k in ("t0", "t1", "scene", "cible", "plan", "mouvement", "passage", "i")} for x in DECOUPE],
                                fiches={r: {k: f.get(k) for k in ("genre", "age", "taille", "barbe", "cheveux")} for r, f in (FICHES or {}).items()},
                                places={k: list(v) for k, v in places.items()}, total=total, doublage=bool(DOUB), mini=mini, separes=SEPARES,
                                bruitages=list(BRUITAGES), lieux=list((B or {}).get("lieux") or []), compagnons=sum(len(v) for v in COMP.values()),
                                decors_ia=bool(decors), coupes_origine=list((B or {}).get("coupes_origine") or []))
    try:                                                                   # empreintes : redessin partiel d'une 2e version (jury)
        RENDU.update(fps=FPS, nf=nf, sig_plans=[(x["t0"], x["t1"], _sig(x)) for x in DECOUPE], sig_ph=[(q["deb"], q["fin"], _sig(q)) for q in ph],
                     sig_parts={k: _sig(v) for k, v in {"fiches": FICHES, "places": places, "comp": COMP, "transitions": transitions, **{"B." + k: v for k, v in (B or {}).items()}}.items()},
                     sig_global=_sig({"fiches": FICHES, "places": places, "lieux": (B or {}).get("lieux"), "comp": COMP, "sep": SEPARES, "total": total,
                                      "decors": sorted(str(k) for k in (decors or {})), "fin": FIN_CARTE, "gel": GEL, "w": W, "h": H, "mini": mini,
                                      "transitions": transitions, "studio": {k: v for k, v in (B or {}).items() if k not in ("decoupe", "plans", "bruitages", "source")}}))
    except Exception as e: print(f"empreintes impossibles ({str(e)[:100]}) : pas de redessin partiel", flush=True); RENDU["sig_global"] = None
    global _IMAGE
    _IMAGE = image                                                         # les processus de rendu héritent de tout (fork)
    n_proc = min(4, os.cpu_count() or 1) if os.environ.get("RENDU_PARALLELE", "1") != "0" else 1
    pool = None
    if n_proc > 1 and nf > 90:                                             # rendu sur plusieurs processeurs (images dans l'ordre)
        import multiprocessing as mp
        try:
            cv2.setNumThreads(1)                                           # avant de dupliquer le programme : pas de fil OpenCV en cours (sinon blocage)
            pool = mp.get_context("fork").Pool(n_proc)
        except Exception as e: print(f"  rendu parallèle impossible ({e}) : un seul processeur", flush=True); pool = None
    x264 = ["-c:v", "libx264", "-preset", (os.environ.get("PRESET_X264") or "slow"), "-tune", "animation",
            "-crf", (os.environ.get("CRF") or "15"), "-maxrate", "20M", "-bufsize", "30M", "-profile:v", "high", "-level", "4.2",
            "-g", str(2 * FPS), "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-pix_fmt", "yuv420p"]
    entree = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    morceaux = None                                                        # 2e version du jury : seulement les passages qui changent
    if reprise and os.path.exists(reprise.get("video") or "") and os.environ.get("REDESSIN_PARTIEL", "1") != "0":
        try:
            refaire = images_a_refaire(reprise.get("rendu"), RENDU, nf, FPS)
            if refaire is not None:
                morceaux = plages(refaire, _images_cles(reprise["video"], FPS), nf)
                n_ref = sum(b_ - a_ for a_, b_ in morceaux)
                if n_ref > 0.75 * nf: morceaux = None                      # presque tout change : rendu complet, plus simple
                else: print(f"  redessin partiel : {n_ref}/{nf} images à redessiner ({len(morceaux)} passage(s)), le reste repris tel quel", flush=True)
        except Exception as e: print(f"  redessin partiel impossible ({str(e)[:120]}) : rendu complet", flush=True); morceaux = None
    import progression, time as _time
    t_rendu = _time.time()
    if limite:                                                             # 2e version du jury : assez de temps avant la limite de GitHub ?
        v_ = float((reprise or {}).get("rendu", {}).get("vitesse") or 0)
        a_faire = nf if morceaux is None else sum(b_ - a_ for a_, b_ in morceaux)
        if v_ > 0 and t_rendu + a_faire / v_ * 1.15 > limite:
            if pool: pool.close(); pool.join()
            raise TempsDepasse(f"{a_faire} images à redessiner, environ {a_faire / v_ / 60:.0f} min : pas le temps avant la limite")
    if morceaux is None:
        ff = subprocess.Popen(entree + ["-i", wav] + x264 + ["-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", sortie], stdin=subprocess.PIPE)
        images = pool.imap(_image_octets, range(nf), chunksize=4) if pool else (image(fi).tobytes() for fi in range(nf))
        try:
            for fi, octets in enumerate(images):
                ff.stdin.write(octets)
                if fi % 300 == 0: print(f"  image {fi}/{nf}" + (f" ({n_proc} processeurs)" if pool and fi == 0 else ""), flush=True)
                if fi % 30 == 0: progression.rendu(fi, nf, t_rendu)      # barre de progression du site
                if limite and _time.time() > limite: raise TempsDepasse("plus le temps de finir la 2e version")
        except BaseException:
            ff.kill(); raise
        finally:
            if pool: pool.close(); pool.join()
        ff.stdin.close(); ff.wait()
        RENDU["vitesse"] = nf / max(1.0, _time.time() - t_rendu)            # images par seconde (sert à prévoir une 2e version)
        return total
    try:                                                                   # passages redessinés, encodés à part (mêmes réglages)
        n_ref, fait, liste = sum(b_ - a_ for a_, b_ in morceaux), 0, []
        for k_, (a_, b_) in enumerate(morceaux):
            seg = f"{tmp}/morceau_{k_}.mp4"
            ff = subprocess.Popen(entree + x264 + ["-an", seg], stdin=subprocess.PIPE)
            images = pool.imap(_image_octets, range(a_, b_), chunksize=4) if pool else (image(fi).tobytes() for fi in range(a_, b_))
            for octets in images:
                if limite and _time.time() > limite: ff.kill(); raise TempsDepasse("plus le temps de finir la 2e version")
                ff.stdin.write(octets); fait += 1
                if fait % 30 == 0: progression.rendu(fait, n_ref, t_rendu)
            ff.stdin.close(); ff.wait()
            if ff.returncode != 0: raise RuntimeError("encodage d'un passage en échec")
            liste.append((a_, seg))
    finally:
        if pool: pool.close(); pool.join()
    coupes = sorted({x for ab in morceaux for x in ab if 0 < x < nf})       # l'ancienne vidéo coupée net à ces images clés (sans réencoder)
    os.makedirs(f"{tmp}/ancien", exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", reprise["video"], "-map", "0:v", "-c", "copy", "-f", "segment",
                    "-segment_frames", ",".join(map(str, coupes)) or "999999999", "-reset_timestamps", "1", f"{tmp}/ancien/p_%04d.mp4"], check=True, timeout=600)
    bornes = [0] + coupes + [nf]; neufs = dict(liste); lignes = []
    for k_ in range(len(bornes) - 1):
        a_ = bornes[k_]
        lignes.append(f"file '{neufs[a_]}'" if a_ in neufs else f"file '{tmp}/ancien/p_{k_:04d}.mp4'")
    open(f"{tmp}/recollage.txt", "w").write("\n".join(lignes) + "\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{tmp}/recollage.txt", "-i", wav, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", sortie], check=True, timeout=900)
    return total

_IMAGE = None
def _image_octets(fi):
    """Une image de la vidéo en cours (appelée dans les processus de rendu)."""
    return _IMAGE(fi).tobytes()
