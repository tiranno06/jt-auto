"""Alerte « un robot ne tourne plus » (choix de l'auteur du 23 novembre 2026, idée 16). L'audit du 22 novembre a montré que la
pré-écoute de la nuit, la réserve de sons, l'éclaireur et le contrôleur du soir n'avaient JAMAIS tourné, sans que personne ne le
voie. Après chaque relevé des statistiques (stats.yml, toutes les heures), on regarde le dernier passage de chaque robot :
- pas de passage depuis trop longtemps (délai propre à chaque robot, compté depuis la dernière modification de son workflow) ;
- ou ses deux derniers passages en échec ;
-> une notification sur le téléphone, une fois par jour et par robot (episodes/veille_robots.json). Un robot coupé dans les réglages
(PRE_ECOUTE=0, ECLAIREUR=0, CONTROLEUR_SOIR=0) n'est pas surveillé. VEILLE_ROBOTS=0 pour couper."""
import datetime, json, os, subprocess, sys

ICI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ICI)
ETAT = os.path.join(ICI, "..", "episodes", "veille_robots.json")

# (workflow, nom pour l'auteur, heures sans passage avant l'alerte, réglage qui le coupe)
ROBOTS = [("garde.yml", "le garde (planning, publication automatique)", 2, None),
          ("pre_ecoute.yml", "la réserve de sons", 6, "PRE_ECOUTE"),
          ("eclaireur.yml", "l'éclaireur", 8, "ECLAIREUR"),
          ("controleur.yml", "le contrôleur du soir", 27, "CONTROLEUR_SOIR")]


def _date(s):
    try: return datetime.datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
    except ValueError: return None


def _gh(chemin):
    r = subprocess.run(["gh", "api", f"repos/{os.environ.get('GITHUB_REPOSITORY', '')}/{chemin}"], capture_output=True, text=True, timeout=60)
    if r.returncode: raise RuntimeError(r.stderr.strip()[:150])
    return json.loads(r.stdout or "{}")


def etat_robot(workflow, runs, maintenant, heures):
    """None si tout va bien, sinon le problème (texte). workflow = infos du workflow (updated_at), runs = derniers passages."""
    finis = [r for r in runs if r.get("status") == "completed"]
    if len(finis) >= 2 and all(r.get("conclusion") == "failure" for r in finis[:2]):
        return "ses deux derniers passages ont échoué"
    dates = [d for d in (_date(r.get("created_at")) for r in runs) if d]
    depuis = max(dates + [d for d in [_date((workflow or {}).get("updated_at"))] if d], default=None)
    if depuis is None: return None
    if maintenant - depuis > datetime.timedelta(hours=heures):
        h = int((maintenant - depuis).total_seconds() // 3600)
        return f"aucun passage depuis {h} h" if dates else f"jamais lancé depuis {h} h"
    return None


def verifier(maintenant=None, lire=None, envoyer=None):
    """Renvoie la liste des problèmes signalés aujourd'hui."""
    if os.environ.get("VEILLE_ROBOTS", "1") == "0": return []
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    lire = lire or _gh
    try: E = json.load(open(ETAT, encoding="utf-8"))
    except (OSError, ValueError): E = {}
    jour = maintenant.date().isoformat(); out = []
    for f, nom, heures, reglage in ROBOTS:
        if reglage and (os.environ.get(reglage) or "1").strip() == "0": continue
        try:
            wf = lire(f"actions/workflows/{f}")
            runs = (lire(f"actions/workflows/{f}/runs?per_page=5") or {}).get("workflow_runs") or []
        except Exception as e:
            print(f"Veille des robots : {f} illisible ({str(e)[:100]})"); continue
        pb = etat_robot(wf, runs, maintenant, heures)
        if not pb: print(f"Veille des robots : {nom} ✔"); continue
        print(f"Veille des robots : {nom} : {pb}")
        if E.get(f) == jour: continue                                      # une fois par jour et par robot
        E[f] = jour; out.append(f"{nom} : {pb}")
    if out:
        (envoyer or (lambda t, m: __import__("alerte").alerter(t, m)))("🤖 Un robot ne tourne plus", " ; ".join(out)[:300])
        os.makedirs(os.path.dirname(ETAT), exist_ok=True)
        json.dump(E, open(ETAT, "w", encoding="utf-8"), indent=1)
    return out


if __name__ == "__main__":
    try: verifier()
    except Exception as e: print(f"veille des robots impossible ({str(e)[:150]})")
