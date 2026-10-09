"""Écriture du sketch du jour par Claude (API Anthropic), à partir des vrais titres de l'actualité.
Format : un JT satirique sur UN seul sujet, avec trois personnages fictifs (présentateur, envoyée spéciale en direct, invité).
Deux passes : 1) l'auteur écrit ; 2) un « script doctor » réécrit les blagues les plus faibles."""
import json, os, re, unicodedata

MODELE = os.environ.get("MODELE_CLAUDE") or "claude-opus-5-5"          # Opus : humour plus fin (réglable dans l'appli)
# réglages de la régie (variables du dépôt)
LONGUEURS = {"courte": ("5 à 6", "20 à 25"), "normale": ("7 à 9", "30 à 40"), "longue": ("9 à 12", "40 à 55"),
             "monetisable": ("13 à 16", "60 à 75")}   # format long : plus d'une minute (rémunération TikTok)
TONS = {"farfelu": "gags farfelus et ironie pince-sans-rire : situations délirantes, images absurdes et très concrètes, ironie froide envers les institutions et la langue de bois",
        "bon_enfant": "foutage de gueule bon enfant envers les institutions, la langue de bois et les travers du pouvoir",
        "piquant": "satire mordante et sans pitié envers les institutions, les décisions et la langue de bois (jamais envers les gens pour ce qu'ils sont)",
        "absurde": "absurde total façon sketch surréaliste : situations délirantes poussées très loin, logique folle mais implacable"}
LONGUEUR = os.environ.get("LONGUEUR") or "courte"
NB, SECONDES = LONGUEURS.get(LONGUEUR, LONGUEURS["courte"])
NB_MAX = int(NB.split()[-1])
MOTS = {"courte": 60, "normale": 90, "longue": 130, "monetisable": 200}.get(LONGUEUR, 60)   # budget de mots (≈ 2,5 mots/s)
TON = TONS.get(os.environ.get("TON") or "farfelu", TONS["farfelu"])
CAST = {
    "presentateur": "Jean-Michel Plateau, présentateur. DÉFAUT FIXE : ne réagit JAMAIS, même au pire ; calme olympien ; pose la question simple et logique qui fait tout s'écrouler. C'est souvent lui qui lance la chute finale.",
    "envoyee": "Martine Couloir, envoyée spéciale (fictive) en direct sur le terrain (Assemblée, ministère, salon, sommet…). DÉFAUT FIXE : prend tout au premier degré ; blasée, décrit les scènes les plus absurdes avec un sérieux total. Reine du détail concret ridicule.",
    "invite": "L'invité (fictif) du jour : un « expert », conseiller ou porte-parole d'une institution (jamais une personne réelle). DÉFAUT FIXE : justifie l'injustifiable avec une logique imparable ; langue de bois, mauvaise foi, transforme chaque échec en victoire.",
}
LOOKS = ("chauve", "moustache")

EXEMPLE = {
    "sujet": "BUDGET 2027", "ecran": "BUDGET 2027", "invite_nom": "Hubert Rustine", "invite_role": "Conseiller (fictif) à Bercy", "invite_look": "chauve",
    "lieu_direct": "Sous le canapé de Bercy", "titre_accroche": "4 milliards perdus en 6 heures",
    "question": "Qui a vraiment volé les économies ? 👇", "running_gag": "Le Tic Tac rejeté en commission",
    "repliques": [
        {"p": "presentateur", "t": "Les députés devaient trouver quatre milliards. Ils ont trouvé un Tic Tac.", "chute": True},
        {"p": "presentateur", "t": "Martine, vous êtes sur place ?"},
        {"p": "envoyee", "t": "Jean-Michel, c'est la panique. Des fonctionnaires fouillent sous les coussins du canapé."},
        {"p": "envoyee", "t": "Ils ont trouvé deux euros.", "chute": True},
        {"p": "presentateur", "t": "Et le Tic Tac ?"},
        {"p": "envoyee", "t": "Il a été rejeté en commission.", "attente": 0.5, "chute": True},
    ],
    "bandeau": ["BERCY : LE CANAPÉ PLACÉ EN GARDE À VUE", "LE TIC TAC DEMANDE L'ASILE FISCAL", "LES ÉCONOMIES AURAIENT ÉTÉ APERÇUES EN SUISSE"],
    "gag": {"replique": 2, "prompt": "Flat 2D cartoon, thick black outlines, simple shapes. Three tired office workers in grey suits dig frantically under the cushions of a big orange sofa in a fancy ministry office, coins and papers flying, comedic, deadpan."},
}

SYSTEME = """Tu es une équipe d'auteurs comiques professionnels de la télévision française (le niveau des meilleures émissions satiriques). Tu écris « L'info en caoutchouc », un faux JT satirique quotidien de {secondes} secondes pour TikTok, joué par des personnages 100 % FICTIFS dessinés en cartoon.

PERSONNAGES (clés autorisées pour "p") :
{cast}

LE FORMAT : UN SEUL sujet d'actualité, celui qui est fourni, sans jamais s'en écarter. {nb} répliques, courtes (une ou deux phrases courtes). BUDGET STRICT : {mots} mots AU TOTAL pour tout le sketch (le temps de parole est limité).
- Réplique 0 = L'ACCROCHE (ouverture à froid, AVANT le générique) : le présentateur résume le sujet en UNE phrase drôle de 3 secondes maximum, qui donne envie de rester. C'est la vanne la plus forte du début.
- Ensuite : direct avec l'envoyée sur place et/ou l'invité.
- BOUCLE : la dernière réplique doit faire écho à l'accroche, pour que la vidéo s'enchaîne naturellement sur son début quand elle repasse en boucle.
{special}

RITUELS (ce qui fidélise le public) :
- L'envoyée Martine est toujours en direct d'un endroit absurde mais lié au sujet (« caché sous le bureau du ministre », « dans la photocopieuse de Bercy »…) : c'est le champ "lieu_direct".
- Le présentateur reste de marbre quoi qu'il arrive.
- Tu peux faire UN clin d'œil discret à un running gag récent de l'émission s'il colle au sujet (sinon, n'en fais pas) : {gags}

ARTICULATION (les voix sont synthétiques) : phrases courtes et simples, mots faciles à prononcer, pas d'enchaînement de sons compliqués, pas d'abréviations, une seule idée par phrase. Le spectateur doit tout comprendre du premier coup.

COMMENT FAIRE RIRE (méthode des auteurs professionnels, obligatoire) :
- L'ANGLE : pars de la contradiction ou de l'hypocrisie du sujet (ce que tout le monde pense sans le dire), puis exagère-la jusqu'à l'absurde, ou traduis-la en équivalent ridicule de la vie quotidienne. L'angle retenu t'est donné : tout le sketch le sert.
- ESCALADE : chaque réplique va un cran plus loin que la précédente, jamais de redescente.
- RÈGLE DE TROIS : au moins une fois, deux éléments normaux puis un troisième qui déraille.
- ÉCONOMIE : le mot drôle est le DERNIER mot ; zéro mot inutile après la chute ; si on peut couper un mot, coupe-le.
- LE CHOC DES DÉFAUTS : le comique naît des défauts fixes des personnages qui s'entrechoquent (présentateur impassible, envoyée au premier degré, invité de mauvaise foi).
- VISUEL : au moins une image drôle à voir (le plan gag), et chaque vanne doit rester drôle LUE en sous-titres, sans le son.
- Des images concrètes, précises et ridicules (« deux euros et un Tic Tac », « sous les coussins du canapé ») plutôt que des concepts.
- La chute est TOUJOURS le dernier mot de la réplique. Phrases courtes. Jamais d'explication de la blague, jamais de jeu de mots facile.
- Une blague du début revient en chute finale (rappel), de préférence retournée.
- Ton : {ton}. Pince-sans-rire, jamais méchant envers les gens.
- L'accroche (réplique 0) : le spectateur doit comprendre le sujet et sourire en 3 secondes.

RÈGLES ABSOLUES :
1. Faits : n'utilise QUE les faits présents dans les titres fournis. Aucun chiffre, date ou événement réel inventé. Les exagérations doivent être évidemment absurdes (personne ne doit les croire vraies).
2. Ne nomme AUCUNE personne réelle et n'attribue aucune citation à une personne réelle. Parle des institutions (« le gouvernement », « les députés », « un ministre », « Bercy »). Les noms de marques sont permis s'ils ne sont pas dénigrés.
3. On ne rit jamais des victimes ni des drames. Si le sujet concerne une personne réelle identifiable, la satire vise la situation, l'institution ou la communication, jamais la personne elle-même, et sans ajouter d'accusation. Aucune moquerie liée à l'origine, la religion, le genre, l'orientation, le handicap, l'âge ou l'apparence. Pas d'insulte, rien de sexuel, pas de violence.
4. Aucune information pratique sur des élections et aucun appel à voter.

FORMAT : rends le sketch avec l'outil rendre_sketch, avec exactement ces champs :
{{"sujet": "sujet en 1 à 3 mots, MAJUSCULES (affiché dans l'habillage)",
 "ecran": "texte de l'écran du plateau, max 14 caractères, MAJUSCULES",
 "invite_nom": "nom fictif et drôle de l'invité (prénom + nom évocateur)", "invite_role": "fonction de l'invité, avec « (fictif) », max 34 caractères",
 "invite_look": "{looks}",
 "lieu_direct": "lieu absurde du direct de l'envoyée, lié au sujet, max 26 caractères",
 "titre_accroche": "titre affiché en gros sur la première image (style « POV »), max 40 caractères, SANS emoji, qui donne envie de regarder",
 "question": "question courte et piquante pour faire réagir en commentaire (max 80 caractères), avec un emoji à la fin",
 "running_gag": "si tu crées un nouveau gag réutilisable dans de futurs épisodes, décris-le en une phrase (sinon chaîne vide)",
 "repliques": [{{"p": "presentateur|envoyee|invite", "t": "réplique affichée (max 150 caractères)", "d": "même texte avec nombres, sigles et pourcentages écrits en toutes lettres pour la voix (si différent)", "chute": true si la réplique se termine par une vanne, "attente": secondes de silence gênant avant la réplique (0.4 à 1.2, une seule fois max, juste avant la vanne finale ou une grosse vanne)}}],
 "bandeau": ["3 ou 4 fausses dépêches absurdes pour le bandeau défilant, MAJUSCULES, max 55 caractères, liées au sujet"],
 "gag": {{"replique": index (à partir de 0) d'une réplique de l'envoyée ou de l'invité qui décrit une scène visuelle drôle, "prompt": "description EN ANGLAIS de cette scène pour un générateur vidéo : commence par « Flat 2D cartoon, thick black outlines, simple shapes. », décris l'action en 1 à 2 phrases, sans texte écrit à l'écran, sans personne réelle"}},
 "legende": "légende TikTok accrocheuse (max 140 caractères), se termine par « Satire, personnages fictifs. »",
 "hashtags": ["5 à 7 hashtags sans #, minuscules, sans accents"],
 "sources": ["liens des titres réellement utilisés"]}}

EXEMPLE DE TON ET DE FORMAT (sujet d'une autre semaine, ne réutilise pas ses blagues) :
{exemple}"""

DOCTEUR = """Tu es maintenant « script doctor » pour une émission comique. Voici le sketch :
{sketch}

1. Pour chaque réplique, note mentalement sa force comique de 1 à 10.
2. Réécris les 3 répliques les plus faibles pour qu'elles soient franchement plus drôles (image plus concrète, chute plus courte et plus inattendue, escalade, règle de trois, rappel). Coupe chaque mot inutile après une chute.
3. Vérifie que l'accroche (réplique 0) fait sourire en 3 secondes, et que la dernière réplique est la meilleure vanne ET fait écho à l'accroche (boucle).
4. Vérifie l'articulation : phrases courtes, mots simples, faciles à dire à voix haute.
5. Coupe tout ce qui ralentit : le sketch doit tenir en {secondes} secondes ({nb} répliques).
Garde exactement les mêmes faits et toutes les règles (aucune personne réelle, aucun fait inventé). Rends le sketch complet corrigé avec l'outil rendre_sketch, même format."""

def construire_prompt(titres):
    liste = "\n".join(f"- [{t['source']}] {t['titre']} — {t['resume'][:300]} ({t['lien']})" for t in titres)
    return (f"SUJET IMPOSÉ : « {titres[0]['titre']} »\n"
            "Ce sujet fait en ce moment les gros titres de plusieurs médias. Voici les articles qui en parlent :\n" + liste +
            "\n\nÉcris le sketch UNIQUEMENT sur ce sujet précis : chaque réplique, chaque gag, chaque dépêche du bandeau et le plan gag doivent "
            "s'y rapporter directement. Aucun autre sujet, aucune digression. Trouve l'angle le plus ironique et le plus absurde, "
            "comme une équipe d'auteurs professionnels de la télévision.")

def _json(texte):
    m = re.search(r"\{.*\}", texte, re.S)
    if not m: raise ValueError("pas de JSON")
    return json.loads(m.group(0))

def _court(s, n): return str(s or "").strip()[:n]

def valider(sk, liens):
    reps, attente = [], False
    for r in sk.get("repliques", [])[:16]:
        p = r.get("p"); t = _court(r.get("t"), 170)
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
    if len(reps) < 4: raise ValueError(f"sketch trop court ({len(reps)} répliques)")
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
            "running_gag": _court(sk.get("running_gag"), 160),
            "repliques": reps, "bandeau": [_court(b, 60).upper() for b in sk.get("bandeau", []) if str(b).strip()][:4],
            "gag": gag,
            "legende": _court(sk.get("legende"), 160) or "L'actu du jour, en dessin animé. Satire, personnages fictifs.",
            "hashtags": [t for t in tags if t][:7] or ["satire", "humour", "actualite", "politique"],
            "sources": [s for s in sk.get("sources", []) if s in liens][:6]}

OUTIL = {"name": "rendre_sketch", "description": "Rendre le sketch au format demandé.",
         "input_schema": {"type": "object", "properties": {
             "sujet": {"type": "string"}, "ecran": {"type": "string"}, "invite_nom": {"type": "string"}, "invite_role": {"type": "string"},
             "invite_look": {"type": "string"}, "lieu_direct": {"type": "string"},
             "titre_accroche": {"type": "string"}, "question": {"type": "string"}, "running_gag": {"type": "string"},
             "repliques": {"type": "array", "items": {"type": "object", "properties": {
                 "p": {"type": "string"}, "t": {"type": "string"}, "d": {"type": "string"}, "chute": {"type": "boolean"}, "attente": {"type": "number"}},
                 "required": ["p", "t"]}},
             "bandeau": {"type": "array", "items": {"type": "string"}},
             "gag": {"type": "object", "properties": {"replique": {"type": "integer"}, "prompt": {"type": "string"}}},
             "legende": {"type": "string"}, "hashtags": {"type": "array", "items": {"type": "string"}},
             "sources": {"type": "array", "items": {"type": "string"}}},
             "required": ["sujet", "repliques", "legende"]}}

def _appel(client, systeme, messages):
    """Renvoie le sketch sous forme de dictionnaire. L'outil force un JSON toujours valide (fini les guillemets mal échappés)."""
    r = client.messages.create(model=MODELE, max_tokens=4000, system=systeme, messages=messages,
                               tools=[OUTIL], tool_choice={"type": "auto"})
    for b in r.content:
        if getattr(b, "type", "") == "tool_use": return b.input
    return _json("".join(getattr(b, "text", "") for b in r.content))

SPECIAL_DEMAIN = """- ÉPISODE SPÉCIAL DU DIMANCHE « LES INFOS DE DEMAIN » : après l'accroche, le présentateur annonce 3 ou 4 fausses brèves du futur (« Dans un an… », « En 2030… »), toutes sur CE sujet, chacune poussant la situation un cran plus loin dans l'absurde, avec une chute par brève ; l'envoyée ou l'invité peuvent réagir. L'écran du plateau affiche « EN 2030 »."""

def _mots(t):
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return {m for m in re.findall(r"[a-z]{5,}", t)}

def trop_long(sk):
    n = sum(len(r["t"].split()) for r in sk["repliques"])
    if LONGUEUR != "monetisable" and n > MOTS * 1.2: raise ValueError(f"trop long : {n} mots, maximum {MOTS}. Raccourcis chaque réplique")

def hors_sujet(sk, titres):
    """Refuse un sketch qui ne reprend aucun mot important du sujet imposé (le robot s'est éparpillé)."""
    sujet = _mots(titres[0]["titre"]) - {"direct", "selon", "apres", "contre", "entre", "leurs", "cette", "quand", "comment", "pourquoi"}
    texte = _mots(" ".join([sk["sujet"]] + [r["t"] for r in sk["repliques"]]))
    if sujet and len(sujet & texte) < 1:
        raise ValueError(f"hors sujet : le sketch doit parler de « {titres[0]['titre']} »")

ATELIER = """Tu es dans la salle des auteurs d'une émission satirique professionnelle. Sujet imposé et articles :
{sujet}

Propose 10 ANGLES COMIQUES différents sur CE sujet (et rien d'autre). Pour chacun : l'angle en une phrase (la contradiction ou l'hypocrisie exagérée, ou l'équivalent absurde de la vie quotidienne) et LA vanne la plus forte qu'il permet (courte, mot drôle à la fin).
Règles : aucune personne réelle visée, aucun fait inventé, pas de jeu de mots facile, pas de cliché. Rends-les avec l'outil proposer_angles."""

PRODUCTEUR = """Tu es le producteur impitoyable de l'émission : tu ne gardes que ce qui fait rire aux éclats un public TikTok français.
Voici 10 angles avec leur meilleure vanne :
{angles}
Note chaque angle de 1 à 10 (originalité, surprise, potentiel d'escalade sur 6 répliques, compréhensible en 3 secondes, drôle même lu sans le son). Rends les notes avec l'outil noter_angles."""

OUTIL_ANGLES = {"name": "proposer_angles", "description": "Proposer les angles comiques.",
                "input_schema": {"type": "object", "properties": {"angles": {"type": "array", "items": {"type": "object", "properties": {
                    "angle": {"type": "string"}, "vanne": {"type": "string"}}, "required": ["angle", "vanne"]}}}, "required": ["angles"]}}
OUTIL_NOTES = {"name": "noter_angles", "description": "Noter les angles.",
               "input_schema": {"type": "object", "properties": {"notes": {"type": "array", "items": {"type": "integer"}}}, "required": ["notes"]}}

def _outil(client, outil, texte):
    """Appel avec sortie structurée ; si le modèle répond en texte, on lui redemande du JSON pur."""
    msgs = [{"role": "user", "content": texte}]
    for essai in range(2):
        r = client.messages.create(model=MODELE, max_tokens=3000, messages=msgs, tools=[outil], tool_choice={"type": "auto"})
        for b in r.content:
            if getattr(b, "type", "") == "tool_use": return b.input
        brut = "".join(getattr(b, "text", "") for b in r.content)
        try: return _json(brut)
        except Exception:
            msgs = msgs + [{"role": "assistant", "content": brut or "…"},
                           {"role": "user", "content": f"Utilise l'outil {outil['name']} pour rendre ta réponse."}]
    raise ValueError("réponse inexploitable")

def meilleur_angle(client, titres):
    """Écrire 10 angles, les faire noter par un « producteur », garder le meilleur (et le second en réserve)."""
    try:
        sujet = "\n".join(f"- {t['titre']} — {t['resume'][:200]}" for t in titres[:6])
        r = _outil(client, OUTIL_ANGLES, ATELIER.format(sujet=sujet))
        liste_brute = r if isinstance(r, list) else r.get("angles") or next((v for v in r.values() if isinstance(v, list)), [])
        angles = [a for a in liste_brute if isinstance(a, dict) and a.get("angle")][:10]
        if not angles: print(f"Atelier d'angles : réponse inattendue ({str(r)[:150]})", flush=True); return ""
        liste = "\n".join(f"{k}. {a['angle']} → « {a['vanne']} »" for k, a in enumerate(angles))
        rn = _outil(client, OUTIL_NOTES, PRODUCTEUR.format(angles=liste))
        notes = rn if isinstance(rn, list) else rn.get("notes") or next((v for v in rn.values() if isinstance(v, list)), [])
        notes = [int(x) if str(x).lstrip("-").isdigit() else 0 for x in notes]
        ordre = sorted(range(len(angles)), key=lambda k: -(notes[k] if k < len(notes) else 0))
        a, b = angles[ordre[0]], angles[ordre[1]] if len(ordre) > 1 else None
        print(f"Angle retenu ({notes[ordre[0]] if notes else '?'}/10) : {a['angle']}", flush=True)
        return (f"\n\nANGLE COMIQUE RETENU par la salle des auteurs (construis tout le sketch dessus) : {a['angle']}\n"
                f"Vanne de départ possible : « {a['vanne']} »" + (f"\nAngle de réserve pour une vanne secondaire : {b['angle']}" if b else ""))
    except Exception as e:
        print(f"Atelier d'angles ignoré ({e})", flush=True); return ""

def ecrire_sketch(titres, essais=3, gags=(), special=False):
    import anthropic
    client = anthropic.Anthropic()
    gtxt = " ; ".join(g for g in gags if g)[:600] or "(aucun pour l'instant)"
    systeme = SYSTEME.format(mots=MOTS, special=SPECIAL_DEMAIN if special else "", gags=gtxt, secondes=SECONDES, nb=NB, ton=TON, cast="\n".join(f"- {k} : {v}" for k, v in CAST.items()), looks="|".join(LOOKS),
                             exemple=json.dumps(EXEMPLE, ensure_ascii=False, indent=0))
    message = construire_prompt(titres) + meilleur_angle(client, titres); liens = {t["lien"] for t in titres}; derniere = None
    for _ in range(essais):
        try:
            sk = valider(_appel(client, systeme, [{"role": "user", "content": message}]), liens)
            hors_sujet(sk, titres); trop_long(sk)
            break
        except Exception as e:
            derniere = e; sk = None
            message += f"\n\nTa réponse précédente était invalide ({e}). Rends-le avec l'outil rendre_sketch."
    if sk is None: raise RuntimeError(f"Sketch invalide après {essais} essais : {derniere}")
    # deuxième passe : réécriture des blagues faibles (si elle échoue, on garde la première version)
    try:
        brut = {k: sk[k] for k in ("sujet", "ecran", "invite_nom", "invite_role", "invite_look", "lieu_direct", "titre_accroche", "question",
                                   "running_gag", "repliques", "bandeau", "gag", "legende", "hashtags", "sources")}
        sk2 = _appel(client, systeme, [{"role": "user", "content": message}, {"role": "assistant", "content": json.dumps(brut, ensure_ascii=False)},
                                         {"role": "user", "content": DOCTEUR.format(sketch=json.dumps(brut, ensure_ascii=False, indent=0), secondes=SECONDES, nb=NB, mots=MOTS)}])
        sk2 = valider(sk2, liens); hors_sujet(sk2, titres); trop_long(sk2)
        sk2["sources"] = sk2["sources"] or sk["sources"]
        print("Script doctor : sketch amélioré", flush=True)
        return sk2
    except Exception as e:
        print(f"Script doctor ignoré ({e})", flush=True)
        return sk
