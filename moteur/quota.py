"""Quota de l'API GitHub (environ 1 000 appels par heure pour le robot) : la barre de progression, la file d'attente et le dessin
partagé en consomment. Chaque réponse de GitHub dit combien d'appels il reste ; quand il en reste peu, le robot ralentit tout
seul les appels qui ne sont pas indispensables (avancement de la barre, coups d'œil de la file d'attente), au lieu d'être bloqué."""
import time

ETAT = {"reste": None, "remise": None}                                     # appels restants, heure de remise à zéro (epoch)
SEUIL = 150


def noter(entetes):
    """À appeler avec les en-têtes de chaque réponse de GitHub."""
    try:
        r = entetes.get("X-RateLimit-Remaining"); z = entetes.get("X-RateLimit-Reset")
        if r is not None: ETAT["reste"] = int(r)
        if z is not None: ETAT["remise"] = int(z)
    except (TypeError, ValueError, AttributeError): pass


def econome():
    """Peu d'appels restants : ne faire que l'indispensable."""
    return ETAT["reste"] is not None and ETAT["reste"] < SEUIL and (ETAT["remise"] or 0) > time.time()


def pause_conseillee(base):
    """Délai entre deux coups d'œil : normal, ou allongé jusqu'à la remise à zéro du quota (au plus 10 min)."""
    if not econome(): return base
    return max(base, min(600, (ETAT["remise"] or time.time()) - time.time() + 5))


def resume():
    return "inconnu" if ETAT["reste"] is None else f"{ETAT['reste']} appels restants"
