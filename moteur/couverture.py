"""Couverture choisie par les statistiques (choix de l'auteur du 6 novembre 2026, idée 45).

Trois images de couverture possibles pour chaque vidéo : la CHUTE finale (comme avant), la RÉACTION la plus forte (visage choqué,
cri, fou rire) et le DÉBUT (les personnages qui posent la situation). Chaque vidéo en prend une ; les vues TikTok
(episodes/stats.json) départagent peu à peu les trois, et la meilleure est choisie plus souvent (30 % du temps on essaie quand
même une autre, pour continuer à apprendre). Réglage COUVERTURE_AUTO=0 : toujours la chute, comme avant."""
import json, os, random

ICI = os.path.dirname(os.path.abspath(__file__))
TYPES = ("chute", "reaction", "debut")
DERNIER = [None]


def _lire(nom, defaut):
    try:
        with open(os.path.join(ICI, "..", "episodes", nom), encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return defaut


def scores(historique=None, vues=None):
    """Vues moyennes de chaque type de couverture (vidéos dont on connaît les vues) : {type: (moyenne, nombre)}."""
    historique = _lire("historique.json", []) if historique is None else historique
    if vues is None:
        vues = {v.get("fichier"): int(v.get("vues") or 0) for v in (_lire("stats.json", {}) or {}).get("videos", []) if v.get("fichier")}
    acc = {t: [] for t in TYPES}
    for h in historique:
        if h.get("type_couverture") in acc and h.get("fichier") in vues: acc[h["type_couverture"]].append(vues[h["fichier"]])
    return {t: (sum(v) / len(v), len(v)) for t, v in acc.items() if v}


def choisir(instants, historique=None, vues=None, hasard=random.random):
    """instants : {type: instant en secondes}. Renvoie l'instant choisi (et note le type dans DERNIER[0])."""
    dispo = [t for t in TYPES if instants.get(t) is not None]
    if not dispo: return None
    if os.environ.get("COUVERTURE_AUTO", "1") == "0" or len(dispo) == 1: t = "chute" if "chute" in dispo else dispo[0]
    else:
        historique = _lire("historique.json", []) if historique is None else historique
        sc = scores(historique, vues)
        ok = {k: v for k, v in sc.items() if k in dispo and v[1] >= 3}
        if len(ok) == len(dispo) and hasard() > 0.3: t = max(ok, key=lambda k: ok[k][0])   # assez de vidéos : la meilleure
        else: t = dispo[len([h for h in historique if h.get("type_couverture")]) % len(dispo)]   # on alterne pour apprendre
    DERNIER[0] = t
    return float(instants[t])
