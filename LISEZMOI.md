# Petits.Dramas — robot 100 % automatique

Sans aucune intervention, le robot fabrique des sketchs animés pour TikTok (style « toons » : personnages adultes à grosse tête ronde, différents à chaque vidéo) :
1. **l'histoire** : la bande son d'une vidéo TikTok que tu donnes (doublage : le robot construit tout l'univers autour du son et des paroles), ton propre texte, ou une idée écrite par **Claude** (gag éclair de ~15 s ou sketch long de plus d'une minute) ;
2. **les voix** : **ElevenLabs** (voix réalistes, rires, colère), sinon Chatterbox sur **Modal**, sinon les voix gratuites Piper (une voix par personnage) ;
3. **la réalisation** : le « studio » choisit le lieu, l'heure, les tenues, le casting, les décors (IA sur Modal ou dessinés par le robot) et monte la vidéo de façon dynamique (plans serrés et larges, réactions, mouvements de caméra calés sur la voix) ;
4. **Claude** vérifie la vidéo finie ; **Buffer** la publie sur TikTok (mention « contenu généré par IA ») ; elle est aussi archivée dans les *Releases* du dépôt.

Si un service est en panne ou sans crédit, le robot ne s'arrête pas : il bascule tout seul sur les outils gratuits (voir plus bas).
---

## Installation (une seule fois, environ 30 minutes)

### 1. GitHub (gratuit)
1. Sur ton compte **github.com** (un compte existant convient très bien), **New repository** → nom `jt-auto` → **Public** → *Create*.
   Public est recommandé : les minutes du robot deviennent illimitées et gratuites, et Buffer a besoin d'une adresse publique pour récupérer la vidéo. Tes clés restent secrètes (les « Secrets » ne sont jamais visibles, même dans un dépôt public).
2. Envoie tout le contenu de ce dossier dans le dépôt (*uploading an existing file*, glisser-déposer). Vérifie que le dossier caché **`.github`** est bien envoyé.
3. **Settings → Pages** → *Source* : **GitHub Actions** (pour le site de régie).

### 2. Claude (écriture des sketchs, quelques euros par mois)
1. **console.anthropic.com** → crée un compte → **Billing** : ajoute 5 à 10 $ de crédit.
2. **API Keys → Create Key** → copie la clé (`sk-ant-…`).

### 3. Modal (GPU pour les voix, crédits gratuits chaque mois)
1. Crée un compte sur **modal.com** (connexion avec GitHub possible).
2. **Settings → API Tokens → New Token** → note le *Token ID* (`ak-…`) et le *Token Secret* (`as-…`).

### 4. Buffer (publication TikTok, gratuit)
1. Crée un compte gratuit sur **buffer.com** et **connecte ton compte TikTok** (Channels → Connect → TikTok).
2. Va sur **publish.buffer.com/settings/api** et crée une **clé API**.
(Le plan gratuit permet 3 réseaux et 10 publications en attente par réseau : largement suffisant pour une vidéo par jour.)

*Alternative payante, si un jour Buffer ne convient plus : Upload-Post (~24 $/mois), déjà prévu dans le robot (secrets `UPLOAD_POST_API_KEY` et `UPLOAD_POST_USER`).*

### 5. Coller les clés dans GitHub (jamais dans un chat ou un message)
Dans le dépôt : **Settings → Secrets and variables → Actions → New repository secret**, une fois par ligne :

| Name | Valeur |
|---|---|
| `ANTHROPIC_API_KEY` | ta clé Claude `sk-ant-…` |
| `MODAL_TOKEN_ID` | le Token ID Modal `ak-…` |
| `MODAL_TOKEN_SECRET` | le Token Secret Modal `as-…` |
| `BUFFER_API_KEY` | ta clé API Buffer |

### 6. Premier lancement
Onglet **Actions** → « Émission du jour » → **Run workflow**.
La première exécution est plus longue (environ 30 à 45 min) : le robot fait le casting vocal et télécharge le modèle de voix. Ensuite, compter environ 20 min par émission.
Après la coche verte ✅, la vidéo est dans **Releases** et part sur TikTok via Buffer (publication immédiate ou dans les 10 minutes).

C'est tout : ensuite, une émission sort **chaque jour automatiquement**.

---

## Régie : vérifier les vidéos avant publication (facultatif)
À chaque émission, le robot met à jour un petit site : **https://<ton-compte>.github.io/jt-auto/**
(l'adresse exacte s'affiche dans *Settings → Pages*).

**L'installer comme une application (Android, ex. Galaxy S23 Ultra)** : ouvre l'adresse dans **Chrome** et touche **📲 Installer l'application** en haut de la page (ou menu ⋮ → *Installer l'application*). Avec **Samsung Internet** : menu ☰ → *Ajouter la page à* → *Écran d'accueil*. L'icône « JT » rouge apparaît avec tes autres applis et s'ouvre en plein écran.

On y trouve :
- l'interrupteur **Publication automatique** (coupé au départ) : activé, chaque vidéo part seule sur TikTok ; coupé, les nouvelles vidéos attendent ton feu vert (badge **⏸ En attente de validation**) ;
- la liste des vidéos, de la plus récente à la plus ancienne, avec un aperçu pour les regarder ;
- le bouton **Publier sur TikTok** : deux touches (la deuxième confirme) et le robot envoie la vidéo tout seul via Buffer, en 1 à 3 minutes, avec le suivi affiché en direct ;
- en secours, **Partage manuel** (menu de partage du téléphone → TikTok) si Buffer coince.

### Connecter la régie (une seule fois, 3 minutes)
Les boutons ont besoin d'une clé limitée à ce seul dépôt :
1. Sur GitHub : photo de profil → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. *Token name* : `regie-jt` ; *Expiration* : 1 an ; *Repository access* : **Only select repositories** → `jt-auto`.
3. *Permissions → Repository permissions* : **Actions : Read and write** et **Variables : Read and write**. Rien d'autre.
4. **Generate token**, copie la clé (`github_pat_…`), ouvre le site sur ton téléphone → « Connecter la régie » → colle → **Enregistrer**.

La clé reste uniquement dans le navigateur de ton téléphone (elle n'est jamais mise sur le site) et ne peut agir que sur ce dépôt. Si tu perds ton téléphone : supprime la clé sur la même page GitHub.

## Moteur humoristique
Les consignes d'auteur sont dans `moteur/prompts/moteur_humour.md` (modifiable sans toucher au code). À chaque émission :
1. le robot réunit les **gros titres français du jour** : sujets des dernières 24 h mis à la une par au moins un grand média et traités par au moins 3 médias, classés par nombre de unes (RSS de 13 médias ; drames, conflits armés, directs sportifs et rubriques récurrentes exclus ; sujets et liens déjà traités évités). Un sujet qui n'est pas à la une n'est pris que si la journée est creuse, et il est marqué « sujet secondaire » dans le journal ;
2. Claude reçoit seulement les 3 plus gros titres, les note sur 10 et choisit parmi eux celui qui donne le meilleur sketch (un choix en dehors est refusé par le code), puis son angle, et vérifie les faits avec la recherche web de l'API si elle est disponible (sinon il s'en tient aux articles, et le journal le signale) ;
3. il écrit un sketch de 60 à 90 s (130 à 190 mots) avec les livrables A à F (résumé factuel, concept, découpage scène par scène avec bruitages, faits réels / inventions) ;
4. une salle d'auteurs prépare 15 vannes et 15 chutes, un jury séparé garde les meilleures, puis un relecteur note le sketch sur 100 ; sous le seuil d'exigence (90 par défaut, réglable dans la régie), jusqu'à 4 retouches ciblées en repartant toujours de la meilleure version, puis un second sujet ; la meilleure version est gardée mais **n'est jamais publiée automatiquement si elle reste sous le seuil** ;
5. les jetons consommés et toutes les décisions sont écrits dans `episodes/journal.txt` ; la fiche complète de l'épisode est dans `episodes/<date>.json` (champ `fiche`).

## Rendu détaillé : le « studio » (gratuit, sans IA)
Pour les sketchs, les gags éclair et les vidéos faites sur la bande son d'une vidéo TikTok, le robot se comporte comme un petit studio de dessin animé, sans dépenser de crédit Claude ni de GPU :
- **bible de l'épisode** (`moteur/studio.py`) : le lieu de chaque scène (salon, cuisine, bureau, cabinet médical, bar, chambre, salle de sport, magasin, classe, rue, restaurant), l'heure (matin, jour, soir, nuit), la lumière, la tenue de chaque personnage selon le lieu et son rôle (celui qui pose les questions au cabinet porte la blouse et le stéthoscope, le serveur le tablier…), des figurants qui vivent au fond, des gags écrits dans le décor et des ambiances (vapeur, poussière dans la lumière, pluie, neige, néon qui grésille). Tout est déduit du texte, avec une graine propre à chaque vidéo ;
- **personnages** (`moteur/marionnette.py`) : garde-robe complète (13 hauts, motifs, bas, chaussures, cravate, badge, stéthoscope, lunettes, moustache…), coiffures, reflets dans les yeux, paupières, rides d'expression, dents, 10 bouches et 12 regards (yeux au ciel, spirale, cœurs, pupilles minuscules…), mains (index pointé, poing, pouce, paume), ombrage selon la lumière, pompon et nœud qui suivent les mouvements, 24 objets à tenir, 15 effets (goutte de gêne, fumée de colère, ampoule, cœurs…) ;
- **décors dessinés par le robot** (`moteur/decor_dessin.py`) : pièces complètes avec fenêtre dont le ciel suit l'heure, meubles, étagères garnies, tableaux, horloge, lampes allumées le soir, tache de soleil au sol, comptoir ou bureau au premier plan, et plein de petits détails (`moteur/decor_details.py` : portes moulurées, prises, tapis, cadres photo, calendrier, extincteur, plantes, tabourets, frise de l'alphabet, banc et panneau STOP dans la rue…). 15 lieux : salon, cuisine, bureau, cabinet médical, bar, chambre, salle de sport, magasin, classe, rue, restaurant, **administration** (guichet, tickets, file d'attente), **hall d'immeuble** (escalier, boîtes aux lettres), **caverne** préhistorique (peintures rupestres, feu) et **palais** (moulures dorées, lustre). Utilisés quand les décors IA sont coupés ou indisponibles ;
- **réalisation** : plans larges, moyens, serrés, très serrés, plongée, contre-plongée, par-dessus l'épaule ; avancée lente, travelling, caméra à l'épaule, zoom choc ; profondeur (le décor glisse moins vite que les personnages), flou d'arrière-plan sur les plans serrés, regard caméra pendant les silences gênants, réactions de celui qui écoute (yeux au ciel, main sur le visage, bras croisés…), étalonnage selon l'heure ;
- **sans indication de jeu** (doublage sans Claude), l'émotion est devinée d'après les mots, la ponctuation et le volume de la voix ; les rires repérés dans la bande son font rire celui qui écoute ;
- **intonation** : la hauteur et l'énergie de chaque voix sont mesurées image par image ; les sourcils montent avec la voix, les yeux s'agrandissent, la tête suit la mélodie et hoche sur les syllabes appuyées ; une voix haute et forte, basse et molle ou qui monte à la fin affine l'émotion jouée ;
- **jeu d'acteur continu** : yeux plissés par le sourire, coins de la bouche relevés ou tombants, sourcil levé, pupilles qui s'agrandissent, haussement d'épaules, buste penché vers l'autre (ou qui recule), pied qui tape d'impatience ; coiffures par épisode (carré, longs, queue de cheval, chignon, boucles, court) qui se balancent, couleur des cheveux, plis des vêtements, ceinture, bijoux, taches de rousseur ;
- **l'image de la vidéo TikTok est analysée** (`moteur/analyse_video.py`, gratuit) : coupes et durée des plans, cadrages, mouvements de caméra, personnes à l'écran et leur place, couleur de leurs habits et de leurs cheveux, sourires, tête penchée, agitation, couleur du décor, lumière et heure. Nos personnages prennent les couleurs d'habits et de cheveux des personnes de la vidéo (la plus présente à l'image joue la voix la plus présente), nos murs la couleur du décor, notre storyboard son rythme et ses cadrages. Quand le crédit Claude le permet, il voit aussi 6 images clés et reprend lieu, objets, tenues, coiffures, gestes et premier plan / arrière-plan dans nos catalogues (quelques centimes de plus) ;
- **banque visuelle** (`episodes/banque_visuelle.json`) : chaque vidéo envoyée y est rangée (mesures de l'image, ce que Claude y a vu, ce que le studio en a fait, notre vidéo). Les tendances sont pondérées par les vues TikTok de nos vidéos : quand une vidéo n'a pas d'image exploitable, le studio reprend le rythme et les cadrages de la banque, et Claude reçoit le résumé de la banque (ce qui revient, ce qui a fait des vues). Plus tu envoies de vidéos, plus la banque s'étoffe ;
- **contrôle technique gratuit** avant publication (format, son, durée, image noire ou figée), en plus du contrôle par IA quand le crédit le permet ;
- quand Claude est disponible, il peut choisir lui-même lieux, heure, tenues, gags et plans (catalogues fermés, vérifiés par le robot) ;
- la mémoire du studio (`episodes/studio_memoire.json`) garde ce qui a été tourné pour varier d'une vidéo à l'autre.

### Personnages adultes, casting libre (par défaut)
Réglage **Personnages** dans l'onglet ⚙️ : « Adultes semi-réalistes » (par défaut) ou « Marionnettes de la chaîne ».
- `moteur/humain.py` dessine des **adultes dans le style des chaînes « toons » de TikTok** (Aristos Toons, Lescromatoons, MotionToonz…), sur la base de nos anciens personnages : grosse tête ronde **blanche** posée directement sur le col (pas de cou), yeux en ovales noirs, sourcils fins, bouche synchronisée ; buste = le vêtement, aux **épaules carrées** et flancs droits ; bras en manches qui tombent sous l'épaule, mains blanches rondes avec pouce ; jambes en pantalon, ou **simples traits noirs** sous une robe ou une jupe ; trait noir épais, aplats. La tenue, la coiffure, la barbe, les lunettes changent à chaque vidéo (casting libre). Réglage `PEAU=humaine` pour une peau de couleur humaine (par défaut : blanche).
- **garde-robe détaillée** (`moteur/garde_robe.py`) : 20 coiffures avec mèches et volume (ondulés, carré plongeant à frange, afro, en bataille, raie sur le côté, ras, nattes, anglaises/perruque, banane, dégarni…), barbes (courte, pleine, bouc, favoris), 12 couvre-chefs (bonnet, casquette, béret, chapeau, melon, tricorne, casque de chantier, toque, bob, couronne, bandana, serre-tête), 20 hauts (dont col roulé, doudoune, blouson, redingote d'époque à galons et jabot, uniforme, tunique en peau de bête, chemise hawaïenne), imprimés dessinés (fleurs, palmiers, fourrure, losanges, chevrons, étoiles), sac en bandoulière, casque audio, bretelles, coutures, ourlets, plis et lacets. **Thèmes** reconnus dans le texte : préhistoire, Versailles/roi, police, chantier, cuisinier, plage, prince/princesse : tout le monde est habillé en conséquence.
- **visages** : rides selon l'âge (pattes d'oie, plis de la bouche, front), cernes (fatigue, tristesse), narines dilatées (colère), rouge à lèvres, dents du bas quand on crie, taille des yeux et épaisseur des sourcils propres à chacun.
- **intonation** : une question fait lever un sourcil et pencher la tête en fin de phrase, une affirmation fait baisser la tête, une voix qui monte fort ouvre grand les yeux, une voix grave et molle alourdit les paupières, le rouge de la colère monte avec la voix, et celui qui écoute acquiesce quand la phrase se pose.
- **Casting libre** : à chaque vidéo, de nouveaux personnages. Le genre vient de la voix (doublage TikTok) ou du prénom du sketch ; l'âge de ce qui est dit (« mamie », « papa », « docteur »…) ou de Claude ; la coiffure, la couleur des cheveux et des habits de la vidéo d'origine ; le reste (visage, peau, yeux, corpulence) est tiré au hasard avec la graine de l'épisode. Les figurants sont aussi des adultes.
- **montage dynamique** (réglage *Montage*, activé par défaut) : chaque réplique est découpée en plusieurs plans selon l'énergie et l'émotion de la voix (dispute : coupes rapides toutes les ~0,8 s ; émotion : plans longs), en alternant plans serrés et larges, celui qui parle et celui qui écoute, plongée et contre-plongée ; la durée moyenne des plans de la vidéo d'origine règle la cadence. Chaque plan a son mouvement de caméra et un passage depuis le précédent (coupe franche avec petit punch, glissé, filé avec flou de mouvement, zoom). Les coupes tombent entre deux mots ou sur un mot appuyé, un poil avant que la voix démarre : le montage reste fluide.
- Toute la mise en scène s'applique (plans, gestes, mimiques, intonation, réactions) ; les cadrages sont adaptés aux proportions d'adulte.

Réglage **Rendu détaillé (studio)** dans l'onglet ⚙️ : coupé, le robot revient exactement à l'ancien rendu (bonshommes blancs, plans simples). Le rendu détaillé prend environ deux fois plus de temps de calcul sur GitHub (gratuit).

## Réglages depuis l'application (onglet ⚙️ Réglages)
Rythme (chaque jour, un jour sur deux, un jour sur trois, pause), heure de fabrication, durée et ton des sketchs, modèle Claude, nom de l'émission, bouton « Fabriquer une émission maintenant » et raccourcis vers les crédits Modal / Claude, Buffer et TikTok Studio. Chaque réglage s'applique dès la prochaine émission.

## Réglages avancés (facultatifs)
| Je veux… | Où |
|---|---|
| changer le nom de l'émission | *Settings → Secrets and variables → Actions → Variables* → `NOM_EMISSION` |
| un modèle Claude plus drôle (un peu plus cher) | variable `MODELE_CLAUDE`, par ex. `claude-opus-5-5` |
| publier en privé pour tester | ajouter la variable d'environnement `TIKTOK_VISIBILITE=SELF_ONLY` dans le workflow |
| refaire le casting des voix | supprimer le dossier `voix/` du dépôt (sauf `.gitkeep`) |
| mettre en pause | *Actions* → « Émission du jour » → *…* → *Disable workflow* |

En cas d'échec, GitHub t'envoie un e-mail ; le détail est dans l'onglet Actions.

## Outils payants par défaut, repli gratuit automatique
Tous les outils payants sont activés par défaut (Claude pour l'écriture, la mise en scène et le contrôle ; ElevenLabs pour les voix ; Modal pour les décors et le plan « reconstitution »). S'il n'y a plus de crédit, le robot bascule tout seul sur les outils gratuits et la vidéo sort quand même :
- **écriture** : sans Claude, un sketch de la réserve `moteur/sketchs_secours.json` (190 sketchs écrits à l'avance : 144 gags éclair et 46 sketchs longs, sur la maison, le travail, l'école, les sorties, le téléphone, l'argent et les époques ; écrite à l'avance, jamais deux fois le même tant qu'il en reste d'inédits ; le JT d'actu devient un gag éclair) ; une alerte prévient qu'il faut recharger le crédit ;
- **doublage TikTok** : sans Claude, casting par la hauteur des voix et mise en scène par le studio gratuit ;
- **voix** : ElevenLabs → Chatterbox → Piper ; **décors** : IA → dessinés par le robot ; **contrôle** : Claude → contrôle technique gratuit.

### Le mode payant profite de toutes les améliorations
Les consignes envoyées à Claude (doublage d'une vidéo TikTok et sketchs écrits) sont générées à partir du code (`studio.consigne_studio`) : Claude connaît tous les lieux, tenues, coiffures, barbes, chapeaux, imprimés, thèmes d'époque, plans, mouvements et gestes, choisit le casting adulte (avec barbe et coiffure) et le rythme du montage (« cadence » : rapide, normal ou posé). Le moteur applique ensuite le montage dynamique, les détails et l'intonation comme en mode gratuit. Les décors IA (Stable Diffusion XL) sont demandés en style détaillé (trait noir épais, beaucoup d'objets) et gardent le premier plan dessiné (comptoir, bureau, guichet).

### Mode économique (réglage « 💰 Mode économique », dans Réglages → Crédits et outils)
Garde les outils payants (Claude, ElevenLabs, décors IA) mais dépense beaucoup moins de crédit Claude : écriture avec Sonnet au lieu d'Opus, petites étapes sur le modèle économique, un seul premier jet au lieu de trois, 2 réécritures et 2 sujets au plus, sans public test ni recherche des tendances, et pas de nouvelles ambiances sonores ElevenLabs (celles déjà fabriquées restent utilisées). Coupé par défaut (meilleure qualité).

## Vitesse et stabilité
- **Crédits vérifiés au départ** (appel minuscule à Claude, solde ElevenLabs) : le robot part directement en payant ou en gratuit.
- **Réessais automatiques** des coupures passagères (réseau, serveur saturé) avant de basculer sur le gratuit ; la publication n'est jamais réessayée (pas de doublon).
- **Rendu sur les 4 processeurs** des serveurs GitHub (réglage `RENDU_PARALLELE=0` pour revenir à un seul).
- **Fiche par vidéo** : l'historique note les outils utilisés (`outils` : Claude ok/secours, voix ElevenLabs/Chatterbox/Piper/TikTok, décors IA/dessinés), affichés en voyants sur le site.
- **Site toujours à jour** : toutes les mises en ligne du site passent par une seule file d'attente (`site.yml`, reconstruit depuis le dernier historique, 2e essai si GitHub refuse) ; avant, deux mises en ligne en même temps pouvaient en écraser une et faire disparaître une vidéo. En plus, l'application ajoute d'elle-même les vidéos toutes neuves que la version du site ne contient pas encore (lues directement depuis les Releases GitHub).
- **Test automatique avant chaque mise à jour** : chaque demande de fusion fabrique une vraie mini-vidéo de bout en bout.

## Style cinéma (toujours en dessin animé)
Chaque vidéo tire au hasard ses effets (pour varier d'une vidéo à l'autre, en mélange avec le style d'avant) : mise au point qui glisse sur celui qui parle (l'autre devient flou dans les plans moyens), effet vertige sur les moments de choc (le personnage avance, le décor recule), règle des tiers dans les plans serrés, couleur de l'image selon l'émotion (chaude, froide, rouge de colère), trois couches de profondeur (décor, figurants, feuillage flou au premier plan), grain de film léger et reflets de lumière, son de cinéma (ambiance du lieu, pas, whoosh sur les passages rapides, musique de fond discrète qui suit l'humeur), sous-titres qui rebondissent et tremblent quand on crie. En mode payant, Claude peut choisir ces effets (« cine » dans la direction artistique).

## Ce que le robot apprend de chaque lien TikTok (banque visuelle et sonore)
À chaque vidéo TikTok envoyée, tout est analysé gratuitement et rangé dans `episodes/banque_visuelle.json` :
- **l'image** (`analyse_video.py`) : montage, durée des plans, cadrages, mouvements de caméra, personnes, couleurs d'habits et de cheveux, sourires, décor, lumière ; avec Claude : lieu, objets, tenues, coiffures, gestes ;
- **le son** (`analyse_audio.py`) : nombre de voix, hauteur et genre de chaque voix, part de parole, débit, blancs, coupures de parole, voix posée ou criée, musique de fond, bruitages (graves type « boom » ou aigus type « pop », et s'ils tombent sur une vanne), rires et autres événements, émotions de jeu.
Les moyennes (pondérées par les vues de nos vidéos) guident les vidéos suivantes : rythme des plans, dosage des bruitages, et un résumé envoyé à Claude.

## L'histoire de la vidéo TikTok, recréée à notre sauce
- **Âges et allures** d'après le dialogue, la voix et l'image : celui qu'on appelle « fiston », « mon fils », ou qui dit « papa, … » est un ado (plus petit, cheveux courts, jamais de barbe) ; ses parents sont plus âgés. Claude peut aussi donner la taille.
- **Lieux différents** : au téléphone, en visio ou l'un chez lui et l'autre en ville, chacun a son propre décor et le montage passe de l'un à l'autre (coupe franche, téléphone en main). Deviné aussi sans Claude aux mots de l'appel (allô, t'es où, je suis au…).
- **Personnes muettes** dont on parle ou qu'on voit (« elle me fait signe ») : dessinées à côté du personnage, avec leur geste (coucou, signe, danse, attend…).
- **Coupes** calées sur celles de la vidéo d'origine ; image toujours nette ; en plan serré, seul celui qui est filmé est à l'image.

## Voix proches : qui parle quand (moteur/locuteurs.py)
Quand deux voix se ressemblent, la transcription peut les confondre (un seul personnage parle alors avec les deux voix). Le robot :
1. redemande à ElevenLabs en annonçant 2 voix si le texte est clairement un dialogue ;
2. recalcule l'**empreinte** de chaque morceau de phrase (ECAPA si installée, sinon timbre MFCC + hauteur + brillance) et regroupe les morceaux qui se ressemblent (gratuit) ;
3. si c'est la même personne qui fait les deux voix, suit le **fil du dialogue** (questions / réponses, « papa, … », « fiston », saut de hauteur) ;
4. en mode payant, Claude relit le dialogue et réattribue chaque réplique à la bonne personne.

## Jury qualité : 5 critiques, corrections automatiques (moteur/qualite.py)
À chaque vidéo, un jury de 5 critiques donne une note sur 10 et au plus 3 remarques précises (avec le moment) : **humoriste** (vannes, chute, réactions, bruitages sur les vannes), **réalisateur** (rythme des plans, celui qui parle bien filmé, réactions, caméra), **directeur artistique** (âge, sexe, allure, décors, personnes dont on parle qu'on devrait voir, lieux séparés), **ingénieur du son** (blancs, bruitages, volume) et **spectateur TikTok** (accroche, moments creux, durée, sous-titres, fin).
- **Gratuit** (toujours) : règles calculées sur ce que le moteur a vraiment monté.
- **Claude** (s'il y a du crédit, ~0,10 $) : il regarde les images de la vidéo et, pour un lien TikTok, celles de la vidéo d'origine aux mêmes instants, et liste ce qui manque.
- **Corrections automatiques** : plan, réaction, bruitage, casting (âge, sexe, barbe), personne ajoutée, lieux séparés, décor, tenue ; la vidéo est refaite et on garde la mieux notée (réglages `JURY_TOURS`, 1 par défaut ; `SEUIL_JURY`, 9,8 ; `JURY=0` pour couper).
- **Mémoire** (`episodes/qualite_memoire.json`) : les erreurs qui reviennent deviennent des règles données à Claude ; le poids de chaque critique s'ajuste selon les vues TikTok. La fiche du jury est gardée dans l'historique de chaque vidéo.

## Bruitages « tendance » (moteur/bruitages.py)
Catalogue tiré d'une recherche sur les bruitages des vidéos d'humour TikTok (octobre 2026) : vine boom, « dun dun duuun », klaxon de clown, sifflet qui descend, boing, petit violon triste, criquets, craquement d'os, scie qui ondule, claquement de dents, bouilloire, « ka-ching » de caisse, flash photo, clavier, bug numérique, bulle. Ce sont **nos propres versions** (pas les extraits protégés des mèmes) : fabriquées une fois par ElevenLabs (workflow « Fabriquer les bruitages ») et, en gratuit, synthétisées par le robot.
Placement automatique : sur une vanne, un mot qui s'y prête (argent → caisse, photo → flash, mot de passe → clavier, bug → glitch, raté → sifflet), une émotion (gêne, tristesse, panique, choc) ou un blanc gênant ; un par réplique au plus, environ un toutes les 3 s, jamais deux fois le même d'affilée. En mode payant, Claude peut les choisir lui-même. **Jamais de rires enregistrés.** Pour ajouter un son : une ligne dans `CATALOGUE` (et sa version gratuite dans `sons_modernes.py`).

## Couverture, accroches et apprentissage
- **Couverture TikTok** : le moteur choisit l'instant où le titre est visible et le visage le plus expressif ; Buffer l'utilise comme image de couverture et le site comme vignette.
- **Deux styles d'accroche** (« POV : … » ou une question au spectateur) : chaque vidéo en prend un, les vues TikTok départagent peu à peu les deux styles (le meilleur sort plus souvent, l'autre reste essayé de temps en temps).
- **Les vidéos qui marchent servent de modèle** : la banque visuelle reprend le rythme et les cadrages des vidéos les plus vues, et les effets cinéma présents dans les vidéos les plus vues reviennent plus souvent.
- **Aperçu avant publication** : coupe « Publication automatique » dans ⚙️ Réglages → Publication ; chaque vidéo attend alors sur le site (⏸ En attente de validation) avec le bouton Publier.

## Animation des personnages
Élan et rebond dans les gestes, cheveux et vêtements qui suivent (mouvements secondaires), poids du corps qui change de jambe, vraie marche à l'entrée, visage tourné de trois quarts vers celui à qui on parle, personnages assis sur une chaise dans les lieux qui s'y prêtent, clignements et regard vers celui qui parle, micro-mouvements des sourcils, mains qui « battent » sur les mots appuyés, réactions juste après le mot qui frappe, gestes à deux (main sur l'épaule, « tope là », donner un objet, pousser) avec des mains qui atteignent vraiment l'autre.

## À savoir
- **Satire et personnages fictifs** : la mention est incrustée dans chaque vidéo et dans la légende. Le robot ne nomme aucune personne réelle et s'interdit toute consigne de vote.
- **Contenu IA** : la légende indique « Contenu généré par IA ». Si Buffer n'active pas automatiquement l'étiquette IA de TikTok, active une fois pour toutes l'option correspondante dans les réglages de ton compte TikTok si elle existe, ou passe par Upload-Post qui envoie l'étiquette officielle.
- **Crédits** : voix issues de *Multilingual LibriSpeech* (CC BY 4.0), transformées ; synthèse Chatterbox (MIT) ; voix de secours Piper/SIWIS (CC BY 4.0) ; polices Poppins (SIL OFL) ; générique et bruitages fabriqués à partir des échantillons d'orchestre VSCO 2 Community Edition (Versilian Studios, CC0) — voir `outils_sons/`. Les crédits sont ajoutés automatiquement à la légende.
- **Coûts estimés** : GitHub gratuit ; Buffer gratuit ; Modal (voix et décors) normalement couvert par les 30 $ de crédits gratuits mensuels — surveille la page *Usage* de Modal les premiers jours, et mets `PLAN_GAG` à `0` si besoin ; Claude quelques euros par mois.

## Organisation
- `moteur/principal.py` : chef d'orchestre (une exécution = une émission)
- `moteur/actu.py` : lecture des flux RSS
- `moteur/ecrire.py` : écriture du sketch (méthode comique, personnages, exemple de ton, script doctor)
- `moteur/casting.py` : choix automatique des voix
- `moteur/voix_modal.py` / `moteur/voix.py` : voix Chatterbox (Modal) et secours Piper
- `moteur/jt.py` : outils communs (sous-titres, sons, mixage, voix gratuites par personnage)
- `moteur/cartoon.py` / `moteur/marionnette.py` : dessin animé (sketchs, gags éclair, doublage) et personnages
- `moteur/studio.py` / `moteur/decor_dessin.py` / `moteur/decor_details.py` : direction artistique et réalisation sans IA, décors dessinés par le robot
- `moteur/garde_robe.py` : coiffures, barbes, couvre-chefs, imprimés et finitions des vêtements
- `moteur/humain.py` : personnages adultes (style « toons ») et leurs fiches (casting libre)
- `moteur/analyse_video.py` / `moteur/banque_visuelle.py` : analyse de l'image des vidéos TikTok envoyées, banque visuelle (détecteur de visages YuNet, licence MIT, dans `moteur/modeles/`)
- `moteur/publier.py` : publication TikTok (Buffer, ou Upload-Post)
- `moteur/site.py` : site de régie (GitHub Pages)
- `.github/workflows/publier.yml` : publication d'une vidéo à la demande (bouton du site)
- `episodes/` : textes de chaque émission et historique
