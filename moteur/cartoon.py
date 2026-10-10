"""Moteur vidéo « cartoon » : uniquement pour les sketchs libres et les gags éclair (le JT garde jt.py).

Les personnages (marionnette.py) sont animés image par image : bouche synchronisée sur la voix, clignements, regard vers
celui qui parle, émotions lues dans les indications de jeu ([laughs], [angry], [cries]…), gestes, réactions aux chutes.
Mise en scène façon TikTok : décor du quotidien, plans serrés qui alternent sur celui qui parle, plan large à chaque scène,
titre « POV » en haut dans un cadre blanc, sous-titres mot par mot, bruitages.

rendre(sk, sortie, audios, mots=None, decors=None, mini=False) -> durée (s)
  decors : {indice de scène: image RGB 1080x1920} (générées par Stable Diffusion XL) ; sinon décor uni pastel."""
import math, os, re, subprocess, sys, tempfile, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ICI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ICI)
import marionnette as M, sons_modernes as SM, marque
from jt import minutage, carton, son, vers_mix, enveloppe, poser, pop, W, H, FPS, SR, SRM, FB

CAP_Y = 1700
MINUTAGE = []                                                              # (début, fin, texte, qui) de la dernière vidéo : contrôle qualité
PASTELS = [(246, 228, 214), (226, 236, 246), (236, 246, 226), (248, 232, 240), (250, 242, 214)]

# ------------------------------------------------------------------ émotions lues dans les indications de jeu
EMOTIONS = [("rire", r"laugh|giggl|chuckl|rire"), ("cri", r"shout|yell|scream|cri"), ("colere", r"angr|annoy|furious|irrit|mad|col[eè]re"),
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
}
GESTES = [((-20, 10), (100, -40)), ((-100, 40), (20, -10)), ((-110, -30), (110, 30)), ((-20, 10), (150, -10)), ((-40, 80), (40, -80))]
# poses expressives (bras gauche, bras droit) : angles épaule / coude en degrés, 0 = vers le bas
POSES = {
    "croises":    ((22, 72), (-22, -72)),          # bras croisés : blasé, fier, « j'attends »
    "haussement": ((-45, -85), (45, 85)),          # haussement d'épaules, paumes vers le ciel : « bah quoi ? »
    "desespoir":  ((-165, -45), (165, 45)),        # bras levés vers la tête : désespoir, panique
    "pointe_d":   ((-18, 8), (98, -6)),            # doigt pointé vers la droite : accusation
    "pointe_g":   ((-98, 6), (18, -8)),            # vers la gauche
    "poing":      ((-18, 8), (150, -130)),         # poing levé : victoire, colère
}
NEUTRE_BRAS = ((-18, 8), (18, -8))

def geste_texte(texte, emo):
    """Geste choisi d'après la réplique (ponctuation, mots) quand l'émotion n'impose rien."""
    t = (texte or "").lower()
    if emo in ("blase", "fier"): return "croises"
    if emo in ("pleurs", "panique"): return "desespoir"
    if emo in ("colere", "cri") and "!" in t: return "pointe"
    if re.search(r"\b(toi|tu|t'|vous)\b", t) and "!" in t: return "pointe"
    if t.rstrip().endswith("?") and re.search(r"\b(quoi|pourquoi|comment|hein)\b", t): return "haussement"
    if re.search(r"\b(gagné|yes|enfin|trop fort)\b", t): return "poing"
    return None

def _ease(u): u = min(1, max(0, u)); return u * u * (3 - 2 * u)

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
    for i, (r, a) in enumerate(zip(reps, audios)):
        niv, lv = enveloppe(a); dur = len(a) / SR; att = float(r.get("attente", 0))
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
        emo_q = emotion(r.get("d"))
        q = dict(i=i, p=r["p"], deb=t, fin=t + dur, lv=lv, emo=emo_q, chute=(bool(r.get("chute")) or i == len(reps) - 1) and not r.get("teaser"),
                 scene=sc, objet=r.get("objet"), teaser=r.get("teaser") is not None, texte=r["t"], geste=geste_texte(r["t"], emo_q),
                 groupes=minutage(r["t"], a, t, (mots or [None] * len(reps))[i]))
        ph.append(q)
        vif = emo_q in ("cri", "colere", "panique")                         # dispute : les répliques s'enchaînent sans blanc
        t += dur + (0.5 if q["chute"] and i < len(reps) - 1 else 0.05 if vif else 0.16)
    FIN = ph[-1]["fin"]
    GEL = FIN + 1.15                                                       # arrêt sur image après la réaction finale
    total = GEL + 1.1
    FIN_CARTE = None
    if not mini and total < 61.5:                                          # vidéo longue : plus d'une minute (rémunération TikTok)
        FIN_CARTE = total; total = 61.5
    elif mini:                                                             # gag éclair : signature de la chaîne (1,3 s)
        FIN_CARTE = total; total += 1.3
    MINUTAGE[:] = [(q["deb"], q["fin"], q["texte"], {"presentateur": "Jojo", "invite": "Kévin", "envoyee": "Lila"}.get(q["p"], "voix off"))
                   for q in ph if not q["teaser"] and q["p"] != "narrateur"]
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
    # animation des personnages : état par rôle
    clign = {r: sorted(rng.uniform(0.5, total, int(total / 2.6))) for r in roles}
    TITRE_FIXE = titre(sk.get("titre_accroche")) if not mini else None
    FILIGRANE = marque.filigrane(52)
    TITRES = {k: titre(sc.get("titre")) for k, sc in enumerate(dec) if sc.get("titre")}
    VOIX_OFF = {q["i"]: carte_titre(reps[q["i"]]["t"]) for q in ph if q["p"] == "narrateur"}
    objets = {}
    print(f"cartoon : durée {total:.1f} s, {len(ph)} répliques, {len(places)} scène(s), personnages {roles}", flush=True)

    def actif(tm):
        return next((x for x in reversed(ph) if x["deb"] - 0.25 <= tm), ph[0])

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
        # celui qui écoute réagit à l'émotion de celui qui parle
        recule = 0.0
        if not parle and q["p"] != role and q["p"] in places[scene] and q["deb"] + 0.3 <= tm <= q["fin"] + 0.4 and emo == "neutre":
            if q["emo"] in ("cri", "colere"): emo = "panique" if (len(role) + q["i"]) % 2 else "choc"; recule = 1.0
            elif q["emo"] == "pleurs": emo = "blase"
            elif q["emo"] in ("rire", "joie") and (len(role) + q["i"]) % 2: emo = "rire"
        yeux, sour, forme, bg, bd, eff, roug, trem = STYLE.get(emo, STYLE["neutre"])
        p.update(yeux=yeux, sourcils=sour, forme=forme, effets=eff, rougeur=roug, tremble=trem, joues=emo in ("rire", "joie"))
        if recule:                                                         # recul face à quelqu'un qui crie
            xa = position(scene, q["p"])[0]; u_r = _ease((tm - q["deb"] - 0.3) / 0.3) * (1 - _ease((tm - q["fin"] - 0.1) / 0.3))
            p["x"] += (-1 if xa > x else 1) * 26 * s * u_r; p["tilt"] += (-1 if xa > x else 1) * 6 * u_r
        # bouche synchronisée sur la voix
        if parle:
            k = int((tm - q["deb"]) * FPS); lv = float(q["lv"][k]) if 0 <= k < len(q["lv"]) else 0.0
            p["bouche"] = min(1.0, lv * 0.9) if emo != "cri" else 0.55 + 0.45 * min(1, lv)
            if emo == "rire": p["bouche"] = 0.4 + 0.4 * abs(math.sin(tm * 14))
            p["sq"] = 0.03 * lv + 0.008 * math.sin(tm * 7)
            if emo == "neutre" and lv > 0.72: p["sourcils"] = "hausses"         # sourcils qui appuient les mots forts
            p["tilt"] = 5 * math.sin(tm * 1.9 + len(role)) + 3 * lv + (8 * math.sin(tm * 15) if emo == "rire" else 0)
            u_d = (tm - q["deb"]) / 0.3
            if 0 <= u_d < 1: p["y"] -= 16 * s * math.sin(math.pi * u_d)            # petit élan quand il prend la parole
        else:
            p["bouche"] = 0.0 if emo not in ("choc", "panique") else 0.25
            p["sq"] = 0.012 * math.sin(tm * 2.4 + len(role))                  # respiration
            p["tilt"] = 3 * math.sin(tm * 0.9 + len(role))
        p["x"] += 7 * s * math.sin(tm * 1.1 + len(role) * 1.7)                # balancement continu : le personnage vit
        if emo == "rire": p["y"] -= abs(math.sin(tm * 12)) * 18 * s
        if emo == "joie": p["y"] -= abs(math.sin(tm * 8)) * 40 * s
        if emo == "soupir": p["sq"] -= 0.05
        # gestes : ceux de l'émotion, sinon gestes de conversation qui changent toutes les ~1,2 s
        g_txt = (q["geste"] if parle else None) or (mien["geste"] if (mien and mien["geste"] in ("croises",) and tm <= mien["fin"] + 0.6) else None)
        if g_txt:                                                          # geste expressif tiré de la réplique (bras croisés, doigt pointé…)
            if g_txt == "pointe":
                cible = next((r2 for r2 in places[scene] if r2 != role), None)
                g_txt = "pointe_d" if cible and position(scene, cible)[0] > x else "pointe_g"
            src = mien if mien else q; u_g = _ease((tm - src["deb"] + 0.1) / 0.35) * (1 - _ease((tm - src["fin"] - 0.35) / 0.35))
            pg, pd = POSES[g_txt]; bg, bd = _mel(NEUTRE_BRAS[0], pg, u_g), _mel(NEUTRE_BRAS[1], pd, u_g)
            if g_txt == "haussement": p["y"] -= 10 * s * u_g; p["tilt"] += 7 * u_g
            if g_txt.startswith("pointe"): p["tilt"] += (5 if g_txt == "pointe_d" else -5) * u_g
        elif bg is None:
            if parle:
                per = 1.6; k_ = int((tm - q["deb"]) / per + q["i"]); u = _ease(((tm - q["deb"]) % per) / 0.45)
                g = GESTES[k_ % len(GESTES)]; g0 = GESTES[(k_ - 1) % len(GESTES)] if tm - q["deb"] >= per else ((-18, 8), (18, -8))
                bg, bd = _mel(g0[0], g[0], u), _mel(g0[1], g[1], u)
                fin_u = _ease((tm - q["fin"] + 0.3) / 0.3)                     # retour au repos en douceur à la fin de la phrase
                bg, bd = _mel(bg, (-18, 8), fin_u), _mel(bd, (18, -8), fin_u)
            else: bg, bd = (-18, 8), (18, -8)
        else:
            bg, bd = _mel((-18, 8), bg, u_emo), _mel((18, -8), bd, u_emo)
            if emo == "colere": bg, bd = (bg[0] + 10 * math.sin(tm * 18), bg[1]), (bd[0] - 10 * math.sin(tm * 18), bd[1])
        p["bras_g"], p["bras_d"] = bg, bd
        # regard vers celui qui parle (ou vers celui à qui on parle), petites saccades, clignements
        autre = q["p"] if q["p"] != role else next((r2 for r2 in places[scene] if r2 != role), None)
        if autre and autre in places[scene]:
            xa = position(scene, autre)[0]; p["regard"] = ((0.8 if xa > x else -0.8) + 0.12 * math.sin(tm * 0.7 + len(role)), 0.08 * math.sin(tm * 1.3))
        if any(0 <= tm - c < 0.12 for c in clign[role]) and p["yeux"] == "ouverts": p["yeux"] = "fermes"
        # objet en main pendant la réplique
        if mien and mien.get("objet") and tm <= mien["fin"] + 0.3:
            o = objets.get((mien["objet"], round(s, 2)))
            if o is None: o = objets[(mien["objet"], round(s, 2))] = M.objet(mien["objet"], s)
            if o is not None: p["main_d"] = o; p["bras_d"] = (120, -100)
        return p

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
            if "fin" not in CARTES: CARTES["fin"] = marque.signature(W, H, "Abonne-toi pour la suite !" if not mini else "Abonne-toi !")
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
        if tm > FIN:                                                       # impact final : secousse qui s'amortit
            v = math.exp(-(tm - FIN) * 5) * 22
            fr = np.roll(fr, (int(v * math.sin(tm * 61)), int(v * math.cos(tm * 53))), (0, 1))
        return fr

    def cadre(q):
        if q["cam"] == "serre" and q["p"] in places[q["scene"]]: return 1.5, position(q["scene"], q["p"])[0], 1130.0
        return 1.0, W / 2, H / 2

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
        """Sur la chute finale, celui qui l'encaisse tombe à la renverse (angle en degrés, 0 = debout)."""
        z = ph[-1]
        if scene != z["scene"] or role == z["p"] or tm < z["fin"] + 0.25: return 0.0
        victime = next((r2 for r2 in places[scene] if r2 != z["p"]), None)
        if role != victime: return 0.0
        u = (tm - z["fin"] - 0.25) / 0.32; sens = 1 if position(scene, role)[0] < W / 2 else -1   # tombe vers le centre : reste dans le cadre
        a = 84 * u * u if u < 1 else 84 - 10 * math.exp(-(u - 1) * 6) * abs(math.sin((u - 1) * 14))   # petit rebond au sol
        return sens * min(84, a)

    def vue(tm):
        q = actif(tm); sc = q["scene"]
        fond = decors.get(sc)
        if fond is None: fond = decors[sc] = decor_uni(sc)
        # caméra : glisse en douceur d'un plan au suivant dans la même scène (pas de coupe sèche)
        z, cx, cy = cadre(q)
        j = ph.index(q)
        if j and ph[j - 1]["scene"] == sc:
            z0, cx0, cy0 = cadre(ph[j - 1]); u = _ease((tm - (q["deb"] - 0.3)) / 0.45)
            z, cx, cy = z0 + (z - z0) * u, cx0 + (cx - cx0) * u, cy0 + (cy - cy0) * u
        u0 = min(1, (tm - max(q["deb"] - 0.25, 0)) / 0.3); z *= 1 + 0.04 * (1 - u0) ** 2 + 0.006 * (tm - q["deb"])   # punch-in puis lente dérive
        if q is ph[-1]:                                                    # chute finale : lent zoom dramatique pendant toute la réplique
            z *= 1 + 0.16 * _ease((tm - q["deb"]) / max(0.5, q["fin"] - q["deb"]))
            if tm > q["fin"]: z *= 1 + 0.08 * _ease((tm - q["fin"]) / 0.12)                            # punch final
            if tm > q["fin"] + 0.2 and len(places[sc]) > 1:                # puis plan large pour voir la réaction (chute à la renverse)
                u_l = _ease((tm - q["fin"] - 0.2) / 0.35); z = z + (1.0 - z) * u_l; cx = cx + (W / 2 - cx) * u_l; cy = cy + (H / 2 - cy) * u_l
        elif q["chute"] and tm > q["fin"] - 0.6: z *= 1 + 0.12 * _ease((tm - q["fin"] + 0.6) / 0.2)
        zr, cible = reaction(tm)
        if cible and zr["scene"] == sc and len(places[sc]) > 1 and zr is not ph[-1]:   # coupe sèche sur la réaction
            z, cx, cy = 1.55, position(sc, cible)[0], 1120.0
        cx = min(max(cx, W / (2 * z)), W - W / (2 * z)); cy = min(max(cy, H / (2 * z)), H - H / (2 * z))
        Mx = np.float32([[z, 0, W / 2 - z * cx], [0, z, H / 2 - z * cy]])
        img = cv2.warpAffine(fond, Mx, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        sce = dec[sc] if sc < len(dec) else {}
        if sce.get("effet") == "tremblement" or (q["emo"] in ("cri", "colere") and q["deb"] <= tm <= q["fin"]):
            img = np.roll(img, (int(6 * math.sin(tm * 53)), int(6 * math.cos(tm * 47))), (0, 1))
        for role in places[sc]:                                            # personnages dessinés nets à l'échelle du plan
            p = pose(role, tm, q, sc)
            p["x"], p["y"], p["s"] = W / 2 + (p["x"] - cx) * z, H / 2 + (p["y"] - cy) * z, p["s"] * z
            ang = chute_au_sol(role, tm, sc)
            if not -400 < p["x"] < W + 400: continue
            if not ang: M.dessiner(img, M.ROLES.get(role, "bonnet"), p); continue
            calque = np.empty_like(img); calque[:] = (1, 2, 3); M.dessiner(calque, M.ROLES.get(role, "bonnet"), p)
            R_ = cv2.getRotationMatrix2D((p["x"], p["y"]), -ang, 1.0)
            calque = cv2.warpAffine(calque, R_, (W, H), flags=cv2.INTER_LINEAR, borderValue=(1, 2, 3))
            m_ = (np.abs(calque.astype(np.int16) - (1, 2, 3)).sum(2) > 9)[..., None]; img[:] = np.where(m_, calque, img)
        if sce.get("effet") == "pluie_billets":
            t0 = min(z2["deb"] for z2 in ph if z2["scene"] == sc); _pluie(img, tm, t0, sc)
        fr = img.astype(np.float32)
        if q["p"] == "narrateur" and tm <= q["fin"] + 0.3:                 # voix off d'ouverture : le titre en grand au centre
            V = VOIX_OFF[q["i"]]; a2 = pop(V, (tm - q["deb"] + 0.2) / 0.3)
            poser(fr, a2, (W - a2.shape[1]) / 2, H * 0.36 - a2.shape[0] / 2)
            return np.clip(fr, 0, 255).astype(np.uint8)
        poser(fr, FILIGRANE, 28, 118)                                     # signature discrète de la chaîne
        T = TITRES.get(sc) if mini else TITRE_FIXE
        if T is not None:
            t0 = min(z2["deb"] for z2 in ph if z2["scene"] == sc) if mini else 0
            a2 = pop(T, (tm - t0 + 0.25) / 0.25); poser(fr, a2, (W - a2.shape[1]) / 2, 190)
        g = next((x for x in q["groupes"] if x[1] <= tm < x[2] + (0.2 if x is q["groupes"][-1] else 0)), None)
        if g and q["deb"] <= tm < q["fin"] + 0.2:
            cc = pop(carton(g[0]), (tm - g[1]) / 0.12); poser(fr, cc, (W - cc.shape[1]) / 2, CAP_Y - cc.shape[0] / 2)
        return np.clip(fr, 0, 255).astype(np.uint8)

    if apercu:
        os.makedirs(sortie, exist_ok=True)
        for q in ph:
            for j, tm in enumerate((q["deb"] + 0.4, q["fin"] + 0.3)):
                cv2.imwrite(f"{sortie}/{q['i']:02d}{'ab'[j]}.png", cv2.cvtColor(cv2.resize(image(int(tm * FPS)), (360, 640)), cv2.COLOR_RGB2BGR))
        return total

    # ---- son : voix, bruitages (woosh à chaque scène, rimshot à la chute finale)
    n = int(SRM * (total + 1)); mix = np.zeros((n, 2))
    for q, a in zip(ph, audios):
        b = vers_mix(a); s0 = int(q["deb"] * SRM); mix[s0:s0 + len(b)] += b[:n - s0]
    fx = np.zeros((n, 2)); public = np.zeros((n, 2))
    def ajoute(nom, t_, g, piste=None):
        x = SM.son(nom); s0 = int(max(0, t_) * SRM); e = min(n, s0 + len(x)); p_ = fx if piste is None else piste
        if e > s0: p_[s0:e] += x[:e - s0] * g
    for tr in transitions:                                                 # changements de scène / de gag bien marqués
        ajoute("transition", tr[0] - 0.25, 0.8)
        if tr[2] == "carton": ajoute("pop", tr[0] + 0.05, 0.7)
    if mini:
        for k in TITRES: ajoute("pop", min(z2["deb"] for z2 in ph if z2["scene"] == k) - 0.2, 0.6)
    for j, q in enumerate(ph[:-1]):
        if q["chute"]:                                                     # vanne en route : impact léger + rires du public
            ajoute("boom_leger", q["fin"] + 0.05, 0.4); ajoute("foule_rire", q["fin"] + 0.12, 0.55, public)
        elif q["emo"] in ("choc", "panique") and j:                        # moment de choc : « oooh » du public
            ajoute("gasp", q["fin"] + 0.05, 0.45, public)
    d_m = len(SM.son("montee")) / SRM
    ajoute("montee", ph[-1]["deb"] - d_m, 0.5)                            # tension juste avant la chute finale
    ajoute("boom_fin", ph[-1]["fin"] + 0.02, 1.0)                         # gros impact sur la chute finale
    ajoute("foule_rire", ph[-1]["fin"] + 0.25, 0.8, public)               # gros rire du public
    if len(places[ph[-1]["scene"]]) > 1: ajoute("boom_leger", ph[-1]["fin"] + 0.57, 0.5)   # celui qui encaisse tombe à la renverse
    ajoute("pop", GEL, 0.5)                                                # arrêt sur image
    if FIN_CARTE is not None: ajoute("pop", FIN_CARTE, 0.6)
    voix_env = np.convolve(np.abs(mix[:, 0]), np.ones(int(0.15 * SRM)) / int(0.15 * SRM), "same")
    voix_env = np.clip(voix_env / (np.percentile(voix_env[voix_env > 1e-4], 90) + 1e-6) if (voix_env > 1e-4).any() else voix_env, 0, 1)
    mix = mix + fx * (1 - 0.5 * voix_env)[:, None] + public * (1 - 0.8 * voix_env)[:, None]   # le public s'efface quand on parle
    mix = np.clip(mix / max(1.0, np.abs(mix).max() / 0.95), -0.99, 0.99)
    brut, wav = f"{tmp}/mix.wav", f"{tmp}/mix_norm.wav"
    with wave.open(brut, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SRM); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", brut, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "2", wav], check=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", sortie], stdin=subprocess.PIPE)
    for fi in range(nf):
        ff.stdin.write(image(fi).tobytes())
        if fi % 300 == 0: print(f"  image {fi}/{nf}", flush=True)
    ff.stdin.close(); ff.wait()
    return total
