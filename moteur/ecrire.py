"""Écriture du sketch du jour par Claude (API Anthropic), à partir des vrais titres de l'actualité.
Format : un JT satirique sur UN seul sujet, avec trois personnages fictifs (présentateur, envoyée spéciale en direct, invité).
Deux passes : 1) l'auteur écrit ; 2) un « script doctor » réécrit les blagues les plus faibles."""
import json, os, re, unicodedata

MODELE = os.environ.get("MODELE_CLAUDE") or "claude-sonnet-5-5"
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
TON = TONS.get(os.environ.get("TON") or "farfelu", TONS["farfelu"])
CAST = {
    "presentateur": "Jean-Michel Plateau, présentateur. Calme olympien, pince-sans-rire, pose les questions simples qui font tout s'écrouler. C'est souvent lui qui lance la chute finale.",
    "envoyee": "Martine Couloir, envoyée spéciale (fictive) en direct sur le terrain (Assemblée, ministère, salon, sommet…). Blasée, a tout vu, décrit des scènes absurdes avec un sérieux total. Reine du détail concret ridicule.",
    "invite": "L'invité (fictif) du jour : un « expert », conseiller ou porte-parole d'une institution (jamais une personne réelle). Langue de bois, mauvaise foi, transforme chaque échec en victoire avec une logique absurde.",
}
LOOKS = ("chauve", "moustache")

EXEMPLE = {
    "sujet": "BUDGET 2027", "ecran": "BUDGET 2027", "invite_nom": "Hubert Rustine", "invite_role": "Conseiller (fictif) à Bercy", "invite_look": "chauve",
    "lieu_direct": "Assemblée",
    "repliques": [
        {"p": "presentateur", "t": "Les députés devaient trouver quatre milliards d'économies. Ils ont tout supprimé en six heures. Martine, sur place ?"},
        {"p": "envoyee", "t": "Jean-Michel, c'est historique. Pour une fois, l'Assemblée a vraiment bossé."},
        {"p": "envoyee", "t": "Dans le mauvais sens, mais elle a bossé.", "chute": True},
        {"p": "presentateur", "t": "Et à Bercy ?"},
        {"p": "envoyee", "t": "Le ministère est en PLS. Des fonctionnaires cherchent des économies sous les coussins du canapé.", "d": "Le ministère est en pé-elle-esse. Des fonctionnaires cherchent des économies sous les coussins du canapé."},
        {"p": "envoyee", "t": "Ils ont trouvé deux euros et un Tic Tac.", "chute": True},
        {"p": "envoyee", "t": "Le Tic Tac a été rejeté en commission.", "attente": 0.5, "chute": True},
        {"p": "presentateur", "t": "Et mardi ?"},
        {"p": "envoyee", "t": "Mardi, tout repart du texte d'origine. Bonne nouvelle : le Tic Tac est de retour.", "chute": True},
    ],
    "bandeau": ["BERCY : LE CANAPÉ PLACÉ EN GARDE À VUE", "LE TIC TAC DEMANDE L'ASILE FISCAL", "LES ÉCONOMIES AURAIENT ÉTÉ APERÇUES EN SUISSE"],
    "gag": {"replique": 4, "prompt": "Flat 2D cartoon, thick black outlines, simple shapes. Three tired office workers in grey suits dig frantically under the cushions of a big orange sofa in a fancy ministry office, coins and papers flying, comedic, deadpan."},
}

SYSTEME = """Tu es une équipe d'auteurs comiques professionnels de la télévision française (le niveau des meilleures émissions satiriques). Tu écris « L'info en caoutchouc », un faux JT satirique quotidien de {secondes} secondes pour TikTok, joué par des personnages 100 % FICTIFS dessinés en cartoon.

PERSONNAGES (clés autorisées pour "p") :
{cast}

LE FORMAT : UN SEUL sujet d'actualité, celui qui est fourni, sans jamais s'en écarter. Le présentateur lance, puis direct avec l'envoyée sur place et/ou l'invité. {nb} répliques, courtes (une ou deux phrases).

COMMENT FAIRE RIRE (méthode obligatoire) :
- Trouve UNE idée comique forte (le « jeu ») et pousse-la jusqu'au bout : chaque réplique monte d'un cran dans l'absurde.
- Des images concrètes, précises et ridicules (« deux euros et un Tic Tac », « sous les coussins du canapé ») plutôt que des concepts.
- La chute est TOUJOURS le dernier mot de la réplique. Phrases courtes. Jamais d'explication de la blague, jamais de jeu de mots facile.
- Une blague du début revient en chute finale (rappel), de préférence retournée.
- Ton : {ton}. Pince-sans-rire, jamais méchant envers les gens.
- Accroche dans la PREMIÈRE phrase : le spectateur doit comprendre le sujet et sourire en 3 secondes.

RÈGLES ABSOLUES :
1. Faits : n'utilise QUE les faits présents dans les titres fournis. Aucun chiffre, date ou événement réel inventé. Les exagérations doivent être évidemment absurdes (personne ne doit les croire vraies).
2. Ne nomme AUCUNE personne réelle et n'attribue aucune citation à une personne réelle. Parle des institutions (« le gouvernement », « les députés », « un ministre », « Bercy »). Les noms de marques sont permis s'ils ne sont pas dénigrés.
3. On ne rit jamais des victimes ni des drames. Aucune moquerie liée à l'origine, la religion, le genre, l'orientation, le handicap, l'âge ou l'apparence. Pas d'insulte, rien de sexuel, pas de violence.
4. Aucune information pratique sur des élections et aucun appel à voter.

FORMAT : rends le sketch avec l'outil rendre_sketch, avec exactement ces champs :
{{"sujet": "sujet en 1 à 3 mots, MAJUSCULES (affiché dans l'habillage)",
 "ecran": "texte de l'écran du plateau, max 14 caractères, MAJUSCULES",
 "invite_nom": "nom fictif et drôle de l'invité (prénom + nom évocateur)", "invite_role": "fonction de l'invité, avec « (fictif) », max 34 caractères",
 "invite_look": "{looks}",
 "lieu_direct": "lieu du direct de l'envoyée, 1 à 2 mots (ex. Assemblée, Bercy, Élysée, Sénat)",
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
2. Réécris les 3 répliques les plus faibles pour qu'elles soient franchement plus drôles (image plus concrète, chute plus courte et plus inattendue, escalade, rappel).
3. Vérifie que la toute dernière réplique est la meilleure vanne du sketch, sinon améliore-la.
4. Coupe tout ce qui ralentit : le sketch doit tenir en {secondes} secondes ({nb} répliques).
Garde exactement les mêmes faits et toutes les règles (aucune personne réelle, aucun fait inventé). Rends le sketch complet corrigé avec l'outil rendre_sketch, même format."""

def construire_prompt(titres):
    liste = "\n".join(f"- [{t['source']}] {t['titre']} — {t['resume'][:300]} ({t['lien']})" for t in titres)
    return ("LE SUJET DU JOUR — il fait en ce moment les gros titres de plusieurs médias. Voici tout ce qu'on sait :\n" + liste +
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
            "lieu_direct": _court(sk.get("lieu_direct"), 16) or "Assemblée",
            "repliques": reps, "bandeau": [_court(b, 60).upper() for b in sk.get("bandeau", []) if str(b).strip()][:4],
            "gag": gag,
            "legende": _court(sk.get("legende"), 160) or "L'actu du jour, en dessin animé. Satire, personnages fictifs.",
            "hashtags": [t for t in tags if t][:7] or ["satire", "humour", "actualite", "politique"],
            "sources": [s for s in sk.get("sources", []) if s in liens][:6]}

OUTIL = {"name": "rendre_sketch", "description": "Rendre le sketch au format demandé.",
         "input_schema": {"type": "object", "properties": {
             "sujet": {"type": "string"}, "ecran": {"type": "string"}, "invite_nom": {"type": "string"}, "invite_role": {"type": "string"},
             "invite_look": {"type": "string"}, "lieu_direct": {"type": "string"},
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

def ecrire_sketch(titres, essais=3):
    import anthropic
    client = anthropic.Anthropic()
    systeme = SYSTEME.format(secondes=SECONDES, nb=NB, ton=TON, cast="\n".join(f"- {k} : {v}" for k, v in CAST.items()), looks="|".join(LOOKS),
                             exemple=json.dumps(EXEMPLE, ensure_ascii=False, indent=0))
    message = construire_prompt(titres); liens = {t["lien"] for t in titres}; derniere = None
    for _ in range(essais):
        try:
            sk = valider(_appel(client, systeme, [{"role": "user", "content": message}]), liens)
            break
        except Exception as e:
            derniere = e; sk = None
            message += f"\n\nTa réponse précédente était invalide ({e}). Rends-le avec l'outil rendre_sketch."
    if sk is None: raise RuntimeError(f"Sketch invalide après {essais} essais : {derniere}")
    # deuxième passe : réécriture des blagues faibles (si elle échoue, on garde la première version)
    try:
        brut = {k: sk[k] for k in ("sujet", "ecran", "invite_nom", "invite_role", "invite_look", "lieu_direct", "repliques", "bandeau", "gag", "legende", "hashtags", "sources")}
        sk2 = _appel(client, systeme, [{"role": "user", "content": message}, {"role": "assistant", "content": json.dumps(brut, ensure_ascii=False)},
                                         {"role": "user", "content": DOCTEUR.format(sketch=json.dumps(brut, ensure_ascii=False, indent=0), secondes=SECONDES, nb=NB)}])
        sk2 = valider(sk2, liens)
        sk2["sources"] = sk2["sources"] or sk["sources"]
        print("Script doctor : sketch amélioré", flush=True)
        return sk2
    except Exception as e:
        print(f"Script doctor ignoré ({e})", flush=True)
        return sk
