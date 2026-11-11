"""Homme ou femme d'après la voix : deux témoins de plus pour le vote de studio.genre_voix (choix de l'auteur du 11 novembre 2026,
idées 1 et 2, après les 6 femmes dessinées en homme du jour).

1. inaSpeechSegmenter (INA, licence MIT) : réseau entraîné sur la radio et la télé FRANÇAISES ; il découpe la voix en morceaux
   « male » / « female » (et repère musique et bruit). Part de « female » dans la voix d'un personnage -> « f », « h » ou doute.
   Il lui faut tensorflow (installé à part dans emission.yml) ; absent -> None. INA_GENRE=0 pour couper.
2. Praat (par parselmouth, GPL) : la référence des chercheurs pour les formants. Longueur apparente du conduit vocal (VTL,
   méthode de Reby et McComb, sur F3 et F4) calculée sur les moments voisés. Plus sûr que notre mesure
   « maison » (studio.espacement_formants) qui s'est trompée sur les dessins animés. PRAAT=0 pour couper.
Chaque témoin rend « h », « f » ou None (doute) ; studio.genre_voix les fait voter avec les autres."""
import os, tempfile, wave
import numpy as np

_SEG = {}
VTL_H, VTL_F = 16.35, 16.2       # cm (F3 et F4) : au-dessus = homme, en dessous = femme, entre les deux = doute ; réglé sur les voix
                                 # de la chaîne : Jojo 17,0-17,9, Kévin 16,5-17,6, Lila 15,8-16,2 (F1 et F2 bougent trop avec la voyelle)


def _wav16(a, sr):
    from scipy.signal import resample_poly
    x = np.asarray(a, np.float64)
    if sr != 16000: x = resample_poly(x, 16000, sr)
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    with wave.open(f, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return f


def ina(a, sr):
    """« h » / « f » d'après inaSpeechSegmenter (70 % de la voix au moins d'un côté), sinon None."""
    if os.environ.get("INA_GENRE", "1") == "0" or len(a) < sr * 1.0 or _SEG.get("echec"): return None
    try:
        if "s" not in _SEG:
            os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
            from inaSpeechSegmenter import Segmenter
            _SEG["s"] = Segmenter(vad_engine="smn", detect_gender=True)
        f = _wav16(a, sr)
        import contextlib, io
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()): segs = _SEG["s"](f)   # (barres de progression)
        finally: os.unlink(f)
    except Exception as e:
        print(f"  inaSpeechSegmenter indisponible ({str(e)[:100]})", flush=True); _SEG["echec"] = True
        return None
    return decision_ina(segs)


def decision_ina(segs):
    """segs = [(étiquette, début, fin)] de inaSpeechSegmenter -> « h » / « f » / None."""
    h = sum(b - a for l, a, b in segs if l == "male"); f = sum(b - a for l, a, b in segs if l == "female")
    if h + f < 0.8: return None
    return "f" if f >= 0.7 * (h + f) else "h" if h >= 0.7 * (h + f) else None


def vtl(a, sr):
    """Longueur apparente du conduit vocal (cm) par Praat, ou None (pas assez de voix, parselmouth absent)."""
    if os.environ.get("PRAAT", "1") == "0" or len(a) < sr * 0.8: return None
    try: import parselmouth
    except Exception: return None
    snd = parselmouth.Sound(np.asarray(a, np.float64), sampling_frequency=sr)
    pitch = snd.to_pitch(time_step=0.01, pitch_floor=75, pitch_ceiling=600)
    form = snd.to_formant_burg(time_step=0.01, max_number_of_formants=5, maximum_formant=5000)
    c = 35000.0
    vals = []
    for t in pitch.xs():
        if not pitch.get_value_at_time(t) or np.isnan(pitch.get_value_at_time(t)): continue      # moments voisés seulement
        F = [form.get_value_at_time(i, t) for i in range(1, 5)]
        if any(f is None or np.isnan(f) for f in F) or not (150 < F[0] < 1200 and F[0] < F[1] < F[2] < F[3] < 5000): continue
        vals.append(np.mean([(2 * i - 1) * c / (4 * F[i - 1]) for i in (3, 4)]))
    return float(np.median(vals)) if len(vals) >= 20 else None


def genre_vtl(v):
    if v is None: return None
    return "h" if v >= VTL_H else "f" if v <= VTL_F else None


def mesurer(sk, role, a, sr):
    """Range dans sk les deux témoins pour ce rôle : "_voix_ina", "_voix_vtl" (cm), "_voix_vtl_genre"."""
    if role in (sk.get("_voix_mesuree") or []): return                     # (2e version du jury, reprise : déjà mesuré)
    sk.setdefault("_voix_mesuree", []).append(role)
    g = ina(a, sr)
    if g: sk.setdefault("_voix_ina", {})[role] = g
    try: v = vtl(a, sr)
    except Exception as e: v = None; print(f"  Praat impossible ({str(e)[:80]})", flush=True)
    if v:
        sk.setdefault("_voix_vtl", {})[role] = round(v, 2)
        g2 = genre_vtl(v)
        if g2: sk.setdefault("_voix_vtl_genre", {})[role] = g2
