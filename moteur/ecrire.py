"""Moteur humoristique : écriture du sketch du jour par Claude (API Anthropic).
Les consignes d'auteur sont dans moteur/prompts/moteur_humour.md (moteur de satire professionnel fourni par l'utilisateur).
Étapes : 1) sélection du sujet parmi plusieurs candidats notés sur 10 (avec vérification web si disponible) et choix de l'angle ;
2) écriture ; 3) contrôle qualité noté sur 100, jusqu'à 4 retouches si la note est sous le seuil (90 par défaut), puis changement de sujet si le sketch reste faible."""
import difflib, json, os, re, unicodedata
ICI = os.path.dirname(os.path.abspath(__file__))
MINI = (os.environ.get("FORMAT") or "").strip().lower() == "mini"         # gag éclair de 8 à 20 s
STYLE_LIBRE = open(os.path.join(ICI, "prompts", "style_mini.md" if MINI else "style_libre.md"), encoding="utf-8").read()
MOTEUR_HUMOUR = open(os.path.join(ICI, "prompts", "moteur_humour.md"), encoding="utf-8").read()

MODELE = os.environ.get("MODELE_CLAUDE") or "claude-opus-5-5"          # Opus : humour plus fin (réglable dans l'appli)
# réglages de la régie (variables du dépôt)
LONGUEURS = {"eclair": ("4 à 8", "15 à 22"), "pro": ("10 à 16", "60 à 90"), "courte": ("5 à 6", "20 à 25"), "normale": ("7 à 9", "30 à 40"), "longue": ("9 à 12", "40 à 55"),
             "monetisable": ("13 à 16", "60 à 75")}   # format long : plus d'une minute (rémunération TikTok)
TONS = {"clash": "CLASH, foutage de gueule direct (le style préféré du public) : on compare l'actu à la vie de tous les jours avec une mauvaise foi assumée (« Ils ont trouvé 3 000 profs en 24 h. Moi, j'ai mis trois semaines à trouver un plombier. »), on balance des hypothèses absurdes en « soit… soit… » (« soit c'est un miracle, soit ils ont recruté au rayon surgelés »), l'invité répond du tac au tac en aggravant son cas (« ils ont été décongelés ce matin »), et la CHUTE finale est une FAUSSE VÉRITÉ IRONIQUE sur le sujet : une phrase rassurante, au ton officiel, affirmée avec aplomb, que la fin de la phrase contredit aussitôt en révélant la réalité (« Rassurez-vous : il n'y a aucune pénurie de profs. Il suffit de ne plus demander de diplôme. »). Phrases courtes, punchlines sèches, comme entre potes qui chambrent",
        "farfelu": "gags farfelus et ironie pince-sans-rire : situations délirantes, images absurdes et très concrètes, ironie froide envers les institutions et la langue de bois",
        "bon_enfant": "foutage de gueule bon enfant envers les institutions, la langue de bois et les travers du pouvoir",
        "piquant": "satire mordante et sans pitié envers les institutions, les décisions et la langue de bois (jamais envers les gens pour ce qu'ils sont)",
        "absurde": "absurde total façon sketch surréaliste : situations délirantes poussées très loin, logique folle mais implacable"}
LONGUEUR = os.environ.get("LONGUEUR") or "pro"
NB, SECONDES = LONGUEURS.get(LONGUEUR, LONGUEURS["pro"])
NB_MAX = int(NB.split()[-1])
MOTS = {"eclair": 60, "pro": 190, "courte": 60, "normale": 90, "longue": 130, "monetisable": 200}.get(LONGUEUR, 190)
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
   "t": "Rassurez-vous : il n'y a aucune pénurie de profs. Il suffit de ne plus demander de diplôme.",
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

PERSONNES RÉELLES : tu peux citer une personnalité publique uniquement pour un fait vérifié présent dans les sources (ce qu'elle a réellement dit ou fait). Tu ne lui fais JAMAIS dire ou faire quoi que ce soit d'inventé, même pour rire : la caricature passe par nos personnages fictifs. Aucune consigne de vote.

HUMOUR NOIR ASSUMÉ, SANS FILTRE (règle du propriétaire) : aucune autocensure. Va au bout de chaque vanne, ne l'adoucis jamais, ne t'excuse jamais, aucune morale. Autorisés et encouragés : l'humour noir (mort, maladie, vieillesse, misère, déprime, échec), le cynisme total, la méchanceté envers les puissants, l'auto-dérision violente, l'humour lourd et beauf assumé, les grossièretés, les gros mots et les insultes bien salées entre personnages, l'humour sur le sexe et les sous-entendus bien gras entre adultes (sans description explicite), la guerre des sexes et les clichés de couple, les vannes sur les masculinistes, les féministes, les « mâles alpha » et les donneurs de leçons de tous bords, la satire des religions comme institutions (rituels absurdes, hypocrisie, interdits, business de la foi, gourous), les sujets tabous du quotidien. Une vanne qui choque mais fait rire vaut mieux qu'une vanne sage.
SEULES LIMITES (non négociables) : on rit des comportements, des idées et des institutions, jamais de ce que les gens sont — aucune vanne qui rabaisse des personnes pour leur origine, leur couleur de peau, leur orientation sexuelle, leur handicap, ni les croyants ou les femmes / les hommes en tant que groupe inférieur (on se moque du masculiniste, pas des hommes ; du dogme, pas des fidèles) ; rien de sexuel impliquant des mineurs ; aucune fausse citation ni fausse action attribuée à une personne réelle comme si elle était vraie ; on ne se moque pas des vraies victimes d'un vrai drame (on peut en revanche massacrer les responsables).

STYLE MAISON (validé par le public) : {ton}

DURÉE : {secondes} secondes, {nb} répliques, entre {mots_min} et {mots} mots prononcés au total. Réplique 0 = l'accroche du présentateur (2 secondes, la punchline la plus forte du début). CHUTE = FAUSSE VÉRITÉ IRONIQUE (règle n°1 du propriétaire) : la dernière réplique est une contre-vérité assumée sur le SUJET PRINCIPAL — une affirmation rassurante, façon communiqué officiel (« Rassurez-vous : … », « Bonne nouvelle : … », « Soyons clairs : … »), aussitôt démentie dans la même phrase par un fait réel ou sa conséquence directe, ce qui révèle la vérité du sujet par l'ironie (ex. : « Rassurez-vous : la justice internationale reste totalement indépendante. Elle a juste six mois pour obéir. »). Elle nomme le sujet ou ses acteurs ; jamais une blague annexe, jamais un rappel d'un gag du sketch, jamais une métaphore. Tout le sketch monte vers elle.
PAS DE MÉTAPHORE FILÉE (règle n°2 du propriétaire) : le sketch parle du sujet lui-même, sans détour, du début à la fin. Interdit de transposer l'actualité dans un autre univers (jeu de société, restaurant, sport, école, cuisine…) ou de filer une image sur plusieurs répliques. Les vannes viennent des faits réels poussés à l'absurde, de la mauvaise foi de l'invité et des comparaisons express d'une ligne.
Voix : phrases courtes, faciles à dire, une idée par phrase. Nombres, sigles et pourcentages en toutes lettres dans le champ "d".
JEU DES ACTEURS : le champ "d" (texte prononcé) accepte des indications de jeu entre crochets, EN ANGLAIS, que la voix interprète : [laughs], [laughing], [sighs], [angry], [shouting], [whispers], [sarcastic], [nervous laugh], [gasps], [annoyed], [excited], [deadpan], [crying]… Mets-en dans la plupart des répliques (une ou deux par réplique, au bon endroit), pour un jeu vivant, des rires et des coups de colère. Hésitations et coupures s'écrivent aussi (« euh… », « attends- »). Jamais de crochets dans le champ "t" (affiché à l'écran).
{special}
Running gags récents de l'émission (un clin d'œil possible s'il colle au sujet) : {gags}
ANTI-RÉPÉTITION — sujets et vannes des derniers épisodes, à NE PAS refaire : {recents}

LIVRABLES : rends tout avec l'outil rendre_sketch, dans ce format JSON strict (A→F du cahier des charges inclus) :
{{"sujet": "1 à 3 mots, MAJUSCULES", "ecran": "max 14 caractères, MAJUSCULES", "titre_accroche": "max 40 caractères, sans emoji",
 "fil": "pitch en une phrase + étapes numérotées de l'histoire (sketch long)", "verite": "la vérité crue du sujet principal, que la chute révèle par une fausse vérité ironique", "concept": "B. concept et titre", "format": "B. format choisi", "angle": "B. angle comique",
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
Écris ensuite, AVANT tout le reste, la VÉRITÉ du sujet (ce qui se passe vraiment derrière l'annonce : qui y gagne, qui paie, quelle hypocrisie, fondé sur les faits), puis la CHUTE qui la révèle sous forme de fausse vérité ironique (affirmation rassurante démentie dans la même phrase).
Rends ton choix avec l'outil choisir_sujet."""

CRITIQUE = """Étape 8 du cahier des charges : relis ce sketch comme un auteur exigeant et note-le sur 100, honnêtement (ne gonfle jamais la note) :
originalité du concept /20, punchlines /25, rythme /15, pertinence satirique /15, dialogues /10, potentiel visuel /10, chute /5.
SUJET PRINCIPAL : {sujet}
Fiche et script (format vidéo animée {secondes} s, voix synthétiques ; les actions visuelles et le découpage comptent pour le potentiel visuel) :
{sketch}
{exigences}
Humour noir, cru et sans filtre voulu par le propriétaire : ne retire JAMAIS de points parce qu'une vanne est noire, vulgaire ou choquante ; retire-en si une vanne est sage, prudente ou édulcorée. Lourd, beauf, salace, insultant entre personnages, satire des religions et des masculinistes / féministes : tout est permis. (Seule exception : une vanne qui rabaisse des gens pour leur origine, leur couleur de peau, leur orientation, leur handicap, ou les croyants / un sexe en tant que groupe, ou qui vise de vraies victimes, est à supprimer.)
Rends la note avec l'outil noter_sketch. Le champ "critique" est OBLIGATOIRE et non vide : cite les répliques faibles (numéro + pourquoi) et propose ce qu'il faut changer."""

REECRITURE = """Ton sketch a obtenu {note}/100 (objectif : au moins {seuil}). Critique du relecteur :
{critique}
{reserve}
RETOUCHE CIBLÉE, comme un punch-up de salle d'auteurs : GARDE telles quelles les répliques qui fonctionnent et la chute si elle n'est pas critiquée. Remplace chaque réplique critiquée par une meilleure vanne (pioche dans les munitions du jury si elles conviennent), supprime les répliques de remplissage. Chute en fausse vérité ironique sur le sujet principal, aucune métaphore filée ; en sketch long, garde UNE histoire continue et répare toute scène qui casse le fil. Mêmes faits, mêmes règles. Rends le sketch complet avec l'outil rendre_sketch."""

EXIGENCES_ACTU = """EXIGENCES DU PROPRIÉTAIRE :
1. La chute (dernière réplique) est une FAUSSE VÉRITÉ IRONIQUE sur CE sujet principal : affirmation rassurante au ton officiel, démentie dans la même phrase par la réalité. Une chute qui est un gag annexe, un rappel d'une blague du sketch, une métaphore ou une simple constatation (« chute_vraie » = false) plafonne la note à 70.
2. Aucune métaphore filée : le sketch parle du sujet lui-même. S'il transpose l'actualité dans un autre univers (jeu, restaurant, sport…) ou file une image sur plusieurs répliques (« metaphore_filee » = true), la note est plafonnée à 70."""

EXIGENCES_LIBRE = """EXIGENCES DU PROPRIÉTAIRE (sketch libre, sans actualité) :
1. La chute (dernière réplique) est une punchline qui retourne toute la situation, sur CE sujet (fausse vérité ironique, aveu, retournement) ; un gag annexe ou un simple rappel d'une blague du sketch (« chute_vraie » = false) plafonne la note à 70.
2. Aucune métaphore filée : le sketch reste dans la situation elle-même (« metaphore_filee » = true : note plafonnée à 70).
3. La situation doit être immédiatement reconnaissable par n'importe qui (« c'est trop moi / c'est trop ma mère »). Ici, « pertinence satirique » = justesse de l'observation du quotidien.
4. FIL CONDUCTEUR ET CONTINUITÉ (sketch long) : une seule histoire continue. Vérifie CHAQUE scène par rapport à la précédente et à la suivante :
   l'enchaînement est-il cohérent (conséquence logique, rien de contradictoire, mêmes personnages et même enjeu), fluide (on passe naturellement de l'une à l'autre, le carton annonce bien le saut), juste (faits internes, personnages qui se souviennent) et limpide (compris en une seconde par quelqu'un qui découvre la vidéo) ?
   Note chaque passage dans « continuite » (un élément par passage : « scène 1 → 2 : OK » ou le problème précis et sa correction). Si un seul passage pose problème, ou si le sketch enchaîne des vannes sans histoire, « fil_continu » = false et la note est plafonnée à 70."""

TECHNIQUE_PUNCHLINE = """TECHNIQUE D'UNE PUNCHLINE QUI FAIT HURLER DE RIRE :
- le mot qui tue est le DERNIER mot de la phrase (rien après lui) ;
- la phrase la plus courte possible : 8 à 20 mots, deux temps « affirmation rassurante. / démenti sec. » ;
- le démenti est un fait réel ou sa conséquence directe, dit de la façon la plus brutale et la plus inattendue ;
- détourne la langue de bois officielle (« Rassurez-vous », « Soyons clairs », « Bonne nouvelle », « Le gouvernement tient à préciser ») ;
- surprise totale : si le public peut deviner la fin, elle est ratée ; préfère le retournement, l'aveu involontaire, le chiffre qui tue ;
- jamais d'explication, jamais de jeu de mots facile, jamais de « en fait » ni de « c'est-à-dire »."""

ATELIER = """ATELIER DE VANNES — sujet : « {sujet} »
Articles :
{articles}
{contexte}
{technique}

1. Écris 15 vannes d'une ligne sur CE sujet (faits réels poussés à l'absurde, mauvaise foi d'un porte-parole, comparaison express avec la vie quotidienne, chiffre retourné). Aucune métaphore filée, aucune vanne qui pourrait s'appliquer à un autre sujet.
2. Écris 15 CHUTES en {type_chute} sur ce sujet, toutes différentes dans leur mécanique (aveu, chiffre, retournement, langue de bois, conséquence absurde mais logique).
Rends le tout avec l'outil atelier_vannes."""

JURY = """Tu es le jury d'une émission satirique française : un public TikTok de 18-35 ans, impitoyable, fan d'humour noir, qui ne rit que si c'est vraiment drôle, surprenant, méchant et osé. Une vanne sage, prudente ou consensuelle ne dépasse pas 4. Le lourd, le beauf, le salace, les insultes et la satire des religions ou des masculinistes / féministes sont bienvenus. (Une vanne qui rabaisse des gens pour leur origine, leur couleur de peau, leur orientation, leur handicap, ou les croyants / un sexe en tant que groupe, ou qui se moque de vraies victimes, vaut 0.)
Sujet : « {sujet} »
VANNES :
{vannes}
CHUTES (fausses vérités ironiques) :
{chutes}
Donne à chaque vanne et à chaque chute une note de rire sur 10 (10 = on se plie en deux, 5 = sourire poli, 3 = rien). Sois dur : une chute prévisible, longue, expliquée ou hors sujet ne dépasse pas 4.
Puis désigne les 6 meilleures vannes et LA meilleure chute ; si tu vois comment rendre la meilleure chute encore plus percutante (plus courte, mot qui tue à la fin), donne-en la version affûtée. Rends le tout avec l'outil jury."""

PERSOS_DEFAUT = {
    "PERSO_JOJO": "le pote radin et de mauvaise foi, qui ne lâche jamais rien et a toujours une excuse prête",
    "PERSO_KEVIN": "le naïf un peu mytho, roi des plans foireux, qui croit tout ce qu'on lui dit et s'enfonce à chaque réplique",
    "PERSO_LILA": "la lucide cash, qui s'énerve vite et balance tout haut les vérités que personne n'ose dire",
}
def personnalites():
    """Bloc « personnages » du mode libre (réglage PERSONNALITES de la régie : fixes = caractère constant d'une vidéo à l'autre)."""
    fixes = (os.environ.get("PERSONNALITES") or "fixes").strip().lower() != "libres"
    def p(cle): return (os.environ.get(cle) or "").strip()[:300] or PERSOS_DEFAUT[cle]
    if fixes:
        return (f'  · "presentateur" = JOJO (bonnet orange) : {p("PERSO_JOJO")} ;\n'
                f'  · "invite" = KÉVIN (casquette à l\'envers) : {p("PERSO_KEVIN")} ;\n'
                f'  · "envoyee" = LILA (nœud rose) : {p("PERSO_LILA")}.\n'
                "  PERSONNALITÉS FIXES (réglage du propriétaire) : chacun garde EXACTEMENT ce caractère, ses tics et sa façon de parler, "
                "d'une vidéo à l'autre ; le public doit les reconnaître et anticiper leurs réactions. Fais jouer ces personnalités dans les vannes.")
    return ('  · "presentateur" = JOJO (bonnet orange) ; "invite" = KÉVIN (casquette à l\'envers) ; "envoyee" = LILA (nœud rose).\n'
            "  PERSONNALITÉS LIBRES (réglage du propriétaire) : donne à chacun le caractère qui sert le mieux l'histoire du jour.")

JEU = """- JEU D'ACTEUR RÉALISTE (règle du propriétaire : une vraie scène, jamais une lecture de texte) :
  · Dans "d", CHAQUE réplique commence par l'émotion vraie du moment en indication anglaise entre crochets ([annoyed], [laughing], [sarcastic], [crying], [shouting], [whispers], [nervous laugh], [sighs], [disgusted], [excited], [panicked], [deadpan]…), et peut en avoir une 2e au milieu (rire qui monte, soupir avant la vanne).
  · Écris l'oral vivant : hésitations (« euh… », « attends… »), reprises (« non mais — non. »), respiration (« … »), mots appuyés, phrases qui se coupent.
  · INTERRUPTIONS ET CHEVAUCHEMENTS : quand un personnage en coupe un autre, la réplique coupée finit par « — » et la suivante a "chevauche": true (elle démarre par-dessus la fin de la précédente). Utilise aussi de courtes réactions par-dessus (« Quoi ?! », « Hein ? », un rire, « Pff… ») avec "chevauche": true. 2 à 4 fois par sketch long, 1 fois dans un gag éclair.
  · RYTHME : "attente" (en secondes, 0 à 1,2) = silence AVANT la réplique : un blanc gênant avant une réponse qui tue, un temps avant la chute finale (0,5 à 0,8). Les échanges qui s'énervent s'enchaînent sans blanc.
  · Toute la palette : rire, colère, joie, peine, gêne, panique, mépris, fierté ; l'émotion change en cours de scène quand la situation bascule.
"""

LIBRE = """
═══════════════════════════════════════════
MODE « SKETCH LIBRE » (prioritaire sur TOUT ce qui précède)
═══════════════════════════════════════════
Aujourd'hui, PAS D'ACTUALITÉ : ignore les étapes de recherche, de vérification et de sélection d'actualité, la règle des gros titres, les faits réels et les sources. Le sujet est une SITUATION DU QUOTIDIEN que tout le monde a vécue (couple, famille, boulot, école, voisins, courses, transports, téléphone, réseaux sociaux, administration, sport, vacances…), observée avec une méchanceté tendre et poussée jusqu'à l'absurde.
- PAS DE JT : oublie le présentateur, l'envoyée, l'invité, le plateau et le direct. Le sketch est une scène de dessin animé jouée par nos trois personnages (petits bonshommes blancs à grosse tête ronde), avec les clés "p" habituelles :
{persos}
  Utilise leurs prénoms. 1 à 3 personnages selon la scène (souvent 2 face à face). Le premier à parler peut être n'importe lequel.
- DÉCOUPAGE POUR L'ANIMATION (obligatoire) : "decoupage" = 1 à 5 scènes ; pour chacune : "repliques" (indices), "decor" = le décor EN ANGLAIS, sans aucun personnage : le lieu PRÉCIS de l'histoire + 2 ou 3 objets visibles qui servent le gag (« a narrow apartment building hallway, a closed front door with a peephole, a torn delivery notice on the floor », « a supermarket self-checkout machine with a red error light, a shopping basket full of groceries »). Si l'histoire reste au même endroit, recopie EXACTEMENT le même texte de décor d'une scène à l'autre. « plain » = fond uni (gags éclair surtout), "titre" = pour un SKETCH LONG : construis-le en 2 à 4 GAGS successifs sur la même situation (un gag = une scène, avec sa propre montée et sa propre vanne de fin, le dernier gag porte la chute finale) ; chaque gag à partir du 2e est annoncé par un carton plein écran : écris son texte, court et clair (« Le lendemain… », « Deux heures plus tard… », « Pendant ce temps, chez Kévin… », « Au boulot… ») ; pour un GAG ÉCLAIR, les 2 à 6 mots affichés en haut pendant ce temps de la blague. "effet" = "pluie_billets", "tremblement" ou vide.
- Une réplique peut faire tenir un objet au personnage : "objet" = telephone, billet, portefeuille, micro, verre ou cafe.
- Aucune personne réelle, aucune marque, aucune actualité.
- "faits_reels" : liste vide ; "inventions" : tout ; "sources" : liste vide ; "resume_factuel" : une phrase qui résume la situation.
- La chute : une punchline qui retourne toute la situation (fausse vérité ironique, aveu involontaire, retournement) ; même exigence de mot qui tue à la fin.
- Anti-répétition : ne reprends aucune situation de la liste des épisodes récents.
- FIL CONDUCTEUR (sketch long, règle n°1 du propriétaire) : UNE SEULE histoire continue, du début à la fin. Écris d'abord le champ "fil" :
  le pitch en une phrase (qui veut quoi, quel est l'obstacle), puis les étapes numérotées de l'histoire.
  · Mêmes personnages, même situation, même enjeu dans toutes les scènes ; aucun sujet nouveau en route.
  · Chaque scène est la CONSÉQUENCE directe de la précédente (« à cause de ça… donc… ») et fait monter le même problème d'un cran.
  · Pas de liste de vannes indépendantes : les blagues servent l'histoire, chaque réplique fait avancer l'action ou la relation.
  · Un détail planté au début (objet, phrase, mensonge) revient à la fin ; la chute finale RÉSOUT ou retourne l'enjeu de départ.
  · Logique interne juste : les personnages se souviennent de ce qui a été dit, rien ne contredit une scène précédente, les lieux et les moments s'enchaînent logiquement (le carton annonce clairement le saut de temps ou de lieu).
  · Limpide : quelqu'un qui découvre la vidéo comprend en une seconde qui parle, où on est et ce qui se passe, à chaque scène.
{jeu}{serie}{accroche}- DICTION : phrases simples et bien articulables, pas de mots collés ni d'abréviations illisibles à l'oral dans "d" (« je sais pas » ou « j'sais pas », jamais « chais pas »), au plus 2 indications de jeu par réplique.
- LÉGENDE TIKTOK (référencement) : "legende" = 1 phrase courte qui donne envie de regarder jusqu'au bout + "question" = une question qui pousse à commenter ou à identifier un ami (« Tag le Kévin de ta bande », « Team Jojo ou team Lila ? ») ; "hashtags" = 4 à 6 mots-clés sans # : 2 larges (humour, pov, sketch, animation), 2 ou 3 précis du sujet (ceux que le public tape dans la recherche), jamais de hashtag trompeur.
- "titre_accroche" : le titre affiché en haut de l'écran, au format « POV : … » ou « Quand … » (40 caractères max).

{style}"""

IDEES = """Propose 8 situations du quotidien pour un sketch animé de {secondes} secondes : chacune vécue par presque tout le monde, avec un vrai potentiel de vanne (frustration universelle, hypocrisie sociale, petite humiliation, absurdité d'une règle). Variées (pas deux fois le même thème), et chacune construite sur une des mécaniques de la fiche de style ci-dessous (dis laquelle dans la description). Titre au format « POV : … » ou « Quand … ».

{style}
Déjà traitées récemment, à NE PAS reprendre : {recents}
Pour chacune : un titre court et une description de 2 phrases qui dit ce qui est drôle. Rends-les avec l'outil proposer_idees."""

SELECTION_LIBRE = """Voici les situations proposées pour le sketch libre du jour :
{candidats}

Note chacune sur 10 (potentiel comique, reconnaissance immédiate, originalité de l'angle, potentiel visuel). Choisis celle qui permet le MEILLEUR sketch (indices [0] à [{dernier}]), trouve son angle comique, écris la VÉRITÉ que tout le monde pense sur cette situation, puis la CHUTE. Rends ton choix avec l'outil choisir_sujet."""

def _schema(props, requis):
    return {"type": "object", "properties": props, "required": requis}

OUTIL = {"name": "rendre_sketch", "description": "Rendre le sketch complet (livrables A à F).",
         "input_schema": _schema({
             "sujet": {"type": "string"}, "ecran": {"type": "string"}, "titre_accroche": {"type": "string"},
             "fil": {"type": "string"}, "verite": {"type": "string"}, "concept": {"type": "string"}, "format": {"type": "string"}, "angle": {"type": "string"}, "resume_factuel": {"type": "string"},
             "faits_reels": {"type": "array", "items": {"type": "string"}}, "inventions": {"type": "array", "items": {"type": "string"}},
             "decoupage": {"type": "array", "items": _schema({"scene": {"type": "string"}, "repliques": {"type": "array", "items": {"type": "integer"}},
                                                              "decor": {"type": "string"}, "titre": {"type": "string"}, "effet": {"type": "string"},
                                                              "lieu": {"type": "string"}, "son": {"type": "string"}, "duree": {"type": "number"}}, ["scene"])},
             "invite_nom": {"type": "string"}, "invite_role": {"type": "string"}, "invite_look": {"type": "string"}, "lieu_direct": {"type": "string"},
             "question": {"type": "string"}, "running_gag": {"type": "string"},
             "repliques": {"type": "array", "items": _schema({"p": {"type": "string"}, "t": {"type": "string"}, "d": {"type": "string"},
                                                              "chute": {"type": "boolean"}, "attente": {"type": "number"}, "objet": {"type": "string"},
                                                              "chevauche": {"type": "boolean"}}, ["p", "t"])},
             "serie_titre": {"type": "string"}, "resume_episode": {"type": "string"}, "teaser": {"type": "integer"},
             "bandeau": {"type": "array", "items": {"type": "string"}},
             "gag": _schema({"replique": {"type": "integer"}, "prompt": {"type": "string"}}, []),
             "legende": {"type": "string"}, "hashtags": {"type": "array", "items": {"type": "string"}}, "sources": {"type": "array", "items": {"type": "string"}}},
             ["sujet", "repliques", "legende"])}
OUTIL_CHOIX = {"name": "choisir_sujet", "description": "Notes des candidats, sujet choisi et angle.",
               "input_schema": _schema({"notes": {"type": "array", "items": _schema({"index": {"type": "integer"}, "note": {"type": "number"},
                                                                                      "raison": {"type": "string"}}, ["index", "note"])},
                                        "choix": {"type": "integer"}, "angle": {"type": "string"},
                                        "verite": {"type": "string", "description": "La vérité crue du sujet en une phrase."},
                                        "chute": {"type": "string", "description": "La chute : fausse vérité ironique qui révèle cette vérité."},
                                        "faits_verifies": {"type": "array", "items": {"type": "string"}}}, ["choix", "angle", "verite"])}
OUTIL_ATELIER = {"name": "atelier_vannes", "description": "15 vannes d'une ligne et 15 chutes en fausse vérité ironique.",
                 "input_schema": _schema({"vannes": {"type": "array", "items": {"type": "string"}},
                                          "chutes": {"type": "array", "items": {"type": "string"}}}, ["vannes", "chutes"])}
OUTIL_JURY = {"name": "jury", "description": "Notes de rire et sélection.",
              "input_schema": _schema({"notes_vannes": {"type": "array", "items": {"type": "number"}},
                                       "notes_chutes": {"type": "array", "items": {"type": "number"}},
                                       "meilleures_vannes": {"type": "array", "items": {"type": "integer"}},
                                       "meilleure_chute": {"type": "integer"}, "chute_affutee": {"type": "string"}},
                                      ["notes_chutes", "meilleures_vannes", "meilleure_chute"])}
OUTIL_IDEES = {"name": "proposer_idees", "description": "Situations du quotidien pour un sketch.",
               "input_schema": _schema({"idees": {"type": "array", "items": _schema({"titre": {"type": "string"}, "description": {"type": "string"}},
                                                                                    ["titre", "description"])}}, ["idees"])}
OUTIL_NOTE = {"name": "noter_sketch", "description": "Note qualité sur 100 et critique.",
              "input_schema": _schema({"chute_vraie": {"type": "boolean", "description": "La dernière réplique est-elle une fausse vérité ironique sur le sujet principal ?"},
                                       "metaphore_filee": {"type": "boolean", "description": "Le sketch transpose-t-il le sujet dans un autre univers ou file-t-il une métaphore ?"},
                                       "continuite": {"type": "array", "items": {"type": "string"}, "description": "Un avis par passage de scène (sketch long) : « scène 1 → 2 : OK » ou le problème et sa correction."},
                                       "fil_continu": {"type": "boolean", "description": "Une seule histoire continue, cohérente, fluide et limpide, scène après scène ?"},
                                       "critique": {"type": "string", "minLength": 40, "description": "À écrire EN PREMIER : répliques faibles (numéro + pourquoi) et corrections précises."},
                                       "originalite": {"type": "number"}, "punchlines": {"type": "number"}, "rythme": {"type": "number"},
                                       "pertinence": {"type": "number"}, "dialogues": {"type": "number"}, "visuel": {"type": "number"},
                                       "chute": {"type": "number"}, "total": {"type": "number"}}, ["chute_vraie", "metaphore_filee", "critique", "total"])}
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

def valider(sk, liens, libre=False, minimum=None):
    reps, attente = [], 0
    if not isinstance(sk, dict): raise ValueError("réponse sans sketch")
    brutes = _liste(sk.get("repliques") or sk.get("script") or sk.get("dialogues"))
    for r in brutes[:16]:
        if not isinstance(r, dict): continue
        p = _role(r.get("p") or r.get("personnage") or r.get("role"), sk)
        t = _court(re.sub(r"\s+", " ", re.sub(r"\[[^\]\[]{1,40}\]", " ", str(r.get("t") or r.get("texte") or r.get("replique") or ""))), 170)   # pas d'indication de jeu à l'écran
        if p not in CAST or not t: continue
        x = {"p": p, "t": t}
        if r.get("d"): x["d"] = _court(r["d"], 260)
        if r.get("chute"): x["chute"] = True
        if str(r.get("objet", "")).lower() in OBJETS: x["objet"] = str(r["objet"]).lower()
        try: a = float(r.get("attente") or 0)
        except (TypeError, ValueError): a = 0
        if a > 0 and attente < (3 if libre else 1): x["attente"] = min(1.2, max(0.2, a)); attente += 1   # silences de jeu
        if libre and r.get("chevauche") and reps: x["chevauche"] = True                     # coupe la parole / réaction par-dessus
        reps.append(x)
    if len(reps) > NB_MAX:                                   # trop long : on garde le début et la chute finale
        reps = reps[:NB_MAX - 1] + [reps[-1]]
    if len(reps) < (minimum or (3 if MINI else 4)):
        vus = sorted({str((r or {}).get("p", "?"))[:20] for r in brutes if isinstance(r, dict)})[:5]
        raise ValueError(f"sketch trop court ({len(reps)} répliques ; champs reçus : {', '.join(sorted(sk))[:120]} ; rôles : {vus})")
    if reps[0]["p"] != "presentateur" and not (MINI or libre): raise ValueError("le présentateur doit ouvrir")
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
            "decoupage": _decoupage(sk.get("decoupage"), len(reps)),
            **({"serie_titre": _court(sk.get("serie_titre"), 50), "resume_episode": _court(sk.get("resume_episode"), 400)} if sk.get("serie_titre") else {}),
            **({"teaser": int(sk["teaser"])} if isinstance(sk.get("teaser"), (int, float)) and 0 <= int(sk["teaser"]) < len(reps) - 1 else {})}

def _norm_lien(u): return re.sub(r"^https?://(www\.)?|[?#].*$|/$", "", str(u or "").strip().lower())

def _sources(proposees, liens):
    """Liens cités par le sketch, uniquement parmi les articles réellement fournis (aucun lien inventé)."""
    par_cle = {_norm_lien(l): l for l in liens if l}
    out = []
    for s in proposees or []:
        l = par_cle.get(_norm_lien(s))
        if l and l not in out: out.append(l)
    return out[:6]

EFFETS = ("pluie_billets", "tremblement")
OBJETS = ("telephone", "billet", "portefeuille", "micro", "verre", "cafe")
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
        x = {"scene": _court(s.get("scene") or s.get("description"), 300), "repliques": idx, "lieu": lieu, "son": son, "duree": duree}
        if s.get("decor"): x["decor"] = re.sub(r"[^\w\s,.'-]", "", _court(s["decor"], 160))       # moteur cartoon : décor (anglais)
        if s.get("titre"): x["titre"] = _court(s["titre"], 50)
        if str(s.get("effet", "")).lower() in EFFETS: x["effet"] = str(s["effet"]).lower()
        out.append(x)
    return out

USAGE = {"appels": 0, "entree": 0, "sortie": 0, "recherches_web": 0, "cache_lu": 0, "cache_ecrit": 0, "cout": 0.0}
# prix en dollars par million de jetons (entrée, sortie) — page « Pricing » de la plateforme Claude, octobre 2026
PRIX = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0)}
ECO = (os.environ.get("ETAPES_ECO") or "0") == "1"                         # réglage : étapes simples sur un modèle moins cher
MODELE_ECO = "claude-sonnet-5-5"                          # suivi du budget (jetons consommés)

def _appel(client, systeme, messages, outil=OUTIL, web=False, max_tokens=12000, modele=None):
    """Appel Claude ; renvoie l'entrée de l'outil demandé (ou un JSON trouvé dans le texte). Recherche web si possible."""
    outils = [outil] + ([RECHERCHE_WEB] if web else [])
    kw = dict(model=modele or MODELE, max_tokens=max_tokens, messages=messages, tools=outils, tool_choice={"type": "auto"})
    if systeme:                                                            # longues consignes mises en cache : relues à 5 % du prix
        kw["system"] = [{"type": "text", "text": systeme, "cache_control": {"type": "ephemeral"}}]
    try:
        r = client.messages.create(**kw)
        u = getattr(r, "usage", None)
        if u:
            e_, s_ = getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0
            cl, ce = getattr(u, "cache_read_input_tokens", 0) or 0, getattr(u, "cache_creation_input_tokens", 0) or 0
            USAGE["entree"] += e_; USAGE["sortie"] += s_; USAGE["appels"] += 1; USAGE["cache_lu"] += cl; USAGE["cache_ecrit"] += ce
            pe, ps = PRIX.get(kw["model"], PRIX["claude-opus-5-5"])
            USAGE["cout"] += (e_ * pe + s_ * ps + cl * pe * 0.05 + ce * pe * 1.25) / 1e6
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
        return _appel(client, systeme, messages, outil, False, max_tokens, modele)
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
    if n > MOTS * (1.3 if MINI else 1.2): raise ValueError(f"trop long : {n} mots prononcés, maximum {MOTS}. Coupe {n - MOTS} mots : retire les relances, garde les vannes et la chute")
    if MOTS_MIN and n < MOTS_MIN * 0.85: raise ValueError(f"trop court : {n} mots prononcés, minimum {MOTS_MIN}. Développe l'escalade")
    return n

def pertinents(titres):
    """Garde le titre principal et les articles qui parlent vraiment du même sujet (au moins 2 mots-clés communs)."""
    if not titres: return titres
    ref = _mots(titres[0]["titre"] + " " + titres[0].get("resume", "")[:200])
    return [titres[0]] + [t for t in titres[1:] if len(ref & _mots(t["titre"] + " " + t.get("resume", "")[:200])) >= 2]

def _bloc_candidat(k, titres):
    return f"[{k}] " + "\n    ".join(f"- [{t['source']}] {t['titre']} — {t['resume'][:220]} ({t['lien']})" for t in titres[:5])

try: SEUIL = max(50, min(98, int(os.environ.get("SEUIL_QUALITE") or 90)))   # note minimale pour « prêt pour production »
except ValueError: SEUIL = 90
TOP = 3                                                                  # le sujet est pris parmi les 3 plus gros titres du jour

def atelier(client, systeme, titres, contexte="", type_chute="fausse vérité ironique"):
    """Salle d'auteurs : 15 vannes + 15 chutes, puis un jury séparé garde les 6 meilleures vannes et la meilleure chute.
    Renvoie (munitions, chute, note_chute) ; ("", "", 0) si l'atelier échoue (le sketch s'écrit alors sans)."""
    try:
        at = _appel(client, systeme, [{"role": "user", "content": ATELIER.format(sujet=titres[0]["titre"], articles=_bloc_candidat(0, titres),
                                                                          contexte=contexte, technique=TECHNIQUE_PUNCHLINE, type_chute=type_chute)}],
                    OUTIL_ATELIER, max_tokens=6000, modele=MODELE_ECO if ECO else None)
        vannes = [str(v).strip() for v in at.get("vannes", []) if str(v).strip()][:20]
        chutes = [str(c).strip() for c in at.get("chutes", []) if str(c).strip()][:20]
        if not chutes: raise ValueError("aucune chute proposée")
        j = _appel(client, None, [{"role": "user", "content": JURY.format(sujet=titres[0]["titre"],
                   vannes="\n".join(f"{i}. {v}" for i, v in enumerate(vannes)), chutes="\n".join(f"{i}. {c}" for i, c in enumerate(chutes)))}],
                   OUTIL_JURY, max_tokens=4000, modele=MODELE_ECO if ECO else None)
        nc = [float(x) if isinstance(x, (int, float)) else 0.0 for x in j.get("notes_chutes", [])]
        i = int(j.get("meilleure_chute", max(range(len(nc)), key=nc.__getitem__) if nc else 0))
        i = i if 0 <= i < len(chutes) else 0
        chute = str(j.get("chute_affutee") or "").strip() or chutes[i]
        note_chute = nc[i] if i < len(nc) else 0.0
        meilleures = [vannes[k] for k in j.get("meilleures_vannes", []) if isinstance(k, int) and 0 <= k < len(vannes)][:6]
        nv = j.get("notes_vannes", [])
        classees = sorted(range(len(vannes)), key=lambda k: -(nv[k] if k < len(nv) and isinstance(nv[k], (int, float)) else 0))
        reserve = [vannes[k] for k in classees if vannes[k] not in meilleures][:6]
        autres_chutes = [c for k, c in sorted(enumerate(chutes), key=lambda x: -(nc[x[0]] if x[0] < len(nc) else 0)) if k != i][:3]
        print(f"  atelier : {len(vannes)} vannes, {len(chutes)} chutes ; chute retenue par le jury ({note_chute:.0f}/10) : {chute[:160]}", flush=True)
        return "\n".join(f"- {v}" for v in meilleures), chute, note_chute, \
            "\n".join([f"- {v}" for v in reserve] + [f"- (chute de rechange) {c}" for c in autres_chutes])
    except Exception as e:
        if _bloquant(e): raise
        print(f"  atelier de vannes impossible ({str(e)[:120]}) : écriture directe.", flush=True)
        return "", "", 0.0, ""

def idees_libres(recents=(), n=6, consignes=""):
    """Mode sketch libre : Claude propose des situations du quotidien ; renvoie des sujets au format des candidats d'actualité."""
    import anthropic
    client = anthropic.Anthropic()
    rtxt = " ; ".join(r for r in recents if r)[:1500] or "(aucune)"
    out = []
    for essai in range(2):                                                 # une seconde tentative si la réponse est inexploitable
        try:
            import serie as _serie
            r = _appel(client, None, [{"role": "user", "content": IDEES.format(secondes=SECONDES, recents=rtxt, style=STYLE_LIBRE) + _serie.idees() + (("\n" + consignes) if consignes else "")}],
                       OUTIL_IDEES, max_tokens=6000, modele=MODELE_ECO if ECO else None)
        except Exception as e:
            if _bloquant(e):
                print(f"  ARRÊT : accès à l'API Claude impossible ({str(e)[:400]}). Action requise : console.anthropic.com > Settings > Limits (plafond de dépenses) ou Billing (crédit).", flush=True)
                raise
            print(f"  idées : appel en échec ({str(e)[:300]})", flush=True); continue
        for i in _liste(r.get("idees") or r.get("situations") or r.get("ideas")):
            if isinstance(i, str): i = {"titre": i}
            if isinstance(i, dict) and str(i.get("titre") or i.get("title") or "").strip():
                t = i.get("titre") or i.get("title")
                out.append([{"titre": _court(t, 120), "resume": _court(i.get("description"), 400), "lien": "", "date": None, "source": "idée"}])
        if out: break
        print(f"  idées : réponse inexploitable (champs reçus : {', '.join(sorted(r))[:120]}), nouvelle tentative", flush=True)
    return out[:n]

PUBLIC = """Vous êtes 3 spectateurs TikTok français qui tombent sur cette vidéo animée en scrollant, sans aucun contexte :
- Inès, 19 ans, étudiante, fan d'humour noir, scrolle très vite ;
- Karim, 31 ans, dans le métro, regarde sans le son une fois sur deux (il lit les sous-titres) ;
- Sandrine, 44 ans, maman, ne connaît pas les codes TikTok.
Vous ne voyez QUE ce qui s'entend et s'affiche (titre, cartons, répliques avec qui parle et le ton) :
{video}
Pour chacun : a-t-il compris l'histoire et la chute (vrai/faux), à quelle réplique il aurait scrollé (numéro, ou -1 s'il est resté jusqu'au bout), note de rire sur 10, réplique préférée, ce qui l'a perdu ou ennuyé.
Puis, ensemble, 3 à 5 critiques CONSTRUCTIVES et concrètes pour améliorer cette vidéo (réplique n° X : faire ceci), du point de vue du public, pas d'un auteur. Soyez honnêtes, pas polis.
Rends le tout avec l'outil avis_public."""
OUTIL_PUBLIC = {"name": "avis_public", "description": "Réactions des 3 spectateurs et critiques constructives.",
                "input_schema": _schema({"spectateurs": {"type": "array", "items": _schema({"nom": {"type": "string"}, "compris": {"type": "boolean"},
                                                                                              "scrolle_a": {"type": "integer"}, "rire": {"type": "number"},
                                                                                              "preferee": {"type": "string"}, "perdu_par": {"type": "string"}},
                                                                                             ["nom", "compris", "rire"])},
                                         "critiques": {"type": "array", "items": {"type": "string"}}}, ["spectateurs", "critiques"])}
MODELE_PUBLIC = os.environ.get("MODELE_PUBLIC") or "claude-sonnet-5-5"     # spectateurs : modèle économique

def public_test(client, sk):
    """Piste 5 : trois spectateurs virtuels découvrent le sketch sans contexte. Renvoie (résumé pour la réécriture, tous ont compris)."""
    if os.environ.get("PUBLIC_TEST", "1") == "0": return "", True
    dec = sk.get("decoupage") or []; scene_de = {i: k for k, sc in enumerate(dec) for i in sc.get("repliques", [])}
    lignes = [f"[Titre en haut de l'écran : {sk.get('titre_accroche', '')}]"]; sc0 = None
    for i, r in enumerate(sk["repliques"]):
        k = scene_de.get(i, sc0)
        if k != sc0 and k is not None and k < len(dec) and dec[k].get("titre") and i: lignes.append(f"[Carton : {dec[k]['titre']}]")
        sc0 = k; ton = ", ".join(re.findall(r"\[([^\]]{1,30})\]", r.get("d") or ""))[:60]
        lignes.append(f"{i}. {NOMS_LIBRES.get(r['p'], r['p'])}{f' ({ton})' if ton else ''} : {r['t']}")
    try:
        a = _appel(client, None, [{"role": "user", "content": PUBLIC.format(video="\n".join(lignes))}], OUTIL_PUBLIC, max_tokens=8000, modele=MODELE_PUBLIC)
    except Exception as e:
        if _bloquant(e): raise
        print(f"  public test indisponible ({str(e)[:100]})", flush=True); return "", True
    sp = [x for x in _liste(a.get("spectateurs")) if isinstance(x, dict)]
    crit = [str(x) for x in _liste(a.get("critiques")) if str(x).strip()][:5]
    compris = all(x.get("compris", True) for x in sp) if sp else True
    rires = [float(x.get("rire", 0) or 0) for x in sp]
    print(f"  public test : compris {sum(1 for x in sp if x.get('compris'))}/{len(sp)}, rire moyen {sum(rires) / max(1, len(rires)):.1f}/10, "
          f"scrolls : {[x.get('scrolle_a') for x in sp]}", flush=True)
    for c in crit[:3]: print(f"    → {c[:140]}", flush=True)
    txt = "AVIS DU PUBLIC TEST (spectateurs sans contexte) :\n" + "\n".join(
        f"- {x.get('nom', '?')} : {'a compris' if x.get('compris') else 'N A PAS COMPRIS'}, rire {x.get('rire', '?')}/10"
        + (f", aurait scrollé à la réplique {x['scrolle_a']}" if isinstance(x.get('scrolle_a'), int) and x['scrolle_a'] >= 0 else "")
        + (f", perdu par : {x.get('perdu_par')}" if x.get("perdu_par") else "") for x in sp) + \
        ("\nCritiques constructives du public :\n" + "\n".join("- " + c for c in crit) if crit else "")
    return txt, compris

NOMS_LIBRES = {"presentateur": "Jojo", "invite": "Kévin", "envoyee": "Lila", "narrateur": "Voix off"}

MISE_EN_SCENE = """Voici le script d'un sketch animé écrit par le propriétaire de la chaîne. Ne change AUCUN mot des répliques.
Personnages : Jojo (bonnet orange), Kévin (casquette), Lila (nœud rose), voix off.
{script}
Ajoute seulement la mise en scène, avec l'outil mise_en_scene :
- "d" : pour chaque réplique (même ordre), le même texte précédé de l'émotion juste en indication anglaise entre crochets ([annoyed], [laughing], [crying], [shouting], [sarcastic], [whispers]…) ;
- "decoupage" : 1 à 4 scènes (indices des répliques, "decor" EN ANGLAIS sans personnage : lieu précis + 2 ou 3 objets, "titre" = carton court si la scène change de moment ou de lieu) ;
- "titre_accroche" (« POV : … » ou « Quand … », 40 caractères max), "legende" (1 phrase), "question" (pour les commentaires), "hashtags" (4 à 6, sans #)."""
OUTIL_MES = {"name": "mise_en_scene", "description": "Mise en scène d'un script imposé.",
             "input_schema": _schema({"d": {"type": "array", "items": {"type": "string"}},
                                      "decoupage": {"type": "array", "items": _schema({"repliques": {"type": "array", "items": {"type": "integer"}},
                                                                                       "decor": {"type": "string"}, "titre": {"type": "string"}}, ["repliques"])},
                                      "titre_accroche": {"type": "string"}, "legende": {"type": "string"}, "question": {"type": "string"},
                                      "hashtags": {"type": "array", "items": {"type": "string"}}}, ["d", "decoupage"])}
ALIAS = {"jojo": "presentateur", "kevin": "invite", "lila": "envoyee", "voix off": "narrateur", "narrateur": "narrateur"}

def lire_script(texte):
    """« Jojo : … » ligne par ligne -> répliques. Un nom inconnu reçoit le premier personnage libre."""
    reps, libres, vus = [], ["presentateur", "invite", "envoyee"], {}
    for ligne in str(texte).splitlines():
        m = re.match(r"\s*([^:]{1,25})\s*:\s*(.+)", ligne)
        if not m:
            if reps and ligne.strip(): reps[-1]["t"] += " " + ligne.strip()
            continue
        nom = unicodedata.normalize("NFKD", m.group(1).strip().lower()).encode("ascii", "ignore").decode()
        p = ALIAS.get(nom) or vus.get(nom)
        if not p:
            pris = set(vus.values()) | {r["p"] for r in reps}
            p = next((x for x in libres if x not in pris), "presentateur"); vus[nom] = p
        brut_t = m.group(2).strip(); propre = re.sub(r"\s+", " ", re.sub(r"\[[^\]]{1,40}\]", " ", brut_t)).strip()
        reps.append({"p": p, "t": propre, **({"d": brut_t} if propre != brut_t else {})})   # [émotions] écrites par l'auteur gardées pour la voix
    return reps

def mettre_en_scene(texte):
    """Script tapé dans la régie : répliques gardées mot pour mot, Claude ajoute seulement le jeu, les scènes et les décors."""
    reps = lire_script(texte)
    if len(reps) < 2: raise RuntimeError("script trop court : écrivez au moins 2 répliques au format « Jojo : … »")
    mots, sujet = reps[0]["t"].rstrip(" .!?…").split(), ""
    for m_ in mots:
        if len(sujet) + len(m_) + 1 > 30: break
        sujet = (sujet + " " + m_).strip()
    brut = {"sujet": sujet or reps[0]["t"][:30], "repliques": [dict(r) for r in reps], "legende": reps[0]["t"][:120], "hashtags": ["humour", "pov", "sketch"],
            "decoupage": [{"scene": "1", "repliques": list(range(len(reps))), "decor": "plain"}], "titre_accroche": ""}
    try:
        import anthropic
        m = _appel(anthropic.Anthropic(), None, [{"role": "user", "content": MISE_EN_SCENE.format(
            script="\n".join(f"{i}. {NOMS_LIBRES[r['p']]} : {r['t']}" for i, r in enumerate(reps)))}], OUTIL_MES, max_tokens=4000, modele=MODELE_PUBLIC)
        d = [str(x) for x in _liste(m.get("d"))]
        for r, x in zip(brut["repliques"], d):
            if not r.get("d") and _mots_bruts(re.sub(r"\[[^\]]*\]", " ", x)) == _mots_bruts(r["t"]): r["d"] = x   # jeu accepté (sauf si l'auteur l'a écrit)
        if _liste(m.get("decoupage")): brut["decoupage"] = [dict(sc, scene=str(k + 1)) for k, sc in enumerate(_liste(m["decoupage"])) if isinstance(sc, dict)]
        for k in ("titre_accroche", "legende", "question"):
            if m.get(k): brut[k] = m[k]
        if _liste(m.get("hashtags")): brut["hashtags"] = _liste(m["hashtags"])
    except Exception as e:
        print(f"  mise en scène automatique impossible ({str(e)[:120]}) : script joué tel quel, une seule scène", flush=True)
    brut["repliques"][-1]["chute"] = True
    narr = [r for r in brut["repliques"] if r["p"] == "narrateur"]
    for r in narr: r["p"] = "presentateur"                                 # la voix off n'est ajoutée que par le robot (titre)
    global NB_MAX
    garde, NB_MAX = NB_MAX, 16                                             # script de l'auteur : aucune réplique supprimée
    try: sk = valider(brut, set(), libre=True, minimum=2)
    finally: NB_MAX = garde
    sk["fiche"] = {"note": 0, "decision": "vidéo manuelle (script imposé)", "decoupage": sk["decoupage"]}
    print(f"  script mis en scène : {len(sk['repliques'])} répliques, {len(sk['decoupage'])} scène(s)", flush=True)
    return sk

RELECTURE = """Tu es correcteur professionnel. Voici les textes qui s'afficheront à l'écran (sous-titres d'un dessin animé, titres, cartons).
Corrige UNIQUEMENT : orthographe, accords, conjugaison, accents (y compris sur les majuscules), ponctuation et typographie françaises
(espace avant « ! ? : ; », guillemets « », points de suspension …). Ne change AUCUN mot, n'en ajoute pas, n'en retire pas, ne reformule rien :
le langage oral est voulu (« t'es », « y a », « j'sais pas », « il boit jamais ») et doit rester tel quel. S'il n'y a rien à corriger, recopie à l'identique.
Textes (un par ligne, numérotés) :
{textes}
Rends exactement le même nombre de textes, dans le même ordre, avec l'outil corriger."""
OUTIL_RELECTURE = {"name": "corriger", "description": "Textes corrigés, même ordre.",
                   "input_schema": {"type": "object", "properties": {"textes": {"type": "array", "items": {"type": "string"}}}, "required": ["textes"]}}

def _mots_bruts(t): return re.findall(r"\w+", unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode())

def relire(client, sk):
    """Dernière étape : relecture orthographique de tout ce qui s'affiche. Une correction qui change les mots (et ne collerait
    plus à la voix) est refusée."""
    if not sk: return sk
    cibles = [("r", i) for i in range(len(sk["repliques"]))]
    if sk.get("titre_accroche"): cibles.append(("titre", None))
    cibles += [("scene", k) for k, sc in enumerate(sk.get("decoupage") or []) if sc.get("titre")]
    def lire(c):
        return sk["repliques"][c[1]]["t"] if c[0] == "r" else sk["titre_accroche"] if c[0] == "titre" else sk["decoupage"][c[1]]["titre"]
    textes = [lire(c) for c in cibles]
    try:
        r = _appel(client, None, [{"role": "user", "content": RELECTURE.format(textes="\n".join(f"{i + 1}. {t}" for i, t in enumerate(textes)))}],
                   OUTIL_RELECTURE, max_tokens=3000, modele=MODELE_ECO if ECO else None)
        corr = [re.sub(r"^\s*\d+\.\s*", "", str(x)).strip() for x in _liste(r.get("textes"))]
    except Exception as e:
        print(f"  relecture impossible ({str(e)[:100]}) : textes gardés tels quels", flush=True); return sk
    if len(corr) != len(textes): print("  relecture : réponse incomplète, ignorée", flush=True); return sk
    n = 0
    for c, avant, apres in zip(cibles, textes, corr):
        if not apres or apres == avant: continue
        a, b = _mots_bruts(avant), _mots_bruts(apres)
        if abs(len(a) - len(b)) > 1 or difflib.SequenceMatcher(None, a, b).ratio() < 0.8: continue   # trop différent : refusé
        if c[0] == "r": sk["repliques"][c[1]]["t"] = apres
        elif c[0] == "titre": sk["titre_accroche"] = apres
        else: sk["decoupage"][c[1]]["titre"] = apres
        n += 1
    print(f"  relecture des sous-titres : {n} correction(s)", flush=True)
    return sk

def _bloquant(e):
    """Erreurs qui ne se règlent pas en réessayant : crédit épuisé, clé invalide, accès refusé."""
    t = str(e).lower()
    return any(m in t for m in ("credit balance", "authentication", "invalid x-api-key", "permission_error", "billing", "usage limits"))

SERIE_BLOC = """- ÉPISODE DE SÉRIE (réglage du propriétaire) : {serie_txt}
  Écris "serie_titre" (le nom de la série, court, identique d'un épisode à l'autre) et "resume_episode" (2 phrases : ce qui s'est passé dans CET épisode, pour écrire la suite).
  Fais des rappels aux épisodes précédents (un détail, une phrase culte, une conséquence) sans qu'il faille les avoir vus pour comprendre.
  Termine sur la chute ET une petite porte ouverte vers la suite."""
ACCROCHE_BLOC = """- ACCROCHE CHOC (réglage du propriétaire) : "teaser" = l'indice de la réplique la plus intrigante ou la plus choquante du sketch (PAS la chute finale) ; elle est rejouée en ouverture, avant le titre, pour accrocher le spectateur dès la première seconde.
"""

def ecrire_sketch(candidats, essais=None, gags=(), special=False, recents=(), libre=False, serie="", stats=""):
    """candidats : liste de sujets (chaque sujet = liste d'articles, le titre principal en premier) — ou une simple liste d'articles.
    Renvoie le sketch validé, avec "fiche" (livrables A-F, note qualité, décision)."""
    import anthropic
    client = anthropic.Anthropic()
    if candidats and isinstance(candidats[0], dict): candidats = [candidats]
    gtxt = " ; ".join(g for g in gags if g)[:600] or "(aucun pour l'instant)"
    rtxt = " ; ".join(r for r in recents if r)[:1500] or "(aucun)"
    if essais is None:
        try: essais = max(0, min(6, int(os.environ.get("MAX_REECRITURES") or 4)))   # variable vide ou invalide : 4
        except ValueError: essais = 4
    systeme = MOTEUR_HUMOUR + ADAPTATION.format(cast="\n".join(f"- {k} : {v}" for k, v in CAST.items()), ton=TON, secondes=SECONDES, nb=NB,
                                                 mots=MOTS, mots_min=MOTS_MIN or 40, special=SPECIAL_DEMAIN if special else "", gags=gtxt, recents=rtxt,
                                                 looks="|".join(LOOKS), top=TOP, exemple=json.dumps(EXEMPLE, ensure_ascii=False, indent=0))
    if libre:
        systeme += (LIBRE.replace("{style}", STYLE_LIBRE).replace("{persos}", personnalites()).replace("{jeu}", JEU)
                    .replace("{serie}", SERIE_BLOC.replace("{serie_txt}", serie) + "\n" if serie else "")
                    .replace("{accroche}", ACCROCHE_BLOC if os.environ.get("ACCROCHE", "0") == "1" else ""))
        if stats: systeme += "\n" + stats
    top = len(candidats) if libre else TOP                                # sketch libre : toutes les idées sont éligibles
    # 1) sélection du sujet et de l'angle
    ordre, angle, verifs, verite = list(range(len(candidats))), "", [], ""
    try:
        ch = _appel(client, systeme, [{"role": "user", "content": (SELECTION_LIBRE if libre else SELECTION).format(dernier=min(top, len(candidats)) - 1, candidats="\n\n".join(_bloc_candidat(k, c) for k, c in enumerate(candidats[:top])))}],
                    OUTIL_CHOIX, web=not libre, max_tokens=4000)
        notes = {int(n.get("index", -1)): float(n.get("note", 0)) for n in ch.get("notes", []) if isinstance(n, dict)}
        choix = int(ch.get("choix", 0))
        if not 0 <= choix < min(top, len(candidats)):
            print(f"Choix {choix} refusé : hors des {top} premiers candidats, on prend le n°0.", flush=True); choix = 0
        ordre = [choix] + sorted([k for k in ordre[:top] if k != choix], key=lambda k: (-notes.get(k, 0), k))   # secours : autre gros titre
        angle, verifs = str(ch.get("angle", "")), [str(x) for x in ch.get("faits_verifies", [])][:8]
        verite = str(ch.get("verite", "")).strip()
        chute = str(ch.get("chute", "")).strip()
        if verite: print(f"Vérité du sujet : {verite[:200]}", flush=True)
        if chute: print(f"Chute proposée : {chute[:200]}", flush=True); verite = f"{verite} → chute proposée (à affûter) : « {chute} »"
        print("Gros titres soumis : " + " | ".join(f"{notes.get(k, '?')}/10 {c[0]['titre'][:60]}" for k, c in enumerate(candidats[:top])), flush=True)
        print(f"Sujet choisi : « {candidats[choix][0]['titre'][:100]} » — angle : {angle[:160]}", flush=True)
    except Exception as e:
        print(f"Sélection automatique impossible ({str(e)[:150]}) : premier candidat.", flush=True)
    meilleur = None
    for rang, k in enumerate(ordre[:2]):                                  # au plus deux sujets essayés
        titres = pertinents(candidats[k]); liens = {t["lien"] for t in titres}
        contexte = ((f"Angle retenu : {angle}\n" if rang == 0 and angle else "") +
                    (f"Vérité du sujet : {verite}\n" if rang == 0 and verite else "") +
                    (f"Faits vérifiés : " + " ; ".join(verifs) if rang == 0 and verifs else ""))
        munitions, chute_jury, _, reserve = atelier(client, systeme, titres, contexte,
                                                    "punchline qui retourne la situation (fausse vérité ironique, aveu, retournement)" if libre else "fausse vérité ironique")
        msg = (f"SUJET CHOISI : « {titres[0]['titre']} »\nArticles :\n" + _bloc_candidat(0, titres) + "\n" + contexte +
               (f"\nMUNITIONS — les vannes qui ont le plus fait rire le jury (place-les, presque telles quelles, aux bons endroits) :\n{munitions}" if munitions else "") +
               (f"\nCHUTE IMPOSÉE — dernière réplique, mot pour mot (tu peux seulement l'adapter au personnage qui la dit) : « {chute_jury} »" if chute_jury
                else "\nCommence par trouver la vérité crue de ce sujet, puis la fausse vérité ironique qui la révèle : ce sera la chute.") +
               "\n" + TECHNIQUE_PUNCHLINE +
               "\nDENSITÉ : chaque réplique est une vanne ou une relance de moins de 8 mots qui prépare une vanne ; aucune réplique de remplissage." +
               "\n\nÉcris le sketch sur CE sujet uniquement (étapes 4 à 9).")
        conv = [{"role": "user", "content": msg}]; sk = None; derniere = None; brut = {}; record = None   # record : meilleure version de CE sujet
        for tour in range(1 + (essais if rang == 0 else min(1, essais))):   # écriture puis jusqu'à 3 réécritures (1 pour le sujet de secours)
            try:
                brut = _appel(client, systeme, conv)
                sk = valider(brut, liens, libre); hors_sujet(sk, titres); n_mots = longueur(sk); chute_sur_sujet(sk, titres)
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
            texte = ((f"Fil conducteur annoncé : {_court(brut.get('fil'), 800)}\n" if libre and not MINI else "") + f"Vérité visée : {sk.get('verite', '')}\nConcept : {_court(brut.get('concept'), 600)}\nFormat : {_court(brut.get('format'), 300)}\n"
                     "Découpage : " + " | ".join(f"[{d['lieu'] or '?'}] {d['scene']}" for d in sk["decoupage"])[:1500] + "\n" +
                     (f"Plan gag (réplique {sk['gag']['replique']}) : {sk['gag']['prompt'][:300]}\n" if sk.get("gag") else "") +
                     "Répliques :\n" + "\n".join(f"{i}. {r['p']} : {r['t']}" for i, r in enumerate(sk["repliques"])))
            try:
                for essai_note in range(2):                                   # relecteur réinterrogé une fois si la note manque
                    nq = _appel(client, None, [{"role": "user", "content": CRITIQUE.format(sketch=texte, secondes=SECONDES, sujet=titres[0]["titre"], exigences=EXIGENCES_LIBRE if libre else EXIGENCES_ACTU)}], OUTIL_NOTE, max_tokens=5000)
                    try: note = float(nq["total"]); break
                    except (KeyError, TypeError, ValueError):
                        parts = [nq.get(k) for k in ("originalite", "punchlines", "rythme", "pertinence", "dialogues", "visuel", "chute")]
                        if all(isinstance(x, (int, float)) for x in parts): note = float(sum(parts)); break
                        print("  note totale absente : on redemande au relecteur", flush=True)
                else: raise ValueError("note totale absente deux fois")
                for cle, val, quoi in (("chute_vraie", False, "chute qui n'est pas une fausse vérité ironique sur le sujet"),
                                       ("metaphore_filee", True, "métaphore filée"),
                                       ("fil_continu", False if (libre and not MINI) else None, "histoire sans fil conducteur ou passage de scène incohérent")):
                    if val is not None and nq.get(cle) is val and note > 70:
                        print(f"  {quoi} : note plafonnée à 70 (au lieu de {note:.0f})", flush=True); note = 70.0
                suivi = [str(x) for x in _liste(nq.get("continuite")) if str(x).strip()]
                if libre and not MINI and suivi:
                    print("  continuité : " + " | ".join(x[:90] for x in suivi), flush=True)
                critique = (("CONTINUITÉ ENTRE LES SCÈNES :\n" + "\n".join("- " + x for x in suivi) + "\n\n") if (libre and not MINI and suivi) else "") + \
                    (str(nq.get("critique") or "").strip() or nq.get("_texte", "")) or \
                    " ; ".join(f"{k} {nq[k]}" for k in ("originalite", "punchlines", "rythme", "pertinence", "dialogues", "visuel", "chute") if k in nq)
            except Exception as e:
                note, critique = 0.0, f"notation impossible ({e})"
            if libre and note >= 60:                                         # piste 5 : le public test donne son avis
                avis, compris = public_test(client, sk)
                if avis: critique = avis + "\n\n" + critique
                if not compris and note > 80:
                    print(f"  un spectateur n'a pas compris : note plafonnée à 80 (au lieu de {note:.0f})", flush=True); note = 80.0
            print(f"  version {tour + 1} : {note:.0f}/100, {len(sk['repliques'])} répliques, {n_mots} mots", flush=True)
            sk["fiche"] = {k2: brut.get(k2) for k2 in ("fil", "concept", "format", "angle", "resume_factuel", "faits_reels", "inventions") if isinstance(brut, dict)}
            sk["fiche"]["decoupage"] = sk["decoupage"]
            sk["fiche"]["titres_sujet"] = [t["titre"] for t in titres[:6]]          # articles du sujet réellement choisi (anti-répétition)
            for k2 in ("concept", "format", "angle"):                       # la note F vient du relecteur, jamais de l'auteur
                if isinstance(sk["fiche"].get(k2), str):
                    sk["fiche"][k2] = re.sub(r"\s*(Note qualit[ée]|Décision|Decision)\b.*$", "", sk["fiche"][k2], flags=re.S | re.I).strip()
            sk["fiche"].update(verification_web=USAGE["recherches_web"] > 0, note=note, critique=critique[:1500], decision="prêt pour production" if note >= SEUIL else "à retravailler")
            if meilleur is None or note > meilleur["fiche"]["note"]: meilleur = sk
            if note >= SEUIL: return relire(client, sk)
            if record is None or note > record[1]: record = (brut, note, critique)
            elif tour: print(f"  pas de progrès : on repart de la meilleure version ({record[1]:.0f}/100)", flush=True)
            b_brut, b_note, b_crit = record                                 # on retouche toujours la meilleure version, jamais une moins bonne
            conv = [{"role": "user", "content": msg}, {"role": "assistant", "content": json.dumps(b_brut, ensure_ascii=False)[:8000]},
                    {"role": "user", "content": REECRITURE.format(note=round(b_note), seuil=SEUIL, critique=b_crit[:3500],
                                                                  reserve=f"Réserve de vannes et de chutes validées par le jury :\n{reserve}" if reserve else "")}]
        if derniere is not None and _bloquant(derniere): break
        print(f"  sujet trop faible après réécritures{' : on essaie un autre sujet' if rang == 0 and len(ordre) > 1 else ''}", flush=True)
    if meilleur is None: raise RuntimeError(f"aucun sketch exploitable : {derniere}")
    print(f"  meilleure version retenue : {meilleur['fiche']['note']:.0f}/100 (sous l'objectif de {SEUIL} : à retravailler, pas de publication automatique)", flush=True)
    return relire(client, meilleur)
