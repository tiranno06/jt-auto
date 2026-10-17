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
  manches courtes coupées droit, sans boule à l'épaule. (Pied nu : garder la version validée par l'auteur, un essai plus long a été refusé.)
  Casting libre (personnages différents à chaque vidéo).
- **Le maximum de détails partout** : tenues, coiffures, barbes, chapeaux, accessoires, expressions du visage, décors.
- Tout l'univers visuel (lieu, tenues, plans, émotions) se construit autour de l'audio TikTok (paroles, intonations, émotions,
  ambiance) et de l'image de la vidéo d'origine ; la banque visuelle s'enrichit vidéo après vidéo.

## Montage (à garder en tête pour chaque vidéo)
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
- **Barbes** : jamais de grosse barbe (barbe mal rasée au plus) ; adultes et 16-17 ans seulement, jamais d'enfant barbu.
- **Jury qualité** (`moteur/qualite.py`) : 5 critiques (humoriste, réalisateur, DA, son, spectateur), gratuit ET Claude, corrections
  automatiques puis nouvelle version (on garde la meilleure), mémoire des erreurs qui reviennent ; à enrichir à chaque remarque de l'auteur.
- **Fiabilité de fabrication** : le dessin toon doit rester rapide (masques sur-échantillonnés ×2, ×1 sur les très gros plans,
  contours par `cv2.findContours`, jamais de `np.mgrid` ni de grosse dilatation : un gros plan coûtait 40 s et 2,4 Go par image et
  GitHub coupait la machine) ; un dessin qui plante repasse en ancien style ; le « Réveil de secours » (garde.yml) relance une
  fois toute fabrication en échec des 6 dernières heures.
- Code : `moteur/studio.py` (`decouper`) et `moteur/cartoon.py` (`vue`, `cadre_plan`) ; réglage MONTAGE (dynamique par défaut).

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
