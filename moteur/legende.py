"""Description TikTok (demande de l'auteur, 30 octobre 2026) : la description de la vidéo, la question pour les commentaires, la
source du son (« 🎧 Son original : @compte ») SANS aucun lien, puis beaucoup de hashtags liés à la vidéo (sujet, univers, métiers,
émotions) + ceux de la chaîne et de la niche (animation, humour, doublage). Utilisé à la fabrication (principal.py) et juste avant
l'envoi (publier.py) : une ancienne vidéo sans hashtags ou avec un lien est corrigée au moment de la publication."""
import json, os, re, unicodedata

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
NB_HASHTAGS = int(os.environ.get("NB_HASHTAGS") or 15)
CHAINE = ["petitsdramas"]
NICHE = ["humour", "drole", "animation", "dessinanime", "cartoon", "sketch", "doublage", "humourfrancais", "francophone", "humourfrancophone"]
# Francophonie (choix de l'auteur du 21 novembre 2026, idée 2) : nos vidéos parlent à tous les francophones (Belgique, Suisse,
# Québec, Afrique, Maghreb) : jamais un hashtag qui enferme la vidéo en France, ni les hashtags inutiles (#fyp / #pourtoi : TikTok
# dit qu'ils ne servent à rien). Aussi retirés des anciennes descriptions à l'envoi. FRANCOPHONIE=0 pour couper.
FRANCE_SEULE = {"france", "tiktokfrance", "francetiktok", "paris", "marseille", "lyon", "toulouse", "lille", "bordeaux", "nantes", "nice",
                "pourtoi", "fyp", "foryou", "foryoupage", "fy", "fypage", "pourtoii", "viral", "fypシ"}


def francophone(h):
    return os.environ.get("FRANCOPHONIE", "1") == "0" or _propre(h) not in FRANCE_SEULE
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


# Hashtags à risque (choix de l'auteur du 11 novembre, idée 7) : ceux que TikTok bloque ou qui font baisser la diffusion (contenu
# adulte, drogue, violence, automutilation, tendances « spam »). Jamais dans nos descriptions ; réglage HASHTAGS_INTERDITS pour en ajouter.
RISQUES = re.compile(r"porn|nsfw|onlyfans|cannabis|cocaine|suicide|selfharm|automutil|terroris|followforfollow|follow4follow|like4like|"
                     r"likeforlike|gainfollowers|freefollowers|^(sex|sexe|sexy|nude|nudes|xxx|boobs|hotgirl|hotboy|drogue|drogues|drug|drugs|"
                     r"weed|coke|beuh|shit|kill|tuer|arme|armes|gun|guns|nazi|hitler|gore|blood|sang|f4f|l4l|suivezmoi|abonnetoi)$")


def interdits():
    return {_propre(h) for h in re.split(r"[\s,;#]+", os.environ.get("HASHTAGS_INTERDITS") or "") if h.strip()}


def hashtag_sur(h):
    """Ce hashtag peut-il être publié sans risque pour la diffusion du compte ?"""
    h = _propre(h)
    return bool(h) and not RISQUES.search(h) and h not in interdits()


def sans_risque(texte):
    """Retire d'un texte les hashtags à risque (descriptions déjà écrites, envoyées à TikTok)."""
    t = re.sub(r"(?<!\w)#([\wÀ-ÿ]+)", lambda m: m.group(0) if hashtag_sur(m.group(1)) and francophone(m.group(1)) else "", str(texte or ""))
    return re.sub(r"[ \t]{2,}", " ", t).strip()


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
    except Exception as _e: __import__("pannes").avale(_e)
    out += NICHE
    vus = []
    for h in out:
        h = _propre(h)
        if h and h not in vus and len(h) > 1 and hashtag_sur(h) and francophone(h): vus.append(h)   # (jamais un hashtag à risque)
    return vus[:n]


ABONNE = "🔔 Abonne-toi : une nouvelle histoire chaque jour !"           # choix de l'auteur (6 novembre, proposition 5 : peu d'abonnés)


def phrase_abonne():
    """Phrase d'abonnement de la description (réglage PHRASE_ABONNE : texte à la place, « 0 » pour l'enlever)."""
    p = (os.environ.get("PHRASE_ABONNE") or "").strip()
    return "" if p == "0" else (p or ABONNE)


def composer(sk, credit=""):
    """Description complète : texte, question, appel à s'abonner, source du son (sans lien), hashtags."""
    corps = str(sk.get("legende") or "").strip()
    if sk.get("question"): corps += "\n\n" + str(sk["question"]).strip()
    try: corps = __import__("orthographe").corriger_texte(corps)          # LanguageTool (idée 15) : accents et accords muets
    except Exception as _e: __import__("pannes").avale(_e)
    try:
        l_ = __import__("suites").ligne_legende(sk)                        # vidéo en plusieurs parties : la suite est annoncée
        if l_: corps += "\n\n" + l_
    except Exception as _e: __import__("pannes").avale(_e)
    if phrase_abonne(): corps += "\n\n" + phrase_abonne()
    if credit: corps += "\n\n" + credit
    return sans_lien(corps) + "\n\n" + " ".join("#" + h for h in hashtags(sk))


CHOIX = ("Team {a} ou team {b} ? 👇", "Vous êtes plutôt {a} ou {b} ? 👇")
GENERAL = ("Vous auriez fait quoi à sa place ? 👇", "Ça vous est déjà arrivé ? Racontez 👇", "Qui a raison selon vous ? 👇",
           "Identifie quelqu'un qui ferait exactement ça 😂👇")


def commentaire(sk):
    """Commentaire de relance à épingler à la main sous la vidéo (audit du 17 novembre 2026, idée 14 : TikTok ne permet pas de le
    poster par un robot). Celui de l'IA s'il existe et diffère de la question de la description ; sinon un choix entre les deux
    personnages (noms dits dans le dialogue, sinon « le personnage de gauche / de droite »), sinon une question générale."""
    import hashlib, re
    c = str(sk.get("commentaire") or "").strip()
    q = str(sk.get("question") or "").strip()
    if c and c.lower() != q.lower(): return c
    graine = int(hashlib.sha1(str(sk.get("sujet") or q).encode()).hexdigest()[:6], 16)
    noms = []
    for r in sk.get("repliques") or []:                                     # « Maurice », « Kenza »… appelés dans le dialogue
        for n in re.findall(r"(?:^|\s)([A-ZÉÈ][a-zéèëïî]{2,12})(?=\s?[,!?])", str(r.get("t") or r.get("texte") or "")):
            if n.lower() not in ("mais", "non", "oui", "bah", "ben", "allez", "alors", "attends", "quoi", "tu", "je", "moi", "toi", "bon",
                                 "ouais", "voilà", "hein", "eh", "oh", "ah", "elle", "il", "on", "nous", "vous", "et", "ça", "pourquoi",
                                 "comment", "regarde", "écoute", "arrête", "putain", "merde", "wesh", "frère", "maman", "papa", "madame",
                                 "monsieur", "viens", "arrête", "attendez", "tiens", "salut", "merci", "pardon", "sérieux", "grave", "vas", "laisse", "dis",
                                 "franchement", "putain", "excuse", "désolé", "chérie", "chéri", "bébé", "mec", "gars", "frérot") and n not in noms: noms.append(n)
    if len(noms) >= 2: return CHOIX[graine % len(CHOIX)].format(a=noms[0], b=noms[1])
    return GENERAL[graine % len(GENERAL)]


def completer(legende, fichier=None):
    """Juste avant l'envoi : enlève les liens ; ajoute les hashtags s'il n'y en a pas (anciennes vidéos), d'après le sketch gardé."""
    t = sans_lien(legende)
    if phrase_abonne() and "abonne" not in t.lower():                    # vidéos faites avant le 6 novembre : la phrase est ajoutée à l'envoi
        i = t.find("#"); i = t.find("🎧") if "🎧" in t else i
        t = (t[:i].rstrip() + "\n\n" + phrase_abonne() + "\n\n" + t[i:]) if i > 0 else (t + "\n\n" + phrase_abonne())
    if "#" in t: return sans_risque(t)                                    # (hashtags à risque retirés, même des anciennes descriptions)
    sk = {}
    if fichier:
        try: sk = json.load(open(os.path.join(RACINE, "episodes", "sketchs", os.path.splitext(os.path.basename(fichier))[0] + ".json"), encoding="utf-8"))
        except (OSError, ValueError): sk = {}
    return t + "\n\n" + " ".join("#" + h for h in hashtags(sk, texte=t))
