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
    try:
        import urllib.parse, urllib.request, reseau
        req = urllib.request.Request("https://www.tikwm.com/api/user/info?" + urllib.parse.urlencode({"unique_id": pseudo}),
                                     headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"})
        d = json.loads(reseau.ouvrir(req, timeout=30) or "{}").get("data") or {}
        bio = str((d.get("user") or {}).get("signature") or "")
    except Exception: pass
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


def _ytdlp(pseudo, n=40):
    import doublage
    url = f"https://www.tiktok.com/@{pseudo}"
    for v in doublage.VARIANTES:
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


def choisir(historique, journal=print, graine=None, essais=4):
    """Liens de vidéos à essayer (jamais déjà utilisées, durée raisonnable), les plus prometteuses d'abord : profils tirés au
    hasard mais pondérés par les vues qu'ils nous rapportent (idée 21), et dans chaque profil les sons qui montent et à bon
    potentiel d'abord (idées 3 et 4), avec un peu de hasard pour varier. On prend la première dont le son passe."""
    profils = liste()
    if not profils: return []
    rng = random.Random(graine); deja = deja_utilisees(historique); out = []
    pw = poids_profils(profils)
    profils = sorted(profils, key=lambda p: -pw[p] * rng.random() ** 0.5)  # tirage pondéré (un bon profil sort plus souvent)
    import saisons, suites
    moment = saisons.mots_du_moment()                                      # Noël, Saint-Valentin, rentrée… : sons sur ce thème d'abord
    profils = [p for p in profils[:8] if not bio_refuse(p, journal)][:5]   # liste noire : bio qui interdit la reprise
    if not profils: return []
    listes = {p: videos(p, journal) for p in profils}
    import time as _t
    vus = {}                                                               # tendance TikTok : hashtag récent chez plusieurs créateurs
    for p, vs_ in listes.items():
        for v in vs_:
            if not v.get("date") or _t.time() - float(v["date"]) < 10 * 86400:
                for h in _hashtags(v.get("titre")): vus.setdefault(h, set()).add(p)
    communs = {h for h, ps in vus.items() if len(ps) >= 2}
    sujets = sujets_du_moment()
    if communs or sujets: journal(f"Tendances : {', '.join('#' + h for h in sorted(communs)[:8]) or 'aucun hashtag commun'} ; sujets qui montent en France : {', '.join(sujets[:6]) or '—'}")
    parties = suites.faites(historique)                                     # parties déjà faites (la suite passe devant)
    for p in profils:
        vs = [v for v in listes[p] if v["id"] not in deja and (v.get("duree") is None or DUREE_MIN <= float(v["duree"]) <= DUREE_MAX)]
        for v in vs:
            v["potentiel"] = potentiel(v)
            if moment and re.search(moment, str(v.get("titre") or "").lower()):
                v["potentiel"] += 30; journal(f"  son du moment (calendrier) : {v['url']} « {str(v.get('titre'))[:60]} »")
            b_, pourquoi = tendance(v, communs, sujets)
            if b_: v["potentiel"] += b_; journal(f"  son dans la tendance ({pourquoi}) : {v['url']}")
            try:
                b_ = __import__("recette").bonus_son(v)                     # idée 41 : la durée qui marche chez nous
                if b_: v["potentiel"] += b_
            except Exception: pass
            b_ = suites.bonus(v, p, parties)
            if b_: v["potentiel"] += b_; journal(f"  suite d'une vidéo déjà faite (partie {suites.num_partie(v.get('titre'))}) : {v['url']}")
        vs.sort(key=lambda v: -(v["potentiel"] + rng.uniform(0, 25)))
        journal(f"Profil TikTok @{p} (poids {pw[p]:.1f}) : {len(vs)} vidéo(s) jamais utilisée(s)" + (f", meilleur potentiel {vs[0]['potentiel']}/100" if vs else ""))
        out += [v["url"] for v in vs[:max(2, essais // len(profils))]]
        if len(out) >= essais: break
    return out[:essais]
