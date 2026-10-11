"""Repli gratuit de l'écriture : quand Claude est indisponible (crédit épuisé, clé refusée), le robot pioche un sketch déjà écrit
dans sketchs_secours.json (jamais deux fois le même tant qu'il en reste d'inédits) ; tout le reste de la chaîne (voix, décors,
studio, montage) tourne normalement. Les outils payants restent la règle : ce repli ne sert que si Claude ne répond pas."""
import json, os, random

ICI = os.path.dirname(os.path.abspath(__file__))
BANQUE = os.path.join(ICI, "sketchs_secours.json")
UTILISES = os.path.join(ICI, "..", "episodes", "secours_utilises.json")


def claude_indisponible(e):
    """L'erreur dit-elle que Claude ne répondra pas en réessayant (crédit, clé, accès) ?"""
    t = str(e).lower()
    return any(m in t for m in ("credit balance", "authentication", "invalid x-api-key", "permission_error", "billing", "usage limits",
                                "api_key", "anthropic_api_key", "could not resolve authentication"))


def _lire(f, defaut):
    try:
        with open(f, encoding="utf-8") as h: return json.load(h)
    except (OSError, ValueError): return defaut


def sketch(fmt="mini"):
    """Un sketch de la réserve au format du robot (répliques, découpage en scènes, légende, hashtags)."""
    B = _lire(BANQUE, {}); genre = "libre" if fmt == "libre" else "mini"
    liste = B.get(genre) or B.get("mini") or []
    if not liste: raise RuntimeError("réserve de sketchs de secours vide")
    deja = _lire(UTILISES, [])
    neufs = [s for s in liste if s["sujet"] not in deja]
    if not neufs:                                                          # tout a servi : on recommence par les plus anciens
        ordre = {s: k for k, s in enumerate(deja)}; neufs = sorted(liste, key=lambda s: ordre.get(s["sujet"], -1))[:max(1, len(liste) // 3)]
    s = random.choice(neufs)
    scenes = s.get("scenes") or [[s.get("decor", ""), s["repliques"]]]
    reps, dec = [], []
    for k, (decor, lignes) in enumerate(scenes):
        dec.append({"scene": str(k + 1), "repliques": list(range(len(reps), len(reps) + len(lignes))), "lieu": "", "son": "", "duree": 0, "decor": decor})
        reps += [dict({"p": l[0], "t": l[1]}, **({"objet": l[2]} if len(l) > 2 and l[2] else {})) for l in lignes]   # 3e élément : objet tenu
    reps[-1]["chute"] = True
    sk = {"sujet": s["sujet"], "titre": s["sujet"].upper(), "titre_accroche": s.get("titre_accroche", ""), "legende": s.get("legende", ""),
          "question": s.get("question", ""), "hashtags": s.get("hashtags") or ["humour", "pov"], "repliques": reps, "decoupage": dec,
          "sources": [], "gag": None, "verite": "", "running_gag": "", "bandeau": [],
          "fiche": {"note": 0, "decision": "sketch de secours (Claude indisponible : crédit épuisé ?)", "decoupage": dec}}
    try:
        os.makedirs(os.path.dirname(UTILISES), exist_ok=True)
        with open(UTILISES, "w", encoding="utf-8") as h: json.dump(([x for x in deja if x != s["sujet"]] + [s["sujet"]])[-200:], h, ensure_ascii=False, indent=1)
    except OSError: pass
    print(f"Sketch de secours (sans Claude) : « {s['sujet']} »", flush=True)
    return sk
