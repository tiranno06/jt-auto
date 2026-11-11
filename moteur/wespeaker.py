"""Empreinte de voix WeSpeaker (ResNet34, entraînée sur VoxCeleb ; code Apache 2.0, modèle CC-BY 4.0 : Wespeaker / wenet-e2e).
Choix de l'auteur du 11 novembre 2026, idée 4 : une 2e empreinte, différente d'ECAPA, pour mieux séparer deux personnages joués
par le même doubleur (locuteurs.rediariser : les deux empreintes sont mises bout à bout). Modèle ONNX (~26 Mo, sans code caché)
téléchargé une fois dans outils/wespeaker (cache du workflow) ; lancé par onnxruntime, déjà là pour RapidOCR. WESPEAKER=0 pour couper.
Caractéristiques : 80 bandes de Mel façon Kaldi (25 ms / 10 ms, pré-accentuation 0,97, fenêtre de Povey), moyenne retirée."""
import os, urllib.request
import numpy as np

URL = "https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM/resolve/main/voxceleb_resnet34_LM.onnx"
CHEMIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outils", "wespeaker", "voxceleb_resnet34_LM.onnx")
_S = {}


def _session():
    if os.environ.get("WESPEAKER", "1") == "0" or _S.get("echec"): return None
    if "s" in _S: return _S["s"]
    try:
        import onnxruntime as ort
        if not os.path.exists(CHEMIN):
            os.makedirs(os.path.dirname(CHEMIN), exist_ok=True)
            urllib.request.urlretrieve(URL, CHEMIN + ".part"); os.replace(CHEMIN + ".part", CHEMIN)
        o = ort.SessionOptions(); o.intra_op_num_threads = 2
        _S["s"] = ort.InferenceSession(CHEMIN, o, providers=["CPUExecutionProvider"])
        return _S["s"]
    except Exception as e:
        print(f"  empreinte WeSpeaker indisponible ({str(e)[:100]})", flush=True); _S["echec"] = True
        return None


def _mel(n_fft=512, n_mel=80, sr=16000, fmin=20.0, fmax=8000.0):
    if "mel" in _S: return _S["mel"]
    m = lambda f: 1127.0 * np.log(1 + f / 700.0)
    pts = np.linspace(m(fmin), m(fmax), n_mel + 2)
    fr = np.arange(n_fft // 2 + 1) * sr / n_fft; mf = m(fr)
    W = np.zeros((n_mel, len(fr)), np.float32)
    for i in range(n_mel):
        a, c, b = pts[i], pts[i + 1], pts[i + 2]
        W[i] = np.clip(np.minimum((mf - a) / (c - a), (b - mf) / (b - c)), 0, None)
    _S["mel"] = W
    return W


def fbank(x16):
    """80 bandes de Mel en log (façon Kaldi), moyenne retirée : [T, 80]."""
    x = np.asarray(x16, np.float64) * 32768.0
    L, H = 400, 160
    if len(x) < L: return None
    n = 1 + (len(x) - L) // H
    idx = np.arange(L)[None, :] + H * np.arange(n)[:, None]
    f = x[idx]
    f = f - f.mean(1, keepdims=True)
    f = np.concatenate([f[:, :1] * (1 - 0.97), f[:, 1:] - 0.97 * f[:, :-1]], axis=1)
    f = f * (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(L) / (L - 1))) ** 0.85          # fenêtre de Povey
    p = np.abs(np.fft.rfft(f, 512)) ** 2
    e = np.log(np.maximum(p @ _mel().T, 1.1920929e-07)).astype(np.float32)
    return e - e.mean(0, keepdims=True)


def empreinte(x16):
    """Empreinte (256 nombres, norme 1) d'un morceau de voix à 16 kHz, ou None."""
    s = _session()
    if s is None or len(x16) < 4000: return None
    F = fbank(x16)
    if F is None: return None
    e = s.run(None, {"feats": F[None]})[0][0]
    return e / (np.linalg.norm(e) + 1e-9)
