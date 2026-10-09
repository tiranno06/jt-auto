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

def salle(a, duree=0.7, mix=0.16, graine=3):
    """Réverbération d'une grande salle (le direct de l'envoyée) + léger filtrage « micro de reportage »."""
    t = np.arange(int(duree * SR)) / SR; ir = np.random.default_rng(graine).normal(0, 1, len(t)) * np.exp(-t * 6.5)
    ir[:int(0.012 * SR)] = 0; ir /= np.sqrt(np.sum(ir ** 2))
    wet = _fft_conv(a, ir); b = np.convolve(a, [0.25, 0.5, 0.25], "same")
    return (b + wet * mix * np.sqrt(np.sum(a ** 2) / max(np.sum(wet ** 2), 1e-9))).astype(np.float32)

def jingle():
    """Générique de JT : accord de cuivres synthétiques + timbale + cloche."""
    t = np.arange(int(2.2 * SR)) / SR; out = np.zeros_like(t)
    def cuivre(f, deb, dur, g):
        m = (t >= deb) & (t < deb + dur); u = t[m] - deb
        env = np.minimum(1, u / 0.03) * np.exp(-u * 1.6)
        s = sum(np.sin(2 * np.pi * f * k * u) / k ** 1.3 for k in range(1, 9))
        out[m] += s * env * g
    for deb, acc in ((0.0, (392, 494, 587)), (0.16, (392, 494, 587)), (0.32, (523, 659, 784))):
        for f in acc: cuivre(f, deb, 1.6 if deb > 0.3 else 0.14, 0.035)
    tim = np.sin(2 * np.pi * (70 + 40 * np.exp(-t * 20)) * t) * np.exp(-t * 3.5) * 0.25
    clo = np.sin(2 * np.pi * 1568 * t) * np.exp(-t * 3) * 0.04 * (t > 0.32)
    return out + tim + clo

def lit_musical(n):
    """Nappe discrète de fond de JT (tic-tac + accord tenu)."""
    t = np.arange(n) / SR; tic = np.zeros(n); per = SR // 2
    clic = np.random.default_rng(5).normal(0, 1, 400) * np.exp(-np.arange(400) / 60)
    for s in range(0, n - 400, per): tic[s:s + 400] += clic * (0.03 if (s // per) % 2 else 0.018)
    nappe = sum(np.sin(2 * np.pi * f * t) for f in (110, 164.8, 220)) * 0.012 * (0.8 + 0.2 * np.sin(2 * np.pi * 0.1 * t))
    return tic + nappe

def bruit_woosh(graine=4):
    n = int(0.28 * SR); w = np.random.default_rng(graine).normal(0, 1, n); w = np.convolve(w, np.ones(24) / 24, "same")
    return w * np.sin(np.linspace(0, np.pi, n)) ** 2 * 0.12

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
    t = 0.2; ph = []; prev = None
    for i, (r, a) in enumerate(zip(reps, audios)):
        niv, lv = enveloppe(a); dur = len(a) / SR
        gs = groupes(r["t"]); poids = np.array([len(g) + 3 for g in gs], float); bo = np.concatenate([[0], np.cumsum(poids) / poids.sum()])
        t0 = t; att = float(r.get("attente", 0)); t += att
        q = dict(i=i, p=r["p"], deb=t, att=att, fin=t + dur, audio=a, niv=niv, lv=lv, chute=bool(r.get("chute")),
                 groupes=[(g, t + bo[k] * dur, t + bo[k + 1] * dur) for k, g in enumerate(gs)])
        # début du plan : coupe vers celui qui parle ; après une vanne, on coupe tôt sur la réaction (visage impassible)
        if r["p"] != prev:
            q["plan"] = (ph[-1]["fin"] + 0.22) if (ph and ph[-1]["chute"]) else max(0, t0 - 0.12)
            q["reaction"] = bool(ph and ph[-1]["chute"])
        else:
            q["plan"] = None
        gg = q["groupes"]; dz = gg[0][1]
        for k2 in range(len(gg) - 1):
            if re.search(r"[.!?…]$", gg[k2][0]): dz = gg[k2 + 1][1]
        q["dz"] = dz; ph.append(q); prev = r["p"]
        t += dur + (0.62 if r.get("chute") else 0.08)
    total = t + 0.7; nf = int(total * FPS)
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

    # ---- son
    n = int(SR * (total + 1)); voixm = np.zeros(n)
    for q in ph:
        a = salle(q["audio"]) if q["p"] == "envoyee" else q["audio"]; s = int(q["deb"] * SR); voixm[s:s + len(a)] += a[:n - s]
    env = np.convolve(np.abs(voixm), np.ones(int(0.15 * SR)) / int(0.15 * SR), "same"); env = np.clip(env / (np.percentile(env, 95) + 1e-6), 0, 1)
    mix = voixm + lit_musical(n) * (1 - 0.65 * env)
    jg = jingle(); mix[:len(jg)] += jg * 0.8
    for q in ph:
        if q["plan"] is not None and q["i"] > 0 and (q["p"] == "envoyee" or q["i"] == gag_i):
            w = bruit_woosh(q["i"]); s = int(q["debplan"] * SR); mix[s:s + len(w)] += w
    th = np.arange(int(0.5 * SR)) / SR
    hit = np.sin(2 * np.pi * 62 * th) * np.exp(-th * 8) * 0.2 + np.random.default_rng(2).normal(0, 1, len(th)) * np.exp(-th * 45) * 0.04
    for q in ph:
        if q["chute"]: s = int((q["fin"] + 0.03) * SR); mix[s:s + len(hit)] += hit[:n - s]
    mix = np.clip(mix / max(1.0, np.abs(mix).max() / 0.95), -0.99, 0.99)
    brut = f"{tmp}/mix.wav"; wav = f"{tmp}/mix_norm.wav"
    with wave.open(brut, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", brut, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", wav], check=True)

    # ---- calques
    ENT = entete(sk.get("sujet", "L'ACTU")); DIRECT = etiquette("DIRECT", (220, 35, 45, 240), point=True)
    TICK, TLAB = bandeau_defilant(sk.get("bandeau")); RECO = etiquette("RECONSTITUTION", (220, 35, 45, 240), taille=38)
    IA = etiquette("image générée par IA", (0, 0, 0, 150), taille=24)
    L_PLAT = etiquette("PLATEAU", (16, 20, 36, 230), taille=30); L_DIR = etiquette(f"EN DIRECT · {sk.get('lieu_direct', '').upper()}", (220, 35, 45, 240), taille=30)
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

    def image(fi):
        tm = fi / FPS
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
        e = ENT if tm > 0.35 else ENT[int(150 * (1 - tm / 0.35) ** 2):]
        poser(fr, e, 0, HEAD_Y)
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
