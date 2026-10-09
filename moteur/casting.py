"""Casting vocal automatique (exécuté une seule fois par le robot).
Source : Multilingual LibriSpeech, partie française (licence CC BY 4.0, lecteurs bénévoles LibriVox).
Le robot écoute objectivement une cinquantaine de lecteurs (hauteur de voix, qualité d'enregistrement, débit),
attribue un lecteur différent à chaque personnage, transforme légèrement le timbre pour en faire une voix
de personnage, et enregistre une référence de ~12 s par rôle dans voix/<role>.wav."""
import io, json, os, subprocess, sys, tempfile, wave
import numpy as np

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOSSIER = os.path.join(RACINE, "voix")
SR = 24000
DEPOT = "facebook/multilingual_librispeech"

# transformation propre à chaque rôle (hauteur, débit) : la voix devient celle du personnage
ROLES = {
    "presentateur": dict(genre="h", hauteur=0.98, tempo=1.0),
    "envoyee":      dict(genre="f", hauteur=1.0, tempo=1.04),
    "invite":       dict(genre="h", hauteur=0.95, tempo=0.98),
}

# ------------------------------------------------------------------ chargement des extraits
def charger_mls(max_par_lecteur=6):
    """Renvoie {speaker_id: [(audio float32 24 kHz, transcription), ...]} à partir des parties dev/test."""
    from huggingface_hub import HfApi, hf_hub_download
    import pyarrow.parquet as pq
    fichiers = [f for f in HfApi().list_repo_files(DEPOT, repo_type="dataset")
                if "french" in f.lower() and f.endswith(".parquet") and ("/dev" in f or "/test" in f)]
    if not fichiers: raise RuntimeError("Fichiers MLS français introuvables")
    lecteurs = {}
    for f in sorted(fichiers):
        chemin = hf_hub_download(DEPOT, f, repo_type="dataset")
        table = pq.read_table(chemin).to_pylist()
        for row in table:
            spk = str(row.get("speaker_id")); dur = float(row.get("audio_duration") or 0)
            if not (4 <= dur <= 16) or len(lecteurs.get(spk, [])) >= max_par_lecteur: continue
            audio = row["audio"]; data = audio.get("bytes") if isinstance(audio, dict) else None
            if not data: continue
            a = decoder(data)
            if a is not None and len(a) > SR * 3: lecteurs.setdefault(spk, []).append((a, row.get("transcript", "")))
        print(f"  {f} : {len(lecteurs)} lecteurs", flush=True)
    return lecteurs

def decoder(octets):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1"],
                       input=octets, capture_output=True)
    if r.returncode or not r.stdout: return None
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768

# ------------------------------------------------------------------ analyse objective
def f0_median(a):
    fr = []; n = 1024
    for i in range(0, len(a) - n, n):
        x = a[i:i + n]
        if np.abs(x).max() < 0.05: continue
        x = x - x.mean(); c = np.correlate(x, x, "full")[n - 1:]
        lo, hi = SR // 400, SR // 60; k = lo + int(np.argmax(c[lo:hi]))
        if c[k] > 0.45 * c[0]: fr.append(SR / k)
    return float(np.median(fr)) if len(fr) > 10 else 0.0

def qualite(a):
    """Rapport signal/bruit approximatif (dB) et proportion d'écrêtage."""
    h = SR // 50; rms = np.array([np.sqrt(np.mean(a[i:i + h] ** 2)) + 1e-6 for i in range(0, len(a) - h, h)])
    snr = 20 * np.log10(np.percentile(rms, 95) / np.percentile(rms, 10))
    clip = float(np.mean(np.abs(a) > 0.98))
    return float(snr), clip

def analyser(lecteurs):
    fiches = []
    for spk, extraits in lecteurs.items():
        if len(extraits) < 2: continue
        tout = np.concatenate([a for a, _ in extraits])
        f0 = f0_median(tout); snr, clip = qualite(tout)
        mots = sum(len(t.split()) for _, t in extraits); dur = len(tout) / SR
        if f0 <= 0 or clip > 0.001: continue
        genre = "h" if f0 < 155 else ("f" if f0 > 170 else "?")
        fiches.append(dict(speaker=spk, f0=f0, snr=snr, debit=mots / dur, genre=genre, n=len(extraits)))
    return fiches

def choisir(fiches):
    """Attribue un lecteur différent à chaque rôle, uniquement parmi les enregistrements propres."""
    bons = sorted([f for f in fiches if f["snr"] >= 22], key=lambda f: -f["snr"])
    if len(bons) < 8: bons = sorted(fiches, key=lambda f: -f["snr"])
    hommes = [f for f in bons if f["genre"] == "h"][:10]; femmes = [f for f in bons if f["genre"] == "f"][:10]
    if len(hommes) < 2 or len(femmes) < 1: raise RuntimeError("Pas assez de voix propres pour le casting")
    pris = set(); choix = {}
    def prendre(role, liste, cle):
        for f in sorted(liste, key=cle):
            if f["speaker"] not in pris:
                pris.add(f["speaker"]); choix[role] = f; return
    prendre("presentateur", hommes, lambda f: abs(f["debit"] - 2.6) - f["snr"] / 40)   # posée et très propre : voix de JT
    prendre("invite", hommes, lambda f: f["f0"])                                        # la plus grave : l'expert solennel
    prendre("envoyee", femmes, lambda f: -(f["debit"] + f["snr"] / 30))                 # vive et nette : reporter de terrain
    return choix

# ------------------------------------------------------------------ fabrication des références
def transformer(a, hauteur, tempo):
    with tempfile.TemporaryDirectory() as t:
        ecrire_wav(f"{t}/in.wav", a)
        for filtre in (f"rubberband=pitch={hauteur}:tempo={tempo}:formant=preserved",
                       f"asetrate={int(SR * hauteur)},aresample={SR},atempo={tempo / hauteur:.4f}"):
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{t}/in.wav", "-af",
                                filtre + ",highpass=f=70,loudnorm=I=-20:TP=-2", "-ar", str(SR), f"{t}/out.wav"], capture_output=True)
            if r.returncode == 0: return lire_wav(f"{t}/out.wav")
    return a

def ecrire_wav(p, a, sr=SR):
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
def lire_wav(p):
    with wave.open(p) as w: return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768

def reference(extraits, duree=12.0):
    morceaux, total = [], 0.0
    for a, _ in sorted(extraits, key=lambda e: -len(e[0])):
        morceaux += [a, np.zeros(int(0.3 * SR), np.float32)]; total += len(a) / SR
        if total >= duree: break
    return np.concatenate(morceaux)[: int(duree * SR * 1.3)]

def casting(lecteurs=None, forcer=False):
    os.makedirs(DOSSIER, exist_ok=True)
    fiche = os.path.join(DOSSIER, "casting.json")
    if os.path.exists(fiche) and not forcer and all(os.path.exists(os.path.join(DOSSIER, f"{r}.wav")) for r in ROLES):
        print("Casting déjà fait."); return json.load(open(fiche))
    print("Casting vocal : téléchargement des extraits MLS français…", flush=True)
    lecteurs = lecteurs or charger_mls()
    fiches = analyser(lecteurs); print(f"{len(fiches)} lecteurs analysés", flush=True)
    choix = choisir(fiches)
    resultat = {"source": "Multilingual LibriSpeech (français), CC BY 4.0 — lecteurs bénévoles LibriVox",
                "credit": "Voix : Multilingual LibriSpeech (CC BY 4.0), transformées", "roles": {}}
    for role, f in choix.items():
        r = ROLES[role]
        a = transformer(reference(lecteurs[f["speaker"]]), r["hauteur"], r["tempo"])
        ecrire_wav(os.path.join(DOSSIER, f"{role}.wav"), a)
        resultat["roles"][role] = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in f.items()}
        print(f"  {role:18s} -> lecteur {f['speaker']} (f0 {f['f0']:.0f} Hz, SNR {f['snr']:.0f} dB)")
    json.dump(resultat, open(fiche, "w"), ensure_ascii=False, indent=1)
    return resultat

if __name__ == "__main__":
    casting(forcer="--forcer" in sys.argv)
