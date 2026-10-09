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
    # une phrase à la fois : la synthèse articule mieux des phrases courtes que de longs blocs
    morceaux = []
    for i, x in enumerate(repliques):
        phr = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", (x.get("dit") or x["texte"]).strip()) if p.strip()] or [x["texte"]]
        for p in phr: morceaux.append((i, p))
    lignes = [dict(texte=p, role=repliques[i]["perso"], exag=JEU.get(repliques[i]["perso"], (0.5, 0.55))[0],
                   cfg=JEU.get(repliques[i]["perso"], (0.5, 0.55))[1]) for i, p in morceaux]
    Voix = modal.Cls.from_name("jt-voix", "Voix")
    octets = Voix().synthese.remote(lignes, refs)
    par_rep = {}
    for k, ((i, _), o) in enumerate(zip(morceaux, octets)):
        par_rep.setdefault(i, []).append(_depuis_octets(o, f"{tmp}/cb{k}"))
    sortie = []
    for i, x in enumerate(repliques):
        pause = np.zeros(int(0.16 * SR), np.float32); bouts = par_rep.get(i, [np.zeros(SR // 2, np.float32)])
        a = np.concatenate([b for bout in bouts for b in (bout, pause)][:-1])
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
