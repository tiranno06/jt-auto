"""Rhubarb Lip Sync (Daniel Wolf, licence MIT ; choix de l'auteur du 11 novembre 2026, idée 8) : l'outil fait pour les dessins
animés. Il écoute la voix et donne, au centième de seconde, la forme de bouche à dessiner (formes de Preston Blair : A fermée
M/B/P, B entrouverte, C ouverte « è », D grande ouverte « a », E arrondie « o », F en avant « ou », G dents sur la lèvre « f/v »,
H langue « l », X repos). Il ne lit pas le texte (reconnaissance « phonetic », valable en français) : il suit ce que la voix fait
vraiment, même quand le dessin animé parle vite. Ses formes remplacent celles devinées d'après le texte (moteur/levres.py) pour
les sons TikTok ; absent ou en échec -> les formes du texte, comme avant. RHUBARB=0 pour couper.
Programme téléchargé par emission.yml dans outils/rhubarb (cache du workflow)."""
import glob, json, os, subprocess, tempfile, wave
import numpy as np

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outils", "rhubarb")
FORMES = {"A": "M", "B": "T", "C": "E", "D": "A", "E": "O", "F": "U", "G": "F", "H": "T", "X": None}   # -> formes de levres.py


def programme():
    for p in [os.path.join(DOSSIER, "rhubarb")] + glob.glob(os.path.join(DOSSIER, "*", "rhubarb")):
        if os.path.isfile(p) and os.access(p, os.X_OK): return p
    return None


def analyser(sig, sr, delai=300):
    """[[début, fin, forme levres]] sur tout le son (forme None = bouche au repos), ou None."""
    if os.environ.get("RHUBARB", "1") == "0" or sig is None or len(sig) < sr * 0.5: return None
    exe = programme()
    if not exe: return None
    from scipy.signal import resample_poly
    x = resample_poly(np.asarray(sig, np.float64), 16000, sr) if sr != 16000 else np.asarray(sig, np.float64)
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    try:
        with wave.open(f, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes((np.clip(x / max(1e-6, np.abs(x).max()) * 0.9, -1, 1) * 32767).astype(np.int16).tobytes())
        r = subprocess.run([exe, "-r", "phonetic", "-f", "json", "--quiet", "--extendedShapes", "GHX", f],
                           capture_output=True, text=True, timeout=delai)
        if r.returncode: print(f"  Rhubarb en échec ({r.stderr[:120]})", flush=True); return None
        return cues(json.loads(r.stdout))
    except Exception as e:
        print(f"  Rhubarb indisponible ({str(e)[:100]})", flush=True); return None
    finally:
        try: os.unlink(f)
        except OSError: pass


def cues(d):
    """Sortie JSON de Rhubarb -> [[début, fin, forme]]."""
    return [[round(float(c["start"]), 3), round(float(c["end"]), 3), FORMES.get(str(c.get("value")), None)] for c in (d.get("mouthCues") or [])]


def chronologie(rh, deb, fin):
    """Formes de la réplique [deb, fin] au format de levres.chronologie [(début, fin, forme)] (repos retiré), ou None si Rhubarb
    n'a presque rien vu bouger (on garde alors les formes du texte)."""
    if not rh: return None
    seg = [(max(a, deb), min(b, fin), v) for a, b, v in rh if b > deb and a < fin and v]
    parle = sum(b - a for a, b, _ in seg)
    return seg if seg and parle >= 0.3 * max(0.1, fin - deb) else None
