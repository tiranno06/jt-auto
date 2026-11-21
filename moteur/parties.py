"""Vidéos longues en deux parties (choix de l'auteur du 21 novembre 2026, idée 5) : un son de plus de 70 s (PARTIES_MIN) donne, en
plus de la vidéo complète, deux vidéos (base_p1.mp4, base_p2.mp4) coupées entre deux répliques, au blanc le plus proche du milieu.
La partie 1 finit sur un carton « La suite dans la partie 2 👉 », la partie 2 commence avec « PARTIE 2 » en grand. À la publication
(publier.py), la partie 1 part à l'heure prévue et la partie 2 quelques heures après (PARTIES_ECART, 4 h) : la 2e ramène les gens
sur le profil (abonnés). Sans Buffer, ou avec PARTIES=0, la vidéo complète est publiée comme avant."""
import os, subprocess, tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
POLICE = os.path.join(ICI, "..", "polices", "Poppins-Bold.ttf")


def actif():
    return os.environ.get("PARTIES", "1") != "0"


def seuil():
    try: return float(os.environ.get("PARTIES_MIN") or 70)
    except ValueError: return 70.0


def ecart_heures():
    try: return max(1.0, float(os.environ.get("PARTIES_ECART") or 4))
    except ValueError: return 4.0


def coupure(repliques, duree):
    """Instant de coupure : le milieu du plus long blanc entre deux répliques, le plus près du milieu de la vidéo (entre 35 % et 65 %)."""
    reps = sorted((float(r["_deb"]), float(r["_fin"])) for r in repliques or [] if r.get("_deb") is not None and r.get("_fin") is not None)
    best = None
    for (a0, b0), (a1, _b1) in zip(reps, reps[1:]):
        if not 0.35 * duree <= b0 <= 0.65 * duree: continue
        blanc = a1 - b0
        if blanc < 0.08: continue
        note = min(blanc, 0.6) - 0.06 * abs((b0 + a1) / 2 - duree / 2)   # un vrai blanc, le plus près du milieu
        if best is None or note > best[0]: best = (note, (b0 + a1) / 2)
    return round(best[1], 2) if best else None


def _x264(): return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k"]


def _txt(t): return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def decouper(video, repliques, duree):
    """Crée video_p1.mp4 et video_p2.mp4 ; renvoie ([noms], instant de coupure) ou (None, None)."""
    if not actif() or duree < seuil() or not os.path.exists(video): return None, None
    t = coupure(repliques, duree)
    if t is None: return None, None
    b = os.path.splitext(video)[0]; p1, p2 = b + "_p1.mp4", b + "_p2.mp4"
    d = tempfile.mkdtemp(); corps = os.path.join(d, "corps.mp4"); carton = os.path.join(d, "carton.mp4")
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-t", f"{t:.2f}", *_x264(), corps], check=True)
        fond = (f"drawtext=fontfile={POLICE}:text='{_txt('La suite dans la')}':fontcolor=white:fontsize=78:x=(w-text_w)/2:y=h*0.40:"
                f"borderw=6:bordercolor=black,drawtext=fontfile={POLICE}:text='{_txt('PARTIE 2')}':fontcolor=0xFFD628:fontsize=120:"
                f"x=(w-text_w)/2:y=h*0.48:borderw=8:bordercolor=black")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.04", "-i", corps, "-f", "lavfi", "-t", "1.8", "-i", "anullsrc=r=44100:cl=stereo",
                        "-filter_complex", f"[0:v]loop=loop=-1:size=1,trim=duration=1.8,setpts=PTS-STARTPTS,eq=brightness=-0.25,{fond}[v]",
                        "-map", "[v]", "-map", "1:a", "-r", "30", *_x264(), carton], check=True)
        liste = os.path.join(d, "liste.txt"); open(liste, "w").write(f"file '{corps}'\nfile '{carton}'\n")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", liste, "-r", "30", *_x264(), p1], check=True)
        titre = (f"drawtext=fontfile={POLICE}:text='PARTIE 2':fontcolor=0xFFD628:fontsize=130:x=(w-text_w)/2:y=h*0.17:"
                 f"borderw=9:bordercolor=black:enable='lt(t,2.5)'")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, t - 0.15):.2f}", "-i", video, "-vf", titre, *_x264(), p2], check=True)
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"  parties : découpage impossible ({str(e)[:120]}) : la vidéo complète seulement", flush=True)
        for f in (p1, p2):
            if os.path.exists(f): os.remove(f)
        return None, None
    print(f"  vidéo en deux parties : coupure à {t:.1f} s sur {duree:.0f} s ({os.path.basename(p1)}, {os.path.basename(p2)})", flush=True)
    return [os.path.basename(p1), os.path.basename(p2)], t


SUITE = "👉 La partie 2 arrive dans quelques heures : abonne-toi pour ne pas la rater !"


def legende_partie(legende, n):
    """Description d'une partie : la 1re annonce la suite, la 2e se présente comme la suite."""
    l = str(legende or "").strip()
    if n == 1: return SUITE + "\n\n" + l
    return "Partie 2/2 🎬 (la partie 1 est juste avant sur le profil)\n\n" + l
