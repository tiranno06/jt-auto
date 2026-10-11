"""Outils communs du montage : format de la vidéo, voix gratuites par personnage, sous-titres (groupes de mots, minutage),
cartons, sons et mixage. (L'ancien rendu « JT d'actualité » a été supprimé : toutes les vidéos passent par le moteur cartoon.)"""
import math, os, re, subprocess, sys, tempfile, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ICI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ICI)

W, H, FPS, SR = 1080, 1920, 30, 22050
POL = os.path.join(ICI, "..", "polices")
FB, FM = os.path.join(POL, "Poppins-Bold.ttf"), os.path.join(POL, "Poppins-Medium.ttf")
# voix de secours (Piper) : hauteur / timbre / débit par rôle
# voix gratuites Piper : une voix différente par personnage (Tom, Pierre, Siwis, Gilles) ; si le fichier manque, la voix Siwis
# retravaillée (pitch / formant) prend le relais
VOIX = {"presentateur": dict(pitch=0.97, formant=1.0, vitesse=1.08, expr=0.55, modele="fr_FR-tom-medium.onnx", pitch_secours=0.86, formant_secours=0.92),
        "envoyee":      dict(pitch=1.04, formant=1.03, vitesse=1.13, expr=0.65),
        "invite":       dict(pitch=1.0, formant=1.0, vitesse=1.05, expr=0.6, modele="fr_FR-upmc-medium.onnx", speaker=1, pitch_secours=0.80, formant_secours=0.89),
        "narrateur":    dict(pitch=1.0, formant=1.0, vitesse=1.06, expr=0.6, modele="fr_FR-gilles-low.onnx", pitch_secours=0.95, formant_secours=0.98)}          # voix off des sketchs animés

# ------------------------------------------------------------------ outils
def poser(base, rgba, x, y):
    h, w = rgba.shape[:2]; x, y = int(x), int(y)
    x0, y0, x1, y1 = max(0, x), max(0, y), min(base.shape[1], x + w), min(base.shape[0], y + h)
    if x1 <= x0 or y1 <= y0: return
    s = rgba[y0 - y:y1 - y, x0 - x:x1 - x]; reg = base[y0:y1, x0:x1]; a = s[..., 3:4] / 255.0
    reg[:] = reg * (1 - a) + s[..., :3] * a

def enveloppe(a):
    n = int(len(a) / SR * FPS) + 1; hop = SR / FPS
    e = np.array([np.sqrt(np.mean(a[int(i * hop):int((i + 1) * hop)] ** 2)) if int(i * hop) < len(a) - 1 else 0 for i in range(n)])
    ref = np.percentile(e[e > 0.01], 90) if (e > 0.01).any() else 1
    lv = np.clip(e / ref, 0, 1.2); lv = np.where(lv < 0.12, 0, lv)
    return np.round(lv * 5).clip(0, 5).astype(int), lv

PETITS = set("""le la les l' un une des du de d' à au aux en et ou mais donc car ni je j' tu il elle on nous vous ils elles me m' te t' se s' lui
leur leurs mon ton son ma ta sa mes tes ses notre votre nos vos ce cet cette ces c' qui que qu' ne n' y pour par sur sous dans avec sans chez
très plus moins si pas ai as a avons avez ont est es suis sont va vais vas""".split())
UNITES = {"h", "min", "s", "€", "%", "km", "kg", "g", "m", "cm", "ans", "euros", "°"}

def groupes(texte):
    """Découpe une réplique en groupes de sous-titres lisibles : 4 mots ou ~18 caractères au plus, coupe après la ponctuation,
    jamais de ponctuation seule, nombre et unité ensemble (« 8 h », « 4,99 € »), jamais de groupe qui finit sur un petit mot."""
    jetons = []
    for m in texte.replace("\u00a0", " ").replace("\u202f", " ").split():
        if jetons and (re.fullmatch(r"[!?:;»…,.]+", m) or (m.lower() in UNITES and re.search(r"\d$", jetons[-1]))):
            jetons[-1] += " " + m                                      # « ! » ou « h » collés au mot d'avant
        elif jetons and jetons[-1] == "«":
            jetons[-1] += " " + m
        else:
            jetons.append(m)
    return [" ".join(g) for g in _regrouper(jetons)]

def _regrouper(jetons):
    res, cur = [], []
    for k, m in enumerate(jetons):
        cur.append(m)
        fin_phrase = bool(re.search(r"[.,:;!?…»]$", m))
        plein = len(cur) >= 4 or len(" ".join(cur)) > 17
        if k == len(jetons) - 1: break
        if fin_phrase: res.append(cur); cur = []; continue
        if plein:
            report = []
            while len(cur) > 1 and re.sub(r"[^\w']", "", cur[-1].lower()) in PETITS: report.insert(0, cur.pop())
            res.append(cur); cur = report
    if cur:
        if res and len(cur) == 1 and len(cur[0]) <= 4 and not re.search(r"[.,:;!?…»]$", res[-1][-1]): res[-1] += cur
        else: res.append(cur)
    return res

F_CAP = ImageFont.truetype(FB, 100); _cache = {}
def carton(txt):
    if txt in _cache: return _cache[txt]
    mots = txt.upper().split()
    cle = max(range(len(mots)), key=lambda i: len(re.sub(r"\W", "", mots[i])))
    if len(re.sub(r"\W", "", mots[cle])) < 5 and not re.search(r"\d", txt): cle = -1
    tmp = Image.new("RGBA", (2400, 200), (0, 0, 0, 0)); d = ImageDraw.Draw(tmp); x = 20
    for i, m in enumerate(mots):
        d.text((x, 20), m, font=F_CAP, fill=(255, 214, 40) if i == cle else (255, 255, 255), stroke_width=10, stroke_fill=(0, 0, 0))
        x += d.textlength(m + " ", font=F_CAP)
    tmp = tmp.crop(tmp.getbbox()); w = min(1000, int(tmp.width * 0.82))
    tmp = tmp.resize((w, int(tmp.height * min(1, 1000 / (tmp.width * 0.82)))), Image.LANCZOS)
    _cache[txt] = np.array(tmp).astype(np.float32); return _cache[txt]

def pop(a, k):
    if k >= 1: return a
    s = 0.75 + 0.25 * (1 - (1 - max(0, k)) ** 3)
    b = cv2.resize(a, (max(1, int(a.shape[1] * s)), max(1, int(a.shape[0] * s)))); b[..., 3] *= min(1, max(0, k) * 2); return b

def rgba(img): return np.array(img).astype(np.float32)

# ------------------------------------------------------------------ sous-titres calés sur la voix
def _syll(m):
    return max(1, len(re.findall(r"[aeiouyàâäéèêëîïôöùûüœæ]+", m.lower())) + 1.5 * len(re.findall(r"\d", m)))

def minutage(texte, a, t0, mots=None):
    """Horaires des groupes de mots, calés sur la voix réelle : les silences ne reçoivent aucun mot,
    et chaque fin de phrase (ponctuation) est accrochée à la pause correspondante dans l'audio."""
    gs = groupes(texte); poids = np.array([sum(_syll(m) for m in g.split()) for g in gs], float)
    if mots and len(mots) >= 2:                                            # instants exacts donnés par Whisper
        cs = np.cumsum([_syll(m) for m, _, _ in mots]); cs = cs / cs[-1]
        c = np.concatenate([[0], np.cumsum(poids) / poids.sum()]); res = []
        def instant(frac, debut):
            k = int(np.searchsorted(cs, frac - 1e-6)); k = min(k, len(mots) - 1)
            return mots[k][1] if debut else mots[k][2]
        for k, g in enumerate(gs):
            d0 = instant(c[k] + 1e-3, True) if k else mots[0][1]; d1 = instant(c[k + 1], False)
            res.append((g, t0 + d0, t0 + max(d1, d0 + 0.12)))
        for k in range(1, len(res)): res[k] = (res[k][0], max(res[k][1], res[k - 1][1] + 0.05), res[k][2])
        return res
    hop = int(0.01 * SR); nfr = max(1, len(a) // hop)
    e = np.array([np.sqrt(np.mean(a[k * hop:(k + 1) * hop] ** 2)) for k in range(nfr)])
    seuil = 0.1 * (np.percentile(e, 95) + 1e-9); v = e > seuil
    if v.sum() < 5: v[:] = True
    cv = np.cumsum(v); V = cv[-1]
    def temps(frac, debut):
        k = int(np.searchsorted(cv, frac * V + (1 if debut else 0))); return min(k, nfr - 1) * 0.01
    pauses, k = [], 0                                                       # silences d'au moins 0,12 s à l'intérieur de la réplique
    premier, dernier = int(np.argmax(v)), nfr - int(np.argmax(v[::-1]))
    while k < nfr:
        if not v[k] and premier < k < dernier:
            j = k
            while j < nfr and not v[j]: j += 1
            if j - k >= 12: pauses.append((k * 0.01, j * 0.01))
            k = j
        else: k += 1
    c = np.concatenate([[0], np.cumsum(poids) / poids.sum()])
    deb = [temps(c[k], True) for k in range(len(gs))]; fin = [temps(c[k + 1], False) for k in range(len(gs))]
    for k in range(len(gs) - 1):
        if re.search(r"[.,:;!?…]$", gs[k]) and pauses:
            p = min(pauses, key=lambda x: abs((x[0] + x[1]) / 2 - fin[k]))
            if abs((p[0] + p[1]) / 2 - fin[k]) < 0.45: fin[k], deb[k + 1] = p[0], p[1]
    for k in range(1, len(gs)): deb[k] = max(deb[k], deb[k - 1] + 0.05)
    return [(g, t0 + deb[k], t0 + max(fin[k], deb[k] + 0.12)) for k, g in enumerate(gs)]

# ------------------------------------------------------------------ sons (orchestre réel, CC0) et générique
SONS = os.path.join(ICI, "..", "sons"); SRM = 44100; INTRO = 5.0; GEN_DUREE = 1.6

def accroche(txt):
    """Grand titre-accroche affiché pendant la première réplique (style « POV » TikTok)."""
    if not txt: return None
    txt = re.sub(r"[^\w\s'’«»:!?,.%€-]", "", str(txt)).strip().upper()[:46]
    f = ImageFont.truetype(FB, 56); d0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    mots, lignes, cur = txt.split(), [], ""
    for m in mots:
        if d0.textlength((cur + " " + m).strip(), font=f) > 900: lignes.append(cur); cur = m
        else: cur = (cur + " " + m).strip()
    lignes.append(cur); lignes = lignes[:3]
    hl = 72; img = Image.new("RGBA", (W, hl * len(lignes) + 50), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    for k, l in enumerate(lignes):
        w = d.textlength(l, font=f); x = (W - w) / 2
        d.rounded_rectangle((x - 22, 18 + k * hl, x + w + 22, 18 + k * hl + hl - 6), 14, fill=(255, 214, 40, 255))
        d.text((x, 22 + k * hl), l, font=f, fill=(20, 20, 30))
    img = img.rotate(-2, resample=Image.BICUBIC, expand=False)
    return np.array(img).astype(np.float32)
def son(nom):
    p = os.path.join(SONS, nom + ".wav")
    if not os.path.exists(p): return np.zeros((1, 2))
    with wave.open(p) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return x.reshape(-1, w.getnchannels()) if w.getnchannels() == 2 else np.repeat(x[:, None], 2, 1)

def vers_mix(a):
    """Voix 22 050 Hz mono → 44 100 Hz stéréo."""
    from scipy.signal import resample_poly
    b = resample_poly(a, 2, 1).astype(np.float32); return np.stack([b, b], 1)
