"""Profils TikTok de l'auteur : une réserve de sons pour les vidéos automatiques.

Filière « Sons TikTok », totalement à part des sketchs du robot (onglet 🎵 TikTok du site) : l'auteur colle une liste de profils
(@pseudo ou lien du profil, un par ligne : PROFILS_TIKTOK) et règle son propre planning (HEURE_TIKTOK, FREQUENCE_TIKTOK). À chaque
créneau, le robot prend une vidéo au hasard d'un profil, jamais déjà utilisée, d'une durée raisonnable ; il reprend son audio et
fabrique la vidéo autour, exactement comme avec un lien collé à la main.

Liste des vidéos d'un profil : yt-dlp (en imitant un navigateur, puis par l'API de l'appli) ; sinon le service public tikwm.com.
Si aucun profil ne répond ou qu'aucun son ne passe : pas de vidéo cette fois (jamais de sketch à la place), nouvel essai au réveil suivant."""
import json, os, random, re, subprocess, sys

DUREE_MIN, DUREE_MAX = 8, 150                                              # secondes : assez de dialogue, pas un film entier


RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NOTRE_CHAINE = {"petitsdramas", "petits.dramas"}


def connus():
    """Profils déjà connus du robot : les comptes des vidéos TikTok dont il a déjà repris le son (historique et sketchs gardés),
    du plus utilisé au moins utilisé. Jamais notre propre chaîne. Sert de liste de départ tant que l'auteur n'a pas la sienne."""
    import glob
    nous = NOTRE_CHAINE | {(os.environ.get("TIKTOK_COMPTE") or "").strip().lstrip("@").lower()}
    textes = []
    try: textes.append(open(os.path.join(RACINE, "episodes", "historique.json"), encoding="utf-8").read())
    except OSError: pass
    for f in glob.glob(os.path.join(RACINE, "episodes", "sketchs", "*.json")):
        try: textes.append(open(f, encoding="utf-8").read())
        except OSError: pass
    compte = {}
    for tx in textes:
        for m in set(re.findall(r"tiktok\.com/@([\w.\-]+)/video/", tx)):
            if m.lower() not in nous: compte[m] = compte.get(m, 0) + 1
    return sorted(compte, key=lambda m: (-compte[m], m.lower()))


def interdits():
    """Liste noire (choix de l'auteur du 6 novembre, idée 27) : profils jamais repris (réglage PROFILS_INTERDITS, même format que
    PROFILS_TIKTOK), plus les profils dont la bio interdit la reprise (« ne pas reprendre », « no repost », « tous droits réservés »…)."""
    return {p.lower() for p in liste(os.environ.get("PROFILS_INTERDITS") or "")} | {p.lower() for p, v in _BIOS.items() if v}


_BIOS = {}                                                                 # pseudo -> la bio interdit la reprise (lu une fois par fabrication)
BIO_REFUS = re.compile(r"(ne\s+pas|pas\s+de|interdi\w*\s+de|merci\s+de\s+ne\s+pas|no|don'?t|do\s+not)\s+(re-?)?(prendre|poster|post|repost|"
                       r"reupload|re-?upload|utiliser|copier|use|steal|voler)\b|tous\s+droits\s+r[ée]serv|all\s+rights\s+reserved|\bno\s+repost",
                       re.I)


def bio_refuse(pseudo, journal=print):
    """La bio du profil interdit-elle la reprise ? (tikwm ; profil illisible = autorisé, comme avant)."""
    p = pseudo.lower()
    if p in _BIOS: return _BIOS[p]
    bio = ""
    if _BIOS.get(" tikwm refuse"): return False                          # tikwm refuse les robots (403) : on ne redemande pas
    try:
        import urllib.parse, urllib.request, reseau
        req = urllib.request.Request("https://www.tikwm.com/api/user/info?" + urllib.parse.urlencode({"unique_id": pseudo}),
                                     headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"})
        d = json.loads(reseau.ouvrir(req, timeout=30) or "{}").get("data") or {}
        bio = str((d.get("user") or {}).get("signature") or "")
    except Exception as _e:
        if "403" in str(_e): _BIOS[" tikwm refuse"] = True                 # refus connu du service (pas une panne du robot)
        else: __import__("pannes").avale(_e)
    _BIOS[p] = bool(BIO_REFUS.search(bio))
    if _BIOS[p]: journal(f"  profil @{pseudo} écarté : sa bio interdit la reprise (« {bio[:80]} »)")
    return _BIOS[p]


def liste(texte=None):
    """Pseudos (sans @) tirés du réglage PROFILS_TIKTOK : « @pseudo », « pseudo » ou lien https://www.tiktok.com/@pseudo…
    Réglage vide : les profils déjà connus du robot (voir connus()). Les profils de la liste noire sont retirés."""
    t = os.environ.get("PROFILS_TIKTOK", "") if texte is None else texte
    if texte is None:
        noirs = interdits()
        return [p for p in (connus() if not (t or "").strip() else liste(t)) if p.lower() not in noirs]
    out = []
    for morceau in re.split(r"[\n,;]+", t or ""):
        m = morceau.strip()
        if not m: continue
        r = re.search(r"tiktok\.com/@([\w.\-]+)", m) or re.match(r"^@?([\w.\-]{2,40})$", m)
        if r and r.group(1).lower() not in [x.lower() for x in out]: out.append(r.group(1))
    return out


def deja_utilisees(historique):
    """Identifiants des vidéos TikTok déjà reprises (sources de l'historique)."""
    ids = set()
    for h in historique:
        for s in (h.get("sources") or []) + [h.get("source_audio") or ""]:
            m = re.search(r"/video/(\d+)", str(s))
            if m: ids.add(m.group(1))
    ids.update(x for x in (os.environ.get("EVITER") or "").replace(",", " ").split() if x.isdigit())   # chaîne : sons des vidéos encore en fabrication
    return ids


VARIANTES = (["--impersonate", "chrome"], ["--extractor-args", "tiktok:api_hostname=api16-normal-c-useast1a.tiktokv.com"], [])


def _ytdlp(pseudo, n=40):
    # (pas « import doublage » : il demande numpy, absent de la machine des statistiques -> la veille des profils échouait
    # avant même d'interroger TikTok et déclarait tous les profils « introuvables », 17-21 novembre 2026)
    url = f"https://www.tiktok.com/@{pseudo}"
    for v in VARIANTES:
        try:
            r = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "--no-warnings", "--socket-timeout", "30", *v,
                                "--playlist-end", str(n), "-J", url], capture_output=True, text=True, timeout=180)
        except Exception: continue
        if r.returncode != 0 or not r.stdout.strip(): continue
        try: d = json.loads(r.stdout)
        except ValueError: continue
        out = []
        for e in d.get("entries") or []:
            vid = str(e.get("id") or ""); lien = e.get("url") or e.get("webpage_url") or ""
            if not vid and lien: vid = (re.search(r"/video/(\d+)", lien) or [None, ""])[1]
            if vid: out.append(dict(id=vid, url=f"https://www.tiktok.com/@{pseudo}/video/{vid}", duree=e.get("duration"),
                                    vues=e.get("view_count"), date=e.get("timestamp") or e.get("release_timestamp"),
                                    titre=str(e.get("title") or e.get("description") or "")[:300]))
        if out: return out
    return []


def _tikwm(pseudo, n=35):
    import urllib.parse, urllib.request, reseau
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
    req = urllib.request.Request("https://www.tikwm.com/api/user/posts?" + urllib.parse.urlencode({"unique_id": pseudo, "count": n, "cursor": 0}), headers=ua)
    d = (json.loads(reseau.ouvrir(req, timeout=60)) or {}).get("data") or {}
    return [dict(id=str(v.get("video_id")), url=f"https://www.tiktok.com/@{pseudo}/video/{v.get('video_id')}", duree=v.get("duration"),
                 vues=v.get("play_count"), date=v.get("create_time"), titre=str(v.get("title") or "")[:300]) for v in d.get("videos") or [] if v.get("video_id")]


def videos(pseudo, journal=print):
    """Vidéos récentes d'un profil : [{id, url, duree}] (vide si le profil ne répond pas)."""
    try:
        v = _ytdlp(pseudo)
        if v: return v
    except Exception as e: journal(f"  profil @{pseudo} : yt-dlp en échec ({str(e)[:100]})")
    try:
        v = _tikwm(pseudo)
        if v: journal(f"  profil @{pseudo} : liste obtenue par tikwm")
        return v
    except Exception as e: journal(f"  profil @{pseudo} : liste impossible ({str(e)[:100]})")
    return []


def vitesse(v, maintenant=None):
    """Sons qui montent (idée 4) : vues par jour depuis la mise en ligne (une vidéo récente qui démarre fort passe devant)."""
    import time
    if not v.get("vues"): return 0.0
    age = max(0.5, ((maintenant or time.time()) - float(v.get("date") or 0)) / 86400) if v.get("date") else 30.0
    return float(v["vues"]) / age ** 0.8


def potentiel(v, maintenant=None):
    """Note de potentiel d'un son AVANT de le fabriquer (idée 3), de 0 à 100 : vitesse des vues (sons qui montent) et durée
    idéale pour TikTok (20 à 70 s). Après l'écoute, principal.py ajoute ce que dit le son (voix bien différentes, échanges)."""
    import math
    d = float(v.get("duree") or 40)
    duree = 1.0 if 20 <= d <= 70 else 0.6 if 12 <= d <= 100 else 0.3
    vi = vitesse(v, maintenant); el = min(1.0, math.log10(1 + vi) / 5) if vi else 0.35   # 100 000 vues/jour = au maximum
    return round(100 * (0.65 * el + 0.35 * duree))


def poids_profils(profils, stats=None):
    """Profils classés par vues (idée 21) : un profil dont les vidéos reprises font des vues chez nous est tiré plus souvent.
    Poids = moyenne de nos vues sur ses sons / moyenne générale (borné 0,4 à 3) ; profil jamais repris = 1."""
    if stats is None:
        try: stats = json.load(open(os.path.join(RACINE, "episodes", "stats.json"), encoding="utf-8"))
        except (OSError, ValueError): stats = {}
    vids = [v for v in stats.get("videos") or [] if v.get("vues") is not None]
    if not vids: return {p: 1.0 for p in profils}
    moy = sum(v["vues"] for v in vids) / len(vids) or 1
    out = {}
    for p in profils:
        m = [v["vues"] for v in vids if re.search(r"@" + re.escape(p) + r"\b", str(v.get("description") or ""), re.I)]
        out[p] = max(0.4, min(3.0, (sum(m) / len(m)) / moy)) if m else 1.0
    return out


GENERIQUES = {"fyp", "foryou", "foryoupage", "pourtoi", "pourtoii", "viral", "fy", "fypシ", "humour", "drole", "humor", "tiktok", "trend",
              "france", "xyzbca", "explore", "capcut", "funny", "comedy", "pov", "sketch", "pourtoipage", "fypage", "tendance"}


def _hashtags(t): return {h.lower() for h in re.findall(r"#([\wÀ-ÿ]{3,40})", str(t or ""))} - GENERIQUES


def sujets_du_moment():
    """Recherches qui montent en France aujourd'hui (Google Trends, flux public) : idée 23 (le Creative Center de TikTok refuse les
    robots). SONS_TENDANCE=0 pour couper."""
    if os.environ.get("SONS_TENDANCE", "1") == "0": return []
    try:
        import urllib.request, reseau, html
        req = urllib.request.Request("https://trends.google.com/trending/rss?geo=FR", headers={"User-Agent": "Mozilla/5.0"})
        x = reseau.ouvrir(req, timeout=20)
        x = x.decode("utf-8", "ignore") if isinstance(x, bytes) else str(x)
        return [html.unescape(t).strip().lower() for t in re.findall(r"<item>\s*<title>([^<]{3,60})</title>", x)][:30]
    except Exception: return []


def tendance(v, communs, sujets):
    """Points de potentiel en plus pour un son dans l'air du temps : hashtag repris par plusieurs de nos créateurs cette semaine
    (une tendance TikTok qui démarre) ou sujet qui monte en France (Google Trends)."""
    if os.environ.get("SONS_TENDANCE", "1") == "0": return 0, ""
    t = str(v.get("titre") or "").lower(); h = _hashtags(t) & communs
    if h: return 20, "#" + sorted(h)[0]
    s = next((x for x in sujets if len(x) >= 4 and re.search(r"(?<!\w)" + re.escape(x) + r"(?!\w)", t)), None)
    return (15, s) if s else (0, "")


def noter(listes, historique, journal=print):
    """Note de chaque son jamais utilisé des profils (listes = {profil: vidéos}) : potentiel (vues, sons qui montent), calendrier,
    tendances, durée et sujets qui marchent chez nous, suite d'une vidéo déjà faite ; sons déjà repris par une chaîne concurrente
    écartés. Renvoie {profil: [vidéos avec "potentiel"]}. Sert au tirage (choisir) et à l'éclaireur (eclairer)."""
    import time as _t
    import saisons, suites
    deja = deja_utilisees(historique)
    moment = saisons.mots_du_moment()                                      # Noël, Saint-Valentin, rentrée… : sons sur ce thème d'abord
    vus = {}                                                               # tendance TikTok : hashtag récent chez plusieurs créateurs
    for p, vs_ in listes.items():
        for v in vs_:
            if not v.get("date") or _t.time() - float(v["date"]) < 10 * 86400:
                for h in _hashtags(v.get("titre")): vus.setdefault(h, set()).add(p)
    communs = {h for h, ps in vus.items() if len(ps) >= 2}
    sujets = sujets_du_moment()
    if communs or sujets: journal(f"Tendances : {', '.join('#' + h for h in sorted(communs)[:8]) or 'aucun hashtag commun'} ; sujets qui montent en France : {', '.join(sujets[:6]) or '—'}")
    parties = suites.faites(historique)                                     # parties déjà faites (la suite passe devant)
    pris = deja_repris(journal)                                            # sons déjà doublés par les chaînes concurrentes (idée 24)
    out = {}
    for p, vs0 in listes.items():
        vs = [v for v in vs0 if v["id"] not in deja and (v.get("duree") is None or DUREE_MIN <= float(v["duree"]) <= DUREE_MAX)]
        avant_ = len(vs); vs = [v for v in vs if not repris_ailleurs(v, p, pris)]
        if len(vs) < avant_: journal(f"  @{p} : {avant_ - len(vs)} son(s) déjà repris par une chaîne concurrente, écarté(s)")
        for v in vs:
            v["potentiel"] = potentiel(v)
            if moment and re.search(moment, str(v.get("titre") or "").lower()):
                v["potentiel"] += 30; journal(f"  son du moment (calendrier) : {v['url']} « {str(v.get('titre'))[:60]} »")
            b_, pourquoi = tendance(v, communs, sujets)
            if b_: v["potentiel"] += b_; journal(f"  son dans la tendance ({pourquoi}) : {v['url']}")
            try:
                b_ = __import__("recette").bonus_son(v)                     # idée 41 : la durée qui marche chez nous
                if b_: v["potentiel"] += b_
            except Exception as _e: __import__("pannes").avale(_e)
            try:
                b_, mots_ = __import__("recette").bonus_sujet(v)           # idée 18 : les sujets qui marchent chez nous
                if b_: v["potentiel"] += b_; journal(f"  sujet {'qui marche' if b_ > 0 else 'qui marche moins'} chez nous ({', '.join(mots_[:4])}, {b_:+d}) : {v['url']}")
            except Exception as _e: __import__("pannes").avale(_e)
            b_ = suites.bonus(v, p, parties)
            if b_: v["potentiel"] += b_; journal(f"  suite d'une vidéo déjà faite (partie {suites.num_partie(v.get('titre'))}) : {v['url']}")
        out[p] = vs
    return out


# Robot « éclaireur » (choix de l'auteur du 22 novembre 2026) : toutes les 3 heures (garde.yml -> eclaireur.yml), une petite machine
# passe en revue TOUS les créateurs suivis (sans rien écouter), note leurs sons jamais utilisés et range le classement dans
# episodes/sons_candidats.json. La réserve de sons et les fabrications piochent dedans (choisir) : plus besoin de relire 5 profils à
# chaque vidéo. Classement de plus de 8 heures, éclaireur coupé (ECLAIREUR=0) ou trop peu de sons -> lecture des profils en direct.
CANDIDATS = os.path.join(RACINE, "episodes", "sons_candidats.json")
FRAIS_H = 8


def eclairer(historique, journal=print, max_profils=20):
    profils = [p for p in liste()[:max_profils] if not bio_refuse(p, journal)]
    listes = {}
    for p in profils:
        vs = videos(p, journal)
        if vs: listes[p] = vs
    notes = noter(listes, historique, journal)
    sons = [{"url": v["url"], "id": v["id"], "profil": p, "potentiel": int(v["potentiel"]), "titre": str(v.get("titre") or "")[:120],
             "duree": v.get("duree"), "date": v.get("date"), "vues": v.get("vues")} for p, vs in notes.items() for v in vs]
    sons.sort(key=lambda x: -x["potentiel"])
    import time as _t
    journal(f"Éclaireur : {len(listes)}/{len(profils)} créateur(s) lus, {len(sons)} son(s) jamais utilisé(s) classé(s)")
    return {"date": int(_t.time()), "profils_lus": len(listes), "sons": sons[:300]}


def candidats_frais():
    """Classement de l'éclaireur s'il est récent (sinon None)."""
    import time as _t
    if os.environ.get("ECLAIREUR", "1") == "0": return None
    try: c = json.load(open(CANDIDATS, encoding="utf-8"))
    except (OSError, ValueError): return None
    if not isinstance(c, dict) or _t.time() - float(c.get("date") or 0) > FRAIS_H * 3600: return None
    return c


def choisir(historique, journal=print, graine=None, essais=4):
    """Liens de vidéos à essayer (jamais déjà utilisées, durée raisonnable), les plus prometteuses d'abord : profils tirés au
    hasard mais pondérés par les vues qu'ils nous rapportent (idée 21), et dans chaque profil les sons qui montent et à bon
    potentiel d'abord (idées 3 et 4), avec un peu de hasard pour varier. On prend la première dont le son passe. Classement de
    l'éclaireur d'abord (s'il est récent), sinon lecture des profils en direct."""
    profils = liste()
    if not profils: return []
    rng = random.Random(graine); deja = deja_utilisees(historique)
    pw = poids_profils(profils)
    profils = sorted(profils, key=lambda p: -pw[p] * rng.random() ** 0.5)  # tirage pondéré (un bon profil sort plus souvent)
    c = candidats_frais()
    if c:
        suivis = {p.lower() for p in profils}; bannis = interdits()
        par = {}
        for x in c.get("sons") or []:
            p = str(x.get("profil") or "")
            if p.lower() in suivis and p.lower() not in bannis and x.get("id") not in deja and x.get("url"):
                par.setdefault(p.lower(), []).append(x)
        ordre = [p for p in profils if p.lower() in par][:5]
        out = []
        for p in ordre:
            vs = sorted(par[p.lower()], key=lambda x: -(float(x.get("potentiel") or 0) + rng.uniform(0, 25)))
            out += [x["url"] for x in vs[:max(2, essais // len(ordre))]]
            if len(out) >= essais: break
        if len(out) >= min(essais, 2):
            import time as _t
            journal(f"Éclaireur : {len(out)} son(s) pris dans le classement d'il y a {int((_t.time() - float(c['date'])) // 60)} min "
                    f"({len(ordre)} créateur(s))")
            return out[:essais]
        journal("Éclaireur : trop peu de sons dans le classement : lecture des profils en direct")
    profils = [p for p in profils[:8] if not bio_refuse(p, journal)][:5]   # liste noire : bio qui interdit la reprise
    if not profils: return []
    notes = noter({p: videos(p, journal) for p in profils}, historique, journal)
    out = []
    for p in profils:
        vs = notes.get(p) or []
        vs.sort(key=lambda v: -(v["potentiel"] + rng.uniform(0, 25)))
        journal(f"Profil TikTok @{p} (poids {pw[p]:.1f}) : {len(vs)} vidéo(s) jamais utilisée(s)" + (f", meilleur potentiel {vs[0]['potentiel']}/100" if vs else ""))
        out += [v["url"] for v in vs[:max(2, essais // len(profils))]]
        if len(out) >= essais: break
    return out[:essais]


# Sons déjà repris ailleurs (choix de l'auteur du 21 novembre 2026, idée 24). TikTok ne donne pas aux robots la liste des vidéos qui
# utilisent un son ; on lit donc les vidéos récentes des chaînes qui font comme nous (réglage CHAINES_CONCURRENTES, une par ligne),
# comme on lit nos créateurs : un son dont elles citent le lien, ou le créateur avec un titre qui ressemble au sien, est écarté.
def concurrentes(texte=None):
    t = os.environ.get("CHAINES_CONCURRENTES", "") if texte is None else texte
    return [p for p in liste(t) if p.lower() not in {x.lower() for x in NOTRE_CHAINE}][:6] if t.strip() else []


def deja_repris(journal=print):
    """{"ids": ids de vidéos d'origine citées, "titres": [(créateur cité, mots du titre)]} d'après les chaînes concurrentes."""
    ids, titres = set(), []
    for c in concurrentes():
        for v in videos(c, journal=lambda m: None)[:40]:
            t = str(v.get("titre") or "")
            ids |= set(re.findall(r"/video/(\d{8,})", t))
            for m in re.findall(r"(?<![\w.])@([\w.\-]{3,30})", t):
                titres.append((m.lower().rstrip("."), _mots_titre(t)))
    if ids or titres: journal(f"Chaînes concurrentes : {len(ids)} lien(s) et {len(titres)} mention(s) de créateurs relevés")
    return {"ids": ids, "titres": titres}


def _mots_titre(t):
    t = re.sub(r"[@#][\w.\-]+|https?://\S+", " ", str(t or "").lower())
    return {w for w in re.findall(r"[a-zà-ÿ]{4,}", t)}


def repris_ailleurs(v, createur, pris):
    """Ce son a-t-il déjà été repris par une chaîne concurrente ? (lien cité, ou créateur cité + titre qui ressemble à 50 %)"""
    if not pris: return False
    if str(v.get("id")) in pris.get("ids", set()): return True
    mots = _mots_titre(v.get("titre"))
    if len(mots) < 3: return False
    for c, m in pris.get("titres", []):
        if c == str(createur).lower() and len(mots & m) >= 0.5 * len(mots): return True
    return False


ETAT = os.path.join(RACINE, "episodes", "profils_etat.json")


def surveiller(journal=print, maintenant=None, lister=None):
    """Créateurs disparus ou inactifs (choix de l'auteur du 15 novembre 2026, idée 8), une fois par jour (après les statistiques) :
    pour chaque profil de la liste, introuvable (supprimé, privé, ou bloqué) deux jours de suite = « introuvable » ; dernière
    vidéo il y a plus de 30 jours = « inactif ». episodes/profils_etat.json (site : « Mes profils TikTok ») ; alerte téléphone pour
    chaque NOUVEAU profil en difficulté. PROFILS_VEILLE=0 pour couper. Renvoie l'état."""
    import datetime, time as _t
    if os.environ.get("PROFILS_VEILLE", "1") == "0": return None
    maintenant = maintenant or _t.time()
    try: E = json.load(open(ETAT, encoding="utf-8"))
    except (OSError, ValueError): E = {}
    jour = datetime.date.fromtimestamp(maintenant).isoformat()
    if E.get("date") == jour: return E                                     # déjà fait aujourd'hui
    anciens = E.get("profils") or {}; nouveaux = {}; alertes = []
    ps = liste(); res = {p: (lister or videos)(p, journal=lambda m: None) for p in ps}
    if len(ps) >= 3 and not any(res.values()):                             # TOUS introuvables d'un coup = c'est notre outil (ou
        journal(f"Veille des profils : aucun des {len(ps)} profils n'a répondu : panne de lecture, rien n'est compté")   # TikTok) qui
        E = dict(E, date=jour)                                             # ne répond pas, pas les créateurs (faux « introuvables »)
        os.makedirs(os.path.dirname(ETAT), exist_ok=True); json.dump(E, open(ETAT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return E
    for p in ps:
        vs = res[p]
        a = dict(anciens.get(p) or {})
        if not vs:
            a["echecs"] = int(a.get("echecs") or 0) + 1
            etat = "introuvable" if a["echecs"] >= 2 else (a.get("etat") or "ok")
        else:
            a["echecs"] = 0
            dates = [float(v["date"]) for v in vs if v.get("date")]
            jours = int((maintenant - max(dates)) / 86400) if dates else None
            a["jours"] = jours; etat = "inactif" if jours is not None and jours > 30 else "ok"
        if etat != "ok" and (anciens.get(p) or {}).get("etat") != etat: alertes.append((p, etat, a.get("jours")))
        a["etat"] = etat; nouveaux[p] = a
    E = {"date": jour, "profils": nouveaux}
    os.makedirs(os.path.dirname(ETAT), exist_ok=True)
    json.dump(E, open(ETAT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for p, etat, j in alertes:
        m = f"@{p} est introuvable (compte supprimé, privé ou bloqué)" if etat == "introuvable" else f"@{p} n'a rien publié depuis {j} jours"
        journal("Profil en difficulté : " + m)
        try: __import__("alerte").alerter("🎵 Profil TikTok à revoir", m + " : retirez-le de « Mes profils » si besoin.")
        except Exception as _e: __import__("pannes").avale(_e)
    journal(f"Veille des profils : {sum(1 for a in nouveaux.values() if a['etat'] == 'ok')}/{len(nouveaux)} en forme")
    return E


if __name__ == "__main__":
    if "--eclairer" in sys.argv:                                           # robot « éclaireur » (eclaireur.yml)
        try: hist = json.load(open(os.path.join(RACINE, "episodes", "historique.json"), encoding="utf-8"))
        except (OSError, ValueError): hist = []
        r = eclairer(hist)
        if r["sons"] or r["profils_lus"]:
            json.dump(r, open(CANDIDATS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"Éclaireur : classement enregistré ({len(r['sons'])} sons)")
        else: print("Éclaireur : aucun créateur n'a répondu : l'ancien classement est gardé")
