"""Alerte « bientôt plus rien à publier » (choix de l'auteur du 21 novembre 2026, idée 10) : le compteur « vidéos à publier » ne se
voyait que sur le site. Après chaque relevé des statistiques (stats.yml), si la publication automatique est activée et qu'il reste
2 jours de vidéos ou moins (cochées « À publier » pas encore publiées + déjà programmées, divisées par le nombre de vidéos par jour),
une notification part sur le téléphone, une fois par jour au plus (episodes/stock_alerte.json). STOCK_ALERTE=0 pour couper."""
import datetime, json, os, sys
ICI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ICI)
ETAT = os.path.join(ICI, "..", "episodes", "stock_alerte.json")


def jours_restants(reglages, historique, maintenant):
    """(nombre de vidéos qui attendent, jours qu'elles couvrent)."""
    import publication_auto as P
    attente = P.file_attente(reglages.get("PUBLI_FILE"), historique)
    prog = [h for h in historique if h.get("publie") is True and h.get("programmee") and str(h["programmee"])[:16] > maintenant.strftime("%Y-%m-%dT%H:%M")]
    par_jour = max(1, len(P.creneaux(reglages, maintenant.weekday(), maintenant.date())))
    n = len(attente) + len(prog)
    return n, n / par_jour


def verifier(maintenant=None, reglages=None, historique=None, envoyer=None):
    """Renvoie le message envoyé (ou None)."""
    if os.environ.get("STOCK_ALERTE", "1") == "0": return None
    from zoneinfo import ZoneInfo
    maintenant = maintenant or datetime.datetime.now(ZoneInfo("Europe/Paris"))
    reglages = reglages if reglages is not None else {k: os.environ.get(k, "") for k in ("PUBLI_AUTO", "PUBLI_HEURE", "PUBLI_FILE", "PUBLI_HEURE_AUTO", "PUBLI_DEUX", "PUBLI_HEURE2", "PUBLI_FRANCO", "PUBLI_HEURE_FRANCO")}
    if str(reglages.get("PUBLI_AUTO") or "0").strip() != "1": return None
    if historique is None:
        try: historique = json.load(open(os.path.join(ICI, "..", "episodes", "historique.json"), encoding="utf-8"))
        except (OSError, ValueError): return None
    n, jours = jours_restants(reglages, historique, maintenant)
    if jours > 2: return None
    try: E = json.load(open(ETAT, encoding="utf-8"))
    except (OSError, ValueError): E = {}
    if E.get("date") == maintenant.date().isoformat(): return None         # une fois par jour au plus
    msg = (f"Plus aucune vidéo cochée « À publier » : la publication automatique s'arrête." if n == 0 else
           f"Il reste {n} vidéo(s) à publier, soit {jours:.1f} jour(s) : lancez une nouvelle salve et cochez-en d'autres.")
    (envoyer or (lambda t, m: __import__("alerte").alerter(t, m)))("📦 Bientôt plus rien à publier", msg)
    os.makedirs(os.path.dirname(ETAT), exist_ok=True)
    json.dump({"date": maintenant.date().isoformat(), "videos": n}, open(ETAT, "w", encoding="utf-8"))
    print(f"Stock : {msg}")
    return msg


if __name__ == "__main__":
    try: verifier()
    except Exception as e: print(f"alerte du stock impossible ({str(e)[:150]})")
