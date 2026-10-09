"""Fabrique la bibliothèque de sons du robot (dossier sons/) à partir d'échantillons d'orchestre réels
VSCO 2 Community Edition (Versilian Studios, licence CC0, https://github.com/sgossner/VSCO-2-CE).
Usage : python outils_sons/fabriquer_sons.py <dossier VSCO-2-CE> <dossier de sortie>
Résultat (44,1 kHz stéréo) : intro.wav (générique 5 s), rimshot, xylo_descente, trombone_triste, dun_dun, woosh, reconstitution, nappe."""
import glob, os, re, subprocess, sys, wave
import numpy as np
from scipy.signal import resample_poly, fftconvolve, butter, sosfilt

SR = 44100
V = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/sgossner/vsco-2-ce"
OUT = sys.argv[2] if len(sys.argv) > 2 else "sons"
NOTES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}

def lire(f):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", f, "-ac", "2", "-ar", str(SR), "-f", "f32le", "pipe:1"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).reshape(-1, 2).copy()

def midi(nom):
    m = re.search(r"_([A-G]#?)(\d)_", os.path.splitext(nom)[0] + "_"); return 12 * (int(m.group(2)) + 1) + NOTES[m.group(1)] if m else None

def banque(motif):
    return [(midi(os.path.basename(f)), f) for f in glob.glob(os.path.join(V, motif)) if midi(os.path.basename(f)) is not None]

def note(bq, cible, duree=None, vel="v3"):
    """Échantillon le plus proche de la note voulue, transposé (rééchantillonnage) si besoin."""
    cands = [b for b in bq if vel in b[1]] or bq
    m, f = min(cands, key=lambda b: (abs(b[0] - cible), b[0] < cible))
    a = lire(f); d = cible - m
    if d:
        r = 2 ** (-d / 12); p, q = int(round(r * 1000)), 1000
        a = np.stack([resample_poly(a[:, c], p, q) for c in range(2)], 1)
    a = a[np.argmax(np.abs(a).max(1) > 0.003):]                                  # coupe le silence de début
    if duree:
        n = int(duree * SR); a = a[:n].copy(); r = min(len(a), int(0.08 * SR)); a[-r:] *= np.linspace(1, 0, r)[:, None]
    return a

def poser(mix, a, t, g=1.0):
    s = int(t * SR); e = min(len(mix), s + len(a)); mix[s:e] += a[:e - s] * g

def salle(a, duree=1.8, mix=0.22):
    t = np.arange(int(duree * SR)) / SR; rng = np.random.default_rng(1)
    ir = np.stack([rng.normal(0, 1, len(t)) * np.exp(-t * 3.2) for _ in range(2)], 1); ir[:int(0.02 * SR)] = 0; ir /= np.sqrt((ir ** 2).sum(0))
    wet = np.stack([fftconvolve(a[:, c], ir[:, c])[:len(a)] for c in range(2)], 1)
    return a + wet * mix * np.sqrt((a ** 2).sum() / max((wet ** 2).sum(), 1e-9))

def normal(a, crete=0.89):
    return a * (crete / max(np.abs(a).max(), 1e-6))

def ecrire(nom, a):
    a = np.clip(a, -1, 1); os.makedirs(OUT, exist_ok=True)
    with wave.open(os.path.join(OUT, nom + ".wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((a * 32767).astype(np.int16).tobytes())
    print(f"{nom}: {len(a) / SR:.2f} s")

def un(motif): return sorted(glob.glob(os.path.join(V, motif)))[0]

TPT_S, TPT_ST = banque("Brass/Trumpet/sus/*.wav"), banque("Brass/Trumpet/stac/*.wav")
TBN_S, TBN_ST = banque("Brass/Tenor Trombone/sus/*.wav"), banque("Brass/Tenor Trombone/stac/*.wav")
COR = banque("Brass/F Horn/sus/*.wav")
XYLO = banque("Percussion/Xylo/*.wav"); GLOCK = banque("Percussion/Glock/*.wav")

def tuba_synth(f, duree):
    t = np.arange(int(duree * SR)) / SR; s = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.6 for k in range(1, 7))
    env = np.minimum(1, t / 0.02) * np.exp(-t * 0.9); return np.stack([s * env] * 2, 1) * 0.25

# ------------------------------------------------------------------ générique 5 s (ré majeur)
def intro():
    mix = np.zeros((int(5.3 * SR), 2))
    roll = lire(un("Percussion/Timpani/Rolls/Timpani1_Roll*")); roll = roll[:int(1.25 * SR)] * np.linspace(0.45, 1, int(1.25 * SR))[:, None] ** 1.5
    poser(mix, roll, 0.0, 1.3)
    cr = lire(un("Percussion/susCymb1-cresc-Short*")); cr = cr[:int(1.25 * SR)]; poser(mix, cr[::-1][:int(1.25 * SR)][::-1], 0.0, 0.5)
    # pulsation « horloge de JT » (claves très légères)
    cl = lire(un("Percussion/Claves1_Hit_v3*"))[:int(0.15 * SR)]
    for k in range(int(5.0 / 0.117)):
        poser(mix, cl, k * 0.117, 0.10 if k % 4 else 0.18)
    # premier impact
    hit = lire(un("Percussion/Timpani/Timpani1_Hit_v3*")); bd = lire(un("Percussion/BDrumNewhit_v6*")); crash = lire(un("Percussion/cymbal-crash1_ff*"))
    for t0 in (1.25,):
        poser(mix, hit, t0, 1.0); poser(mix, bd, t0, 0.8); poser(mix, crash, t0, 0.55)
    accord = [(TPT_ST, 74), (TPT_ST, 78), (TPT_ST, 81), (TBN_ST, 62), (TBN_ST, 57), (COR, 66)]
    for bq, n in accord: poser(mix, note(bq, n, 0.45), 1.25, 0.35)
    # motif de trompette : ta-ta-taaaa
    for t0, n, d in ((2.05, 81, 0.16), (2.23, 81, 0.16), (2.41, 86, 1.9)):
        bq = TPT_ST if d < 0.5 else TPT_S; poser(mix, note(bq, n, d), t0, 0.5)
    # grand accord final tenu + timbale + crash
    for bq, n in ((TPT_S, 78), (TPT_S, 81), (TBN_S, 62), (TBN_S, 57), (TBN_S, 50), (COR, 66), (COR, 69)):
        poser(mix, note(bq, n, 2.3), 2.41, 0.32)
    poser(mix, tuba_synth(73.4, 2.4), 2.41, 0.6)
    poser(mix, lire(un("Percussion/Timpani/Timpani1_Hit_v3*")), 2.41, 0.9); poser(mix, crash, 2.41, 0.5)
    poser(mix, lire(un("Percussion/Snare2-rollNS_v3*"))[:int(0.8 * SR)] * np.linspace(0.2, 1, int(0.8 * SR))[:, None], 1.6, 0.35)
    g = note(GLOCK, 86); poser(mix, g, 2.41, 0.25)
    n = len(mix); f = np.ones(n); a, b = int(4.4 * SR), int(5.2 * SR); f[a:b] = np.linspace(1, 0, b - a); f[b:] = 0
    mix = salle(mix * f[:, None], 2.0, 0.3)
    return normal(mix[:int(5.2 * SR)])

# ------------------------------------------------------------------ bruitages de comédie
def rimshot():
    m = np.zeros((int(1.6 * SR), 2)); sn = lire(un("Percussion/Snare2-HitNS_v3*")); sn2 = lire(un("Percussion/Snare2-HitNS_v6*"))
    poser(m, sn, 0.0, 0.7); poser(m, sn2, 0.16, 0.9); poser(m, lire(un("Percussion/cymbal-crashshort*")), 0.32, 0.6)
    poser(m, lire(un("Percussion/BDrumNewhit_v6*")), 0.32, 0.5); return normal(salle(m, 0.8, 0.15), 0.8)

def xylo_descente():
    m = np.zeros((int(1.4 * SR), 2))
    for k, n in enumerate((84, 79, 76, 72)): poser(m, note(XYLO, n, 0.7), k * 0.11, 0.8 if k < 3 else 1.0)
    return normal(salle(m, 1.0, 0.2), 0.75)

def trombone_triste():
    """« Wah wah wah waaah » au trombone, avec vibrato sur la dernière note."""
    m = np.zeros((int(2.6 * SR), 2))
    for k, (n, d) in enumerate(((58, 0.42), (57, 0.42), (56, 0.42), (55, 1.2))):
        a = note(TBN_S, n, d + 0.1)
        if k == 3:
            t = np.arange(len(a)) / SR; lfo = 1 + 0.012 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t / 0.3)
            idx = np.clip(np.cumsum(lfo), 0, len(a) - 1); a = np.stack([np.interp(idx, np.arange(len(a)), a[:, c]) for c in range(2)], 1)
        poser(m, a, k * 0.45, 0.9)
    return normal(salle(m, 1.0, 0.15), 0.8)

def dun_dun():
    """« Dun dun DUNNN » dramatique (cuivres graves + timbales)."""
    m = np.zeros((int(2.6 * SR), 2)); tim = lire(un("Percussion/Timpani/Timpani1_Hit_v3*"))
    for t0, notes, d, g in ((0.0, (50, 57, 62), 0.35, 0.7), (0.42, (49, 56, 61), 0.35, 0.7), (0.84, (46, 53, 58, 65), 1.6, 1.0)):
        for n in notes: poser(m, note(TBN_S if n < 60 else COR, n, d), t0, 0.35 * g)
        poser(m, tim, t0, 0.8 * g)
    poser(m, lire(un("Percussion/cymbal-crash1_ff*")), 0.84, 0.3); return normal(salle(m, 1.5, 0.25), 0.85)

def woosh():
    a = lire(un("Percussion/susCymb1-cresc-Short*")); n = int(0.45 * SR); a = a[-n:] if len(a) > n else a
    sos = butter(2, [400, 9000], "bandpass", fs=SR, output="sos"); a = sosfilt(sos, a, axis=0)
    env = np.sin(np.linspace(0, np.pi, len(a))) ** 1.5; a = a * env[:, None]
    a[:, 0] *= np.linspace(1.2, 0.6, len(a)); a[:, 1] *= np.linspace(0.6, 1.2, len(a))         # passe de gauche à droite
    return normal(a, 0.6)

def reconstitution():
    m = np.zeros((int(1.8 * SR), 2)); poser(m, lire(un("Percussion/Timpani/Timpani1_Hit_v3*")), 0, 0.7)
    for k, n in enumerate((79, 74)): poser(m, note(GLOCK, n), 0.05 + k * 0.14, 0.5)
    return normal(salle(m, 1.0, 0.2), 0.7)

def nappe():
    """Fond musical discret de 8 s (bouclable) : cors et trombones très doux en ré."""
    m = np.zeros((int(8.4 * SR), 2))
    for t0, notes in ((0, (50, 57, 62, 66)), (4.0, (47, 55, 62, 67))):
        for n in notes: poser(m, note(COR if n > 55 else TBN_S, n, 4.4, vel="v1"), t0, 0.22)
    f = np.ones(len(m)); r = int(0.4 * SR); f[:r] = np.linspace(0, 1, r); f[-r:] = np.linspace(1, 0, r)
    return normal(salle(m * f[:, None], 2.0, 0.35), 0.5)

if __name__ == "__main__":
    for nom, f in (("intro", intro), ("rimshot", rimshot), ("xylo_descente", xylo_descente), ("trombone_triste", trombone_triste),
                   ("dun_dun", dun_dun), ("woosh", woosh), ("reconstitution", reconstitution), ("nappe", nappe)):
        ecrire(nom, f())
