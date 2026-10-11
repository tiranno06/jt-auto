"""Analyse gratuite de la bande son d'une vidéo TikTok envoyée (doublage) : ce qu'on y entend, rangé dans la banque
(episodes/banque_visuelle.json, champ « audio ») pour que le robot apprenne vidéo après vidéo.

Mesures : nombre de voix, hauteur et genre de chaque voix, part de parole de chacune, débit (mots par seconde), blancs entre les
répliques, répliques qui se coupent la parole, dynamique (voix posée ou criée), présence de musique de fond, bruitages (impacts
repérés dans le son hors voix : graves type « boom » ou aigus type « pop / ding », et s'ils tombent sur une fin de réplique = une
vanne), événements repérés par ElevenLabs (rires, applaudissements…) et émotions de jeu (indications de Claude)."""
import re
from collections import Counter
import numpy as np

SR = 22050


def _rms(x, h):
    n = len(x) // h
    return np.sqrt(np.mean(np.square(x[:n * h].reshape(n, h)), 1) + 1e-12) if n else np.zeros(0)


def _impacts(fond, sr=SR):
    """Attaques nettes dans le son hors voix (bruitages) : liste de (instant, grave ou aigu)."""
    h = sr // 100; e = _rms(fond, h)
    if len(e) < 20: return []
    seuil = max(np.percentile(e, 75), 1e-4)
    out, der = [], -1.0
    for k in range(6, len(e) - 1):
        avant = float(np.mean(e[k - 6:k - 1])) + 1e-6                    # attaque : 4 fois plus fort que les 50 ms d'avant
        if e[k] > seuil and e[k] > 4.0 * avant and e[k] >= e[k + 1] and k / 100 - der > 0.35:
            seg = fond[k * h:k * h + int(0.15 * sr)]
            if len(seg) < 256: continue
            sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2; f = np.fft.rfftfreq(len(seg), 1 / sr)
            grave = float(sp[f < 250].sum() / (sp.sum() + 1e-12))           # part d'énergie sous 250 Hz : « boom » ou « pop / ding »
            out.append((round(k / 100, 2), "grave" if grave > 0.45 else "aigu")); der = k / 100
    return out


def analyser(mono, voix_sig, segs, hz, evenements=(), indications=()):
    mono = np.asarray(mono, np.float32); duree = len(mono) / SR
    mots = sum(len(s.get("mots") or s.get("t", "").split()) for s in segs)
    parole = sum(max(0.0, s["fin"] - s["deb"]) for s in segs) or 1e-6
    voix = []
    for v, h_ in hz.items():
        part = sum(s["fin"] - s["deb"] for s in segs if s["voix"] == v) / parole
        voix.append(dict(hz=h_, genre=(None if not h_ else "f" if h_ > 185 else "h" if h_ < 165 else "?"), part=round(part, 2)))
    blancs = [segs[k + 1]["deb"] - segs[k]["fin"] for k in range(len(segs) - 1)]
    coupes = sum(1 for b, k in zip(blancs, range(len(segs) - 1)) if b < 0.05 and segs[k]["voix"] != segs[k + 1]["voix"])
    v_ = voix_sig if voix_sig is not None and len(voix_sig) >= len(mono) * 0.9 else None
    ev = _rms(v_ if v_ is not None else mono, SR // 50); ev = ev[ev > 1e-3]
    dyn = float(20 * np.log10(np.percentile(ev, 95) / np.percentile(ev, 20))) if len(ev) > 10 else 0.0
    cris = float(np.mean(ev > 0.7 * ev.max())) if len(ev) else 0.0
    musique, impacts = None, []
    if v_ is not None:                                                     # son hors voix = musique + bruitages
        fond = mono[:len(v_)] - v_[:len(mono)]
        rf, rm = _rms(fond, SR // 10), _rms(mono[:len(fond)], SR // 10)
        musique = round(float(np.median(rf / (rm + 1e-9))), 2) if len(rm) else None
        impacts = _impacts(fond)
    fins = [s["fin"] for s in segs]
    sur_vanne = sum(1 for t, _ in impacts if any(-0.2 <= t - f <= 0.8 for f in fins))
    emo = Counter(m.lower() for d in indications for m in re.findall(r"\[([^\]]{2,25})\]", str(d)))
    return dict(duree=round(duree, 1), nb_voix=len(hz), voix=voix, debit=round(mots / parole, 2),
                blanc_moyen=round(float(np.mean([b for b in blancs if b > 0] or [0])), 2), coupes=coupes,
                dynamique_db=round(dyn, 1), cris=round(cris, 3), musique=musique,
                impacts=len(impacts), impacts_10s=round(10 * len(impacts) / max(duree, 1), 2),
                graves=sum(1 for _, g in impacts if g == "grave"), aigus=sum(1 for _, g in impacts if g == "aigu"), sur_vanne=sur_vanne,
                evenements=dict(Counter(str(e[2]) for e in evenements).most_common(8)), emotions=dict(emo.most_common(8)))


def texte(A):
    if not A: return ""
    v = ", ".join(f"{x['hz']} Hz ({x['genre'] or '?'}, {int(100 * x['part'])} %)" for x in A.get("voix") or [])
    m = "pas de mesure" if A.get("musique") is None else ("musique de fond" if A["musique"] > 0.25 else "peu ou pas de musique")
    return (f"{A['nb_voix']} voix [{v}], {A['debit']} mots/s, blancs {A['blanc_moyen']} s, {A['coupes']} coupure(s) de parole, "
            f"dynamique {A['dynamique_db']} dB, {m}, {A['impacts']} bruitage(s) ({A['graves']} graves, {A['aigus']} aigus, "
            f"{A['sur_vanne']} sur une fin de réplique), événements {A.get('evenements') or {}}, émotions {A.get('emotions') or {}}")
