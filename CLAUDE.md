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
  (`publication_auto.creneaux`, chaque publication automatique du jour compte pour un créneau) ; calendrier du site sur les deux heures.
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
  sans IA ; même son, mêmes répliques ; remarque gardée pour le jury) ; **OpenRouter** = 4e IA gratuite (secret OPENROUTER_API_KEY,
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
  métiers, émotions, puis #petitsdramas et la niche ; NB_HASHTAGS) ; `publier.py` nettoie aussi les anciennes légendes à l'envoi.
- **Style « croquis » = STYLE PAR DÉFAUT (validé par l'auteur le 30 octobre 2026)** : `moteur/croquis.py` (dessin) +
  `moteur/perso_croquis.py` (traduit la pose du moteur : bras en angles -> coude et main, émotion -> expression, bouche ouverte selon la
  voix en gardant l'expression, forme des lèvres par son, regard, larmes / sueur / rougeur, costume, métier, chapeau, lunettes, barbe
  mal rasée) ; STYLE_PERSO=croquis (défaut ; « toon » et « ancien » restent au choix) ; silhouette tirée par personnage, le PETIT ou
  le GRAND pour tous les âges (SILHOUETTE = petit / grand / les_deux) ; tête et pieds aux mêmes places que l'ancien style (cadrages,
  objets tenus, contrôle image inchangés) ; toujours debout (assis = jambes à travers les meubles) ; décors dessinés ou IA passés à
  l'encre + aquarelle sur papier (`croquis.croquifier`, DECOR_CROQUIS=0 pour couper). Vitesse : chaque personnage dessiné dans un petit
  cadre, aquarelle / hachures / flous calculés seulement dans la zone peinte (sinon 10 fois plus lent) ; une ombre ne déborde jamais
  d'une forme (sur la toile « vide » du super-échantillonnage, un débord devient une tache noire). Maquettes et références :
  `maquettes/croquis/` (images de l'auteur, faites par lui avec une IA). Choix déjà faits : les DEUX silhouettes (le petit à grosse tête et le grand stickman), pour enfants, ados,
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
