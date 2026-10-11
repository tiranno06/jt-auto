# L'info en caoutchouc — robot 100 % automatique

Chaque matin, sans aucune intervention :
1. le robot lit les titres politiques des dernières 36 h (franceinfo, Le Monde, Le Figaro, 20 Minutes, L'Express, BFM) ;
2. **Claude** choisit LE sujet le plus drôle du jour et écrit un faux JT de 30 à 45 s : le présentateur Jean-Michel Plateau, l'envoyée spéciale Martine Couloir en direct, et un « expert » fictif. Une deuxième passe (« script doctor ») réécrit les blagues les plus faibles. Uniquement des faits présents dans les titres, aucune personne réelle nommée ;
3. **Chatterbox** (open source, licence MIT) fait parler chaque personnage avec sa voix, sur un GPU **Modal**. Les voix ont été choisies automatiquement par le robot lors de sa première exécution, parmi les lecteurs du corpus *Multilingual LibriSpeech* (CC BY 4.0) ;
4. **Wan 2.2** (open source, Apache 2.0) génère sur Modal un plan gag « reconstitution » de quelques secondes, signalé à l'écran comme image générée par IA (facultatif) ;
5. le moteur fait le montage façon studio télé : écran partagé plateau/direct, plans large et serré, réactions du présentateur après chaque vanne, zooms sur les chutes, sous-titres karaoké, bandeau défilant de fausses dépêches, générique, ambiance de salle pour le direct, son normalisé au standard TikTok ;
6. **Buffer** (plan gratuit) publie la vidéo sur TikTok, avec la mention « contenu généré par IA » dans la légende ;
7. la vidéo est aussi archivée dans les *Releases* du dépôt.

Si un service est en panne, le robot ne s'arrête pas : sans Modal, il utilise la voix de secours Piper et saute le plan gag ; si la publication échoue, la vidéo reste dans les Releases.

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
- **décors dessinés par le robot** (`moteur/decor_dessin.py`) : pièces complètes avec fenêtre dont le ciel suit l'heure, meubles, étagères garnies, tableaux, horloge, lampes allumées le soir, tache de soleil au sol, comptoir ou bureau au premier plan. Utilisés quand les décors IA sont coupés ou indisponibles ;
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
- `moteur/humain.py` dessine des **adultes dans le style de nos anciens personnages** : trait noir, aplats et ombre nette, grosse tête ronde aussi expressive que celle de Jojo, Kévin et Lila (mêmes yeux brillants, sourcils, bouche synchronisée, coiffures, effets) sur un vrai corps d'adulte (environ 5 têtes de haut) : cou, épaules, buste, taille, hanches, bras et jambes d'un seul tenant qui se plient en souplesse, mains à quatre doigts et pouce, peau de couleur humaine, oreilles, rides selon l'âge, barbe, lunettes, cheveux qui grisonnent, tenue complète.
- **Casting libre** : à chaque vidéo, de nouveaux personnages. Le genre vient de la voix (doublage TikTok) ou du prénom du sketch ; l'âge de ce qui est dit (« mamie », « papa », « docteur »…) ou de Claude ; la coiffure, la couleur des cheveux et des habits de la vidéo d'origine ; le reste (visage, peau, yeux, corpulence) est tiré au hasard avec la graine de l'épisode. Les figurants sont aussi des adultes.
- Toute la mise en scène s'applique (plans, gestes, mimiques, intonation, réactions) ; les cadrages sont adaptés aux proportions d'adulte.

### Vraie 3D (Blender, coupée par défaut)
Réglage **Vraie 3D (Blender)** : les personnages adultes sont construits en 3D d'après la même fiche (`moteur/blender_humain.py`, logiciel libre Blender, rendu Cycles : vraies ombres et lumières), animés par les mêmes poses, puis posés sur les décors (`moteur/rendu3d.py`). Le workflow n'installe Blender que si le réglage est activé. Les poses identiques ne sont rendues qu'une fois. C'est **beaucoup plus long** (1 à 3 s par pose sur les serveurs GitHub : une vidéo de 90 s peut dépasser une heure, la limite du workflow est de 120 min). En cas d'échec, la vidéo sort automatiquement en 2D. C'est une première version : formes encore simples (style « figurines »), à affiner.

Réglage **Rendu détaillé (studio)** dans l'onglet ⚙️ : coupé, le robot revient exactement à l'ancien rendu (bonshommes blancs, plans simples). Le rendu détaillé prend environ deux fois plus de temps de calcul sur GitHub (gratuit).

## Réglages depuis l'application (onglet ⚙️ Réglages)
Rythme (chaque jour, un jour sur deux, un jour sur trois, pause), heure de fabrication, durée et ton des sketchs, modèle Claude, nom de l'émission, plan gag IA, bouton « Fabriquer une émission maintenant » et raccourcis vers les crédits Modal / Claude, Buffer et TikTok Studio. Chaque réglage s'applique dès la prochaine émission.

## Réglages avancés (facultatifs)
| Je veux… | Où |
|---|---|
| changer le nom de l'émission | *Settings → Secrets and variables → Actions → Variables* → `NOM_EMISSION` |
| un modèle Claude plus drôle (un peu plus cher) | variable `MODELE_CLAUDE`, par ex. `claude-opus-5-5` |
| publier en privé pour tester | ajouter la variable d'environnement `TIKTOK_VISIBILITE=SELF_ONLY` dans le workflow |
| désactiver le plan gag IA (économiser les crédits Modal) | variable `PLAN_GAG` = `0` |
| refaire le casting des voix | supprimer le dossier `voix/` du dépôt (sauf `.gitkeep`) |
| mettre en pause | *Actions* → « Émission du jour » → *…* → *Disable workflow* |

En cas d'échec, GitHub t'envoie un e-mail ; le détail est dans l'onglet Actions.

## À savoir
- **Satire et personnages fictifs** : la mention est incrustée dans chaque vidéo et dans la légende. Le robot ne nomme aucune personne réelle et s'interdit toute consigne de vote.
- **Contenu IA** : la légende indique « Contenu généré par IA ». Si Buffer n'active pas automatiquement l'étiquette IA de TikTok, active une fois pour toutes l'option correspondante dans les réglages de ton compte TikTok si elle existe, ou passe par Upload-Post qui envoie l'étiquette officielle.
- **Crédits** : voix issues de *Multilingual LibriSpeech* (CC BY 4.0), transformées ; synthèse Chatterbox (MIT) ; voix de secours Piper/SIWIS (CC BY 4.0) ; polices Poppins (SIL OFL) ; générique et bruitages fabriqués à partir des échantillons d'orchestre VSCO 2 Community Edition (Versilian Studios, CC0) — voir `outils_sons/`. Les crédits sont ajoutés automatiquement à la légende.
- **Coûts estimés** : GitHub gratuit ; Buffer gratuit ; Modal (voix + plan gag) normalement couvert par les 30 $ de crédits gratuits mensuels — surveille la page *Usage* de Modal les premiers jours, et mets `PLAN_GAG` à `0` si besoin ; Claude quelques euros par mois.

## Organisation
- `moteur/principal.py` : chef d'orchestre (une exécution = une émission)
- `moteur/actu.py` : lecture des flux RSS
- `moteur/ecrire.py` : écriture du sketch (méthode comique, personnages, exemple de ton, script doctor)
- `moteur/casting.py` : choix automatique des voix
- `moteur/voix_modal.py` / `moteur/voix.py` : voix Chatterbox (Modal) et secours Piper
- `moteur/video_modal.py` : plan gag Wan 2.2 (Modal)
- `moteur/dessin_jt.py` / `moteur/jt.py` : dessins, montage studio et mixage
- `moteur/cartoon.py` / `moteur/marionnette.py` : dessin animé (sketchs, gags éclair, doublage) et personnages
- `moteur/studio.py` / `moteur/decor_dessin.py` : direction artistique et réalisation sans IA, décors dessinés par le robot
- `moteur/humain.py` : personnages adultes 2D en volume et leurs fiches (casting libre)
- `moteur/rendu3d.py` / `moteur/blender_humain.py` : vraie 3D (Blender), réglage RENDU_3D
- `moteur/analyse_video.py` / `moteur/banque_visuelle.py` : analyse de l'image des vidéos TikTok envoyées, banque visuelle (détecteur de visages YuNet, licence MIT, dans `moteur/modeles/`)
- `moteur/publier.py` : publication TikTok (Buffer, ou Upload-Post)
- `moteur/site.py` : site de régie (GitHub Pages)
- `.github/workflows/publier.yml` : publication d'une vidéo à la demande (bouton du site)
- `episodes/` : textes de chaque émission et historique
