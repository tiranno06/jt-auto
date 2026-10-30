"""39 lieux de plus (liste gardée par l'auteur, créée après la validation du style croquis le 30 octobre 2026), dessinés comme les
autres décors (trait noir, aplats, gags écrits lisibles) puis passés à l'encre et à l'aquarelle par cartoon (style croquis).
Maison : salle de bain, jardin, balcon, garage de maison, grenier, salle à manger ; école : cour de récré, cantine, bureau du
proviseur, bibliothèque, amphi ; ville : arrêt de bus, métro, gare, aéroport, parking, fast-food, kebab, cinéma ; sorties : plage,
piscine, parc, camping, montagne, stade, salle de concert, boîte de nuit ; santé et services : hôpital, urgences, pharmacie,
commissariat, prison, banque, poste ; autres : mariage, église, plateau télé, studio radio, salle de jeux vidéo.
Chaque lieu : GAGS (3 textes), COULEURS_MUR, REGLES (mots de l'audio qui le désignent), DECOR_EN (description pour les décors IA)."""
import math
import numpy as np, cv2

TRAIT = (26, 22, 30)
AA = cv2.LINE_AA
S = 1210                                                                   # = decor_dessin.SOL
W = 1080

GAGS = {
    "salle_de_bain": ["Occupé (depuis 45 minutes)", "Qui a fini le papier ?!", "Miroir : ne pas juger"],
    "jardin": ["Attention : nains de jardin méchants", "Pelouse interdite (même au chien)", "Potager bio (enfin, presque)"],
    "balcon": ["Vue sur le balcon d'en face", "Plantes en survie", "Interdit de chanter après 22 h"],
    "garage_maison": ["On range dimanche (lequel ?)", "Ici reposent nos vélos", "Bricolage : niveau débutant"],
    "grenier": ["Souvenirs (et araignées)", "Ne pas ouvrir : Noël 1998", "Fantôme : loyer impayé"],
    "salle_a_manger": ["On ne parle pas la bouche pleine", "Repas de famille : courage", "Le dessert se mérite"],
    "cour_recre": ["Interdit de courir (lol)", "Échange de cartes : zone libre", "Sonnerie dans 3… 2… 1…"],
    "cantine": ["Menu : surprise du chef", "Purée du jour (comme hier)", "Ne pas lancer les petits pois"],
    "bureau_proviseur": ["Frappez avant d'entrer (et de pleurer)", "Règlement intérieur, page 1 sur 400", "Café du proviseur : NE PAS TOUCHER"],
    "bibliotheque": ["Silence (on vous voit)", "Livres en retard : on sait où vous habitez", "Rayon : romans d'amour tristes"],
    "amphi": ["Partiels dans 3 jours", "Le prof ne voit pas le dernier rang (il voit)", "Wi-Fi : en option"],
    "arret_bus": ["Prochain bus : un jour", "Ligne 12 : retard habituel", "Abri anti-pluie (presque)"],
    "metro": ["Attention à la marche (et aux gens)", "Ligne 14 : direction loin", "Pas de manspreading"],
    "gare": ["TGV 8247 : retard 45 min", "Voie 3 (ou 4, on verra)", "Composteur en panne"],
    "aeroport": ["Embarquement porte 42", "Bagages : 23 kg (pas 24)", "Vol annulé (bon courage)"],
    "parking": ["Place réservée au boss", "Parking payant (même à pied)", "Ne pas oublier où on s'est garé"],
    "fast_food": ["Menu XXL (et un salade)", "Frites à volonté (non)", "Commande n° 247"],
    "kebab": ["Salade tomate oignon ?", "Sauce blanche obligatoire", "Kebab du Chef : ouvert 24/24"],
    "cinema": ["Éteignez vos téléphones", "Pop-corn : 9 € (oui)", "Salle 5 : film d'horreur"],
    "plage": ["Baignade surveillée (par les mouettes)", "Crème solaire indice 50", "Interdit aux châteaux de sable moches"],
    "piscine": ["Bonnet obligatoire", "Pas de bombe (sauf le maître-nageur)", "Douche avant baignade !"],
    "parc": ["Pelouse au repos", "Chiens tenus en laisse (et maîtres aussi)", "Pigeons : ne pas nourrir"],
    "camping": ["Camping des Flots Bleus", "Animation karaoké : 21 h", "Moustiques gratuits"],
    "montagne": ["Piste noire (bonne chance)", "Chocolat chaud : 6 €", "Attention : chute de skieurs"],
    "stade": ["Allez les Bleus !", "Score : 0 - 0 (encore)", "Arbitre : on t'aime pas"],
    "concert": ["Tournée d'adieu n° 6", "Fosse : ne pas pousser", "Rappel ! Rappel !"],
    "boite_nuit": ["Dress code : sois beau", "DJ ce soir : DJ Tonton", "Fermeture : quand le soleil se lève"],
    "hopital": ["Repos : interdit aux visiteurs bruyants", "Menu : soupe (encore)", "Sonnez l'infirmière (pas trop)"],
    "urgences": ["Temps d'attente : 6 h", "Ticket n° 87", "Merci de votre patience (vraiment)"],
    "pharmacie": ["Ordonnance illisible ? On traduit", "Vitamine C en promo", "Pastilles pour la toux"],
    "commissariat": ["Dépôt de plainte : prenez un ticket", "Avis de recherche : chat perdu", "Café des agents"],
    "prison": ["Sortie : dans 10 ans", "Cantine du lundi : surprise", "Promenade : 15 h"],
    "banque": ["Votre argent est en sécurité (le nôtre aussi)", "Prêt immobilier : sur 75 ans", "Guichet fermé (toujours)"],
    "poste": ["Colis en attente depuis 1 an", "Timbres : rouge ou vert ?", "Faites la queue (longue)"],
    "mariage": ["Oui, je le veux (le gâteau)", "Vive les mariés !", "Bar à bonbons"],
    "eglise": ["Silence, s'il vous plaît", "Messe de 11 h", "Quête : merci"],
    "plateau_tele": ["EN DIRECT", "Applaudissez !", "Le Grand Débat"],
    "studio_radio": ["ON AIR", "Radio Petits Dramas 98.4", "Ne pas toucher aux boutons"],
    "salle_jeux": ["Game over", "Encore une partie !", "Record : 999 999"],
}
COULEURS_MUR = {"salle_de_bain": (205, 232, 238), "jardin": (150, 200, 240), "balcon": (150, 200, 240), "garage_maison": (175, 178, 182),
                "grenier": (190, 160, 120), "salle_a_manger": (236, 220, 196), "cour_recre": (150, 200, 240), "cantine": (232, 236, 214),
                "bureau_proviseur": (214, 200, 176), "bibliotheque": (210, 186, 150), "amphi": (220, 214, 200), "arret_bus": (150, 200, 240),
                "metro": (220, 226, 230), "gare": (226, 220, 206), "aeroport": (226, 232, 238), "parking": (150, 200, 240),
                "fast_food": (250, 222, 120), "kebab": (240, 210, 170), "cinema": (60, 30, 40), "plage": (140, 200, 245),
                "piscine": (200, 230, 240), "parc": (150, 200, 240), "camping": (150, 200, 240), "montagne": (150, 200, 240),
                "stade": (60, 80, 120), "concert": (30, 24, 40), "boite_nuit": (36, 24, 56), "hopital": (222, 238, 236),
                "urgences": (226, 236, 240), "pharmacie": (226, 242, 228), "commissariat": (196, 206, 222), "prison": (170, 170, 172),
                "banque": (226, 222, 210), "poste": (250, 222, 120), "mariage": (246, 236, 230), "eglise": (210, 196, 170),
                "plateau_tele": (40, 50, 90), "studio_radio": (60, 64, 76), "salle_jeux": (40, 30, 70)}
LIEUX = tuple(GAGS)
REGLES = [
    ("salle_de_bain", r"salle de bains?|douche|baignoire|brosse à dents|toilettes|\bwc\b|lavabo|bathroom"),
    ("jardin", r"jardin|pelouse|tondeuse|barbecue|potager|garden|backyard"), ("balcon", r"balcon|terrasse de l'appart|balcony"),
    ("garage_maison", r"dans le garage|garage de la maison|établi|home garage"), ("grenier", r"grenier|combles|attic"),
    ("salle_a_manger", r"salle à manger|à table|repas de famille|dîner de famille|dining room"),
    ("cour_recre", r"récré|cour de l'école|cour du collège|playground"), ("cantine", r"cantine|réfectoire|self du lycée|cafeteria"),
    ("bureau_proviseur", r"proviseur|principal du collège|directeur de l'école|dans le bureau du dirlo|principal's office"),
    ("bibliotheque", r"biblioth[eè]que|\bcdi\b|library"), ("amphi", r"amphi|\bfac\b|université|partiels|lecture hall"),
    ("arret_bus", r"arrêt de bus|abribus|le bus|bus stop"), ("metro", r"\bmétro\b|\brer\b|subway|tube station"),
    ("gare", r"\bgare\b|\btgv\b|\bsncf\b|quai du train|le train|train station"), ("aeroport", r"aéroport|avion|embarquement|valises?|airport"),
    ("parking", r"parking|car park|garé"), ("fast_food", r"mcdo|macdo|burger king|fast-?food|burger|frites|nuggets"),
    ("kebab", r"kebab|grec\b|tacos|sauce blanche|samouraï"), ("cinema", r"cinéma|\bciné\b|film|pop-?corn|movie theater"),
    ("plage", r"plage|la mer\b|sable|bronzer|beach"), ("piscine", r"piscine|plonge|maillot de bain|swimming pool"),
    ("parc", r"\bparc\b|jardin public|square|park bench"), ("camping", r"camping|tente|caravane|mobil-?home|campsite"),
    ("montagne", r"montagne|\bski\b|skier|station de ski|neige|chalet|mountain"), ("stade", r"stade|match de foot|supporters?|stadium"),
    ("concert", r"concert|festival|chanteur sur scène|scène|stage lights"), ("boite_nuit", r"bo[iî]te de nuit|en boîte|night ?club|soirée dansante"),
    ("hopital", r"h[ôo]pital|chambre d'hôpital|hospital room|perfusion"), ("urgences", r"urgences|\bsamu\b|emergency room"),
    ("pharmacie", r"pharmacie|pharmacien|médicaments|pharmacy"), ("commissariat", r"commissariat|garde à vue|déposer plainte|police station"),
    ("prison", r"prison|taule|derrière les barreaux|cellule|jail"), ("banque", r"\bbanque\b|banquier|conseiller bancaire|découvert|bank"),
    ("poste", r"la poste|bureau de poste|colis|facteur|post office"), ("mariage", r"mariage|mariée?s?|noces|wedding"),
    ("eglise", r"église|curé|messe|church"), ("plateau_tele", r"plateau télé|émission de télé|en direct à la télé|tv studio|jeu télé"),
    ("studio_radio", r"radio|à l'antenne|animateur radio|on air"), ("salle_jeux", r"jeux? vidéo|console|manette|playstation|gaming|fortnite"),
]
DECOR_EN = {"salle_de_bain": "bathroom, bathtub, sink with mirror, tiles, towels", "jardin": "back garden, lawn, flowers, fence, barbecue",
            "balcon": "apartment balcony, railing, plants, city view", "garage_maison": "home garage, workbench, bikes, boxes",
            "grenier": "attic, wooden beams, old boxes, dusty trunk", "salle_a_manger": "dining room, set table, chairs, chandelier",
            "cour_recre": "school playground, hopscotch, trees, basketball hoop", "cantine": "school cafeteria, trays, long tables",
            "bureau_proviseur": "headmaster office, desk, diplomas, flag", "bibliotheque": "library, bookshelves, reading tables, lamps",
            "amphi": "university lecture hall, rows of seats, blackboard", "arret_bus": "bus stop shelter on a street, bus sign",
            "metro": "subway station platform, tiles, train arriving", "gare": "train station hall, departure board, platform",
            "aeroport": "airport terminal, departure board, big windows with planes", "parking": "parking lot, painted lines, cars",
            "fast_food": "fast food restaurant counter, menu board, burgers", "kebab": "kebab shop, rotating meat spit, menu board",
            "cinema": "movie theater, red seats, big screen", "plage": "sunny beach, sea, sand, parasol", "piscine": "public swimming pool, lanes, diving board",
            "parc": "city park, trees, bench, pond", "camping": "campsite, tent, campfire, caravan", "montagne": "snowy mountain ski resort, chalet, pine trees",
            "stade": "football stadium, crowd, pitch, floodlights", "concert": "concert stage, spotlights, speakers, crowd",
            "boite_nuit": "nightclub, dance floor, disco ball, DJ booth", "hopital": "hospital room, bed, drip, monitor",
            "urgences": "hospital emergency waiting room, chairs, ticket screen", "pharmacie": "pharmacy, shelves of medicine, green cross",
            "commissariat": "police station desk, wanted posters", "prison": "prison cell, bars, bunk bed", "banque": "bank counter, safe, logo",
            "poste": "post office counter, parcels, mailboxes", "mariage": "wedding reception, arch of flowers, wedding cake",
            "eglise": "church interior, stained glass, pews", "plateau_tele": "tv show studio, lights, presenter desk, screens",
            "studio_radio": "radio studio, microphones, mixing desk, on air sign", "salle_jeux": "gaming room, big screen, consoles, neon lights"}

import decor_dessin as D                                                   # (après les données : import croisé sans souci)
import decor_details as DX


# ------------------------------------------------------------------ outils
def _int(img, lieu, rng, motif="uni", c_sol=(190, 170, 150), m_sol="parquet", plinthe=True):
    D.mur(img, D._variante(COULEURS_MUR[lieu], rng, 8), motif, rng); D.sol(img, D._variante(c_sol, rng, 6), m_sol)
    if plinthe: D.plinthe(img)


def _ext(img, moment, rng, c_sol=(130, 190, 90), m_sol="moquette", ville=False):
    D.ciel(img, 0, 0, W, S, moment, rng, ville); D.sol(img, D._variante(c_sol, rng, 8), m_sol)


def _arbre(img, x, y_sol, k=1.0, col=(90, 160, 80)):
    D.boite(img, x - 18 * k, y_sol - 260 * k, x + 18 * k, y_sol, (130, 90, 60), 5)
    for dx, dy, r in ((0, -330, 120), (-80, -270, 90), (80, -270, 90)): D.rond(img, (x + dx * k, y_sol + dy * k), r * k, D._variante(col, np.random.default_rng(int(x)), 10), 6)


def _gens(img, x0, x1, y, rng, n=8, k=1.0):
    """Foule simplifiée (silhouettes rondes au loin)."""
    for i in range(n):
        x = x0 + (x1 - x0) * (i + 0.5) / n + rng.uniform(-12, 12); c = D._variante(((200, 80, 80), (80, 120, 200), (240, 200, 70), (90, 170, 110))[i % 4], rng, 12)
        D.boite(img, x - 22 * k, y - 50 * k, x + 22 * k, y + 20 * k, c, 4, 12); D.rond(img, (x, y - 72 * k), 22 * k, (245, 240, 236), 4)


def _ecran_infos(img, x0, y0, x1, y1, lignes, coul=(250, 200, 60)):
    D.boite(img, x0, y0, x1, y1, (24, 26, 32), 8, 6)
    h = (y1 - y0 - 20) / max(1, len(lignes))
    for k, l in enumerate(lignes): D.texte(img, l, x0 + 14, y0 + 10 + k * h, x1 - 14, y0 + 10 + (k + 1) * h, coul, int(h * 0.55), False)


# ------------------------------------------------------------------ maison
def salle_de_bain(img, rng, res, gag, moment, allume):
    _int(img, "salle_de_bain", rng, "uni", (230, 236, 240), "carrelage")
    for y in range(300, S, 60):                                            # faïence
        D.ligne(img, (0, y), (W, y), (180, 205, 212), 3)
    D.boite(img, 600, 320, 960, 640, (200, 228, 240), 8, 20); res["miroirs"] = res.get("miroirs", []) + [(600, 320, 960, 640)]
    D.boite(img, 620, 700, 940, 790, (250, 250, 250), 6, 20); D.ligne(img, (780, 660), (780, 700), (170, 175, 185), 12)   # lavabo
    D.boite(img, 40, S - 230, 520, S + 40, (250, 250, 250), 7, 40); D.ligne(img, (60, S - 230), (500, S - 230), (150, 200, 230), 10)   # baignoire
    for k, c_ in enumerate(((230, 110, 140), (110, 180, 230))): D.boite(img, 140 + k * 140, 520, 240 + k * 140, 760, c_, 5, 6)   # serviettes
    D.affiche(img, 60, 300, 520, 460, gag(0), (250, 250, 245)); res["fenetre"] = None


def jardin(img, rng, res, gag, moment, allume):
    _ext(img, moment, rng)
    for x in range(0, W, 70): D.boite(img, x + 6, S - 180, x + 46, S + 20, (240, 236, 220), 4, 6)     # palissade blanche
    _arbre(img, 140, S - 40, 1.1); _arbre(img, 930, S - 60, 0.9)
    D.boite(img, 640, S + 60, 860, S + 200, (60, 60, 66), 6, 10); D.texte(img, "BBQ", 640, S + 60, 860, S + 200, (250, 180, 60), 50)   # barbecue
    for k in range(6): D.rond(img, (300 + k * 60, S + 260 + (k % 2) * 20), 18, ((230, 70, 90), (250, 210, 60), (200, 120, 230))[k % 3], 4)   # fleurs
    D.affiche(img, 380, S - 330, 720, S - 200, gag(0), (250, 240, 200)); res["fenetre"] = (0, 0, W, S)


def balcon(img, rng, res, gag, moment, allume):
    D.ciel(img, 0, 0, W, S + 120, moment, rng, True)
    D.sol(img, D._variante((170, 160, 150), rng, 6), "carrelage", S + 120)
    D.boite(img, 0, S - 140, W, S - 112, (60, 64, 72), 5)                  # rambarde
    for x in range(20, W, 54): D.ligne(img, (x, S - 112), (x, S + 120), (60, 64, 72), 8)
    for x in (120, 940): D.pot(img, x, S + 170, 1.6, D._variante((200, 110, 80), rng))
    D.affiche(img, 340, 200, 740, 340, gag(1), (250, 250, 240)); res["fenetre"] = (0, 0, W, S)


def garage_maison(img, rng, res, gag, moment, allume):
    _int(img, "garage_maison", rng, "uni", (150, 152, 156), "carrelage", False)
    D.boite(img, 40, 300, 540, 700, (210, 180, 130), 6)                   # panneau d'outils
    for k in range(8): D.ligne(img, (80 + k * 56, 340), (80 + k * 56, 440 + (k % 3) * 40), ((200, 50, 50), (60, 110, 200), (90, 90, 100))[k % 3], 10)
    D.boite(img, 600, S - 300, 1040, S - 60, (190, 150, 100), 6)          # cartons empilés
    for k in range(3): D.boite(img, 620 + k * 140, S - 280, 740 + k * 140, S - 180, (215, 175, 120), 4); D.texte(img, ("NOËL", "DIVERS", "?!")[k], 620 + k * 140, S - 280, 740 + k * 140, S - 180, TRAIT, 26)
    D.rond(img, (300, S + 120), 80, (40, 40, 46), 8); D.rond(img, (520, S + 120), 80, (40, 40, 46), 8)   # vélo
    D.ligne(img, (300, S + 120), (420, S + 20), (200, 60, 60), 10); D.ligne(img, (420, S + 20), (520, S + 120), (200, 60, 60), 10)
    D.affiche(img, 600, 320, 1020, 460, gag(0), (250, 220, 80)); res["lampes"].append(D.suspension(img, 540, 110, True))


def grenier(img, rng, res, gag, moment, allume):
    _int(img, "grenier", rng, "uni", (150, 110, 80), "parquet", False)
    D.poly(img, [(0, 0), (540, 0), (0, 600)], (120, 85, 60), 0); D.poly(img, [(W, 0), (540, 0), (W, 600)], (120, 85, 60), 0)   # toit en pente
    for x in (200, 540, 880): D.ligne(img, (x, 0), (x, S), (110, 75, 50), 22)
    res["fenetre"] = (440, 160, 640, 360); D.fenetre(img, 440, 160, 640, 360, moment, rng)
    D.boite(img, 60, S - 200, 360, S + 40, (140, 90, 60), 7, 10); D.texte(img, "MALLE", 60, S - 150, 360, S - 60, (240, 220, 160), 40)
    for k in range(3): D.boite(img, 700 + k * 100, S - 160 - k * 70, 820 + k * 100, S + 40 - k * 70 * 0, (200, 170, 120), 4)
    cv2.circle(img, (960, 120), 60, (240, 240, 240), 2, AA); cv2.line(img, (960, 60), (960, 180), (240, 240, 240), 2, AA)   # toile d'araignée
    D.affiche(img, 700, 420, 1020, 560, gag(1), (240, 230, 200))


def salle_a_manger(img, rng, res, gag, moment, allume):
    _int(img, "salle_a_manger", rng, "rayures", (180, 130, 90), "parquet")
    res["fenetre"] = (640, 300, 1000, 680); D.fenetre(img, *res["fenetre"], moment, rng, rideaux=D._variante((150, 60, 70), rng))
    D.cadre_tableau(img, 100, 320, 460, 600, rng); DX.lustre(img, 540, 90, allume)
    D.boite(img, 120, S - 40, 960, S + 10, (250, 250, 248), 5)            # table nappée
    for x in (220, 420, 640, 840): D.rond(img, (x, S - 52), 30, (250, 250, 250), 4)   # assiettes
    for x in (140, 940): D.boite(img, x - 10, S + 10, x + 10, S + 160, (130, 90, 60), 4)
    D.affiche(img, 100, 640, 460, 780, gag(0), (252, 248, 236), punaises=False)


# ------------------------------------------------------------------ école
def cour_recre(img, rng, res, gag, moment, allume):
    _ext(img, moment, rng, (180, 180, 186), "trottoir")
    D.boite(img, 0, 300, W, S, (220, 190, 160), 6)                        # bâtiment de l'école
    for x in range(60, W - 100, 200): D.fenetre(img, x, 380, x + 140, 560, moment, rng)
    D.boite(img, 380, 660, 700, S, (150, 80, 60), 6); D.texte(img, "ÉCOLE", 380, 600, 700, 660, TRAIT, 46)
    for k in range(5): D.boite(img, 120 + k * 90, S + 200, 200 + k * 90, S + 280, (250, 250, 250), 4); D.texte(img, str(k + 1), 120 + k * 90, S + 200, 200 + k * 90, S + 280, TRAIT, 40)   # marelle
    D.ligne(img, (980, S + 200), (980, S - 200), (90, 90, 100), 14); D.boite(img, 900, S - 260, 1060, S - 180, (250, 250, 250), 5)   # panier
    D.affiche(img, 60, S - 330, 340, S - 200, gag(2), (250, 240, 200)); res["fenetre"] = (0, 0, W, 300)


def cantine(img, rng, res, gag, moment, allume):
    _int(img, "cantine", rng, "uni", (220, 224, 210), "damier")
    D.boite(img, 60, 300, 1020, 560, (40, 60, 50), 10, 6); D.texte(img, "MENU DU JOUR", 80, 320, 1000, 400, (250, 250, 230), 50)
    D.texte(img, gag(1), 80, 410, 1000, 540, (250, 240, 200), 40)
    D.boite(img, 0, 800, W, 860, (190, 195, 200), 5)                      # comptoir du self
    for x in range(60, W, 160): D.boite(img, x, 760, x + 120, 800, (210, 215, 220), 4, 6)
    D.boite(img, 100, S + 20, 980, S + 60, (200, 160, 110), 5)            # longue table
    for x in (180, 420, 660, 900): D.boite(img, x - 60, S - 10, x + 60, S + 20, (240, 120, 80), 4, 6)   # plateaux


def bureau_proviseur(img, rng, res, gag, moment, allume):
    _int(img, "bureau_proviseur", rng, "lambris", (150, 100, 70), "parquet")
    res["fenetre"] = (640, 300, 1000, 640); D.fenetre(img, *res["fenetre"], moment, rng, rideaux=(90, 60, 50))
    for k in range(3): D.cadre_tableau(img, 80 + k * 170, 320, 220 + k * 170, 460, rng, (60, 60, 70), "abstrait"); D.texte(img, "DIPLÔME", 92 + k * 170, 360, 208 + k * 170, 410, TRAIT, 20)
    D.ligne(img, (580, 260), (580, S - 20), (210, 180, 90), 8)
    for k, c_ in enumerate(((40, 70, 160), (250, 250, 250), (210, 40, 50))): D.poly(img, [(586, 280 + k * 50), (640, 288 + k * 50), (640, 338 + k * 50), (586, 330 + k * 50)], c_, 3)
    D.affiche(img, 80, 520, 520, 680, gag(1), (252, 248, 236))
    return D._avant(lambda a3: (D.comptoir_avant(a3, 1560, (120, 80, 50), (90, 60, 40)), D.boite(a3, 860, 1500, 960, 1566, (250, 250, 250), 5, 8)), 1560, [(850, 1490, W, 1566)])


def bibliotheque(img, rng, res, gag, moment, allume):
    _int(img, "bibliotheque", rng, "uni", (160, 120, 90), "parquet")
    for col in (0, 720):
        for k in range(5): D.etagere(img, col + 30, 360 + k * 160, col + 330, rng, True, False)
    D.boite(img, 380, 320, 700, 460, (40, 60, 50), 8, 6); D.texte(img, "SILENCE", 380, 320, 700, 460, (250, 250, 230), 54)
    D.affiche(img, 400, 520, 680, 680, gag(1), (250, 240, 200))
    for x in (300, 780): res["lampes"].append(D.suspension(img, x, 120, True))


def amphi(img, rng, res, gag, moment, allume):
    _int(img, "amphi", rng, "uni", (170, 130, 100), "parquet")
    D.boite(img, 100, 260, 980, 640, (40, 60, 50), 12, 6); D.texte(img, "∫ f(x) dx = ???", 140, 300, 940, 420, (250, 250, 230), 60)
    D.texte(img, gag(0), 140, 450, 940, 600, (250, 240, 200), 40)
    for k in range(4):                                                     # gradins
        y = 700 + k * 110; D.boite(img, 0, y, W, y + 26, (150, 110, 80), 4)
        _gens(img, 40, W - 40, y - 10, rng, 9, 0.6 + 0.05 * k)


# ------------------------------------------------------------------ ville
def arret_bus(img, rng, res, gag, moment, allume):
    _ext(img, moment, rng, (186, 186, 190), "trottoir", True)
    D.boite(img, 120, 420, 760, 460, (60, 70, 80), 5)                     # abribus
    for x in (140, 740): D.ligne(img, (x, 460), (x, S + 40), (60, 70, 80), 14)
    D.boite(img, 160, 470, 720, S - 40, (190, 220, 235), 4); res["vitrines"].append((160, 470, 720, S - 40))
    D.affiche(img, 220, 560, 660, 760, gag(0), (250, 240, 200))
    D.ligne(img, (900, S + 60), (900, 420), TRAIT, 14); D.rond(img, (900, 400), 70, (60, 120, 200), 6); D.texte(img, "BUS", 840, 360, 960, 440, (255, 255, 255), 40)
    DX.banc(img, 220, 660, S + 40); res["fenetre"] = (0, 0, W, S)


def metro(img, rng, res, gag, moment, allume):
    _int(img, "metro", rng, "uni", (150, 150, 156), "carrelage", False)
    for y in range(260, S - 260, 46):
        for x in range(0, W, 90): D.boite(img, x + 2, y + 2, x + 88, y + 44, (240, 242, 244), 2, 8)   # carrelage blanc biseauté
    D.boite(img, 0, S - 260, W, S - 40, (60, 120, 90), 6)                 # rame du métro
    for x in range(40, W, 220): D.boite(img, x, S - 230, x + 160, S - 100, (180, 210, 225), 5, 10)
    D.boite(img, 300, 200, 780, 280, (40, 60, 120), 6, 8); D.texte(img, gag(1), 300, 200, 780, 280, (255, 255, 255), 30)
    D.boite(img, 0, S - 40, W, S, (240, 210, 60), 0)                      # bande jaune du quai


def gare(img, rng, res, gag, moment, allume):
    _int(img, "gare", rng, "uni", (190, 186, 180), "carrelage", False)
    for x in range(0, W, 180): D.poly(img, [(x, 0), (x + 90, 160), (x + 180, 0)], (160, 170, 180), 4)   # verrière
    _ecran_infos(img, 140, 260, 940, 600, ["DÉPARTS", "TGV 8247  Paris   RETARD", "TER 512   Lyon    voie 3", "TGV 6612  Nice    ANNULÉ"])
    D.horloge(img, 540, 700, 60, (8, 47)); D.affiche(img, 80, 820, 400, 960, gag(1), (250, 240, 200))
    _gens(img, 600, 1040, S - 20, rng, 5, 0.8)


def aeroport(img, rng, res, gag, moment, allume):
    _int(img, "aeroport", rng, "uni", (220, 224, 230), "carrelage", False)
    D.ciel(img, 0, 200, W, 700, moment, rng, False)
    for x in range(0, W, 180): D.ligne(img, (x, 200), (x, 700), (120, 130, 140), 8)
    D.poly(img, [(600, 520), (900, 470), (920, 490), (640, 540)], (250, 250, 250), 5)   # avion au loin
    _ecran_infos(img, 100, 760, 980, 1000, ["EMBARQUEMENT", "AF 1234  New York  porte 42", "EZY 88   Ibiza     ANNULÉ"], (120, 220, 255))
    for k in range(3): D.boite(img, 820 + k * 60, S - 120, 870 + k * 60, S + 30, D._variante((200, 70, 70), rng, 40), 5, 8)   # valises


def parking(img, rng, res, gag, moment, allume):
    _ext(img, moment, rng, (110, 112, 118), "trottoir", True)
    D.boite(img, 0, 700, W, S, (210, 200, 180), 6); D.texte(img, "SUPERMARCHÉ", 200, 740, 880, 840, (220, 60, 50), 70)
    for x in range(0, W, 220): D.ligne(img, (x, S + 40), (x + 80, S + 600), (250, 250, 250), 8)
    D.affiche(img, 760, 880, 1040, 1020, gag(0), (60, 110, 200), (255, 255, 255)); res["fenetre"] = (0, 0, W, 700)


def fast_food(img, rng, res, gag, moment, allume):
    _int(img, "fast_food", rng, "uni", (230, 60, 50), "damier")
    D.boite(img, 60, 280, 1020, 560, (40, 30, 30), 8, 6)
    for k, (t, p_) in enumerate((("BURGER", "6,50"), ("FRITES", "3,20"), ("NUGGETS", "4,90"))): D.texte(img, f"{t}  {p_} €", 90, 300 + k * 80, 990, 370 + k * 80, (250, 220, 90), 40, False)
    D.affiche(img, 300, 600, 780, 740, gag(0), (250, 250, 240))
    return D._avant(lambda a3: (D.comptoir_avant(a3, 1560, (240, 70, 60), (250, 200, 60)), D.boite(a3, 860, 1470, 1040, 1566, (70, 70, 80), 6, 8)), 1560, [(850, 1460, W, 1566)])


def kebab(img, rng, res, gag, moment, allume):
    _int(img, "kebab", rng, "carrelage" if False else "uni", (200, 190, 180), "damier")
    D.boite(img, 70, 360, 270, 900, (180, 120, 70), 6, 60); D.ligne(img, (170, 300), (170, 960), (150, 150, 160), 10)   # broche
    D.neon(img, 340, 300, 1000, 440, gag(2), (255, 160, 60))
    D.boite(img, 340, 480, 1000, 820, (40, 30, 30), 8, 6)
    for k, t in enumerate(("KEBAB 7 €", "TACOS 8 €", "ASSIETTE 11 €")): D.texte(img, t, 360, 500 + k * 100, 980, 580 + k * 100, (250, 230, 120), 44, False)
    return D._avant(lambda a3: D.comptoir_avant(a3, 1560, (200, 200, 205), (180, 120, 70)), 1560, [])


def cinema(img, rng, res, gag, moment, allume):
    _int(img, "cinema", rng, "uni", (110, 30, 40), "moquette", False)
    D.boite(img, 60, 160, 1020, 720, (230, 232, 240), 10); D.texte(img, gag(2), 60, 360, 1020, 520, (60, 60, 80), 54)
    for k in range(3):                                                     # rangées de fauteuils rouges
        y = 900 + k * 130
        for x in range(0, W, 120): D.boite(img, x + 10, y, x + 110, y + 110, (170, 30, 40), 5, 20)
    res["ecrans"].append((60, 160, 1020, 720))


# ------------------------------------------------------------------ sorties
def plage(img, rng, res, gag, moment, allume):
    D.ciel(img, 0, 0, W, 800, moment, rng, False)
    D.boite(img, 0, 800, W, S, (60, 150, 210), 0)                         # la mer
    for y in range(840, S, 70): D.ligne(img, (60 + (y % 140), y), (260 + (y % 140), y), (230, 240, 250), 5)
    D.sol(img, D._variante((240, 214, 150), rng, 8), "moquette")
    D.ligne(img, (860, S + 300), (860, S - 200), (240, 240, 240), 10); D.poly(img, [(700, S - 200), (860, S - 330), (1020, S - 200)], (230, 70, 70), 6)   # parasol
    D.boite(img, 120, S + 160, 420, S + 230, (80, 160, 220), 5, 8)        # serviette
    D.affiche(img, 360, S - 330, 700, S - 200, gag(0), (250, 240, 200)); res["fenetre"] = (0, 0, W, S)


def piscine(img, rng, res, gag, moment, allume):
    _int(img, "piscine", rng, "uni", (230, 236, 240), "carrelage", False)
    D.boite(img, 0, 800, W, S, (70, 170, 230), 0)
    for x in (270, 540, 810): D.ligne(img, (x, 800), (x, S), (240, 60, 60), 8)   # lignes d'eau
    D.boite(img, 820, 640, 1040, 680, (250, 250, 250), 5); D.ligne(img, (1000, 680), (1000, 800), (180, 185, 195), 12)   # plongeoir
    D.affiche(img, 80, 320, 520, 460, gag(0), (250, 250, 245)); D.horloge(img, 760, 380, 60)


def parc(img, rng, res, gag, moment, allume):
    _ext(img, moment, rng)
    _arbre(img, 120, S - 40, 1.2); _arbre(img, 960, S - 60, 1.0); _arbre(img, 560, S - 160, 0.7)
    cv2.ellipse(img, (540, S + 260), (260, 60), 0, 0, 360, (90, 160, 210), -1, AA); cv2.ellipse(img, (540, S + 260), (260, 60), 0, 0, 360, TRAIT, 5, AA)   # bassin
    DX.banc(img, 680, 1000, S + 80); D.affiche(img, 300, S - 330, 640, S - 200, gag(0), (250, 240, 200)); res["fenetre"] = (0, 0, W, S)


def camping(img, rng, res, gag, moment, allume):
    _ext(img, moment, rng)
    _arbre(img, 100, S - 40, 1.0); _arbre(img, 990, S - 40, 0.9)
    D.poly(img, [(560, S + 100), (760, S - 160), (960, S + 100)], D._variante((240, 140, 40), rng), 7)   # tente
    D.poly(img, [(720, S + 100), (760, S - 60), (800, S + 100)], (60, 50, 50), 4)
    for k in range(5): D.ligne(img, (240 + k * 14, S + 200), (300 - k * 14, S + 160), (120, 80, 50), 10)   # feu de camp
    D.poly(img, [(250, S + 170), (275, S + 100), (300, S + 170)], (250, 160, 40), 3)
    D.affiche(img, 200, S - 330, 520, S - 200, gag(0), (60, 110, 200), (255, 255, 255)); res["fenetre"] = (0, 0, W, S)


def montagne(img, rng, res, gag, moment, allume):
    D.ciel(img, 0, 0, W, S, moment, rng, False)
    for x0, h_ in ((-200, 700), (300, 900), (700, 650)):
        D.poly(img, [(x0, S), (x0 + 350, S - h_), (x0 + 700, S)], (150, 160, 180), 5)
        D.poly(img, [(x0 + 270, S - h_ + 160), (x0 + 350, S - h_), (x0 + 430, S - h_ + 160)], (250, 250, 252), 4)
    D.sol(img, (245, 247, 250), "moquette")
    D.boite(img, 60, S - 200, 360, S + 40, (150, 100, 60), 6); D.poly(img, [(40, S - 200), (210, S - 330), (380, S - 200)], (200, 210, 220), 6)   # chalet
    D.affiche(img, 620, S - 330, 1000, S - 200, gag(0), (250, 240, 200)); res["fenetre"] = (0, 0, W, S)


def stade(img, rng, res, gag, moment, allume):
    D.ciel(img, 0, 0, W, 420, moment, rng, False)
    D.boite(img, 0, 300, W, 760, (90, 100, 120), 0)                       # tribunes et foule
    for k in range(3): _gens(img, 0, W, 420 + k * 120, rng, 14, 0.7)
    for x in (80, 1000): D.ligne(img, (x, 300), (x, 80), (60, 64, 72), 12); D.boite(img, x - 60, 40, x + 60, 100, (250, 250, 220), 5)   # projecteurs
    D.sol(img, D._variante((70, 160, 70), rng, 6), "moquette", 760)
    D.ligne(img, (0, 1000), (W, 1000), (250, 250, 250), 6); cv2.ellipse(img, (540, 1000), (180, 60), 0, 0, 360, (250, 250, 250), 5, AA)
    _ecran_infos(img, 360, 140, 720, 280, [gag(1)], (250, 220, 90))


def concert(img, rng, res, gag, moment, allume):
    img[:] = D._variante(COULEURS_MUR["concert"], rng, 6)
    for k, c_ in enumerate(((255, 80, 160), (80, 200, 255), (255, 220, 80))):   # faisceaux de lumière
        D.poly(img, [(180 + k * 360, 0), (60 + k * 360, 900), (300 + k * 360, 900)], tuple(int(v * 0.5) for v in c_), 0)
    D.boite(img, 0, 900, W, 960, (40, 40, 46), 5)                          # scène
    for x in (60, 900): D.boite(img, x, 620, x + 120, 900, (30, 30, 34), 5, 6); D.rond(img, (x + 60, 700), 40, (80, 80, 90), 5)   # enceintes
    D.neon(img, 260, 160, 820, 300, gag(0), (255, 90, 170)); D.sol(img, (40, 36, 50), "moquette")
    _gens(img, 0, W, S + 300, rng, 10, 1.0)


def boite_nuit(img, rng, res, gag, moment, allume):
    img[:] = D._variante(COULEURS_MUR["boite_nuit"], rng, 6)
    D.rond(img, (540, 160), 80, (200, 205, 215), 5)                       # boule à facettes
    for k in range(12): D.ligne(img, (540, 160), (540 + 520 * math.cos(k * 0.52), 160 + 520 * math.sin(k * 0.52) + 200), ((255, 80, 160), (80, 200, 255), (255, 220, 80))[k % 3], 3)
    D.boite(img, 300, 620, 780, 820, (30, 30, 40), 6, 8); D.texte(img, "DJ", 300, 620, 780, 820, (120, 255, 200), 80)
    D.neon(img, 200, 360, 880, 500, gag(1), (255, 90, 170))
    D.sol(img, (40, 30, 60), "damier"); res["neons"].append((200, 360, 880, 500))


# ------------------------------------------------------------------ santé et services
def hopital(img, rng, res, gag, moment, allume):
    _int(img, "hopital", rng, "uni", (210, 220, 225), "carrelage")
    res["fenetre"] = (640, 300, 1000, 640); D.fenetre(img, *res["fenetre"], moment, rng, cadre=(240, 244, 248))
    D.lit(img, 60, 620, S + 140, (210, 230, 240))
    D.ligne(img, (700, S + 40), (700, 520), (180, 185, 195), 8); D.boite(img, 660, 520, 740, 640, (200, 230, 245), 5, 10)   # perfusion
    D.boite(img, 800, 700, 1020, 880, (30, 30, 36), 6, 8); D.ligne(img, (820, 800), (870, 800), (80, 255, 120), 4); D.ligne(img, (870, 800), (890, 740), (80, 255, 120), 4); D.ligne(img, (890, 740), (910, 840), (80, 255, 120), 4); D.ligne(img, (910, 840), (1000, 800), (80, 255, 120), 4)
    D.affiche(img, 60, 320, 560, 460, gag(0), (252, 252, 248))


def urgences(img, rng, res, gag, moment, allume):
    _int(img, "urgences", rng, "uni", (200, 210, 215), "carrelage")
    D.boite(img, 140, 220, 940, 320, (220, 40, 40), 6, 8); D.texte(img, "URGENCES", 140, 220, 940, 320, (255, 255, 255), 64)
    _ecran_infos(img, 600, 400, 1000, 600, ["TICKET", "N° 12"], (255, 80, 80))
    D.affiche(img, 80, 400, 520, 560, gag(0), (252, 252, 248))
    for x in range(60, W, 140): DX.chaise(img, x + 60, S + 40, (60, 120, 200))


def pharmacie(img, rng, res, gag, moment, allume):
    _int(img, "pharmacie", rng, "uni", (230, 236, 232), "carrelage")
    for k in range(4):
        y = 380 + k * 150; D.boite(img, 40, y + 110, 1040, y + 126, (200, 200, 205), 4)
        for x in range(60, 1020, 70): D.boite(img, x, y + 40, x + 50, y + 110, D._variante(((240, 240, 240), (120, 200, 140), (240, 120, 120), (120, 160, 240))[(x // 70 + k) % 4], rng, 10), 3, 4)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (0, 0)): D.boite(img, 500 + dx * 40, 220 + dy * 40, 540 + dx * 40, 260 + dy * 40, (60, 180, 90), 0)   # croix verte
    D.affiche(img, 620, 200, 1020, 340, gag(1), (250, 250, 240))
    return D._avant(lambda a3: D.comptoir_avant(a3, 1560, (240, 244, 240), (60, 180, 90)), 1560, [])


def commissariat(img, rng, res, gag, moment, allume):
    _int(img, "commissariat", rng, "uni", (190, 190, 196), "carrelage")
    D.boite(img, 140, 220, 940, 320, (40, 55, 100), 6, 8); D.texte(img, "POLICE", 140, 220, 940, 320, (255, 255, 255), 64)
    for k in range(3): D.affiche(img, 100 + k * 300, 400, 320 + k * 300, 640, ("RECHERCHÉ", "ATTENTION", gag(1))[k], (250, 240, 200), dessin="portrait" if False else None)
    return D._avant(lambda a3: D.comptoir_avant(a3, 1560, (120, 130, 150), (40, 55, 100)), 1560, [])


def prison(img, rng, res, gag, moment, allume):
    _int(img, "prison", rng, "briques", (150, 150, 152), "carrelage", False)
    D.boite(img, 700, 260, 900, 420, (60, 70, 80), 6); [D.ligne(img, (720 + k * 40, 260), (720 + k * 40, 420), (40, 40, 46), 8) for k in range(5)]   # lucarne
    D.boite(img, 60, S - 300, 460, S - 240, (130, 130, 140), 5); D.boite(img, 60, S - 100, 460, S - 40, (130, 130, 140), 5)   # lits superposés
    D.affiche(img, 60, 320, 460, 460, gag(0), (240, 240, 230))
    D.boite(img, 600, 300, 1040, S + 10, (90, 94, 100), 8)                # porte de cellule à barreaux (au fond, jamais devant un visage)
    for x in range(630, 1030, 60): D.ligne(img, (x, 310), (x, S), (50, 54, 60), 14)
    D.ligne(img, (600, 700), (1040, 700), (50, 54, 60), 14)


def banque(img, rng, res, gag, moment, allume):
    _int(img, "banque", rng, "lambris", (200, 196, 190), "carrelage")
    D.rond(img, (880, 520), 160, (170, 175, 185), 10); D.rond(img, (880, 520), 40, (120, 125, 135), 6)   # coffre-fort
    D.boite(img, 120, 240, 620, 340, (40, 80, 60), 6, 8); D.texte(img, "BANQUE", 120, 240, 620, 340, (250, 220, 90), 60)
    D.affiche(img, 120, 400, 620, 560, gag(0), (252, 248, 236))
    return D._avant(lambda a3: D.comptoir_avant(a3, 1560, (200, 190, 170), (40, 80, 60)), 1560, [])


def poste(img, rng, res, gag, moment, allume):
    _int(img, "poste", rng, "uni", (220, 220, 214), "carrelage")
    D.boite(img, 140, 220, 940, 320, (40, 60, 150), 6, 8); D.texte(img, "LA POSTE", 140, 220, 940, 320, (250, 210, 60), 64)
    for k in range(4): D.boite(img, 80 + k * 110, S - 180 - k * 40, 180 + k * 110, S + 40, (210, 170, 120), 5)   # colis empilés
    D.affiche(img, 560, 400, 1000, 560, gag(0), (250, 250, 240))
    return D._avant(lambda a3: D.comptoir_avant(a3, 1560, (230, 230, 220), (250, 210, 60)), 1560, [])


# ------------------------------------------------------------------ autres
def mariage(img, rng, res, gag, moment, allume):
    _int(img, "mariage", rng, "uni", (220, 200, 180), "parquet")
    cv2.ellipse(img, (540, 700), (360, 420), 0, 180, 360, (240, 160, 190), 40, AA)   # arche de fleurs
    for a in range(180, 361, 15): D.rond(img, (540 + 360 * math.cos(math.radians(a)), 700 + 420 * math.sin(math.radians(a))), 26, ((250, 250, 250), (240, 120, 160), (250, 210, 220))[a % 3], 4)
    D.boite(img, 820, S - 300, 980, S + 40, (250, 250, 248), 6); D.boite(img, 850, S - 400, 950, S - 300, (250, 250, 248), 6); D.rond(img, (900, S - 420), 20, (240, 120, 160), 4)   # gâteau
    D.affiche(img, 80, 320, 400, 460, gag(1), (252, 248, 240)); DX.lustre(img, 540, 90, True)


def eglise(img, rng, res, gag, moment, allume):
    _int(img, "eglise", rng, "uni", (170, 150, 120), "carrelage")
    for x in (120, 760):                                                   # vitraux
        D.poly(img, [(x, 760), (x, 380), (x + 100, 260), (x + 200, 380), (x + 200, 760)], (60, 60, 70), 6)
        for k, c_ in enumerate(((220, 60, 60), (60, 120, 220), (240, 200, 60), (80, 170, 100))): D.boite(img, x + 20 + (k % 2) * 80, 420 + (k // 2) * 160, x + 100 + (k % 2) * 80, 560 + (k // 2) * 160, c_, 3)
    D.boite(img, 440, 300, 640, 760, (190, 160, 110), 6); D.texte(img, gag(1), 440, 480, 640, 600, TRAIT, 30)
    for k in range(3): D.boite(img, 0, S + 60 + k * 120, 380, S + 110 + k * 120, (140, 90, 60), 5); D.boite(img, 700, S + 60 + k * 120, W, S + 110 + k * 120, (140, 90, 60), 5)   # bancs


def plateau_tele(img, rng, res, gag, moment, allume):
    img[:] = D._variante(COULEURS_MUR["plateau_tele"], rng, 6)
    for k in range(3): D.ecran(img, 80 + k * 330, 260, 330 + k * 330, 460, "bleu", rng)
    D.boite(img, 320, 540, 760, 620, (220, 40, 40), 6, 8); D.texte(img, gag(0), 320, 540, 760, 620, (255, 255, 255), 40)
    for x in (60, 1020): D.ligne(img, (x, 0), (x, 200), (200, 200, 210), 8); D.boite(img, x - 50, 200, x + 50, 260, (250, 250, 220), 5)
    D.sol(img, (60, 70, 110), "carrelage")
    return D._avant(lambda a3: D.comptoir_avant(a3, 1570, (230, 230, 240), (220, 40, 40)), 1570, [])


def studio_radio(img, rng, res, gag, moment, allume):
    _int(img, "studio_radio", rng, "uni", (60, 60, 66), "moquette", False)
    for y in range(260, S - 100, 80):
        for x in range(0, W, 80): D.boite(img, x + 4, y + 4, x + 76, y + 76, (80, 80, 90), 2, 10)   # mousse acoustique
    D.boite(img, 360, 220, 720, 320, (40, 30, 30), 6, 8); D.texte(img, "ON AIR", 360, 220, 720, 320, (255, 60, 60), 64)
    D.affiche(img, 760, 380, 1040, 520, gag(1), (250, 250, 240))
    def avant(a3):
        D.comptoir_avant(a3, 1560, (50, 50, 56), (200, 200, 210))
        for x in (220, 860): D.ligne(a3, (x, 1560), (x, 1420), (40, 40, 46), 10); D.rond(a3, (x, 1400), 36, (70, 70, 80), 5)   # micros
    return D._avant(avant, 1380, [(150, 1340, 300, 1566), (790, 1340, 940, 1566)])


def salle_jeux(img, rng, res, gag, moment, allume):
    img[:] = D._variante(COULEURS_MUR["salle_jeux"], rng, 6)
    D.boite(img, 180, 260, 900, 700, (20, 20, 26), 10, 8); D.boite(img, 210, 290, 870, 670, (60, 200, 120), 0)   # grand écran
    D.texte(img, gag(0), 210, 400, 870, 560, (255, 255, 255), 70); res["ecrans"].append((210, 290, 870, 670))
    D.neon(img, 120, 140, 960, 230, gag(2), (120, 255, 200)); D.sol(img, (50, 40, 80), "moquette")
    D.boite(img, 380, S - 60, 700, S + 40, (220, 60, 60), 6, 30)           # pouf gamer


DESSINS = {k: globals()[k] for k in LIEUX}

# ------------------------------------------------------------------ inscription dans le catalogue des décors dessinés
D.LIEUX = tuple(dict.fromkeys(D.LIEUX + LIEUX)); D.GAGS.update(GAGS); D.COULEURS_MUR.update(COULEURS_MUR)
DX.NOUVEAUX.update(DESSINS)
