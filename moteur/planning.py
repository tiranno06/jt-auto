"""Décide si le robot doit fabriquer une émission maintenant (réglages de la régie).
Le workflow se réveille toutes les heures ; on ne produit que si :
- le rythme (variable FREQUENCE : 2x = deux par jour (12 h + HEURE), 1 = chaque jour, 2 = un jour sur deux, 3 = un jour sur trois, 0 = pause) le permet ;
- l'heure de Paris a atteint HEURE (0 à 23, 17 par défaut : vidéo prête pour le pic d'audience de 18-21 h), avec rattrapage
  si GitHub a sauté un réveil ;
- le nombre de vidéos AUTOMATIQUES du jour n'est pas atteint (les vidéos lancées à la main ne comptent pas).
Un lancement manuel (bouton « Lancer une émission ») passe toujours."""
import datetime, json, os, sys
from zoneinfo import ZoneInfo

FORMATS = ("mini", "libre", "actu", "programme")

def horaires():
    """Créneaux réglés dans la régie (variable HEURE). Format libre : « 12:00=mini;18:30=libre;21:15|jours=12345 »
    (heure[=type de vidéo], plusieurs créneaux séparés par « ; », jours ISO 1 = lundi … 7 = dimanche). Anciens réglages
    (« 17 », « auto », FREQUENCE « 2x ») toujours compris. Renvoie ([(minutes, type ou None)], jours)."""
    brut = (os.environ.get("HEURE") or "17").strip().lower(); jours = set(range(1, 8))
    if "|jours=" in brut:
        brut, j = brut.split("|jours=", 1); jours = {int(c) for c in j if c in "1234567"} or jours
    creneaux = []
    for morceau in [m.strip() for m in brut.split(";") if m.strip()]:
        h, _, fmt = morceau.partition("="); fmt = fmt.strip() if fmt.strip() in FORMATS else None
        h = h.strip()
        if h == "auto":
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            try:
                import stats; minutes = stats.meilleure_heure() * 60
            except Exception: minutes = 17 * 60
        else:
            hh, _, mm = h.replace("h", ":").partition(":")
            try: minutes = int(hh) * 60 + (int(mm) if mm else 0)
            except ValueError: continue
        if 0 <= minutes < 24 * 60: creneaux.append((minutes, fmt))
    if (os.environ.get("FREQUENCE") or "").strip() == "2x" and len(creneaux) == 1 and creneaux[0][0] != 12 * 60:
        creneaux.append((12 * 60, None))                                     # ancien réglage « deux par jour »
    return sorted(creneaux or [(17 * 60, None)]), jours

def _hist():
    h = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "historique.json")
    try: return json.load(open(h, encoding="utf-8"))
    except (OSError, ValueError): return []

def decision():
    """(go, raison) — voir decision_complete pour le type de vidéo du créneau."""
    return decision_complete()[:2]

def decision_complete():
    """(go, raison, type de vidéo du créneau ou None)."""
    if os.environ.get("EVENEMENT") != "schedule": return True, "lancement manuel", None
    f_ = (os.environ.get("FREQUENCE") or "1").strip()
    try: freq = 1 if f_ == "2x" else int(f_)
    except ValueError: freq = 1
    if freq <= 0: return False, "robot en pause", None
    maintenant = datetime.datetime.now(ZoneInfo("Europe/Paris")); jour = maintenant.date()
    creneaux, jours = horaires()
    if maintenant.isoweekday() not in jours: return False, "jour sans émission (réglage des jours)", None
    if jour.toordinal() % freq: return False, f"jour de repos (une émission tous les {freq} jours)", None
    # créneaux du jour déjà passés : on rattrape si GitHub a sauté un réveil (ses tâches planifiées sont souvent en retard ou omises)
    m_now = maintenant.hour * 60 + maintenant.minute
    dus = sum(1 for m, _ in creneaux if m_now >= m)
    lib = ", ".join(f"{m // 60}:{m % 60:02d}" for m, _ in creneaux)
    if not dus: return False, f"pas encore l'heure ({maintenant:%H:%M}, créneaux {lib})", None
    hist = _hist()
    faites = sum(1 for e in hist if e.get("date") == jour.isoformat() and e.get("auto"))   # seules les vidéos AUTOMATIQUES comptent
    budget = (os.environ.get("BUDGET_MOIS") or "").strip().replace(",", ".")
    if budget:                                                             # plafond de dépenses Claude du mois (réglage de la régie)
        mois = jour.isoformat()[:7]
        depense = sum((e.get("couts") or {}).get("claude_usd", 0) for e in hist if str(e.get("date", "")).startswith(mois))
        try:
            if depense >= float(budget): return False, f"budget du mois atteint ({depense:.2f} $ sur {float(budget):.2f} $)", None
        except ValueError: pass
    if faites >= dus: return False, f"vidéo(s) automatique(s) du jour déjà faite(s) ({faites}/{len(creneaux)})", None
    m, fmt = creneaux[faites]
    return True, f"créneau de {m // 60}:{m % 60:02d} ({faites + 1}/{len(creneaux)} aujourd'hui)", fmt

if __name__ == "__main__":
    go, raison, _ = decision_complete(); print(f"Planning : {'GO' if go else 'rien'} ({raison})")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f: f.write(f"go={'true' if go else 'false'}\n")
