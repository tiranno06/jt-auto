"""Appels réseau robustes : réessai automatique des coupures passagères (réseau, serveur saturé, erreur 5xx, 429)."""
import socket, time, urllib.error, urllib.request

PASSAGERES = (429, 500, 502, 503, 504, 520, 522, 524, 529)

def ouvrir(req, timeout=60, essais=4, pause=2.0):
    """urllib.request.urlopen(req).read() avec réessais (pauses 2, 4, 8 s). Les autres erreurs (crédit, clé…) remontent tout de suite."""
    for k in range(essais):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code not in PASSAGERES or k == essais - 1: raise
            print(f"  réseau : erreur {e.code} passagère, nouvel essai dans {pause * 2 ** k:.0f} s", flush=True)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            if k == essais - 1: raise
            print(f"  réseau : coupure ({str(e)[:80]}), nouvel essai dans {pause * 2 ** k:.0f} s", flush=True)
        time.sleep(pause * 2 ** k)

def claude():
    """Client Claude qui réessaie tout seul les surcharges et coupures passagères (5 essais)."""
    import anthropic
    try: return anthropic.Anthropic(max_retries=5)
    except TypeError: return anthropic.Anthropic()                         # (client simulé des tests)


# ------------------------------------------------------------------ mode économique (réglage du site)
def mode_eco():
    """Réglage « Mode économique » : on garde les outils payants (Claude, ElevenLabs, décors IA) mais on dépense moins.
    Claude Sonnet au lieu d'Opus, petites étapes sur le modèle économique, 1 premier jet au lieu de 3, 2 réécritures et 2 sujets
    au plus, pas de public test ni de recherche des tendances, pas de nouvelles ambiances sonores ElevenLabs (celles déjà faites
    restent utilisées). À appeler avant d'importer ecrire. Renvoie True si le mode est actif."""
    import os
    if (os.environ.get("MODE_ECO") or "0") != "1": return False
    os.environ.update(MODELE_CLAUDE="claude-sonnet-5-5", ETAPES_ECO="1", VERSIONS="1", PUBLIC_TEST="0", TENDANCES="0", AMBIANCES_ELEVEN="0")
    for cle, plafond in (("MAX_REECRITURES", 2), ("SUJETS_MAX", 2)):
        try: v = int(os.environ.get(cle) or plafond)
        except ValueError: v = plafond
        os.environ[cle] = str(min(v, plafond))
    print("Mode économique : Claude Sonnet, 1 premier jet, 2 réécritures au plus, sans public test ni tendances.", flush=True)
    return True


# ------------------------------------------------------------------ crédits vérifiés au départ
def verifier_credits():
    """Vérifie au lancement si Claude et ElevenLabs répondent et ont du crédit (appel minuscule, coût négligeable).
    Pose CLAUDE_INDISPONIBLE=1 et/ou ELEVENLABS=0 dans l'environnement : le robot part directement sur les outils gratuits.
    Renvoie {"claude": "ok"|"secours"|"absent", "elevenlabs": "ok"|"epuise"|"absent"}."""
    import json, os
    etat = {}
    if not os.environ.get("ANTHROPIC_API_KEY"): etat["claude"] = "absent"
    else:
        try:
            claude().messages.create(model="claude-haiku-5-5", max_tokens=1, messages=[{"role": "user", "content": "ok"}]); etat["claude"] = "ok"
        except Exception as e:
            import secours
            etat["claude"] = "secours" if secours.claude_indisponible(e) else "ok"   # erreur passagère : on tentera quand même
    if etat["claude"] != "ok": os.environ["CLAUDE_INDISPONIBLE"] = "1"
    cle = os.environ.get("ELEVENLABS_API_KEY")
    if not cle: etat["elevenlabs"] = "absent"
    else:
        try:
            d = json.loads(ouvrir(urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": cle}), timeout=30))
            reste = int(d.get("character_limit", 0)) - int(d.get("character_count", 0))
            etat["elevenlabs"] = "ok" if reste > 300 else "epuise"
            if etat["elevenlabs"] == "epuise": os.environ["ELEVENLABS"] = "0"
        except Exception as e:
            etat["elevenlabs"] = "ok"                                      # lecture du solde impossible : on tentera quand même
    print(f"Crédits au départ : Claude {etat['claude']}, ElevenLabs {etat['elevenlabs']}", flush=True)
    return etat
