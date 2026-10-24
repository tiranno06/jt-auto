"""Pause et reprise d'une fabrication (jamais de vidéo perdue à cause de la limite de temps de GitHub).

Juste avant la limite, la fabrication sauvegarde tout ce qui est déjà fait (sketch, son, voix, décors, blocs d'images déjà
dessinés, 1re version et avis du jury si c'est la 2e version qui était en cours), le dépose dans la release temporaire
« dessins-temp » et relance elle-même une fabrication « Reprise » avec les mêmes réglages (entrée chaine = « suite:<nom>|… »).
La reprise passe en tête de la file d'attente, ne refait ni l'écriture, ni le son, ni les voix, ni les décors, et repart de
l'image où l'on s'était arrêté (1re ou 2e version)."""
import gzip, io, json, os, pickle, tarfile, tempfile, time

import dessin_partage as DP

PREFIXE = "s"                                                              # fichiers de reprise dans la release (gardés 3 jours)


class EnPause(BaseException):
    """La fabrication a été mise en pause et une reprise lancée (BaseException : aucun « except Exception » ne l'arrête)."""


def demandee():
    """(nom, chaine d'origine) si cette fabrication est une reprise, sinon (None, None)."""
    c = os.environ.get("CHAINE") or ""
    if not c.startswith("suite:"): return None, None
    nom, _, orig = c[len("suite:"):].partition("|")
    return nom.strip() or None, orig.strip()


def sauver(ctx, fichiers):
    """Dépose l'état (ctx) et les fichiers (vidéos déjà faites) ; renvoie le nom de la reprise."""
    run = os.environ.get("GITHUB_RUN_ID", "0"); nom = f"{PREFIXE}{run}_{int(time.time()) % 100000}"
    rel = DP.release(); tmp = tempfile.mkdtemp(); noms = {}
    for k, chemin in enumerate(fichiers):
        if chemin and os.path.exists(chemin):
            n = f"{nom}_f{k}{os.path.splitext(chemin)[1]}"; DP.envoyer(rel, chemin, n); noms[chemin] = n
    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode="w:gz") as t:
        for p in DP.fichiers_modifies(): t.add(p)
    with gzip.open(f"{tmp}/etat.pkl.gz", "wb") as f: pickle.dump({"ctx": ctx, "fichiers": noms, "depot": tar.getvalue()}, f)
    DP.envoyer(rel, f"{tmp}/etat.pkl.gz", f"{nom}_etat.pkl.gz")
    return nom


def relancer(nom, chaine_orig=""):
    """Nouvelle fabrication avec les mêmes réglages que celle-ci, marquée « reprise »."""
    entrees = {}
    try: entrees = {k: str(v) for k, v in json.loads(os.environ.get("ENTREES") or "{}").items() if v not in (None, "")}
    except ValueError: pass
    entrees["chaine"] = f"suite:{nom}|{chaine_orig}"
    DP._req("POST", f"{DP.API}/repos/{DP._depot()}/actions/workflows/emission.yml/dispatches", {"ref": "main", "inputs": entrees})


def charger(nom):
    """Récupère l'état d'une fabrication en pause : renvoie ctx, avec les chemins des fichiers remplacés par leur copie locale."""
    rel = DP.release(); tmp = tempfile.mkdtemp()
    dispo = {a["name"]: a for a in DP.fichiers(rel)}
    if f"{nom}_etat.pkl.gz" not in dispo: raise RuntimeError(f"reprise {nom} introuvable")
    DP.telecharger(dispo[f"{nom}_etat.pkl.gz"], f"{tmp}/etat.pkl.gz")
    with gzip.open(f"{tmp}/etat.pkl.gz", "rb") as f: d = pickle.load(f)
    with tarfile.open(fileobj=io.BytesIO(d["depot"]), mode="r:gz") as t: t.extractall(".", filter="data")
    local = {}
    for chemin, n in d["fichiers"].items():
        local[chemin] = os.path.join(tmp, n); DP.telecharger(dispo[n], local[chemin])
    def remplacer(x):
        if isinstance(x, str) and x in local: return local[x]
        if isinstance(x, dict): return {k: remplacer(v) for k, v in x.items()}
        if isinstance(x, list): return [remplacer(v) for v in x]
        if isinstance(x, tuple): return tuple(remplacer(v) for v in x)
        return x
    return remplacer(d["ctx"])


def nettoyer(nom):
    try:
        rel = DP.release()
        for a in DP.fichiers(rel):
            if a["name"].startswith(nom + "_"): DP.effacer(a)
    except Exception: pass
