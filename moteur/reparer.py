"""Réparation d'une vidéo déjà archivée (workflow reparer.yml) : remet le son à sa place quand il a été décalé (le contrôle final du
31 octobre 2026 avait « recalé » à tort le son de « Retrait bancaire » de +0,28 s ; cette fonction est maintenant retirée).
La vidéo pleine qualité est remuxée sans réencodage (son remis à 0), la version légère refaite, puis les deux renvoyées aux archives.
Usage : FICHIER=2026-10-31_15h34_emission.mp4 python moteur/reparer.py"""
import json, os, re, subprocess, sys, tempfile

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def debut_son(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=start_time", "-of", "csv=p=0", video],
                       capture_output=True, text=True)
    try: return float(r.stdout.strip() or 0)
    except ValueError: return 0.0


def main():
    nom = os.environ.get("FICHIER", "").strip()
    if not re.fullmatch(r"[\w.-]+\.mp4", nom): print(f"Nom refusé : {nom!r}"); return 1
    hist = json.load(open(os.path.join(RACINE, "episodes", "historique.json"), encoding="utf-8"))
    e = next((h for h in hist if h.get("fichier") == nom), None)
    if not e: print(f"{nom} introuvable"); return 1
    tag = e.get("tag") or f"emissions-{nom[:7]}"; tmp = tempfile.mkdtemp(); src = os.path.join(tmp, nom)
    subprocess.run(["gh", "release", "download", tag, "-p", nom, "-D", tmp, "--clobber"], check=True)
    d = debut_son(src)
    if abs(d) < 0.02: print(f"Son déjà à sa place ({d:+.3f} s) : rien à réparer"); return 0
    ok = os.path.join(tmp, "ok.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-itsoffset", f"{-d:.3f}", "-i", src, "-map", "0:v", "-map", "1:a", "-c", "copy", ok], check=True)
    print(f"Son remis à sa place ({d:+.3f} s -> {debut_son(ok):+.3f} s)")
    os.replace(ok, src)
    web = os.path.join(tmp, nom.replace(".mp4", "_web.mp4"))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", "scale=720:-2,fps=30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", web], check=True)
    subprocess.run(["gh", "release", "upload", tag, src, web, "--clobber"], check=True)
    print(f"Réparée et renvoyée aux archives : {nom} (+ version légère)"); return 0


if __name__ == "__main__":
    sys.exit(main())
