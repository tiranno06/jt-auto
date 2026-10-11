"""Deux styles de titre d'accroche qui s'affrontent : « POV : … » et la question directe au spectateur (« Toi aussi … ? »).
Chaque vidéo en prend un ; les vues TikTok (episodes/stats.json) départagent peu à peu les deux styles, et le meilleur est
choisi plus souvent (30 % du temps on essaie quand même l'autre, pour continuer à apprendre)."""
import json, os, random

ICI = os.path.dirname(os.path.abspath(__file__))
STYLES = ("pov", "question")

def _vues():
    try:
        with open(os.path.join(ICI, "..", "episodes", "stats.json"), encoding="utf-8") as f:
            return {v.get("fichier"): int(v.get("vues") or 0) for v in json.load(f).get("videos", []) if v.get("fichier")}
    except (OSError, ValueError, AttributeError): return {}

def variantes(sk):
    """Les deux titres possibles pour ce sketch (46 caractères au plus)."""
    t = str(sk.get("titre_accroche") or "").strip(); q = str(sk.get("question") or "").strip()
    pov = t if t.lower().startswith(("pov", "quand")) else (("POV : " + t) if t else "")
    out = {}
    if pov and len(pov) <= 46: out["pov"] = pov
    if q.endswith("?") and len(q) <= 46: out["question"] = q
    return out

def scores(historique, vues=None):
    """Vues moyennes de chaque style (seulement les vidéos dont on connaît les vues)."""
    vues = _vues() if vues is None else vues; acc = {s: [] for s in STYLES}
    for h in historique:
        if h.get("style_accroche") in acc and h.get("fichier") in vues: acc[h["style_accroche"]].append(vues[h["fichier"]])
    return {s: (sum(v) / len(v), len(v)) for s, v in acc.items() if v}

def choisir(sk, historique, vues=None, hasard=random.random):
    """Applique un style au sketch (sk["titre_accroche"]) ; renvoie le style choisi (ou None si un seul possible)."""
    v = variantes(sk)
    if not v: return None
    if len(v) == 1: s = next(iter(v))
    else:
        sc = scores(historique, vues)
        meilleur = max(STYLES, key=lambda s: sc.get(s, (0, 0))[0]) if len(sc) == 2 and min(n for _, n in sc.values()) >= 3 else None
        if meilleur and hasard() > 0.3: s = meilleur
        else: s = STYLES[len([h for h in historique if h.get("style_accroche")]) % 2]   # on alterne pour apprendre
    sk["titre_accroche"] = v[s]
    return s
