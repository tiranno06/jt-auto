"""Voix sur mesure des personnages (ElevenLabs Voice Design) : une voix unique, créée pour la chaîne, pour Jojo, Kévin et Lila.

Pour chaque personnage : 3 essais de voix d'après sa description, réécoutés par Whisper (on garde celui qui articule le mieux),
puis la voix est enregistrée dans le compte ElevenLabs. Résultat : voix/voix_persos.json (rôle -> voice_id) et un extrait
voix/apercus/<prénom>.mp3 pour écouter. Les voix ne servent que si le réglage « Voix des personnages » est sur « sur mesure ».
Usage : python moteur/voix_design.py   (workflow voix_design.yml, une seule fois ; relançable pour refaire une voix)"""
import base64, io, json, os, sys, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import voix_banque as VB

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FICHE = os.path.join(RACINE, "voix", "voix_persos.json")
APERCUS = os.path.join(RACINE, "voix", "apercus")

PERSOS = {
    "presentateur": ("Jojo", "Native French man in his early thirties with a natural Parisian accent. Medium, slightly nasal, cheeky voice of a stingy guy "
                     "of total bad faith who always has an excuse; laughs at his own jokes, fast and lively delivery, very expressive. Clean studio recording.",
                     "Non mais attends, je suis pas radin, je suis prévoyant ! Si je rends pas la monnaie, c'est pour t'apprendre la valeur de l'argent. "
                     "Franchement, tu devrais me remercier, tu vois ce que je veux dire ?"),
    "invite": ("Kévin", "Young native French man in his early twenties from the Paris suburbs. Light, slightly high-pitched, naive and enthusiastic voice, "
               "a bit goofy, believes everything, speaks fast with youthful energy, very expressive and funny. Clean studio recording.",
               "Ah ouais, trop fort ! Attends, j'ai une idée de génie : on met le téléphone dans le riz et après on le met au four. "
               "Comme ça il sèche deux fois plus vite, non ? Je suis sûr que ça marche, frère !"),
    "envoyee": ("Lila", "Native French woman in her late twenties with a Parisian accent. Clear, confident, sharp and sarcastic voice; quick-witted, "
                "blunt, gets annoyed fast; articulates every word perfectly, very expressive. Clean studio recording.",
                "Alors toi, tu es incroyable. Neuf jours que ta poêle trempe dans l'évier et tu appelles ça une technique ? "
                "Non, Jojo, ça s'appelle la flemme. Et tu vas la laver. Maintenant."),
}

def _wav(b64):
    """mp3 base64 -> signal mono 22 050 Hz."""
    import subprocess, tempfile
    d = tempfile.mkdtemp(); open(f"{d}/a.mp3", "wb").write(base64.b64decode(b64))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{d}/a.mp3", "-ac", "1", "-ar", str(VB.SR), f"{d}/a.wav"], check=True)
    with wave.open(f"{d}/a.wav") as w: return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768

def creer(role, seulement=None):
    prenom, description, texte = PERSOS[role]
    rep = VB._eleven("/v1/text-to-voice/design", {"voice_description": description, "model_id": "eleven_ttv_v3", "text": texte,
                                                    "guidance_scale": 5, "loudness": 0.5}, timeout=300)
    previews = rep.get("previews") or []
    if not previews: raise RuntimeError(f"{prenom} : aucun essai de voix reçu")
    clips = [_wav(p["audio_base_64"]) for p in previews]
    ecoutes = VB.ecouter(clips) or [None] * len(clips)
    notes = []
    for p, c, e in zip(previews, clips, ecoutes):
        ok, d = VB.note(texte, c, e); notes.append((d.get("sim", 0.5) + (0.2 if ok else 0), p, d))
        print(f"  {prenom} essai {p['generated_voice_id'][:8]} : {d}", flush=True)
    _, meilleur, d = max(notes, key=lambda x: x[0])
    v = VB._eleven("/v1/text-to-voice", {"voice_name": f"Petits.Dramas {prenom}", "voice_description": description,
                                         "generated_voice_id": meilleur["generated_voice_id"], "labels": {"chaine": "petits-dramas", "role": role}})
    os.makedirs(APERCUS, exist_ok=True)
    open(os.path.join(APERCUS, f"{prenom.lower().replace('é', 'e')}.mp3"), "wb").write(base64.b64decode(meilleur["audio_base_64"]))
    print(f"{prenom} : voix créée ({v.get('voice_id')}), articulation {d}", flush=True)
    return v["voice_id"]

def main():
    fiche = json.load(open(FICHE, encoding="utf-8")) if os.path.exists(FICHE) else {}
    roles = [r for r in (os.environ.get("ROLES") or "presentateur,invite,envoyee").split(",") if r in PERSOS]
    for role in roles:
        try: fiche[role] = creer(role)
        except Exception as e: print(f"{PERSOS[role][0]} : échec ({str(e)[:300]})", flush=True)
    os.makedirs(os.path.dirname(FICHE), exist_ok=True)
    json.dump(fiche, open(FICHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Voix sur mesure : {fiche}")

if __name__ == "__main__":
    main()
