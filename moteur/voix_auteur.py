"""Voix enregistrée par l'auteur depuis le site (idée 30) : 10 à 20 secondes au téléphone deviennent la voix de référence d'un
personnage. Les voix gratuites qui imitent une voix (Chatterbox, Zonos) parlent alors avec ce timbre et ce ton.

Le site envoie l'enregistrement (Opus compressé, en base64) au workflow « Ma voix » (voix_auteur.yml) ; ce module le décode,
le nettoie (mono 24 kHz, silences coupés, volume égalisé) et l'enregistre :
- émotion « base » : voix/refs/<rôle>_neutre.wav (servira pour toutes les émotions sans référence propre) ;
- sinon voix/refs/<rôle>_<émotion>.wav (rire, colère… jouée par l'auteur).
Le rôle est noté dans voix/refs/enregistrees.json : jamais écrasé par le robot, priorité au casting (qui est refait).
Usage : python moteur/voix_auteur.py <rôle> <émotion> <fichier base64>"""
import base64, json, os, subprocess, sys, tempfile

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOSSIER = os.path.join(RACINE, "voix", "refs")
ROLES = ("presentateur", "invite", "envoyee")
EMOTIONS = ("base", "neutre", "vif", "rire", "colere", "triste", "calme")


def enregistrer(role, emo, b64):
    if role not in ROLES: raise ValueError(f"rôle inconnu : {role}")
    if emo not in EMOTIONS: raise ValueError(f"émotion inconnue : {emo}")
    brut = base64.b64decode(b64.split(",", 1)[-1])
    if len(brut) < 4000: raise ValueError("enregistrement trop court")
    os.makedirs(DOSSIER, exist_ok=True)
    tmp = tempfile.mktemp(suffix=".webm"); open(tmp, "wb").write(brut)
    sortie = os.path.join(DOSSIER, f"{role}_{'neutre' if emo == 'base' else emo}.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-ac", "1", "-ar", "24000",
                    "-af", "highpass=f=70,silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration=0.6:stop_threshold=-45dB,loudnorm=I=-18:TP=-2",
                    "-t", "20", sortie], check=True)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", sortie], capture_output=True, text=True)
    duree = float(r.stdout.strip() or 0)
    if duree < 3: os.remove(sortie); raise ValueError(f"pas assez de voix entendue ({duree:.1f} s) : parlez plus près du micro")
    p = os.path.join(DOSSIER, "enregistrees.json")
    try: deja = set(json.load(open(p, encoding="utf-8")))
    except Exception: deja = set()
    json.dump(sorted(deja | {role}), open(p, "w", encoding="utf-8"))
    print(f"Voix de l'auteur enregistrée : {role} ({'toutes émotions' if emo == 'base' else emo}), {duree:.1f} s → {os.path.relpath(sortie, RACINE)}")
    return sortie


if __name__ == "__main__":
    role, emo, fichier = sys.argv[1], sys.argv[2], sys.argv[3]
    enregistrer(role, emo, open(fichier, encoding="utf-8").read().strip())
