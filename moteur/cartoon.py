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
import marionnette as M, sons_modernes as SM, marque, studio, decor_dessin as DD, humain as HU
from jt import minutage, carton, son, vers_mix, enveloppe, poser, pop, W, H, FPS, SR, SRM, FB

CAP_Y = 1700
MINUTAGE = []                                                              # (début, fin, texte, qui) de la dernière vidéo : contrôle qualité
PH = []                                                                    # répliques de la dernière vidéo avec leur plan (mémoire du studio)
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
NEUTRE_BRAS = ((-18, 8), (18, -8))

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

# ------------------------------------------------------------------ rendu
def rendre(sk, sortie, audios, mots=None, decors=None, mini=False, apercu=False):
    tmp = tempfile.mkdtemp(); reps = sk["repliques"]; decors = decors or {}; rng = np.random.default_rng(11)
    roles = sorted({r["p"] for r in reps if r["p"] != "narrateur"}, key=lambda r: [x["p"] for x in reps].index(r))   # la voix off n'est pas dessinée
    # scènes : découpage de l'auteur (sinon une seule scène)
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
            t = float(r["_deb"]); lv = np.convolve(np.pad(lv, 2, mode="edge"), [0.1, 0.2, 0.4, 0.2, 0.1], "valid")
            sc = scene_de.get(i, ph[-1]["scene"] if ph else 0)
            if ph and sc != ph[-1]["scene"]:                               # changement de scène : panoramique dans le blanc entre deux répliques
                d0 = max(ph[-1]["fin"] + 0.05, t - 0.45)
                if t - d0 >= 0.2: transitions.append((d0, t - 0.02, "panoramique", sc, ""))
            emo_q = emo_de(i, r)
            rires = any(re.search(r"laugh|rire|giggl|chuckl", str(e_[2])) and e_[0] < t + dur + 0.6 and e_[1] > t for e_ in (DOUB.get("evenements") or []))
            ph.append(dict(i=i, p=r["p"], deb=t, fin=t + dur, lv=lv, emo=emo_q, chute=bool(r.get("chute")) or i == len(reps) - 1, rires=rires,
                           scene=sc, objet=r.get("objet"), teaser=False, texte=r["t"], geste=geste_texte(r["t"], emo_q, i),
                           groupes=minutage(r["t"], a, t, (mots or [None] * len(reps))[i])))
            continue
        if i == len(reps) - 1 and not att and i: att = 0.45                # un temps avant la chute finale
        t += att
        lv = np.convolve(np.pad(lv, 2, mode="edge"), [0.1, 0.2, 0.4, 0.2, 0.1], "valid")         # bouche lissée : pas de clignotement
        sc = scene_de.get(i, ph[-1]["scene"] if ph else 0)
        if ph and ph[-1].get("teaser"):                                     # après l'accroche : retour au début de l'histoire
            transitions.append((t, t + 0.9, "carton", sc, "Un peu plus tôt…")); t += 0.9
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
    nf = int(total * FPS)
    # placement : qui est dans chaque scène, à quelle place
    places = {}
    for q in ph: places.setdefault(q["scene"], [])
    for q in ph:
        if q["p"] != "narrateur" and q["p"] not in places[q["scene"]]: places[q["scene"]].append(q["p"])
    for k in places: places[k].sort(key=roles.index)                     # chacun garde son côté d'une scène à l'autre
    def position(scene, role):
        ps = places[scene]; n = len(ps); k = ps.index(role) if role in ps else 0
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
    AVANT, INFOS = {}, {}; FICHES = None; DECOUPE = []
    if B:
        studio.realiser(ph, places, B); sk["_bible"] = B
        DECOUPE = studio.decouper(ph, places, B, FPS) if os.environ.get("MONTAGE", "dynamique") != "simple" else []   # plusieurs plans par réplique
        if DECOUPE: print(f"montage : {len(DECOUPE)} plans (" + " ".join(f"{x['t0']:.1f}:{x['plan']}>{x['cible'][:3]}/{x['passage']}" for x in DECOUPE) + ")", flush=True)
        FICHES = B.get("fiches") if HUMAINS else None
        for sc_ in places:
            lieu = B["lieux"][min(sc_, len(B["lieux"]) - 1)]
            dd = DD.dessiner(lieu, B, graine=B["graine"] % 9973 + sc_)
            if dd.get("avant") is not None: AVANT[sc_] = dd["avant"]          # premier plan (comptoir, bureau, guichet) : aussi devant un décor IA
            if sc_ in decors: continue                                     # décor IA (mode payant) : gardé tel quel
            decors[sc_] = dd["fond"]; INFOS[sc_] = dd
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
                if f_["scene"] != sc_: continue
                f_["_x"] = libres[k_ % len(libres)]; f_["_s"] = 0.4 if len(places[sc_]) >= 3 else 0.46; k_ += 1
        rng_p = np.random.default_rng(B["graine"] % 99991)
        PARTICULES = rng_p.uniform(0, 1, (60, 4))                          # positions et vitesses (poussière, pluie, neige, vapeur)
    # animation des personnages : état par rôle
    clign = {r: sorted(rng.uniform(0.5, total, int(total / 2.6))) for r in roles}
    DEBUT_SCENE = {}
    for q in ph: DEBUT_SCENE.setdefault(q["scene"], q["deb"] - 0.1)
    COUVERTURE_MS[0] = int(max(0.5, ph[-1]["deb"] + 0.4) * 1000)           # image de couverture TikTok : la chute finale
    SANS_ENTREE = {ph[0]["scene"]}                                         # 1re scène : déjà là dès la première image (l'accroche compte)
    TITRE_FIXE = titre(sk.get("titre_accroche")) if not mini else None
    FILIGRANE = marque.filigrane(52)
    TITRES = {k: titre(sc.get("titre")) for k, sc in enumerate(dec) if sc.get("titre")}
    VOIX_OFF = {q["i"]: carte_titre(reps[q["i"]]["t"]) for q in ph if q["p"] == "narrateur"}
    objets = {}
    print(f"cartoon : durée {total:.1f} s, {len(ph)} répliques, {len(places)} scène(s), personnages {roles}", flush=True)

    def actif(tm):
        return next((x for x in reversed(ph) if x["deb"] - 0.25 <= tm), ph[0])

    ASSIS = (B or {}).get("assis") or {}
    CINE = (B or {}).get("cine") or {}                                     # effets « cinéma » de l'épisode (varient d'une vidéo à l'autre)
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
            if cam_regard: p.update(forme="coin" if (len(role) + int(tm)) % 2 else "neutre", sourcils="neutre")
        if recule:                                                         # recul face à quelqu'un qui crie
            xa = position(scene, q["p"])[0]; u_r = _ressort((tm - t_r) / 0.35) * (1 - _ease((tm - q["fin"] - 0.1) / 0.3))
            p["x"] += (-1 if xa > x else 1) * 26 * s * u_r; p["tilt"] += (-1 if xa > x else 1) * 6 * u_r
        # bouche synchronisée sur la voix
        if parle:
            k = int((tm - q["deb"]) * FPS); lv = float(q["lv"][k]) if 0 <= k < len(q["lv"]) else 0.0
            p["bouche"] = min(1.0, lv * 0.9) if emo != "cri" else 0.55 + 0.45 * min(1, lv)
            if emo == "rire": p["bouche"] = 0.4 + 0.4 * abs(math.sin(tm * 14))
            elif emo != "cri": p["viseme"] = viseme_a(q["groupes"], tm)
            p["sq"] = 0.03 * lv + 0.008 * math.sin(tm * 7)
            if emo == "neutre" and lv > 0.72: p["sourcils"] = "hausses"         # sourcils qui appuient les mots forts
            p["tilt"] = 5 * math.sin(tm * 1.9 + len(role)) + 3 * lv + (8 * math.sin(tm * 15) if emo == "rire" else 0)
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
            pg, pd = POSES[g_txt]; bg, bd = _mel(NEUTRE_BRAS[0], pg, u_g), _mel(NEUTRE_BRAS[1], pd, u_g)
            if g_txt == "haussement": p["y"] -= 10 * s * u_g; p["tilt"] += 7 * u_g; p["epaules"] = max(p.get("epaules", 0.0), u_g)
            if g_txt.startswith("pointe"): p["tilt"] += (5 if g_txt == "pointe_d" else -5) * u_g
        elif bg is None:
            if parle:
                per = 1.6 - 0.7 * float(((B or {}).get("rythme") or {}).get("energie", 0.3))   # vidéo d'origine agitée : gestes plus fréquents
                k_ = int((tm - q["deb"]) / per + q["i"]); u = _ressort(((tm - q["deb"]) % per) / 0.55); elan = u - _ease(((tm - q["deb"]) % per) / 0.55)
                g = GESTES[k_ % len(GESTES)]; g0 = GESTES[(k_ - 1) % len(GESTES)] if tm - q["deb"] >= per else ((-18, 8), (18, -8))
                mains = MAINS_CONV[k_ % len(MAINS_CONV)]
                if FICHES:                                                 # adultes : gestes de conversation plus mesurés
                    g, g0 = tuple((v[0] * 0.6, v[1] * 0.8) for v in g), tuple((v[0] * 0.6, v[1] * 0.8) for v in g0)
                bg, bd = _mel(g0[0], g[0], u), _mel(g0[1], g[1], u)
                fin_u = _ease((tm - q["fin"] + 0.3) / 0.3)                     # retour au repos en douceur à la fin de la phrase
                bg, bd = _mel(bg, (-18, 8), fin_u), _mel(bd, (18, -8), fin_u)
            else: bg, bd = (-18, 8), (18, -8)
        else:
            bg, bd = _mel((-18, 8), bg, u_emo), _mel((18, -8), bd, u_emo)
            if emo == "colere": bg, bd = (bg[0] + 10 * math.sin(tm * 18), bg[1]), (bd[0] - 10 * math.sin(tm * 18), bd[1])
        if parle and B and not g_txt:                                       # les mains « battent » sur les mots appuyés de la voix
            k_ = int((tm - q["deb"]) * FPS)
            for j_ in range(min(k_, len(q["lv"]) - 1), max(3, k_ - 9), -1):
                if q["lv"][j_] - q["lv"][j_ - 3] > 0.32:
                    b_ = math.sin(math.pi * min(1.0, (k_ - j_) / FPS / 0.3)); bd = (bd[0], bd[1] - 28 * b_); bg = (bg[0], bg[1] + 14 * b_); break
        p["bras_g"], p["bras_d"] = bg, bd
        p["main_forme_g"], p["main_forme_d"] = mains
        if B: duo(p, role, tm, q, scene, parle)                            # gestes à deux (tope, main sur l'épaule, donner, pousser)
        if B:                                                              # corps vivant : poids du corps, trois-quarts, cheveux et vêtements qui suivent
            autre_ = q["p"] if q["p"] != role else next((r2 for r2 in places[scene] if r2 != role), None)
            if autre_ in places[scene] and not cam_regard: p["tq"] = (0.35 if parle or q["p"] != role else 0.2) * (1 if position(scene, autre_)[0] > x else -1)
            p["hanche"] = (0.35 if parle else 0.55) * math.sin(tm * (0.8 if parle else 0.45) + len(role) * 1.3)
            p["balance"] = p.get("balance", 0.0) + 2.4 * elan
            p["sourcils_h"] = p.get("sourcils_h", 0.0) + 0.1 * math.sin(tm * 2.7 + len(role) * 2) + 0.05 * math.sin(tm * 6.1)
            if FICHES and ASSIS.get(scene) == role:                        # assis : il reste sur sa chaise
                p.update(assis=True, x=x + 4 * s * math.sin(tm * 0.6), y=y, hanche=0.0, marche=None)
        # regard vers celui qui parle (ou vers celui à qui on parle), petites saccades, clignements
        autre = q["p"] if q["p"] != role else next((r2 for r2 in places[scene] if r2 != role), None)
        if autre and autre in places[scene]:
            xa = position(scene, autre)[0]; p["regard"] = ((0.8 if xa > x else -0.8) + 0.12 * math.sin(tm * 0.7 + len(role)), 0.08 * math.sin(tm * 1.3))
        if B and cam_regard: p["regard"] = (0.0, 0.05); p["tilt"] *= 0.3   # il fixe la caméra
        if any(0 <= tm - c < 0.12 for c in clign[role]) and p["yeux"] == "ouverts": p["yeux"] = "fermes"
        # objet en main pendant la réplique
        if mien and mien.get("objet") and tm <= mien["fin"] + 0.3:
            o = objets.get((mien["objet"], round(s, 2)))
            if o is None: o = objets[(mien["objet"], round(s, 2))] = M.objet(mien["objet"], s * (0.5 if FICHES else 1.0))
            if o is not None: p["main_d"] = o; p["bras_d"] = (120, -100); p["main_forme_d"] = "poing"
        return p

    global COUVERTURE                                                      # couverture : titre visible et visage le plus expressif
    fortes = [z for z in ph if z["emo"] in ("choc", "cri", "colere", "panique", "rire", "joie") and z["p"] != "narrateur"]
    if ph and ph[0]["p"] == "narrateur" and mini: COUVERTURE = ph[0]["deb"] + 0.6
    elif fortes: COUVERTURE = t_reaction(fortes[0]) + 0.15
    else: COUVERTURE = (ph[-1]["fin"] + 0.45) if ph else 1.0
    COUVERTURE = round(float(COUVERTURE), 2)
    CARTES = {k: carte(tr[4]) for k, tr in enumerate(transitions) if tr[2] == "carton"}
    GELEE = {}

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
        x = x0 + (math.sin(tm * 0.25 + k) * 60 if act == "marche" else 6 * math.sin(tm * 0.9 + k)); y = 1265
        p.update(x=W / 2 + (x - cxb) * zb, y=H / 2 + (y - cyb) * zb, s=f.get("_s", 0.5) * zb, t=tm, costume=f["costume"], reflets=True, lumiere=B["lumiere"],
                 ombre=B["ombre"], mains=True, tilt=4 * math.sin(tm * 0.7 + k), regard=(math.sin(tm * 0.4 + k) * 0.8, 0.1),
                 balance=0.5 * math.sin(tm * 2 + k))
        cyc = (tm * 0.35 + k) % 1
        if act in ("boit", "mange"):
            lev = _ease(min(1, cyc / 0.15)) * (1 - _ease(max(0, cyc - 0.35) / 0.15)) if cyc < 0.5 else 0.0
            p["bras_d"] = _mel((60, 80), (150, 75), lev); p["main_d"] = objets.setdefault((act, round(p["s"], 2)), M.objet("verre" if act == "boit" else "croissant", p["s"] * (0.6 if FICHES else 1.0)))
            p["main_forme_d"] = "poing"; p["bouche"] = 0.3 * lev
        elif act == "telephone":
            p["bras_d"] = POSES["telephone"][1]; p["main_forme_d"] = "poing"; p["bouche"] = 0.4 * abs(math.sin(tm * 7 + k)) if (tm + k) % 4 < 2.5 else 0.0
            p["viseme"] = "A" if p["bouche"] > 0.2 else None
        elif act == "tape":
            p["bras_g"], p["bras_d"] = (-40, 90 + 8 * math.sin(tm * 17)), (40, -90 + 8 * math.sin(tm * 19 + 1)); p["regard"] = (0.0, 0.6)
        elif act == "souleve":
            u = abs(math.sin(tm * 1.6 + k)); p["bras_g"], p["bras_d"] = (-60 - 100 * u, -40), (60 + 100 * u, 40)
            p["main_g"] = p["main_d"] = objets.setdefault(("haltere", round(p["s"], 2)), M.objet("haltere", p["s"] * (0.45 if FICHES else 0.7))); p["sq"] = -0.05 * u
        elif act == "cherche":
            p["regard"] = (math.sin(tm * 0.8 + k), -0.3); p["tilt"] = 10 * math.sin(tm * 0.8 + k); p["bras_d"] = (60, 40); p["main_forme_d"] = "index"
        if any(0 <= ((tm + k * 3) % 3.7) < 0.12 for _ in (0,)): p["yeux"] = "fermes"
        if FICHES and f.get("fiche"): p["s"] *= 1.15; HU.dessiner(img, f["fiche"], p)
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

    def vue(tm):
        q = actif(tm); sc = q["scene"]
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
                elif sh["passage"] == "zoom": flou_h = 0.35 * math.sin(math.pi * u_p)
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
        if q is ph[-1]:                                                    # chute finale : lent zoom dramatique pendant toute la réplique
            z *= 1 + 0.16 * _ease((tm - q["deb"]) / max(0.5, q["fin"] - q["deb"]))
            if tm > q["fin"]: z *= 1 + 0.08 * _ease((tm - q["fin"]) / 0.12)                            # punch final
            if tm > q["fin"] + 0.2 and len(places[sc]) > 1:                # puis plan large pour voir la réaction (chute à la renverse)
                u_l = _ease((tm - q["fin"] - 0.2) / 0.35); z = z + (1.0 - z) * u_l; cx = cx + (W / 2 - cx) * u_l; cy = cy + (H / 2 - cy) * u_l
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
        Mx = np.float32([[zb, 0, W / 2 - zb * cxb], [0, zb, H / 2 - zb * cyb]])
        img = cv2.warpAffine(fond, Mx, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        if B:
            for f_ in B["figurants"]:
                if f_["scene"] == sc: figurant(f_, tm, img, zm, cxm, cym)
            if z > 1.3: img = cv2.GaussianBlur(img, (0, 0), min(4.5, 6 * (z - 1.1)))   # flou d'arrière-plan sur les plans serrés
        sce = dec[sc] if sc < len(dec) else {}
        if sce.get("effet") == "tremblement" or (q["emo"] in ("cri", "colere") and q["deb"] <= tm <= q["fin"]):
            img = np.roll(img, (int(6 * math.sin(tm * 53)), int(6 * math.cos(tm * 47))), (0, 1))
        for role in places[sc]:                                            # personnages dessinés nets à l'échelle du plan
            p = pose(role, tm, q, sc)
            p["x"], p["y"], p["s"] = W / 2 + (p["x"] - cx) * z, H / 2 + (p["y"] - cy) * z, p["s"] * z
            ang, ko = chute_au_sol(role, tm, sc)
            if ko:                                                         # KO : écrasé, yeux en croix, étoiles
                p["sq"] = max(p["sq"], 0.28 * ko); p["yeux"] = "plisses"; p["forme"] = "o"; p["bouche"] = 0.2
                p["effets"] = tuple(set(p["effets"]) | {"etoiles"}); p["bras_g"], p["bras_d"] = (-60, 20), (60, -20)
            if not -400 < p["x"] < W + 400: continue
            flou_p = 0.0
            if B and CINE.get("focus") and len(places[sc]) > 1 and plan_courant in ("moyen", "large") and not ang and q["p"] in places[sc] and role != q["p"]:
                flou_p = 3.2 * _ease((tm - q["deb"] + 0.05) / 0.35)                # mise au point sur celui qui parle : l'autre devient flou
            if flou_p > 0.3:
                calque = np.empty_like(img); calque[:] = (1, 2, 3); dessine(calque, role, p)
                m_ = cv2.GaussianBlur((np.abs(calque.astype(np.int16) - (1, 2, 3)).sum(2) > 9).astype(np.float32), (0, 0), flou_p)[..., None]
                calque = cv2.GaussianBlur(calque, (0, 0), flou_p).astype(np.float32)
                img[:] = (img * (1 - m_) + calque * m_).astype(np.uint8); continue
            if not ang: dessine(img, role, p); continue
            calque = np.empty_like(img); calque[:] = (1, 2, 3); dessine(calque, role, p)
            R_ = cv2.getRotationMatrix2D((p["x"], p["y"]), -ang, 1.0)
            calque = cv2.warpAffine(calque, R_, (W, H), flags=cv2.INTER_LINEAR, borderValue=(1, 2, 3))
            m_ = (np.abs(calque.astype(np.int16) - (1, 2, 3)).sum(2) > 9)[..., None]; img[:] = np.where(m_, calque, img)
        if B and plan_courant == "epaule" and dans_q and ecoutant(q) and (sh is None or sh["cible"] == q["p"]):   # l'autre, de dos, flou, en amorce
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
                k_ = int(5 + 120 * flou_h) | 1; img = cv2.blur(img, (k_, 1 if sh["passage"] == "file" else k_ // 3 | 1))
        if B and sc in AVANT_FLOU and z > 1.25:                            # 3e couche : feuillage flou au tout premier plan
            za = z * 1.15; cxa, cya = W / 2 + (cx - W / 2) * 1.15, H / 2 + (cy - H / 2) * 1.05
            Ma = np.float32([[za, 0, W / 2 - za * cxa], [0, za, H / 2 - za * cya]])
            c_, m_ = AVANT_FLOU[sc]; ca = cv2.warpAffine(c_, Ma, (W, H)); ma = cv2.warpAffine(m_, Ma, (W, H))[..., None] * 0.95
            img = (img * (1 - ma) + ca * ma).astype(np.uint8)
        if B: img = cv2.multiply(img, GRADE, scale=1 / 255)                 # étalonnage de l'heure + vignettage (avant les textes)
        if B and CINE.get("etalonnage"):                                    # couleur de l'émotion (chaude, froide, rouge), en fondu
            j_ = ph.index(q); t_a = TEINTES.get(q["emo"], (1.0, 1.0, 1.0))
            t_p = TEINTES.get(ph[j_ - 1]["emo"], (1.0, 1.0, 1.0)) if j_ else (1.0, 1.0, 1.0); u_t = _ease((tm - q["deb"] + 0.2) / 0.5)
            t3 = tuple(a + (b - a) * u_t for a, b in zip(t_p, t_a))
            if max(abs(v - 1) for v in t3) > 0.005: img = cv2.LUT(img, teinte_lut(t3))
        if REFLET is not None and sh is not None and sh["passage"] == "coupe" and int(sh["t0"] * 7) % 3 == 0 and tm - sh["t0"] < 0.7:
            img = cv2.add(img, (REFLET * math.sin(math.pi * (tm - sh["t0"]) / 0.7)).astype(np.uint8))   # reflet de lumière chaude
        if GRAIN: img = cv2.subtract(cv2.add(img, GRAIN[int(tm * FPS) % 3]), (4, 4, 4, 0))
        fr = img.astype(np.float32)
        if q["p"] == "narrateur" and tm <= q["fin"] + 0.3:                 # voix off : le titre en grand au centre à l'ouverture,
            V = VOIX_OFF[q["i"]]; a2 = pop(V, (tm - q["deb"] + 0.2) / 0.3)   # en haut de l'image ensuite (jamais sur les têtes)
            poser(fr, a2, (W - a2.shape[1]) / 2, (H * 0.36 - a2.shape[0] / 2) if q is ph[0] else 300)
            if q is not ph[0]: poser(fr, FILIGRANE, 28, 118)
            return np.clip(fr, 0, 255).astype(np.uint8)
        poser(fr, FILIGRANE, 28, 118)                                     # signature discrète de la chaîne
        T = TITRES.get(sc) if mini else TITRE_FIXE
        if T is not None:
            t0 = min(z2["deb"] for z2 in ph if z2["scene"] == sc) if mini else 0
            d_t = tm - t0
            if not mini or d_t < 3.2:                                      # carton de scène : 3 s puis il s'efface (il ne cache pas les visages)
                a2 = pop(T, (d_t + 0.25) / 0.25)
                if mini and d_t > 2.7: a2 = a2.copy(); a2[..., 3] *= max(0.0, (3.2 - d_t) / 0.5)
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
                cv2.imwrite(f"{sortie}/{q['i']:02d}{'abcd'[j]}.png", cv2.cvtColor(cv2.resize(image(int(tm * FPS)), (360, 640)), cv2.COLOR_RGB2BGR))
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
            b = vers_mix(a); s0 = int(q["deb"] * SRM); mix[s0:s0 + len(b)] += b[:n - s0]
    fx = np.zeros((n, 2))
    def ajoute(nom, t_, g):
        x = SM.son(nom); s0 = int(max(0, t_) * SRM); e = min(n, s0 + len(x))
        if e > s0: fx[s0:e] += x[:e - s0] * g
    for tr in (() if DOUB else transitions):                              # changements de scène / de gag bien marqués
        ajoute("transition", tr[0] - 0.25, 0.8)
        if tr[2] == "carton": ajoute("pop", tr[0] + 0.05, 0.7)
    if mini:
        for k in TITRES: ajoute("pop", min(z2["deb"] for z2 in ph if z2["scene"] == k) - 0.2, 0.6)
    for j, q in enumerate([] if DOUB else ph[:-1]):                       # doublage : la bande son d'origine a déjà ses effets
        if q["chute"]: ajoute("boom_leger", q["fin"] + 0.05, 0.4)          # vanne en route : impact léger (pas de rires enregistrés)
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
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", sortie], stdin=subprocess.PIPE)
    images = pool.imap(_image_octets, range(nf), chunksize=4) if pool else (image(fi).tobytes() for fi in range(nf))
    try:
        for fi, octets in enumerate(images):
            ff.stdin.write(octets)
            if fi % 300 == 0: print(f"  image {fi}/{nf}" + (f" ({n_proc} processeurs)" if pool and fi == 0 else ""), flush=True)
    finally:
        if pool: pool.close(); pool.join()
    ff.stdin.close(); ff.wait()
    return total

_IMAGE = None
def _image_octets(fi):
    """Une image de la vidéo en cours (appelée dans les processus de rendu)."""
    return _IMAGE(fi).tobytes()
