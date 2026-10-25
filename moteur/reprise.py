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


def sauver(ctx, fichiers, nom=None):
    """Dépose l'état (ctx) et les fichiers (vidéos déjà faites) ; renvoie le nom de la reprise."""
    run = os.environ.get("GITHUB_RUN_ID", "0"); nom = nom or f"{PREFIXE}{run}_{int(time.time()) % 100000}"
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
    faits_plus = []                                                        # blocs déposés un à un pendant le dessin (point de sauvegarde)
    for n, a in dispo.items():
        m = __import__("re").match(rf"{__import__('re').escape(nom)}_b_(\d+)_(\d+)\.mp4$", n)
        if m:
            c = os.path.join(tmp, n); DP.telecharger(a, c); faits_plus.append((int(m.group(1)), int(m.group(2)), c))
    def remplacer(x):
        if isinstance(x, str) and x in local: return local[x]
        if isinstance(x, dict): return {k: remplacer(v) for k, v in x.items()}
        if isinstance(x, list): return [remplacer(v) for v in x]
        if isinstance(x, tuple): return tuple(remplacer(v) for v in x)
        return x
    ctx = remplacer(d["ctx"])
    if faits_plus: ctx["faits"] = sorted({(x[0], x[1]): x for x in list(ctx.get("faits") or []) + faits_plus}.values())
    return ctx


# ------------------------------------------------------------------ point de sauvegarde (machine coupée par surprise)
def nom_point(phase):
    """Point de sauvegarde de CETTE fabrication (même nom à la relance par le garde : même n° de run)."""
    return f"c{os.environ.get('GITHUB_RUN_ID', '0')}_{phase}"


def poser_point(ctx, fichiers, phase):
    """Avant de dessiner : tout ce qu'il faut pour reprendre est déposé ; chaque bloc fini sera ajouté (deposer_bloc)."""
    if os.environ.get("POINT_SAUVEGARDE", "1") == "0" or not os.environ.get("GITHUB_RUN_ID") and not DP.LOCAL: return None
    nom = nom_point(phase)
    try:
        if f"{nom}_etat.pkl.gz" in {a["name"] for a in DP.fichiers(DP.release())}: return nom   # (relance : il existe déjà)
        return sauver(ctx, fichiers, nom=nom)
    except Exception as e: print(f"  point de sauvegarde impossible ({str(e)[:120]})", flush=True); return None


ENVOIS = []


def deposer_bloc(nom, a, b, chemin):
    """Bloc d'images fini : copié dans la release en arrière-plan (le dessin continue pendant l'envoi)."""
    import shutil, threading
    if not nom: return
    copie = chemin + ".envoi"; shutil.copy(chemin, copie)
    def envoi():
        try: DP.envoyer(DP.release(), copie, f"{nom}_b_{a}_{b}.mp4")
        except Exception as e: print(f"  bloc {a}–{b} non sauvegardé ({str(e)[:100]})", flush=True)
        finally:
            try: os.remove(copie)
            except OSError: pass
    t = threading.Thread(target=envoi, daemon=True); t.start(); ENVOIS.append(t)


def point_existant():
    """Relance d'une fabrication coupée (2e tentative) : son point de sauvegarde, s'il existe (2e version d'abord)."""
    if int(os.environ.get("GITHUB_RUN_ATTEMPT") or 1) < 2: return None, None
    try: noms = {a["name"] for a in DP.fichiers(DP.release())}
    except Exception: return None, None
    for phase in ("v2", "v1"):
        n = nom_point(phase)
        if f"{n}_etat.pkl.gz" in noms:
            try: return n, charger(n)
            except Exception as e: print(f"  point de sauvegarde {n} illisible ({str(e)[:120]})", flush=True)
    return None, None


def nettoyer(nom):
    try:
        rel = DP.release()
        for a in DP.fichiers(rel):
            if a["name"].startswith(nom + "_"): DP.effacer(a)
    except Exception: pass
