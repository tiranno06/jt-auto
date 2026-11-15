# Archives : sketchs écrits par le robot, Jojo / Kévin / Lila et anciens styles (mis de côté le 15 novembre 2026)

Ces consignes ne s'appliquent plus tant que l'auteur ne reprend pas les sketchs (décision du 15 novembre 2026 : le projet = les
vidéos faites sur les sons TikTok). Le code est toujours là ; sur le site tout est masqué (classe « ancien ») et revient avec la
variable GitHub SITE_COMPLET=1. Gardé ici pour mémoire, dans l'ordre d'origine de CLAUDE.md.

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
- Vidéos **dynamiques**, toujours en fonction de l'audio, de son univers et des échanges entre les personnages.
- **Beaucoup de changements de plan** : plans serrés et plans larges sur les personnages, plans de réaction de celui qui écoute.
- **Caméra vivante** : mouvements dans chaque plan (avancée, recul, travelling, caméra à l'épaule, zoom choc) et passages de plan
  variés (coupe franche, glissé, filé, zoom).
- **Tout doit rester fluide** : coupes calées sur la voix (entre deux mots ou sur un mot appuyé), mouvements adoucis, flou de
  mouvement sur les passages rapides, pas de plan trop court ni de faux raccord.
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
- **Fiabilité de fabrication** : le dessin toon doit rester rapide (masques sur-échantillonnés ×2, ×1 sur les très gros plans,
  contours par `cv2.findContours`, jamais de `np.mgrid` ni de grosse dilatation : un gros plan coûtait 40 s et 2,4 Go par image et
  GitHub coupait la machine) ; un dessin qui plante repasse en ancien style ; le « Réveil de secours » (garde.yml) relance une
  fois toute fabrication en échec des 6 dernières heures.
## Ancien « mode amélioré » (écriture des sketchs par Claude)
- **Claude** : écriture et doublage (comprendre l'audio, découpage en scènes, émotions, indications de jeu), direction artistique
  du studio (lieux, tenues, coiffures, objets, gags écrits, plans et mouvements de caméra, réactions), analyse des images clés de
  la vidéo TikTok d'origine, contrôle qualité de la vidéo finie.
- **Graphisme** : décors générés (Stable Diffusion XL sur Modal) adaptés à l'histoire, en plus des décors dessinés.
- **Voix** : ElevenLabs (voix réalistes, rires, colère, voix sur mesure de la chaîne).
- Le mode gratuit (sans Claude) doit **toujours** rester disponible en repli automatique si le crédit manque.
- Les briques existent (`ecrire.py`, `doublage.py` : consignes « studio », `controle.py`, `decors.py`) : à enrichir sans jamais
  casser le repli gratuit.
