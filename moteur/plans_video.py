"""Changements de plan de la vidéo d'origine par TransNetV2 (Souček et Lokoč ; portage PyTorch MIT, poids compris dans le paquet
transnetv2-pytorch ; choix de l'auteur du 11 novembre 2026, idée 10). Réseau entraîné pour ça : il ne confond plus un mouvement
rapide ou un flash avec une coupe, et voit les fondus. Sert à analyse_video (plans, images clés, coupes du montage d'origine) et au
témoin visages (personnages suivis plan par plan). Lu une fois par vidéo (gardé en mémoire), ~10-20 s sur la machine.
Absent ou en échec -> l'ancienne détection (couleurs et différences d'image). TRANSNET=0 pour couper."""
import os, subprocess
import numpy as np

_M, _MEMO = {}, {}


def coupes(video, seuil=0.5, duree_max=200):
    """Instants (s) des changements de plan, ou None si l'outil manque."""
    if os.environ.get("TRANSNET", "1") == "0" or not video or not os.path.exists(video) or _M.get("echec"): return None
    if video in _MEMO: return _MEMO[video]
    try:
        import torch
        from transnetv2_pytorch import TransNetV2
        if "m" not in _M:
            m = TransNetV2(device="cpu"); m.eval(); _M["m"] = m
        fps = _fps(video)
        r = subprocess.run(["ffmpeg", "-v", "error", "-t", str(duree_max), "-i", video, "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "48x27", "-"],
                           capture_output=True, check=True)
        img = np.frombuffer(r.stdout, np.uint8).reshape(-1, 27, 48, 3)
        if len(img) < 10: return None
        with torch.no_grad(): un, _tous = _M["m"].predict_frames(torch.from_numpy(img.copy()), quiet=True)
        p = un.detach().cpu().numpy().reshape(-1)
        out = instants(p, fps, seuil)
        _MEMO[video] = out
        print(f"  TransNetV2 : {len(out)} changement(s) de plan dans l'original", flush=True)
        return out
    except Exception as e:
        print(f"  TransNetV2 indisponible ({str(e)[:120]}) : détection des coupes par l'image", flush=True); _M["echec"] = True
        return None


def instants(p, fps, seuil=0.5):
    """Probabilités de coupe image par image -> instants des coupes (une par groupe d'images au-dessus du seuil)."""
    out, dedans = [], False
    for i, v in enumerate(np.asarray(p, np.float64)):
        if v > seuil and not dedans: out.append(round((i + 0.5) / fps, 2)); dedans = True
        elif v <= seuil: dedans = False
    return [t for t in out if t > 0.1]


def _fps(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=avg_frame_rate", "-of", "csv=p=0", video],
                       capture_output=True, text=True)
    try:
        a, b = r.stdout.strip().split("/"); f = float(a) / float(b)
        return f if 1 < f < 240 else 30.0
    except Exception: return 30.0


def entre(cps, t0, t1):
    """Une coupe entre deux images échantillonnées (t0, t1] ?"""
    return any(t0 < c <= t1 for c in cps or [])
