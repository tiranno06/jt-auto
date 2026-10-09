"""Décide si le robot doit fabriquer une émission maintenant (réglages de la régie).
Le workflow se réveille toutes les heures ; on ne produit que si :
- le rythme (variable FREQUENCE : 1 = chaque jour, 2 = un jour sur deux, 3 = un jour sur trois, 0 = pause) le permet ;
- l'heure de Paris correspond à HEURE (0 à 23, 7 par défaut) ;
- aucune émission n'a déjà été fabriquée aujourd'hui.
Un lancement manuel (bouton « Lancer une émission ») passe toujours."""
import datetime, json, os
from zoneinfo import ZoneInfo

def decision():
    if os.environ.get("EVENEMENT") != "schedule": return True, "lancement manuel"
    try: freq = int(os.environ.get("FREQUENCE") or 1)
    except ValueError: freq = 1
    try: heure = int(os.environ.get("HEURE") or 7)
    except ValueError: heure = 7
    if freq <= 0: return False, "robot en pause"
    maintenant = datetime.datetime.now(ZoneInfo("Europe/Paris")); jour = maintenant.date()
    if maintenant.hour != heure: return False, f"pas l'heure ({maintenant.hour} h, réglé sur {heure} h)"
    if jour.toordinal() % freq: return False, f"jour de repos (une émission tous les {freq} jours)"
    h = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "historique.json")
    if os.path.exists(h) and any(e.get("date") == jour.isoformat() for e in json.load(open(h, encoding="utf-8"))):
        return False, "émission du jour déjà faite"
    return True, "c'est l'heure"

if __name__ == "__main__":
    go, raison = decision(); print(f"Planning : {'GO' if go else 'rien'} ({raison})")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f: f.write(f"go={'true' if go else 'false'}\n")
