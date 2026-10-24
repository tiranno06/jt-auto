"""Profils TikTok de l'auteur : une réserve de sons pour les vidéos automatiques.

Sur le site (Réglages), l'auteur colle une liste de profils TikTok (@pseudo ou lien du profil, un par ligne) et choisit la part
des vidéos automatiques faites à partir de ces profils (PART_PROFILS : 0, 25, 50, 75 ou 100 %). À chaque vidéo automatique, le
robot tire au sort : soit une idée de sketch comme avant, soit une vidéo au hasard d'un profil de la liste, jamais déjà utilisée,
d'une durée raisonnable ; il reprend alors son audio et fabrique la vidéo autour, exactement comme avec un lien collé à la main.

Liste des vidéos d'un profil : yt-dlp (en imitant un navigateur, puis par l'API de l'appli) ; sinon le service public tikwm.com.
Si aucun profil ne répond, ou si le son ne passe pas, le robot revient aux idées automatiques : la vidéo sort quand même."""
import json, os, random, re, subprocess, sys

DUREE_MIN, DUREE_MAX = 8, 150                                              # secondes : assez de dialogue, pas un film entier


def liste(texte=None):
    """Pseudos (sans @) tirés du réglage PROFILS_TIKTOK : « @pseudo », « pseudo » ou lien https://www.tiktok.com/@pseudo…"""
    t = os.environ.get("PROFILS_TIKTOK", "") if texte is None else texte
    out = []
    for morceau in re.split(r"[\n,;]+", t or ""):
        m = morceau.strip()
        if not m: continue
        r = re.search(r"tiktok\.com/@([\w.\-]+)", m) or re.match(r"^@?([\w.\-]{2,40})$", m)
        if r and r.group(1).lower() not in [x.lower() for x in out]: out.append(r.group(1))
    return out


def part():
    """Part des vidéos automatiques faites depuis les profils (0 à 1). Par défaut une sur deux quand une liste existe."""
    try: p = float((os.environ.get("PART_PROFILS") or "50").strip().rstrip("%"))
    except ValueError: p = 50.0
    return max(0.0, min(1.0, p / 100))


def deja_utilisees(historique):
    """Identifiants des vidéos TikTok déjà reprises (sources de l'historique)."""
    ids = set()
    for h in historique:
        for s in (h.get("sources") or []) + [h.get("source_audio") or ""]:
            m = re.search(r"/video/(\d+)", str(s))
            if m: ids.add(m.group(1))
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
            if vid: out.append(dict(id=vid, url=f"https://www.tiktok.com/@{pseudo}/video/{vid}", duree=e.get("duration")))
        if out: return out
    return []


def _tikwm(pseudo, n=35):
    import urllib.parse, urllib.request, reseau
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
    req = urllib.request.Request("https://www.tikwm.com/api/user/posts?" + urllib.parse.urlencode({"unique_id": pseudo, "count": n, "cursor": 0}), headers=ua)
    d = (json.loads(reseau.ouvrir(req, timeout=60)) or {}).get("data") or {}
    return [dict(id=str(v.get("video_id")), url=f"https://www.tiktok.com/@{pseudo}/video/{v.get('video_id')}", duree=v.get("duration"))
            for v in d.get("videos") or [] if v.get("video_id")]


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


def choisir(historique, journal=print, graine=None, essais=4):
    """Liens de vidéos à essayer (au hasard, jamais déjà utilisées, durée raisonnable), dans l'ordre : on prend la première
    dont le son passe. Liste vide si aucun profil n'est réglé ou ne répond."""
    profils = liste()
    if not profils: return []
    rng = random.Random(graine); rng.shuffle(profils); deja = deja_utilisees(historique); out = []
    for p in profils[:6]:
        vs = [v for v in videos(p, journal) if v["id"] not in deja and (v.get("duree") is None or DUREE_MIN <= float(v["duree"]) <= DUREE_MAX)]
        journal(f"Profil TikTok @{p} : {len(vs)} vidéo(s) jamais utilisée(s)")
        rng.shuffle(vs); out += [v["url"] for v in vs[:max(2, essais // len(profils))]]
        if len(out) >= essais: break
    return out[:essais]


def tirage(auto, theme="", lot=False, graine=None):
    """Cette vidéo automatique vient-elle d'un profil ? (seulement les vidéos du planning, jamais une demande manuelle)"""
    if not auto or theme or lot or not liste(): return False
    return random.Random(graine).random() < part()
