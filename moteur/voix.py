"""Choix automatique de la meilleure voix disponible :
1. Chatterbox (naturel, voix du casting) via Modal si les clés Modal sont présentes ;
2. sinon, ou en cas de panne, Piper (gratuit, local) pour que la vidéo sorte quand même."""
import os, subprocess, tempfile, wave
import numpy as np
import voix_piper

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SR = 22050
# expressivité Chatterbox par personnage (exaggeration, cfg_weight)
JEU = {"presentateur": (0.4, 0.5), "envoyee": (0.6, 0.45), "invite": (0.7, 0.4)}
GRAVES = ("presentateur", "invite")

def _depuis_octets(octets, tmp):
    with open(f"{tmp}.in.wav", "wb") as f: f.write(octets)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmp}.in.wav", "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                    "-ac", "1", "-ar", str(SR), f"{tmp}.out.wav"], check=True)
    with wave.open(f"{tmp}.out.wav") as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768

def chatterbox(repliques, tmp):
    import modal
    refs = {}
    repliques = [{"perso": x["p"], "texte": x["t"], "dit": x.get("d")} for x in repliques]
    for r in {x["perso"] for x in repliques}:
        p = os.path.join(RACINE, "voix", f"{r}.wav")
        if os.path.exists(p): refs[r] = open(p, "rb").read()
    lignes = [dict(texte=x.get("dit") or x["texte"], role=x["perso"], exag=JEU.get(x["perso"], (0.5, 0.5))[0],
                   cfg=JEU.get(x["perso"], (0.5, 0.5))[1]) for x in repliques]
    Voix = modal.Cls.from_name("jt-voix", "Voix")
    octets = Voix().synthese.remote(lignes, refs)
    sortie = []
    for i, (o, x) in enumerate(zip(octets, repliques)):
        a = _depuis_octets(o, f"{tmp}/cb{i}")
        sortie.append(voix_piper.studio(a, f"{tmp}/st{i}", grave=x["perso"] in GRAVES))
    return sortie

def piper(repliques, tmp, secours):
    return [voix_piper.parler(x.get("d") or x["t"], secours[x["p"]], f"{tmp}/p{i}") for i, x in enumerate(repliques)]

def generer(repliques, secours):
    """repliques : [{"p", "t", "d"}] ; secours : réglages Piper par rôle. Renvoie (liste d'audios, nom du moteur utilisé)."""
    tmp = tempfile.mkdtemp()
    if os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET"):
        try:
            return chatterbox(repliques, tmp), "chatterbox"
        except Exception as e:
            print(f"Chatterbox indisponible ({e}) : voix de secours Piper.", flush=True)
    return piper(repliques, tmp, secours), "piper"
