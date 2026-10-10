"""Épisodes en série (réglage EPISODES de la régie : « serie » ou « aleatoire »).

En mode série, les vidéos racontent la même histoire d'épisode en épisode (« Jojo cherche un appart, épisode 3 ») :
le robot garde le titre de la série et le résumé de chaque épisode dans episodes/serie.json, les donne à l'auteur pour
écrire la suite, et démarre une nouvelle série quand la saison est finie (EPISODES_PAR_SERIE, 5 par défaut)."""
import json, os

FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "serie.json")

def actif():
    return (os.environ.get("EPISODES") or "aleatoire").strip().lower() == "serie"

def taille():
    try: return max(2, min(20, int(os.environ.get("EPISODES_PAR_SERIE") or 5)))
    except ValueError: return 5

def etat():
    try: return json.load(open(FICHIER, encoding="utf-8"))
    except (OSError, ValueError): return {}

def prochain():
    """(numéro de l'épisode à écrire, état de la série en cours ou {} si on en commence une nouvelle)."""
    e = etat()
    if not e.get("titre") or len(e.get("episodes", [])) >= taille(): return 1, {}
    return len(e["episodes"]) + 1, e

def contexte():
    """Consigne donnée à l'auteur (vide si le mode série est coupé)."""
    if not actif(): return ""
    n, e = prochain()
    if n == 1:
        return (f"épisode 1 d'une NOUVELLE série de {taille()} épisodes. Choisis une situation de départ qui peut tenir une saison "
                "(un projet, une galère, une relation qui va dégénérer d'épisode en épisode) et donne-lui un titre de série accrocheur.")
    passes = "\n".join(f"    Épisode {k + 1} : {x.get('resume', '')}" for k, x in enumerate(e["episodes"]))
    fin = " C'est le DERNIER épisode de la saison : il doit conclure l'histoire en beauté." if n >= taille() else ""
    return (f"épisode {n} sur {taille()} de la série « {e['titre']} ». Épisodes précédents :\n{passes}\n"
            f"  Cet épisode est la SUITE directe : mêmes personnages, même situation qui empire ou rebondit.{fin}")

def idees():
    """Consigne pour la recherche d'idées en mode série."""
    if not actif(): return ""
    n, e = prochain()
    if n == 1: return "\nMODE SÉRIE : chaque idée est le point de départ d'une série de plusieurs épisodes (une galère qui peut durer)."
    return (f"\nMODE SÉRIE : toutes les idées sont des suites possibles (épisode {n}) de la série « {e['titre']} » : "
            + " ; ".join(x.get("resume", "")[:160] for x in e["episodes"][-3:]) + ". Le titre de chaque idée commence par le nom de la série.")

def enregistrer(sk, fichier=""):
    """Après fabrication : ajoute l'épisode à la série (ou démarre la nouvelle). Renvoie le numéro de l'épisode."""
    if not actif() or not sk.get("serie_titre"): return None
    n, e = prochain()
    if n == 1: e = {"titre": sk["serie_titre"], "episodes": []}
    e["episodes"].append({"resume": sk.get("resume_episode") or sk.get("sujet", ""), "fichier": fichier, "titre": sk.get("titre_accroche", "")})
    os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
    json.dump(e, open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return n
