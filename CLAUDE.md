# Consignes du projet (préférences de l'auteur de la chaîne @petitsdramas)

À respecter pour toute modification du robot vidéo :

## Budget et outils
- **Outils payants activés par défaut** (Claude, ElevenLabs, décors et plans IA sur Modal, contrôle vidéo par Claude) : on vise
  toujours la meilleure qualité.
- **Bascule automatique sur les outils gratuits seulement s'il n'y a plus de crédit** (ou si l'outil ne répond pas) : chaque
  appel payant a un repli gratuit (Claude → sketchs de secours `moteur/secours.py` + studio sans IA ; ElevenLabs → Chatterbox →
  Piper ; décors IA → décors dessinés ; contrôle Claude → contrôle technique gratuit). La vidéo sort quoi qu'il arrive.
- Pas de nouveaux modèles d'IA plus coûteux : on garde les outils actuels (Modal, ElevenLabs, Buffer, dessin par le code).
- **Pas de 3D** (abandonnée : trop lourde et trop coûteuse).

## Style visuel
- **Nouveau style de personnage (octobre 2026, `moteur/toon.py`, réglage STYLE_PERSO=toon par défaut, « ancien » = marionnettes)** :
  copié sur l'image de référence de l'auteur et les vidéos du créateur animady67 (nos propres personnages, jamais les siens) :
  tête blanche en œuf de trois-quarts (1/4 de la hauteur), grands yeux ovales blancs à petite pupille, sourcils courts, bouche
  NORMALE dans le visage (petite moue fermée ; ouverte quand il parle : dents en grille, langue), corps élancé (sweat ample à
  capuche et cordons, short long, jambes blanches, grands pieds nus à orteils), trait noir fin et régulier, ombre douce grise
  sur la tête. Gestes naturels des vidéos : bras croisés, mains sur les hanches, main au menton, téléphone, main sur la bouche.
  Coiffures redessinées sur la tête en œuf (queue de cheval haute + mèche le long du visage, cheveux longs/carré, courts en calotte,
  dreads qui encadrent le visage même sous la casquette, afro, chignon), oreille côté nuque, plis du sweat, jupe droite, lèvres
  rouges épaisses pour le maquillage. Méthode : toujours comparer côte à côte avec les images des vidéos de référence.
  **Plus de style marionnette** : bras et jambes d'un seul contour (`toon.membre` : biceps, coude, mollet, cheville), sans boule aux
  articulations, manche qui sort du sweat sans trait, pli intérieur du coude, genou et mollet ; main sur le visage / téléphone : l'avant-bras passe devant la tête.
  Jambes nues et pieds nus d'un seul contour (`toon.jambe_pied`, d'après les vidéos) : cheville large, talon rond, semelle plate,
  pied plus court, talon rond, cheville fine avec sa bosse, dessus du pied qui descend en douceur, gros orteil + 4 petits
  orteils en bosses qui dépassent du bord, séparés par de petits traits ; les deux pieds vers où il regarde.
  Mains (`toon._main`, un seul contour via `toon.silhouette`) : au repos (doigts serrés + pouce), poing, index, paume, pouce ;
  bras croisés = mains à plat sur les biceps ; mains sur les hanches = main à plat sur la hanche (« hanche ») ; le poing
  fermé est remplacé par une main détendue (« detendue ») sauf colère ou objet tenu. Manche longue : la main est dessinée sous
  la manche (aucune articulation au poignet).
  Chaussures (`toon.chaussure`) d'un seul contour, dessinées sous le bas du pantalon (coupé droit, un pli sur la chaussure) ;
  t-shirt : buste + manches courtes d'UN seul contour (`toon.manche_courte`, bras nus dessinés dessous) ; objets tenus à taille
  réelle (×0,8 de l'échelle, doigts refermés par-dessus) ; cheveux : grosses mèches arrondies (`toon.meches`), volume bosselé,
  reflet brillant, ombre vers la nuque. Gestes (cartoon : `GESTES_TOON`, `POSES_TOON`, `bras_naturel`) : coudes pliés près du
  corps, un bras qui explique, gestes tenus ~3 s, amplitude bornée (pas de bras tendus ni levés derrière la tête). (Pied nu : garder la version validée par l'auteur, un essai plus long a été refusé.)
  Casting libre (personnages différents à chaque vidéo).
- **Le maximum de détails partout** : tenues, coiffures, barbes, chapeaux, accessoires, expressions du visage, décors.
- Tout l'univers visuel (lieu, tenues, plans, émotions) se construit autour de l'audio TikTok (paroles, intonations, émotions,
  ambiance) et de l'image de la vidéo d'origine ; la banque visuelle s'enrichit vidéo après vidéo.

## Montage (à garder en tête pour chaque vidéo)
- **Choix de l'auteur (25 octobre 2026) : montage « plan large » par défaut** (réglage MONTAGE = large) : un seul plan large et FIXE
  par scène, les personnages qui se parlent toujours à l'image, aucun zoom, aucun mouvement de caméra, aucune coupe sur la réaction
  (`studio.plans_larges`, `cartoon` → PLAN_LARGE) ; le jury n'ajoute jamais de plan serré dans ce mode. Le montage « dynamique »
  ci-dessous reste disponible dans les Réglages.
- Vidéos **dynamiques**, toujours en fonction de l'audio, de son univers et des échanges entre les personnages.
- **Beaucoup de changements de plan** : plans serrés et plans larges sur les personnages, plans de réaction de celui qui écoute.
- **Caméra vivante** : mouvements dans chaque plan (avancée, recul, travelling, caméra à l'épaule, zoom choc) et passages de plan
  variés (coupe franche, glissé, filé, zoom).
- **Tout doit rester fluide** : coupes calées sur la voix (entre deux mots ou sur un mot appuyé), mouvements adoucis, flou de
  mouvement sur les passages rapides, pas de plan trop court ni de faux raccord.
- **Pas de rires enregistrés** (rires du public façon série américaine, « oooh » du public) : supprimés à la demande de l'auteur. Bruitages « tendance » : catalogue `moteur/bruitages.py` (nos propres versions, libres de droits), à enrichir.
- **Image toujours nette** : aucun flou de mise au point ni de premier plan, aucun flou de mouvement sur les zooms (il dédoublait
  les personnages). **Plan serré = seul le personnage filmé à l'image** (personne coupé en deux) ; plan large = tout le monde.
- **Recréer toute l'histoire** de la vidéo TikTok, à notre sauce, sans qu'on le demande : âge, genre, taille et allure de chacun
  d'après le dialogue, la voix et l'image (« fiston », « papa, … » = ado : plus petit, cheveux courts, jamais de barbe) ;
  personnages dans des lieux différents (appel, visio, l'un ailleurs) = un décor chacun et coupe franche (`studio.separer_lieux`) ;
  personnes muettes dont on parle ou qu'on voit = compagnons dessinés à côté (`studio.compagnons`) ; coupes calées sur la vidéo d'origine.
  Garde-fous quand l'IA (surtout gratuite) répond mal : `studio.accorder_roles` (descriptions remises sur les rôles qui parlent),
  `appel_devine` / `lieux_devines` (appel deviné : l'ado dehors, le parent chez lui), `figurants_devines` (« la dame » à côté),
  `gag_dans_le_sujet` (pas de gag d'actualité hors sujet) ; le jury tire aussi des corrections de ses remarques écrites.
- **Réalisme visuel** (octobre 2026) : jeu d'acteur copié sur l'original et exagéré façon toons (`studio` → "jeu" : émotion, geste,
  intensité 1-3 ; réglage EXAGERE, 1.25 par défaut) ; lèvres calées sur chaque son du français (`moteur/levres.py`) ; décors IA
  décrits d'après la vidéo d'origine ("decors_vus"), agrandis par l'IA (Real-ESRGAN) et sans flou, avec carte de profondeur
  (Depth Anything) pour la parallaxe (réglage PARALLAXE) ; personnages teintés par la lumière du lieu + liseré (LUMIERE_DECOR) ;
  contrôle image par image gratuit (têtes coupées, chevauchements, sous-titre sur un visage → corrections du jury).
- **Finition « pro »** : 60 images/s en production (variable IPS, 30 en test), encodage x264 haute qualité (CRF 15, preset slow,
  tune animation) ; ombrage en aplat + contour extérieur épais (CEL) ; yeux vivants (saccades, clignements selon l'émotion) ;
  cheveux/vêtements en retard sur la tête ; voiture dessinée quand on en parle (`moteur/vehicules.py`) ; lumières vivantes
  (phares, télé, néon : LUMIERES_VIVES) ; effets manga (fond qui explose, traits de vitesse : MANGA) ; signature de la chaîne
  (logo qui « pop », courbe de couleurs : SIGNATURE) ; note et remarque de l'auteur depuis le site → `episodes/remarques_auteur.json`,
  prioritaires dans `qualite.regles_apprises`.
- **Qualité « 4K ramenée en 1080p »** : personnages dessinés en double résolution puis réduits (SSAA) ; mains à 3-4 doigts
  (gants toons), avant-bras effilés, bras qui s'étirent sur un geste vif ; décors IA en aplats doux + trait d'origine net
  (DECOR_APLATS), faux textes de l'IA effacés et remplacés par un gag lisible ; voiture qui passe au loin dans la rue
  (DECOR_VIVANT) ; parallaxe 72 % (fond) → 98 % (premier plan) ; jury IA attentif à la finesse de l'image.
  Styles de rendu au choix (STYLE_RENDU) : `cel` (aplats pro, défaut), `volume` (effet 3D doux), `3d` (3D toon brillant) :
  relief « gonflé » calculé par partie du corps puis éclairé (pas de moteur 3D). Le choix du style revient à l'auteur.
- Position assise : vue de face (buste, genoux et jambes dans le même sens).
- **Améliorations d'octobre 2026 (liste V/D/P/S/F choisie par l'auteur)** :
  voix gratuites : références de jeu par émotion (`moteur/voix_refs.py`, voix/refs/<rôle>_<émotion>.wav, faites avec ElevenLabs ou
  Google Chirp 3 ; un enregistrement de l'auteur du même nom n'est jamais écrasé), juge automatique UTMOS + Whisper (MOS_MIN, la
  meilleure prise gagne), Kokoro en repli avant Piper, Piper = dernier recours avec badge « voix de secours » sur le site,
  hésitations / souffles dans les voix gratuites ; décors : réutilisation d'un lieu ressemblant de la banque avec variante
  (`decors.voisin` / `varier`) et budget Modal mensuel (DECORS_MOIS, 60 par défaut), intérieur de voiture dessiné (« voiture »,
  volant et tableau de bord au premier plan), lieux plus détaillés ; personnages : larmes, sueur, mâchoire qui tombe, yeux au ciel
  (`toon._larmes_sueur`), poses tenues « poches », « appuye », « pianote » (téléphone), « volant », veste en jean, maillot de foot,
  chaîne, banane, sac à dos, écouteurs ; gestes calés sur les mouvements de l'original (`analyse_video` → "gestes",
  B["gestes_origine"], tenus 2 s au moins) ; plan de réaction sur la chute ; musiques IA ACE-Step (`moteur/musique_modal.py`,
  workflow « Musiques d'ambiance » → sons/musique, MUSIQUE_IA=0 pour la nappe synthétisée) ; aperçu rapide 10 s (case du site,
  24 images/s, jamais publié).
- **Améliorations d'octobre 2026, 2e liste (3, 6-11, 13, 16, 21, 22, 29, 30)** : décors dessinés vivants (`moteur/decor_anime.py` :
  trotteuse, vapeur de tasse, ventilateur, poisson rouge, match à la télé du bar, porte du hall, chat qui traverse, pigeons qui
  s'envolent quand on crie, gouttes sur les vitres, orage + tonnerre `SM.meteo`, essuie-glace ; réglage DECOR_VIVANT) ; ombres
  portées des personnages au sol (+ sur le mur le soir, jamais dehors ; OMBRES) ; reflets dans le miroir, les vitrines et la vitre
  le soir (plans larges seulement : pas de tête fantôme en gros plan) ; tatouages et bracelets sur les bras nus (adultes seulement),
  teint qui change peu à peu (colère qui monte, pâleur, joues de gêne : `toon.teint`) ; appels (lieux séparés) : écran partagé,
  plans d'écoute avec voix filtrée « téléphone » (`SM.telephone`), téléphone collé à l'oreille (APPEL_PARTAGE) ; « revenons… /
  deux heures plus tôt » = rembobinage façon cassette (REMBOBINAGE) ; boutons « Juste la voix » (autres voix de la banque :
  VOIX_NOUVELLES) et « Juste le décor » (décors tirés à neuf : DECOR_GRAINE) ; bêtisier du dimanche (`moteur/betisier.py`,
  workflow betisier.yml, ratés notés par le jury) ; voix de l'auteur enregistrée depuis le site (`moteur/voix_auteur.py`,
  workflow voix_auteur.yml → voix/refs, priorité au casting, jamais écrasée).
- **Sons TikTok = filière totalement à part des sketchs** (demande de l'auteur) : onglet « 🎵 TikTok » du site (lien à coller, liste
  de profils PROFILS_TIKTOK, bouton « son au hasard », planning propre HEURE_TIKTOK + FREQUENCE_TIKTOK, liste de ses vidéos) ;
  jamais mélangée aux sketchs/idées du robot (plus de lien TikTok dans « Créer », vidéos TikTok absentes de l'onglet Vidéos des
  sketchs, plannings comptés à part : historique "filiere" = "tiktok", `planning` → FILIERE). Créneau TikTok lancé par le garde
  (garde.yml → emission.yml filiere=tiktok, file « sons-tiktok ») ; `moteur/profils_tiktok.py` choisit une vidéo au hasard (jamais
  déjà utilisée, 8 à 150 s ; yt-dlp puis tikwm) ; aucun son utilisable = pas de vidéo (jamais un sketch à la place).
  Profils déjà connus (`profils_tiktok.connus()` : comptes des sons déjà repris, jamais notre chaîne) = liste de départ tant que
  PROFILS_TIKTOK est vide ; sur le site, liste pré-remplie et bouton « ➕ Ajouter les profils déjà connus ».
- **Site toujours à jour** (`moteur/site.py`, site.yml) : GitHub Pages refuse au-delà de 1 Go → les 6 vidéos les plus récentes en
  pleine qualité (partage manuel), les autres en version légère 720p (~5 Mo, cache `.cache_site` du workflow), plafond 930 Mo
  (au-delà : vidéo lue depuis les Releases) ; après chaque mise en ligne, `moteur/verif_site.py` vérifie que la dernière vidéo est
  visible sur le site en ligne (sinon 2e mise en ligne puis alerte téléphone) ; l'appli relit l'historique à chaque retour
  (page jamais servie depuis un cache périmé) ; nouvelle vidéo TikTok = point rouge sur l'onglet 🎵 TikTok + message dans l'accueil.
- **Barre de progression en temps réel** (accueil + onglet TikTok, PC et mobile) : le robot publie son avancement toutes les 8 s
  (`moteur/progression.py` → statut « progression-<run> » du commit : %, type, étape, heure de fin ; dessin des images = vitesse
  réelle) ; le site le relit toutes les 5 s, fait avancer barre et compte à rebours chaque seconde, montre la file d'attente et la
  mise en ligne du site (durées habituelles des derniers runs). Workflow emission.yml : permission `statuses: write`.
- **File d'attente des fabrications** (`moteur/file_attente.py`, job « file » d'emission.yml, 340 min max) : une seule vidéo fabriquée à
  la fois (sketch, son TikTok, manuelle, refaire, aperçu, série), dans l'ordre des demandes (heure de lancement de la tentative :
  une fabrication relancée par le garde repasse en fin de file, et revérifie son tour au début du job « emission ») ; aucune demande
  perdue (les files « concurrency » de GitHub n'en gardent qu'une en attente) ; les réveils « rien à faire » ne bloquent personne ;
  le site affiche « En file d'attente : n vidéo(s) avant ».
  Onglet TikTok : bouton « 🎲 Plusieurs vidéos à la chaîne » + nombre (1 à 10) → emission.yml chaine=« 1/n » ; chaque vidéo finie
  (même ratée) lance la suivante (« 2/n »…, dernière étape d'emission.yml, pas de doublon si le garde relance) ; la barre affiche
  « vidéo 2/n : … ». Le robot publie son avancement toutes les 8 s et la file regarde de moins en moins souvent (quota de l'API GitHub).
- **Vitesse de fabrication** (octobre 2026) : dessin accéléré sans changer un pixel (toile des personnages remise à zéro seulement là où
  on a dessiné, comparaisons de couleurs par OpenCV, dégradés et barbe sans grille, grain de barbe calculé une fois) ; 2e version
  du jury = **redessin partiel** (`cartoon.images_a_refaire` : empreinte de chaque plan et réplique ; seules les images autour de ce
  qui change sont redessinées, le reste est recopié de la 1re version sans réencodage, coupé aux images clés, REDESSIN_PARTIEL=0
  pour couper) ; **jamais de vidéo perdue par la limite de temps** : job emission 180 min (LIMITE_JOB_MIN), mise en pause puis
  reprise automatique 25 min avant la limite (`principal.limite_job`, `cartoon.TempsDepasse`, voir « Pause et reprise »). Vérifier toute accélération image par image avec
  PYTHONHASHSEED fixé (le dessin varie très légèrement d'un lancement à l'autre sinon).
  **Dessin partagé entre plusieurs machines** (`moteur/dessin_partage.py`, `dessin_aide.py`, workflow dessin.yml) : au-delà de
  1 200 images (PARTAGE_MIN_IMAGES), la vidéo est coupée en morceaux ; 3 machines d'aide (AIDES) en dessinent chacune un pendant
  que la principale fait le sien (paquet + morceaux échangés par la release temporaire « dessins-temp », vidée ensuite, jamais de
  secret dans le paquet), puis recollage sans réencodage ; une aide en retard ou en échec → la principale redessine le morceau
  elle-même (rien n'est perdu). PYTHONHASHSEED=0 partout. DESSIN_PARTAGE=0 pour couper ; DESSIN_LOCAL=dossier pour les essais.
  **Pause et reprise** (`moteur/reprise.py`) : le dessin se fait par blocs (BLOC_IMAGES, 600) ; à 25 min de la limite, la fabrication
  (1re OU 2e version du jury) se met en pause : sketch, son, voix, décors, blocs déjà dessinés, 1re version et avis du jury sont
  sauvegardés (release « dessins-temp », 3 jours) et une fabrication « Reprise d'une fabrication en pause » est relancée avec les
  mêmes réglages (entrée chaine = « suite:<nom>|<chaîne d'origine> »), en tête de file ; elle repart du bloc suivant (vidéo
  identique à l'image près). Essai : entrée rendu = essai_pause (pause après le 1er bloc).
- **Améliorations d'octobre 2026, 3e liste (1-7, 9, 10 choisis par l'auteur)** : point de sauvegarde au fil du dessin (chaque bloc fini
  déposé en arrière-plan ; une relance repart du dernier bloc : `reprise.poser_point`, `deposer_bloc`, `point_existant`) ; Réveil
  de secours `moteur/relance.py` (relance aussi les fabrications annulées PAR GITHUB, jamais celles annulées par l'auteur) ; date
  des fichiers à l'heure de Paris ; alertes : appareils disparus notés par empreinte (`episodes/abonnements_morts.json`) et retirés
  par le site ; sous-titres : Whisper large-v3-turbo (en cache) + correction des mots mal entendus par l'IA (`doublage.corriger_textes`,
  jamais de réécriture) ; pyannote si le secret HF_TOKEN (clé Hugging Face gratuite) est réglé (`locuteurs.pyannote`) ;
  **pré-jury** : les règles sûres du jury appliquées avant de dessiner (`cartoon.rendre(plans_seuls=True)` + `qualite.jury_gratuit`,
  PRE_JURY=0 pour couper) ; quota de l'API GitHub surveillé (`moteur/quota.py` : barre et file ralentissent, voyant sur la barre) ;
  vidéos d'essai rangées à part (filtre « 🧪 Essais », historique "essai") et effacées au bout de 3 jours (garde → supprimer.yml ESSAIS).
  Réglages → notifications : « Activer » et « Désactiver sur cet appareil » (retire l'appareil de PUSH_ABONNEMENTS).
- **Bonne voix sur le bon personnage (sons TikTok)** : `locuteurs.affiner` vérifie qui parle MOT PAR MOT (empreinte vocale ECAPA
  autour de chaque mot, comparée à chaque voix, fil le plus probable façon Viterbi, 2-3 tours ; une « voix » presque muette est
  rattachée à la plus proche) puis `caler_sur_phrases` met chaque changement de personne sur la fin de phrase la plus proche
  (3 mots au plus) ; chaque mot a sa certitude (`sure`) : l'IA qui ne lit que le texte ne peut plus déplacer une réplique « voix
  sûre » (`doublage.voix_sure`) ; deux voix ne jouent jamais le même personnage (`doublage.casting_unique`). Réglages `_P` trouvés
  sur un banc d'essai (dialogues montés avec nos voix, vérité connue : 84 % → 96 % de temps de parole bien attribué).
- **Barbes** : jamais de grosse barbe (barbe mal rasée au plus) ; adultes et 16-17 ans seulement, jamais d'enfant barbu.
- **Jury qualité** (`moteur/qualite.py`) : 5 critiques (humoriste, réalisateur, DA, son, spectateur), gratuit ET Claude, corrections
  automatiques puis nouvelle version (on garde la meilleure), mémoire des erreurs qui reviennent ; à enrichir à chaque remarque de l'auteur.
- **Fiabilité de fabrication** : le dessin toon doit rester rapide (masques sur-échantillonnés ×2, ×1 sur les très gros plans,
  contours par `cv2.findContours`, jamais de `np.mgrid` ni de grosse dilatation : un gros plan coûtait 40 s et 2,4 Go par image et
  GitHub coupait la machine) ; un dessin qui plante repasse en ancien style ; le « Réveil de secours » (garde.yml) relance une
  fois toute fabrication en échec des 6 dernières heures.
- Code : `moteur/studio.py` (`decouper`, `plans_larges`) et `moteur/cartoon.py` (`vue`, `cadre_plan`) ; réglage MONTAGE (large par défaut, dynamique, simple).

## Mode amélioré (Claude + outils payants : c'est le mode par défaut dès qu'il y a du crédit)
L'auteur rechargera à un moment le crédit Claude (Anthropic). Le mode amélioré s'appuie sur Claude et sur les outils payants
déjà en place, pour aller plus loin que le mode gratuit, et doit être enrichi au fil du temps :
- **Claude** : écriture et doublage (comprendre l'audio, découpage en scènes, émotions, indications de jeu), direction artistique
  du studio (lieux, tenues, coiffures, objets, gags écrits, plans et mouvements de caméra, réactions), analyse des images clés de
  la vidéo TikTok d'origine, contrôle qualité de la vidéo finie.
- **Graphisme** : décors générés (Stable Diffusion XL sur Modal) adaptés à l'histoire, en plus des décors dessinés.
- **Voix** : ElevenLabs (voix réalistes, rires, colère, voix sur mesure de la chaîne).
- Le mode gratuit (sans Claude) doit **toujours** rester disponible en repli automatique si le crédit manque.
- Les briques existent (`ecrire.py`, `doublage.py` : consignes « studio », `controle.py`, `decors.py`) : à enrichir sans jamais
  casser le repli gratuit.

## Relais gratuits de Claude (branchés : secrets GitHub MISTRAL_API_KEY et GEMINI_API_KEY)
- Tous les appels passent par `reseau.claude()` : Claude d'abord (s'il a du crédit), puis **Mistral** (texte, humour en français)
  et **Gemini** (en premier pour les images : doublage, jury) ; offre gratuite Mistral : seuls ministral-14b (30/min, images) et
  ministral-8b (188/min) répondent (medium/small = 0/min, large = payant) ; un fournisseur à quota épuisé est sauté pour la fabrication ;
  sans aucune IA : sketchs de secours + studio sans IA. Coût compté à 0 pour Mistral / Gemini. Voyants du site : `moteur/credits.py`
  (episodes/credits.json, bouton « Vérifier maintenant » = workflow credits.yml, et à chaque vidéo).
- Pistes suivantes si besoin : Groq, OpenRouter `:free`, modèle libre sur Modal (vLLM), LiteLLM. GitHub Models et Cerebras ne sont
  plus gratuits ; Cohere interdit l'usage commercial.

## Langue
- L'auteur parle français : répondre et documenter en français simple.
