"""Moteur humoristique : écriture du sketch du jour par Claude (API Anthropic).
Les consignes d'auteur sont dans moteur/prompts/moteur_humour.md (moteur de satire professionnel fourni par l'utilisateur).
Étapes : 1) sélection du sujet parmi plusieurs candidats notés sur 10 (avec vérification web si disponible) et choix de l'angle ;
2) écriture ; 3) contrôle qualité noté sur 100, jusqu'à 3 réécritures si < 80, puis changement de sujet si le sketch reste faible."""
import json, os, re, unicodedata
ICI = os.path.dirname(os.path.abspath(__file__))
MOTEUR_HUMOUR = open(os.path.join(ICI, "prompts", "moteur_humour.md"), encoding="utf-8").read()

MODELE = os.environ.get("MODELE_CLAUDE") or "claude-opus-5-5"          # Opus : humour plus fin (réglable dans l'appli)
# réglages de la régie (variables du dépôt)
LONGUEURS = {"pro": ("10 à 16", "60 à 90"), "courte": ("5 à 6", "20 à 25"), "normale": ("7 à 9", "30 à 40"), "longue": ("9 à 12", "40 à 55"),
             "monetisable": ("13 à 16", "60 à 75")}   # format long : plus d'une minute (rémunération TikTok)
TONS = {"clash": "CLASH, foutage de gueule direct (le style préféré du public) : on compare l'actu à la vie de tous les jours avec une mauvaise foi assumée (« Ils ont trouvé 3 000 profs en 24 h. Moi, j'ai mis trois semaines à trouver un plombier. »), on balance des hypothèses absurdes en « soit… soit… » (« soit c'est un miracle, soit ils ont recruté au rayon surgelés »), l'invité répond du tac au tac en aggravant son cas (« ils ont été décongelés ce matin »), et la CHUTE finale balance la vérité crue du sujet, cash, comme un clash : ce qui se passe vraiment, qui y gagne, qui paie (« En clair : il manque des profs, on recrute à la va-vite, et vos enfants servent de période d'essai. »). Phrases courtes, punchlines sèches, comme entre potes qui chambrent",
        "farfelu": "gags farfelus et ironie pince-sans-rire : situations délirantes, images absurdes et très concrètes, ironie froide envers les institutions et la langue de bois",
        "bon_enfant": "foutage de gueule bon enfant envers les institutions, la langue de bois et les travers du pouvoir",
        "piquant": "satire mordante et sans pitié envers les institutions, les décisions et la langue de bois (jamais envers les gens pour ce qu'ils sont)",
        "absurde": "absurde total façon sketch surréaliste : situations délirantes poussées très loin, logique folle mais implacable"}
LONGUEUR = os.environ.get("LONGUEUR") or "pro"
NB, SECONDES = LONGUEURS.get(LONGUEUR, LONGUEURS["pro"])
NB_MAX = int(NB.split()[-1])
MOTS = {"pro": 190, "courte": 60, "normale": 90, "longue": 130, "monetisable": 200}.get(LONGUEUR, 190)
MOTS_MIN = {"pro": 130, "monetisable": 150}.get(LONGUEUR, 0)   # budget de mots (≈ 2,5 mots/s)
TON = TONS.get(os.environ.get("TON") or "clash", TONS["clash"])
CAST = {
    "presentateur": "Jean-Michel Plateau, présentateur. DÉFAUT FIXE : ne réagit JAMAIS, même au pire ; calme olympien ; pose la question simple et logique qui fait tout s'écrouler. C'est souvent lui qui lance la chute finale.",
    "envoyee": "Martine Couloir, envoyée spéciale (fictive) en direct sur le terrain (Assemblée, ministère, salon, sommet…). DÉFAUT FIXE : prend tout au premier degré ; blasée, décrit les scènes les plus absurdes avec un sérieux total. Reine du détail concret ridicule.",
    "invite": "L'invité (fictif) du jour : un « expert », conseiller ou porte-parole d'une institution (jamais une personne réelle). DÉFAUT FIXE : justifie l'injustifiable avec une logique imparable ; langue de bois, mauvaise foi, transforme chaque échec en victoire.",
}
LOOKS = ("chauve", "moustache")

EXEMPLE = {
 "sujet": "3000 PROFS EXPRESS",
 "verite": "Il manque des profs depuis des années ; pour le cacher, on recrute à la va-vite, et ce sont les élèves qui paient.",
 "ecran": "3000 PROFS",
 "titre_accroche": "3000 profs en 24 h, mon plombier : 3 semaines",
 "invite_nom": "Hubert Rustine",
 "invite_role": "Porte-parole (fictif) du ministère",
 "invite_look": "chauve",
 "lieu_direct": "Rayon surgelés",
 "question": "Votre prof remplaçant, il était encore congelé ? 👇",
 "repliques": [
  {
   "p": "presentateur",
   "t": "Le ministère a trouvé 3 000 profs en 24 heures. Moi, j'ai mis trois semaines à trouver un plombier.",
   "d": "Le ministère a trouvé trois mille profs en vingt-quatre heures. Moi, j'ai mis trois semaines à trouver un plombier.",
   "chute": True
  },
  {
   "p": "presentateur",
   "t": "Martine, ils sortent d'où, ces profs ?"
  },
  {
   "p": "envoyee",
   "t": "J'ai mené l'enquête. Soit c'est un miracle, soit ils ont recruté au rayon surgelés.",
   "chute": True
  },
  {
   "p": "invite",
   "t": "N'importe quoi. Nos profs sont frais. Ils ont été décongelés ce matin.",
   "chute": True
  },
  {
   "p": "presentateur",
   "t": "Et ils enseignent quoi ?"
  },
  {
   "p": "invite",
   "t": "Ce qui reste. Le prof de sport fait les maths. Il compte les tours de terrain.",
   "chute": True
  },
  {
   "p": "envoyee",
   "t": "Bonne nouvelle, Jean-Michel : votre plombier est arrivé. Il vient d'être nommé prof de physique.",
   "attente": 0.5,
   "chute": True
  },
  {
   "p": "presentateur",
   "t": "En clair : il manque des profs depuis des années, on recrute à la va-vite, et vos enfants servent de période d'essai.",
   "chute": True
  }
 ],
 "bandeau": [
  "UN PROF RETROUVÉ ENTRE LES PETITS POIS ET LES FRITES",
  "LE PLOMBIER DE JEAN-MICHEL NOMMÉ PROF DE PHYSIQUE",
  "RECRUTEMENT EXPRESS : DES PROFS LIVRÉS EN DRIVE"
 ],
 "gag": {
  "replique": 2,
  "prompt": "Flat 2D cartoon, thick black outlines, simple shapes. In a supermarket frozen food aisle, a confused teacher with a briefcase and glasses steps out of a chest freezer covered in frost, holding a piece of chalk, shoppers stare, comedic, deadpan."
 }
}

ADAPTATION = """
═══════════════════════════════════════════
ADAPTATION AU ROBOT « L'INFO EN CAOUTCHOUC » (prioritaire en cas de conflit avec ce qui précède)
═══════════════════════════════════════════
SUJET — RÈGLE DU PROPRIÉTAIRE (remplace la section 2 « pas nécessairement le titre le plus important ») : le sujet DOIT être un des gros titres de l'actualité française du jour. Les candidats te sont donnés classés par importance (nombre de médias français qui les mettent à la une). Tu choisis parmi les {top} premiers uniquement ; le potentiel comique départage, il ne justifie jamais de prendre un sujet secondaire.
RECHERCHE : le robot a déjà collecté l'actualité des dernières 24 à 36 heures dans les flux RSS de plusieurs médias français ; tu reçois les sujets candidats avec leurs articles. Si l'outil de recherche web est disponible, utilise-le pour vérifier les faits du sujet choisi (dates, chiffres) ; sinon, appuie-toi uniquement sur les articles fournis et dis-le dans "faits_reels".

PERSONNAGES (fictifs, animés en dessin, clés autorisées pour "p") :
{cast}
Les dialogues sont joués UNIQUEMENT par ces trois personnages. Le format choisi (faux JT, conférence de presse, réunion de crise, interview absurde, parodie publicitaire, débat…) se joue à l'intérieur de notre JT : le présentateur ouvre et ferme, l'envoyée est en direct sur le lieu de l'action, l'invité incarne le camp moqué (porte-parole, ministre, PDG, expert… toujours FICTIF, avec un nom inventé).

PERSONNES RÉELLES : tu peux citer une personnalité publique uniquement pour un fait vérifié présent dans les sources (ce qu'elle a réellement dit ou fait). Tu ne lui fais JAMAIS dire ou faire quoi que ce soit d'inventé, même pour rire : la caricature passe par nos personnages fictifs. Jamais de moquerie liée à l'origine, la religion, le genre, l'orientation, le handicap ; on ne rit pas des victimes ; aucune consigne de vote.

STYLE MAISON (validé par le public) : {ton}

DURÉE : {secondes} secondes, {nb} répliques, entre {mots_min} et {mots} mots prononcés au total. Réplique 0 = l'accroche du présentateur (2 secondes, la punchline la plus forte du début). CHUTE VÉRITÉ (règle n°1 du propriétaire) : la dernière réplique dit tout haut la vérité du SUJET PRINCIPAL que tout le monde pense tout bas — le vrai mécanisme, la vraie hypocrisie, qui gagne et qui paie — en une phrase sèche de clash, fondée sur les faits réels. Elle nomme le sujet (ses acteurs, son enjeu) ; jamais une blague annexe, jamais un simple rappel d'un gag du sketch (le yaourt, le plombier…). Tout le sketch est construit pour y mener : chaque réplique monte vers cette vérité. Un clin d'œil à l'accroche n'est permis que s'il sert cette vérité.
Voix synthétiques : phrases courtes, faciles à dire, une idée par phrase. Nombres, sigles et pourcentages en toutes lettres dans le champ "d".
{special}
Running gags récents de l'émission (un clin d'œil possible s'il colle au sujet) : {gags}
ANTI-RÉPÉTITION — sujets et vannes des derniers épisodes, à NE PAS refaire : {recents}

LIVRABLES : rends tout avec l'outil rendre_sketch, dans ce format JSON strict (A→F du cahier des charges inclus) :
{{"sujet": "1 à 3 mots, MAJUSCULES", "ecran": "max 14 caractères, MAJUSCULES", "titre_accroche": "max 40 caractères, sans emoji",
 "verite": "la vérité crue du sujet principal, dite par la dernière réplique", "concept": "B. concept et titre", "format": "B. format choisi", "angle": "B. angle comique",
 "resume_factuel": "A. résumé factuel daté", "faits_reels": ["E. faits réels vérifiés"], "inventions": ["E. inventions satiriques"],
 "decoupage": [{{"scene": "D. description : lieu, actions visuelles, transition", "repliques": [indices des répliques de la scène], "lieu": "plateau|direct|duplex|reconstitution", "son": "bruitage à la fin de la scène parmi : rimshot, xylo_descente, trombone_triste, dun_dun, woosh, reconstitution (ou vide)", "duree": secondes estimées}}],
 "invite_nom": "nom fictif", "invite_role": "fonction avec « (fictif) », max 34 caractères", "invite_look": "{looks}",
 "lieu_direct": "lieu du direct de l'envoyée, max 26 caractères",
 "repliques": [{{"p": "presentateur|envoyee|invite", "t": "réplique affichée (max 160 caractères)", "d": "version à prononcer si différente", "chute": true si vanne, "attente": silence avant la réplique (0.4 à 1.2, une seule fois)}}],
 "bandeau": ["3 ou 4 fausses dépêches absurdes, MAJUSCULES, max 55 caractères"],
 "gag": {{"replique": index d'une réplique de l'envoyée ou de l'invité décrivant une scène visuelle drôle, "prompt": "scène EN ANGLAIS pour un générateur vidéo, commence par « Flat 2D cartoon, thick black outlines, simple shapes. », sans texte, sans personne réelle"}},
 "question": "question pour les commentaires, avec emoji", "running_gag": "nouveau gag réutilisable (ou vide)",
 "legende": "légende TikTok (max 140 caractères) finissant par « Satire, personnages fictifs. »", "hashtags": ["5 à 7, sans #, minuscules, sans accents"],
 "sources": ["2 ou 3 URL complètes copiées parmi les liens des articles fournis"]}}
Ne mets AUCUNE note ni décision (« prêt pour production ») dans tes livrables : la note F est donnée par un relecteur indépendant.

EXEMPLE DE STYLE ET DE FORMAT (court, sujet d'une autre semaine, ne réutilise pas ses blagues) :
{exemple}"""

SELECTION = """Étapes 1 à 3 du cahier des charges. Voici les gros titres de l'actualité française du jour, classés par importance (le [0] est le plus à la une) :
{candidats}

Note chaque candidat sur 10 (potentiel comique, absurdité, potentiel satirique, originalité, reconnaissance par le public, potentiel visuel, fraîcheur ; plus de poids à l'originalité et au potentiel comique). Écarte les drames et les sujets où l'on rirait de victimes.
Choisis OBLIGATOIREMENT parmi les candidats [0] à [{dernier}] celui qui permet le MEILLEUR sketch, puis trouve son angle comique (contradiction discours/actes, mauvaise foi, absurdité administrative, double standard, conséquence grotesque). Si tu disposes de la recherche web, vérifie rapidement les faits clés du sujet choisi.
Écris ensuite, AVANT tout le reste, la VÉRITÉ du sujet : une phrase brute qui dit ce qui se passe vraiment derrière l'annonce (qui y gagne, qui paie, quelle hypocrisie), fondée sur les faits. Ce sera la chute du sketch.
Rends ton choix avec l'outil choisir_sujet."""

CRITIQUE = """Étape 8 du cahier des charges : relis ce sketch comme un auteur exigeant et note-le sur 100, honnêtement (ne gonfle jamais la note) :
originalité du concept /20, punchlines /25, rythme /15, pertinence satirique /15, dialogues /10, potentiel visuel /10, chute /5.
SUJET PRINCIPAL : {sujet}
Fiche et script (format vidéo animée {secondes} s, voix synthétiques ; les actions visuelles et le découpage comptent pour le potentiel visuel) :
{sketch}
EXIGENCE N°1 DU PROPRIÉTAIRE : la chute (dernière réplique) doit dire la vérité crue de CE sujet principal, comme un clash (ce qui se passe vraiment, qui gagne, qui paie). Une chute qui n'est qu'un gag annexe ou un rappel d'une blague du sketch (« chute_vraie » = false) plafonne la note à 70, quelle que soit la qualité du reste.
Rends la note avec l'outil noter_sketch. Le champ "critique" est OBLIGATOIRE et non vide : cite les répliques faibles (numéro + pourquoi) et propose ce qu'il faut changer."""

REECRITURE = """Ton sketch a obtenu {note}/100 (seuil : 80). Critique du relecteur :
{critique}
Réécris-le en profondeur (pas de retouches cosmétiques) pour dépasser 80 : punchlines plus surprenantes, escalade plus forte, chute qui balance la vérité crue du sujet principal (pas un gag annexe). Mêmes faits, mêmes règles. Rends le sketch complet avec l'outil rendre_sketch."""

def _schema(props, requis):
    return {"type": "object", "properties": props, "required": requis}

OUTIL = {"name": "rendre_sketch", "description": "Rendre le sketch complet (livrables A à F).",
         "input_schema": _schema({
             "sujet": {"type": "string"}, "ecran": {"type": "string"}, "titre_accroche": {"type": "string"},
             "verite": {"type": "string"}, "concept": {"type": "string"}, "format": {"type": "string"}, "angle": {"type": "string"}, "resume_factuel": {"type": "string"},
             "faits_reels": {"type": "array", "items": {"type": "string"}}, "inventions": {"type": "array", "items": {"type": "string"}},
             "decoupage": {"type": "array", "items": _schema({"scene": {"type": "string"}, "repliques": {"type": "array", "items": {"type": "integer"}},
                                                              "lieu": {"type": "string"}, "son": {"type": "string"}, "duree": {"type": "number"}}, ["scene"])},
             "invite_nom": {"type": "string"}, "invite_role": {"type": "string"}, "invite_look": {"type": "string"}, "lieu_direct": {"type": "string"},
             "question": {"type": "string"}, "running_gag": {"type": "string"},
             "repliques": {"type": "array", "items": _schema({"p": {"type": "string"}, "t": {"type": "string"}, "d": {"type": "string"},
                                                              "chute": {"type": "boolean"}, "attente": {"type": "number"}}, ["p", "t"])},
             "bandeau": {"type": "array", "items": {"type": "string"}},
             "gag": _schema({"replique": {"type": "integer"}, "prompt": {"type": "string"}}, []),
             "legende": {"type": "string"}, "hashtags": {"type": "array", "items": {"type": "string"}}, "sources": {"type": "array", "items": {"type": "string"}}},
             ["sujet", "repliques", "legende"])}
OUTIL_CHOIX = {"name": "choisir_sujet", "description": "Notes des candidats, sujet choisi et angle.",
               "input_schema": _schema({"notes": {"type": "array", "items": _schema({"index": {"type": "integer"}, "note": {"type": "number"},
                                                                                      "raison": {"type": "string"}}, ["index", "note"])},
                                        "choix": {"type": "integer"}, "angle": {"type": "string"},
                                        "verite": {"type": "string", "description": "La vérité crue du sujet en une phrase : ce sera la chute."},
                                        "faits_verifies": {"type": "array", "items": {"type": "string"}}}, ["choix", "angle", "verite"])}
OUTIL_NOTE = {"name": "noter_sketch", "description": "Note qualité sur 100 et critique.",
              "input_schema": _schema({"chute_vraie": {"type": "boolean", "description": "La dernière réplique dit-elle la vérité crue du sujet principal ?"},
                                       "critique": {"type": "string", "minLength": 40, "description": "À écrire EN PREMIER : répliques faibles (numéro + pourquoi) et corrections précises."},
                                       "originalite": {"type": "number"}, "punchlines": {"type": "number"}, "rythme": {"type": "number"},
                                       "pertinence": {"type": "number"}, "dialogues": {"type": "number"}, "visuel": {"type": "number"},
                                       "chute": {"type": "number"}, "total": {"type": "number"}}, ["chute_vraie", "critique", "total"])}
RECHERCHE_WEB = {"type": "web_search_20250305", "name": "web_search", "max_uses": 4}

def _json(texte):
    m = re.search(r"\{.*\}", texte, re.S)
    if not m: raise ValueError("pas de JSON")
    return json.loads(m.group(0))

def _court(s, n): return str(s or "").strip()[:n]

def _role(p, sk):
    """Rôle normalisé : accepte « Présentateur », « envoyée spéciale », le nom fictif de l'invité…"""
    x = unicodedata.normalize("NFKD", str(p or "").lower()).encode("ascii", "ignore").decode()
    for cle, motif in (("presentateur", "present"), ("envoyee", "envoy"), ("invite", "invit")):
        if motif in x: return cle
    nom = unicodedata.normalize("NFKD", str(sk.get("invite_nom") or "").lower()).encode("ascii", "ignore").decode()
    return "invite" if nom and x and (x in nom or nom in x) else x

def _liste(v):
    if isinstance(v, str):                                                # tableau renvoyé sous forme de texte JSON
        try: v = json.loads(v)
        except Exception: return []
    return v if isinstance(v, list) else []

def valider(sk, liens):
    reps, attente = [], False
    if not isinstance(sk, dict): raise ValueError("réponse sans sketch")
    brutes = _liste(sk.get("repliques") or sk.get("script") or sk.get("dialogues"))
    for r in brutes[:16]:
        if not isinstance(r, dict): continue
        p = _role(r.get("p") or r.get("personnage") or r.get("role"), sk); t = _court(r.get("t") or r.get("texte") or r.get("replique"), 170)
        if p not in CAST or not t: continue
        x = {"p": p, "t": t}
        if r.get("d"): x["d"] = _court(r["d"], 260)
        if r.get("chute"): x["chute"] = True
        try: a = float(r.get("attente") or 0)
        except (TypeError, ValueError): a = 0
        if a > 0 and not attente: x["attente"] = min(1.2, max(0.3, a)); attente = True
        reps.append(x)
    if len(reps) > NB_MAX:                                   # trop long : on garde le début et la chute finale
        reps = reps[:NB_MAX - 1] + [reps[-1]]
    if len(reps) < 4:
        vus = sorted({str((r or {}).get("p", "?"))[:20] for r in brutes if isinstance(r, dict)})[:5]
        raise ValueError(f"sketch trop court ({len(reps)} répliques ; champs reçus : {', '.join(sorted(sk))[:120]} ; rôles : {vus})")
    if reps[0]["p"] != "presentateur": raise ValueError("le présentateur doit ouvrir")
    tags = [re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(h).lower()).encode("ascii", "ignore").decode()) for h in sk.get("hashtags", [])]
    gag = None
    g = sk.get("gag") or {}
    try:
        i = int(g.get("replique"))
        if 0 <= i < len(reps) and reps[i]["p"] != "presentateur" and str(g.get("prompt", "")).strip():
            gag = {"replique": i, "prompt": _court(g["prompt"], 600)}
    except (TypeError, ValueError):
        pass
    look = sk.get("invite_look") if sk.get("invite_look") in LOOKS else LOOKS[0]
    return {"titre": _court(sk.get("sujet"), 30).upper() or "L'ACTU", "sujet": _court(sk.get("sujet"), 30).upper() or "L'ACTU",
            "ecran": _court(sk.get("ecran") or sk.get("sujet"), 14).upper(),
            "invite_nom": _court(sk.get("invite_nom"), 26) or "Hubert Rustine",
            "invite_role": _court(sk.get("invite_role"), 36) or "Expert (fictif)", "invite_look": look,
            "lieu_direct": _court(sk.get("lieu_direct"), 28) or "Assemblée",
            "titre_accroche": _court(sk.get("titre_accroche"), 46), "question": _court(sk.get("question"), 90),
            "running_gag": _court(sk.get("running_gag"), 160), "verite": _court(sk.get("verite"), 300),
            "repliques": reps, "bandeau": [_court(b, 60).upper() for b in sk.get("bandeau", []) if str(b).strip()][:4],
            "gag": gag,
            "legende": _court(sk.get("legende"), 160) or "L'actu du jour, en dessin animé. Satire, personnages fictifs.",
            "hashtags": [t for t in tags if t][:7] or ["satire", "humour", "actualite", "politique"],
            "sources": _sources(sk.get("sources"), liens),
            "decoupage": _decoupage(sk.get("decoupage"), len(reps))}

def _norm_lien(u): return re.sub(r"^https?://(www\.)?|[?#].*$|/$", "", str(u or "").strip().lower())

def _sources(proposees, liens):
    """Liens cités par le sketch, uniquement parmi les articles réellement fournis (aucun lien inventé)."""
    par_cle = {_norm_lien(l): l for l in liens if l}
    out = []
    for s in proposees or []:
        l = par_cle.get(_norm_lien(s))
        if l and l not in out: out.append(l)
    return out[:6]

SONS_DISPONIBLES = ("rimshot", "xylo_descente", "trombone_triste", "dun_dun", "woosh", "reconstitution")
def _decoupage(dec, n):
    """Découpage scène par scène, normalisé pour le moteur vidéo :
    [{"scene", "repliques": [indices], "lieu": plateau|direct|duplex|reconstitution, "son": bruitage de notre banque ou "", "duree": s}]."""
    out = []
    for s in (dec or [])[:12]:
        if not isinstance(s, dict): continue
        try: idx = [int(i) for i in s.get("repliques", []) if 0 <= int(i) < n]
        except (TypeError, ValueError): idx = []
        lieu = str(s.get("lieu", "")).lower(); lieu = lieu if lieu in ("plateau", "direct", "duplex", "reconstitution") else ""
        son = str(s.get("son", "")).lower(); son = son if son in SONS_DISPONIBLES else ""
        try: duree = round(float(s.get("duree", 0)), 1)
        except (TypeError, ValueError): duree = 0
        out.append({"scene": _court(s.get("scene") or s.get("description"), 300), "repliques": idx, "lieu": lieu, "son": son, "duree": duree})
    return out

USAGE = {"appels": 0, "entree": 0, "sortie": 0, "recherches_web": 0}                          # suivi du budget (jetons consommés)

def _appel(client, systeme, messages, outil=OUTIL, web=False, max_tokens=12000):
    """Appel Claude ; renvoie l'entrée de l'outil demandé (ou un JSON trouvé dans le texte). Recherche web si possible."""
    outils = [outil] + ([RECHERCHE_WEB] if web else [])
    kw = dict(model=MODELE, max_tokens=max_tokens, messages=messages, tools=outils, tool_choice={"type": "auto"})
    if systeme: kw["system"] = systeme
    try:
        r = client.messages.create(**kw)
        u = getattr(r, "usage", None)
        if u: USAGE["entree"] += getattr(u, "input_tokens", 0) or 0; USAGE["sortie"] += getattr(u, "output_tokens", 0) or 0; USAGE["appels"] += 1
        if web:
            n_web = getattr(getattr(u, "server_tool_use", None), "web_search_requests", None)
            if n_web is None: n_web = sum(1 for b in r.content if getattr(b, "type", "") == "server_tool_use")
            erreurs = [getattr(getattr(b, "content", None), "error_code", None) for b in r.content if getattr(b, "type", "") == "web_search_tool_result"]
            erreurs = [x for x in erreurs if x]
            USAGE["recherches_web"] += int(n_web or 0)
            print(f"Recherche web : {int(n_web or 0)} requête(s)" + (f", erreurs : {', '.join(map(str, erreurs))}" if erreurs else "") +
                  ("" if n_web else " — le modèle n'a pas consulté le web, vérification sur les articles RSS uniquement"), flush=True)
    except Exception as e:
        if not web: raise
        print(f"Recherche web indisponible ({str(e)[:120]}) : vérification sur les seuls articles fournis.", flush=True)
        return _appel(client, systeme, messages, outil, False, max_tokens)
    if getattr(r, "stop_reason", "") == "max_tokens":
        print(f"  réponse coupée (limite de {max_tokens} jetons atteinte) pour {outil['name']}", flush=True)
    brut = "".join(getattr(b, "text", "") or "" for b in r.content if getattr(b, "type", "") == "text")
    for b in r.content:
        if getattr(b, "type", "") == "tool_use" and getattr(b, "name", "") == outil["name"]:
            out = dict(b.input) if isinstance(b.input, dict) else {}
            if brut.strip(): out["_texte"] = brut.strip()[:3000]            # texte d'accompagnement (ex. critique écrite hors de l'outil)
            return out
    try: return _json(brut)
    except Exception:
        r2 = client.messages.create(**dict(kw, tools=[outil], messages=messages + [{"role": "assistant", "content": brut or "…"},
                                    {"role": "user", "content": f"Rends maintenant ta réponse avec l'outil {outil['name']}."}]))
        for b in r2.content:
            if getattr(b, "type", "") == "tool_use": return b.input
        raise ValueError("réponse inexploitable")

SPECIAL_DEMAIN = """- ÉPISODE SPÉCIAL DU DIMANCHE « LES INFOS DE DEMAIN » : après l'accroche, le présentateur annonce 3 ou 4 fausses brèves du futur (« Dans un an… », « En 2030… »), toutes sur CE sujet, chacune poussant la situation un cran plus loin dans l'absurde, avec une chute par brève ; l'envoyée ou l'invité peuvent réagir. L'écran du plateau affiche « EN 2030 »."""

def _mots(t):
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return {m for m in re.findall(r"[a-z]{5,}", t)}

def hors_sujet(sk, titres):
    """Refuse un sketch qui ne reprend aucun mot important du sujet imposé (le robot s'est éparpillé)."""
    sujet = _mots(titres[0]["titre"]) - {"direct", "selon", "apres", "contre", "entre", "leurs", "cette", "quand", "comment", "pourquoi"}
    texte = _mots(" ".join([sk["sujet"]] + [r["t"] for r in sk["repliques"]]))
    if sujet and len(sujet & texte) < 1:
        raise ValueError(f"hors sujet : le sketch doit parler de « {titres[0]['titre']} »")

def _prefixes(t): return {m[:5] for m in _mots(t)}

def chute_sur_sujet(sk, titres):
    """La chute (dernière réplique) doit parler du sujet principal : au moins un mot-clé du titre, des articles ou de la vérité déclarée."""
    fin = sk["repliques"][-1]; texte = fin.get("d") or fin["t"]
    ref = _prefixes(" ".join([titres[0]["titre"], titres[0].get("resume", "")[:300], sk.get("verite", ""), sk.get("sujet", "")] +
                             [t["titre"] for t in titres[1:4]])) - {"cette", "alors", "comme", "toujours", "encore", "votre", "notre"}
    if not (_prefixes(texte) & ref):
        raise ValueError(f"chute hors sujet : la dernière réplique (« {fin['t'][:80]} ») ne parle pas du sujet principal. "
                         "Elle doit balancer la vérité crue du sujet lui-même, pas un gag annexe ni un simple rappel")

def longueur(sk):
    n = sum(len((r.get("d") or r["t"]).split()) for r in sk["repliques"])
    if n > MOTS * 1.2: raise ValueError(f"trop long : {n} mots prononcés, maximum {MOTS}. Coupe")
    if MOTS_MIN and n < MOTS_MIN * 0.85: raise ValueError(f"trop court : {n} mots prononcés, minimum {MOTS_MIN}. Développe l'escalade")
    return n

def pertinents(titres):
    """Garde le titre principal et les articles qui parlent vraiment du même sujet (au moins 2 mots-clés communs)."""
    if not titres: return titres
    ref = _mots(titres[0]["titre"] + " " + titres[0].get("resume", "")[:200])
    return [titres[0]] + [t for t in titres[1:] if len(ref & _mots(t["titre"] + " " + t.get("resume", "")[:200])) >= 2]

def _bloc_candidat(k, titres):
    return f"[{k}] " + "\n    ".join(f"- [{t['source']}] {t['titre']} — {t['resume'][:220]} ({t['lien']})" for t in titres[:5])

TOP = 3                                                                  # le sujet est pris parmi les 3 plus gros titres du jour

def _bloquant(e):
    """Erreurs qui ne se règlent pas en réessayant : crédit épuisé, clé invalide, accès refusé."""
    t = str(e).lower()
    return any(m in t for m in ("credit balance", "authentication", "invalid x-api-key", "permission_error", "billing"))

def ecrire_sketch(candidats, essais=None, gags=(), special=False, recents=()):
    """candidats : liste de sujets (chaque sujet = liste d'articles, le titre principal en premier) — ou une simple liste d'articles.
    Renvoie le sketch validé, avec "fiche" (livrables A-F, note qualité, décision)."""
    import anthropic
    client = anthropic.Anthropic()
    if candidats and isinstance(candidats[0], dict): candidats = [candidats]
    gtxt = " ; ".join(g for g in gags if g)[:600] or "(aucun pour l'instant)"
    rtxt = " ; ".join(r for r in recents if r)[:1500] or "(aucun)"
    if essais is None:
        try: essais = max(0, min(5, int(os.environ.get("MAX_REECRITURES") or 3)))   # variable vide ou invalide : 3
        except ValueError: essais = 3
    systeme = MOTEUR_HUMOUR + ADAPTATION.format(cast="\n".join(f"- {k} : {v}" for k, v in CAST.items()), ton=TON, secondes=SECONDES, nb=NB,
                                                 mots=MOTS, mots_min=MOTS_MIN or 40, special=SPECIAL_DEMAIN if special else "", gags=gtxt, recents=rtxt,
                                                 looks="|".join(LOOKS), top=TOP, exemple=json.dumps(EXEMPLE, ensure_ascii=False, indent=0))
    # 1) sélection du sujet et de l'angle
    ordre, angle, verifs, verite = list(range(len(candidats))), "", [], ""
    try:
        ch = _appel(client, systeme, [{"role": "user", "content": SELECTION.format(dernier=min(TOP, len(candidats)) - 1, candidats="\n\n".join(_bloc_candidat(k, c) for k, c in enumerate(candidats[:TOP])))}],
                    OUTIL_CHOIX, web=True, max_tokens=4000)
        notes = {int(n.get("index", -1)): float(n.get("note", 0)) for n in ch.get("notes", []) if isinstance(n, dict)}
        choix = int(ch.get("choix", 0))
        if not 0 <= choix < min(TOP, len(candidats)):
            print(f"Choix {choix} refusé : hors des {TOP} plus gros titres, on prend le n°0.", flush=True); choix = 0
        ordre = [choix] + sorted([k for k in ordre[:TOP] if k != choix], key=lambda k: (-notes.get(k, 0), k))   # secours : autre gros titre
        angle, verifs = str(ch.get("angle", "")), [str(x) for x in ch.get("faits_verifies", [])][:8]
        verite = str(ch.get("verite", "")).strip()
        if verite: print(f"Vérité visée pour la chute : {verite[:200]}", flush=True)
        print("Gros titres soumis : " + " | ".join(f"{notes.get(k, '?')}/10 {c[0]['titre'][:60]}" for k, c in enumerate(candidats[:TOP])), flush=True)
        print(f"Sujet choisi : « {candidats[choix][0]['titre'][:100]} » — angle : {angle[:160]}", flush=True)
    except Exception as e:
        print(f"Sélection automatique impossible ({str(e)[:150]}) : premier candidat.", flush=True)
    meilleur = None
    for rang, k in enumerate(ordre[:2]):                                  # au plus deux sujets essayés
        titres = pertinents(candidats[k]); liens = {t["lien"] for t in titres}
        msg = (f"SUJET CHOISI : « {titres[0]['titre']} »\nArticles :\n" + _bloc_candidat(0, titres) +
               (f"\nAngle retenu : {angle}" if rang == 0 and angle else "") +
               (f"\nVÉRITÉ À BALANCER EN CHUTE (dernière réplique) : {verite}" if rang == 0 and verite else "\nCommence par trouver la vérité crue de ce sujet : ce sera la chute.") +
               (f"\nFaits vérifiés : " + " ; ".join(verifs) if rang == 0 and verifs else "") +
               "\n\nÉcris le sketch sur CE sujet uniquement (étapes 4 à 9).")
        conv = [{"role": "user", "content": msg}]; sk = None; derniere = None; brut = {}
        for tour in range(1 + (essais if rang == 0 else min(1, essais))):   # écriture puis jusqu'à 3 réécritures (1 pour le sujet de secours)
            try:
                brut = _appel(client, systeme, conv)
                sk = valider(brut, liens); hors_sujet(sk, titres); n_mots = longueur(sk); chute_sur_sujet(sk, titres)
            except Exception as e:
                derniere = e
                if _bloquant(e):
                    print(f"  ARRÊT : accès à l'API Claude impossible ({str(e)[:160]}). Action requise : recharger le crédit ou vérifier la clé ANTHROPIC_API_KEY.", flush=True)
                    break
                print(f"  version {tour + 1} refusée : {str(e)[:150]}", flush=True)
                conv = conv + [{"role": "assistant", "content": json.dumps(brut if isinstance(brut, dict) else {}, ensure_ascii=False)[:6000] or "…"},
                               {"role": "user", "content": f"Version invalide ({e}). Corrige et rends le sketch complet avec l'outil rendre_sketch."}]
                continue
            if not sk["sources"]:                                            # le modèle n'a pas recopié d'URL exacte : on cite les articles RSS fournis
                sk["sources"] = [t["lien"] for t in titres if t.get("lien")][:3]
            texte = (f"Vérité visée : {sk.get('verite', '')}\nConcept : {_court(brut.get('concept'), 600)}\nFormat : {_court(brut.get('format'), 300)}\n"
                     "Découpage : " + " | ".join(f"[{d['lieu'] or '?'}] {d['scene']}" for d in sk["decoupage"])[:1500] + "\n" +
                     (f"Plan gag (réplique {sk['gag']['replique']}) : {sk['gag']['prompt'][:300]}\n" if sk.get("gag") else "") +
                     "Répliques :\n" + "\n".join(f"{i}. {r['p']} : {r['t']}" for i, r in enumerate(sk["repliques"])))
            try:
                for essai_note in range(2):                                   # relecteur réinterrogé une fois si la note manque
                    nq = _appel(client, None, [{"role": "user", "content": CRITIQUE.format(sketch=texte, secondes=SECONDES, sujet=titres[0]["titre"])}], OUTIL_NOTE, max_tokens=5000)
                    try: note = float(nq["total"]); break
                    except (KeyError, TypeError, ValueError):
                        parts = [nq.get(k) for k in ("originalite", "punchlines", "rythme", "pertinence", "dialogues", "visuel", "chute")]
                        if all(isinstance(x, (int, float)) for x in parts): note = float(sum(parts)); break
                        print("  note totale absente : on redemande au relecteur", flush=True)
                else: raise ValueError("note totale absente deux fois")
                if nq.get("chute_vraie") is False and note > 70:
                    print(f"  chute jugée hors sujet par le relecteur : note plafonnée à 70 (au lieu de {note:.0f})", flush=True); note = 70.0
                critique = str(nq.get("critique") or "").strip() or nq.get("_texte", "") or \
                    " ; ".join(f"{k} {nq[k]}" for k in ("originalite", "punchlines", "rythme", "pertinence", "dialogues", "visuel", "chute") if k in nq)
            except Exception as e:
                note, critique = 0.0, f"notation impossible ({e})"
            print(f"  version {tour + 1} : {note:.0f}/100, {len(sk['repliques'])} répliques, {n_mots} mots", flush=True)
            sk["fiche"] = {k2: brut.get(k2) for k2 in ("concept", "format", "angle", "resume_factuel", "faits_reels", "inventions") if isinstance(brut, dict)}
            sk["fiche"]["decoupage"] = sk["decoupage"]
            sk["fiche"]["titres_sujet"] = [t["titre"] for t in titres[:6]]          # articles du sujet réellement choisi (anti-répétition)
            for k2 in ("concept", "format", "angle"):                       # la note F vient du relecteur, jamais de l'auteur
                if isinstance(sk["fiche"].get(k2), str):
                    sk["fiche"][k2] = re.sub(r"\s*(Note qualit[ée]|Décision|Decision)\b.*$", "", sk["fiche"][k2], flags=re.S | re.I).strip()
            sk["fiche"].update(verification_web=USAGE["recherches_web"] > 0, note=note, critique=critique[:1500], decision="prêt pour production" if note >= 80 else "à retravailler")
            if meilleur is None or note > meilleur["fiche"]["note"]: meilleur = sk
            if note >= 80: return sk
            conv = conv + [{"role": "assistant", "content": json.dumps(brut, ensure_ascii=False)[:8000]},
                           {"role": "user", "content": REECRITURE.format(note=round(note), critique=critique[:2000])}]
        if derniere is not None and _bloquant(derniere): break
        print(f"  sujet trop faible après réécritures{' : on essaie un autre sujet' if rang == 0 and len(ordre) > 1 else ''}", flush=True)
    if meilleur is None: raise RuntimeError(f"aucun sketch exploitable : {derniere}")
    print(f"  meilleure version retenue : {meilleur['fiche']['note']:.0f}/100 (à retravailler)", flush=True)
    return meilleur
