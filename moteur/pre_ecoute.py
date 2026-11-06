"""Pré-écoute la nuit (choix de l'auteur du 6 novembre 2026, option PRE_ECOUTE : 1 = activée, par défaut ; 0 = coupée).

Vers 2 h du matin (heure de Paris), le garde lance le workflow « Pré-écoute des sons TikTok » (pre_ecoute.yml). Il tire au hasard
quelques sons des profils (comme une vraie fabrication : jamais déjà utilisés, voix bien différentes d'abord) et fait TOUTE l'écoute
à l'avance : téléchargement, voix isolée, transcriptions, qui parle, image de l'original, mise en scène par l'IA. Le résultat est
rangé dans la release « sons-prets » (3 jours au plus). À l'heure du créneau, la fabrication prend le plus ancien son prêt et passe
tout de suite au dessin. Les sons ratés (aucune parole, trop longs, refusés) sont écartés la nuit, sans faire attendre personne.
Rien de prêt (option coupée, stock vide, son repris entre-temps) : la fabrication écoute elle-même un son, comme avant.
Nombre de sons préparés : STOCK_SONS (par défaut, autant que de créneaux TikTok dans la journée, 1 à 4)."""
import calendar, gzip, json, os, pickle, re, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dessin_partage as DP

TAG = "sons-prets"
AGE_MAX = 3 * 86400


def actif():
    return (os.environ.get("PRE_ECOUTE") or "1").strip() != "0"


def stock_voulu():
    try:
        n = int(os.environ.get("STOCK_SONS") or 0)
        if n > 0: return min(n, 6)
    except ValueError: pass
    heures = [h for h in re.split(r"[;,\s]+", os.environ.get("HEURE_TIKTOK") or "") if re.match(r"^\d{1,2}:\d{2}$", h)]
    return max(1, min(4, len(heures) or 1))


def _release():
    if DP.LOCAL: os.makedirs(DP.LOCAL, exist_ok=True); return {"id": 0}
    import urllib.error
    try: return DP._req("GET", f"{DP.API}/repos/{DP._depot()}/releases/tags/{TAG}")
    except urllib.error.HTTPError as e:
        if e.code != 404: raise
    return DP._req("POST", f"{DP.API}/repos/{DP._depot()}/releases", {"tag_name": TAG, "name": "Sons TikTok déjà écoutés (temporaire)", "prerelease": True,
                                                                   "body": "Sons écoutés la nuit (pré-écoute), pris par les fabrications de la journée. Vidé automatiquement."})


def _age(a):
    try: return time.time() - calendar.timegm(time.strptime(a["created_at"], "%Y-%m-%dT%H:%M:%SZ"))
    except (KeyError, ValueError): return 0


def _id(url):
    m = re.search(r"/video/(\d+)", str(url)); return m.group(1) if m else ""


def stock(rel=None):
    """Sons prêts : [{nom, id, asset, age}] (les plus anciens d'abord). Les trop vieux sont effacés."""
    rel = rel or _release(); out = []; fich = DP.fichiers(rel)
    for a in fich:
        m = re.match(r"^(p\d+_(\d+))_etat\.pkl\.gz$", a["name"])
        if not m: continue
        if _age(a) > AGE_MAX:
            for b in fich:
                if b["name"].startswith(m.group(1) + "_"): DP.effacer(b)
            continue
        out.append(dict(nom=m.group(1), id=m.group(2), asset=a, age=_age(a)))
    return sorted(out, key=lambda x: -x["age"])


def _fichiers_de(x, racine):
    """Fichiers temporaires (son, vidéo d'origine…) cités dans l'écoute : à déposer avec elle."""
    out = set()
    if isinstance(x, str):
        if x.startswith(racine) and os.path.isfile(x): out.add(x)
    elif isinstance(x, dict):
        for v in x.values(): out |= _fichiers_de(v, racine)
    elif isinstance(x, (list, tuple)):
        for v in x: out |= _fichiers_de(v, racine)
    return out


def _etats():
    import doublage, video_ia, locuteurs
    return {"EVENEMENTS": list(doublage.EVENEMENTS), "SOURCE_MOTS": list(doublage.SOURCE_MOTS), "DERNIER": dict(video_ia.DERNIER),
            "ETAT": dict(locuteurs.ETAT)}


def _remettre(e):
    import doublage, video_ia, locuteurs
    doublage.EVENEMENTS[:] = e.get("EVENEMENTS") or []; doublage.SOURCE_MOTS[:] = e.get("SOURCE_MOTS") or [""]
    video_ia.DERNIER.clear(); video_ia.DERNIER.update(e.get("DERNIER") or {})
    locuteurs.ETAT.clear(); locuteurs.ETAT.update(e.get("ETAT") or {"ressemblance": None})


def deposer(url, prep, rel=None):
    """Range l'écoute d'un son (url, résultat de doublage.preparer) dans la release « sons-prets »."""
    rel = rel or _release(); nom = f"p{int(time.time())}_{_id(url) or '0'}"; tmp = tempfile.mkdtemp()
    noms = {}
    for k, chemin in enumerate(sorted(_fichiers_de(prep, tempfile.gettempdir()))):
        n = f"{nom}_f{k}{os.path.splitext(chemin)[1]}"; DP.envoyer(rel, chemin, n); noms[chemin] = n
    with gzip.open(f"{tmp}/etat.pkl.gz", "wb") as f:
        pickle.dump({"url": url, "prep": prep, "etats": _etats(), "fichiers": noms, "date": time.time()}, f)
    DP.envoyer(rel, f"{tmp}/etat.pkl.gz", f"{nom}_etat.pkl.gz")
    return nom


def _remplacer(x, local):
    if isinstance(x, str) and x in local: return local[x]
    if isinstance(x, dict): return {k: _remplacer(v, local) for k, v in x.items()}
    if isinstance(x, list): return [_remplacer(v, local) for v in x]
    if isinstance(x, tuple): return tuple(_remplacer(v, local) for v in x)
    return x


def prendre(historique, journal=print):
    """Le plus ancien son prêt jamais utilisé : (url, prep) avec ses fichiers téléchargés, ou None. Il est retiré du stock."""
    if not actif(): return None
    try:
        import profils_tiktok
        rel = _release(); deja = profils_tiktok.deja_utilisees(historique); fich = DP.fichiers(rel)
        for s in stock(rel):
            parts = [b for b in fich if b["name"].startswith(s["nom"] + "_")]
            if s["id"] in deja:                                            # repris entre-temps (lien collé à la main…) : écarté
                for b in parts: DP.effacer(b)
                continue
            tmp = tempfile.mkdtemp(); DP.telecharger(s["asset"], f"{tmp}/etat.pkl.gz")
            DP.effacer(s["asset"])                                         # réservé : une autre fabrication ne le prendra pas
            with gzip.open(f"{tmp}/etat.pkl.gz", "rb") as f: d = pickle.load(f)
            dispo = {b["name"]: b for b in parts}; local = {}
            for chemin, n in d["fichiers"].items():
                local[chemin] = os.path.join(tmp, n); DP.telecharger(dispo[n], local[chemin])
            for b in parts:
                if b["name"] != s["asset"]["name"]: DP.effacer(b)          # pris : fichiers retirés du stock
            _remettre(d.get("etats") or {})
            journal(f"Pré-écoute : son déjà écouté cette nuit pris dans le stock ({d['url']}) : on passe directement à la suite")
            return d["url"], _remplacer(d["prep"], local)
    except Exception as e: journal(f"Pré-écoute : stock illisible ({str(e)[:150]}) : écoute normale")
    return None


def remplir(journal=print):
    """Travail de la nuit : complète le stock jusqu'à stock_voulu() sons prêts. Renvoie le nombre de sons ajoutés."""
    if not actif(): journal("Pré-écoute coupée (réglage PRE_ECOUTE=0)"); return 0
    import profils_tiktok, doublage, locuteurs
    hist = []
    try: hist = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "historique.json"), encoding="utf-8"))
    except (OSError, ValueError): pass
    rel = _release(); deja = stock(rel); manque = stock_voulu() - len(deja)
    journal(f"Pré-écoute : {len(deja)} son(s) déjà prêt(s), {max(0, manque)} à préparer")
    if manque <= 0: return 0
    eviter = " ".join(filter(None, [os.environ.get("EVITER") or ""] + [s["id"] for s in deja]))
    os.environ["EVITER"] = eviter                                          # jamais deux fois le même son dans le stock
    seuil = float(os.environ.get("VOIX_DIFFERENTES") or 0.6); ajoutes, t0 = 0, time.time()
    for url in profils_tiktok.choisir(hist, journal=journal, essais=6 * manque):
        if ajoutes >= manque or time.time() - t0 > 100 * 60: break
        if _id(url) in os.environ["EVITER"].split(): continue
        locuteurs.ETAT["ressemblance"] = None
        try: prep = doublage.preparer(url)
        except Exception as e: journal(f"  son de {url} écarté ({str(e)[:160]})"); continue
        r_ = locuteurs.ETAT.get("ressemblance")
        if r_ is not None and r_ > seuil and seuil < 1:
            journal(f"  voix trop proches dans {url} (ressemblance {r_:.2f}) : écarté (la journée en cherchera un autre)"); continue
        nom = deposer(url, prep, rel); ajoutes += 1
        os.environ["EVITER"] += " " + _id(url)
        journal(f"  ✅ son prêt : {url} ({nom})")
    return ajoutes


if __name__ == "__main__":
    n = remplir()
    print(f"Pré-écoute finie : {n} son(s) ajouté(s) au stock", flush=True)
