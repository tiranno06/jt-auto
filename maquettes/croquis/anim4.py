"""Essai des mouvements choisis par l'auteur (5, 8, 10, 11, 13-29, 31-35) dans le style croquis — rien n'est branché au robot."""
import os, sys, math, subprocess, wave, re, cv2, numpy as np
import croquis as C, serie2_outils as O
sys.path.insert(0, "/home/user/jt-auto/moteur"); import decor_dessin as D
W, H, IPS = 720, 1280, 30
k = W / 1080; SOL = 1500 * k
r = D.dessiner("salon", {"moment": "soir"}, 12)
FOND = O.croquifier(cv2.resize(r["fond"], (W, H), interpolation=cv2.INTER_AREA), C.papier(W, H, 40), graine=12)
AVANT = cv2.resize(r["avant"], (W, H)) if r.get("avant") is not None else None
def lire(f):
    with wave.open(f) as w: sr = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if sr != 22050:
        from scipy.signal import resample_poly
        a = resample_poly(a, 22050, sr).astype(np.float32)
    return a, 22050
# ---------------------------------------------------------------- son et texte
REPL = [(1.0, "fille", "Papa ! J'ai eu ma note de maths !", "maths"), (4.6, "papa", "Ah oui ? Combien ?", "Combien"),
        (6.2, "fille", "Euh… deux.", None), (7.9, "papa", "Deux ?!", "Deux"), (8.9, "fille", "Sur vingt… mais c'est presque la moyenne !", "presque"),
        (12.5, "fille", "Je rigole ! J'ai eu dix-huit !", "dix-huit"), (15.0, "papa", "Reviens ici, toi !", "Reviens")]
DUREE = 19.0; N = int(DUREE * IPS); SR = 22050
piste = np.zeros(int(DUREE * SR), np.float32); voix = {"papa": np.zeros_like(piste), "fille": np.zeros_like(piste)}; segs = []
for i, (d, qui, txt, appui) in enumerate(REPL):
    a, SR = lire(f"voix/s{i}.wav"); piste[int(d * SR):int(d * SR) + len(a)] += a; voix[qui][int(d * SR):int(d * SR) + len(a)] += a
    segs.append((d, d + len(a) / SR, qui, txt, appui))
with wave.open("voix/piste4.wav", "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(piste, -1, 1) * 32767).astype(np.int16).tobytes())
def enveloppe(s):
    out, v = [], 0.0
    for n in range(N):
        t = n / IPS; a = s[max(0, int((t - 0.025) * SR)):int((t + 0.025) * SR)]
        x = float(np.sqrt(np.mean(a ** 2))) if len(a) else 0.0
        v = v + (x - v) * (0.6 if x > v else 0.3); out.append(v)
    out = np.array(out); m = np.percentile(out[out > 0.005], 90) if (out > 0.005).any() else 1
    return np.clip(out / m, 0, 1) ** 0.8
OUV = {q: enveloppe(s) for q, s in voix.items()}
def son(qui, t):                                                           # 11 : forme de bouche selon la lettre prononcée
    for d, f, q, txt, _ in segs:
        if q == qui and d <= t <= f:
            lettres = re.sub(r"[^a-zéèêàùôîç]", "", txt.lower()); i = min(len(lettres) - 1, int((t - d) / (f - d) * len(lettres)))
            c = lettres[i]
            return "m" if c in "mbp" else "o" if c in "ouô" else "i" if c in "iéèeêy" else "a"
    return "a"
def appui(qui, t):                                                         # 10 : sourcils qui montent sur le mot appuyé
    for d, f, q, txt, ap in segs:
        if q == qui and ap and d <= t <= f:
            pos = txt.find(ap) / max(1, len(txt)); tm = d + pos * (f - d) + 0.12
            return max(0.0, 1 - abs(t - tm) / 0.35)
    return 0.0
def parle(qui, t): return any(q == qui and d - 0.05 <= t <= f + 0.1 for d, f, q, _, _ in segs)
# ---------------------------------------------------------------- outils de mouvement
def lisse(u): u = min(1.0, max(0.0, u)); return u * u * (3 - 2 * u)
def ressort(u, s=1.4):                                                     # 27 + 28 : anticipation (petit recul) puis dépassement et retour
    u = min(1.0, max(0.0, u)); s2 = s * 1.525
    return (2 * u) ** 2 * ((s2 + 1) * 2 * u - s2) / 2 if u < 0.5 else ((2 * u - 2) ** 2 * ((s2 + 1) * (2 * u - 2) + s2) + 2) / 2
def piste_val(cles, t, interp=lisse, dur=0.5):
    """cles : [(t, valeur)] -> valeur adoucie entre deux clés (nombre)."""
    v = cles[0][1]
    for (t0, a), (t1, b) in zip(cles, cles[1:]):
        if t >= t1: v = b; continue
        if t >= t0: u = interp(min(1, (t - t0) / min(dur, t1 - t0) if t1 > t0 else 1)); v = a + (b - a) * u
        break
    else: v = cles[-1][1]
    return v
def pose(cles, t, dur=0.45, interp=ressort):
    """cles : [(t, poseG, poseD)] -> bras fondus (avec anticipation et dépassement)."""
    j = max(i for i, c in enumerate(cles) if c[0] <= t); cur = cles[j]; prev = cles[j - 1] if j else cur
    u = interp((t - cur[0]) / dur)
    return tuple((p, c, u) for p, c in zip(prev[1:3], cur[1:3]))
def expr(cles, t):
    j = max(i for i, c in enumerate(cles) if c[0] <= t); return (cles[j - 1][1] if j else cles[j][1]), cles[j][1], min(1.0, (t - cles[j][0]) / 0.28) if j else 1.0
def cligne(t, decal): tt = (t + decal) % 3.4; return max(0.0, 1 - abs(tt - 1.7) / 0.08)
# ---------------------------------------------------------------- mise en scène
# position x (pixels 1080), avec marche / course
XF = [(0.0, 1250), (2.6, 790), (8.9, 790), (9.6, 860), (12.6, 860), (13.5, 610), (14.6, 610), (15.2, 610), (16.4, 1300)]   # 20, 22, 26
XP = [(0.0, 250), (8.0, 250), (8.15, 330), (8.5, 330), (15.6, 330), (16.9, 1350)]                                     # 22 avance, 26 poursuite
def x_de(cles, t):
    for (t0, a), (t1, b) in zip(cles, cles[1:]):
        if t0 <= t < t1: return a + (b - a) * (t - t0) / (t1 - t0) if abs(b - a) > 150 else a + (b - a) * lisse((t - t0) / (t1 - t0))
    return cles[-1][1] if t >= cles[-1][0] else cles[0][1]
def vitesse(cles, t): return (x_de(cles, t + 0.02) - x_de(cles, t - 0.02)) / 0.04
BRAS_P = [(0.0, "ballants", "telephone"), (3.7, "ballants", "ballants"), (5.0, "ballants", "devant"), (6.0, "croises", "croises"),
          (7.75, "ballants", "ballants"), (7.9, "en_lair", "en_lair"), (8.6, "hanches", "hanches"), (10.9, "tete", "tete"), (12.3, "croises", "croises"),
          (14.2, "ballants", "bouche"), (15.0, "ballants", "devant")]
EXPR_P = [(0.0, "neutre"), (3.7, "etonne"), (5.6, "douteux"), (7.75, "surpris"), (8.0, "colere"), (10.0, "fache"), (10.9, "frustration"), (12.5, "etonne"), (14.2, "surpris"), (15.0, "fache")]
BRAS_F = [(0.0, "ballants", "salut"), (2.6, "ballants", "devant"), (4.4, "joint", "joint"), (6.1, "ballants", "tete"), (7.9, "en_lair", "en_lair"),
          (8.3, "joint", "joint"), (10.4, "ballants", "ballants"), (12.4, "coeur", "coeur"), (13.5, "ballants", "ballants")]
EXPR_F = [(0.0, "joie"), (4.4, "neutre"), (5.9, "honteux"), (7.9, "peur"), (8.9, "inquiet"), (10.6, "malicieux"), (12.4, "joie"), (15.0, "peur")]
def personnage(img, qui, t, choix):
    if qui == "papa":
        x = x_de(XP, t) * k; R = O.AGES["grand"]["adulte"] * k * 1.4; taille = "grand"
        bras = pose(BRAS_P, t); e0, e1, a = expr(EXPR_P, t); e = e1 if choix else e0
        assis = piste_val([(0, 1.0), (3.9, 1.0), (4.5, 0.0)], t, lisse, 0.6)          # 21 : se lève
        jamb = (("debout", "assis", assis), ("debout", "assis", assis)) if assis > 0.01 else ("debout", "debout")
        regard = (0.0, 0.75) if t < 3.7 else (0.65, 0.0)                               # 8 : regarde son téléphone, puis 5 : regarde sa fille
        if 7.0 < t < 7.6: regard = (-0.6, -0.4)                                        # 25 : regards qui s'évitent (silence gêné)
        if 10.9 < t < 12.3: regard = (0.0, -0.8)                                       # 8 : yeux au ciel
        objet = C.tenir("telephone", 0.9) if t < 3.9 else None
        fx = {"regard": regard, "leve": appui("papa", t), "son": son("papa", t)}
        if 11.4 < t < 12.3: fx["micro"] = "joues"                                      # 13 : joues gonflées (soupir)
        rouge = piste_val([(0, 0), (7.9, 0.0), (8.3, 1.0), (12.3, 1.0), (13.0, 0.0)], t)
        teint = tuple(int(v) for v in np.array(C.PEAU) * (1 - 0.35 * rouge) + np.array((236, 118, 100)) * 0.35 * rouge) if rouge > 0.02 else None
        tremb = (math.sin(t * 61) * 2.5 if (8.0 < t < 8.8 or 10.9 < t < 11.4) else 0)  # 31 : tremble de rage
        autre = x_de(XF, t) * k
    else:
        x = x_de(XF, t) * k; R = O.AGES["chibi"]["ado"] * k * 1.35; taille = "chibi"
        bras = pose(BRAS_F, t); e0, e1, a = expr(EXPR_F, t); e = e1 if choix else e0
        jamb = ("debout", "debout"); teint = None; objet = None; tremb = 0
        regard = (-0.65, 0.0)
        if 6.0 < t < 7.6: regard = (-0.2, 0.8)                                         # 8 : regard au sol (gêne)
        if 7.0 < t < 7.3: regard = (-0.6, 0.0)                                         # 25 : petit coup d'œil vers papa
        fx = {"regard": regard, "leve": appui("fille", t), "son": son("fille", t), "rouge": piste_val([(0, 0), (6.1, 0), (6.6, 1.0), (8.0, 1.0), (8.6, 0.2)], t)}
        if 6.9 < t < 7.8: fx["micro"] = "mord"                                         # 13 : se mord la lèvre
        fx["sueur"] = piste_val([(0, 0), (8.6, 0), (9.3, 1.0), (11.0, 1.0), (11.6, 0)], t)
        fx["larmes"] = piste_val([(0, 0), (12.9, 0), (13.6, 0.8), (14.4, 0.8), (14.8, 0)], t)   # larmes de rire
        if 13.6 <= t < 14.6:                                                           # 24 : tape sur l'épaule de papa
            Rp = O.AGES["grand"]["adulte"] * k * 1.4; xp = x_de(XP, t) * k
            ep_ = (xp + Rp * 0.19, SOL - Rp * 2.3 - Rp * 1.2 + Rp * 0.1); tape = math.sin((t - 13.6) * 14) * Rp * 0.06
            u = lisse((t - 13.6) / 0.35) * (1 - lisse((t - 14.25) / 0.35))
            bras = ((bras[0][0] if isinstance(bras[0], tuple) else bras[0], ("cible", (ep_[0], ep_[1] + tape)), u), bras[1])
        autre = x_de(XP, t) * k
    vit = vitesse(XF if qui == "fille" else XP, t) * k; bouge = abs(vit) > 30
    sens = 1 if vit >= 0 else -1; hz = 0.0; ecr = 1.0; penche = 0.0
    if bouge:                                                                      # 19 + 16 : marche / course avec rebond et bras balancés
        court = abs(vit) > 500; pas = (t * (9.5 if court else 6.0))
        u = 0.5 + 0.5 * math.sin(pas)
        jamb = (("course_av" if court else "marche_av", "course_ar" if court else "marche_ar", u), ("course_ar" if court else "marche_ar", "course_av" if court else "marche_av", u))
        bras = (("course_av", "course_ar", u), ("course_ar", "course_av", u))
        hz = abs(math.sin(pas)) * (16 if court else 7); penche = 0.12 * sens if court else 0.04 * sens
    if 7.9 <= t < 8.35:                                                            # 32 + 29 : sursaut sur le cri (écrasé puis étiré)
        u = (t - 7.9) / 0.45; hz = max(hz, math.sin(math.pi * u) * (45 if qui == "fille" else 20)); ecr = 1 + 0.14 * math.sin(math.pi * u) - (0.12 if u > 0.85 else 0)
    if 12.6 < t < 14.4 and qui == "fille":                                         # 33 : épaules qui tressautent de rire
        hz += abs(math.sin(t * 18)) * 6; penche += math.sin(t * 9) * 0.05
    n = min(N - 1, int(t * IPS)); ouv = float(OUV[qui][n]); par = parle(qui, t)
    if par: penche += math.sin(t * 7.5) * 0.03 * ouv
    if not par and parle("papa" if qui == "fille" else "fille", t) and not bouge:  # 23 : celui qui écoute réagit (petits hochements)
        penche += math.sin(t * 4) * 0.025
    if bouge or 15.0 < t: fx["regard"] = (0.7 * sens, 0.0)
    souffle = math.sin(t * 2.1 + (0 if qui == "papa" else 1.3)) * 2.5
    if qui == "papa" and assis > 0.01: O.chaise(img, x + R * 0.1, SOL, R * 0.9, h=R * 2.3 * 0.55 - R * 0.05)
    C.ombre_sol(img, (x, SOL + 4), R * (0.9 - hz / 300))
    C.bonhomme(img, x + tremb, SOL - hz + souffle, R, e, bras=bras, jambes=jamb, taille=taille, graine=1 if qui == "papa" else 2,
               haut="pull" if qui == "papa" else "tshirt", c_haut=(90, 130, 190) if qui == "papa" else (230, 110, 150),
               c_bas=(55, 60, 75) if qui == "papa" else (70, 95, 150), teint=teint, objet=objet,
               extras=[O.coiffure("courts", (60, 45, 35)) if qui == "papa" else O.coiffure("queue", (150, 90, 50))],
               ouv=ouv if par else None, cligne=cligne(t, 0.0 if qui == "papa" else 1.1), penche=penche, fx=fx, sens=sens, ecrase=ecr)
    return a
def image(t, choix):
    img = FOND.copy(); fondus = {}
    for qui in ("papa", "fille"): fondus[qui] = personnage(img, qui, t, choix.get(qui, True))
    if AVANT is not None: O.poser(img, AVANT, 0, 0, img)
    return img, fondus
def sous_titre(img, t):
    from PIL import Image, ImageDraw, ImageFont
    for d, f, q, txt, _ in segs:
        if d - 0.05 <= t <= f + 0.25:
            al = min(1, (t - d + 0.05) / 0.12, (f + 0.25 - t) / 0.12)
            pil = Image.fromarray(img).convert("RGBA"); cal = Image.new("RGBA", pil.size, (0, 0, 0, 0)); dd = ImageDraw.Draw(cal); fo = ImageFont.truetype(O.POLB, 38)
            col = (255, 220, 120) if q == "papa" else (255, 190, 220)
            lignes, cur = [], ""
            for mot in txt.split():                                         # sous-titre coupé en lignes qui tiennent dans l'image
                if cur and dd.textlength(cur + " " + mot, font=fo) > W - 70: lignes.append(cur); cur = mot
                else: cur = (cur + " " + mot).strip()
            lignes.append(cur)
            for j, l in enumerate(lignes):
                w = dd.textlength(l, font=fo); dd.text(((W - w) / 2, 1085 - 24 * (len(lignes) - 1) + j * 48), l, font=fo, fill=col + (int(255 * al),), stroke_width=5, stroke_fill=(25, 22, 28, int(255 * al)))
            img[:] = np.array(Image.alpha_composite(pil, cal).convert("RGB"))
tmp = "anim4_frames"; os.makedirs(tmp, exist_ok=True)
for n in (range(N) if len(sys.argv) < 2 else [int(x) for x in sys.argv[1].split(",")]):
    t = n / IPS
    img, fondus = image(t, {})
    if any(a < 1 for a in fondus.values()):                                       # expressions en fondu
        a_ = min(fondus.values()); avant, _ = image(t, {q: fondus[q] >= 1 for q in fondus})
        img = (avant.astype(np.float32) * (1 - lisse(a_)) + img.astype(np.float32) * lisse(a_)).astype(np.uint8)
    sous_titre(img, t)
    cv2.imwrite(f"{tmp}/{n:04d}.png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    if n % 90 == 0: print(n, "/", N, flush=True)
if len(sys.argv) < 2: subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(IPS), "-i", f"{tmp}/%04d.png", "-i", "voix/piste4.wav",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17", "-tune", "animation", "-c:a", "aac", "-b:a", "160k", "-shortest",
                "final/12_animation_mouvements.mp4"], check=True)
print("fini")
