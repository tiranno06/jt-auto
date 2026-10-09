"""Choix automatique de la meilleure voix disponible :
1. Chatterbox (naturel, voix du casting) via Modal si les clés Modal sont présentes ;
2. sinon, ou en cas de panne, Piper (gratuit, local) pour que la vidéo sorte quand même."""
import os, re, subprocess, tempfile, wave
import numpy as np
import voix_piper

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SR = 22050
# expressivité Chatterbox par personnage (exaggeration, cfg_weight)
# (expressivité, cfg) : cfg plus élevé = diction plus posée et plus nette
JEU = {"presentateur": (0.4, 0.6), "envoyee": (0.5, 0.55), "invite": (0.55, 0.55)}
GRAVES = ("presentateur", "invite")

def _depuis_octets(octets, tmp):
    """Décode, coupe précisément le silence de début et de fin (selon l'énergie de la voix)
    et raccourcit les blancs trop longs au milieu (> 0,3 s ramenés à 0,2 s)."""
    with open(f"{tmp}.in.wav", "wb") as f: f.write(octets)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmp}.in.wav", "-ac", "1", "-ar", str(SR), f"{tmp}.out.wav"], check=True)
    with wave.open(f"{tmp}.out.wav") as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    h = int(0.01 * SR); n = max(1, len(a) // h)
    e = np.array([np.sqrt(np.mean(a[k * h:(k + 1) * h] ** 2)) for k in range(n)])
    v = e > 0.05 * (np.percentile(e, 95) + 1e-9)
    if not v.any(): return a
    i0, i1 = max(0, int(np.argmax(v)) - 3), min(n, n - int(np.argmax(v[::-1])) + 8)
    morceaux, k = [], i0
    while k < i1:                                                           # blancs internes raccourcis
        j = k
        if not v[k]:
            while j < i1 and not v[j]: j += 1
            garde = min(j - k, 20) if j - k > 30 else j - k
            morceaux.append(a[k * h:(k + garde) * h]); k = j
        else:
            while j < i1 and v[j]: j += 1
            morceaux.append(a[k * h:j * h]); k = j
    b = np.concatenate(morceaux) if morceaux else a
    r = min(len(b), int(0.015 * SR)); b[:r] *= np.linspace(0, 1, r); b[-r:] *= np.linspace(1, 0, r)
    return b

def chatterbox(repliques, tmp):
    import modal
    refs = {}
    repliques = [{"perso": x["p"], "texte": x["t"], "dit": x.get("d")} for x in repliques]
    for r in {x["perso"] for x in repliques}:
        p = os.path.join(RACINE, "voix", f"{r}.wav")
        if os.path.exists(p): refs[r] = open(p, "rb").read()
    lignes = [dict(texte=x.get("dit") or x["texte"], role=x["perso"], exag=JEU.get(x["perso"], (0.5, 0.55))[0],
                   cfg=JEU.get(x["perso"], (0.5, 0.55))[1]) for x in repliques]
    Voix = modal.Cls.from_name("jt-voix", "Voix")
    res = Voix().synthese.remote(lignes, refs)
    sortie = []
    for i, (r, x) in enumerate(zip(res, repliques)):
        info = r.get("info", {}) if isinstance(r, dict) else {}; o = r.get("wav", b"") if isinstance(r, dict) else r
        if not o: raise RuntimeError(f"réplique {i} impossible à synthétiser")
        a = _depuis_octets(o, f"{tmp}/cb{i}")
        print(f"  voix {i} ({x['perso']}) : {len(a) / SR:.1f} s, prises {info.get('essais')}, rapport durée {info.get('ratio')}, plus long blanc {info.get('blanc')} s", flush=True)
        sortie.append(voix_piper.studio(a, f"{tmp}/st{i}", grave=x["perso"] in GRAVES))
    return sortie

def piper(repliques, tmp, secours):
    return [voix_piper.parler(x.get("d") or x["t"], secours[x["p"]], f"{tmp}/p{i}") for i, x in enumerate(repliques)]

def generer(repliques, secours):
    """repliques : [{"p", "t", "d"}] ; secours : réglages Piper par rôle.
    Renvoie (audios, crédits, mots) : la banque de voix d'abord (meilleure voix vérifiée par Whisper),
    puis Chatterbox seul, puis Piper pour que la vidéo sorte quoi qu'il arrive."""
    tmp = tempfile.mkdtemp()
    try:
        import voix_banque
        r = voix_banque.generer(repliques)
        if r: return r[0], r[2], r[1]
        print("Banque de voix indisponible ou insuffisante : chaîne de secours.", flush=True)
    except Exception as e:
        print(f"Banque de voix en erreur ({str(e)[:200]}) : chaîne de secours.", flush=True)
    if os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET"):
        try:
            return chatterbox(repliques, tmp), ["Chatterbox (MIT), voix Multilingual LibriSpeech (CC BY 4.0)"], None
        except Exception as e:
            print(f"Chatterbox indisponible ({e}) : voix de secours Piper.", flush=True)
    return piper(repliques, tmp, secours), ["Piper / SIWIS (CC BY 4.0)"], None
