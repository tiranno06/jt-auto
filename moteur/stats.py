"""Statistiques TikTok récupérées par le robot lui-même (pistes 4 et 15).

collecter() : lit la page publique de la chaîne (compte réglé dans la régie, variable TIKTOK_COMPTE, « petits.dramas » par
défaut) avec yt-dlp — vues, j'aime, commentaires, partages et date de chaque vidéo — sans clé ni connexion, puis rattache
chaque vidéo TikTok à la vidéo fabriquée correspondante (même début de légende) et enregistre episodes/stats.json.
Ensuite :
- pour_auteur() / pour_idees() : ce qui marche et ce qui ne marche pas sur la chaîne, donné à l'auteur (banque de chutes
  qui ont fait des vues, mécaniques à refaire, sujets à éviter) ;
- hashtags_gagnants() : hashtags des vidéos qui font le plus de vues ;
- meilleure_heure() : l'heure de publication qui fait le plus de vues (réglage « Heure : automatique »).
Usage : python moteur/stats.py   (workflow stats.yml, chaque jour)"""
import datetime, json, os, re, subprocess, sys, unicodedata

RACINE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FICHIER = os.path.join(RACINE, "episodes", "stats.json")
HIST = os.path.join(RACINE, "episodes", "historique.json")

def compte():
    return (os.environ.get("TIKTOK_COMPTE") or "").strip().lstrip("@")     # vide tant que le compte n'est pas réglé dans la régie

def _cle(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", re.sub(r"#\w+", " ", t)))[:60]

def lire():
    try: return json.load(open(FICHIER, encoding="utf-8"))
    except (OSError, ValueError): return {}

def _info(v):
    return {"id": str(v.get("id", "")), "url": v.get("webpage_url") or v.get("url") or "", "description": v.get("description") or v.get("title") or "",
            "date": v.get("timestamp"), "vues": v.get("view_count") or 0, "likes": v.get("like_count") or 0,
            "commentaires": v.get("comment_count") or 0, "partages": v.get("repost_count") or 0, "duree": v.get("duration")}

def _videos_ytdlp(nom, limite=60):
    """Liste des vidéos de la chaîne (la page du profil donne souvent déjà les compteurs) ; sinon, vidéo par vidéo."""
    base = [sys.executable, "-m", "yt_dlp", "--ignore-errors", "--no-warnings", "--playlist-end", str(limite)]
    r = subprocess.run(base + ["--flat-playlist", "-J", f"https://www.tiktok.com/@{nom}"], capture_output=True, text=True, timeout=600)
    try: entrees = (json.loads(r.stdout or "{}") or {}).get("entries") or []
    except ValueError: entrees = []
    if entrees: print(f"Stats : {len(entrees)} vidéos listées ; champs : {sorted(entrees[0])[:25]}", flush=True)
    out = [_info(e) for e in entrees]
    manque = [v for v in out if not v["vues"] and v["url"]]
    for v in manque[:limite]:                                              # compteurs absents de la liste : page de la vidéo
        r2 = subprocess.run(base + ["--dump-json", "--skip-download", v["url"]], capture_output=True, text=True, timeout=120)
        try: v.update({k: x for k, x in _info(json.loads(r2.stdout.splitlines()[0])).items() if x})
        except (ValueError, IndexError): pass
    if not out:
        vide = "any videos" in (r.stderr or "") or not (r.stderr or "").strip() or r.stdout.strip() == "null"
        print(f"Stats @{nom} : " + ("aucune vidéo publiée pour l'instant (normal pour un compte neuf)." if vide
                                    else f"lecture impossible ({(r.stderr or '').strip()[-300:]})"), flush=True)
    return out

def collecter():
    nom = compte()
    if not nom: print("Stats : compte TikTok non réglé (régie > Réglages > Statistiques TikTok).", flush=True); return False
    videos = _videos_ytdlp(nom)
    if not videos:
        os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
        json.dump({"maj": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"), "compte": nom, "videos": []},
                  open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return False
    hist = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else []
    par_cle = {}
    for h in hist:
        for src in (h.get("legende_publiee"), h.get("legende")):              # texte réellement publié d'abord
            k = _cle((src or "").split("\n")[0])
            if k: par_cle.setdefault(k[:40], h)
    lies = 0
    for v in videos:
        h = par_cle.get(_cle(v["description"])[:40])
        if h is None:                                                      # légende retouchée à la main : on tente le début
            k = _cle(v["description"])[:20]
            h = next((x for c, x in par_cle.items() if k and c.startswith(k)), None)
        if h is not None:
            v["fichier"] = h.get("fichier"); lies += 1
            h["vues"], h["likes"], h["commentaires"], h["partages"] = v["vues"], v["likes"], v["commentaires"], v["partages"]
            h["url_tiktok"] = v["url"]; h["publie"] = True
    os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
    json.dump({"maj": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"), "compte": nom, "videos": videos},
              open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if hist: json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    total = sum(v["vues"] for v in videos)
    print(f"Stats @{nom} : {len(videos)} vidéos, {total} vues au total, {lies} reliées aux vidéos du robot", flush=True)
    for v in sorted(videos, key=lambda x: -x["vues"])[:5]: print(f"  {v['vues']:>8} vues  {v['description'][:70]}", flush=True)
    return True

def _historique_note():
    hist = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else []
    return [h for h in hist if isinstance(h.get("vues"), int)]

def _bilan(n_top=5, n_flop=3):
    h = _historique_note()
    if len(h) < 3: return [], []
    h = sorted(h, key=lambda x: -x["vues"]); return h[:n_top], h[-n_flop:] if len(h) > n_top else []

def pour_auteur():
    """Banque de ce qui marche : donnée à l'auteur à chaque sketch (vide tant qu'il n'y a pas assez de vidéos publiées)."""
    top, flop = _bilan()
    if not top: return ""
    def ligne(x): return f"  · {x['vues']} vues — « {x.get('titre', '')} » : {(x.get('accroche') or '')[:120]}"
    txt = ("CE QUI MARCHE SUR LA CHAÎNE (vues TikTok réelles, mises à jour chaque jour) :\n" + "\n".join(ligne(x) for x in top) +
           ("\nCE QUI NE MARCHE PAS :\n" + "\n".join(ligne(x) for x in flop) if flop else "") +
           "\nRefais les MÉCANIQUES, les thèmes et le type de chute des vidéos qui marchent (jamais les mêmes blagues) ; évite ce qui fait des flops.")
    tags = hashtags_gagnants()
    if tags: txt += "\nHashtags des vidéos qui marchent (à privilégier s'ils collent au sujet) : " + " ".join("#" + t for t in tags)
    return txt

def pour_idees():
    top, flop = _bilan(4, 2)
    if not top: return ""
    return ("Thèmes qui font des vues sur la chaîne : " + " ; ".join(x.get("titre", "") for x in top) +
            (". Thèmes qui ne marchent pas : " + " ; ".join(x.get("titre", "") for x in flop) if flop else "") + ". Inspire-toi des premiers.")

def hashtags_gagnants(n=6):
    poids = {}
    for v in lire().get("videos", []):
        if not v.get("fichier"): continue                                  # seulement NOS vidéos (reliées à l'historique)
        for t in re.findall(r"#(\w+)", v.get("description", "")): poids[t.lower()] = poids.get(t.lower(), 0) + v.get("vues", 0)
    return [t for t, p in sorted(poids.items(), key=lambda x: -x[1]) if p > 0][:n]

def meilleure_heure(defaut=17):
    """Heure de fabrication (Paris) qui fait sortir la vidéo à l'heure la plus regardée ; défaut tant qu'il y a moins de 8 vidéos."""
    from zoneinfo import ZoneInfo
    vids = [v for v in lire().get("videos", []) if v.get("date") and v.get("fichier")]
    if len(vids) < 8: return defaut
    par_h = {}
    for v in vids:
        h = datetime.datetime.fromtimestamp(v["date"], ZoneInfo("Europe/Paris")).hour; par_h.setdefault(h, []).append(v.get("vues", 0))
    bonnes = {h: sum(x) / len(x) for h, x in par_h.items() if len(x) >= 2}
    if not bonnes: return defaut
    return (max(bonnes, key=bonnes.get) - 1) % 24                         # la fabrication prend environ 30 min

def pseudos_libres(noms):
    """Vérifie si des pseudos TikTok sont déjà pris (une chaîne publique existe à cette adresse)."""
    for n in noms:
        n = n.strip().lstrip("@")
        if not n: continue
        try:
            r = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "-J", "--playlist-end", "3", "--no-warnings", "--socket-timeout", "20",
                                f"https://www.tiktok.com/@{n}"], capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            print(f"Pseudo @{n} : pas de réponse de TikTok (à vérifier à la main)", flush=True); continue
        try: d = json.loads(r.stdout or "{}") or {}
        except ValueError: d = {}
        if d.get("entries"): print(f"Pseudo @{n} : PRIS ({len(d['entries'])}+ vidéos publiques, ex. « {(d['entries'][0].get('description') or '')[:60]} »)")
        elif "doesn't exist" in (r.stderr or "").lower() or "not exist" in (r.stderr or "").lower() or "404" in (r.stderr or ""):
            print(f"Pseudo @{n} : probablement LIBRE (aucune chaîne à cette adresse)")
        else: print(f"Pseudo @{n} : aucune vidéo publique (libre, ou compte sans vidéo) — {(r.stderr or '').strip()[-120:]}")

if __name__ == "__main__":
    if os.environ.get("PSEUDOS"): pseudos_libres(os.environ["PSEUDOS"].split(",")); sys.exit(0)
    ok = collecter()
    print(pour_auteur() or "Pas encore assez de vidéos reliées pour en tirer des leçons.")
    print(f"Meilleure heure de fabrication : {meilleure_heure()} h")
    sys.exit(0)
