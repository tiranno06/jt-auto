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
- Personnages adultes dans le style des chaînes « toons » de TikTok (Aristos Toons, Lescromatoons, MotionToonz) sur la base de
  nos anciens personnages : grosse tête ronde blanche posée sur le col, yeux en ovales noirs, vêtements aux épaules carrées,
  trait noir épais, aplats. Casting libre (personnages différents à chaque vidéo).
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
- Position assise : vue de face (buste, genoux et jambes dans le même sens).
- **Barbes** : jamais de grosse barbe (barbe mal rasée au plus) ; adultes et 16-17 ans seulement, jamais d'enfant barbu.
- **Jury qualité** (`moteur/qualite.py`) : 5 critiques (humoriste, réalisateur, DA, son, spectateur), gratuit ET Claude, corrections
  automatiques puis nouvelle version (on garde la meilleure), mémoire des erreurs qui reviennent ; à enrichir à chaque remarque de l'auteur.
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

## Plus tard : remplaçants gratuits de Claude (recherche d'octobre 2026, en attente de l'accord de l'auteur)
- L'auteur n'a plus de crédit Claude. Piste retenue : clés gratuites **Gemini** (images, doublage, contrôle ; Flash ≈ 20/jour,
  Flash-Lite ≈ 500/jour) et **Mistral** (humour en français), puis Groq, OpenRouter `:free` (1 000/jour après 10 $ uniques),
  NVIDIA / Cloudflare en dépannage, modèle libre sur Modal (Gemma 4 / Qwen 3.6 avec vLLM, ~0,2-0,5 $/vidéo) ; bascule avec LiteLLM ;
  le mode gratuit actuel reste le dernier secours. Fermés ou plus gratuits en 2026 : GitHub Models, Cerebras ; Cohere interdit
  l'usage commercial. À brancher seulement quand l'auteur aura créé les clés.

## Langue
- L'auteur parle français : répondre et documenter en français simple.
