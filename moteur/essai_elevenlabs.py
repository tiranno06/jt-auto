"""Essai de l'accès ElevenLabs (clé dans le secret ELEVENLABS_API_KEY) : abonnement, modèles, voix françaises,
une réplique avec indications de jeu (v3) et un mini-dialogue à deux voix. N'affiche jamais la clé."""
import json, os, sys, urllib.request, urllib.error

CLE = os.environ.get("ELEVENLABS_API_KEY", "").strip()
API = "https://api.elevenlabs.io"
os.makedirs("essai_elevenlabs", exist_ok=True)

def appel(chemin, corps=None, binaire=False):
    req = urllib.request.Request(API + chemin, data=json.dumps(corps).encode() if corps is not None else None,
                                 headers={"xi-api-key": CLE, "Content-Type": "application/json", "Accept": "*/*"},
                                 method="POST" if corps is not None else "GET")
    try:
        r = urllib.request.urlopen(req, timeout=120); d = r.read()
        return r.status, (d if binaire else json.loads(d or b"{}"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400]
    except Exception as e:
        return 0, str(e)[:300]

if not CLE: print("ÉCHEC : le secret ELEVENLABS_API_KEY est vide ou absent."); sys.exit(1)

c, s = appel("/v1/user/subscription")
print(f"1) Abonnement : HTTP {c}")
if c == 200: print(f"   offre {s.get('tier')} ; caractères utilisés {s.get('character_count')} / {s.get('character_limit')} ; "
                   f"clonage instantané {s.get('can_use_instant_voice_cloning')} ; renouvellement {s.get('next_character_count_reset_unix')}")
else: print("   ", s)

c, m = appel("/v1/models")
print(f"2) Modèles : HTTP {c}")
if c == 200:
    for x in m:
        fr = any(l.get("language_id") == "fr" for l in x.get("languages", []))
        print(f"   {x.get('model_id'):28} tts={x.get('can_do_text_to_speech')} français={fr} coût/caractère={x.get('model_rates', {}).get('character_cost_multiplier')}")
else: print("   ", m)
ids = [x.get("model_id") for x in m] if c == 200 else []
pref = [i for i in ids if "v4" in i and "turbo" not in i and "flash" not in i] + [i for i in ids if "v4" in i] + ["eleven_v3", "eleven_multilingual_v2"]
modele = next((i for i in pref if i in ids), "eleven_v3")
print(f"   modèle retenu pour l'essai : {modele}")

c, v = appel("/v1/shared-voices?language=fr&page_size=12&sort=usage_character_count_1y")
print(f"3) Voix françaises de la bibliothèque : HTTP {c}")
voix_fr = []
if c == 200:
    for x in v.get("voices", []):
        voix_fr.append(x); print(f"   {x.get('name')[:28]:28} {x.get('gender')}/{x.get('age')} accent={x.get('accent')} usage={x.get('use_case')} id={x.get('voice_id')}")
else: print("   ", v)
c, mv = appel("/v2/voices?page_size=30")
print(f"   Voix du compte : HTTP {c} ; {len(mv.get('voices', [])) if c == 200 else mv}")
perso = mv.get("voices", []) if c == 200 else []

def choisir(genre):
    for x in voix_fr:
        if x.get("gender") == genre: return x["voice_id"], x.get("name"), x.get("public_owner_id")
    for x in perso:
        if (x.get("labels") or {}).get("gender") == genre: return x["voice_id"], x.get("name"), None
    return (perso[0]["voice_id"], perso[0].get("name"), None) if perso else (None, None, None)

h = choisir("male"); f = choisir("female")
for vid, nom, owner in (h, f):                                     # une voix de la bibliothèque doit être ajoutée au compte pour l'API
    if owner and vid not in {x["voice_id"] for x in perso}:
        c2, r2 = appel(f"/v1/voices/add/{owner}/{vid}", {"new_name": f"JT {nom}"[:30]})
        print(f"   ajout de la voix {nom} au compte : HTTP {c2} {'' if c2 == 200 else r2}")
        if c2 == 200 and r2.get("voice_id"):
            if vid == h[0]: h = (r2["voice_id"], nom, None)
            else: f = (r2["voice_id"], nom, None)

texte = "[soupir] Non mais attends... t'es sérieux là ? [rire] Une p'tite bière, qu'il dit. La dernière fois on a fini à six heures du mat' dans un champ avec des chèvres !"
if h[0]:
    c, a = appel(f"/v1/text-to-speech/{h[0]}?output_format=mp3_44100_128", {"text": texte, "model_id": modele}, binaire=True)
    print(f"4) Réplique jouée ({modele}, voix {h[1]}) : HTTP {c} {'' if c == 200 else a}")
    if c == 200: open("essai_elevenlabs/1_replique.mp3", "wb").write(a); print(f"   {len(a)} octets")
else: print("4) Pas de voix disponible pour l'essai.")

if h[0] and f[0]:
    dial = {"model_id": modele, "inputs": [
        {"text": "Allô ? Ouais, je t'appelle pour te dire que... euh... je te quitte.", "voice_id": h[0]},
        {"text": "[rire nerveux] Tu me quittes ? Par téléphone ? Un dimanche ?", "voice_id": f[0]},
        {"text": "Bah ouais, le lundi j'ai foot.", "voice_id": h[0]},
        {"text": "[énervée] T'es sérieux ?! Huit ans, et tu me largues entre deux matchs ?!", "voice_id": f[0]}]}
    c, a = appel("/v1/text-to-dialogue?output_format=mp3_44100_128", dial, binaire=True)
    print(f"5) Dialogue à deux voix : HTTP {c} {'' if c == 200 else a}")
    if c == 200: open("essai_elevenlabs/2_dialogue.mp3", "wb").write(a); print(f"   {len(a)} octets")

c, s = appel("/v1/user/subscription")
if c == 200: print(f"6) Après l'essai : caractères utilisés {s.get('character_count')} / {s.get('character_limit')}")
