"""Paliers d'abonnés fêtés (choix de l'auteur du 11 novembre 2026, idée 14).

Après chaque relevé des statistiques (stats.yml, toutes les heures), si le compte vient de passer un palier (500, 1 000, 2 000,
5 000, 10 000, 20 000, 50 000, 100 000…), le robot fabrique une petite vidéo « merci » jouée par nos personnages (vidéo manuelle sur
un script : jamais publiée automatiquement, l'auteur la regarde et la publie s'il veut) et prévient le téléphone. Chaque palier n'est
fêté qu'une fois (episodes/paliers.json) ; les paliers déjà passés le jour où l'idée est arrivée ne sont pas fêtés après coup.
PALIERS=0 pour couper."""
import datetime, json, os, subprocess, sys

FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "paliers.json")
PALIERS = (500, 1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000, 30000, 50000, 75000, 100000, 200000, 500000, 1000000)


def joli(n):
    return f"{n // 1000000} million{'s' if n >= 2000000 else ''}" if n >= 1000000 else (f"{n:,}".replace(",", " "))


def script(n):
    """Script de la vidéo « merci » (format des scripts de la régie : « Nom : réplique »)."""
    j = joli(n)
    return (f"Jojo : Attends… regarde le compteur… on est {j} ?!\n"
            f"Lila : {j} abonnés ! Mais c'est énorme !\n"
            f"Kévin : Franchement, merci à vous tous, vraiment.\n"
            f"Jojo : Allez, on continue : une nouvelle histoire chaque jour !")


def nouveaux(abonnes, deja, premier=False):
    """Paliers à fêter maintenant. premier=True : on note juste ceux déjà passés (rien n'est fêté après coup)."""
    passes = [p for p in PALIERS if abonnes is not None and abonnes >= p and str(p) not in deja]
    if premier: return [], passes
    return passes[-1:], passes                                             # (plusieurs d'un coup : seul le plus haut est fêté)


def main():
    if os.environ.get("PALIERS", "1") == "0": return
    try: n = json.load(open(os.path.join(os.path.dirname(FICHIER), "stats.json"), encoding="utf-8")).get("abonnes")
    except (OSError, ValueError): return
    if not isinstance(n, int): return
    try: d = json.load(open(FICHIER, encoding="utf-8"))
    except (OSError, ValueError): d = None
    premier = d is None; d = d or {"fetes": {}}
    feter, passes = nouveaux(n, d["fetes"], premier)
    for p in passes: d["fetes"].setdefault(str(p), {"date": datetime.date.today().isoformat(), "fete": bool(p in feter)})
    json.dump(d, open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for p in feter:
        print(f"🎉 Palier de {joli(p)} abonnés passé ({n}) : vidéo « merci » lancée", flush=True)
        r = subprocess.run(["gh", "workflow", "run", "emission.yml", "-R", os.environ.get("GITHUB_REPOSITORY", ""),
                            "-f", "theme=SCRIPT::" + script(p), "-f", "format=mini"], capture_output=True, text=True)
        if r.returncode: print(f"  vidéo « merci » impossible à lancer : {r.stderr[:200]}", flush=True)
        try:
            import alerte
            alerte.alerter(f"🎉 {joli(p)} abonnés !", "Une petite vidéo « merci » est en fabrication : elle sera dans l'onglet Vidéos (jamais publiée toute seule).")
        except Exception: pass
    if premier: print(f"Paliers : {len(passes)} palier(s) déjà passé(s) notés ({n} abonnés), rien de fêté après coup", flush=True)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
