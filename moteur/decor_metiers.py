"""Décors des métiers (idée 17 de l'auteur), dessinés comme les autres lieux (trait noir, aplats, gags écrits lisibles) :
caserne de pompiers, garage, boulangerie, ferme, tribunal, laboratoire, cockpit d'avion, espace (station spatiale), salon de coiffure.
Chaque lieu : fond + premier plan éventuel (comptoir, établi, tableau de bord) qui glisse devant les personnages (parallaxe).
Le lieu est choisi d'après les mots de l'audio (decor_dessin.lieu_de) ou d'après le métier reconnu (studio.bible, METIER_LIEU)."""
import numpy as np, cv2

TRAIT = (26, 22, 30)
AA = cv2.LINE_AA
S = 1210                                                                   # = decor_dessin.SOL (ligne mur / sol)

GAGS = {
    "caserne": ["Pompiers : on arrive (après le café)", "Jours sans incendie : 0", "Ne pas toucher au camion (Kévin !)"],
    "garage": ["Devis gratuit (la réparation non)", "Ici on répare tout sauf les cœurs", "Vidange express : 3 jours"],
    "boulangerie": ["Pain du jour : celui d'hier", "Croissant ou pain au chocolat ? Chocolatine.", "Baguette tradition : 1,30 €"],
    "ferme": ["Œufs frais (demandez aux poules)", "Attention : chien gentil, oie méchante", "Ferme des Trois Vaches (il en reste deux)"],
    "tribunal": ["Silence (même vous, Maître)", "La loi est la même pour tous (sauf le lundi)", "Pas de selfies avec le juge"],
    "labo": ["Ne pas boire les échantillons", "Expérience n° 47 (les 46 autres ont explosé)", "Danger : stagiaire"],
    "cockpit": ["Ne pas toucher au gros bouton rouge", "Pilote automatique : ON (normalement)", "Attachez vos ceintures"],
    "espace": ["Pas de Wi-Fi au-delà de la Lune", "Gravité : en option", "Prochaine station : Mars (2 ans)"],
    "coiffeur": ["Coupe + brushing + potins : 25 €", "On rattrape tout (presque)", "Hair Mess, salon de coiffure"],
}
COULEURS_MUR = {"caserne": (196, 70, 60), "garage": (150, 160, 170), "boulangerie": (246, 226, 190), "ferme": (176, 90, 70),
                "tribunal": (196, 160, 120), "labo": (230, 240, 244), "cockpit": (70, 76, 90), "espace": (20, 24, 48), "coiffeur": (246, 214, 222)}
LIEUX = tuple(GAGS)
METIER_LIEU = {"pompier": "caserne", "mecanicien": "garage", "boulanger": "boulangerie", "agriculteur": "ferme", "juge": "tribunal",
               "avocat": "tribunal", "scientifique": "labo", "pilote": "cockpit", "hotesse": "cockpit", "astronaute": "espace", "coiffeur": "coiffeur"}
REGLES = [("espace", r"dans l'espace|cosmos|station spatiale|en orbite|apesanteur|astronautes?|fus[ée]es?\b|space ?station|outer space|spaceship"),
          ("cockpit", r"cockpit|poste de pilotage|commandant de bord|copilote|pilote de ligne|airplane cockpit"),
          ("caserne", r"caserne|fire station|firehouse|camion de pompiers?|grande [ée]chelle|sapeurs?[- ]pompiers?"),
          ("garage", r"\bgarage\b|garagiste|m[ée]canicien|car repair|vidange|pneus? crev|sous le capot"),
          ("boulangerie", r"boulangerie|boulang[eè]re?s?\b|bakery|baguettes? de pain|pains? au chocolat|chocolatines?|viennoiser"),
          ("ferme", r"\bfarm\b|fermi[eè]re?s?\b|agricult|tracteurs?|vaches?\b|cochons?\b|moutons?\b|botte de foin|grange|\bbarn\b"),
          ("tribunal", r"tribunal|courtroom|(le|la|monsieur le|madame la) juge\b|avocate?s?\b|plaidoirie|verdict|votre honneur"),
          ("labo", r"laboratoire|\blabo\b|laboratory|[ée]prouvettes?|microscope|formule secr[eè]te"),
          ("coiffeur", r"coiffeur|coiffeuse|salon de coiffure|hair salon|barber|barbier|coupe de cheveux|brushing")]


import decor_dessin as D                                                   # (après les données : import croisé sans souci)


def _sol_mur(img, lieu, rng, motif_mur="uni", c_sol=(190, 190, 196), m_sol="carrelage", plinthe=True, c_mur=None):
    D.mur(img, D._variante(c_mur or COULEURS_MUR[lieu], rng, 8), motif_mur, rng); D.sol(img, D._variante(c_sol, rng, 6), m_sol)
    if plinthe: D.plinthe(img)


def gyrophare(img, x, y, c=(230, 40, 40), r=26):
    D.boite(img, x - r, y - r, x + r, y + r // 2, c, 5, r); D.boite(img, x - r - 10, y + r // 2, x + r + 10, y + r // 2 + 14, (60, 60, 66), 4)


# ------------------------------------------------------------------ lieux
def caserne(img, rng, res, gag, moment, allume):
    """Caserne : mur de briques rouges, grande porte de garage ouverte sur le camion, casques et vestes accrochés, mât de descente."""
    _sol_mur(img, "caserne", rng, "briques", (150, 150, 156), "carrelage", False)
    D.boite(img, 330, 300, 1000, S, (70, 70, 78), 10)                     # grande porte ouverte : le nez du camion rouge
    for k in range(6): D.ligne(img, (340, 330 + k * 36), (990, 330 + k * 36), (110, 110, 118), 6)   # rideau métallique relevé
    D.boite(img, 380, 560, 960, S - 10, (210, 40, 40), 8, 14)              # cabine du camion vue de face
    D.boite(img, 430, 600, 910, 790, (160, 200, 225), 7, 10); D.ligne(img, (670, 600), (670, 790), TRAIT, 6)
    for x in (470, 870): cv2.circle(img, (x, 900), 40, (255, 240, 170), -1, AA); cv2.circle(img, (x, 900), 40, TRAIT, 5, AA)
    D.boite(img, 560, 860, 780, 960, (230, 230, 232), 5, 6)
    for k in range(5): D.ligne(img, (575 + k * 50, 870), (575 + k * 50, 950), (90, 90, 98), 6)
    D.texte(img, "18", 600, 980, 740, 1060, (255, 255, 255), 64)
    gyrophare(img, 520, 540, (40, 110, 230)); gyrophare(img, 820, 540, (40, 110, 230))
    D.boite(img, 380, 230, 960, 290, (250, 250, 248), 6, 8); D.texte(img, "SAPEURS-POMPIERS", 390, 234, 950, 286, (200, 30, 30), 44)
    for k in range(3):                                                     # vestiaire : casques et vestes
        x = 60 + k * 90; D.boite(img, x, 520, x + 70, 780, (200, 70, 40), 5, 10); D.ligne(img, (x + 4, 640), (x + 66, 640), (250, 220, 60), 9)
        cv2.ellipse(img, (x + 35, 500), (40, 28), 0, 180, 360, (205, 35, 35), -1, AA); cv2.ellipse(img, (x + 35, 500), (40, 28), 0, 180, 360, TRAIT, 5, AA)
        D.boite(img, x - 8, 496, x + 78, 510, (205, 35, 35), 4, 4)
    D.ligne(img, (240, 0), (240, S + 60), (190, 190, 200), 20); D.ligne(img, (240, 0), (240, S + 60), TRAIT, 4)   # mât de descente
    D.affiche(img, 40, 830, 300, 1060, gag(0), (250, 240, 200))
    import decor_details as DX
    DX.extincteur(img, 300, S + 40)
    for k in range(3): cv2.ellipse(img, (110, S + 140 + k * 26), (90, 20), 0, 0, 360, (200, 60, 50), 10, AA)   # tuyau enroulé
    res["lampes"].append(D.suspension(img, 660, 120, allume))


def garage(img, rng, res, gag, moment, allume):
    """Garage : voiture sur le pont élévateur, panneau d'outils, pneus empilés, bidons d'huile, taches au sol, établi devant."""
    _sol_mur(img, "garage", rng, "uni", (120, 124, 130), "carrelage", False)
    D.boite(img, 40, 260, 460, 700, (210, 180, 130), 6)                    # panneau d'outils
    for j in range(3):
        for i in range(5):
            x, y = 80 + i * 76, 320 + j * 130
            col = ((200, 50, 50), (60, 110, 200), (90, 90, 100))[(i + j) % 3]
            D.ligne(img, (x, y), (x, y + 90), TRAIT, 12); D.ligne(img, (x, y), (x, y + 90), col, 6)
            cv2.circle(img, (x, y), 14, (160, 160, 170), -1, AA); cv2.circle(img, (x, y), 14, TRAIT, 4, AA)
    import vehicules as VH
    v = VH.voiture(D._variante((60, 100, 190), rng), 1, 540)              # voiture levée sur le pont
    y0 = 560; x0 = 500; h_, w_ = v.shape[:2]
    zone = img[y0:y0 + h_, x0:x0 + w_]; a = v[:zone.shape[0], :zone.shape[1], 3:4] / 255.0
    zone[:] = (zone * (1 - a) + v[:zone.shape[0], :zone.shape[1], :3] * a).astype(np.uint8)
    for x in (560, 960): D.boite(img, x, y0 + h_ - 20, x + 26, S + 20, (240, 200, 40), 5)   # bras du pont élévateur
    D.boite(img, 520, y0 + h_ - 30, 1000, y0 + h_ - 6, (240, 200, 40), 5)
    for k in range(4):                                                     # pneus empilés
        cv2.ellipse(img, (110, S + 40 - k * 60), (80, 34), 0, 0, 360, (35, 35, 40), -1, AA); cv2.ellipse(img, (110, S + 40 - k * 60), (80, 34), 0, 0, 360, TRAIT, 4, AA)
        cv2.ellipse(img, (110, S + 40 - k * 60), (36, 14), 0, 0, 360, (90, 90, 96), -1, AA)
    for k, c_ in enumerate(((230, 60, 50), (60, 150, 80), (250, 190, 40))): D.boite(img, 240 + k * 70, S - 60, 300 + k * 70, S + 40, c_, 5, 6); D.texte(img, "OIL", 240 + k * 70, S - 40, 300 + k * 70, S, (255, 255, 255), 18)
    for _ in range(4): cv2.ellipse(img, (int(rng.uniform(300, 900)), int(rng.uniform(S + 60, S + 250))), (int(rng.uniform(30, 60)), 12), 0, 0, 360, (80, 84, 90), -1, AA)
    D.affiche(img, 520, 280, 1000, 460, gag(0), (250, 220, 80))
    av = D._avant(lambda a3: (D.comptoir_avant(a3, 1560, (150, 110, 70), (90, 90, 100)), D.boite(a3, 60, 1500, 200, 1560, (200, 40, 40), 5, 6),
                              D.ligne(a3, (900, 1540), (1030, 1500), (160, 160, 170), 12)), 1560, [(0, 1480, 220, 1566), (880, 1480, D.W, 1566)])
    res["lampes"].append(D.suspension(img, 760, 110, True))
    return av


def boulangerie(img, rng, res, gag, moment, allume):
    """Boulangerie : étagères de pains et baguettes, ardoise des prix, vitrine de gâteaux au premier plan."""
    _sol_mur(img, "boulangerie", rng, "uni", (200, 160, 120), "damier")
    for k in range(3):                                                     # étagères de pains
        y = 420 + k * 170; D.boite(img, 60, y, 640, y + 18, (150, 100, 60), 5)
        for i in range(7):
            x = 80 + i * 80
            if (i + k) % 2: D.boite(img, x, y - 90, x + 26, y, (210, 150, 70), 4, 10); D.boite(img, x + 30, y - 84, x + 56, y, (200, 140, 60), 4, 10)   # baguettes debout
            else: cv2.ellipse(img, (x + 30, y - 30), (36, 28), 0, 0, 360, (196, 130, 60), -1, AA); cv2.ellipse(img, (x + 30, y - 30), (36, 28), 0, 0, 360, TRAIT, 4, AA); D.ligne(img, (x + 14, y - 40), (x + 44, y - 22), (240, 200, 130), 4)
    D.boite(img, 700, 300, 1030, 760, (40, 44, 48), 12, 6); D.texte(img, "NOS PAINS", 720, 320, 1010, 390, (250, 240, 200), 44)
    for k, t in enumerate(("Baguette  1,30", "Croissant  1,20", "Chocolatine  1,40", "Éclair  2,80")): D.texte(img, t, 720, 410 + k * 70, 1010, 470 + k * 70, (250, 240, 200), 30, False)
    D.affiche(img, 700, 800, 1030, 980, gag(0), (252, 248, 236))
    res["fenetre"] = None
    av = D._avant(lambda a3: (D.comptoir_avant(a3, 1530, (240, 236, 228), (180, 130, 80)), D.boite(a3, 40, 1450, 420, 1540, (200, 225, 240), 5, 6),
                              [cv2.circle(a3, (90 + 64 * k, 1505), 24, ((230, 120, 150, 255), (140, 90, 60, 255), (250, 230, 200, 255))[k % 3], -1, AA) for k in range(5)],
                              D.boite(a3, 860, 1440, 1050, 1536, (70, 70, 80), 6, 8)), 1530, [(30, 1430, 430, 1546), (850, 1430, D.W, 1546)])
    return av


def ferme(img, rng, res, gag, moment, allume):
    """Ferme : grange rouge, prairie, clôture, botte de foin, poules, tracteur au loin, ciel de l'heure."""
    D.ciel(img, 0, 0, D.W, S, moment, rng, False)
    cv2.ellipse(img, (300, S), (700, 160), 0, 180, 360, (130, 190, 100), -1, AA)   # collines
    cv2.ellipse(img, (900, S), (600, 120), 0, 180, 360, (110, 170, 90), -1, AA)
    gr = [(560, S), (560, 600), (780, 420), (1000, 600), (1000, S)]          # grange
    D.poly(img, gr, D._variante((176, 60, 50), rng), 8)
    D.poly(img, [(540, 610), (780, 400), (1020, 610)], (240, 240, 236), 0); D.poly(img, [(560, 600), (780, 420), (1000, 600)], D._variante((176, 60, 50), rng), 8)
    D.boite(img, 690, 850, 870, S, (120, 60, 40), 6)
    D.ligne(img, (690, 850), (870, S), (240, 240, 236), 10); D.ligne(img, (870, 850), (690, S), (240, 240, 236), 10)
    D.boite(img, 740, 620, 820, 700, (250, 230, 150), 5)
    D.texte(img, gag(2), 570, 760, 990, 830, (255, 255, 255), 30)
    D.sol(img, D._variante((140, 190, 90), rng, 8), "moquette")
    for x in range(0, 540, 90):                                            # clôture en bois
        D.boite(img, x + 10, S - 120, x + 30, S + 40, (190, 140, 90), 4)
    for y in (S - 90, S - 30): D.boite(img, 0, y, 540, y + 16, (190, 140, 90), 4)
    D.boite(img, 60, S + 60, 300, S + 200, (240, 200, 90), 6, 20)            # botte de foin
    for k in range(5): D.ligne(img, (80 + k * 44, S + 70), (90 + k * 44, S + 190), (210, 170, 60), 4)
    for k in range(3):                                                     # poules
        x, y = 360 + k * 70, S + 230 + (k % 2) * 30
        cv2.ellipse(img, (x, y), (30, 22), 0, 0, 360, (250, 250, 246), -1, AA); cv2.ellipse(img, (x, y), (30, 22), 0, 0, 360, TRAIT, 4, AA)
        cv2.circle(img, (x + 24, y - 20), 13, (250, 250, 246), -1, AA); cv2.circle(img, (x + 24, y - 20), 13, TRAIT, 4, AA)
        cv2.circle(img, (x + 24, y - 34), 6, (220, 40, 40), -1, AA); D.poly(img, [(x + 36, y - 22), (x + 48, y - 18), (x + 36, y - 14)], (250, 180, 40), 2)
    res["fenetre"] = (0, 0, D.W, S)


def tribunal(img, rng, res, gag, moment, allume):
    """Tribunal : boiseries, estrade du juge, balance de la justice, drapeau, barre des témoins au premier plan."""
    _sol_mur(img, "tribunal", rng, "lambris", (150, 100, 70), "parquet", False)
    D.boite(img, 240, 260, 840, 560, (120, 70, 40), 8, 6)                  # grand panneau derrière le juge
    cv2.circle(img, (540, 400), 100, (230, 190, 90), -1, AA); cv2.circle(img, (540, 400), 100, TRAIT, 6, AA)   # balance de la justice
    D.ligne(img, (540, 330), (540, 470), TRAIT, 8); D.ligne(img, (470, 360), (610, 360), TRAIT, 8)
    for x in (470, 610): cv2.ellipse(img, (x, 410), (36, 18), 0, 0, 180, (250, 240, 200), -1, AA); cv2.ellipse(img, (x, 410), (36, 18), 0, 0, 180, TRAIT, 4, AA); D.ligne(img, (x, 360), (x, 410), TRAIT, 3)
    D.boite(img, 160, 700, 920, S - 40, (140, 84, 50), 8, 6)                # estrade du juge
    for k in range(4): D.boite(img, 190 + k * 180, 740, 330 + k * 180, S - 80, (160, 100, 60), 4, 4)
    D.boite(img, 440, 600, 640, 700, (90, 50, 30), 6, 10)                   # fauteuil du juge
    D.boite(img, 600, 650, 680, 690, (120, 70, 40), 4, 6); D.ligne(img, (620, 650), (660, 620), TRAIT, 10)   # marteau
    D.texte(img, gag(0), 260, 590, 430, 690, (250, 240, 210), 22)
    D.ligne(img, (980, 220), (980, S - 20), (210, 180, 90), 10)            # drapeau
    for k, c_ in enumerate(((40, 70, 160), (250, 250, 250), (210, 40, 50))): D.poly(img, [(986, 240 + k * 70), (1060, 250 + k * 70), (1060, 320 + k * 70), (986, 310 + k * 70)], c_, 3)
    av = D._avant(lambda a3: (D.comptoir_avant(a3, 1580, (130, 80, 50), (90, 50, 30)), D.boite(a3, 380, 1470, 420, 1586, (90, 50, 30), 4)), 1580, [])
    res["lampes"] += [D.suspension(img, 200, 110, True), D.suspension(img, 880, 110, True)]
    return av


def labo(img, rng, res, gag, moment, allume):
    """Laboratoire : paillasse blanche, éprouvettes colorées qui fument, microscope, tableau de formules, hotte."""
    _sol_mur(img, "labo", rng, "uni", (220, 228, 232), "carrelage")
    D.boite(img, 80, 300, 640, 680, (40, 70, 60), 12, 6)                    # tableau de formules
    for k, f in enumerate(("E = mc² (+ café)", "H2O + ? = oups", "x + y = ça va exploser")): D.texte(img, f, 110, 330 + k * 110, 610, 420 + k * 110, (240, 240, 230), 38, False)
    D.boite(img, 720, 240, 1030, 520, (200, 205, 212), 7, 6); D.boite(img, 740, 520, 1010, 600, (160, 200, 225), 5)   # hotte
    D.texte(img, "DANGER", 740, 260, 1010, 330, (220, 40, 40), 40)
    D.boite(img, 40, 900, 1040, 940, (250, 250, 250), 6)                    # paillasse
    for k in range(6):                                                     # éprouvettes sur leur support
        x = 120 + k * 60; col = ((90, 200, 90), (230, 80, 160), (80, 160, 230), (250, 200, 60), (230, 90, 60), (150, 90, 210))[k]
        D.boite(img, x, 790, x + 30, 900, (235, 245, 250), 4, 14); D.boite(img, x + 3, 840, x + 27, 897, col, 0, 12)
        if k % 2 == 0: res["vapeur"].append((x + 15, 780))
    D.boite(img, 100, 890, 480, 906, (150, 150, 160), 4)
    D.poly(img, [(600, 900), (660, 760), (700, 760), (760, 900)], (220, 236, 245), 5); D.poly(img, [(615, 900), (650, 820), (710, 820), (745, 900)], (120, 220, 120), 0)   # erlenmeyer
    D.boite(img, 860, 700, 940, 900, (60, 60, 70), 6, 8); D.boite(img, 900, 650, 930, 760, (60, 60, 70), 5); D.boite(img, 840, 880, 980, 906, (60, 60, 70), 5)   # microscope
    D.affiche(img, 720, 620, 1030, 760, gag(1), (255, 240, 120))
    for x in (180, 820): D.boite(img, x, 940, x + 20, S + 40, (180, 185, 195), 4)
    res["fenetre"] = None


def cockpit(img, rng, res, gag, moment, allume):
    """Cockpit d'avion : pare-brise sur le ciel de l'heure (nuages en dessous), tableau de bord et manches au premier plan."""
    img[:] = D._variante(COULEURS_MUR["cockpit"], rng, 6)
    D.ciel(img, 60, 160, 1020, 900, moment, rng, False)
    for k in range(5): cv2.ellipse(img, (int(rng.uniform(100, 980)), int(rng.uniform(700, 880))), (int(rng.uniform(90, 160)), 40), 0, 0, 360, (250, 250, 252), -1, AA)
    for pts in ([(60, 160), (520, 160), (520, 900), (60, 820)], [(560, 160), (1020, 160), (1020, 820), (560, 900)]):
        cv2.polylines(img, [np.array(pts, np.int32)], True, TRAIT, 14, AA)
    D.boite(img, 520, 120, 560, 940, (60, 64, 76), 6)
    D.boite(img, 0, 900, D.W, S + 40, (50, 54, 64), 6)                      # tableau de bord (haut)
    for k in range(8):
        x = 90 + k * 120; cv2.circle(img, (x, 1020), 42, (20, 22, 28), -1, AA); cv2.circle(img, (x, 1020), 42, (160, 160, 170), 5, AA)
        D.ligne(img, (x, 1020), (int(x + 30 * np.cos(k)), int(1020 - 30 * abs(np.sin(k)))), (250, 250, 250), 5)
    for k in range(10): D.boite(img, 80 + k * 94, 1110, 140 + k * 94, 1150, ((230, 60, 60), (80, 200, 90), (250, 200, 60))[k % 3], 4, 6)
    D.boite(img, 380, 940, 700, 990, (30, 30, 36), 4, 6); D.texte(img, gag(1), 380, 940, 700, 990, (120, 255, 160), 22)
    res["ecrans"].append((380, 940, 700, 990)); res["fenetre"] = (60, 160, 1020, 900)
    def avant(a3):
        D.boite(a3, 0, 1500, D.W, D.H, (44, 46, 56), 8)
        for x in (250, 830): D.ligne(a3, (x, 1720), (x, 1560), (40, 40, 46), 26); D.boite(a3, x - 70, 1520, x + 70, 1570, (30, 30, 36), 6, 14)   # manches
        D.boite(a3, 470, 1540, 610, 1640, (80, 84, 96), 6, 8)
        for k in range(3): D.boite(a3, 490, 1560 + k * 26, 590, 1574 + k * 26, (200, 200, 210), 3)
    return D._avant(avant, 1500, [])


def espace(img, rng, res, gag, moment, allume):
    """Station spatiale : grand hublot sur la Terre et les étoiles, panneaux de commandes, câbles, objets qui flottent."""
    img[:] = D._variante((200, 206, 214), rng, 6)
    cx, cy, r = 540, 560, 400
    cv2.circle(img, (cx, cy), r + 40, (150, 156, 166), -1, AA); cv2.circle(img, (cx, cy), r + 40, TRAIT, 8, AA)
    cv2.circle(img, (cx, cy), r, (14, 16, 40), -1, AA)
    for _ in range(80): cv2.circle(img, (int(rng.uniform(cx - r, cx + r)), int(rng.uniform(cy - r, cy + r))), int(rng.uniform(1, 4)), (250, 250, 255), -1, AA)
    cv2.circle(img, (cx - 60, cy + 420), 330, (60, 120, 210), -1, AA)        # la Terre
    for pts in ([(260, 800), (360, 740), (420, 820), (330, 900)], [(560, 760), (680, 720), (720, 800), (600, 860)]): D.poly(img, pts, (90, 170, 90), 0)
    cv2.ellipse(img, (cx - 60, cy + 420), (330, 330), 0, 200, 340, (150, 200, 250), 10, AA)
    mask = np.zeros(img.shape[:2], np.uint8); cv2.circle(mask, (cx, cy), r, 255, -1)
    out = np.where(mask[..., None] > 0, img, D._variante((200, 206, 214), rng, 0)); img[:] = out
    cv2.circle(img, (cx, cy), r + 40, (150, 156, 166), 40, AA); cv2.circle(img, (cx, cy), r + 60, TRAIT, 6, AA); cv2.circle(img, (cx, cy), r, TRAIT, 6, AA)
    for k in range(10): cv2.circle(img, (int(cx + (r + 40) * np.cos(k * 0.628)), int(cy + (r + 40) * np.sin(k * 0.628))), 9, (90, 94, 104), -1, AA)   # rivets
    for x0 in (30, 860):                                                   # panneaux de commandes
        D.boite(img, x0, 1020, x0 + 190, S + 80, (90, 96, 110), 6, 8)
        for j in range(4):
            for i in range(3): D.boite(img, x0 + 20 + i * 56, 1050 + j * 60, x0 + 60 + i * 56, 1080 + j * 60, ((230, 60, 60), (80, 200, 90), (250, 200, 60), (80, 160, 240))[(i + j) % 4], 3, 6)
    D.boite(img, 300, 1040, 780, 1110, (30, 30, 36), 5, 8); D.texte(img, gag(0), 300, 1040, 780, 1110, (120, 255, 160), 28)
    D.sol(img, (150, 156, 166), "carrelage")
    for k in range(3): D.ligne(img, (0, 200 + k * 30), (D.W, 260 + k * 30), ((220, 60, 60), (250, 200, 60), (60, 120, 220))[k], 8)   # câbles
    res["fenetre"] = None; res["ecrans"].append((300, 1040, 780, 1110))


def coiffeur(img, rng, res, gag, moment, allume):
    """Salon de coiffure : grands miroirs éclairés, fauteuils, bac à shampoing, produits, sèche-cheveux sur pied."""
    _sol_mur(img, "coiffeur", rng, "rayures", (240, 240, 244), "damier")
    for x0 in (80, 600):                                                   # miroirs à ampoules
        D.boite(img, x0, 300, x0 + 400, 820, (200, 225, 240), 8, 16)
        for k in range(7): cv2.circle(img, (x0 + 20 + k * 60, 286), 16, (255, 240, 170), -1, AA); cv2.circle(img, (x0 + 20 + k * 60, 286), 16, TRAIT, 3, AA)
        for k in range(2): D.ligne(img, (x0 + 60 + k * 160, 780), (x0 + 160 + k * 160, 360), (235, 245, 252), 8)
        res["miroirs"] = res.get("miroirs", []) + [(x0, 300, x0 + 400, 820)]
        D.boite(img, x0, 840, x0 + 400, 870, (250, 250, 250), 5)
        for k in range(4): D.boite(img, x0 + 30 + k * 90, 770, x0 + 70 + k * 90, 840, ((230, 120, 170), (120, 180, 230), (250, 200, 80), (160, 220, 160))[k], 4, 10)
    D.texte(img, gag(2), 300, 170, 780, 240, (190, 60, 110), 40)
    for x in (280, 800):                                                   # fauteuils
        D.boite(img, x - 110, S - 140, x + 110, S + 20, (40, 40, 46), 6, 30); D.boite(img, x - 20, S + 20, x + 20, S + 110, (160, 160, 170), 4)
        cv2.ellipse(img, (x, S + 120), (90, 22), 0, 0, 360, (160, 160, 170), -1, AA); cv2.ellipse(img, (x, S + 120), (90, 22), 0, 0, 360, TRAIT, 4, AA)
    D.ligne(img, (1020, S + 60), (1020, 640), (190, 190, 200), 10); cv2.ellipse(img, (980, 600), (90, 70), 0, 0, 360, (240, 160, 190), -1, AA); cv2.ellipse(img, (980, 600), (90, 70), 0, 0, 360, TRAIT, 5, AA)   # casque séchoir
    for _ in range(5): cv2.ellipse(img, (int(rng.uniform(400, 700)), int(rng.uniform(S + 60, S + 220))), (22, 8), rng.uniform(0, 180), 0, 360, (90, 60, 40), -1, AA)   # mèches coupées
    res["lampes"].append(D.suspension(img, 540, 110, True)); res["fenetre"] = None


DESSINS = {"caserne": caserne, "garage": garage, "boulangerie": boulangerie, "ferme": ferme, "tribunal": tribunal, "labo": labo,
           "cockpit": cockpit, "espace": espace, "coiffeur": coiffeur}
DECOR_EN = {"caserne": "fire station interior, red fire truck in the open garage bay, helmets and jackets on hooks, brick walls",
            "garage": "car repair garage, car on a lift, tool wall, tires stacked, oil cans, workbench",
            "boulangerie": "french bakery, shelves of baguettes and bread, pastry display counter, chalkboard prices",
            "ferme": "farm yard, red barn, wooden fence, hay bales, chickens, green hills",
            "tribunal": "courtroom, wooden judge bench, scales of justice, witness stand, flags",
            "labo": "science laboratory, white bench with colorful test tubes, microscope, chalkboard formulas",
            "cockpit": "airplane cockpit, windshield with clouds, instrument panel, control yokes",
            "espace": "space station interior, big round window on planet Earth and stars, control panels",
            "coiffeur": "hair salon, mirrors with light bulbs, barber chairs, hair products, hair dryer"}


# ------------------------------------------------------------------ inscription dans le catalogue des décors dessinés
import decor_details as _DX
D.LIEUX = tuple(dict.fromkeys(D.LIEUX + LIEUX)); D.GAGS.update(GAGS); D.COULEURS_MUR.update(COULEURS_MUR)
_DX.NOUVEAUX.update(DESSINS)
