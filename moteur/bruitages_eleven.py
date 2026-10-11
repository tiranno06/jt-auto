"""Banque de bruitages du moteur cartoon générée une fois avec l'API Sound Effects d'ElevenLabs (secret ELEVENLABS_API_KEY,
permission « Sound Effects » requise), enregistrée dans sons_eleven/ et réutilisée à chaque vidéo (aucun crédit consommé ensuite).
Lancer : python moteur/bruitages_eleven.py [--refaire]"""
import json, os, sys, urllib.error, urllib.request
import reseau

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOSSIER = os.path.join(RACINE, "sons_eleven")
# nom : (description en anglais, durée en secondes)
BANQUE = {
    "transition":  ("fast modern whoosh transition for a TikTok video edit, clean and punchy, air swoosh passing by", 1.0),
    "swipe":       ("quick short swipe swoosh sound for a video cut, crisp and modern", 0.5),
    "pop":         ("short clean satisfying pop sound for text appearing on screen, modern UI", 0.5),
    "boom_leger":  ("short punchy cinematic bass hit, modern, tight, no reverb tail", 0.8),
    "boom_fin":    ("huge deep cinematic boom impact with sub bass drop and short reverb tail, dramatic meme punchline hit", 2.2),
    "montee":      ("short suspense tension riser building up quickly, modern cinematic, stops abruptly at the end", 1.6),
    "disque":      ("record scratch sound effect, vinyl stop, comedic freeze moment", 0.9),
    "ding":        ("bright modern notification ding, smartphone message", 0.6),
    "foule_rire":  ("small crowd laughing out loud in a room, real people, natural sitcom audience laughter", 2.5),
    "gasp":        ("small crowd gasping in shock, real audience reaction oooh", 1.5),
}

# ambiance de fond de chaque lieu (mode payant) : fabriquée UNE fois par lieu, gardée dans sons_eleven/ambiances/, puis réutilisée
AMBIANCES = {
    "salon": "quiet apartment living room ambience, distant city, clock ticking softly, no voices",
    "cuisine": "kitchen room tone, fridge hum, faint simmering pot, no voices",
    "bureau": "open space office ambience, air conditioning hum, distant keyboard typing, no clear voices",
    "cabinet_medical": "quiet doctor's office room tone, soft air vent, distant hallway, no voices",
    "bar": "busy bar ambience at night, crowd murmur, glasses clinking, no music",
    "chambre": "quiet bedroom at night, soft room tone, distant traffic outside, no voices",
    "salle_sport": "gym ambience, weights clanking, treadmill running, no music",
    "magasin": "supermarket ambience, distant beeps of cashier scanners, trolleys, murmur",
    "classe": "classroom ambience, chairs moving, pages turning, distant murmur",
    "rue": "city street ambience, cars passing, distant horn, footsteps on pavement",
    "restaurant": "restaurant ambience, cutlery and plates, soft crowd murmur, no music",
    "administration": "public office waiting room ambience, ticket machine beep, murmur, air conditioning",
    "hall": "apartment building hallway ambience, echo, distant door closing, footsteps upstairs",
    "caverne": "prehistoric cave ambience, crackling campfire, wind at the entrance, water drops",
    "palais": "large palace hall ambience, big reverb, distant footsteps on marble, harpsichord far away",
}

def ambiance_lieu(lieu, duree=20):
    """Chemin de l'ambiance ElevenLabs du lieu (fabriquée si elle manque) ; None si impossible (pas de clé, pas de crédit)."""
    if lieu not in AMBIANCES: return None
    p = os.path.join(DOSSIER, "ambiances", lieu + ".mp3")
    if os.path.exists(p): return p
    if not os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVENLABS") == "0": return None
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(generer(lieu, AMBIANCES[lieu], duree))
        print(f"  ambiance ElevenLabs fabriquée : {lieu}", flush=True); return p
    except Exception as e:
        print(f"  ambiance ElevenLabs impossible ({lieu} : {str(e)[:120]}) : ambiance de synthèse", flush=True); return None

def generer(nom, texte, duree):
    req = urllib.request.Request("https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128",
                                 data=json.dumps({"text": texte, "duration_seconds": duree, "prompt_influence": 0.6}).encode(),
                                 headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"}, method="POST")
    return reseau.ouvrir(req, timeout=120)

def main(refaire=False):
    if not os.environ.get("ELEVENLABS_API_KEY"): print("ÉCHEC : secret ELEVENLABS_API_KEY absent."); return 1
    os.makedirs(DOSSIER, exist_ok=True); ok = 0
    for nom, (texte, duree) in BANQUE.items():
        p = os.path.join(DOSSIER, nom + ".mp3")
        if os.path.exists(p) and not refaire: print(f"{nom} : déjà présent"); ok += 1; continue
        try:
            a = generer(nom, texte, duree); open(p, "wb").write(a); ok += 1; print(f"{nom} : {len(a)} octets")
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:300]; print(f"{nom} : HTTP {e.code} {msg}")
            if e.code in (401, 403): print("=> La clé n'a pas la permission « Sound Effects » : à activer sur elevenlabs.io (Developers > API Keys)."); return 1
        except Exception as e:
            print(f"{nom} : {e}")
    print(f"{ok}/{len(BANQUE)} bruitages prêts"); return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main("--refaire" in sys.argv))
