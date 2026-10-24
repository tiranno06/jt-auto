"""File d'attente des fabrications : une seule vidéo fabriquée à la fois, dans l'ordre des demandes, aucune demande perdue.

GitHub ne garde qu'UNE fabrication en attente par file (une 3e demande annule celle qui attendait) : on ne s'en sert donc pas pour
la file. À la place, chaque fabrication (sketch, son TikTok, vidéo manuelle, refaire, aperçu, série, réveil de secours) commence
par ce petit poste d'attente : tant qu'une fabrication lancée AVANT elle n'est pas finie, elle attend son tour. Les réveils du
planning qui n'ont rien à faire (« rien à fabriquer ») ne bloquent personne. Pendant l'attente, la barre de progression du site
affiche « En file d'attente : n vidéo(s) avant ». Sans jeton (essai sur un ordinateur) : rien à attendre."""
import json, os, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progression

PAUSE = 40                                                                 # secondes entre deux coups d'œil (quota de l'API GitHub)
EN_COURS = ("queued", "in_progress", "waiting", "pending", "requested")


def _lire(chemin):
    jeton, depot = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    req = urllib.request.Request(f"https://api.github.com/repos/{depot}{chemin}",
                                 headers={"Authorization": f"Bearer {jeton}", "Accept": "application/vnd.github+json", "User-Agent": "petitsdramas-robot"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read() or b"{}")


def bloque(jobs):
    """Cette fabrication (plus ancienne) passe-t-elle avant nous ? Non si son planning a dit « rien à faire » (fabrication sautée)."""
    fab = next((j for j in jobs if j.get("name") == "emission"), None)
    if fab is not None: return fab.get("status") != "completed" and fab.get("conclusion") != "skipped"
    plan = next((j for j in jobs if j.get("name") == "planning"), None)
    return plan is None or plan.get("status") != "completed" or plan.get("conclusion") == "success"   # planning en cours : peut-être


def rang(r):
    """Ordre de passage : heure de lancement de la tentative (une fabrication relancée par le garde repasse en fin de file), puis n°."""
    return (str(r.get("run_started_at") or r.get("created_at") or ""), int(r["id"]))


def devant(runs, moi, jobs_de):
    """Fabrications lancées avant la nôtre et pas encore finies (les plus anciennes d'abord). moi = notre run (dict)."""
    avant = sorted((r for r in runs if r["id"] != moi["id"] and r.get("status") in EN_COURS and rang(r) < rang(moi)), key=rang)
    return [r for r in avant if bloque(jobs_de(r["id"]))]


def attendre():
    moi = int(os.environ.get("GITHUB_RUN_ID") or 0)
    if not moi or not (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")): return
    progression.TYPE[0] = os.environ.get("TYPE_VIDEO") or "sketch"
    sautes, debut, vu, nous = set(), time.time(), None, None
    while True:
        try:
            nous = nous or _lire(f"/actions/runs/{moi}")
            runs = []
            for st in ("in_progress", "queued", "waiting", "pending", "requested"):
                runs += _lire(f"/actions/workflows/emission.yml/runs?status={st}&per_page=50").get("workflow_runs") or []
            def jobs_de(i):
                if i in sautes: return [{"name": "emission", "status": "completed", "conclusion": "skipped"}]
                j = _lire(f"/actions/runs/{i}/jobs").get("jobs") or []
                if any(x.get("name") == "emission" and x.get("conclusion") == "skipped" for x in j): sautes.add(i)
                return j
            d = devant({r["id"]: r for r in runs}.values(), nous, jobs_de)
        except Exception as e:
            print(f"File d'attente : lecture impossible ({str(e)[:120]}), nouvel essai", flush=True); time.sleep(PAUSE); continue
        if not d:
            if vu: print(f"File d'attente : à nous ! (attente {int(time.time() - debut) // 60} min)", flush=True)
            else: print("File d'attente : aucune autre fabrication en cours, on y va", flush=True)
            return
        if len(d) != vu:
            vu = len(d)
            print(f"File d'attente : {vu} fabrication(s) avant la nôtre : " + ", ".join(r.get("html_url", str(r["id"])) for r in d), flush=True)
        progression.etape(0, f"En file d'attente : {vu} vidéo{'s' if vu > 1 else ''} avant", forcer=True)
        time.sleep(PAUSE)


if __name__ == "__main__":
    attendre()
