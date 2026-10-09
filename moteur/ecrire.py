"""Écriture du sketch du jour par Claude (API Anthropic), à partir des vrais titres de l'actualité.
Format : un JT satirique sur UN seul sujet, avec trois personnages fictifs (présentateur, envoyée spéciale en direct, invité).
Deux passes : 1) l'auteur écrit ; 2) un « script doctor » réécrit les blagues les plus faibles."""
import json, os, re, unicodedata

MODELE = os.environ.get("MODELE_CLAUDE") or "claude-sonnet-5-5"
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

SYSTEME = """Tu es le meilleur auteur comique de France. Tu écris « L'info en caoutchouc », un faux JT satirique quotidien de 30 à 45 secondes pour TikTok, joué par des personnages 100 % FICTIFS dessinés en cartoon.

PERSONNAGES (clés autorisées pour "p") :
{cast}

LE FORMAT : UN SEUL sujet d'actualité, le plus drôle à traiter parmi les titres fournis. Le présentateur lance, puis direct avec l'envoyée sur place et/ou l'invité. 8 à 12 répliques, courtes (une ou deux phrases).

COMMENT FAIRE RIRE (méthode obligatoire) :
- Trouve UNE idée comique forte (le « jeu ») et pousse-la jusqu'au bout : chaque réplique monte d'un cran dans l'absurde.
- Des images concrètes, précises et ridicules (« deux euros et un Tic Tac », « sous les coussins du canapé ») plutôt que des concepts.
- La chute est TOUJOURS le dernier mot de la réplique. Phrases courtes. Jamais d'explication de la blague, jamais de jeu de mots facile.
- Une blague du début revient en chute finale (rappel), de préférence retournée.
- Ton : foutage de gueule bon enfant envers les institutions, la langue de bois et les travers du pouvoir. Pince-sans-rire, jamais méchant envers les gens.
- Accroche dans la PREMIÈRE phrase : le spectateur doit comprendre le sujet et sourire en 3 secondes.

RÈGLES ABSOLUES :
1. Faits : n'utilise QUE les faits présents dans les titres fournis. Aucun chiffre, date ou événement réel inventé. Les exagérations doivent être évidemment absurdes (personne ne doit les croire vraies).
2. Ne nomme AUCUNE personne réelle et n'attribue aucune citation à une personne réelle. Parle des institutions (« le gouvernement », « les députés », « un ministre », « Bercy »). Les noms de marques sont permis s'ils ne sont pas dénigrés.
3. Aucune moquerie liée à l'origine, la religion, le genre, l'orientation, le handicap, l'âge ou l'apparence. Pas d'insulte, rien de sexuel, pas de violence.
4. Aucune information pratique sur des élections et aucun appel à voter.

FORMAT : réponds UNIQUEMENT avec un objet JSON valide :
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
4. Coupe tout ce qui ralentit : le sketch doit tenir en 30 à 45 secondes (8 à 12 répliques).
Garde exactement les mêmes faits et toutes les règles (aucune personne réelle, aucun fait inventé). Réponds UNIQUEMENT avec le JSON complet corrigé, même format."""

def construire_prompt(titres):
    liste = "\n".join(f"- [{t['source']}] {t['titre']} — {t['resume'][:250]} ({t['lien']})" for t in titres)
    return "TITRES POLITIQUES DES DERNIÈRES 36 HEURES :\n" + liste + "\n\nChoisis LE sujet le plus drôle à traiter et écris le sketch du jour."

def _json(texte):
    m = re.search(r"\{.*\}", texte, re.S)
    if not m: raise ValueError("pas de JSON")
    return json.loads(m.group(0))

def _court(s, n): return str(s or "").strip()[:n]

def valider(sk, liens):
    reps, attente = [], False
    for r in sk.get("repliques", [])[:14]:
        p = r.get("p"); t = _court(r.get("t"), 170)
        if p not in CAST or not t: continue
        x = {"p": p, "t": t}
        if r.get("d"): x["d"] = _court(r["d"], 260)
        if r.get("chute"): x["chute"] = True
        try: a = float(r.get("attente") or 0)
        except (TypeError, ValueError): a = 0
        if a > 0 and not attente: x["attente"] = min(1.2, max(0.3, a)); attente = True
        reps.append(x)
    if len(reps) < 5: raise ValueError(f"sketch trop court ({len(reps)} répliques)")
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

def _appel(client, systeme, messages):
    r = client.messages.create(model=MODELE, max_tokens=4000, system=systeme, messages=messages)
    return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")

def ecrire_sketch(titres, essais=3):
    import anthropic
    client = anthropic.Anthropic()
    systeme = SYSTEME.format(cast="\n".join(f"- {k} : {v}" for k, v in CAST.items()), looks="|".join(LOOKS),
                             exemple=json.dumps(EXEMPLE, ensure_ascii=False, indent=0))
    message = construire_prompt(titres); liens = {t["lien"] for t in titres}; derniere = None
    for _ in range(essais):
        texte = _appel(client, systeme, [{"role": "user", "content": message}])
        try:
            sk = valider(_json(texte), liens)
            break
        except Exception as e:
            derniere = e; sk = None
            message += f"\n\nTa réponse précédente était invalide ({e}). Réponds uniquement avec le JSON demandé."
    if sk is None: raise RuntimeError(f"Sketch invalide après {essais} essais : {derniere}")
    # deuxième passe : réécriture des blagues faibles (si elle échoue, on garde la première version)
    try:
        brut = {k: sk[k] for k in ("sujet", "ecran", "invite_nom", "invite_role", "invite_look", "lieu_direct", "repliques", "bandeau", "gag", "legende", "hashtags", "sources")}
        texte = _appel(client, systeme, [{"role": "user", "content": message}, {"role": "assistant", "content": json.dumps(brut, ensure_ascii=False)},
                                         {"role": "user", "content": DOCTEUR.format(sketch=json.dumps(brut, ensure_ascii=False, indent=0))}])
        sk2 = valider(_json(texte), liens)
        sk2["sources"] = sk2["sources"] or sk["sources"]
        print("Script doctor : sketch amélioré", flush=True)
        return sk2
    except Exception as e:
        print(f"Script doctor ignoré ({e})", flush=True)
        return sk
