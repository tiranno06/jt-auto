"""Dessin partagé entre plusieurs machines GitHub (gratuites : dépôt public) : la vidéo est découpée en morceaux, des machines
« aides » (workflow dessin.yml) en dessinent chacune un, pendant que la machine principale dessine le sien ; les morceaux sont
recollés sans réencodage (mêmes réglages x264). Échanges par une release GitHub temporaire « dessins-temp » (paquet de départ,
morceaux finis), vidée au fur et à mesure.

Sécurité : une aide en retard ou en échec n'est jamais bloquante, la machine principale redessine elle-même le morceau manquant.
Réglages : DESSIN_PARTAGE=0 pour couper, AIDES (3 par défaut), PARTAGE_MIN_IMAGES (1 200 : en dessous, une seule machine suffit)."""
import gzip, io, json, os, pickle, subprocess, tarfile, time, urllib.request

TAG = "dessins-temp"
VITESSE = [0.0]
API = "https://api.github.com"


LOCAL = os.environ.get("DESSIN_LOCAL")                                     # essais : un dossier à la place de GitHub, aides = programmes locaux


def actif(nf):
    if os.environ.get("DESSIN_PARTAGE", "1") == "0" or os.environ.get("AIDE_DESSIN") == "1": return False
    if nf < int(os.environ.get("PARTAGE_MIN_IMAGES") or 1200): return False
    if (os.environ.get("RENDU") or "") == "essai_pause": return False      # essai de la pause/reprise : une seule machine
    return bool(LOCAL) or (bool(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")) and bool(os.environ.get("GITHUB_REPOSITORY"))
                           and bool(os.environ.get("GITHUB_SHA")))


def _req(methode, url, corps=None, entetes=None, brut=False, timeout=120):
    jeton = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    h = {"Authorization": f"Bearer {jeton}", "Accept": "application/vnd.github+json", "User-Agent": "petitsdramas-robot"}
    h.update(entetes or {})
    data = corps if isinstance(corps, (bytes, type(None))) else json.dumps(corps).encode()
    if data is not None and "Content-Type" not in h: h["Content-Type"] = "application/json"
    r = urllib.request.urlopen(urllib.request.Request(url, data=data, method=methode, headers=h), timeout=timeout)
    contenu = r.read()
    return contenu if brut else (json.loads(contenu) if contenu else {})


def _depot(): return os.environ["GITHUB_REPOSITORY"]


def release():
    """La release temporaire (créée au besoin)."""
    if LOCAL: os.makedirs(LOCAL, exist_ok=True); return {"id": 0}
    try: return _req("GET", f"{API}/repos/{_depot()}/releases/tags/{TAG}")
    except urllib.error.HTTPError as e:
        if e.code != 404: raise
    return _req("POST", f"{API}/repos/{_depot()}/releases", {"tag_name": TAG, "name": "Dessins en cours (temporaire)", "prerelease": True,
                                                            "body": "Morceaux de vidéos en cours de dessin, partagés entre machines. Vidé automatiquement."})


def fichiers(rel):
    if LOCAL:
        return [{"name": n, "url": os.path.join(LOCAL, n), "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                for n in os.listdir(LOCAL) if not n.endswith(".part")]
    out, page = [], 1
    while True:
        lot = _req("GET", f"{API}/repos/{_depot()}/releases/{rel['id']}/assets?per_page=100&page={page}")
        out += lot
        if len(lot) < 100: return out
        page += 1


def envoyer(rel, chemin, nom):
    if LOCAL:
        import shutil; shutil.copy(chemin, os.path.join(LOCAL, nom + ".part")); os.replace(os.path.join(LOCAL, nom + ".part"), os.path.join(LOCAL, nom)); return {}
    with open(chemin, "rb") as f: data = f.read()
    url = f"https://uploads.github.com/repos/{_depot()}/releases/{rel['id']}/assets?name={nom}"
    return _req("POST", url, data, {"Content-Type": "application/octet-stream"}, timeout=900)


def telecharger(asset, chemin):
    if LOCAL:
        import shutil; shutil.copy(asset["url"], chemin); return
    data = _req("GET", asset["url"], entetes={"Accept": "application/octet-stream"}, brut=True, timeout=900)
    with open(chemin, "wb") as f: f.write(data)


def effacer(asset):
    if LOCAL:
        try: os.remove(asset["url"])
        except OSError: pass
        return
    try: _req("DELETE", asset["url"])
    except Exception: pass


def menage(rel, garder=""):
    """Efface les morceaux de plus de 6 h (fabrications coupées) et ceux de ce dessin une fois recollé."""
    for a in fichiers(rel):
        import calendar
        age = time.time() - calendar.timegm(time.strptime(a["created_at"], "%Y-%m-%dT%H:%M:%SZ"))
        vieux = age > (3 * 86400 if a["name"].startswith("s") else 6 * 3600)   # fabrication en pause (reprise.py) : gardée 3 jours
        if vieux or (garder and a["name"].startswith(garder)): effacer(a)


def fichiers_modifies():
    """Fichiers du dépôt modifiés pendant la fabrication (mémoire du studio, banque, voix…) : les aides en ont besoin pour dessiner
    exactement pareil. Les vidéos et les gros fichiers sont laissés de côté."""
    r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True)
    out = []
    for ligne in r.stdout.splitlines():
        p = ligne[3:].strip().strip('"')
        if " -> " in p: p = p.split(" -> ")[1]
        if os.path.isfile(p) and not p.endswith((".mp4", ".mov", ".webm")) and os.path.getsize(p) < 30_000_000: out.append(p)
    return out


VARS_EXCLUES = ("TOKEN", "KEY", "SECRET", "PASSWORD", "PRIVEE", "ABONNEMENTS", "USER", "MAIL", "CREDENTIAL", "PAT", "AUTH", "COOKIE", "SESSION", "AZURE")   # jamais de secret dans le paquet (release publique)


def paquet(chemin, args):
    """Tout ce qu'il faut à une aide pour dessiner : arguments du rendu, réglages (sans secrets), fichiers modifiés."""
    env = {k: v for k, v in os.environ.items() if k.isupper() and not any(x in k for x in VARS_EXCLUES) and not k.startswith(("GITHUB_", "RUNNER_", "ACTIONS_"))}
    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode="w:gz") as t:
        for p in fichiers_modifies(): t.add(p)
    with gzip.open(chemin, "wb") as f: pickle.dump({"args": args, "env": env, "fichiers": tar.getvalue()}, f)


def ouvrir(chemin):
    with gzip.open(chemin, "rb") as f: d = pickle.load(f)
    with tarfile.open(fileobj=io.BytesIO(d["fichiers"]), mode="r:gz") as t: t.extractall(".", filter="data")
    return d


def lancer_aides(nom, sha, plages):
    """Une seule demande : le workflow dessin.yml lance une machine par morceau (matrice)."""
    if LOCAL:
        for a, b in plages:
            subprocess.Popen([os.sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "dessin_aide.py"), nom, str(a), str(b)],
                             env=dict(os.environ, PYTHONHASHSEED="0"))
        return
    _req("POST", f"{API}/repos/{_depot()}/actions/workflows/dessin.yml/dispatches",
         {"ref": "main", "inputs": {"paquet": nom, "sha": sha, "plages": json.dumps([list(p) for p in plages])}})


def decouper(nf, n):
    """n morceaux contigus de tailles égales."""
    bornes = [round(k * nf / n) for k in range(n + 1)]
    return [(bornes[k], bornes[k + 1]) for k in range(n) if bornes[k + 1] > bornes[k]]


def dessiner(nf, args, dessiner_plage, journal=print, progres=None):
    """Dessine les images 0..nf-1 avec l'aide d'autres machines. dessiner_plage(a, b, chemin) dessine localement (vidéo seule).
    Renvoie la liste ordonnée des morceaux vidéo (fichiers mp4) à recoller, ou None si le partage est impossible."""
    import tempfile
    n_aides = max(1, min(8, int(os.environ.get("AIDES") or 3)))
    morceaux = decouper(nf, n_aides + 1)
    a_moi, aux_aides = morceaux[0], morceaux[1:]
    run = os.environ.get("GITHUB_RUN_ID", "0"); nom = f"d{run}_{int(time.time()) % 100000}"
    tmp = tempfile.mkdtemp()
    try:
        rel = release(); menage(rel)
        paquet(f"{tmp}/{nom}.pkl.gz", args)
        envoyer(rel, f"{tmp}/{nom}.pkl.gz", f"{nom}_paquet.pkl.gz")
        lancer_aides(nom, os.environ.get("GITHUB_SHA", ""), aux_aides)
    except Exception as e:
        journal(f"  dessin partagé impossible ({str(e)[:150]}) : une seule machine"); return None
    journal(f"  dessin partagé : {len(aux_aides)} machine(s) d'aide + celle-ci ({len(morceaux)} morceaux de ~{nf // len(morceaux)} images)")
    t0 = time.time()
    chemins = {a_moi: f"{tmp}/m0.mp4"}
    dessiner_plage(a_moi[0], a_moi[1], chemins[a_moi], progres)
    duree_moi = max(60.0, time.time() - t0)
    VITESSE[0] = (a_moi[1] - a_moi[0]) / max(1.0, time.time() - t0)       # images/s d'une machine (pour prévoir une 2e version)
    attente_max = time.time() + max(20 * 60, 0.8 * duree_moi)                # une aide qui démarre tard a encore le temps de finir
    restants = list(aux_aides)
    while restants:
        try:
            dispo = {a["name"]: a for a in fichiers(rel)}
            for p in list(restants):
                cle = f"{nom}_{p[0]}_{p[1]}.mp4"
                if cle in dispo:
                    chemins[p] = f"{tmp}/{p[0]}.mp4"; telecharger(dispo[cle], chemins[p]); restants.remove(p)
                    journal(f"  morceau {p[0]}–{p[1]} reçu d'une machine d'aide")
                elif f"{nom}_{p[0]}_{p[1]}.echec" in dispo or time.time() > attente_max:
                    journal(f"  morceau {p[0]}–{p[1]} : aide en retard ou en échec, dessiné ici"); restants.remove(p)
                    chemins[p] = f"{tmp}/{p[0]}.mp4"; dessiner_plage(p[0], p[1], chemins[p], progres)
        except Exception as e:
            journal(f"  lecture des morceaux impossible ({str(e)[:120]}), nouvel essai")
        if restants: time.sleep(20)
    try: menage(rel, garder=nom)
    except Exception: pass
    return [chemins[p] for p in morceaux]
