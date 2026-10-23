"""Voix de référence par émotion (V1/V2) : les voix gratuites qui imitent une voix (Chatterbox, Zonos) copient le TON de
leur référence. Avec une référence de livre audio, elles lisent ; avec une référence jouée, elles jouent.

Ce module fabrique une fois pour toutes, pour chaque personnage, une courte référence dans chaque émotion
(voix/refs/<rôle>_<émotion>.wav : neutre, vif, rire, colère, triste, calme), avec la meilleure voix disponible :
1. les voix sur mesure de la chaîne (ElevenLabs Voice Design, voix/voix_persos.json), quand il reste du crédit ;
2. sinon Google Chirp 3 HD (offre gratuite) si la clé GOOGLE_TTS_API_KEY existe.
Coût : environ 2 000 caractères ElevenLabs, une seule fois. Les références sont ensuite gratuites pour toujours.
Une référence enregistrée par l'auteur (même nom de fichier) n'est jamais écrasée."""
import json, os, subprocess, tempfile

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOSSIER = os.path.join(RACINE, "voix", "refs")
ROLES = ("presentateur", "invite", "envoyee")
# phrases de jeu (indications ElevenLabs entre crochets) : 8 à 12 secondes, ton de conversation, pas de lecture
LIGNES = {
    "neutre": "Bon, écoute, je vais être honnête avec toi. Franchement, je ne sais pas trop quoi en penser, mais on va voir, hein.",
    "vif": "[excited] Attends, attends, attends ! Tu rigoles ? C'est génial ça ! Mais raconte-moi tout, je veux tout savoir !",
    "rire": "[laughs] Non mais arrête, t'es pas sérieux ? [laughs] Oh là là, j'en peux plus, tu me tues, franchement !",
    "colere": "[angry] Non mais là, ça suffit ! Ça fait trois fois que je te le dis ! Tu m'écoutes jamais, c'est incroyable !",
    "triste": "[sad] [sighs] Je sais pas... j'y croyais vraiment, tu vois. Et puis voilà. Ça s'est pas passé comme prévu.",
    "calme": "[whispers] Chut, doucement. Parle moins fort, il va nous entendre. On attend encore un petit peu, d'accord ?",
}


def manquantes():
    return [(r, e) for r in ROLES for e in LIGNES if not os.path.exists(os.path.join(DOSSIER, f"{r}_{e}.wav"))]


def _wav(octets, chemin):
    tmp = tempfile.mktemp(suffix=".bin"); open(tmp, "wb").write(octets)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-ac", "1", "-ar", "24000", chemin], check=True)


def fabriquer(journal=print):
    """Crée les références qui manquent. Renvoie le nombre créé (0 si aucune source disponible)."""
    a_faire = manquantes()
    if not a_faire: return 0
    os.makedirs(DOSSIER, exist_ok=True); n = 0
    import voix_banque as VB
    persos = {}
    p = os.path.join(RACINE, "voix", "voix_persos.json")
    if os.path.exists(p): persos = json.load(open(p, encoding="utf-8"))
    eleven = bool(os.environ.get("ELEVENLABS_API_KEY")) and os.environ.get("ELEVENLABS", "1") != "0" and "elevenlabs" not in VB.EN_PANNE
    google = bool(os.environ.get("GOOGLE_TTS_API_KEY"))
    GOOGLE_VOIX = {"presentateur": "Charon", "invite": "Orus", "envoyee": "Aoede"}
    for role, emo in a_faire:
        texte = LIGNES[emo]; o = b""
        if eleven and persos.get(role):
            o = (VB.elevenlabs(persos[role], [texte]) or [b""])[0]
            if "elevenlabs" in VB.EN_PANNE: eleven = False
        if not o and google:
            o = (VB.google(GOOGLE_VOIX[role], [VB.sans_tags(texte)]) or [b""])[0]
        if not o: continue
        try:
            _wav(o, os.path.join(DOSSIER, f"{role}_{emo}.wav")); n += 1
        except Exception as e:
            journal(f"  référence {role}/{emo} impossible : {str(e)[:100]}")
    if n: journal(f"Voix de référence par émotion : {n} créée(s) dans voix/refs (les voix gratuites joueront ces émotions)")
    return n


if __name__ == "__main__":
    print(fabriquer(), "référence(s) créée(s)")
