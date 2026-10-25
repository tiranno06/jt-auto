"""Réveil de secours (garde.yml) : relance UNE fois chaque fabrication des 6 dernières heures coupée en route.

Avant, seules les fabrications « en échec » étaient relancées ; une machine coupée par GitHub (délai dépassé, machine arrêtée,
liaison perdue) apparaît « annulée » et était oubliée. Maintenant : échec → relancée ; annulée par GitHub → relancée ; annulée
par l'auteur (« canceled by … ») → laissée telle quelle. La relance reprend là où la fabrication s'était arrêtée quand un point
de sauvegarde existe (moteur/reprise.py)."""
import calendar, json, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dessin_partage as DP

COUPE_GITHUB = re.compile(r"maximum execution time|shutdown signal|lost communication|runner .*(lost|offline|terminated)|"
                          r"exceeded the maximum|has been cancelled because|was not able to complete", re.I)


def annule_par_github(run_id):
    """Annulée par GitHub (et pas par l'auteur) ? Les messages des étapes coupées le disent."""
    msgs = []
    for j in DP._req("GET", f"{DP.API}/repos/{DP._depot()}/actions/runs/{run_id}/jobs").get("jobs") or []:
        if j.get("conclusion") not in ("cancelled", "failure"): continue
        try: msgs += [a.get("message", "") for a in DP._req("GET", f"{DP.API}/repos/{DP._depot()}/check-runs/{j['id']}/annotations")]
        except Exception: pass
    texte = " ".join(msgs)
    if re.search(r"canceled by|cancelled by", texte, re.I): return False
    return bool(COUPE_GITHUB.search(texte))


def a_relancer(runs, maintenant, annule):
    out = []
    for r in runs:
        if r.get("run_attempt", 1) != 1 or r.get("status") != "completed": continue
        if maintenant - calendar.timegm(time.strptime(r["created_at"], "%Y-%m-%dT%H:%M:%SZ")) > 6 * 3600: continue
        if r.get("conclusion") == "failure" or (r.get("conclusion") == "cancelled" and annule(r["id"])): out.append(r["id"])
    return out


def main():
    runs = DP._req("GET", f"{DP.API}/repos/{DP._depot()}/actions/workflows/emission.yml/runs?per_page=30").get("workflow_runs") or []
    for i in a_relancer(runs, time.time(), annule_par_github):
        r = subprocess.run(["gh", "run", "rerun", str(i), "-R", DP._depot(), "--failed"], capture_output=True, text=True)
        print(f"Fabrication {i} relancée (coupée en route)." if r.returncode == 0 else f"Relance de {i} impossible : {r.stderr[:200]}", flush=True)


if __name__ == "__main__":
    try: main()
    except Exception as e: print(f"Réveil de secours : {e}")
