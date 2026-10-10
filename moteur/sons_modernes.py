"""Bruitages modernes du moteur cartoon, fabriqués par synthèse sonore (aucun échantillon externe, donc libres de droits) :
whoosh de transition, impact grave (« boom ») de chute, pop de titre, montée de tension avant la dernière réplique, swipe.
Tous renvoient un signal stéréo float32 à 44 100 Hz."""
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

BANQUE = {"whoosh": whoosh, "swipe": swipe, "boom": boom, "pop": pop, "montee": montee, "transition": transition}
_cache = {}
def son(nom):
    if nom not in _cache: _cache[nom] = BANQUE[nom]()
    return _cache[nom]
