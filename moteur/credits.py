"""Contrôle en direct des outils et des crédits (bouton « Vérifier maintenant » des réglages du site, et à chaque vidéo).

Teste Claude, Mistral, Gemini (un appel minuscule chacun), ElevenLabs (solde de caractères) et Modal (clé valide), puis écrit
episodes/credits.json, que le site lit pour allumer ses voyants (vert : OK ; rouge : crédit épuisé, clé refusée ou absente)."""
import datetime, json, os, subprocess, sys

ICI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ICI)
FICHIER = os.path.join(ICI, "..", "episodes", "credits.json")


def modal():
    if not (os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET")): return "absent"
    try:
        r = subprocess.run(["modal", "app", "list"], capture_output=True, text=True, timeout=120)
        return "ok" if r.returncode == 0 else ("cle" if "token" in (r.stderr + r.stdout).lower() else "erreur")
    except Exception: return "erreur"


def enregistrer(etat):
    d = dict(etat); d["date"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    try:
        os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
        with open(FICHIER, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError: pass
    return d


def main():
    import reseau
    etat = reseau.verifier_credits()
    etat["modal"] = modal()
    d = enregistrer(etat)
    print("Crédits : " + ", ".join(f"{k} = {v}" for k, v in d.items()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
