"""Décide si le robot doit fabriquer une émission maintenant (réglages de la régie).
Le workflow se réveille toutes les heures ; on ne produit que si :
- le rythme (variable FREQUENCE : 2x = deux par jour (12 h + HEURE), 1 = chaque jour, 2 = un jour sur deux, 3 = un jour sur trois, 0 = pause) le permet ;
- l'heure de Paris correspond à HEURE (0 à 23, 17 par défaut : vidéo prête pour le pic d'audience de 18-21 h) ;
- aucune émission n'a déjà été fabriquée aujourd'hui.
Un lancement manuel (bouton « Lancer une émission ») passe toujours."""
import datetime, json, os
from zoneinfo import ZoneInfo

def decision():
    if os.environ.get("EVENEMENT") != "schedule": return True, "lancement manuel"
    deux = (os.environ.get("FREQUENCE") or "").strip() == "2x"
    try: freq = 1 if deux else int(os.environ.get("FREQUENCE") or 1)
    except ValueError: freq = 1
    try: heure = int(os.environ.get("HEURE") or 17)
    except ValueError: heure = 17
    if freq <= 0: return False, "robot en pause"
    maintenant = datetime.datetime.now(ZoneInfo("Europe/Paris")); jour = maintenant.date()
    heures = {heure, 12} if deux else {heure}
    if maintenant.hour not in heures: return False, f"pas l'heure ({maintenant.hour} h, réglé sur {sorted(heures)})"
    if jour.toordinal() % freq: return False, f"jour de repos (une émission tous les {freq} jours)"
    h = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "historique.json")
    if os.path.exists(h):
        faites = sum(1 for e in json.load(open(h, encoding="utf-8")) if e.get("date") == jour.isoformat())
        if faites >= (2 if deux else 1): return False, "émission(s) du jour déjà faite(s)"
    return True, "c'est l'heure"

if __name__ == "__main__":
    go, raison = decision(); print(f"Planning : {'GO' if go else 'rien'} ({raison})")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f: f.write(f"go={'true' if go else 'false'}\n")
