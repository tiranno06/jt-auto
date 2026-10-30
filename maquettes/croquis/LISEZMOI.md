# Style « croquis » — maquettes EN ATTENTE DE VALIDATION de l'auteur

Rien ici n'est branché au robot. Ce dossier garde le prototype du nouveau style de personnages (d'après les images de référence
de l'auteur, faites par lui avec une IA : `references/`) et les visuels de validation (`visuels/`).

- `croquis.py` : dessin du style (papier, encre, aquarelle, hachures, têtes rondes, yeux, 30 expressions, corps « petit » (chibi)
  et « grand » (stickman géant), poses de bras et de jambes, poses fondues `(poseA, poseB, u)`, bouche ouverte selon la voix `ouv`,
  clignement doux `cligne`, main sur le visage qui passe devant la tête, chapeaux, outils des métiers).
- `serie2_outils.py` : coiffures, âges (enfant, ado, adulte, senior pour les deux silhouettes), chaise, bulles, décors du robot
  passés au style croquis (`croquifier`), scènes verticales 9:16.
- `anim3.py` : animation fluide (30 i/s, mouvements adoucis, expressions en fondu, bouche calée sur la voix, respiration, sauts en arc).
  Voix de test : Piper (`pip install piper-tts`, voix fr_FR tom / siwis de rhasspy/piper-voices), dossier `voix/` à recréer.
- Les scripts `p6`…`p9`, `emotions.py`, `visages.py`, `metiers_pl.py` refont les planches (lancer depuis ce dossier).

Choix de l'auteur (30 octobre 2026) : **les deux silhouettes** (le petit ET le grand), pour tous les âges ; visuels 1-5 validés
« pour le moment » ; animation : **beaucoup plus fluide** (pas d'image par image ni de saccades).
