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
    if e.get("plan") and len(e.get("episodes", [])) < len(e["plan"]): return len(e["episodes"]) + 1, e
    if not e.get("titre") or len(e.get("episodes", [])) >= max(taille(), len(e.get("plan") or [])): return 1, {}
    return len(e["episodes"]) + 1, e

PLAN = """Tu prépares une SAISON COMPLÈTE de {n} épisodes d'une série de sketchs animés TikTok avec Jojo, Kévin et Lila.
{persos}
Format de chaque épisode : {format}.
Choisis une situation du quotidien qui peut dégénérer d'épisode en épisode (un projet, une galère, une relation), donne un titre de série court et accrocheur,
puis écris le plan : pour chaque épisode, un titre (« POV : … » ou « Quand … », 40 caractères max) et un résumé de 2 phrases (ce qui se passe, la vanne principale, la chute).
Une vraie histoire continue : chaque épisode découle du précédent, la tension monte, chaque épisode finit sur une porte ouverte vers la suite, le dernier conclut en beauté.
Déjà traité récemment (à ne pas reprendre) : {recents}
Rends le plan avec l'outil plan_saison."""
OUTIL_PLAN = {"name": "plan_saison", "description": "Titre de la série et plan des épisodes.",
              "input_schema": {"type": "object", "properties": {"titre": {"type": "string"},
                               "episodes": {"type": "array", "items": {"type": "object", "properties": {"titre": {"type": "string"}, "resume": {"type": "string"}},
                                                                       "required": ["titre", "resume"]}}}, "required": ["titre", "episodes"]}}

def planifier(format_="mini", recents=()):
    """Série d'un seul jet (bouton de la régie) : la saison entière est planifiée d'avance pour que les épisodes s'enchaînent."""
    import anthropic, ecrire
    r = ecrire._appel(anthropic.Anthropic(), None, [{"role": "user", "content": PLAN.format(
        n=taille(), persos=ecrire.personnalites(), recents=" ; ".join(recents)[:1200] or "(rien)",
        format="gag éclair de 15 à 22 s, une seule scène" if format_ == "mini" else "sketch long de plus d'une minute, 2 à 4 scènes")}],
        OUTIL_PLAN, max_tokens=4000)
    eps = [x for x in ecrire._liste(r.get("episodes")) if isinstance(x, dict) and x.get("titre")][:taille()]
    if not r.get("titre") or len(eps) < 2: raise RuntimeError("plan de saison inexploitable")
    e = {"titre": str(r["titre"])[:50], "episodes": [], "plan": [{"titre": str(x["titre"])[:60], "resume": str(x.get("resume", ""))[:500]} for x in eps]}
    os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
    json.dump(e, open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Saison planifiée : « {e['titre']} », {len(eps)} épisodes", flush=True)
    for k, x in enumerate(e["plan"]): print(f"  Épisode {k + 1} : {x['titre']} — {x['resume'][:120]}", flush=True)
    return e

def a_faire():
    """Épisode planifié suivant ({titre, resume} et numéro), ou (None, 0) s'il n'y a plus rien à fabriquer dans le lot."""
    e = etat(); plan = e.get("plan") or []; n = len(e.get("episodes", []))
    return (plan[n], n + 1) if n < len(plan) else (None, 0)

def contexte():
    """Consigne donnée à l'auteur (vide si le mode série est coupé)."""
    if not actif(): return ""
    prevu, k = a_faire()
    if prevu:                                                              # saison planifiée d'avance (série d'un seul jet)
        e = etat()
        passes = "\n".join(f"    Épisode {j + 1} : {x.get('resume', '')}" for j, x in enumerate(e.get("episodes", []))) or "    (aucun : c'est le premier)"
        plan = "\n".join(f"    {j + 1}. {x['titre']} — {x['resume']}" for j, x in enumerate(e["plan"]))
        return (f"épisode {k} sur {len(e['plan'])} de la série « {e['titre']} » (serie_titre = ce titre exactement). Plan de la saison :\n{plan}\n"
                f"  Épisodes déjà fabriqués :\n{passes}\n  ÉCRIS L'ÉPISODE {k} : « {prevu['titre']} » — {prevu['resume']}"
                + (" C'est le DERNIER épisode : il conclut l'histoire en beauté." if k >= len(e["plan"]) else " Termine sur une porte ouverte vers l'épisode suivant."))
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
    if a_faire()[0]:                                                       # série planifiée : on remplit le plan
        e = etat(); n = len(e["episodes"]) + 1
    else:
        n, e = prochain()
        if n == 1: e = {"titre": sk["serie_titre"], "episodes": []}
    e["episodes"].append({"resume": sk.get("resume_episode") or sk.get("sujet", ""), "fichier": fichier, "titre": sk.get("titre_accroche", "")})
    os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
    json.dump(e, open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return n
