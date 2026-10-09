"""Voix plus naturelles à partir de Piper (gratuit) :
- synthèse phrase par phrase avec une intonation qui varie selon la ponctuation (!, ?, …) ;
- réglages d'expressivité de Piper (noise_scale / noise_w) ;
- grave/aigu sans effet « chipmunk » : on décale un peu le timbre et surtout la hauteur (rubberband, formants préservés) ;
- traitement « studio » : égaliseur, compresseur, légère acoustique de plateau ;
- pauses naturelles entre les phrases."""
import os, re, subprocess, wave, hashlib
import numpy as np

SR = 22050
RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TTS = os.environ.get("TTS_DIR", os.path.join(RACINE, "outils"))
PIPER = os.environ.get("PIPER_BIN", os.path.join(TTS, "piper", "piper"))
MODELE = os.environ.get("VOIX_PRINCIPALE", os.path.join(TTS, "voix", "fr-siwis-medium.onnx"))

def _lire(chemin):
    with wave.open(chemin) as w:
        sr = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a, sr
def _ecrire(chemin, a, sr=SR):
    with wave.open(chemin, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())

def decouper(texte):
    """Phrases + pause qui suit, selon la ponctuation."""
    morceaux = re.findall(r"[^.!?…]+(?:\.\.\.|…|[.!?]+)?", texte)
    out = []
    for m in morceaux:
        m = m.strip()
        if not m: continue
        fin = m[-1]
        pause = {"!": 0.22, "?": 0.30, "…": 0.45, ".": 0.28}.get(fin, 0.2)
        if m.endswith("..."): pause = 0.45
        out.append((m.replace("…", "..."), fin, pause))
    return out

def phrase(texte, fin, v, tmp, graine):
    r = np.random.default_rng(graine)
    lent = v.get("vitesse", 1.0) * (1.06 if fin == "?" else 0.95 if fin == "!" else 1.0) * r.uniform(0.97, 1.03)
    expr = v.get("expr", 0.7)
    brut = f"{tmp}.brut.wav"
    subprocess.run([PIPER, "-m", MODELE, "-f", brut, "--length_scale", f"{lent:.3f}", "--noise_scale", f"{0.55 + 0.35 * expr:.3f}",
                    "--noise_w", f"{0.7 + 0.35 * expr:.3f}", "--sentence_silence", "0"], input=texte.encode(), capture_output=True, check=True)
    _, sr = _lire(brut)
    formant = v.get("formant", 1.0)
    var = {"!": 1.05, "?": 1.03}.get(fin, 1.0) * r.uniform(0.975, 1.025)
    hauteur = v.get("pitch", 1.0) / formant * var
    filtres = [f"asetrate={int(sr * formant)}", f"aresample={SR}", f"atempo={1 / formant:.5f}"]
    if abs(hauteur - 1) > 0.005:
        filtres.append(f"rubberband=pitch={hauteur:.4f}:formant=preserved:transients=smooth:pitchq=quality")
    filtres += ["silenceremove=start_periods=1:start_threshold=-45dB", "areverse",
                "silenceremove=start_periods=1:start_threshold=-45dB", "areverse"]
    sortie = f"{tmp}.ph.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", brut, "-af", ",".join(filtres), "-ac", "1", "-ar", str(SR), sortie], check=True)
    a, _ = _lire(sortie)
    n = int(0.012 * SR)                                                     # micro-fondus anti-clic
    if len(a) > 2 * n: a[:n] *= np.linspace(0, 1, n); a[-n:] *= np.linspace(1, 0, n)
    return a

def studio(a, tmp, grave=False):
    _ecrire(f"{tmp}.sec.wav", a)
    chaine = ["highpass=f=75", f"equalizer=f={170 if grave else 220}:t=q:w=1:g=2.5", "equalizer=f=3200:t=q:w=1.2:g=2.5",
              "equalizer=f=280:t=q:w=1.2:g=-2.5", "equalizer=f=7000:t=q:w=1:g=-1", "deesser=i=0.3",
              "acompressor=threshold=-20dB:ratio=3:attack=5:release=90:makeup=2", "aecho=0.9:0.4:15:0.025"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmp}.sec.wav", "-af", ",".join(chaine), f"{tmp}.studio.wav"], check=True)
    b, _ = _lire(f"{tmp}.studio.wav")
    rms = np.sqrt(np.mean(b[np.abs(b) > 0.01] ** 2)) if (np.abs(b) > 0.01).any() else 0.1
    return np.clip(b * (0.12 / max(rms, 1e-4)), -0.98, 0.98)

def parler(texte, v, tmp):
    """Renvoie l'audio (float32, 22050 Hz) d'une réplique complète."""
    parts = []
    for i, (t, fin, pause) in enumerate(decouper(texte)):
        g = int(hashlib.md5(t.encode()).hexdigest()[:8], 16)
        parts.append(phrase(t, fin, v, f"{tmp}_{i}", g))
        parts.append(np.zeros(int(pause * SR), np.float32))
    a = np.concatenate(parts[:-1]) if parts else np.zeros(SR // 2, np.float32)
    return studio(a, tmp, grave=v.get("pitch", 1) < 0.9)

if __name__ == "__main__":
    import sys
    v = dict(pitch=float(sys.argv[2]), formant=float(sys.argv[3]), vitesse=1.0, expr=0.8)
    _ecrire(sys.argv[4], parler(sys.argv[1], v, "/tmp/voixtest"))
