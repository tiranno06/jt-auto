"""Description TikTok (demande de l'auteur, 30 octobre 2026) : la description de la vidéo, la question pour les commentaires, la
source du son (« 🎧 Son original : @compte ») SANS aucun lien, puis beaucoup de hashtags liés à la vidéo (sujet, univers, métiers,
émotions) + ceux de la chaîne et de la niche (animation, humour, doublage). Utilisé à la fabrication (principal.py) et juste avant
l'envoi (publier.py) : une ancienne vidéo sans hashtags ou avec un lien est corrigée au moment de la publication."""
import json, os, re, unicodedata

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
NB_HASHTAGS = int(os.environ.get("NB_HASHTAGS") or 15)
CHAINE = ["petitsdramas"]
NICHE = ["humour", "drole", "animation", "dessinanime", "cartoon", "sketch", "doublage", "pourtoi", "fyp", "tiktokfrance", "humourfrancais"]
THEMES = [  # (motif dans le texte, hashtags)
    (r"\b(papa|maman|fiston|ma fille|mon fils|parents?|daron|daronne|famille|mamie|papi|grand-?m[eè]re|grand-?p[eè]re)\b", ["famille", "parents", "parentsvsenfants"]),
    (r"\b(fr[eè]re|s[oœ]eur|frangin|frangine)\b", ["freresoeur", "famille"]),
    (r"\b(prof|lyc[ée]e|coll[eè]ge|[ée]cole|note|interro|devoirs?|bac|brevet|classe|cours)\b", ["ecole", "lycee", "eleves", "prof"]),
    (r"\b(ch[ée]rie?|mon amour|b[ée]b[ée]|copine|copain|mari|femme|couple|rendez-vous|date|ex)\b", ["couple", "amour", "relation"]),
    (r"\b(patron|boss|bureau|coll[eè]gue|travail|boulot|r[ée]union|salaire|stage|entretien)\b", ["travail", "bureau", "viedebureau"]),
    (r"\b(pote|pot[eo]s|fr[ée]ro|ami|amie|meilleur ami|bff|bande)\b", ["amitie", "potes", "bff"]),
    (r"\b(voisins?|immeuble|palier)\b", ["voisins"]),
    (r"\b(t[ée]l[ée]phone|portable|appel|insta|snap|tiktok|r[ée]seaux|message|texto)\b", ["telephone", "reseauxsociaux"]),
    (r"\b(manger|bouffe|repas|resto|pizza|kebab|burger|frigo|cuisine)\b", ["nourriture", "food"]),
    (r"\b(voiture|permis|conduire|caisse|bagnole)\b", ["voiture", "permis"]),
    (r"\b(foot|match|sport|salle|muscu|gym)\b", ["sport", "foot"]),
    (r"\b(argent|thune|sous|payer|cher|euros?|banque)\b", ["argent"]),
    (r"\b(no[eë]l|cadeau|anniversaire|f[eê]te|halloween|vacances)\b", ["fete", "vacances"]),
    (r"\b(m[ée]decin|docteur|h[ôo]pital|malade|pharmacie)\b", ["medecin", "sante"]),
    (r"\b(aura|battle|clash|vanne|roast)\b", ["clash", "aura"]),
]
EMOTIONS = [(r"\b(col[eè]re|énerv|enerv|furieu|cri)\w*", ["colere"]), (r"\b(g[eê]n|malaise|awkward)\w*", ["malaise", "gene"]),
            (r"\b(mdr|ptdr|lol|rire|rigol)\w*", ["mdr", "fourire"]), (r"\b(triste|pleur)\w*", ["emotion"])]


def _propre(h):
    h = unicodedata.normalize("NFKD", str(h).lower().lstrip("#").replace("œ", "oe").replace("æ", "ae"))
    return re.sub(r"[^a-z0-9_]", "", "".join(c for c in h if not unicodedata.combining(c)))[:30]


def sans_lien(t):
    """Retire tout lien (la source du son reste nommée : « 🎧 Son original : @compte »)."""
    t = re.sub(r"\s*[—–-]\s*https?://\S+", "", t or "")
    t = re.sub(r"https?://\S+|www\.\S+|\b(vm|vt)\.tiktok\.com/\S+", "", t)
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", t)).strip()


def hashtags(sk=None, texte="", n=None):
    """Hashtags de la vidéo : ceux de l'IA, puis ceux du sujet (famille, école, couple, travail…), des métiers reconnus, des
    émotions, puis la chaîne et la niche ; sans doublon, sans accent, NB_HASHTAGS au plus (15 par défaut)."""
    sk = sk or {}; n = n or NB_HASHTAGS
    t = " ".join([texte or "", str(sk.get("legende") or ""), str(sk.get("sujet") or "")] + [str(r.get("t", "")) for r in sk.get("repliques") or []]).lower()
    out = list(CHAINE)
    out += [_propre(h) for h in (sk.get("hashtags") or [])]
    for motif, hs in THEMES + EMOTIONS:
        if re.search(motif, t): out += hs
    try:
        import metiers
        out += [_propre(m) for m in set(metiers.qui_fait(sk).values())] if sk.get("repliques") else []
    except Exception: pass
    out += NICHE
    vus = []
    for h in out:
        h = _propre(h)
        if h and h not in vus and len(h) > 1: vus.append(h)
    return vus[:n]


def composer(sk, credit=""):
    """Description complète : texte, question, source du son (sans lien), hashtags."""
    corps = str(sk.get("legende") or "").strip()
    if sk.get("question"): corps += "\n\n" + str(sk["question"]).strip()
    if credit: corps += "\n\n" + credit
    return sans_lien(corps) + "\n\n" + " ".join("#" + h for h in hashtags(sk))


def completer(legende, fichier=None):
    """Juste avant l'envoi : enlève les liens ; ajoute les hashtags s'il n'y en a pas (anciennes vidéos), d'après le sketch gardé."""
    t = sans_lien(legende)
    if "#" in t: return t
    sk = {}
    if fichier:
        try: sk = json.load(open(os.path.join(RACINE, "episodes", "sketchs", os.path.splitext(os.path.basename(fichier))[0] + ".json"), encoding="utf-8"))
        except (OSError, ValueError): sk = {}
    return t + "\n\n" + " ".join("#" + h for h in hashtags(sk, texte=t))
