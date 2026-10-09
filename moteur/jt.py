"""Rendu « studio » du JT satirique : plateau, duplex, direct, invité, plan gag IA, bandeau défilant, habillage télé, mixage.
rendre(sk, sortie, audios, gag=None) : sk = sketch validé (ecrire.py), audios = liste de signaux float32 à 22 050 Hz (un par réplique),
gag = chemin d'un clip vidéo (Wan 2.2) à insérer pendant la réplique sk["gag"]["replique"], ou None."""
import math, os, re, subprocess, sys, tempfile, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ICI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ICI)
import dessin_jt as D

W, H, FPS, SR = 1080, 1920, 30, 22050
POL = os.path.join(ICI, "..", "polices")
FB, FM = os.path.join(POL, "Poppins-Bold.ttf"), os.path.join(POL, "Poppins-Medium.ttf")
NOM = os.environ.get("NOM_EMISSION") or "L'INFO EN CAOUTCHOUC"
HEAD_Y, LOWER_Y, CAP_Y, TICK_Y = 232, 1075, 1335, 1438
# voix de secours (Piper) : hauteur / timbre / débit par rôle
VOIX = {"presentateur": dict(pitch=0.86, formant=0.92, vitesse=1.1, expr=0.5),
        "envoyee":      dict(pitch=1.04, formant=1.03, vitesse=1.13, expr=0.65),
        "invite":       dict(pitch=0.80, formant=0.89, vitesse=1.06, expr=0.55)}

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

def groupes(texte):
    out, cur = [], []
    for m in texte.split():
        cur.append(m)
        if len(cur) == 3 or re.search(r"[.,:;!?…]$", m) or len(" ".join(cur)) > 16: out.append(cur); cur = []
    if cur: out.append(cur)
    return [" ".join(g) for g in out]

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

def minutage(texte, a, t0):
    """Horaires des groupes de mots, calés sur la voix réelle : les silences ne reçoivent aucun mot,
    et chaque fin de phrase (ponctuation) est accrochée à la pause correspondante dans l'audio."""
    gs = groupes(texte); poids = np.array([sum(_syll(m) for m in g.split()) for g in gs], float)
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

def generique_images():
    """Prépare les calques du générique (globe, titre, date)."""
    import datetime
    from zoneinfo import ZoneInfo
    J = ["LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE"]
    M = ["JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"]
    d = datetime.datetime.now(ZoneInfo("Europe/Paris")).date(); date = f"{J[d.weekday()]} {d.day} {M[d.month - 1]} {d.year}"
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    fond = np.zeros((H, W, 3), np.float32); k = (yy / H)[..., None]
    fond[:] = (8, 14, 46) * (1 - k) + np.array((2, 4, 16)) * k
    halo = np.exp(-(((xx - W / 2) / 520) ** 2 + ((yy - 860) / 520) ** 2))[..., None] * np.array((40, 80, 200), np.float32)
    fond += halo
    img = Image.new("RGBA", (W, 520), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
    f1, f2 = ImageFont.truetype(FB, 96), ImageFont.truetype(FB, 120)
    l1, l2 = "L'INFO EN", "CAOUTCHOUC"
    if NOM.upper() != "L'INFO EN CAOUTCHOUC":
        mots = NOM.upper().split(); l1, l2 = " ".join(mots[:len(mots) // 2]), " ".join(mots[len(mots) // 2:])
    while dr.textlength(l2, font=f2) > W - 120 and f2.size > 60: f2 = ImageFont.truetype(FB, f2.size - 6)
    dr.rounded_rectangle((60, 120, W - 60, 440), 30, fill=(12, 20, 60, 235), outline=(255, 214, 40, 255), width=6)
    dr.text(((W - dr.textlength(l1, font=f1)) / 2, 140), l1, font=f1, fill=(255, 255, 255))
    dr.text(((W - dr.textlength(l2, font=f2)) / 2, 260), l2, font=f2, fill=(255, 214, 40), stroke_width=4, stroke_fill=(140, 20, 30))
    dr.rounded_rectangle((W / 2 - 80, 20, W / 2 + 80, 110), 22, fill=(220, 35, 45, 255)); fj = ImageFont.truetype(FB, 70)
    dr.text(((W - dr.textlength("JT", font=fj)) / 2, 22), "JT", font=fj, fill=(255, 255, 255))
    titre = np.array(img).astype(np.float32)
    im2 = Image.new("RGBA", (W, 130), (0, 0, 0, 0)); d2 = ImageDraw.Draw(im2); f3, f4 = ImageFont.truetype(FB, 44), ImageFont.truetype(FM, 30)
    d2.text(((W - d2.textlength(date, font=f3)) / 2, 0), date, font=f3, fill=(255, 255, 255))
    t4 = "ÉDITION SATIRIQUE · PERSONNAGES FICTIFS"; d2.text(((W - d2.textlength(t4, font=f4)) / 2, 70), t4, font=f4, fill=(160, 180, 230))
    return fond, titre, np.array(im2).astype(np.float32)

def globe(fr, tm, cx, cy, R, alpha):
    """Globe terrestre en fil de fer qui tourne (méridiens et parallèles)."""
    calque = np.zeros_like(fr); rot = tm * 0.9; inc = 0.38
    for lon in np.linspace(0, np.pi, 12, endpoint=False):
        th = np.linspace(-np.pi / 2, np.pi / 2, 60); x = np.cos(th) * np.cos(lon + rot); z = np.cos(th) * np.sin(lon + rot); y = np.sin(th)
        for sgn in (1, -1):
            X, Z = sgn * x, sgn * z; Y2 = y * np.cos(inc) - Z * np.sin(inc); Z2 = y * np.sin(inc) + Z * np.cos(inc)
            pts = np.stack([cx + R * X, cy - R * Y2], 1).astype(np.int32); avant = Z2.mean() > 0
            cv2.polylines(calque, [pts], False, (90, 170, 255) if avant else (35, 60, 120), 3 if avant else 2, cv2.LINE_AA)
    for lat in np.linspace(-1.2, 1.2, 7):
        ph_ = np.linspace(0, 2 * np.pi, 90); x = np.cos(lat) * np.cos(ph_); z = np.cos(lat) * np.sin(ph_); y = np.full_like(ph_, np.sin(lat))
        Y2 = y * np.cos(inc) - z * np.sin(inc); Z2 = y * np.sin(inc) + z * np.cos(inc)
        pts = np.stack([cx + R * x, cy - R * Y2], 1).astype(np.int32)
        cv2.polylines(calque, [pts], True, (60, 120, 210), 2, cv2.LINE_AA)
    cv2.circle(calque, (int(cx), int(cy)), int(R), (120, 200, 255), 4, cv2.LINE_AA)
    flou = cv2.resize(cv2.GaussianBlur(cv2.resize(calque, (W // 4, H // 4), interpolation=cv2.INTER_AREA), (0, 0), 2.5), (W, H))
    fr += (calque + flou * 1.2) * alpha

def image_generique(tm, G):
    """Générique de 5 s : globe et faisceaux, impact du titre (1,25 s), date (2,4 s), plongée vers le plateau."""
    fond, titre, date = G
    fr = fond.copy(); zoom = 1 + 0.05 * tm / INTRO
    cal = np.zeros((H // 8, W // 8, 3), np.float32)                        # faisceaux lumineux qui balaient (calculés en petit)
    for k in range(5):
        ang = -1.2 + k * 0.55 + 0.25 * np.sin(tm * 1.3 + k)
        p0 = (W // 16, (H + 100) // 8); p1 = (int((W / 2 + 2600 * np.sin(ang)) / 8), int((H + 100 - 2600 * np.cos(ang)) / 8))
        cv2.line(cal, p0, p1, (60, 110, 255), 11, cv2.LINE_AA)
    fr += cv2.resize(cv2.GaussianBlur(cal, (0, 0), 5), (W, H), interpolation=cv2.INTER_LINEAR) * 0.25
    globe(fr, tm, W / 2, 900, 330 * zoom, min(1, tm / 0.6))
    for k in range(14):                                                     # traînées horizontales
        y = (k * 137 + tm * (600 + 50 * k)) % H; x = (k * 311 + tm * 900) % (W + 600) - 300
        cv2.line(fr, (int(x), int(y)), (int(x + 260), int(y)), (120, 170, 255), 2, cv2.LINE_AA)
    if tm >= 1.25:
        u = (tm - 1.25) / 0.35; s = 1.0 if u >= 1 else 1 + 0.9 * (1 - u) ** 2 - 0.12 * np.sin(u * np.pi)
        t2 = cv2.resize(titre, (int(W * s), int(titre.shape[0] * s)))
        t2[..., 3] *= min(1, u * 3) if u < 1 else 1
        poser(fr, t2, (W - t2.shape[1]) / 2, 330 - (t2.shape[0] - titre.shape[0]) / 2)
        if 0.3 < tm - 1.25 < 1.6:                                           # reflet qui traverse le titre
            x = int(-200 + (tm - 1.55) / 1.3 * (W + 400)); cal = np.zeros((H // 4, W // 4, 3), np.float32)
            cv2.line(cal, (x // 4, 105), ((x + 160) // 4, 200), (255, 255, 255), 12, cv2.LINE_AA)
            fr += cv2.resize(cv2.GaussianBlur(cal, (0, 0), 3.5), (W, H)) * 0.35
    if tm >= 2.41:
        u = min(1, (tm - 2.41) / 0.4); d = date.copy(); d[..., 3] *= u; poser(fr, d, 0, 900 + 260 + 40 * (1 - u))
    flash = max(0.0, 1 - abs(tm - 1.25) / 0.12) * 0.8 + max(0.0, (tm - (INTRO - 0.25)) / 0.25) * 1.0
    if tm > INTRO - 0.6:                                                    # plongée finale
        z = 1 + ((tm - (INTRO - 0.6)) / 0.6) ** 2 * 0.6; M = np.float32([[z, 0, W / 2 - z * W / 2], [0, z, 700 - z * 700]])
        fr = cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    if flash > 0: fr = fr * (1 - min(1, flash)) + 255 * min(1, flash)
    return fr

def image_fin(u, G):
    """Carton de fin (format long) : globe, titre et appel à s'abonner."""
    fond, titre, date = G; fr = fond.copy(); globe(fr, u + 3, W / 2, 1150, 300, 1.0)
    poser(fr, titre, 0, 260)
    if not hasattr(image_fin, "abo"):
        im = Image.new("RGBA", (W, 260), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f1, f2 = ImageFont.truetype(FB, 64), ImageFont.truetype(FM, 36)
        t1, t2 = "ABONNE-TOI", "pour le JT de demain"
        d.rounded_rectangle(((W - d.textlength(t1, font=f1)) / 2 - 40, 20, (W + d.textlength(t1, font=f1)) / 2 + 40, 120), 30, fill=(220, 35, 45, 255))
        d.text(((W - d.textlength(t1, font=f1)) / 2, 26), t1, font=f1, fill=(255, 255, 255))
        d.text(((W - d.textlength(t2, font=f2)) / 2, 150), t2, font=f2, fill=(230, 235, 255))
        image_fin.abo = np.array(im).astype(np.float32)
    s = 1 + 0.04 * np.sin(u * 4); a = cv2.resize(image_fin.abo, (int(W * s), int(260 * s)))
    poser(fr, a, (W - a.shape[1]) / 2, 1500)
    if u < 0.25: fr = fr * (u / 0.25) + 255 * (1 - u / 0.25) * 0.6
    return fr

# ------------------------------------------------------------------ habillage
def entete(sujet):
    img = Image.new("RGBA", (W, 150), (0, 0, 0, 0)); d = ImageDraw.Draw(img); f = ImageFont.truetype(FB, 48)
    a, b = "JT", sujet.upper(); wa, wb = d.textlength(a, font=f), d.textlength(b, font=f); x0 = (W - (wa + wb + 100)) / 2
    d.rounded_rectangle((x0, 10, x0 + wa + 50, 86), 20, fill=(220, 35, 45, 240)); d.text((x0 + 25, 16), a, font=f, fill=(255, 255, 255))
    d.rounded_rectangle((x0 + wa + 40, 10, x0 + wa + wb + 100, 86), 20, fill=(16, 20, 36, 225)); d.text((x0 + wa + 72, 16), b, font=f, fill=(255, 255, 255))
    f3 = ImageFont.truetype(FM, 25); t = f"{NOM} · satire · personnages fictifs"; w3 = d.textlength(t, font=f3)
    d.rounded_rectangle(((W - w3) / 2 - 14, 96, (W + w3) / 2 + 14, 134), 12, fill=(0, 0, 0, 120)); d.text(((W - w3) / 2, 99), t, font=f3, fill=(235, 235, 240))
    return rgba(img)

def bandeau_nom(c):
    img = Image.new("RGBA", (W, 170), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    f, f2 = ImageFont.truetype(FB, 50), ImageFont.truetype(FM, 29)
    L = max(d.textlength(c["nom"].upper(), font=f), d.textlength(c["role"], font=f2)) + 70; x0 = 50
    d.rectangle((x0, 10, x0 + 14, 140), fill=(255, 214, 40, 255))
    d.rectangle((x0 + 14, 10, x0 + 14 + L, 86), fill=c["couleur"] + (245,)); d.text((x0 + 40, 16), c["nom"].upper(), font=f, fill=(255, 255, 255))
    d.rectangle((x0 + 14, 86, x0 + 14 + L, 140), fill=(255, 255, 255, 245)); d.text((x0 + 40, 94), c["role"], font=f2, fill=(30, 30, 40))
    return rgba(img)

def etiquette(txt, fond, coul=(255, 255, 255), taille=40, point=False):
    f = ImageFont.truetype(FB, taille); w = int(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(txt, font=f))
    img = Image.new("RGBA", (w + (86 if point else 44), int(taille * 1.8)), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, img.width - 1, img.height - 1), 12, fill=fond)
    d.text(((66 if point else 22), int(taille * 0.2)), txt, font=f, fill=coul)
    a = rgba(img)
    if point:
        b = a.copy(); cv2.circle(b, (34, img.height // 2), 12, (255, 255, 255, 255), -1, cv2.LINE_AA); return a, b
    return a

def bandeau_defilant(items):
    f = ImageFont.truetype(FB, 34); txt = "   |   ".join(items or ["L'ACTU, MAIS EN PIRE"]) + "   |   "
    w = int(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(txt, font=f)) + 4
    img = Image.new("RGBA", (w, 64), (170, 20, 30, 235)); ImageDraw.Draw(img).text((0, 9), txt, font=f, fill=(255, 255, 255))
    lab = Image.new("RGBA", (190, 64), (255, 214, 40, 255)); ImageDraw.Draw(lab).text((22, 9), "EN BREF", font=f, fill=(20, 20, 30))
    return rgba(img), rgba(lab)

# ------------------------------------------------------------------ son
def _fft_conv(a, ir):
    n = len(a) + len(ir); m = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(a, m) * np.fft.rfft(ir, m), m)[:len(a)]

def salle(a, duree=0.5, mix=0.06, graine=3):
    """Réverbération d'une grande salle (le direct de l'envoyée) + léger filtrage « micro de reportage »."""
    t = np.arange(int(duree * SR)) / SR; ir = np.random.default_rng(graine).normal(0, 1, len(t)) * np.exp(-t * 6.5)
    ir[:int(0.012 * SR)] = 0; ir /= np.sqrt(np.sum(ir ** 2))
    wet = _fft_conv(a, ir); b = np.convolve(a, [0.25, 0.5, 0.25], "same")
    return (b + wet * mix * np.sqrt(np.sum(a ** 2) / max(np.sum(wet ** 2), 1e-9))).astype(np.float32)

# ------------------------------------------------------------------ rendu
def rendre(sk, sortie, audios, gag=None, apercu=False):
    tmp = tempfile.mkdtemp(); rng = np.random.default_rng(5)
    cast = D.casting(sk); reps = sk["repliques"]
    for k, c in cast.items():
        c["spr"], c["off"] = D.sprites(c)
        f = cv2.GaussianBlur(c["fond"][..., :3].astype(np.float32), (0, 0), 2.6 if k == "envoyee" else 1.8)   # profondeur de champ
        D_ = c["corps"].astype(np.float32); a = D_[..., 3:4] / 255
        sh = cv2.GaussianBlur(D_[..., 3], (0, 0), 18)[..., None] / 255 * 0.35                               # ombre portée douce
        f = f * (1 - np.roll(sh, (14, 22), (0, 1))); f = f * (1 - a) + D_[..., :3] * a
        c["plan"] = f
        if c["devant"] is not None:
            dv = c["devant"].astype(np.float32); y = np.where(dv[..., 3].max(1) > 0)[0].min(); c["dv"] = (dv[y:], y)
        c["band"] = bandeau_nom(c)
    # ---- chronologie
    t = 0.12; ph = []; prev = None; GEN0 = GEN1 = None
    for i, (r, a) in enumerate(zip(reps, audios)):
        niv, lv = enveloppe(a); dur = len(a) / SR
        if i == 1:                                                          # après l'accroche : mini-générique de 1,6 s
            GEN0 = t; GEN1 = t + GEN_DUREE; t = GEN1 + 0.12; prev = None
        t0 = t; att = float(r.get("attente", 0)); t += att
        q = dict(i=i, p=r["p"], deb=t, att=att, fin=t + dur, audio=a, niv=niv, lv=lv, chute=bool(r.get("chute")),
                 groupes=minutage(r["t"], a, t))
        # début du plan : coupe vers celui qui parle ; après une vanne, on coupe tôt sur la réaction (visage impassible)
        if r["p"] != prev:
            q["plan"] = (ph[-1]["fin"] + 0.22) if (ph and ph[-1]["chute"] and i != 1) else max(GEN1 or 0, t0 - 0.12)
            q["reaction"] = bool(ph and ph[-1]["chute"] and i != 1)
        else:
            q["plan"] = None
        gg = q["groupes"]; dz = gg[0][1]
        for k2 in range(len(gg) - 1):
            if re.search(r"[.!?…]$", gg[k2][0]): dz = gg[k2 + 1][1]
        q["dz"] = dz; ph.append(q); prev = r["p"]
        t += dur + (0.45 if r.get("chute") and i != 0 else 0.06 if i else 0.08)
    if GEN0 is None: GEN0 = t; GEN1 = t + GEN_DUREE; t = GEN1
    total = t + 0.35                                                        # fin sèche : la vidéo reboucle sur l'accroche
    FIN = None
    if os.environ.get("LONGUEUR") == "monetisable" and total < 62.0:     # format long : carton de fin pour dépasser 1 minute
        FIN = t + 0.5; total = 62.0
    nf = int(total * FPS)
    # cadrage : large au début de chaque plan, serré à la réplique suivante du même personnage (coupe caméra)
    vu, cadre = set(), "large"
    for q in ph:
        if q["plan"] is not None: cadre = "large"
        else: cadre = "serre" if cadre == "large" else "large"
        q["cadre"] = cadre; q["bandeau"] = q["p"] not in vu and q["plan"] is not None; vu.add(q["p"])
        q["debplan"] = q["plan"] if q["plan"] is not None else q["deb"] - 0.05
    # duplex : la question qui lance le premier direct s'affiche en écran partagé
    i_env = next((q["i"] for q in ph if q["p"] == "envoyee"), None)
    duplex = i_env - 1 if i_env and ph[i_env - 1]["p"] == "presentateur" else None
    # plan gag IA
    gag_i = (sk.get("gag") or {}).get("replique") if gag else None
    clip = []
    if gag_i is not None and os.path.exists(gag):
        cap = cv2.VideoCapture(gag); clip_fps = cap.get(cv2.CAP_PROP_FPS) or 24
        while len(clip) < 240:                                                  # au plus ~10 s, gardé en demi-résolution
            ok, im = cap.read()
            if not ok: break
            im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB); s = max(W / 2 / im.shape[1], H / 2 / im.shape[0])
            im = cv2.resize(im, (int(im.shape[1] * s + 1), int(im.shape[0] * s + 1)), interpolation=cv2.INTER_AREA)
            y0, x0 = (im.shape[0] - H // 2) // 2, (im.shape[1] - W // 2) // 2; clip.append(im[y0:y0 + H // 2, x0:x0 + W // 2].copy())
        if not clip: gag_i = None
    else:
        gag_i = None
    print(f"durée {total:.1f} s, {len(ph)} répliques, duplex={duplex}, gag={gag_i}", flush=True)

    # ---- son (44,1 kHz stéréo) : voix, générique, nappe, bruitages d'orchestre réels
    n = int(SRM * (total + 1)); voixm = np.zeros((n, 2))
    for q in ph:
        a = vers_mix(salle(q["audio"]) if q["p"] == "envoyee" else q["audio"]); s0 = int(q["deb"] * SRM); voixm[s0:s0 + len(a)] += a[:n - s0]
    m1 = np.abs(voixm[:, 0]); k = int(0.2 * SRM)
    env = np.convolve(m1, np.ones(k) / k, "same"); env = np.clip(env / (np.percentile(env[env > 1e-4], 90) + 1e-6) if (env > 1e-4).any() else env, 0, 1)
    duck = (1 - 0.9 * env)[:, None]                                         # musique et bruitages s'effacent sous la voix
    fond = np.zeros((n, 2)); nap = son("nappe")
    if len(nap) > 10:
        for s0 in range(int((GEN1 - 0.2) * SRM), n, len(nap) - int(0.4 * SRM)):
            e = min(n, s0 + len(nap)); fond[s0:e] += nap[:e - s0] * 0.11
    def ajoute(nom, t, g):
        x = son(nom); s0 = int(t * SRM); e = min(n, s0 + len(x))
        if e > s0: fond[s0:e] += x[:e - s0] * g
    chutes = [q for q in ph if q["chute"] and q["i"] > 0]; cycle = ["xylo_descente", "rimshot", "trombone_triste"]
    for j, q in enumerate(chutes):
        if q is ph[-1]: ajoute("rimshot", q["fin"] + 0.02, 0.9)
        else: ajoute(cycle[j % len(cycle)], q["fin"] + 0.02, 0.7 if cycle[j % len(cycle)] != "trombone_triste" else 0.5)
    for q in ph:
        if q["plan"] is not None and q["i"] > 0 and (q["p"] == "envoyee" or q["i"] == gag_i): ajoute("woosh", q["debplan"] - 0.12, 0.6)
        if q["i"] == gag_i: ajoute("reconstitution", q["debplan"], 0.6)
    mix = voixm + fond * duck
    ig = son("intro_courte"); s0 = int(max(0, GEN0 - 0.06) * SRM); e = min(n, s0 + len(ig)); mix[s0:e] += ig[:e - s0] * 0.95
    mix = np.clip(mix / max(1.0, np.abs(mix).max() / 0.95), -0.99, 0.99)
    brut = f"{tmp}/mix.wav"; wav = f"{tmp}/mix_norm.wav"
    with wave.open(brut, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SRM); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", brut, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "2", wav], check=True)

    # ---- calques
    ENT = entete(sk.get("sujet", "L'ACTU")); DIRECT = etiquette("DIRECT", (220, 35, 45, 240), point=True)
    TICK, TLAB = bandeau_defilant(sk.get("bandeau")); RECO = etiquette("RECONSTITUTION", (220, 35, 45, 240), taille=38)
    IA = etiquette("image générée par IA", (0, 0, 0, 150), taille=24)
    L_PLAT = etiquette("PLATEAU", (16, 20, 36, 230), taille=30); lieu = sk.get('lieu_direct', '').upper(); lieu = lieu if len(lieu) <= 16 else lieu[:15].rstrip() + "…"
    L_DIR = etiquette(f"DIRECT · {lieu}", (220, 35, 45, 240), taille=28)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    VIG = (1 - 0.28 * np.clip(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.45) / (H * 0.7)) ** 2, 0, 1))[..., None]
    GRAIN = [np.random.default_rng(k).normal(0, 1.8, (H, W, 1)).astype(np.float32) for k in range(4)]
    clign = sorted(rng.uniform(0.8, total, int(total / 3.0)))
    regards = [(t0, rng.choice([-1.0, 1.0])) for t0 in rng.uniform(2, total, int(total / 7))]

    def perso(c, k_p, tm, q, parle, cadre="large", chute_z=0.0):
        """Image d'un personnage à l'instant tm (parle=False : il écoute)."""
        if parle:
            k = int((tm - q["deb"]) * FPS); n_ = int(q["niv"][k]) if 0 <= k < len(q["niv"]) else 0
            lv = float(q["lv"][k]) if 0 <= k < len(q["lv"]) else 0.0
        else: n_, lv = 0, 0.0
        var = 1 if n_ >= 2 and (int(tm * 5.5) * 7919) % 5 == 0 else 0
        e, rg = "ouvert", 0.0
        if any(0 <= tm - cl < 0.13 for cl in clign): e = "ferme"
        if q.get("reaction") and not parle and 0.25 <= tm - q["debplan"] < 0.42: e = "ferme"          # clignement impassible
        for t0, r in regards:
            if 0 <= tm - t0 < 0.7 and e == "ouvert": rg = r
        if parle and q["chute"] and 0 <= tm - q["fin"] < 0.45 and k_p != "invite": e, rg = "grand", 0.0
        fr = c["plan"].copy(); ox, oy = c["off"]
        dx = dy = 0
        if c.get("direct"): dx, dy = 4 * math.sin(tm * 1.9) + 2 * math.sin(tm * 4.3), 3 * math.sin(tm * 1.4 + 1)   # caméra à l'épaule
        poser(fr, c["spr"][(e, rg, n_, var if n_ else 0)].astype(np.float32), ox, oy + int(-5 * lv + 2 * math.sin(tm * 1.6)))
        if "dv" in c: poser(fr, c["dv"][0], 0, c["dv"][1])
        z = (1.16 if cadre == "serre" else 1.0) + chute_z
        cx, cy = c["cx"], c["cy"] + 40
        M = np.float32([[z, 0, cx - z * cx + dx], [0, z, cy - z * cy + dy]])
        return cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    GEN = generique_images(); ACC = accroche(sk.get("titre_accroche"))
    def image(fi):
        tm = fi / FPS
        if GEN0 <= tm < GEN1:                                               # mini-générique accéléré (impact, titre, date, plongée)
            return np.clip(image_generique(1.2 + (tm - GEN0) / GEN_DUREE * (INTRO - 1.2), GEN), 0, 255).astype(np.uint8)
        if FIN and tm >= FIN: return np.clip(image_fin(tm - FIN, GEN), 0, 255).astype(np.uint8)
        q = next((x for x in reversed(ph) if x["debplan"] <= tm), ph[0])
        # zoom : petit punch-in à l'ouverture du plan, lent zoom pendant un silence, zoom sec sur la vanne
        u0 = min(1, (tm - q["debplan"]) / 0.25); z = 0.05 * (1 - u0) ** 2 + 0.01 * (tm - q["debplan"]) / 6
        if q["att"] and tm < q["deb"] + 0.4: u = min(1, max(0, (tm - (q["deb"] - q["att"])) / q["att"])); z += 0.2 * u * u
        elif q["att"]: z += 0.2
        if q["chute"] and q["dz"] <= tm: z += 0.18 * (1 - (1 - min(1, (tm - q["dz"]) / 0.15)) ** 3)
        parle = q["deb"] - 0.05 <= tm
        if q["i"] == gag_i and clip:
            k = min(len(clip) - 1, int((tm - q["debplan"]) * clip_fps))
            fr = cv2.resize(clip[k], (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32)
            zz = 1 + 0.04 * (tm - q["debplan"]); M = np.float32([[zz, 0, W / 2 - zz * W / 2], [0, zz, H / 2 - zz * H / 2]])
            fr = cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            poser(fr, RECO, 40, 400); poser(fr, IA, 40, 480)
        elif q["i"] == duplex:
            fr = np.zeros((H, W, 3), np.float32); fr[:] = (14, 20, 48)
            for j, (kk, lab) in enumerate((("presentateur", L_PLAT), ("envoyee", L_DIR))):
                c = cast[kk]; im = perso(c, kk, tm, q, parle and kk == "presentateur")
                x0 = int(np.clip(c["cx"] - 405, 0, W - 810)); y0 = int(np.clip(c["cy"] - 560, 0, H - 1440))
                box = cv2.resize(im[y0:y0 + 1350, x0:x0 + 810], (530, 883), interpolation=cv2.INTER_AREA)
                bx = 6 + j * 538; fr[395:1278, bx:bx + 530] = box
                cv2.rectangle(fr, (bx, 395), (bx + 529, 1277), (255, 214, 40), 5)
                poser(fr, lab, bx + 16, 1196)
        else:
            c = cast[q["p"]]; fr = perso(c, q["p"], tm, q, parle, q["cadre"], 0.0)
            if z > 0.001:
                cx, cy = c["cx"], c["cy"] + 40; zz = 1 + z; M = np.float32([[zz, 0, cx - zz * cx], [0, zz, cy - zz * cy]])
                fr = cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            if c.get("direct"): poser(fr, DIRECT[int(tm * 2) % 2], 40, 400)
            if q["bandeau"]:
                dt = tm - q["debplan"]
                if 0.2 < dt < 3.4:
                    s = min(1, (dt - 0.2) / 0.2) if dt < 3.2 else max(0, (3.4 - dt) / 0.2); b = c["band"].copy(); b[..., 3] *= s
                    dx = int(60 * (1 - s)); poser(fr, b[:, dx:], 0, LOWER_Y)
        # étalonnage : vignettage + léger contraste + grain
        fr = (fr * 1.05 - 6) * VIG + GRAIN[fi % 4]
        # habillage
        poser(fr, ENT, 0, HEAD_Y)
        if q["i"] == 0 and ACC is not None:                                 # titre-accroche (sert aussi de couverture)
            u = min(1, tm / 0.25); a2 = pop(ACC, u); poser(fr, a2, (W - a2.shape[1]) / 2, 470 - a2.shape[0] / 2)
        if q["i"] != gag_i:
            ox = int(tm * 150) % TICK.shape[1]
            poser(fr, TICK, 190 - ox, TICK_Y); poser(fr, TICK, 190 - ox + TICK.shape[1], TICK_Y); poser(fr, TLAB, 0, TICK_Y)
        g = next((x for x in q["groupes"] if x[1] <= tm < x[2] + (0.2 if x is q["groupes"][-1] else 0)), None)
        if g and q["deb"] <= tm < q["fin"] + 0.2:
            cc = pop(carton(g[0]), (tm - g[1]) / 0.12); poser(fr, cc, (W - cc.shape[1]) / 2, CAP_Y - cc.shape[0] / 2)
        return np.clip(fr, 0, 255).astype(np.uint8)

    if apercu:
        os.makedirs(sortie, exist_ok=True)
        for q in ph:
            for j, tm in enumerate((max(q["debplan"], q["deb"] - 0.3) + 0.5, q["fin"] + 0.1)):
                cv2.imwrite(f"{sortie}/{q['i']:02d}{'ab'[j]}.png", cv2.cvtColor(cv2.resize(image(int(tm * FPS)), (360, 640)), cv2.COLOR_RGB2BGR))
        return total
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", sortie], stdin=subprocess.PIPE)
    for fi in range(nf):
        ff.stdin.write(image(fi).tobytes())
        if fi % 300 == 0: print(f"  image {fi}/{nf}", flush=True)
    ff.stdin.close(); ff.wait()
    return total
