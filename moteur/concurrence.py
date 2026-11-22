"""Recherche de chaînes concurrentes (demande de l'auteur du 21 novembre 2026) : des chaînes qui font la MÊME chose que nous (sons et
dialogues TikTok repris, refaits en dessin animé), pour que le robot évite les sons qu'elles ont déjà repris (CHAINES_CONCURRENTES,
profils_tiktok.repris_ailleurs) et pour comparer.

Candidats (pas de recherche par mot-clé possible : TikTok la refuse aux robots) : les comptes cités « @… » dans les titres de nos
créateurs, des chaînes concurrentes déjà connues (de proche en proche) et des vidéos d'origine déjà reprises. TRIPLE VÉRIFICATION :
1. le TEXTE : ses titres créditent d'autres créateurs (« son original », 🎧, « voix », @…), dont de préférence NOS créateurs ;
2. le FORMAT : au moins 6 vidéos de 8 à 150 s, publié ces 30 derniers jours, des vues (médiane ≥ 1 000) ;
3. l'IMAGE : Gemini regarde une image d'une de ses vidéos : dessin animé / animation qui met en scène un dialogue, comme nos vidéos
   (sans Gemini : « image non vérifiée », jamais proposé en tête).
Puis COMPARAISON avec notre chaîne et les concurrentes actuelles : créateurs repris en commun et hashtags en commun -> note de
ressemblance (0-100). Résultat : episodes/concurrentes_proposees.json, montré sur le site (« 🥊 Chaînes concurrentes » : ➕ / 🚫).
CONCURRENCE=0 pour couper."""
import datetime, json, os, re, statistics, subprocess, sys, tempfile, time

ICI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ICI)
FICHIER = os.path.join(ICI, "..", "episodes", "concurrentes_proposees.json")
VUES_MIN = 1000
CREDIT = re.compile(r"son original|🎧|\bvoix\b|doubl|\bdub\b|\bcr[ée]dit|\bvia @|\bsound\b|\baudio\b|original sound", re.I)


def _mentions(t):
    """Pseudos cités « @… » : jamais un nom coupé par TikTok (« @AGUE… ») ni un nom affiché suivi d'un emoji (« @Chou✨ »)."""
    out = set()
    for m in re.finditer(r"(?<![\w.])@([\w.\-]{3,30})(\S?)", str(t or "")):
        nom, apres = m.group(1), m.group(2)
        if nom.endswith("..") or apres in ("…",) or (apres and not apres.isspace() and not re.match(r"[\s,;:!?)\]]", apres)): continue
        out.add(nom.lower().rstrip("."))
    return out


def texte(videos, nos_createurs):
    """Vérification 1 (le texte) -> (ok, détail, créateurs cités en commun)."""
    titres = [str(v.get("titre") or "") for v in videos]
    if not titres: return False, "aucun titre", set()
    credites = sum(1 for t in titres if CREDIT.search(t) or _mentions(t))
    communs = set().union(*[_mentions(t) for t in titres]) & nos_createurs
    ok = credites >= max(2, 0.25 * len(titres)) or len(communs) >= 2
    return ok, f"{credites}/{len(titres)} titres créditent un son ou un créateur, {len(communs)} de nos créateurs repris", communs


def format_(videos):
    """Vérification 2 (le format) -> (ok, détail, médiane des vues)."""
    import profils_tiktok as P
    vs = [v for v in videos if v.get("duree") is None or P.DUREE_MIN <= float(v["duree"]) <= P.DUREE_MAX]
    recentes = [v for v in vs if v.get("date") and time.time() - float(v["date"]) < 30 * 86400]
    vues = [int(v["vues"]) for v in vs if v.get("vues") is not None]
    med = int(statistics.median(vues)) if vues else 0
    ok = len(vs) >= 6 and bool(recentes) and med >= VUES_MIN
    return ok, f"{len(vs)} vidéos courtes, {len(recentes)} ce mois-ci, {med} vues (médiane)", med


QUESTION = """Voici une image tirée d'une vidéo TikTok. Notre chaîne reprend le son de sketchs / dialogues TikTok et les refait en DESSIN
ANIMÉ (personnages dessinés qui se parlent, sous-titres). Cette vidéo est-elle du même genre : animation (dessin, 2D, 3D, personnages
animés) qui met en scène un dialogue ou un sketch ? Réponds en JSON : {"anime": true/false, "dialogue": true/false, "raison": "..."}"""


def image(video_url, regarder=None):
    """Vérification 3 (l'image) -> (True / False / None si impossible, détail)."""
    if not video_url: return None, "pas de vidéo"
    d = tempfile.mkdtemp(); f = os.path.join(d, "v.mp4")
    try:
        subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "--no-warnings", "-f", "worst[ext=mp4]/worst", "--max-filesize", "40M",
                        "-o", f, video_url], capture_output=True, timeout=180)
        if not os.path.exists(f): return None, "vidéo illisible"
        import cv2
        cap = cv2.VideoCapture(f); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(n * 0.4))); ok, im = cap.read(); cap.release()
        if not ok: return None, "image illisible"
        r = (regarder or (lambda ims, q: __import__("fiche_tournage")._gemini_images(ims, q, timeout=60)))([cv2.cvtColor(im, cv2.COLOR_BGR2RGB)], QUESTION)
        if not isinstance(r, dict): return None, "Gemini n'a pas répondu"
        return bool(r.get("anime")) and r.get("dialogue") is not False, str(r.get("raison") or "")[:120]
    except Exception as e: return None, f"image impossible ({str(e)[:60]})"


def _tags(textes):
    return {h.lower() for t in textes for h in re.findall(r"#([\wÀ-ÿ]{3,40})", str(t or ""))}


def ressemblance(communs, tags_cand, tags_nous, n_nos):
    """Comparaison avec notre chaîne (0-100) : créateurs repris en commun (60 %) + hashtags en commun (40 %)."""
    c = min(1.0, len(communs) / max(1, min(4, n_nos)))
    h = len(tags_cand & tags_nous) / max(1, min(len(tags_cand), 12)) if tags_cand else 0.0
    return round(100 * (0.6 * c + 0.4 * min(1.0, h)))


def chercher(journal=print, max_candidats=25, lister=None, regarder=None):
    if os.environ.get("CONCURRENCE", "1") == "0": return []
    import profils_tiktok as P
    lister = lister or (lambda p: P.videos(p, journal=lambda m: None))
    nos_createurs = {p.lower() for p in P.liste()} | {p.lower() for p in P.connus()}
    actuelles = [c.lower() for c in P.concurrentes()]
    exclus = nos_createurs | set(actuelles) | P.interdits() | {x.lower() for x in P.NOTRE_CHAINE}
    exclus.add((os.environ.get("TIKTOK_COMPTE") or "").strip().lstrip("@").lower())
    titres, tags_conc = [], set()
    for p in list(P.liste())[:8] + actuelles:                               # mentions chez nos créateurs ET chez les concurrentes connues
        vs_ = lister(p) or []; titres += [v.get("titre") for v in vs_]
        if p in actuelles: tags_conc |= _tags(v.get("titre") for v in vs_)
    try:
        hist = json.load(open(os.path.join(ICI, "..", "episodes", "historique.json"), encoding="utf-8"))
    except (OSError, ValueError): hist = []
    titres += [h.get("titre_source") for h in hist if h.get("titre_source")]
    tags_nous = _tags(h.get("legende") for h in hist if h.get("filiere") == "tiktok") | tags_conc
    c = {}
    for t in titres:
        for m in _mentions(t):
            if m not in exclus: c[m] = c.get(m, 0) + 1
    cand = sorted(c, key=lambda m: -c[m])[:max_candidats]
    journal(f"Chaînes concurrentes : {len(c)} compte(s) cité(s), {len(cand)} vérifié(s) (texte, format, image)")
    out = []
    for m in cand:
        vs = lister(m)
        if not vs: journal(f"  ✗ @{m} : compte introuvable ou privé (souvent un prénom ou un nom affiché écrit avec @ dans un titre, pas un vrai pseudo)"); continue
        ok1, d1, communs = texte(vs, nos_createurs)
        if not ok1: journal(f"  ✗ @{m} : ne reprend pas de sons ({d1})"); continue
        ok2, d2, med = format_(vs)
        if not ok2: journal(f"  ✗ @{m} : format différent ({d2})"); continue
        meilleure = max(vs, key=lambda v: int(v.get("vues") or 0))
        ok3, d3 = image(meilleure.get("url"), regarder)
        if ok3 is False: journal(f"  ✗ @{m} : pas le même genre à l'image ({d3})"); continue
        note = ressemblance(communs, _tags(v.get("titre") for v in vs), tags_nous, len(nos_createurs))
        out.append({"profil": m, "vues_mediane": med, "ressemblance": note, "createurs_communs": sorted(communs)[:6],
                    "image_verifiee": ok3 is True, "texte": d1, "format": d2, "image": d3, "exemple": meilleure.get("url"),
                    "titre": str(meilleure.get("titre") or "")[:90]})
        journal(f"  ✅ @{m} : ressemblance {note}/100 ({d1} ; {d2} ; image : {d3 if ok3 else 'non vérifiée'})")
    out.sort(key=lambda f: (not f["image_verifiee"], -f["ressemblance"], -f["vues_mediane"]))
    return out[:8]


if __name__ == "__main__":
    r = chercher()
    json.dump({"date": datetime.date.today().isoformat(), "profils": r}, open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Chaînes concurrentes : {len(r)} proposée(s)")
