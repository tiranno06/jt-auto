# Consignes du projet (préférences de l'auteur de la chaîne @petitsdramas)

À respecter pour toute modification du robot vidéo :

## PRIORITÉ (décision de l'auteur du 11 novembre 2026)
- **On ne travaille plus QUE sur la filière « Sons TikTok »** : reprise des sons et des voix des vidéos TikTok, profils TikTok,
  création des vidéos à partir de ces voix (écoute, qui parle, casting, mise en scène, dessin, contrôle, publication). Tout le reste
  (sketchs écrits par le robot, émissions, anciens styles de personnages toon / marionnettes, voix de synthèse des sketchs…) est mis de
  côté : on n'y touche plus, sauf si une modification de la filière TikTok l'exige, et on ne le propose plus dans les listes d'idées.
- **Grand ménage du 15 novembre 2026 (demande de l'auteur)** : sur le site, tout ce qui concerne les sketchs et les trois personnages du
  début (Jojo, Kévin, Lila : rôles « presentateur », « invite », « envoyee » dans le code, qui restent les noms internes des personnages
  des sons TikTok) est MASQUÉ, pas effacé : onglets Accueil et Vidéos (sketchs) cachés, l'onglet 🎵 TikTok est la page d'accueil (la
  fiche d'une vidéo TikTok s'ouvre toujours dans l'onglet Vidéos, filtre « tiktok »), réglages d'écriture, personnalités, séries,
  planning des sketchs, voix des personnages, mode réaliste, ma voix, bêtisier cachés ; « Refaire » ne propose que « nouveaux décors ».
  Mécanisme : classe CSS `ancien` + `body.tiktok-seul` (`site.modeSite`, `tiktokSeul`) ; variable GitHub SITE_COMPLET=1 pour tout
  réafficher. Les anciennes consignes (sketchs, style toon, marionnettes, voix de synthèse, montage dynamique…) sont rangées dans
  `docs/archives_sketchs.md` (à relire seulement si l'auteur reprend les sketchs).
- **Nouveau logo (15 novembre 2026, demande de l'auteur : plus de Jojo)** : `marque.duo` : deux personnages croquis (elle en colère,
  lui choqué avec une goutte de sueur) dans un médaillon rond sur papier, sur le fond jaune à rayons ; sert partout (`marque.logo` :
  icône de l'appli et photo de profil, `filigrane` en haut des vidéos, `signature` = carton de fin). Ancienne tête : `marque.tete_jojo`.

## Budget et outils
- **Outils payants activés par défaut** (Claude, ElevenLabs, décors et plans IA sur Modal, contrôle vidéo par Claude) : on vise
  toujours la meilleure qualité.
- **Bascule automatique sur les outils gratuits seulement s'il n'y a plus de crédit** (ou si l'outil ne répond pas) : chaque
  appel payant a un repli gratuit (Claude → IA gratuites (Gemini, Groq, Mistral, OpenRouter) puis studio sans IA ; isolation et
  transcription ElevenLabs → Demucs / Groq / Whisper ; décors IA → décors dessinés ; contrôle Claude → contrôle technique gratuit).
  La vidéo sort quoi qu'il arrive.
- Pas de nouveaux modèles d'IA plus coûteux : on garde les outils actuels (Modal, ElevenLabs, Buffer, dessin par le code).
- **Pas de 3D** (abandonnée : trop lourde et trop coûteuse).

## Style visuel
- **Le maximum de détails partout** : tenues, coiffures, barbes, chapeaux, accessoires, expressions du visage, décors.
- Tout l'univers visuel (lieu, tenues, plans, émotions) se construit autour de l'audio TikTok (paroles, intonations, émotions,
  ambiance) et de l'image de la vidéo d'origine ; la banque visuelle s'enrichit vidéo après vidéo.

## Montage (à garder en tête pour chaque vidéo)
- **Choix de l'auteur (25 octobre 2026) : montage « plan large » par défaut** (réglage MONTAGE = large) : un seul plan large et FIXE
  par scène, les personnages qui se parlent toujours à l'image, aucun zoom, aucun mouvement de caméra, aucune coupe sur la réaction
  (`studio.plans_larges`, `cartoon` → PLAN_LARGE) ; le jury n'ajoute jamais de plan serré dans ce mode. Le montage « dynamique »
  (plans serrés, caméra vivante : voir `docs/archives_sketchs.md`) reste au choix dans les Réglages.
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
- **Site et appli rapides (choix de l'auteur, 31 octobre 2026 : A 1-2-3-6, B 7-11, C 12-15, D 16-17)** : **suppression directe** depuis
  l'appli (API GitHub : historique.json modifié par l'appli avec 3 essais si le robot écrit en même temps, fichiers des archives
  effacés : vidéo, légende, _web.mp4, .jpg ; vérifiée, « ✅ Supprimée pour de bon » ou « ❌ Réessayer » ; mémorisée sur l'appareil
  « jt_supprimees » : jamais réaffichée ; sans droit d'écriture du jeton : supprimer.yml, sans ffmpeg) ; le robot fabrique lui-même
  la **version légère 720p (_web.mp4) et la couverture (.jpg)** rangées dans les archives (historique "web") : l'appli les lit
  directement, le site ne garde que les 6 pleines qualités pour le partage ; **site reconstruit seulement pour une nouvelle vidéo**
  (plus après suppression, publication, régie) ; ouverture instantanée (service worker : copie gardée tout de suite, version en ligne
  pour la fois suivante ; dernier historique gardé « jt_historique ») ; **tirer vers le bas / bouton 🔄** ; rafraîchissement dès
  qu'une fabrication finit ; lectures conditionnelles (ETag / 304, quota ménagé) ; **nouvelle version détectée** (version.txt =
  empreinte du code, bouton « ✨ Nouvelle version ») ; boutons à réponse immédiate avec retour en arrière si GitHub refuse ; voyant
  de connexion dans l'en-tête (🟢 à jour il y a… / 🟠 hors connexion / 🔴 clé expirée).
- **Liste du 31 octobre 2026 (choix de l'auteur 4, 6, 7, 9, 12, 14)** : **note de confiance** de chaque vidéo (`verif_finale.confiance` :
  100 moins les points à vérifier et contrôles ratés, jury < 6/10 ; historique "confiance", badge 🛡️ et tri « plus sûres d'abord ») ;
  **recherche et filtres** de l'onglet TikTok (texte, ⚠️ à vérifier, à publier, publiées, profil d'origine, date ; gardés sur
  l'appareil « jt_filtres ») ; **calendrier de publication** (prochains jours d'après PUBLI_FILE et l'heure, ▲▼ ou glisser pour
  changer le jour, vidéos programmées) ; **chaîne en parallèle** (PREPA_PARALLELE=1 : la vidéo k/n lance k+1 quand elle commence à
  dessiner (`principal.tour_de_dessiner`), k+1 prépare son écoute puis attend son tour avant de dessiner (`file_attente.prepa_parallele`,
  `attendre(avant_dessin=True)`) ; son déjà pris passé en entrée « eviter » (EVITER) ; nom du run « Son TikTok (k/n) », pas de
  doublon à la fin (sortie/.suivante_lancee)) ; **machines d'aide selon la durée** (`dessin_partage.nb_aides` : ~1 000 images par
  machine, 1 à 5 ; AIDES=n impose) ; **nouvelles poses croquis** (meubles `B["meubles"]` → p["meuble"] : malade au lit sous la
  couette dans sa chambre, canapé au salon, volant en voiture, accoudé au comptoir au bar / resto / magasin ; `croquis.lit_face`,
  `couette`, `canape_face`, `comptoir` ; couleurs en BGR). **Appels : écran coupé en deux du début à la fin** (chacun dans son décor,
  aucun changement de plan ; APPEL_CONTINU=0 pour l'ancien montage alterné). **Bouton « À publier » partout** : sur la vidéo ouverte
  (#aPublier) et sur les vidéos TikTok de la page Vidéos (état « ✅ À publier (n° k) » visible), même bouton que l'onglet TikTok
  (`boutonPubli`, `majPubliPartout`). **Onglet TikTok en menus déroulants** (demande de l'auteur, 1er novembre 2026) : chaque bloc
  (lien, profils, lancer des vidéos, vidéos automatiques, publication automatique, mes vidéos) est un `details.groupe.repliTk`,
  ouvert / fermé gardé sur l'appareil (« jt_replis ») ; « Lancer des vidéos » et « Mes vidéos TikTok » ouverts au départ ; la
  recherche et les filtres dans « 🔎 Rechercher et filtrer » (ouvert si un filtre est actif) ; la fabrication en cours reste visible.
- **Compteur « vidéos à publier » (demande de l'auteur du 15 novembre 2026)** : au-dessus de chaque cadre « ⏳ Fabrication en cours »
  (accueil et onglet TikTok), `site.rendreStock` : nombre de vidéos qui restent à envoyer sur TikTok (cochées « À publier » pas encore
  publiées + déjà programmées), jusqu'à quel jour elles tiennent (créneaux 1 ou 2 par jour) et un conseil en couleur (🔴 ≤ 2 jours :
  lancer une nouvelle salve, 🟠 ≤ 5 jours, 🟢 sinon) ; avertit si la publication automatique est coupée ; relu toutes les 30 s.
- **Vitrine du profil retirée (demande de l'auteur du 15 novembre 2026)** : cadre « 🏪 Vitrine du profil » masqué (classe `ancien`) et
  plus préparée chaque lundi (vitrine.yml : seulement si la variable VITRINE=1) ; les nouveaux créateurs proposés restent.
- **Ordre de l'onglet TikTok (demande de l'auteur du 15 novembre 2026)** : compteur des vidéos à publier, « ⏳ Fabrication en cours »,
  puis tout de suite « 🎬 Mes vidéos TikTok » (repliable comme les autres blocs), puis profils, « 🔗 Une vidéo sur un son TikTok » juste
  au-dessus de « 🎲 Lancer des vidéos », puis vidéos automatiques, publication…
- **Bouton « ⚡ Charger la dernière version maintenant »** (Réglages → Avancé → Application, demande de l'auteur du 15 novembre 2026) :
  version.txt relu sans cache ; nouvelle version -> copies gardées effacées et page rechargée (`rechargerPropre`) ; site en cours de
  reconstruction (site.yml) -> l'appli attend et se recharge toute seule dès que la nouvelle version est en ligne.
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
- **Plusieurs vidéos fabriquées en même temps (demande de l'auteur du 15 novembre 2026)** : réglage « ⚡ Vidéos fabriquées en même temps »
  (onglet TikTok, « Lancer des vidéos » ; variable EN_MEME_TEMPS, 2 par défaut, 1 à 8 ; 1 = l'ancien fonctionnement, une après l'autre
  avec la préparation de la suivante pendant le dessin). `file_attente.en_meme_temps` / `bloquants` : une fabrication n'attend que s'il
  y a déjà N fabrications lancées avant elle et pas finies. Chaîne « k/n » : avec N ≥ 2, la vidéo k lance k+1 dès que son son est choisi
  (`principal.lancer_suivante`, son passé en « eviter » : jamais deux fois le même), k+1 attend une place libre ; avec N = 1, lancement
  au moment de dessiner (`tour_de_dessiner`). Machines d'aide au dessin par vidéo selon N (`dessin_partage.nb_aides` : 5 / 3 / 2 / 1 /
  aucune au-delà de 4 ; GitHub : 20 machines à la fois pour le compte ; dépôt public = minutes gratuites). Pré-écoute : un son prêt n'est
  pris que par une seule fabrication (`pre_ecoute.reserver`). Limites : quotas à la minute des IA gratuites plus vite atteints (repli
  sur l'IA suivante), budget Modal inchangé au total.
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
- **Corrections de l'audit (25 octobre 2026)** : le créneau d'une vidéo du planning est celui de sa DEMANDE (`planning.moment` : heure de
  création du run) : une vidéo qui a attendu son tour ou qui est relancée garde son créneau (plus d'abandon « rien à faire ») ; une
  2e demande pour le même créneau ne part pas (`planning.deja_en_file`, nom du run « Émission du jour (créneau) » / « Créneau son
  TikTok ») ; le Réveil de secours relance la fabrication EN ENTIER (elle attend dans la file, 340 min, plus dans la fabrication) ;
  une vidéo supprimée pendant une fabrication ne revient plus (`fusion.fusion_historique` avec le point de départ commun) ;
  versions des bibliothèques figées dans `contraintes.txt` (`pip … -c contraintes.txt` partout, sauf yt-dlp toujours à jour ;
  changer un numéro = le tester d'abord) ; musiques d'ambiance en MP3 ; essai complet appel + pause + reprise dans les tests
  (`TestVideoComplete.test_appel_pause_et_reprise`) ; aucun nom de réglage de `cartoon.rendre` réutilisé dans la fonction
  (test `test_rendre_garde_ses_parametres`) ; site sans connexion limité par GitHub : message « suivi en pause » au lieu d'une barre figée.
- **L'auteur n'utilise que la filière Sons TikTok (30 octobre 2026)** : priorité à cette partie. Réglages → « 🗂️ Onglets affichés »
  (Accueil, Vidéos, Stats masquables ; TikTok et Réglages toujours là ; variable ONGLETS_MASQUES, copie sur l'appareil ; onglet caché
  → TikTok). **Publication automatique** (onglet TikTok, `moteur/publication_auto.py` lancé par garde.yml) : case « À publier » sur
  chaque vidéo (variable PUBLI_FILE, ordre de coche), PUBLI_AUTO + PUBLI_HEURE (Paris) : une vidéo par jour, la plus ancienne cochée
  non publiée, envoyée à Buffer pour l'heure exacte (publier.yml auto=1, run « Publication automatique : … » = journée faite) ; une
  vidéo en échec est sautée. **Deux vidéos par jour** (demande de l'auteur, 1er novembre 2026) : case « Deux vidéos par jour »
  (PUBLI_DEUX) + 2e heure (PUBLI_HEURE2, 12:00 par défaut, au moins une heure d'écart) ; une vidéo par créneau
  (`publication_auto.creneaux`, chaque publication automatique du jour compte pour un créneau) ; calendrier du site sur les deux heures. **Réparé le 6 novembre** : aucune publication automatique n'était jamais partie (`gh api` refusait
  l'option « -R » ajoutée par `publication_auto._gh` : erreur avalée, journal « unknown shorthand flag »).
- **Métiers (30 octobre 2026, planches de référence de l'auteur)** : `moteur/metiers.py` : ~38 métiers et univers (pompier, policier,
  médecin, infirmier, chirurgien, dentiste, vétérinaire, prof, cuisinier, boulanger, serveur, ingénieur, ouvrier, électricien, plombier,
  mécanicien, agriculteur, jardinier, peintre, musicien, pilote, hôtesse, scientifique, informaticien, avocat, juge, astronaute,
  livreur, facteur, coiffeur, caissier, vigile, karatéka, sportif, cow-boy, sorcier, agent secret…) : costume complet (tenues toon
  `toon.metier_buste` : tablier, veste_chef, veste_pompier, salopette, kimono, combinaison, tunique_med, stéthoscope, nœud pap ;
  chapeaux `garde_robe.chapeau` : casque_pompier, casquette_officier, calot(_infirmier), charlotte, chapeau_paille,
  casque_astronaute, chapeau_cowboy, chapeau_sorcier, toque refaite) + outil en main (`metiers.outil`, tenu main gauche quand
  aucun autre objet). `qui_fait` : « je suis… » = celui qui parle ; « t'es… ? », « bonjour docteur », « monsieur l'agent » =
  l'autre ; un métier juste cité n'habille personne ; l'IA peut aussi choisir (studio → "metiers"). Les couleurs de la vidéo
  d'origine ne repeignent jamais un costume de métier.
- **Bonne voix sur le bon personnage (sons TikTok)** : `locuteurs.affiner` vérifie qui parle MOT PAR MOT (empreinte vocale ECAPA
  autour de chaque mot, comparée à chaque voix, fil le plus probable façon Viterbi, 2-3 tours ; une « voix » presque muette est
  rattachée à la plus proche) puis `caler_sur_phrases` met chaque changement de personne sur la fin de phrase la plus proche
  (3 mots au plus) ; chaque mot a sa certitude (`sure`) : l'IA qui ne lit que le texte ne peut plus déplacer une réplique « voix
  sûre » (`doublage.voix_sure`) ; deux voix ne jouent jamais le même personnage (`doublage.casting_unique`). Réglages `_P` trouvés
  sur un banc d'essai (dialogues montés avec nos voix, vérité connue : 84 % → 96 % de temps de parole bien attribué).
  **Voix trop proches** (même personne qui fait les deux voix, ressemblance ECAPA > 0,7 : `locuteurs.PROCHES`) : le son ne tranche
  plus, la vérification mot par mot est laissée de côté (aucune voix « sûre ») et le **contrôle questions-réponses** décide phrase
  par phrase (`locuteurs.fil_dialogue`) : logique du texte (`indices_dialogue` : après une question l'autre répond, « oui / bah /
  mais » = réponse, reprise des mots de l'autre, phrase coupée = la suite) + relecture du dialogue par l'IA, Gemini d'abord
  (`doublage.relire_dialogue`, `reseau.claude(raisonner=True)`, RELIRE_DIALOGUE=0 pour couper). « Battle d'aura » : 68 % → 97 %.
  **Corrections du 31 octobre 2026 (remarques de l'auteur)** : points oubliés par la transcription gratuite remis
  (`locuteurs.fins_de_phrase` : « …rouge Mais pourquoi… » -> nouvelle phrase ; jamais sur un nom propre) ; une phrase qui repart en
  minuscule reste à la même personne (`caler_sur_phrases`, `indices_dialogue`) ; contrôle questions-réponses aussi quand les voix se
  ressemblent « un peu » (ressemblance > 0,55 : `locuteurs.DOUTE`, le son garde du poids) et quand une seule voix est trouvée (l'IA dit
  si c'est un vrai monologue : jamais de personne inventée). **Un seul décor par son TikTok** (`studio.une_scene`, UNE_SCENE=0 pour
  couper ; appels et visios gardent un décor chacun) et personne n'entre en marchant (plus de bruits de pas « toc toc toc »).
  **Analyse des vidéos du 31 octobre (2e passe)** : l'IA gratuite ne peut plus inventer un appel (`separer_lieux` : lieux séparés
  refusés si rien dans le son ne parle d'appel ; téléphone en main retiré) ; proches présentés ou montrés (« je te présente mon
  père », « mon arrière-grand-père qui est là-bas ») dessinés à côté (`studio.famille_presentee`) ; Whisper qui tourne en boucle
  (« Oh mais non je suis sale » ×3 en 1 s) nettoyé (`locuteurs.sans_boucles`) ; une voix qui dit plus de 70 % du texte = souvent deux
  personnes à la même voix : l'IA la partage, l'autre voix devient une 3e personne (`doublage.scinder_voix_dominante`) ; réponses de
  l'IA gratuite remises en forme (indications de jeu en liste, personnages sans rôle) ; Groq réparé (refusé sans nom de robot,
  réponse mal lue) ; ressemblance des voix toujours notée dans le journal.
  **Équipe de fabrication contrôlée poste par poste (demande de l'auteur, 31 octobre 2026, `moteur/equipe.py`)** : chaque poste a
  son contrôleur qui vérifie, corrige ce qu'il peut et note le reste dans le bulletin (sk["equipe"] + journal « [équipe · …] ») :
  ingé son (boucles de Whisper, ponctuation isolée, mots impossibles, longs blancs) ; casting voix : TROIS témoins votent, le son
  (empreinte), le texte (questions / réponses relues par l'IA) et l'IMAGE de l'original (`moteur/regard.py` : qui bouge, gauche ou
  droite, quand la phrase est dite, images sans coupure seulement ; REGARD=0) ; si l'image contredit le son sur plus de 30 % des
  phrases, le fil du dialogue est repris avec les trois (`locuteurs.fil_dialogue(vue=…)`) ; une seule voix + deux personnes qui
  bougent à tour de rôle = deux personnages même sans IA ; une nouvelle réplique après chaque question ; scripte (une réplique = une
  personne, appel seulement si le son en parle, téléphone seulement s'il en est question, autant de personnages que de voix) ;
  monteur (ordre, durées, chevauchements, mots dans leur réplique, rien après la fin du son). Puis pré-jury, contrôle image et jury.
  Essai « Fierté familiale » (même voix pour les deux copains) : la parole passe de 85 % / 15 % à un vrai dialogue 57 % / 43 %.
  **Contrôles renforcés (choix de l'auteur 1, 2, 3, 4, 6, 7, 8, 9)** : deux transcriptions comparées (Groq + Whisper de la machine,
  `equipe.deux_transcriptions` : l'IA tranche les mots en désaccord, instants inchangés) ; deux IA relisent le dialogue chacune de
  leur côté (`relire_dialogue` : 2e avis par `reseau.claude(exclure=…)`, désaccord = la phrase est laissée au son et à l'image ;
  DEUX_AVIS=0) ; témoin image : plans larges = gauche / droite, gros plans = COULEURS de ce qui bouge (`regard.signature`, k-moyennes) ;
  **vidéo finie contrôlée** (`moteur/verif_finale.py`, VERIF_FINALE=0) : synchro des bouches (pendant chaque réplique c'est le bon
  personnage qui bouge ; positions `cartoon.RENDU["xs"]`) et décalage son / image mesuré puis corrigé au-delà de 0,12 s (son recalé,
  `recaler`) ; sous-titres vérifiés à l'oreille (son de la vidéo finie retranscrit, comparé réplique par réplique, voix sans
  sous-titre) ; technique (sauts d'image hors coupes prévues, clignotements, contrôle image du dessin) ; liste de contrôle par l'IA
  (une image toutes les 2 s, 6 questions fixes) ; **feu rouge** : points non corrigés -> historique "a_verifier" -> badge
  « ⚠️ À vérifier (n) » + moments sur l'onglet TikTok, et cocher « À publier » demande confirmation.
  **Leçons de la chaîne du 31 octobre** : le décalage son / image est seulement MESURÉ (jamais corrigé : le son et l'image sortent du même
  calcul, un « recalage » de +0,28 s avait décalé une vidéo juste ; `moteur/reparer.py` + workflow reparer.yml remettent le son d'une
  vidéo archivée à 0) ; l'IA de contrôle ne juge plus les sous-titres (vérifiés à l'oreille) ; fin d'une réplique = fin de son mot le
  plus tardif (`doublage.segments`). Mise en scène par l'IA gratuite : JSON lu aussi dans le texte (`ecrire._appel`), 2e essai sans les images
  (`doublage`) avant de retomber sur « une seule scène, casting par la hauteur des voix ».
  **Liste du 31 octobre au soir (choix de l'auteur 1, 3, 4, 5, 6, 7, 9, 11, 12, 16)** : jury jamais contre le montage « plan large »
  (`qualite.HORS_LARGE`, `sans_reproches_large` : remarques sur plans / zooms / caméra retirées, +0,8 point chacune ; consigne à l'IA) ;
  titre jamais coupé au milieu (`ecrire.titre_net`) ; lieu quand l'IA n'a pas fait la mise en scène : regardé sur 2 images de l'original
  par l'IA, sinon d'après les mots (2 indices au moins : `doublage.lieu_vu`, `decor_dessin.scores_lieux` ; animal de compagnie = salon ;
  LIEU_VU=0) ; le monteur CORRIGE (réplique élargie autour de ses mots, ordre du son avec découpage renuméroté, fin du son, un
  personnage qui se chevauche : `equipe.monteur(sk, duree, B, segs)`, avant le calcul des voix) ; 3e écoute (Whisper large-v3 de Groq)
  qui départage les deux transcriptions à la majorité, l'IA seulement pour le reste ; silence du début retiré (`doublage.debut_parole`
  sur la voix isolée, > 0,8 s : son, voix et vidéo d'origine coupés au même instant, `couper_debut`, sk["doublage"]["debut"] repris par
  « Corriger qui parle » ; DEBUT_COURT=0) ; IA gratuites : Groq = 3e IA (llama-3.3-70b…, vision llama-4), ordre texte Mistral → Groq →
  Gemini (quota de Gemini gardé pour les images), logique d'un dialogue Groq → Gemini → Mistral, quotas du jour lus dans les en-têtes
  (`reseau.QUOTA`, historique outils "appels" / "epuisees" / "quota") ; **voyant « 🤖 IA gratuites aujourd'hui »** sous le bouton de la
  chaîne (onglet TikTok, `rendreQuotaIA`) ; bouches corrigées : réplique où un autre bouge plus que celui qui parle (`verif_finale.synchro`
  → "i") redessinée avec celui qui écoute calme (`_calme` → ph "calme" dans `cartoon.pose`, redessin partiel, gardée seulement si
  mieux ; BOUCHES_CORRIGEES=0) ; **animaux et objets qui parlent** (`moteur/animaux.py`, style croquis : chat, chien, steak, pizza, œuf,
  banane, objet quelconque ; même visage et bouche que nos personnages ; fiche "espece" de l'IA ou `animaux.qui_est` d'après le dialogue :
  « je suis un chat » = lui, « mon chat, t'es… », « sale chien » = l'autre ; plus petits ; ESPECES=0).
  **Liste du 1er novembre (choix 4, 5, 6, 11)** : animaux et objets en plus (lapin, souris, oiseau, poisson qui flotte, voiture sur ses
  roues, frigo, téléphone, verre d'eau, croissant ; « je suis au téléphone » ne compte jamais ; un mot doux ou une insulte seuls
  (« mon lapin », « sale chien ») ne suffisent plus : il faut « je suis un… », un 2e indice ou l'IA) ; accessoires des animaux et objets
  (chapeau du costume ou du métier, lunettes, collier à médaille pour chat et chien, petit nœud pour une voix de femme) ; **deuxième
  chance** (`moteur/deuxieme_chance.py`) : vidéo TikTok à confiance < CONFIANCE_MIN (40) refaite une fois sur le même son (emission.yml
  theme « TIKTOK::lien##2e:fichier »), la moins sûre des deux supprimée (jamais une vidéo publiée ou cochée « À publier » : alors les
  deux restent ; DEUXIEME_CHANCE=0) ; **jamais deux sons du même profil d'affilée** à la publication (`publication_auto.alterner`,
  même ordre dans le calendrier du site : `alternerPubli`).
  **Liste du 1er novembre (choix 1, 2, 3, 8, 11, 12, 14, 15)** : **Gemini regarde la vidéo d'origine EN ENTIER**, image + son
  (`moteur/video_ia.py`, API native, vidéo réduite 360p ; personnages, lieu, résumé, qui dit chaque phrase ; consigne : une MÊME
  personne peut jouer 2-3 personnages -> on compte les personnages ; VIDEO_IA=0) ; **témoin visages** (`moteur/visages.py`, MediaPipe
  Face Landmarker : bouches qui bougent, pistes suivies dans chaque plan, personnages regroupés par apparence (haut, cheveux /
  perruque) ET regard gauche / droite -> la même personne qui se tourne ou change de tenue = deux personnages ; jamais deux visages
  vus ensemble dans le même personnage ; dessins animés : il se tait ; VISAGES=0) ; les trois témoins de l'image (Gemini 1, visages
  0,9, mouvements 0,6) votent (`equipe.combiner`, numéros alignés) ; 3 personnages vus ou plus = chaque phrase au personnage vu
  (`equipe.trois_personnages`) ; ce que Gemini a vu passe dans la mise en scène (lieu, espèce d'un animal / objet) ;
  **décors de saison** (`moteur/saisons.py` : Noël, Halloween, Saint-Valentin, été, posés sur les bords ; SAISON=0 / noel…) ;
  **sons du calendrier** (`saisons.mots_du_moment` : +30 au potentiel d'un son dont le titre parle de l'événement proche ;
  SONS_CALENDRIER=0) ; **« Dis ce qui ne va pas, le robot corrige »** (fiche d'une vidéo TikTok : remarque écrite ou dictée 🎤 ->
  refaire « fichier|remarque|texte » -> `moteur/remarque.py` : l'IA traduit en « qui dit quoi » + corrections du jury, règles simples
  sans IA ; même son, mêmes répliques ; remarque gardée pour le jury) ; (leçon du 1er novembre) « Maurice est censé être un chat » = le personnage qu'on APPELLE Maurice devient un chat (`remarque.role_nomme`), l'IA ne peut plus changer qui dit les répliques si la remarque n'en parle pas (`parle_de_qui_parle`), et jamais de deuxième chance sur une vidéo refaite à la main ; **OpenRouter** = 4e IA gratuite (secret OPENROUTER_API_KEY,
  modèles « :free » lus en direct sur openrouter.ai/api/v1/models par `reseau._openrouter_libres` : ils changent souvent) ;
  **notre IA de secours sur Modal** (`moteur/ia_modal.py`, Qwen2.5-VL 7B Apache 2.0 sous vLLM, GPU L4, arrêt
  2 min après ; app jt-ia, workflow « IA de secours sur Modal » ; utilisée en tout dernier recours si elle est déployée :
  IA_MODAL_PRETE ; IA_MODAL=0).
  **Tirage au hasard des sons TikTok** : le robot préfère les vidéos aux voix bien différentes (ressemblance ≤ 0,6, réglage
  VOIX_DIFFERENTES ; 1 = sans tri) : jusqu'à 6 vidéos écoutées (25 min au plus), sinon celle aux voix les plus nettes. Un lien collé
  à la main n'est jamais refusé (le contrôle questions-réponses s'en charge).
- **Idées choisies par l'auteur (30 octobre 2026, 1re partie)** : plus de figurants inutiles en arrière-plan (FIGURANTS=1 pour les
  remettre ; les compagnons dont on parle restent), plus de voiture qui passe au hasard (VOITURE_PASSE=1), plus de chute en arrière
  à la fin (CHUTE_KO=1) ; **fin en boucle** (`moteur/boucle.py` : la dernière image glisse vers la première, BOUCLE=0 pour couper) ;
  **note de potentiel** des sons avant fabrication + **sons qui montent** (`profils_tiktok.potentiel` / `vitesse` : vues par jour,
  durée 20-70 s) ; **profils pondérés par nos vues** (`profils_tiktok.poids_profils`) ; **heure de publication par les stats**
  (case « Heure choisie par les statistiques », PUBLI_HEURE_AUTO, `stats.meilleure_heure_publication` ; l'heure fixe reste au
  choix) ; **partage direct depuis l'appli TikTok** (site installé = cible de partage : `?partage=1` remplit le lien de l'onglet TikTok).
- **Idées choisies par l'auteur (30 octobre 2026, 2e partie)** : **écoute gratuite** (`moteur/ecoute.py`) : Demucs (voix sans la
  musique quand l'isolation ElevenLabs manque, DEMUCS=0), Groq (Whisper en quelques secondes, secret GROQ_API_KEY gratuit, avant le
  Whisper de Modal et de la machine), calage de chaque mot sur la voix façon WhisperX (wav2vec2 français Apache 2.0 + alignement forcé
  torchaudio, ALIGNEMENT=0), émotion de la voix (SpeechBrain, EMOTION_VOIX=0) et rires / cris / bruits de l'original (CLAP, seuils
  réglés sur ESC-50, CLAP=0) -> indications de jeu sur les répliques sans indication de l'IA (`ecoute.jeu_entendu`, jamais le texte) ;
  **Modal** (`moteur/ecoute_modal.py`, app jt-ecoute) : NeMo (qui parle quand, avant pyannote, quand une seule voix est trouvée) et
  Florence-2 (décrit les images clés quand ni Claude ni Gemini ne peuvent les regarder ; ECOUTE_MODAL=0) ; **postures** de l'original
  par MediaPipe (`moteur/postures.py` : bras croisés, mains sur les hanches, menton, téléphone, main sur la bouche, bras levés / ouverts,
  doigt pointé -> geste de la réplique, POSTURES=0) ; **décors des métiers** (`moteur/decor_metiers.py` : caserne, garage, boulangerie,
  ferme, tribunal, labo, cockpit, espace, coiffeur ; choisis par les mots ou par le métier reconnu quand rien d'autre ne dit le lieu,
  LIEU_METIER=0) ; **véhicules des métiers** (`vehicules.py` : police, ambulance, camion de pompiers, tracteur, fusée ; dehors
  seulement, quand on en parle ou que le métier est là, VEHICULES_METIERS=0) ; fiche d'une vidéo TikTok : **📺 Comparer avec
  l'original** (lecteur TikTok à côté de la nôtre) et **🗣️ Corriger qui parle** (personnage de chaque réplique -> Refaire
  « fichier|qui|0=invite;3=presentateur » : même son d'origine re-téléchargé, mêmes instants : `doublage.depuis_sketch`, mots gardés
  dans le sketch « _mots ») ; le bouton Refaire retrouve enfin le sketch gardé (nom sans « .mp4 »).
- **Description TikTok** (`moteur/legende.py`, demande de l'auteur) : description de la vidéo + question + « 🎧 Son original :
  @compte » **sans aucun lien**, puis ~15 hashtags liés à la vidéo (ceux de l'IA, sujet : famille / école / couple / travail…,
  métiers, émotions, puis #petitsdramas et la niche ; NB_HASHTAGS) ; `publier.py` nettoie aussi les anciennes légendes à l'envoi. **Phrase d'abonnement** (choix de l'auteur du 6 novembre, peu
  d'abonnés malgré les vues) : « 🔔 Abonne-toi : une nouvelle histoire chaque jour ! » avant la source du son (`legende.phrase_abonne`,
  réglage PHRASE_ABONNE = autre texte ou « 0 » ; ajoutée à l'envoi aux vidéos plus anciennes, jamais deux fois).
- **Style « croquis » = STYLE PAR DÉFAUT (validé par l'auteur le 30 octobre 2026)** : `moteur/croquis.py` (dessin) +
  `moteur/perso_croquis.py` (traduit la pose du moteur : bras en angles -> coude et main, émotion -> expression, bouche ouverte selon la
  voix en gardant l'expression, forme des lèvres par son, regard, larmes / sueur / rougeur, costume, métier, chapeau, lunettes, barbe
  mal rasée) ; STYLE_PERSO=croquis (défaut ; « toon » et « ancien » restent au choix) ; silhouette tirée par personnage, le PETIT ou
  le GRAND pour tous les âges (SILHOUETTE = petit / grand / les_deux) ; tête et pieds aux mêmes places que l'ancien style (cadrages,
  objets tenus, contrôle image inchangés) ; toujours debout (assis = jambes à travers les meubles) ; décors dessinés ou IA passés à
  l'encre + aquarelle sur papier (`croquis.croquifier`, DECOR_CROQUIS=0 pour couper). Vitesse : chaque personnage dessiné dans un petit
  cadre, aquarelle / hachures / flous calculés seulement dans la zone peinte (sinon 10 fois plus lent) ; une ombre ne déborde jamais
  d'une forme (sur la toile « vide » du super-échantillonnage, un débord devient une tache noire). Maquettes et références :
  `maquettes/croquis/` (images de l'auteur, faites par lui avec une IA ; rangées depuis le 17 novembre dans la release « archives-fichiers », maquettes.zip). Choix déjà faits : les DEUX silhouettes (le petit à grosse tête et le grand stickman), pour enfants, ados,
  adultes et seniors ; visuels 1-5 validés « pour le moment » ; animation BEAUCOUP plus fluide (poses fondues et adoucies, bouche
  qui s'ouvre selon la voix en gardant l'expression, expressions en fondu, clignements doux, 30 i/s ou plus, jamais saccadé).
  **Créé le 30 octobre 2026 (feu vert de l'auteur)** : mouvements dans le robot (micro-expressions quand il se tait : lèvre mordue si gêne,
  joues gonflées si soupir, rictus si sceptique ; rire qui secoue le corps + larmes de rire ; sursaut étiré / écrasé quand l'autre crie ;
  gestes avec élan et léger dépassement `_ressort`) ; position assise vue de face sur une chaise croquis (`croquis.chaise_face`,
  jambes « assis_face ») ; 39 lieux (`moteur/decor_lieux.py`, mots dans `REGLES`, ajoutés en dernier dans `lieu_de` : à égalité les
  anciens lieux gagnent) ; 45 métiers (`metiers.CATALOGUE`, 82 en tout ; mots retirés des anciens métiers quand un nouveau les prend :
  DJ, chanteur, maçon, footballeur, magicien, vendeur, gendarme, pâtissier, garde du corps) avec lieu (`decor_metiers.METIER_LIEU`) et
  véhicule ; tenues du contexte (`studio.habiller_contexte` : pyjama, peignoir, maillot de bain, doudoune + écharpe + gants, imperméable,
  survêtement, gilet jaune, uniforme, robe de mariée / de soirée, costume-cravate, déguisements d'Halloween ; clé costume « tenue »,
  jamais sur un costume imposé ou de métier, jamais repeinte par les couleurs de l'original) ; accessoires (montre, lunettes de ski,
  écharpe, gants) ; objets tenus d'après les mots (`studio.OBJETS_MOTS` : valise, parapluie, sac à main, casque de moto…). Croquis :
  chapeaux tricorne, bob, bandana, couronne, bonnet de père Noël, casque de chevalier, oreilles de lapin ; détails cravate, cape, logo,
  bandelettes, antennes, crocs, nez rouge, cache-œil, sifflet, boutons dorés, ceinture, barbe blanche (déguisement) ; teint du
  costume (zombie, extraterrestre, vampire) ; robe / jupe. Vitesse : flous sur entiers, grand flou de l'ombre de la tête calculé
  réduit (sinon 2 fois plus lent). **Liste d'origine (pour mémoire)** :
  lieux : salle de bain, jardin, balcon, garage de maison, grenier, salle à manger, cour de récré, cantine, bureau du proviseur,
  bibliothèque, amphi, arrêt de bus, métro, gare, aéroport, parking de supermarché, fast-food, kebab, cinéma, plage, piscine, parc,
  camping, montagne / ski, stade de foot, salle de concert, boîte de nuit, hôpital (chambre, urgences), pharmacie, commissariat,
  prison, banque, poste, mariage, église, plateau télé, studio radio, salle de jeux vidéo ; métiers : ambulancier, sage-femme, kiné,
  opticien, pharmacien, psychologue, vendeur, fleuriste, boucher, poissonnier, pâtissier, barista, livreur de pizza, chauffeur de
  bus, chauffeur VTC / taxi, conducteur de train, capitaine de bateau, contrôleur, militaire, gendarme, douanier, garde du corps,
  maître-nageur, journaliste, présentateur télé, youtubeur / streamer, chanteur, DJ, magicien, clown, footballeur, maçon, menuisier,
  peintre en bâtiment, agent d'entretien, baby-sitter, déménageur, pirate, chevalier, super-héros, père Noël, vampire, zombie, momie,
  extraterrestre ; tenues : pyjama, peignoir, maillot de bain, tenue de sport, survêtement, costume-cravate, robe de soirée, robe de
  mariée, doudoune, imperméable, déguisements (Halloween, fêtes : sorcière, citrouille, lapin), uniforme scolaire, gilet jaune ;
  accessoires : sac à main, valise, parapluie, écharpe, gants, lunettes de ski, montre, casque de moto. Et tout l'existant
  (25 lieux, 37 métiers, 20 outils, 28 hauts, 21 coiffures, 21 chapeaux, 44 objets, véhicules) redessiné en croquis.
- **Décors « Semi-réaliste » = STYLE PAR DÉFAUT (choix de l'auteur, 1er novembre 2026, après essais vidéo)** : réglage « Style des
  décors » (variable STYLE_DECOR : `semi_realiste` par défaut, `croquis` = décor dessiné à l'encre et à l'aquarelle) ; le décor est
  une PEINTURE semi-réaliste façon fond de film d'animation (même IA : SDXL sur Modal, `decor_modal.generer_semi`, 2 tirages par lieu,
  sans aplats ni aquarelle, rien de dessiné par-dessus : ni saison, ni premier plan, ni détails animés ; `cartoon` → `SEMI_`,
  sk["_decors_semi"]) ; personnages toujours en croquis ; **pieds VRAIMENT posés au sol** (`moteur/semi_realiste.py`) : grand sol
  libre demandé à l'IA, sol trouvé par la carte de profondeur (le sol = un plan mesuré en bas de l'image ; chaise, table, lit, mur
  = obstacles), cadrage 9:16 au zoom le plus faible qui met les pieds de chacun (places fixes du moteur, ligne 1500) sur le sol
  sans obstacle autour ; aucun cadrage possible / budget atteint / Modal absent -> décor dessiné en croquis (jamais de pieds qui
  flottent). Banque à part (descriptions « [semi] … », déjà cadrées, jamais mélangées aux décors croquis). Coût : ~3-10 centimes
  par lieu neuf, 60 lieux neufs par mois au plus (DECORS_MOIS). **Compteur du budget réparé** (`decors/compteur.json` : la date
  des fichiers ne veut rien dire sur GitHub, le budget paraissait toujours atteint). Essais visuels : `maquettes/photo/` (release « archives-fichiers », maquettes.zip). Leçons des 2 premières vidéos : description du lieu toujours en anglais
  (`studio.DECOR_EN` quand la mise en scène l'écrit en français : l'IA comprenait mal), lumière du moment ajoutée, 3 tirages, pas
  d'agrandisseur « anime » (il donnait un style BD : simple agrandissement doux). Soir du 1er novembre : lieux sans description
  anglaise complétés (`semi_realiste.LIEUX_EN` : cuisine, cabinet médical, salle de sport, classe…) ; deux fabrications qui finissent
  en même temps ne s'écrasent plus la banque des décors (`fusion.FUSIONNES` : index.tsv = lignes ajoutées, compteur.json = somme) ;
  « Dis ce qui ne va pas » et « Corriger qui parle » aussi sur les vidéos plus récentes que le site (`chargerRepliques` : répliques
  lues en direct dans le sketch gardé).
- **Analyse des 10 vidéos du 1er novembre (demande de l'auteur du 6 novembre : la vidéo doit sortir propre, sans points à vérifier
  inutiles)** : remarque « un seul personnage » = toutes les répliques (même les bruits du narrateur) au même personnage
  (`remarque` type "un_seul", champ IA `un_seul_personnage`) ; personnage DANS un objet (`animaux.CONTENANTS` : micro-ondes avec
  vitre, plateau et minuteur, four, frigo, poêle qui fume, bocal, carton, cage ; `contenant_de`, fiche "dans", dessiné en deux fois :
  fond avant le personnage, façade après) ; « il s'appelle comment » n'est plus un appel et un résumé « après une conversation
  téléphonique » non plus quand deux personnes sont à l'image ensemble (`studio.appel_devine` : nb_personnes ≥ 2 ou Gemini qui voit
  ≥ 2 personnages ensemble) ; phrases inventées par Whisper sur un silence (« Sous-titrage Société Radio-Canada », « Merci d'avoir
  regardé »…) retirées (`locuteurs.sans_hallucinations`, ingé son + contrôle final) ; le carton de fin « Abonne-toi » n'est plus un
  « saut d'image » (`RENDU["fin_carte"]`, 3,6 dernières s) ; l'IA de contrôle ne juge plus les textes affichés ni « personne ne parle » ;
  sous-titre « entendu autrement » grave seulement si presque rien ne correspond ; **seuls les défauts graves restent « à vérifier »**
  (le reste au journal) ; jury IA : la réponse en texte d'une IA de relais est lue (`ecrire._appel`, 2 essais) au lieu de retomber sur
  la note gratuite 9,8 ; Groq : modèles du jour lus en direct (`reseau._groq_modeles`, les « vision » changent) et outil mal formé
  -> réponse JSON en texte.
- **Homme / femme d'après la voix (remarque de l'auteur du 6 novembre : voix de femme sur un physique d'homme et inversement)** :
  `studio.genre_voix` décide dans cet ordre : 1. le TIMBRE (`studio.espacement_formants` : espacement des formants par LPC, longueur
  du conduit vocal ; < 1060 Hz = homme, > 1100 Hz = femme, calculé par `cartoon` -> sk["_voix_timbre"], "_voix_timbre_genre") —
  il ne bouge pas quand un homme crie ou quand la voix d'un dessin animé est accélérée (la hauteur seule avait mis des corps de
  femme sur 3 voix d'homme aiguës les 2-3 novembre) ; 2. la hauteur nette (vote) si Gemini ne voit pas l'inverse ; 3. ce que Gemini
  a vu dans l'original (`video_ia.genres_par_voix` -> personnages "genre_vu") ; 4. l'IA de mise en scène (« homme » / « femme »
  compris) ; 5. la hauteur moyenne. Un personnage à voix d'homme n'est jamais en robe / jupe (sauf mariée), coiffures déjà gardées
  par `humain.POUR_H / POUR_F`.
  **Revu le 11 novembre (analyse des 11 vidéos du jour : 6 femmes dessinées en homme)** : le timbre seul se trompait sur les dessins
  animés (un seul doubleur pour toutes les voix : 997-1045 Hz pour tout le monde). `genre_voix` fait maintenant VOTER les témoins :
  Gemini (ce qu'il a vu) 2, timbre 1,5 s'il est net (< 980 / > 1110 Hz) sinon 0,5, hauteur nette 1, IA de mise en scène 1, accords
  du texte (« je suis choquée » / « je suis content » : `ACCORD_F` / `ACCORD_H`) 1 ; à égalité Gemini, puis timbre, hauteur nette, IA.
  Le jury (`qualite`, « voix de femme mais dessiné en homme ») utilise le même vote (net seulement), plus la hauteur seule.
- **Liste du 6 novembre 2026 (choix de l'auteur 1, 2, 3, 4, 5, 7, 11, 18, 21, 23, 26, 27, 37, 40, 41, 45, 46, 48, 50)** :
  **machine toute prête** (1 + 2) : bibliothèques installées par `uv` (pip en repli) dans ~/venv, gardé en cache GitHub (clé = version
  de Python + requirements.txt + contraintes.txt ; yt-dlp toujours mis à jour) ; gain mesuré modeste (~1 à 2 min, l'installation prenait
  ~3 min sur 25) ; **pré-écoute la nuit** (3, option « 🌙 Pré-écoute la nuit » de l'onglet TikTok, PRE_ECOUTE=0 pour couper) :
  vers 2 h (garde.yml → pre_ecoute.yml, seulement si les vidéos TikTok automatiques sont activées) le robot écoute à l'avance un son par
  heure de HEURE_TIKTOK (STOCK_SONS, 1 à 4) et les range dans la release « sons-prets » (3 jours) ; la fabrication prend le plus ancien
  son prêt (`pre_ecoute.prendre`, états de l'écoute remis : événements, analyse Gemini, ressemblance des voix) et passe au dessin ;
  **dessin compilé** (4, `moteur/rapide.py`, Numba) : aquarelle, hachures, collage des personnages et ombre portée en une passe
  compilée, EXACTEMENT les mêmes pixels (vérifié image par image : 111 s → 74 s sur la vidéo d'essai, −33 %) ; NUMBA=0 = NumPy ;
  (5, personnage immobile gardé en mémoire : mesuré, rien à gagner, les personnages respirent et clignent à chaque image) ;
  **⏱️ temps par étape** (7, `progression.chrono` → historique "temps", "temps_lents" si 2 fois plus lent que la médiane des 20
  dernières ; carte « ⏱️ Temps de fabrication » des Réglages) ; **🎭 Changer les personnages** (11, fiche d'une vidéo TikTok : homme /
  femme, âge, silhouette, animal ou objet, coiffure, haut, couleur, chapeau, lunettes → refaire « fichier|casting|{json} » →
  sk["_casting_auteur"] → `studio.casting_auteur`, passe avant tout, sans IA) ; **raccourcis de l'icône** (18, manifeste « shortcuts » :
  son au hasard, 3 vidéos, mes vidéos ; confirmation avant de lancer) ; **sous-titres de l'original** (21, `moteur/ocr.py`, RapidOCR,
  une image / 0,6 s, OCR=0) : comparés LETTRE par LETTRE (la lecture colle les mots et perd les accents) ; si ≥ 60 % des lettres
  entendues sont écrites : les mots différents passent à l'arbitrage de l'IA (`equipe._arbitrer`), et une couleur de sous-titre par
  voix (≥ 75 %) remet les phrases mal rangées sur leur voix (jamais une voix sûre) ; **tendances** (23 ; le Creative Center de TikTok
  refuse les robots) : hashtag récent chez 2 de nos créateurs au moins (+20) ou recherche qui monte en France (Google Trends, +15),
  SONS_TENDANCE=0 ; **parties** (26 + 37, `moteur/suites.py`, SUITES=0) : « partie 2 / pt2 / épisode 3 / 2/3 » lu dans le titre de
  l'original (sk["doublage"]["titre"] → historique "titre_source") ; la suite d'une vidéo déjà faite passe devant au tirage (+60) et
  reprend les mêmes personnages (sk["_casting_final"] gardé dans chaque sketch, homme avec homme, femme avec femme) ; carte de fin
  « Partie N+1 bientôt ! Abonne-toi » et ligne « ➡️ Partie N+1 bientôt sur la chaîne ! » dans la description ; **liste noire** (27,
  PROFILS_INTERDITS + bio qui interdit la reprise lue par tikwm) ; **♻️ rediffusion** (40, REDIFFUSION, activée) : quand aucune vidéo
  cochée n'attend, la vidéo publiée il y a plus de 3 mois qui a fait le plus de vues repart (publier.yml forcer + rediffusion=1,
  « ♻️ On la remet pour ceux qui l'ont ratée 😂 », historique "rediffusee", jamais deux fois en 3 mois) ; **📈 recette du succès** (41,
  `moteur/recette.py` après stats.py → episodes/recette.json, bloc « 📈 Ce qui marche » de l'onglet TikTok ; historique "recette" :
  lieu, animal, personnages, partie ; la durée qui marche donne ±10 au potentiel d'un son, RECETTE=0) ; **couverture par les stats**
  (45, `moteur/couverture.py` : chute, réaction ou début, alternées puis la meilleure à 70 % ; historique "type_couverture",
  COUVERTURE_AUTO=0) ; **images de référence** (46, `moteur/references.py`, tests/references/*.png, TestImagesDeReference ; changement
  VOULU du dessin : `python moteur/references.py --refaire` puis regarder les images) ; **vrai compteur Modal** (48,
  `moteur/budget_modal.py` : `modal billing summary --json` au départ de chaque fabrication et dans credits.yml ; au-delà de
  BUDGET_MODAL − 2 $ (30 $ par défaut) Modal est coupé pour la fabrication (replis gratuits), alerte une fois par jour, voyant orange
  et montant sur le site) ; **mode panne** (50 : githubstatus.com lu toutes les 10 min, bandeau « 🛠️ Panne chez GitHub » si Actions,
  API ou Pages ne marchent pas).
- **Notes des vidéos TikTok au plus haut (demande de l'auteur du 7 novembre)** : deux notes : la **note de confiance** (/100,
  `verif_finale.confiance` : points graves non corrigés et contrôles d'équipe ratés) et la **note du jury** (/10, `qualite.evaluer`).
  Analyse des 40 dernières vidéos TikTok puis corrections : sous-titres lisibles même quand on parle vite (`jt.lisibles` : un groupe
  affiché moins de 0,45 s est fusionné avec son voisin s'il tient sur une ligne, chaque groupe reste jusqu'au suivant ; règle du jury
  par groupe affiché) ; début coupé au PREMIER MOT transcrit (`doublage.attente_premier_mot` : un bruit pris pour de la voix laissait
  la 1re parole à 5 s) ; durée jamais reprochée sur un son imposé ; jury IA : `CONSIGNE_SON_IMPOSE` + `sans_reproches_son_impose`
  (vannes, chute, rythme, voix, silences, volume = l'original : jamais reprochés, sauf correction « jeu » / « bruitage » possible ;
  +0,8 par remarque retirée), style croquis et animaux / objets qui parlent annoncés comme voulus ; contrôle IA final : plus de prénoms
  internes (« Kévin » faisait croire à un homme), « le personnage 1… » + espèce voulue, remarques « chat au lieu d'un humain » /
  « même apparence » écartées ; équipe : un défaut CORRIGÉ par son contrôleur compte comme bon (boucles de Whisper, téléphone retiré,
  appel refusé, désaccord son / image repris par le fil du dialogue, deux transcriptions dont chaque désaccord est tranché).
  **Compte rendu corrigé tout de suite** (précision de l'auteur, 7 novembre : les problèmes signalés dans le compte rendu de chaque
  vidéo doivent être réglés, pas seulement affichés ; `moteur/compte_rendu.py`) : pendant la fabrication d'un son TikTok, après le
  contrôle de la vidéo finie, les points à vérifier + remarques du jury + contrôles « à revoir » sont écrits comme une remarque d'auteur
  (`compte_rendu.texte`, sans les avis de goût ni les défauts techniques) et passent au correcteur de « Dis ce qui ne va pas »
  (`remarque.appliquer(…, memoriser=False)`) ; seuls les passages touchés sont redessinés (depuis la copie « _avant_boucle »), la vidéo
  est recontrôlée (verif_finale + jury) et gardée seulement si la confiance monte (à égalité : la note du jury) ; 2 tours au plus
  (COMPTE_RENDU_TOURS), jamais au-delà de la limite de temps, COMPTE_RENDU=0 pour couper. Vidéos déjà faites : fiche d'une vidéo TikTok
  « 🛠️ Corriger les n problèmes signalés » et onglet TikTok « 🛠️ Corriger les vidéos signalées » (non publiées, avec points à vérifier
  ou confiance < 70, 10 au plus) -> refaire « fichier|compte_rendu » ; la moins sûre des deux versions est retirée (sortie/.perdante),
  jamais une vidéo publiée ou cochée « À publier ».
- **Liste du 11 novembre 2026 (choix de l'auteur 1, 3, 4, 9)** : **jeu copié sur l'original** (1 + 3, `moteur/jeu_original.py`,
  JEU_ORIGINAL=0) : `visages.lire` (MediaPipe, 8 images/s, lecture gardée en mémoire pour le témoin et le jeu) note pour chaque visage
  ses expressions (sourire, sourcils levés / froncés, yeux plissés / écarquillés, bouche bée, moue), l'inclinaison et les mouvements
  de la tête, et le geste de la main la plus proche (Gesture Recognizer : index, pouce levé / baissé, V, main ouverte, poing ; MAINS=0) ;
  chaque visage suivi est rendu au rôle qui dit ses répliques (bouche qui bouge ; piste muette vue en même temps = l'autre rôle) ;
  sk["_jeu_original"] (4 valeurs / s) -> `cartoon.pose` -> `jeu_original.appliquer` : émotion lue seulement si rien de fort n'est déjà
  joué, sourcils et yeux d'après l'ÉCART au visage habituel de la personne, tête penchée / tournée / baissée d'après ses MOUVEMENTS,
  geste des doigts sur la main droite libre, bras tendu sur le côté à hauteur de poitrine (`BRAS_DOIGTS` : une main levée passait
  devant la grosse tête), doigts dessinés par `croquis.main` (formes index, deux, pouce, pouce_bas, poing ; p["doigts_d"]).
  **Dessins animés ignorés** : visage peint en aplat (`visages._plat` : dessin 0,84-0,92, vraie peau 0,58-0,74 ; PLAT_MAX 0,78) ou
  visages vus moins d'un quart du temps de parole -> rien de recopié. NB : la plupart des sons repris viennent de chaînes de dessins
  animés (vignianimation, yan_animation0, kodanimation…) : le jeu copié ne sert que pour les vidéos avec de vraies personnes.
  **Objets vus dans l'original** (4, `moteur/objets_vus.py`, OWL-ViT de Google, Apache 2.0, une image / 1,5 s, ~30 s par vidéo,
  OBJETS_VUS=0) : objets tenus seulement (téléphone, verre, tasse, livre, sac, parapluie, fleurs, cadeau, pizza, micro…, jamais
  l'ordinateur de bureau), vus sur 2 images au moins, donnés au personnage qui parle à ce moment si sa réplique n'a pas d'objet ;
  marche aussi sur les dessins animés ; le téléphone caché par la main à l'oreille n'est pas vu. Cache des modèles : hf-ecoute-v3.
  **Nom du compte** (9) : le petit logo existait mais il était caché par la barre du haut de l'appli TikTok (y = 118) et disait
  « Petits.Dramas » : il affiche maintenant le compte (`marque.compte`, TIKTOK_COMPTE, sinon @petitsdramas), à y = 215 (FIL_Y), et
  n'apparaît qu'après le titre (jamais par-dessus).
- **Liste du 11 novembre 2026, 2e partie (choix de l'auteur 7, 8, 9, 14, 15, 20)** : **hashtags à risque** (7, `legende.RISQUES`,
  `hashtag_sur`, `sans_risque` ; contenu adulte, drogue, violence, automutilation, « follow4follow »… ; mots courts comparés en entier :
  « charmeur » ou « armée » restent ; HASHTAGS_INTERDITS pour en ajouter ; aussi retirés des anciennes descriptions à l'envoi) ;
  **variété du fil** (8, `publication_auto.alterner` + `alternerPubli` du site : changer de créateur ET de lieu d'une publication à
  l'autre, sinon au moins de créateur ; lieu = historique "recette", sinon la réalisation du sketch) ; **nouveaux créateurs** (9,
  `moteur/decouverte.py`, workflow vitrine.yml chaque lundi) : comptes cités « @… » dans les titres de vos créateurs et des originaux
  (la recherche par hashtag est cassée dans yt-dlp et tikwm refuse les robots), 30 vérifiés au plus (8 vidéos de 8 à 150 s, publié
  ces 30 jours, médiane ≥ 5 000 vues), 6 proposés (episodes/decouvertes.json ; site : « ➕ » / « 🚫 » dans « Mes profils ») ; essai
  du 11 novembre : @enzolefrere, @aguerin30, @42malek, @brutuslerobuste, @jawedyoussef ; **paliers d'abonnés** (14, `moteur/paliers.py`
  après chaque relevé de stats.yml : 500, 1 000, 2 000… -> vidéo « merci » sur un script, vidéo manuelle jamais publiée seule, alerte ;
  episodes/paliers.json ; paliers déjà passés au 1er passage jamais fêtés après coup ; PALIERS=0) ; **vitrine du profil** (15,
  `moteur/vitrine.py`, chaque lundi : 3 bios de 80 caractères au plus par l'IA gratuite, sinon toutes prêtes ; 3 vidéos à épingler,
  les plus vues de créateurs différents ; logo à télécharger ; episodes/vitrine.json ; site : « 🏪 Vitrine du profil ») ; **registre
  des pannes** (20, `moteur/pannes.py` à la fin de chaque fabrication : lignes d'erreur / de repli du journal ramenées à leur forme
  (sans chiffres, liens, chemins, citations), comptées par jour, oubliées après 90 jours ; episodes/pannes.json, additionné par
  `fusion.FUSIONNES` ; site : Réglages → « 🧯 Registre des pannes », 30 derniers jours). Compte réel de la chaîne : **@petitsdramas**
  (`marque.COMPTE`, le logo disait « @petits.dramas »). NB du 11 novembre : le journal montre le crédit ElevenLabs épuisé (isolation et
  transcription passent par les outils gratuits).
- **Pas de personnage en trop (remarque de l'auteur du 11 novembre : 3 personnages au lieu de 2 quand on parle d'une personne absente)** :
  analyse des vidéos « grand frère » (yan_animation0) et « Débat loyer » : la séparation des voix trouvait 3 voix (doubleur qui change
  sa voix, ou message vocal du frère) -> 3 personnages, alors que l'original n'en montre que 2 ; et « Voilà, voilà mon frère » était
  pris pour une présentation (frère dessiné à côté). Corrections : Gemini dit qui est VISIBLE (`video_ia` : "visible", `visibles`,
  `voix_hors_champ` ; une personne dont on parle n'est pas un personnage) ; `equipe.presents` (fin du casting voix, PRESENTS=0) :
  plus de voix que de personnes à l'image (Gemini, sinon `nb_personnes` des mouvements ; jamais quand une seule personne est vue)
  -> la voix d'un message vocal / appel (Gemini, ou voix qui n'arrive qu'après « il m'a envoyé un vocal », « écoute ça »…) reste
  entendue et sous-titrée mais n'est pas dessinée (réplique "narrateur" + "_hors_champ" : sans carton de titre) ; sinon ses phrases
  retournent aux personnes à l'image, tour à tour ; « voilà » ne présente plus personne et jamais un absent (vocal, appel, pas là) ;
  son TikTok : jamais plus de personnes dessinées (qui parlent + muets) que dans l'original (`studio.compagnons`, sk["doublage"]["nb_vus"]).
  Aussi : textes de l'IA rendus en `{'texte': …}` (sous-titres « {'texte': 'Avec toi.'} » de « Robin, il faut que je te dise »)
  remis en texte (`doublage.texte_ia`).
  Même analyse : « Mais t'es où ? » répété dans une dispute (= « tu dis n'importe quoi ») faisait croire à un appel (écran coupé en
  deux) : `studio.appel_devine` compte les FORMES différentes des mots de l'appel, et avec une seule personne à l'image (créateur qui
  joue les deux rôles) « t'es où » / « je suis au… » seuls ne suffisent plus.
- **Outils libres du 11 novembre 2026 (choix de l'auteur 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)** : chaque outil a son
  interrupteur (réglage `=0`) et un repli sur l'ancien fonctionnement ; aucun appel payant. **Homme / femme** : inaSpeechSegmenter
  (INA, MIT, tensorflow-cpu installé à part ; `voix_genre.ina`, vote 1,5, INA_GENRE=0) et Praat (parselmouth, GPL ; longueur du conduit
  vocal sur F3/F4, réglée sur Jojo / Kévin / Lila : homme ≥ 16,35 cm, femme ≤ 16,2 ; `voix_genre.vtl`, vote 1, PRAAT=0), mesurés par
  `cartoon` (sk "_voix_ina", "_voix_vtl", "_voix_vtl_genre", une fois par rôle) et comptés dans `studio.genre_voix`. NB : une voix
  d'homme accélérée (dessin animé) sonne « femme » pour ina : Gemini (vote 2) reste le premier témoin. **Silero VAD** (MIT,
  `ecoute.parole`, VAD=0) : début de la parole (`doublage.debut_parole`) et mots écrits là où personne ne parle retirés (3 de suite au
  moins : `ecoute.mots_sans_voix`, ingé son). **WeSpeaker** (ResNet34 ONNX, CC-BY 4.0, `moteur/wespeaker.py`, outils/wespeaker,
  WESPEAKER=0) : 2e empreinte mise bout à bout avec ECAPA dans `locuteurs.rediariser` (`_avec_wespeaker` ; même voix ≈ 0,6, voix
  différentes ≈ 0,1). **emotion2vec+** (FunASR, `ecoute.emotion2vec`, EMOTION2VEC=0) : colère, joie, tristesse, SURPRISE, PEUR
  entendues (repli SpeechBrain). **pyloudnorm** (MIT, `jt.filtre_volume`, VOLUME_STATIQUE=0) : un seul réglage de volume pour toute la
  vidéo (-14 LUFS) + limiteur, au lieu du loudnorm dynamique. **Rhubarb Lip Sync** (MIT, `moteur/rhubarb.py`, outils/rhubarb téléchargé
  par emission.yml / pre_ecoute.yml, RHUBARB=0) : formes de bouche lues dans la voix (sk "_rhubarb"), elles remplacent celles du texte
  pour les sons TikTok (~2 s pour 10 s de voix). **TransNetV2** (MIT, `moteur/plans_video.py`, TRANSNET=0) : vraies coupes de
  l'original pour analyse_video et le témoin visages. **Grounding DINO + SAM 2** (Apache 2.0, `moteur/personnes_vues.py`,
  PERSONNES_VUES=0) : une image / 1,5 s, personnes (vraies ou dessinées) et objets tenus en une passe ; nombre de personnes vues
  ensemble -> `equipe.presents` et sk["doublage"]["nb_vus"] quand Gemini manque ; objets -> `objets_vus` (OWL-ViT en repli) ;
  silhouettes SAM 2 au début de chaque plan puis mouvement DANS chaque silhouette (décor et caméra retirés) -> témoin « qui parle »
  (poids 0,8). **Note de beauté** (prédicteur LAION v1, `moteur/beaute.py`, BEAUTE=0) : parmi les 3 décors semi-réalistes, le plus
  beau des cadrages pas plus de 25 % plus zoomés que le meilleur. **LanguageTool** (service public gratuit, `moteur/orthographe.py`,
  ORTHOGRAPHE=0) : sous-titres et description, seulement ce qui ne s'entend pas (accents, terminaisons muettes ajoutées) ; « J'sais
  pas » et les noms propres ne bougent jamais. **Pas fait** : RIFE (9) et LaMa (14) : leurs poids ne se trouvent que sur des copies non
  officielles, dans un format qui peut cacher du code (refusé par sécurité). Cache des modèles : hf-ecoute-v4 (+ outils/rhubarb,
  outils/wespeaker) ; venv refait une fois (contraintes.txt). Tests : ces outils sont coupés par défaut (`TestOutilsLibres`).
- **Registre des pannes du 15 novembre 2026 (demande de l'auteur : régler ce qui revient)** : Gemini « quota dépassé » (429) coupait
  Gemini pour toute la vidéo dès le 1er modèle : chaque modèle gratuit a SON quota -> modèle suivant ; limite « à la minute » -> attente
  du délai demandé (60 s au plus) ; « réponse trop lente » (timeout) -> 2e essai puis modèle suivant (`reseau._appel_openai`, texte de
  l'erreur gardé pour reconnaître un vrai quota épuisé). Aussi relevé dans le journal : corrections du compte rendu coupées à 1 500
  jetons (`remarque`, 4 000 maintenant) ; notification « vidéo prête » qui disait « note 0/100 » (note d'écriture des sketchs) ->
  confiance, jury et points à vérifier (`principal.resume_alerte`, sortie « resume » d'emission.yml) ; temps par étape faussés (contrôle
  de la vidéo finie et corrections du compte rendu comptés dans « jury » : étapes à part ; pas d'alerte « plus lent » sur une étape
  d'habitude < 1 min ni sur l'attente dans la file : `progression.lents`).
- **Liste du 15 novembre 2026 (choix de l'auteur 1, 4, 8, 14, 17, 18)** : **sous-titres karaoké avec un VRAI contrôle des paroles** (1,
  `jt.karaoke`, KARAOKE=0) : le mot dit passe en jaune à l'instant où on l'entend (instants des mots calés sur la voix) ; un mot affiché
  n'a un instant que s'il est retrouvé dans le son (même mot, ou corrigé à la même place avec le même début) ; moins de 85 % retrouvés
  ou ordre impossible -> sous-titres normaux pour cette réplique ; après la vidéo, le son de la vidéo FINIE est réécouté et l'écart
  mot jaune / mot entendu mesuré (`verif_finale.controle_karaoke` : > 0,3 s en médiane = point grave « karaoké décalé » ; le compte
  rendu retire alors le karaoké : sk["_sans_karaoke"]) ; **longs silences raccourcis** (4, `doublage.silences_a_couper` /
  `couper_silences` / `decaler`, SILENCES_COURTS=0) : blanc > 1 s sans voix (Silero) ni rire / souffle (voix isolée) ramené à 0,45 s,
  coupé au même instant dans la vidéo d'origine, la piste, le son mono et la voix ; sk["doublage"]["silences"] rejoué par « Corriger qui
  parle » ; **profils disparus** (8, `profils_tiktok.surveiller`, stats.yml une fois par jour, PROFILS_VEILLE=0) : introuvable deux jours
  de suite ou rien publié depuis 30 jours -> episodes/profils_etat.json, alerte téléphone, bandeau + « Retirer » dans « Mes profils » ;
  **courbe des vues des 48 premières heures** (14, `stats.noter_courbes` -> episodes/courbes.json, un point par relevé pendant 72 h,
  gardé 45 jours ; fiche d'une vidéo publiée : sa courbe en jaune, la médiane des autres en pointillés, « ×n la moyenne ») ;
  **meilleure heure selon le jour** (17, `stats.meilleure_heure_publication(jour=…)` : 6 vidéos au moins ce jour-là, sinon l'heure de
  la semaine ; `publication_auto.creneaux(…, jour)`, CONF["heures_jours"] et calendrier du site) ; **sujets qui marchent** (18,
  `recette.mots_gagnants` / `bonus_sujet` : mots et hashtags du titre des sons repris, 3 vidéos au moins, ±15 au potentiel d'un son ;
  créateurs et durée étaient déjà pris en compte). Réglages (Style) : cases « Sous-titres karaoké » et « Raccourcir les longs silences ».
  **Heure des statistiques affichée** (demande de l'auteur du 15 novembre) : sous la case « Heure choisie par les statistiques »
  (`#heureStats`, `site.heuresStats` = même calcul que `stats.meilleure_heure_publication`, refait dans l'appli à chaque relevé des vues :
  l'affichage et le calendrier suivent tout seuls quand l'heure change) : heure d'aujourd'hui et de demain, et de chaque jour.
- **Audit du 17 novembre 2026 (choix de l'auteur 1, 2, 8, 11, 14, 16, 19, 20, 21, 22, 23, 25, 29, 32)** : **contrôle IA trié**
  (`verif_finale.trier_ia` : les 132 anciennes remarques relues ; sous-titres, goût (« trop neutre »), âge / genre, personnes absentes,
  « question 3 non validée », décalé / flottant, animal voulu = fausses alertes écartées ; seuls les vrais défauts du dessin (bras en
  double, tête coupée, déformé) restent graves) ; **Gemini ÉCOUTE les passages en doute** (`video_ia.ecouter`, son mono 32 kb/s, ECOUTE_GEMINI=0) :
  désaccords des deux transcriptions encore ouverts après la 3e écoute (`equipe.departager`, avant l'IA texte) et sous-titres de la
  vidéo finie signalés faux (confirmé par Gemini = pas de point ; Gemini entend lui aussi autre chose = point grave) ; **décors variés**
  (`decors.recents` / `noter_usage`, decors/utilises.tsv fusionné : un décor de la banque déjà montré dans les 7 jours n'est pas repris,
  nouveau tirage `variante` si le budget le permet ; DECORS_VARIES=0) ; **publier plus vite quand ça décolle** (`publication_auto.decolle`
  / `avancer` : vidéo publiée < 48 h à plus de 2× la médiane des vues à 6 h (episodes/courbes.json) -> la vidéo en attente du même
  créateur, sinon du même lieu, passe en tête ; DECOLLE=0) ; **commentaire à épingler** (`legende.commentaire` : champ "commentaire" de
  l'IA, sinon « Team X ou team Y ? » avec les prénoms appelés, sinon une question générale ; historique "commentaire" ; fiche : « 💬
  Commentaire à épingler » + 📋 Copier ; TikTok ne laisse pas un robot épingler) ; **rappel avant expiration de la clé GitHub de
  l'appli** (date lue dans la réponse de GitHub quand il la donne, sinon champ « 📅 Date d'expiration » de Réglages → Connecter ;
  bandeau 14 jours avant, rouge les 3 derniers ; « jt_cle_expire » sur l'appareil) ; **dépôt allégé** (le téléchargement était déjà
  « dernière version seulement » ; maquettes (62 Mo, jamais lues) et anciens décors (style croquis + fichiers sans index, ~39 Mo)
  retirés du dépôt et rangés dans la release « archives-fichiers » par le workflow ranger.yml : dézipper à la racine pour les remettre ;
  les décors croquis seraient refaits si STYLE_DECOR=croquis revenait) ; **plus d'erreur silencieuse** (`pannes.avale` : les 51
  « except Exception: pass » écrivent « erreur avalée dans fichier.fonction » une fois par endroit -> registre des pannes ;
  moteur/pannes.py ajouté aux téléchargements partiels d'emission.yml et garde.yml) ; **dessin découpé** (bande son sortie de
  `cartoon.rendre` -> `cartoon._bande_son`, son identique à l'octet près ; `tache`, `keystone`, `rembobine`, `teinte_lut` remontés au
  niveau du module ; le reste de `rendre` dépend de dizaines de variables partagées : à découper petit à petit, toujours en vérifiant
  le son et l'image avant / après) ; **code des sketchs rangé** dans `moteur/sketchs/` (actu, serie, casting, realiste, betisier,
  voix_auteur, voix_design ; un petit fichier garde l'ancien nom dans moteur/ : « import actu » marche toujours) ; **tests découpés
  par sujet** (tests/commun.py = préparation commune ; test_ecriture, test_dessin, test_son_voix, test_site_publication, test_listes ;
  `python -m unittest discover -s tests`) ; **📅 Ma semaine** (onglet TikTok : vidéos fabriquées et publiées, vues gagnées
  (stats.json "vues_hist", un relevé par heure), abonnés gagnés, dépenses, confiance moyenne) ; **coût de chaque vidéo**
  (`principal.cout_estime` : Claude + ElevenLabs 0,00022 $ / caractère + GPU Modal 0,00031 $ / s ; historique couts "total_usd" et
  "modal_mesure_usd" = vraie dépense Modal pendant la fabrication ; ligne « 💶 Coût de cette vidéo » dans la fiche).
- **Barbes** : jamais de grosse barbe (barbe mal rasée au plus) ; adultes et 16-17 ans seulement, jamais d'enfant barbu.
- **Jury qualité** (`moteur/qualite.py`) : 5 critiques (humoriste, réalisateur, DA, son, spectateur), gratuit ET Claude, corrections
  automatiques puis nouvelle version (on garde la meilleure), mémoire des erreurs qui reviennent ; à enrichir à chaque remarque de l'auteur.
- Code : `moteur/studio.py` (`decouper`, `plans_larges`) et `moteur/cartoon.py` (`vue`, `cadre_plan`) ; réglage MONTAGE (large par défaut, dynamique, simple).

## Claude et les outils payants (sons TikTok)
- Claude (s'il a du crédit) : mise en scène du son TikTok (qui parle, découpage, émotions, indications de jeu, lieux, tenues, objets),
  analyse des images clés de la vidéo d'origine, jury et contrôle de la vidéo finie ; ElevenLabs : isolation de la voix et
  transcription ; Modal : décors semi-réalistes (SDXL) et écoute (NeMo, Florence-2). Le repli gratuit reste TOUJOURS disponible.

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
