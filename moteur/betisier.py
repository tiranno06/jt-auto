"""Bêtisier de la semaine (idée 3 de l'auteur) : les ratés relevés par le jury dans les vidéos des 7 derniers jours, montés en
une quinzaine de secondes. Chaque raté = 3 secondes autour de l'instant noté par le jury (« 49 s La chute manque d'impact »),
avec la remarque du jury en bandeau, un tampon « RATÉ ! » et un « boing ». Carton d'ouverture aux couleurs de la chaîne.

Lancé chaque dimanche par le workflow « Bêtisier de la semaine » (betisier.yml) ; la vidéo arrive dans la liste du site comme les
autres (jamais publiée automatiquement). Gratuit : aucun outil payant, seulement ffmpeg.
Usage : python moteur/betisier.py [jours]"""
import datetime, json, math, os, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ICI = os.path.dirname(os.path.abspath(__file__)); RACINE = os.path.join(ICI, "..")
HIST = os.path.join(RACINE, "episodes", "historique.json")
POLICE = os.path.join(RACINE, "polices", "Poppins-Bold.ttf")
W, H, IPS, SR = 1080, 1920, 30, 44100
JAUNE = (255, 214, 40); NOIR = (26, 22, 30)


def moments(historique, jours=7, aujourd_hui=None, nb=4):
    """Les ratés à montrer : (vidéo, instant en s, remarque), des vidéos les moins bien notées d'abord, 2 par vidéo au plus."""
    jour0 = (aujourd_hui or datetime.date.today()) - datetime.timedelta(days=jours)
    cands = []
    for h in historique:
        try: d = datetime.date.fromisoformat(str(h.get("date", ""))[:10])
        except ValueError: continue
        if d < jour0 or not h.get("fichier") or h.get("betisier"): continue
        txt = str(h.get("controle_video") or "")
        notes = [(float(m.group(1).replace(",", ".")), m.group(2).strip(" .")) for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*s\s+([^;]{8,160})", txt)]
        duree = float(h.get("duree") or 0)
        notes = [(t, r) for t, r in notes if 1.5 <= t <= max(1.5, duree - 0.5)][:2]
        for t, r in notes: cands.append((float(h.get("note") or 50), h, t, r))
    cands.sort(key=lambda c: c[0])
    out, par_video = [], {}
    for _, h, t, r in cands:
        if par_video.get(h["fichier"], 0) >= 2: continue
        par_video[h["fichier"]] = par_video.get(h["fichier"], 0) + 1; out.append((h, t, r))
        if len(out) >= nb: break
    return out


def _police(t): return ImageFont.truetype(POLICE, t)


def _lignes(d, txt, f, w):
    mots, lignes, cur = txt.split(), [], ""
    for m in mots:
        if d.textlength((cur + " " + m).strip(), font=f) <= w: cur = (cur + " " + m).strip()
        else: lignes.append(cur); cur = m
    return lignes + [cur] if cur else lignes


def bandeau(remarque, numero):
    """Calque PNG (RGBA) d'un raté : bandeau « BÊTISIER » en haut, remarque du jury en bas, tampon « RATÉ ! »."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((40, 150, W - 40, 300), 30, fill=JAUNE + (255,), outline=NOIR + (255,), width=8)
    f = _police(70); t = f"BÊTISIER  #{numero}"; d.text(((W - d.textlength(t, font=f)) / 2, 182), t, font=f, fill=NOIR + (255,))
    f2 = _police(46); L = _lignes(d, f"Le jury : « {remarque} »", f2, W - 160)[:4]
    h_ = 60 * len(L) + 60; y0 = H - 380 - h_
    d.rounded_rectangle((50, y0, W - 50, y0 + h_), 28, fill=(255, 255, 255, 235), outline=NOIR + (255,), width=6)
    for k, l in enumerate(L): d.text(((W - d.textlength(l, font=f2)) / 2, y0 + 30 + 60 * k), l, font=f2, fill=NOIR + (255,))
    return im


def tampon():
    """Tampon rouge « RATÉ ! » penché (posé à la fin de chaque raté)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); s = Image.new("RGBA", (760, 260), (0, 0, 0, 0)); d = ImageDraw.Draw(s)
    d.rounded_rectangle((10, 10, 750, 250), 30, outline=(220, 40, 50, 255), width=18)
    f = _police(150); d.text(((760 - d.textlength("RATÉ !", font=f)) / 2, 30), "RATÉ !", font=f, fill=(220, 40, 50, 255))
    s = s.rotate(14, expand=True, resample=Image.BICUBIC); im.paste(s, ((W - s.width) // 2, int(H * 0.42) - s.height // 2), s)
    return im


def carton(n):
    im = Image.new("RGB", (W, H), JAUNE); d = ImageDraw.Draw(im)
    for k in range(24):                                                    # rayons

        a0, a1 = k * math.pi / 12, k * math.pi / 12 + math.pi / 24
        d.polygon([(W / 2, H * 0.42), (W / 2 + 3000 * math.cos(a0), H * 0.42 + 3000 * math.sin(a0)), (W / 2 + 3000 * math.cos(a1), H * 0.42 + 3000 * math.sin(a1))], fill=(255, 196, 30))
    f = _police(130); f2 = _police(64)
    for k, l in enumerate(("LE BÊTISIER", "DE LA SEMAINE")):
        w = d.textlength(l, font=f); x, y = (W - w) / 2, H * 0.34 + k * 160
        for dx in range(-8, 9, 4):
            for dy in range(-8, 9, 4): d.text((x + dx, y + dy), l, font=f, fill=NOIR)
        d.text((x, y), l, font=f, fill=(255, 255, 255))
    t = f"{n} ratés relevés par notre jury"; d.text(((W - d.textlength(t, font=f2)) / 2, H * 0.58), t, font=f2, fill=NOIR)
    return im


def _boing(chemin, duree=0.5):
    t = np.arange(int(SR * duree)) / SR; f = 520 * np.exp(-t * 3.2) + 120
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5) * (1 + 0.6 * np.sin(2 * np.pi * 14 * t)) * 0.45
    import wave
    with wave.open(chemin, "wb") as w_:
        w_.setnchannels(1); w_.setsampwidth(2); w_.setframerate(SR); w_.writeframes((np.clip(s, -1, 1) * 32767).astype(np.int16).tobytes())


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def monter(rates, sortie, videos):
    """rates : [(historique, instant, remarque)] ; videos : {fichier: chemin local}. Écrit la vidéo, renvoie sa durée."""
    tmp = tempfile.mkdtemp(); morceaux = []
    carton(len(rates)).save(f"{tmp}/carton.png")
    _ff("-loop", "1", "-t", "1.6", "-i", f"{tmp}/carton.png", "-f", "lavfi", "-t", "1.6", "-i", f"anullsrc=r={SR}:cl=stereo",
        "-vf", f"scale={W}:{H},fps={IPS},format=yuv420p", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-shortest", f"{tmp}/m0.mp4")
    morceaux.append(f"{tmp}/m0.mp4"); _boing(f"{tmp}/boing.wav"); tampon().save(f"{tmp}/tampon.png")
    for k, (h, t, r) in enumerate(rates, 1):
        src = videos.get(h["fichier"])
        if not src or not os.path.exists(src): continue
        bandeau(r, k).save(f"{tmp}/b{k}.png"); d0 = max(0.0, t - 1.7); L = 3.4
        _ff("-ss", f"{d0:.2f}", "-t", f"{L:.2f}", "-i", src, "-i", f"{tmp}/b{k}.png", "-i", f"{tmp}/tampon.png", "-i", f"{tmp}/boing.wav",
            "-filter_complex",
            f"[0:v]scale={W}:{H},fps={IPS},setpts=PTS-STARTPTS[v0];[v0][1:v]overlay=0:0[v1];"
            f"[v1][2:v]overlay=0:0:enable='gte(t,{L - 0.9:.2f})'[v];"
            f"[0:a]aresample={SR},atrim=0:{L:.2f},asetpts=PTS-STARTPTS[a0];[3:a]adelay={int((L - 0.9) * 1000)}|{int((L - 0.9) * 1000)},aresample={SR}[b];"
            f"[a0][b]amix=inputs=2:duration=first:normalize=0[a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", "-ac", "2", "-ar", str(SR),
            "-pix_fmt", "yuv420p", f"{tmp}/m{k}.mp4")
        morceaux.append(f"{tmp}/m{k}.mp4")
    if len(morceaux) < 3: return 0.0                                       # moins de 2 ratés : pas de bêtisier cette semaine
    entrees = sum((["-i", m] for m in morceaux), [])
    concat = "".join(f"[{i}:v][{i}:a]" for i in range(len(morceaux))) + f"concat=n={len(morceaux)}:v=1:a=1[v][a]"
    _ff(*entrees, "-filter_complex", concat, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "slow",
        "-tune", "animation", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", sortie)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", sortie], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def telecharger(rates, dossier):
    """Vidéos d'origine depuis les Releases GitHub (gh release download)."""
    os.makedirs(dossier, exist_ok=True); out = {}
    for h, _, _ in rates:
        f = h["fichier"]
        if f in out: continue
        chemin = os.path.join(dossier, f)
        if not os.path.exists(chemin):
            r = subprocess.run(["gh", "release", "download", h.get("tag") or f"emissions-{h['date'][:7]}", "--pattern", f, "--dir", dossier, "--clobber"], capture_output=True, text=True)
            if r.returncode: print(f"  {f} introuvable : {r.stderr.strip()[:160]}", flush=True); continue
        out[f] = chemin
    return out


def main(jours=7):
    historique = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else []
    rates = moments(historique, jours)
    print(f"Bêtisier : {len(rates)} raté(s) trouvé(s) dans les {jours} derniers jours", flush=True)
    if len(rates) < 2: print("Pas assez de ratés cette semaine : pas de bêtisier."); return 0
    videos = telecharger(rates, os.path.join(RACINE, "sortie", "sources"))
    rates = [x for x in rates if x[0]["fichier"] in videos]
    jour = datetime.date.today().isoformat(); base = os.path.join(RACINE, "sortie", f"{jour}_betisier")
    os.makedirs(os.path.dirname(base), exist_ok=True)
    duree = monter(rates, base + ".mp4", videos)
    if duree <= 0: print("Montage impossible : pas de bêtisier."); return 0
    legende = ("Le bêtisier de la semaine 🎬 Nos personnages ne sont pas parfaits… et notre jury le leur fait savoir 😅\n\n"
               "Lequel est le pire ?\n\n#petitsdramas #betisier #humour #dessinanime\n\nContenu généré par IA.")
    open(base + ".txt", "w", encoding="utf-8").write(legende + "\n")
    historique.append(dict(date=jour, format="mini", titre="LE BÊTISIER DE LA SEMAINE", titre_affiche="Le bêtisier de la semaine",
                           sources=[x[0]["fichier"] for x in rates], note=None, decision="bêtisier automatique (ratés relevés par le jury)",
                           accroche="Le bêtisier de la semaine", duree=round(duree, 1), fichier=os.path.basename(base) + ".mp4",
                           tag=f"emissions-{jour[:7]}", legende=legende, publie=None, manuel=True, betisier=True,
                           outils=dict(claude="aucun", voix="aucune", decors="aucun")))
    json.dump(historique, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sortie = os.environ.get("GITHUB_OUTPUT")
    if sortie:
        with open(sortie, "a") as f:
            f.write(f"video={base}.mp4\nlegende={base}.txt\nnom={os.path.basename(base)}.mp4\nmois={jour[:7]}\n")
    print(f"OK : {base}.mp4 ({duree:.1f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 7))
