# Consignes du projet (préférences de l'auteur de la chaîne @petitsdramas)

À respecter pour toute modification du robot vidéo :

## Budget et outils
- Tout doit fonctionner **sans crédit Claude** : chaque appel à Claude a un repli automatique (règles, hasard contrôlé, analyse
  gratuite du son et de l'image). Les consignes pour Claude restent prêtes pour plus tard.
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
- Code : `moteur/studio.py` (`decouper`) et `moteur/cartoon.py` (`vue`, `cadre_plan`) ; réglage MONTAGE (dynamique par défaut).

## Langue
- L'auteur parle français : répondre et documenter en français simple.
