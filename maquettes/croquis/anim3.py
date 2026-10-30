"""Animation croquis FLUIDE (≈ 11 s, 9:16, 30 i/s) : poses fondues (mouvement adouci), bouche qui s'ouvre selon la voix en gardant
l'expression, expressions en fondu, clignements doux, respiration, tête qui accompagne la parole, saut en arc."""
import os, sys, math, subprocess, wave, cv2, numpy as np
import croquis as C, serie2_outils as O
sys.path.insert(0, "/home/user/jt-auto/moteur"); import decor_dessin as D
W, H, IPS = 720, 1280, 30
k = W / 1080
r = D.dessiner("salon", {"moment": "soir"}, 12)
FOND = O.croquifier(cv2.resize(r["fond"], (W, H), interpolation=cv2.INTER_AREA), C.papier(W, H, 40), graine=12)
AVANT = cv2.resize(r["avant"], (W, H)) if r.get("avant") is not None else None
def lire(f):
    with wave.open(f) as w: sr = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a, sr
debuts = [0.4, 2.73, 4.11, 5.65]; QUI = ["papa", "fille", "papa", "fille"]
TXT = ["Ma puce… c'est quoi, cette note ?", "Bah… c'est un deux.", "Sur vingt ?!", "Non, sur dix ! C'est mieux, non ?"]
repl = []
for i, d in enumerate(debuts):
    a, sr = lire(f"voix/r{i}.wav"); repl.append((d, d + len(a) / sr, a, sr))
SR = repl[0][3]; DUREE = 11.0; N = int(DUREE * IPS)
piste = np.zeros(int(DUREE * SR), np.float32); voix = {"papa": np.zeros_like(piste), "fille": np.zeros_like(piste)}
for (d, f, a, _), q in zip(repl, QUI): piste[int(d * SR):int(d * SR) + len(a)] += a; voix[q][int(d * SR):int(d * SR) + len(a)] += a
with wave.open("voix/piste.wav", "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(piste, -1, 1) * 32767).astype(np.int16).tobytes())
def enveloppe(s):                                                          # ouverture de bouche 0..1, lissée (attaque rapide, retombée douce)
    out, v = [], 0.0
    for n in range(N):
        t = n / IPS; a = s[max(0, int((t - 0.025) * SR)):int((t + 0.025) * SR)]
        x = float(np.sqrt(np.mean(a ** 2))) if len(a) else 0.0
        v = v + (x - v) * (0.6 if x > v else 0.3); out.append(v)
    out = np.array(out); m = np.percentile(out[out > 0.005], 90) if (out > 0.005).any() else 1
    return np.clip(out / m, 0, 1) ** 0.8
OUV = {q: enveloppe(s) for q, s in voix.items()}
def lisse(u): u = min(1.0, max(0.0, u)); return u * u * (3 - 2 * u)      # mouvement adouci (départ et arrivée en douceur)
# images clés : (instant, expression, bras gauche, bras droit, jambes)
CLES = {"papa": [(0.0, "fache", "hanches", "hanches"), (2.55, "douteux", "croises", "croises"), (3.95, "surpris", "en_lair", "en_lair"),
                 (5.45, "etonne", "croises", "menton"), (8.95, "frustration", "ballants", "tete")],
        "fille": [(0.0, "honteux", "joint", "joint"), (2.55, "honteux", "ballants", "tete"), (4.0, "peur", "joint", "joint"),
                  (5.5, "joie", "ballants", "devant"), (8.95, "joie", "en_lair", "en_lair")]}
TRANS = 0.45; FONDU = 0.28
def etat(qui, t):
    L = CLES[qui]; j = max(i for i, c in enumerate(L) if c[0] <= t); cur = L[j]; prev = L[j - 1] if j else cur
    u = lisse((t - cur[0]) / TRANS)
    bras = tuple((p, c, u) for p, c in zip(prev[2:4], cur[2:4]))
    a_expr = min(1.0, (t - cur[0]) / FONDU) if j else 1.0
    return bras, prev[1], cur[1], a_expr
def cligne(t, decal):
    tt = (t + decal) % 3.3; return max(0.0, 1 - abs(tt - 1.6) / 0.08)
def dessiner(t, choix):
    img = FOND.copy(); sol = 1500 * k
    for qui in ("papa", "fille"):
        bras, e0, e1, a = etat(qui, t); e = e1 if choix[qui] else e0
        n = min(N - 1, int(t * IPS)); ouv = float(OUV[qui][n])
        parle = ouv > 0.06
        souffle = math.sin(t * 2.1 + (0 if qui == "papa" else 1.3)) * 2.5
        penche = (math.sin(t * 7.5) * 0.025 * ouv) + (0.03 if parle else 0)
        if qui == "papa":
            R = O.AGES["grand"]["adulte"] * k * 1.4; x = 250 * k
            C.ombre_sol(img, (x, sol + 4), R * 0.9)
            C.bonhomme(img, x, sol + souffle, R, e, bras=bras, taille="grand", graine=1, haut="pull", c_haut=(90, 130, 190), c_bas=(55, 60, 75),
                       extras=[O.coiffure("courts", (60, 45, 35))], ouv=ouv if parle else None, cligne=cligne(t, 0.0), penche=penche)
        else:
            R = O.AGES["chibi"]["ado"] * k * 1.35; x = 780 * k
            hz = 0.0; jamb = ("debout", "debout")
            if t > 9.05:                                                   # sauts en arc (montée et descente adoucies)
                ph = ((t - 9.05) * 1.9) % 1.0; hz = math.sin(math.pi * ph) * 70
                u = lisse(min(1, hz / 30)); jamb = (("debout", "saut", u), ("debout", "saut", u))
            C.ombre_sol(img, (x, sol + 4), R * (0.9 - hz / 260))
            C.bonhomme(img, x, sol - hz - souffle * 0.6, R, e, bras=bras, jambes=jamb, taille="chibi", graine=2, c_haut=(230, 110, 150), c_bas=(70, 95, 150),
                       extras=[O.coiffure("queue", (150, 90, 50))], ouv=ouv if parle else None, cligne=cligne(t, 1.1), penche=-penche)
    if AVANT is not None: O.poser(img, AVANT, 0, 0, img)
    return img
def sous_titre(img, t):
    for i, (d, f, _, _) in enumerate(repl):
        if d - 0.05 <= t <= f + 0.2:
            from PIL import Image, ImageDraw, ImageFont
            al = min(1, (t - d + 0.05) / 0.12, (f + 0.2 - t) / 0.12)          # sous-titre qui apparaît et disparaît en fondu
            pil = Image.fromarray(img); calque = Image.new("RGBA", pil.size, (0, 0, 0, 0)); dd = ImageDraw.Draw(calque); fo = ImageFont.truetype(O.POLB, 40)
            w = dd.textlength(TXT[i], font=fo); dd.text(((W - w) / 2, 1090), TXT[i], font=fo, fill=(255, 255, 255, int(255 * al)), stroke_width=5, stroke_fill=(25, 22, 28, int(255 * al)))
            img[:] = np.array(Image.alpha_composite(pil.convert("RGBA"), calque).convert("RGB"))
tmp = "anim3_frames"; os.makedirs(tmp, exist_ok=True)
for n in range(N):
    t = n / IPS
    fondus = {q: etat(q, t)[3] for q in ("papa", "fille")}
    img = dessiner(t, {"papa": True, "fille": True})
    if any(a < 1 for a in fondus.values()):                               # changement d'expression : fondu entre l'ancienne et la nouvelle
        a_ = min(fondus.values()); avant = dessiner(t, {q: fondus[q] >= 1 for q in fondus})
        img = (avant.astype(np.float32) * (1 - lisse(a_)) + img.astype(np.float32) * lisse(a_)).astype(np.uint8)
    sous_titre(img, t)
    cv2.imwrite(f"{tmp}/{n:04d}.png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    if n % 60 == 0: print(n, "/", N, flush=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(IPS), "-i", f"{tmp}/%04d.png", "-i", "voix/piste.wav",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17", "-tune", "animation", "-c:a", "aac", "-b:a", "160k", "-shortest",
                "final/11_animation_fluide.mp4"], check=True)
print("fini")
