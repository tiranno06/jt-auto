"""Fin en boucle (idée 11 de l'auteur) : TikTok rejoue la vidéo en boucle ; si la dernière image se raccorde à la première, le
spectateur la revoit sans s'en rendre compte (bon pour l'algorithme). La dernière demi-seconde glisse en fondu vers la toute
première image ; le son s'éteint doucement. Réglage BOUCLE=0 pour couper."""
import json, os, subprocess, tempfile


def _duree(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", f], capture_output=True, text=True)
    return float(json.loads(r.stdout or "{}").get("format", {}).get("duration") or 0)


def _video(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", f], capture_output=True, text=True)
    s = (json.loads(r.stdout or "{}").get("streams") or [{}])[0]
    a, b = str(s.get("r_frame_rate") or "30/1").split("/")
    return int(s.get("width") or 1080), int(s.get("height") or 1920), round(float(a) / float(b or 1))


def boucler(chemin, fondu=0.35, tenue=0.25):
    """Ajoute le raccord de boucle à la fin de la vidéo (en place). Renvoie la nouvelle durée (ou l'ancienne si impossible)."""
    d = _duree(chemin)
    if os.environ.get("BOUCLE", "1") == "0" or d < 3: return d
    w, h, ips = _video(chemin); tmp = tempfile.mkdtemp(); img0 = os.path.join(tmp, "debut.png"); sortie = os.path.join(tmp, "boucle.mp4")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.04", "-i", chemin, "-frames:v", "1", img0], check=True, timeout=120)
        fin = fondu + tenue; off = max(0.1, d - 0.05)
        filtre = (f"[1:v]scale={w}:{h},setsar=1,fps={ips},settb=AVTB,format=yuv420p[f];[0:v]fps={ips},settb=AVTB,format=yuv420p[v];"
                  f"[v][f]xfade=transition=fade:duration={fondu}:offset={off:.3f}[vo];"
                  f"[0:a]apad=pad_dur={fin:.3f},atrim=0:{off + fin:.3f},afade=t=out:st={off - 0.1:.3f}:d={fondu + 0.1:.3f}[ao]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", chemin, "-loop", "1", "-t", f"{fin + 0.1:.2f}", "-i", img0, "-filter_complex", filtre,
                        "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-crf", str(os.environ.get("CRF") or 15), "-preset", "medium", "-tune", "animation",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", sortie], check=True, timeout=1800)
        if _duree(sortie) < d: return d
        os.replace(sortie, chemin)
        print(f"fin en boucle : la dernière image se raccorde à la première ({fondu:.2f} s de fondu)", flush=True)
        return _duree(chemin)
    except Exception as e:
        print(f"fin en boucle impossible ({str(e)[:120]}) : vidéo gardée telle quelle", flush=True); return d
