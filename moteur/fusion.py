"""Envoi sûr des résultats d'une fabrication (historique, casting, série) quand plusieurs tournent en parallèle.

git pull --rebase, puis push. Si deux fabrications ont modifié episodes/historique.json en même temps (conflit),
on repart de la version distante, on y réapplique nos fichiers et on FUSIONNE l'historique (aucune vidéo perdue)."""
import json, os, subprocess, sys

def git(*a, ok=False):
    r = subprocess.run(["git", *a], capture_output=True)
    if r.returncode and not ok: raise RuntimeError(f"git {' '.join(a)} : {r.stderr.decode()[:300]}")
    return r

def fusion_historique(nous, eux):
    vus = {h.get("fichier") for h in eux}
    for h in eux:                                                          # même vidéo des deux côtés : on complète
        n = next((x for x in nous if x.get("fichier") and x.get("fichier") == h.get("fichier")), None)
        if n:
            for k, v in n.items(): h.setdefault(k, v)
    return eux + [h for h in nous if h.get("fichier") not in vus]

def rejouer(commande, message):
    """Conflit : on repart de la version distante et on refait l'action (suppression, marquage « publiée »…)."""
    git("rebase", "--abort", ok=True); git("fetch", "-q", "origin"); git("reset", "-q", "--hard", "origin/main")
    subprocess.run(commande, shell=True, check=False)
    git("add", "episodes", ok=True); git("commit", "-q", "-m", message, ok=True)

def main():
    commande = os.environ.get("REJOUER", "").strip()
    for essai in range(4):
        if git("pull", "--rebase", "-q", ok=True).returncode == 0:
            if git("push", ok=True).returncode == 0: print("Historique envoyé."); return 0
            continue
        if commande:
            rejouer(commande, os.environ.get("MESSAGE", "Mise à jour de l'historique"))
            if git("push", ok=True).returncode == 0: print("Action refaite sur la dernière version et envoyée."); return 0
            continue
        git("rebase", "--abort", ok=True); git("fetch", "-q", "origin")
        distant = "origin/main"; base = git("merge-base", "HEAD", distant).stdout.decode().strip()
        fichiers = [f for f in git("diff", "--name-only", base, "HEAD").stdout.decode().splitlines() if f]
        contenus = {}
        for f in fichiers:
            r = git("show", f"HEAD:{f}", ok=True); contenus[f] = r.stdout if r.returncode == 0 else None
        nous = json.loads(contenus.get("episodes/historique.json") or b"[]")
        git("reset", "-q", "--hard", distant)
        for f, c in contenus.items():
            if f == "episodes/historique.json": continue
            if c is None: git("rm", "-q", "--ignore-unmatch", f, ok=True); continue
            os.makedirs(os.path.dirname(f) or ".", exist_ok=True); open(f, "wb").write(c)
        if "episodes/historique.json" in contenus:
            try: eux = json.load(open("episodes/historique.json", encoding="utf-8"))
            except (OSError, ValueError): eux = []
            json.dump(fusion_historique(nous, eux)[-200:], open("episodes/historique.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        git("add", "-A", *contenus.keys(), ok=True)
        git("commit", "-q", "-m", "Émission (historique fusionné)", ok=True)
        if git("push", ok=True).returncode == 0: print("Historique fusionné et envoyé."); return 0
    print("Envoi de l'historique impossible après 4 essais."); return 1

if __name__ == "__main__":
    sys.exit(main())
