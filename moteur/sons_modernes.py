"""Bruitages modernes du moteur cartoon, fabriqués par synthèse sonore (aucun échantillon externe, donc libres de droits) :
whoosh de transition, impact grave (« boom ») de chute, pop de titre, montée de tension avant la dernière réplique, swipe.
Tous renvoient un signal stéréo float32 à 44 100 Hz."""
import os
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 44100

def _t(d): return np.arange(int(d * SR)) / SR

def _bande(x, f0, f1, ordre=2):
    sos = butter(ordre, [max(20, f0), min(SR / 2 - 100, f1)], "bandpass", fs=SR, output="sos"); return sosfilt(sos, x)

def _passe_bas(x, f, ordre=4):
    sos = butter(ordre, min(f, SR / 2 - 100), "lowpass", fs=SR, output="sos"); return sosfilt(sos, x)

def _reverb(x, duree=0.9, mix=0.25, graine=0):
    rng = np.random.default_rng(graine); n = int(duree * SR)
    ir = rng.normal(0, 1, n) * np.exp(-np.linspace(0, 7, n)); ir = _passe_bas(ir, 6000); ir /= np.abs(ir).sum() ** 0.5 * 8
    return x + mix * fftconvolve(x, ir)[:len(x)]

def _stereo(m, pan=None):
    if pan is None: return np.stack([m, m], 1).astype(np.float32)
    g = (np.clip(pan, -1, 1) + 1) / 2
    return np.stack([m * np.sqrt(1 - g), m * np.sqrt(g)], 1).astype(np.float32) * 1.3

def _norm(x, crete=0.9):
    return x / (np.abs(x).max() + 1e-9) * crete

def whoosh(duree=0.55, graine=1):
    """Souffle filtré qui balaie les fréquences et traverse de gauche à droite."""
    rng = np.random.default_rng(graine); t = _t(duree); u = t / duree
    bruit = rng.normal(0, 1, len(t))
    env = np.sin(np.pi * u) ** 1.6 * np.exp(-1.2 * u)
    sortie = np.zeros_like(bruit)
    for k, (f0, f1) in enumerate(((250, 900), (600, 2200), (1500, 5000))):        # trois bandes qui s'ouvrent au centre
        poids = np.exp(-((u - (0.35 + 0.12 * k)) / 0.22) ** 2)
        sortie += _bande(bruit, f0, f1) * poids * (1.0, 0.8, 0.45)[k]
    sortie = _reverb(sortie * env, 0.6, 0.18, graine)
    return _stereo(_norm(sortie, 0.8), pan=np.linspace(-0.8, 0.8, len(t)))

def swipe(duree=0.22, graine=2):
    rng = np.random.default_rng(graine); t = _t(duree); u = t / duree
    x = _bande(rng.normal(0, 1, len(t)), 2000, 9000) * np.sin(np.pi * u) ** 2
    return _stereo(_norm(x, 0.6), pan=np.linspace(0.7, -0.7, len(t)))

def boom(duree=1.6, force=1.0, graine=3):
    """Impact grave moderne : attaque claquée + sub qui plonge (120 -> 38 Hz) + saturation douce + queue de réverbération."""
    rng = np.random.default_rng(graine); t = _t(duree)
    f = 38 + 82 * np.exp(-t * 9); phase = 2 * np.pi * np.cumsum(f) / SR
    sub = np.sin(phase) * np.exp(-t * 2.6)
    corps = np.sin(2 * phase) * 0.35 * np.exp(-t * 5)
    claque = _bande(rng.normal(0, 1, len(t)), 800, 7000) * np.exp(-t * 55) * 0.9
    thump = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 18) * 0.8
    x = np.tanh((sub + corps + thump) * 2.2 * force) * 0.85 + claque
    x = _reverb(x, 1.2, 0.3, graine)
    return _stereo(_norm(x, 0.95))

def pop(graine=4):
    """Petit « pop » net quand un titre apparaît."""
    t = _t(0.12); f = 500 + 1400 * (1 - np.exp(-t * 60))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 45)
    x += _bande(np.random.default_rng(graine).normal(0, 1, len(t)), 3000, 9000) * np.exp(-t * 200) * 0.3
    return _stereo(_norm(x, 0.55))

def montee(duree=1.3, graine=5):
    """Montée de tension avant la chute finale : souffle qui s'ouvre + note qui monte, coupée net."""
    rng = np.random.default_rng(graine); t = _t(duree); u = t / duree
    bruit = rng.normal(0, 1, len(t)); x = np.zeros_like(bruit); seg = len(t) // 8
    for k in range(8):                                                     # filtre qui s'ouvre progressivement
        a, b = k * seg, (k + 1) * seg if k < 7 else len(t)
        x[a:b] = _bande(bruit, 300 + 500 * k, 1200 + 1200 * k)[a:b]
    f = 180 * 2 ** (2.2 * u); ton = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.35 + np.sin(4 * np.pi * np.cumsum(f) / SR) * 0.12
    x = (x * 0.6 + ton) * u ** 2.2
    x[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
    return _stereo(_norm(x, 0.6))

def transition(graine=6):
    """Changement de scène : whoosh + petit impact grave au moment de la coupe."""
    w = whoosh(0.6, graine); b = boom(0.9, 0.55, graine) * 0.55
    out = np.zeros((max(len(w), int(0.3 * SR) + len(b)), 2), np.float32)
    out[:len(w)] += w; s0 = int(0.3 * SR); out[s0:s0 + len(b)] += b
    return out / max(1, np.abs(out).max() / 0.95)

# ------------------------------------------------------------------ bruitages « tendance » (catalogue : moteur/bruitages.py)
def _env(t, attaque=0.005, chute=8.0):
    return np.minimum(1, t / max(attaque, 1e-4)) * np.exp(-t * chute)

def _scie(f, t):                                                           # dent de scie douce (cuivres, violon)
    ph = np.cumsum(np.broadcast_to(f, t.shape)) / SR
    return sum(np.sin(2 * np.pi * k * ph) / k for k in range(1, 9))

def vine_boom(graine=11):
    b = boom(1.1, 1.25, graine)[:, 0]; t = _t(len(b) / SR)
    anneau = np.sin(2 * np.pi * 410 * t) * np.exp(-t * 9) * 0.12
    return _stereo(_norm(b + anneau, 0.95))

def dun_dun(graine=12):
    notes = [(0.0, 0.32, 146.8), (0.42, 0.32, 138.6), (0.84, 1.3, 110.0)]       # ré, do#, la : « dun dun duuun »
    out = np.zeros(int(2.3 * SR))
    for d, l, f in notes:
        t = _t(l); x = _passe_bas(_scie(f * (1 + 0.004 * np.sin(2 * np.pi * 5 * t)), t), 1800) * _env(t, 0.02, 1.2 / l)
        a = int(d * SR); out[a:a + len(x)] += x
    return _stereo(_norm(_reverb(out, 1.0, 0.3, graine), 0.8))

def klaxon_clown(graine=13):
    out = np.zeros(int(0.9 * SR))
    for d in (0.0, 0.38):
        t = _t(0.3); f = 330 * (1 + 0.03 * np.sin(2 * np.pi * 9 * t))
        x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * _env(t, 0.01, 4)
        x = _bande(x, 400, 2600); a = int(d * SR); out[a:a + len(x)] += x
    return _stereo(_norm(out, 0.7))

def sifflet_chute(graine=14):
    t = _t(0.95); u = t / 0.95; f = 1900 * (300 / 1900) ** u * (1 + 0.02 * np.sin(2 * np.pi * 7 * t))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.03) * (1 - u) ** 0.4
    x += _bande(np.random.default_rng(graine).normal(0, 1, len(t)), 1500, 6000) * 0.05
    return _stereo(_norm(x, 0.6))

def boing(graine=15):
    t = _t(0.8); f = 170 * (1 + 0.35 * np.sin(2 * np.pi * 14 * t) * np.exp(-t * 4)) * (1 + 0.6 * np.exp(-t * 25))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(t, 0.003, 4.5) + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR) * _env(t, 0.003, 7)
    return _stereo(_norm(x, 0.7))

def violon_triste(graine=16):
    out = np.zeros(int(2.7 * SR))
    for k, f in enumerate((440.0, 392.0, 349.2, 329.6)):                    # la, sol, fa, mi : petit violon qui descend
        l = 0.55 if k < 3 else 1.0; t = _t(l)
        x = _passe_bas(_scie(f * (1 + 0.012 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t / 0.2)), t), 4200)
        x *= np.minimum(1, t / 0.08) * np.minimum(1, (l - t) / 0.08)
        a = int(k * 0.55 * SR); out[a:a + len(x)] += x
    return _stereo(_norm(_reverb(out, 1.2, 0.35, graine), 0.55))

def criquets(graine=17):
    rng = np.random.default_rng(graine); out = np.zeros(int(2.4 * SR))
    for d in np.arange(0.05, 2.2, 0.55) + rng.uniform(-0.05, 0.05, 4):
        for k in range(3):                                                 # « cri-cri-cri »
            t = _t(0.035); x = np.sin(2 * np.pi * 4600 * t) * np.sin(np.pi * t / 0.035)
            a = int((d + k * 0.06) * SR); out[a:a + len(x)] += x
    return _stereo(_norm(_reverb(out, 1.5, 0.4, graine), 0.4), pan=0.3)

def os_craque(graine=18):
    rng = np.random.default_rng(graine); out = np.zeros(int(0.5 * SR))
    for d in (0.0, 0.05, 0.085, 0.16):
        t = _t(0.03); x = _bande(rng.normal(0, 1, len(t)), 900, 5000) * np.exp(-t * 160)
        a = int(d * SR); out[a:a + len(x)] += x
    return _stereo(_norm(out, 0.8))

def scie_wobble(graine=19):
    t = _t(1.2); f = 620 * (1 + 0.06 * np.sin(2 * np.pi * 6 * t)) * (1 - 0.25 * t / 1.2)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.1) * np.minimum(1, (1.2 - t) / 0.2)
    return _stereo(_norm(_reverb(x, 0.8, 0.25, graine), 0.5))

def dents(graine=20):
    rng = np.random.default_rng(graine); out = np.zeros(int(1.0 * SR))
    for d in np.arange(0, 0.95, 1 / 17):
        t = _t(0.012); x = _bande(rng.normal(0, 1, len(t)), 1800, 7000) * np.exp(-t * 400)
        a = int(d * SR); out[a:a + len(x)] += x * rng.uniform(0.6, 1)
    return _stereo(_norm(out, 0.6))

def bouilloire(graine=21):
    t = _t(1.6); u = t / 1.6; f = 1300 * 2 ** u
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * u ** 1.5 + _bande(np.random.default_rng(graine).normal(0, 1, len(t)), 2000, 6000) * 0.15 * u
    return _stereo(_norm(x, 0.45))

def caisse(graine=22):
    t = _t(1.0); clic = _bande(np.random.default_rng(graine).normal(0, 1, len(t)), 2000, 8000) * np.exp(-t * 90)
    cloche = np.zeros(len(t)); a = int(0.08 * SR); tt = t[:len(t) - a]
    cloche[a:] = (np.sin(2 * np.pi * 2637 * tt) + 0.6 * np.sin(2 * np.pi * 3951 * tt) + 0.3 * np.sin(2 * np.pi * 5274 * tt)) * np.exp(-tt * 5)
    return _stereo(_norm(clic * 0.7 + cloche * 0.6, 0.6))

def flash(graine=23):
    rng = np.random.default_rng(graine); t = _t(0.7); out = np.zeros(len(t))
    for d in (0.0, 0.06):
        tt = _t(0.02); x = _bande(rng.normal(0, 1, len(tt)), 1500, 9000) * np.exp(-tt * 250); a = int(d * SR); out[a:a + len(x)] += x
    out += np.sin(2 * np.pi * np.cumsum(3000 + 4000 * t / 0.7) / SR) * 0.08 * np.minimum(1, t / 0.1) * (t > 0.1)
    return _stereo(_norm(out, 0.6))

def clavier(graine=24):
    rng = np.random.default_rng(graine); out = np.zeros(int(1.4 * SR)); d = 0.0
    while d < 1.3:
        t = _t(0.025); x = _bande(rng.normal(0, 1, len(t)), 1200, 6000) * np.exp(-t * 300) * rng.uniform(0.5, 1)
        a = int(d * SR); out[a:a + len(x)] += x; d += rng.uniform(0.06, 0.13)
    return _stereo(_norm(out, 0.5))

def glitch(graine=25):
    rng = np.random.default_rng(graine); out = []
    for _ in range(9):
        l = int(rng.uniform(0.02, 0.07) * SR); f = rng.choice([220, 440, 880, 1760])
        x = np.sign(np.sin(2 * np.pi * f * np.arange(l) / SR)) * 0.5 + rng.normal(0, 0.3, l)
        out.append(x * (rng.random() > 0.2))
    return _stereo(_norm(_passe_bas(np.concatenate(out), 7000), 0.5))

def bulle(graine=26):
    t = _t(0.18); f = 600 + 2200 * (t / 0.18) ** 0.6
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 28)
    return _stereo(_norm(x, 0.55))

BANQUE = {"whoosh": whoosh, "swipe": swipe, "boom": boom, "pop": pop, "montee": montee, "transition": transition,
          "boom_leger": lambda: boom(0.9, 0.6), "boom_fin": boom,
          "vine_boom": vine_boom, "dun_dun": dun_dun, "klaxon_clown": klaxon_clown, "sifflet_chute": sifflet_chute, "boing": boing,
          "violon_triste": violon_triste, "criquets": criquets, "os_craque": os_craque, "scie_wobble": scie_wobble, "dents": dents,
          "bouilloire": bouilloire, "caisse": caisse, "flash": flash, "clavier": clavier, "glitch": glitch, "bulle": bulle}
ELEVEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sons_eleven")
_cache = {}

def _lire(chemin):
    """Décode un mp3 (bruitage ElevenLabs) en stéréo float32 à 44 100 Hz."""
    import subprocess
    brut = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", chemin, "-f", "s16le", "-ac", "2", "-ar", str(SR), "-"],
                          capture_output=True, check=True).stdout
    return (np.frombuffer(brut, np.int16).astype(np.float32) / 32768).reshape(-1, 2)

def son(nom):
    """Bruitage ElevenLabs s'il a été fabriqué (sons_eleven/), sinon version synthétisée."""
    if nom not in _cache:
        p = os.path.join(ELEVEN, nom + ".mp3")
        try: _cache[nom] = _lire(p) if os.path.exists(p) else None
        except Exception: _cache[nom] = None
        if _cache[nom] is None: _cache[nom] = BANQUE[nom]() if nom in BANQUE else np.zeros((1, 2), np.float32)
    return _cache[nom]

# ------------------------------------------------------------------ son « cinéma » : ambiance du lieu, pas, musique de fond
def _bruit(n, rng): return rng.normal(0, 1, n)

def meteo(duree, orage=False, graine=7):
    """Pluie (bruissement doux) et, s'il y a de l'orage, grondement de tonnerre juste après chaque éclair de l'image
    (decor_anime : éclair toutes les 6,5 s, le premier à 5,2 s). Stéréo 44,1 kHz, très bas sous les voix."""
    n = int(duree * SR); rng = np.random.default_rng(graine); t = np.arange(n) / SR
    pluie = _bande(_bruit(n, rng), 1500, 7000) * 0.035 + _passe_bas(_bruit(n, rng), 600) * 0.03
    if orage:
        for c in np.arange(5.2, duree, 6.5):
            env = np.where(t >= c + 0.25, np.exp(-(t - c - 0.25) / 1.4), 0.0) * (1 - np.exp(-np.maximum(0, t - c - 0.25) * 20))
            pluie = pluie + _passe_bas(_bruit(n, rng), 120) * env * 0.5
    return np.stack([pluie, pluie * 0.96], 1).astype(np.float32)


def ambiance(lieu, duree, graine=7):
    """Ambiance de fond du lieu (très bas sous les voix) : celle d'ElevenLabs si elle a été fabriquée (sons_eleven/ambiances/),
    sinon une ambiance de synthèse (salle, rue, bar, bureau, cuisine, caverne…). Stéréo 44,1 kHz."""
    n = int(duree * SR)
    p = os.path.join(ELEVEN, "ambiances", f"{lieu}.mp3")
    if os.path.exists(p):
        try:
            a = _lire(p)
            if len(a) > SR:
                a = np.tile(a, (n // len(a) + 1, 1))[:n]
                return (a / (np.abs(a).max() + 1e-9) * 0.12).astype(np.float32)
        except Exception: pass
    rng = np.random.default_rng(graine); t = np.arange(n) / SR
    fond = _passe_bas(_bruit(n, rng), 400) * 0.05                          # « room tone » : le souffle de la pièce
    if lieu in ("bar", "restaurant", "palais"):                            # murmure de clients, tintements
        mur = _bande(_bruit(n, rng), 250, 2200) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.23 * t + 1) * np.sin(2 * np.pi * 0.71 * t)) * 0.08
        fond = fond + mur
        for _ in range(int(duree / 3)):
            k = int(rng.uniform(0, max(1, n - SR // 2))); d = np.arange(SR // 3) / SR
            fond[k:k + len(d)] += 0.05 * np.sin(2 * np.pi * rng.uniform(2200, 3400) * d) * np.exp(-d * 18)
    elif lieu == "rue":                                                    # circulation, une voiture qui passe
        fond = fond + _passe_bas(_bruit(n, rng), 180) * 0.25
        for _ in range(max(1, int(duree / 6))):
            c = rng.uniform(0, duree); env = np.exp(-((t - c) / 1.2) ** 2)
            fond += _bande(_bruit(n, rng), 80, 900) * env * 0.12
    elif lieu in ("bureau", "administration", "classe"):                   # climatisation, clics de clavier
        fond = fond + 0.012 * np.sin(2 * np.pi * 60 * t) + _bande(_bruit(n, rng), 150, 500) * 0.04
        for _ in range(int(duree * 1.5)):
            k = int(rng.uniform(0, max(1, n - 800))); fond[k:k + 400] += _bande(rng.normal(0, 1, 400), 2000, 6000) * np.exp(-np.arange(400) / 60) * 0.05
    elif lieu == "cuisine":
        fond = fond + 0.01 * np.sin(2 * np.pi * 50 * t) + _bande(_bruit(n, rng), 200, 800) * 0.03
    elif lieu == "caverne":                                                # vent et crépitement du feu
        fond = fond + _passe_bas(_bruit(n, rng), 300) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.1 * t)) * 0.15
        for _ in range(int(duree * 6)):
            k = int(rng.uniform(0, max(1, n - 300))); fond[k:k + 150] += rng.normal(0, 1, 150) * np.exp(-np.arange(150) / 25) * 0.08
    elif lieu == "salle_sport":
        fond = fond + _bande(_bruit(n, rng), 300, 1500) * 0.04
    return _stereo(_reverb(fond, 0.6, 0.15, graine) * 0.6)

def pas(n=5, intervalle=0.17, graine=8):
    """Bruits de pas (quelqu'un entre dans le champ)."""
    rng = np.random.default_rng(graine); x = np.zeros(int((n * intervalle + 0.3) * SR))
    for k in range(n):
        s0 = int(k * intervalle * SR); d = np.arange(int(0.09 * SR)) / SR
        x[s0:s0 + len(d)] += (_passe_bas(rng.normal(0, 1, len(d)), 900) * 0.6 + np.sin(2 * np.pi * 85 * d) * 0.5) * np.exp(-d * 45) * rng.uniform(0.7, 1.0)
    return _stereo(_norm(x, 0.5))

ACCORDS = {"joie": [(0, 4, 7), (5, 9, 12), (7, 11, 14), (0, 4, 7)], "triste": [(0, 3, 7), (-4, 0, 3), (-2, 2, 5), (0, 3, 7)],
           "tension": [(0, 3, 6), (1, 4, 7), (0, 3, 6), (-1, 2, 5)], "neutre": [(0, 4, 7), (-3, 0, 4), (5, 9, 12), (7, 11, 14)]}

def _bibliotheque(duree, humeur, graine):
    """Boucle de la bibliothèque générée par IA (sons/musique/<humeur>_<n>.wav, ACE-Step Apache 2.0), ou None."""
    import glob, wave
    racine = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sons", "musique")
    fichiers = sorted(glob.glob(os.path.join(racine, f"{humeur}_*.wav"))) or sorted(glob.glob(os.path.join(racine, "neutre_*.wav")))
    if not fichiers or os.environ.get("MUSIQUE_IA", "1") == "0": return None
    try:
        import subprocess, tempfile
        tmp = tempfile.mktemp(suffix=".wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", fichiers[graine % len(fichiers)], "-ac", "1", "-ar", str(SR), tmp], check=True)
        with wave.open(tmp) as w: x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        n = int(duree * SR)
        if len(x) < SR: return None
        while len(x) < n: x = np.concatenate([x, x])                       # bouclée si la vidéo est plus longue
        x = x[:n].copy(); f = min(n // 4, int(1.5 * SR)); x[:f] *= np.linspace(0, 1, f); x[-f:] *= np.linspace(1, 0, f)
        return _stereo(_norm(x, 0.35))
    except Exception:
        return None


def musique(duree, humeur="neutre", graine=9):
    """Musique d'ambiance très discrète qui suit l'humeur du sketch : boucle de la bibliothèque générée par IA (S2) si elle existe,
    sinon nappe synthétisée (accords doux, libre de droits)."""
    m = _bibliotheque(duree, humeur, graine)
    if m is not None: return m
    acc = ACCORDS.get(humeur, ACCORDS["neutre"]); n = int(duree * SR); t = np.arange(n) / SR; x = np.zeros(n)
    base = {"joie": 220.0, "triste": 196.0, "tension": 146.8}.get(humeur, 207.7); d_acc = 2.4 if humeur != "tension" else 1.2
    for k in range(int(duree / d_acc) + 1):
        s0 = int(k * d_acc * SR); e = min(n, s0 + int((d_acc + 0.6) * SR))
        if s0 >= n: break
        tt = t[s0:e] - t[s0]; env = np.minimum(1, tt / 0.5) * np.exp(-np.maximum(0, tt - d_acc) * 4)
        for i in acc[k % len(acc)]:
            f = base * 2 ** (i / 12); x[s0:e] += (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt)) * env / 3
    if humeur == "tension": x *= 0.7 + 0.3 * np.sin(2 * np.pi * 2.0 * t)
    return _stereo(_norm(_reverb(_passe_bas(x, 2500), 1.4, 0.35, graine), 0.35))
