"""Décide si le robot doit fabriquer une émission maintenant (réglages de la régie).
Le workflow se réveille toutes les heures ; on ne produit que si :
- le rythme (variable FREQUENCE : 2x = deux par jour (12 h + HEURE), 1 = chaque jour, 2 = un jour sur deux, 3 = un jour sur trois, 0 = pause) le permet ;
- l'heure de Paris a atteint HEURE (0 à 23, 17 par défaut : vidéo prête pour le pic d'audience de 18-21 h), avec rattrapage
  si GitHub a sauté un réveil ;
- le nombre de vidéos AUTOMATIQUES du jour n'est pas atteint (les vidéos lancées à la main ne comptent pas).
Un lancement manuel (bouton « Lancer une émission ») passe toujours."""
import datetime, json, os, re, sys
FENETRE = 120                                                              # minutes après l'heure d'un créneau pendant lesquelles il peut encore partir
from zoneinfo import ZoneInfo

FORMATS = ("mini", "libre", "programme")

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

EN_COURS = ("queued", "in_progress", "waiting", "pending", "requested")

def _api(chemin):
    import urllib.request
    jeton, depot = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not jeton or not depot: return None
    req = urllib.request.Request(f"https://api.github.com/repos/{depot}{chemin}", headers={"Authorization": f"Bearer {jeton}",
                                 "Accept": "application/vnd.github+json", "User-Agent": "petitsdramas-robot"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read() or b"{}")

_MOI = {}
def ce_run():
    """Notre fabrication telle que GitHub la voit (heure de CRÉATION : la même pour une relance) ; {} sans jeton (essais)."""
    if "r" not in _MOI:
        try: _MOI["r"] = (_api(f"/actions/runs/{os.environ['GITHUB_RUN_ID']}") or {}) if os.environ.get("GITHUB_RUN_ID") else {}
        except Exception: _MOI["r"] = {}
    return _MOI["r"]

def _utc(iso): return datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)

def moment():
    """L'heure qui décide du créneau : celle de la DEMANDE (création de la fabrication), pas celle du départ. Une vidéo qui a
    attendu son tour dans la file (ou relancée par le Réveil de secours) garde son créneau au lieu d'être abandonnée."""
    c = ce_run().get("created_at")
    try: return _utc(c).astimezone(ZoneInfo("Europe/Paris")) if c else datetime.datetime.now(ZoneInfo("Europe/Paris"))
    except ValueError: return datetime.datetime.now(ZoneInfo("Europe/Paris"))

def deja_en_file(debut_creneau):
    """Une fabrication du MÊME créneau (même nom : créneau sketch / créneau son TikTok) est-elle déjà en file d'attente ou en cours,
    demandée avant la nôtre ? Alors pas de doublon (le robot se réveille toutes les 30 min tant que la vidéo n'est pas faite)."""
    moi = ce_run()
    if not moi.get("id"): return None
    try: runs = (_api("/actions/workflows/emission.yml/runs?per_page=40") or {}).get("workflow_runs") or []
    except Exception: return None
    for r in runs:
        if r.get("id") == moi["id"] or r.get("status") not in EN_COURS or r.get("display_title") != moi.get("display_title"): continue
        try:
            if debut_creneau <= _utc(r["created_at"]) < _utc(moi["created_at"]): return r
        except (KeyError, ValueError): continue
    return None

def decision(file=True):
    """(go, raison) — voir decision_complete pour le type de vidéo du créneau."""
    return decision_complete(file)[:2]

def decision_complete(file=True):
    """(go, raison, type de vidéo du créneau ou None). file=False : sans chercher de doublon dans la file d'attente (nouvelle
    vérification au départ de la fabrication, quand notre tour est venu)."""
    if os.environ.get("EVENEMENT") != "schedule": return True, "lancement manuel", None
    f_ = (os.environ.get("FREQUENCE") or "1").strip()
    try: freq = 1 if f_ == "2x" else int(f_)
    except ValueError: freq = 1
    if freq <= 0: return False, "robot en pause", None
    maintenant = moment(); jour = maintenant.date()
    creneaux, jours = horaires()
    if maintenant.isoweekday() not in jours: return False, "jour sans émission (réglage des jours)", None
    if jour.toordinal() % freq: return False, f"jour de repos (une émission tous les {freq} jours)", None
    # seul le DERNIER créneau passé compte, et seulement dans les 2 h qui suivent son heure (retard des réveils) :
    # un créneau manqué plus tôt dans la journée n'est jamais rattrapé (pas de rafale de vidéos ni d'essais en boucle)
    m_now = maintenant.hour * 60 + maintenant.minute
    lib = ", ".join(f"{m // 60}:{m % 60:02d}" for m, _ in creneaux)
    passes = [(m, f) for m, f in creneaux if m <= m_now]
    if not passes: return False, f"pas encore l'heure ({maintenant:%H:%M}, créneaux {lib})", None
    m, fmt = passes[-1]
    if m_now - m > FENETRE: return False, f"aucun créneau en cours ({maintenant:%H:%M}, créneaux {lib})", None
    hist = _hist()
    # déjà fait pour CE créneau = une vidéo automatique fabriquée depuis l'heure du créneau. Un essai abandonné (note trop basse)
    # ne compte PAS : le robot réessaie au réveil suivant, tant qu'on est dans la fenêtre et sous ESSAIS_MAX essais
    def apres(date, hhmm):
        try: return date == jour.isoformat() and int(hhmm[:2]) * 60 + int(hhmm[3:5]) >= m
        except (TypeError, ValueError): return False
    def heure_fichier(e):
        r_ = re.search(r"_(\d{2})h(\d{2})_", e.get("fichier", "")); return f"{r_.group(1)}:{r_.group(2)}" if r_ else None
    filiere = "tiktok" if (os.environ.get("FILIERE") or "").strip() == "tiktok" else "sketch"   # sketchs et sons TikTok : plannings séparés
    de_la_filiere = lambda e: (e.get("filiere") or "sketch") == filiere
    faites = sum(1 for e in hist if e.get("auto") and de_la_filiere(e) and apres(e.get("date"), heure_fichier(e))); rates = 0
    try:
        tent = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "tentatives.json"), encoding="utf-8"))
        rates = sum(1 for e in tent if e.get("auto") and de_la_filiere(e) and apres(e.get("date"), e.get("heure") or "00:00"))
    except (OSError, ValueError): pass
    budget = (os.environ.get("BUDGET_MOIS") or "").strip().replace(",", ".")
    if budget:                                                             # plafond de dépenses Claude du mois (réglage de la régie)
        mois = jour.isoformat()[:7]
        depense = sum((e.get("couts") or {}).get("claude_usd", 0) for e in hist if str(e.get("date", "")).startswith(mois))
        try:
            if depense >= float(budget): return False, f"budget du mois atteint ({depense:.2f} $ sur {float(budget):.2f} $)", None
        except ValueError: pass
    if faites: return False, f"créneau de {m // 60}:{m % 60:02d} déjà traité", None
    try: essais_max = max(1, int(os.environ.get("ESSAIS_MAX") or 3))
    except ValueError: essais_max = 3
    if rates >= essais_max:
        return False, f"créneau de {m // 60}:{m % 60:02d} : {rates} essai(s) sans sketch assez bon, limite atteinte (réglage ⚙️ Écriture)", None
    if file:
        debut = datetime.datetime.combine(jour, datetime.time(m // 60, m % 60), ZoneInfo("Europe/Paris")).astimezone(datetime.timezone.utc)
        autre = deja_en_file(debut)
        if autre: return False, f"créneau de {m // 60}:{m % 60:02d} déjà en file d'attente ({autre.get('html_url', autre.get('id'))})", None
    return True, f"créneau de {m // 60}:{m % 60:02d}" + (f", nouvel essai ({rates + 1}/{essais_max})" if rates else ""), fmt

if __name__ == "__main__":
    go, raison, _ = decision_complete(); print(f"Planning : {'GO' if go else 'rien'} ({raison})")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f: f.write(f"go={'true' if go else 'false'}\n")
