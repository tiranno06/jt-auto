"""Décide si le robot doit fabriquer une émission maintenant (réglages de la régie).
Le workflow se réveille toutes les heures ; on ne produit que si :
- le rythme (variable FREQUENCE : 2x = deux par jour (12 h + HEURE), 1 = chaque jour, 2 = un jour sur deux, 3 = un jour sur trois, 0 = pause) le permet ;
- l'heure de Paris a atteint HEURE (0 à 23, 17 par défaut : vidéo prête pour le pic d'audience de 18-21 h), avec rattrapage
  si GitHub a sauté un réveil ;
- le nombre de vidéos AUTOMATIQUES du jour n'est pas atteint (les vidéos lancées à la main ne comptent pas).
Un lancement manuel (bouton « Lancer une émission ») passe toujours."""
import datetime, json, os
from zoneinfo import ZoneInfo

def decision():
    if os.environ.get("EVENEMENT") != "schedule": return True, "lancement manuel"
    deux = (os.environ.get("FREQUENCE") or "").strip() == "2x"
    try: freq = 1 if deux else int(os.environ.get("FREQUENCE") or 1)
    except ValueError: freq = 1
    h_ = (os.environ.get("HEURE") or "17").strip().lower()
    if h_ == "auto":                                                       # heure apprise sur les statistiques de la chaîne
        import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            import stats; heure = stats.meilleure_heure()
        except Exception: heure = 17
    else:
        try: heure = int(h_)
        except ValueError: heure = 17
    if freq <= 0: return False, "robot en pause"
    maintenant = datetime.datetime.now(ZoneInfo("Europe/Paris")); jour = maintenant.date()
    if jour.toordinal() % freq: return False, f"jour de repos (une émission tous les {freq} jours)"
    # créneaux du jour déjà passés : on rattrape si GitHub a sauté un réveil (ses tâches planifiées sont souvent en retard ou omises)
    creneaux = sorted({12, heure}) if deux else [heure]
    dus = sum(1 for c in creneaux if maintenant.hour >= c)
    if not dus: return False, f"pas encore l'heure ({maintenant.hour} h, réglé sur {creneaux})"
    h = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "historique.json")
    faites = 0
    if os.path.exists(h):                                                  # seules les vidéos AUTOMATIQUES du jour comptent
        faites = sum(1 for e in json.load(open(h, encoding="utf-8")) if e.get("date") == jour.isoformat() and e.get("auto"))
    budget = (os.environ.get("BUDGET_MOIS") or "").strip().replace(",", ".")
    if budget and os.path.exists(h):                                       # plafond de dépenses Claude du mois (réglage de la régie)
        mois = jour.isoformat()[:7]
        depense = sum((e.get("couts") or {}).get("claude_usd", 0) for e in json.load(open(h, encoding="utf-8")) if str(e.get("date", "")).startswith(mois))
        try:
            if depense >= float(budget): return False, f"budget du mois atteint ({depense:.2f} $ sur {float(budget):.2f} $)"
        except ValueError: pass
    if faites >= dus: return False, f"vidéo(s) automatique(s) du jour déjà faite(s) ({faites}/{len(creneaux)})"
    return True, f"créneau de {creneaux[dus - 1]} h ({faites + 1}/{len(creneaux)} aujourd'hui)"

if __name__ == "__main__":
    go, raison = decision(); print(f"Planning : {'GO' if go else 'rien'} ({raison})")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f: f.write(f"go={'true' if go else 'false'}\n")
