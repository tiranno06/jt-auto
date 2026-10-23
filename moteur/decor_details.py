"""Détails des décors dessinés (sans IA) : portes moulurées, prises et interrupteurs, tapis, cadres photo, calendrier, extincteur,
porte-manteau, plantes, poubelle, banc, panneaux… et quatre lieux de plus : administration (guichet), hall d'immeuble (escalier,
boîtes aux lettres), caverne préhistorique (peintures rupestres, feu) et palais (moulures dorées, lustre, marbre).

habiller(img, lieu, rng, res, moment) ajoute les petits objets qui rendent chaque lieu vivant, après les meubles principaux."""
import math
import numpy as np, cv2

import decor_dessin as D

TRAIT = (26, 22, 30)                                                       # = decor_dessin.TRAIT


# ------------------------------------------------------------------ petits objets
def porte(img, x0, x1, y_sol, col, vitre=False):
    """Porte à moulures (deux panneaux), chambranle et poignée ronde dorée."""
    y0 = y_sol - int((x1 - x0) * 2.25)
    D.boite(img, x0 - 22, y0 - 22, x1 + 22, y_sol + 2, D.clair(col, 0.55), 6)          # chambranle
    D.boite(img, x0, y0, x1, y_sol, col, 6)
    w = x1 - x0
    if vitre: D.boite(img, x0 + w * 0.18, y0 + 40, x1 - w * 0.18, y0 + (y_sol - y0) * 0.45, (190, 215, 235), 5)
    else: D.boite(img, x0 + w * 0.16, y0 + 40, x1 - w * 0.16, y0 + (y_sol - y0) * 0.45, D.fonce(col, 0.9), 4)
    D.boite(img, x0 + w * 0.16, y0 + (y_sol - y0) * 0.52, x1 - w * 0.16, y_sol - 40, D.fonce(col, 0.9), 4)
    D.rond(img, (x1 - w * 0.12, y0 + (y_sol - y0) * 0.5), 14, (215, 180, 80), 4)


def prise(img, x, y):
    D.boite(img, x - 22, y - 22, x + 22, y + 22, (248, 248, 246), 4, 6)
    for dx in (-7, 7): cv2.circle(img, (int(x + dx), int(y)), 4, TRAIT, -1, cv2.LINE_AA)


def interrupteur(img, x, y):
    D.boite(img, x - 22, y - 30, x + 22, y + 30, (248, 248, 246), 4, 6); D.boite(img, x - 10, y - 16, x + 10, y + 16, (230, 230, 228), 3, 4)


def tapis(img, cx, cy, w, h, col, motif="bord"):
    """Tapis au sol (ellipse aplatie par la perspective), bordure et motif."""
    cv2.ellipse(img, (int(cx), int(cy)), (int(w / 2 + 6), int(h / 2 + 6)), 0, 0, 360, TRAIT, -1, cv2.LINE_AA)
    cv2.ellipse(img, (int(cx), int(cy)), (int(w / 2), int(h / 2)), 0, 0, 360, col, -1, cv2.LINE_AA)
    cv2.ellipse(img, (int(cx), int(cy)), (int(w / 2 - 26), int(h / 2 - 16)), 0, 0, 360, D.fonce(col, 0.8), 6, cv2.LINE_AA)
    if motif == "losanges":
        for k in range(-3, 4): D.poly(img, [(cx + k * w / 9, cy - h / 6), (cx + k * w / 9 + w / 22, cy), (cx + k * w / 9, cy + h / 6), (cx + k * w / 9 - w / 22, cy)], D.clair(col, 0.3), 0)
    for k in range(0, 360, 12):                                            # franges
        a = math.radians(k); x, y = cx + math.cos(a) * w / 2, cy + math.sin(a) * h / 2
        if abs(math.cos(a)) > 0.92: cv2.line(img, (int(x), int(y)), (int(x + math.copysign(14, math.cos(a))), int(y)), D.clair(col, 0.4), 3, cv2.LINE_AA)


def cadres_photo(img, x0, y0, rng, n=3):
    for k in range(n):
        w, h = int(rng.uniform(70, 110)), int(rng.uniform(80, 120)); x = x0 + k * 125; y = y0 + int(rng.uniform(-20, 20))
        D.boite(img, x, y, x + w, y + h, (60, 50, 45) if k % 2 else (200, 170, 110), 5)
        D.boite(img, x + 10, y + 10, x + w - 10, y + h - 10, (220, 235, 245), 3)
        cv2.circle(img, (x + w // 2, y + h // 2 - 4), 12, D._variante((230, 190, 160), rng), -1, cv2.LINE_AA)
        cv2.ellipse(img, (x + w // 2, y + h - 12), (20, 14), 0, 180, 360, D._variante((90, 120, 200), rng), -1, cv2.LINE_AA)


def calendrier(img, x0, y0, x1, y1, txt="LUNDI"):
    D.boite(img, x0, y0, x1, y1, (252, 252, 250), 5); D.boite(img, x0, y0, x1, y0 + (y1 - y0) * 0.25, (220, 60, 60), 5)
    D.texte(img, txt, x0, y0, x1, y0 + (y1 - y0) * 0.25, (255, 255, 255), 22)
    for j in range(4):
        for i in range(5):
            xx, yy = x0 + 14 + i * (x1 - x0 - 28) / 5, y0 + (y1 - y0) * 0.33 + j * (y1 - y0) * 0.16
            D.boite(img, xx, yy, xx + (x1 - x0 - 28) / 5 - 6, yy + (y1 - y0) * 0.12, (235, 235, 232), 2)
    cv2.line(img, (int(x0 + 20), int(y0 + (y1 - y0) * 0.5)), (int(x0 + 50), int(y0 + (y1 - y0) * 0.6)), (220, 60, 60), 5, cv2.LINE_AA)


def extincteur(img, x, y_sol):
    D.boite(img, x - 28, y_sol - 170, x + 28, y_sol, (215, 45, 45), 5, 20); D.boite(img, x - 14, y_sol - 196, x + 14, y_sol - 168, (40, 40, 46), 4)
    D.ligne(img, (x + 14, y_sol - 186), (x + 44, y_sol - 120), TRAIT, 7); D.boite(img, x - 20, y_sol - 120, x + 20, y_sol - 80, (250, 250, 250), 3)


def poubelle(img, x, y_sol, col=(120, 130, 140)):
    D.poly(img, [(x - 46, y_sol - 140), (x + 46, y_sol - 140), (x + 36, y_sol), (x - 36, y_sol)], col, 6)
    D.boite(img, x - 52, y_sol - 156, x + 52, y_sol - 136, D.fonce(col, 0.85), 5, 6)
    for k in (-1, 0, 1): D.ligne(img, (x + k * 22, y_sol - 120), (x + k * 18, y_sol - 20), D.fonce(col, 0.8), 4)


def porte_manteau(img, x, y_sol, rng):
    D.ligne(img, (x, y_sol), (x, y_sol - 520), TRAIT, 16); D.ligne(img, (x, y_sol), (x, y_sol - 520), (120, 80, 50), 8)
    for sg in (-1, 1): D.ligne(img, (x, y_sol - 500), (x + sg * 50, y_sol - 540), (120, 80, 50), 8)
    D.poly(img, [(x - 80, y_sol), (x + 80, y_sol), (x, y_sol - 30)], (120, 80, 50), 5)
    col = D._variante((80, 110, 170), rng)                                 # un manteau suspendu
    D.poly(img, [(x - 46, y_sol - 500), (x + 6, y_sol - 500), (x + 10, y_sol - 260), (x - 70, y_sol - 260)], col, 5)
    D.boite(img, x + 20, y_sol - 530, x + 90, y_sol - 490, D._variante((200, 60, 60), rng), 4, 14)   # écharpe / sac


def plante_haute(img, x, y_sol, k=1.0):
    D.pot(img, x, y_sol, 1.2 * k, (220, 220, 215))
    for j in range(7):
        a = math.radians(-150 + j * 20); L = 200 * k * (0.7 + 0.3 * (j % 2))
        c = (x + math.cos(a) * L * 0.6, y_sol - 120 * k + math.sin(a) * L)
        D.ligne(img, (x, y_sol - 100 * k), c, (60, 120, 70), 6)
        cv2.ellipse(img, (int(c[0]), int(c[1])), (int(34 * k), int(14 * k)), math.degrees(a), 0, 360, TRAIT, -1, cv2.LINE_AA)
        cv2.ellipse(img, (int(c[0]), int(c[1])), (int(29 * k), int(10 * k)), math.degrees(a), 0, 360, (90, 170, 100), -1, cv2.LINE_AA)


def chaise(img, x, y_sol, col, sg=1):
    D.boite(img, x - 50, y_sol - 120, x + 50, y_sol - 100, col, 5); D.boite(img, x - sg * 50 - (6 if sg > 0 else -6), y_sol - 260, x - sg * 50 + (14 if sg > 0 else -14), y_sol - 100, col, 5)
    for dx in (-44, 40): D.boite(img, x + dx, y_sol - 100, x + dx + 8, y_sol, D.fonce(col, 0.7), 3)


def banc(img, x0, x1, y_sol, col=(120, 160, 110)):
    for k in range(3): D.boite(img, x0, y_sol - 200 + k * 34, x1, y_sol - 176 + k * 34, col, 4, 6)
    D.boite(img, x0, y_sol - 96, x1, y_sol - 72, col, 4, 6)
    for xx in (x0 + 20, x1 - 40): D.boite(img, xx, y_sol - 72, xx + 18, y_sol, (60, 60, 66), 4)


def panneau_rue(img, x, y_sol, txt="STOP"):
    D.ligne(img, (x, y_sol), (x, y_sol - 520), TRAIT, 14); D.ligne(img, (x, y_sol), (x, y_sol - 520), (170, 175, 185), 7)
    pts = [(x + 70 * math.cos(math.pi / 8 + k * math.pi / 4), y_sol - 600 + 70 * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
    D.poly(img, pts, (210, 40, 40), 6); D.texte(img, txt, x - 56, y_sol - 630, x + 56, y_sol - 570, (255, 255, 255), 30)


def lustre(img, x, y, allume):
    D.ligne(img, (x, 0), (x, y), TRAIT, 5)
    c = (255, 236, 160) if allume else (240, 220, 150)
    D.boite(img, x - 140, y, x + 140, y + 20, (215, 175, 70), 4, 8)
    for k in range(-3, 4):
        D.ligne(img, (x + k * 40, y + 20), (x + k * 40, y + 70), (215, 175, 70), 5)
        D.poly(img, [(x + k * 40 - 12, y + 70), (x + k * 40 + 12, y + 70), (x + k * 40, y + 40)], c, 3)
        for j in range(2): cv2.circle(img, (int(x + k * 40), int(y + 90 + j * 22)), 7, (200, 225, 245), -1, cv2.LINE_AA)
    return (x, y + 60)


# ------------------------------------------------------------------ lieux en plus
def administration(img, rng, res, gag, moment, allume):
    """Guichet d'administration : mur bleu, affiches « service public » (inventées), afficheur de tickets, file d'attente."""
    img[:620] = D._variante((52, 92, 160), rng, 8)
    D.boite(img, 70, 200, 470, 900, (250, 250, 248), 6)
    for k, c_ in enumerate(((40, 70, 150), (250, 250, 250), (210, 50, 50))): cv2.rectangle(img, (100 + 70 * k, 240), (170 + 70 * k, 290), c_, -1)
    cv2.rectangle(img, (100, 240), (310, 290), TRAIT, 4, cv2.LINE_AA)
    D.texte(img, "SERVICE PUBLIC", 100, 310, 440, 380, (30, 40, 90), 40, False)
    D.texte(img, gag(0), 100, 400, 440, 560, (30, 40, 90), 30, False)
    for k, t in enumerate(("Accueil", "Dossiers", "Réclamations", "Patience")):
        cv2.circle(img, (125, 610 + k * 70), 20, (40, 70, 150), -1, cv2.LINE_AA); D.texte(img, t, 160, 590 + k * 70, 440, 635 + k * 70, (30, 40, 90), 30, False)
    D.boite(img, 600, 230, 1000, 400, (30, 30, 34), 8, 10)                 # afficheur de tickets
    D.texte(img, "N° 3", 620, 245, 790, 385, (255, 90, 70), 70); D.texte(img, "VOUS : 847", 790, 245, 990, 385, (250, 200, 80), 34)
    D.horloge(img, 800, 520, 60, (11, 55))
    D.boite(img, 560, 700, 1040, 880, (250, 250, 248), 5); D.texte(img, gag(1), 580, 715, 1020, 865, (30, 40, 90), 30)
    D.boite(img, 820, D.SOL - 260, 1040, D.SOL - 80, (120, 130, 145), 6, 4)   # armoire à dossiers
    for k in range(2): D.boite(img, 900, D.SOL - 230 + k * 80, 960, D.SOL - 215 + k * 80, (230, 230, 232), 3, 4)
    for x in (110, 300): D.boite(img, x, D.SOL - 20, x + 18, D.SOL + 150, (190, 160, 70), 4); D.boite(img, x - 20, D.SOL + 150, x + 38, D.SOL + 166, (90, 90, 100), 4)
    D.ligne(img, (128, D.SOL + 10), (310, D.SOL + 30), (200, 40, 60), 9)  # cordon de file d'attente
    av = D._avant(lambda a3: (D.comptoir_avant(a3, 1560, (230, 232, 236), (52, 92, 160)), D.boite(a3, 860, 1440, 1060, 1566, (70, 70, 80), 6, 8),
                              D.ecran(a3, 880, 1450, 1040, 1540, "bleu"), D.texte(a3, "GUICHET 2", 300, 1600, 780, 1680, (52, 92, 160), 50)),
                  1560, [(850, 1430, D.W, 1566)])
    res["ecrans"].append((600, 230, 1000, 400))
    return av


def hall(img, rng, res, gag, moment, allume):
    """Hall d'immeuble ancien : moulures, porte palière, escalier en bois et rampe en fer, boîtes aux lettres, carrelage à cabochons."""
    c = D._variante((236, 226, 206), rng, 8); img[:D.SOL] = c
    for x0 in (40, 560):                                                   # panneaux moulurés
        D.boite(img, x0, 160, x0 + 460, 560, D.fonce(c, 0.95), 4)
    res["fenetre"] = (60, 220, 330, 820); D.fenetre(img, *res["fenetre"], moment, rng, cadre=(250, 250, 246))
    porte(img, 640, 940, D.SOL, D._variante((70, 90, 80), rng))
    D.boite(img, 690, D.SOL - 760, 900, D.SOL - 700, (210, 180, 90), 4); D.texte(img, "Mme DUPONT", 690, D.SOL - 760, 900, D.SOL - 700, TRAIT, 22)
    D.boite(img, 360, 600, 600, 900, (150, 110, 70), 6)                    # boîtes aux lettres
    for j in range(3):
        for i in range(2):
            D.boite(img, 375 + i * 115, 615 + j * 95, 470 + i * 115, 695 + j * 95, (180, 140, 90), 3)
            D.ligne(img, (390 + i * 115, 640 + j * 95), (455 + i * 115, 640 + j * 95), TRAIT, 4)
    for k in range(7):                                                     # escalier qui monte à gauche, rampe en fer forgé
        y = D.SOL - k * 90; D.boite(img, 0, y - 90, 330 - k * 46, y, (180, 130, 80), 4)
    D.ligne(img, (330, D.SOL - 140), (0, D.SOL - 760), (130, 80, 45), 26)
    for k in range(8):
        x = 320 - k * 42; D.ligne(img, (x, D.SOL - 140 - k * 78 + 10), (x, D.SOL - k * 90), (40, 40, 46), 6)
    res["lampes"].append(D.suspension(img, 540, 120, allume))
    D.sol(img, D._variante((236, 230, 220), rng, 6), "damier")


def caverne(img, rng, res, gag, moment, allume):
    """Caverne préhistorique : paroi rocheuse, peintures rupestres, feu de camp, os et outils, entrée de la grotte."""
    img[:D.SOL] = (150, 120, 92)
    for _ in range(26):                                                    # blocs de roche
        x, y = rng.uniform(0, D.W), rng.uniform(0, D.SOL); r = rng.uniform(60, 160)
        pts = [(x + r * math.cos(a) * rng.uniform(0.7, 1.1), y + r * 0.7 * math.sin(a) * rng.uniform(0.7, 1.1)) for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
        D.poly(img, pts, D._variante((160, 128, 98), rng, 14), 4)
    cv2.ellipse(img, (860, 760), (190, 330), 0, 0, 360, TRAIT, -1, cv2.LINE_AA)    # entrée de la grotte : le dehors
    sky = (255, 214, 150) if moment in ("matin", "soir") else ((40, 50, 90) if moment == "nuit" else (170, 210, 240))
    cv2.ellipse(img, (860, 760), (180, 320), 0, 0, 360, sky, -1, cv2.LINE_AA)
    D.poly(img, [(700, 1000), (800, 820), (900, 900), (1030, 760), (1040, 1100), (700, 1100)], (110, 140, 90), 0)
    rouge = (170, 60, 40)                                                  # peintures rupestres : mammouth, chasseurs, mains
    cv2.ellipse(img, (330, 380), (130, 80), 0, 180, 360, rouge, 8, cv2.LINE_AA); D.ligne(img, (200, 380), (460, 380), rouge, 8)
    for dx in (230, 290, 380, 430): D.ligne(img, (dx, 380), (dx, 450), rouge, 8)
    D.ligne(img, (200, 380), (170, 470), rouge, 8); cv2.ellipse(img, (175, 480), (22, 12), 0, 0, 180, rouge, 6, cv2.LINE_AA)
    for k in range(3):
        x = 140 + k * 110; y = 640
        cv2.circle(img, (x, y - 50), 14, rouge, -1, cv2.LINE_AA); D.ligne(img, (x, y - 36), (x, y + 20), rouge, 7)
        for sg in (-1, 1): D.ligne(img, (x, y + 20), (x + sg * 18, y + 60), rouge, 6); D.ligne(img, (x, y - 20), (x + sg * 24, y), rouge, 6)
        D.ligne(img, (x + 24, y - 60), (x + 40, y + 30), rouge, 4)
    for k in range(3):
        c = (520 + k * 70, 300 + (k % 2) * 40); cv2.circle(img, c, 22, (230, 200, 150), -1, cv2.LINE_AA)
        for j in range(5): a = math.radians(-150 + j * 30); D.ligne(img, c, (c[0] + 38 * math.cos(a), c[1] + 38 * math.sin(a)), (230, 200, 150), 9)
    D.sol(img, (130, 100, 72), "moquette")
    for k in range(5):                                                     # feu de camp
        a = math.radians(k * 36); D.ligne(img, (540 + 120 * math.cos(a), D.SOL + 160), (540 - 120 * math.cos(a), D.SOL + 100), (110, 70, 40), 18)
    for r, col in ((80, (240, 120, 40)), (55, (250, 190, 60)), (30, (255, 240, 170))):
        D.poly(img, [(540 - r, D.SOL + 110), (540 + r, D.SOL + 110), (540 + r * 0.3, D.SOL + 110 - r * 2.4), (540, D.SOL + 110 - r * 1.6), (540 - r * 0.4, D.SOL + 110 - r * 2.6)], col, 0)
    res["lampes"].append((540, D.SOL - 40)); res["vapeur"].append((540, D.SOL - 140))
    D.ligne(img, (80, D.SOL + 60), (200, D.SOL + 30), (245, 240, 225), 16)   # os
    for p_ in ((80, D.SOL + 60), (200, D.SOL + 30)): cv2.circle(img, p_, 14, (245, 240, 225), -1, cv2.LINE_AA)
    res["fenetre"] = (680, 440, 1040, 1080)


def palais(img, rng, res, gag, moment, allume):
    """Palais (style Versailles) : boiseries crème à moulures dorées, grands tableaux, fenêtres hautes, lustre, sol en marbre."""
    or_ = (215, 175, 70); c = D._variante((244, 236, 214), rng, 6); img[:D.SOL] = c
    for x0 in (40, 400, 760):
        D.boite(img, x0, 120, x0 + 290, D.SOL - 360, D.fonce(c, 0.97), 0)
        cv2.rectangle(img, (x0, 120), (x0 + 290, D.SOL - 360), or_, 8, cv2.LINE_AA); cv2.rectangle(img, (x0 + 20, 140), (x0 + 270, D.SOL - 380), or_, 3, cv2.LINE_AA)
    res["fenetre"] = (60, 220, 310, 780); D.fenetre(img, *res["fenetre"], moment, rng, rideaux=(150, 40, 60))
    D.cadre_tableau(img, 440, 260, 690, 560, rng, or_, "portrait"); D.cadre_tableau(img, 800, 300, 1010, 520, rng, or_, "montagne")
    D.boite(img, 0, D.SOL - 330, D.W, D.SOL, D.fonce(c, 0.9), 5)           # soubassement
    for x in range(30, D.W, 180): cv2.rectangle(img, (x, D.SOL - 300), (x + 140, D.SOL - 40), or_, 4, cv2.LINE_AA)
    res["lampes"].append(lustre(img, 540, 140, allume))
    D.boite(img, 820, D.SOL - 260, 1000, D.SOL - 230, (120, 70, 40), 5); D.boite(img, 840, D.SOL - 230, 860, D.SOL + 40, (120, 70, 40), 4); D.boite(img, 960, D.SOL - 230, 980, D.SOL + 40, (120, 70, 40), 4)
    D.poly(img, [(880, D.SOL - 260), (940, D.SOL - 260), (930, D.SOL - 340), (890, D.SOL - 340)], (230, 230, 240), 4)      # vase
    for k in range(5): cv2.circle(img, (880 + k * 15, D.SOL - 360 - (k % 2) * 16), 14, (230, 90, 120), -1, cv2.LINE_AA)
    D.sol(img, (238, 236, 232), "damier")


def voiture(img, rng, res, gag, moment, allume):
    """Intérieur de voiture (D4) vu depuis le pare-brise : dossiers et appuie-tête derrière les personnages, lunette arrière qui
    montre la route, plafonnier, rétroviseur et petit sapin parfumé ; au premier plan, tableau de bord et volant (devant eux)."""
    c_hab = D._variante((70, 74, 86), rng, 8); img[:] = c_hab
    nuit = moment in ("soir", "nuit")
    D.boite(img, 120, 260, 960, 760, (40, 44, 52), 10, 60)                 # lunette arrière (la route derrière)
    D.ciel(img, 140, 280, 940, 740, moment, rng, True)
    D.poly(img, [(140, 740), (940, 740), (600, 560), (480, 560)], (90, 92, 100), 0)          # route qui file
    for k in range(4): D.ligne(img, (540, 580 + k * 42), (540, 600 + k * 42), (250, 250, 240), 6 + 2 * k)
    for xx in (230, 860):
        if nuit: cv2.circle(img, (xx, 690), 16, (255, 236, 170), -1, cv2.LINE_AA)
    cv2.rectangle(img, (120, 260), (960, 760), D.TRAIT, 10, cv2.LINE_AA)
    D.boite(img, 0, 0, D.W, 150, D.fonce(c_hab, 0.85), 6)                  # pavillon + plafonnier
    D.boite(img, 470, 70, 610, 130, (240, 236, 220) if nuit else (210, 210, 214), 5, 20)
    res["lampes"].append((540, 140)) if nuit else None
    D.ligne(img, (0, 160), (110, 900), D.TRAIT, 24); D.ligne(img, (D.W, 160), (D.W - 110, 900), D.TRAIT, 24)   # montants
    c_siege = D._variante(rng.choice([(150, 60, 50), (50, 60, 80), (120, 100, 80), (40, 40, 46)]), rng)
    for x0 in (40, 580):                                                   # dossiers + appuie-tête (derrière les personnages)
        D.boite(img, x0 + 90, 640, x0 + 370, 820, c_siege, 7, 40)
        D.boite(img, x0 + 20, 800, x0 + 440, D.H, c_siege, 8, 70)
        for k in range(3): D.ligne(img, (x0 + 80, 920 + k * 150), (x0 + 380, 920 + k * 150), D.fonce(c_siege, 0.8), 5)
        D.ligne(img, (x0 + 180, 820), (x0 + 180, 800), (180, 180, 186), 8); D.ligne(img, (x0 + 280, 820), (x0 + 280, 800), (180, 180, 186), 8)
    D.boite(img, 440, 150, 640, 210, (30, 30, 36), 5, 14)                  # rétroviseur
    D.boite(img, 455, 160, 625, 200, (150, 180, 210), 3, 10)
    D.ligne(img, (590, 210), (590, 300), D.TRAIT, 3)                       # petit sapin parfumé
    D.poly(img, [(590, 300), (560, 380), (620, 380)], (60, 170, 90), 4); D.poly(img, [(590, 340), (550, 430), (630, 430)], (60, 170, 90), 4)
    D.texte(img, "VANILLE", 555, 395, 625, 425, (255, 255, 255), 14)
    res["fenetre"] = (120, 260, 960, 760)
    res["voiture"] = True
    c_tab = D._variante((44, 46, 54), rng, 6)
    def devant(a3):
        D.boite(a3, -20, 1300, D.W + 20, D.H + 20, c_tab, 8, 60)           # tableau de bord
        D.boite(a3, 30, 1360, D.W - 30, 1400, D.fonce(c_tab, 0.7), 4, 20)
        D.ecran(a3, 470, 1420, 640, 1530, "bleu"); D.texte(a3, "GPS : demi-tour", 476, 1540, 636, 1580, (220, 230, 240), 18)
        for xx in (380, 720): D.boite(a3, xx - 40, 1430, xx + 40, 1480, (30, 30, 36), 5, 10)    # aérations
        cv2.circle(a3, (200, 1410), 170, D.TRAIT, 44, cv2.LINE_AA); cv2.circle(a3, (200, 1410), 170, (36, 36, 42), 30, cv2.LINE_AA)   # volant
        D.boite(a3, 160, 1385, 240, 1445, (36, 36, 42), 5, 20); D.ligne(a3, (60, 1425), (160, 1412), (36, 36, 42), 24); D.ligne(a3, (240, 1412), (340, 1425), (36, 36, 42), 24)
        D.boite(a3, 700, 1560, 1010, 1760, D.fonce(c_tab, 0.85), 6, 18); D.boite(a3, 820, 1640, 890, 1666, (150, 150, 160), 3, 8)   # boîte à gants
        D.boite(a3, 820, 1330, 1000, 1400, (230, 200, 90), 4, 10); D.texte(a3, gag(0), 826, 1334, 994, 1396, D.TRAIT, 16)   # post-it collé
    return D._avant(devant, 1300, [(0, 1200, 300, 1300)])


NOUVEAUX = {"administration": administration, "hall": hall, "caverne": caverne, "palais": palais, "voiture": voiture}


# ------------------------------------------------------------------ habillage des lieux existants
def habiller(img, lieu, rng, res, moment, gag=lambda k: ""):
    """Petits objets en plus, à des places libres de chaque décor."""
    S = D.SOL
    if lieu in ("salon", "chambre", "bureau", "cabinet_medical", "classe", "restaurant", "administration", "palais"):
        prise(img, 470, S - 70)
    if lieu == "salon":
        interrupteur(img, 500, 820); cadres_photo(img, 560, 230, rng, 3)
        tapis(img, 540, S + 330, 860, 190, D._variante((170, 70, 70), rng), "losanges")
    elif lieu == "chambre":
        tapis(img, 520, S + 360, 560, 150, D._variante((120, 180, 200), rng))
        cadres_photo(img, 90, 760, rng, 2); interrupteur(img, 600, 640)
        D.boite(img, 650, S + 190, 720, S + 220, D._variante((60, 90, 160), rng), 4, 10); D.boite(img, 700, S + 205, 760, S + 232, (240, 240, 240), 4, 10)  # chaussettes par terre
    elif lieu == "cuisine":
        tapis(img, 560, S + 300, 520, 120, D._variante((220, 120, 60), rng))
        for k in range(3): D.boite(img, 680 + k * 54, 868, 722 + k * 54, 940, D._variante((240, 240, 230), rng), 4, 8)   # bocaux
        for k, c_ in enumerate(((230, 60, 60), (250, 200, 60), (60, 140, 220))):          # aimants sur le frigo (D3)
            cv2.circle(img, (60 + k * 40, 860 + (k % 2) * 30), 14, c_, -1, cv2.LINE_AA); cv2.circle(img, (60 + k * 40, 860 + (k % 2) * 30), 14, TRAIT, 3, cv2.LINE_AA)
        cv2.ellipse(img, (900, 900), (80, 34), 0, 0, 180, D._variante((200, 120, 70), rng), -1, cv2.LINE_AA)   # corbeille de fruits
        for k, c_ in enumerate(((230, 60, 50), (250, 200, 50), (120, 190, 70))): cv2.circle(img, (860 + k * 40, 890 - (k % 2) * 14), 22, c_, -1, cv2.LINE_AA)
        cv2.ellipse(img, (900, 900), (80, 34), 0, 0, 180, TRAIT, 4, cv2.LINE_AA)
        D.boite(img, 980, 760, 1060, 940, (210, 170, 120), 4, 6)                 # planche à découper
    elif lieu == "bureau":
        extincteur(img, 570, S + 30); calendrier(img, 190, 880, 350, 1040, "LUNDI")
        D.postit(img, 375, 870, "Urgent", D._variante((255, 230, 110), rng), -6)
        D.postit(img, 990, 1010, "Café !", D._variante((150, 220, 255), rng), 5)
        poubelle(img, 900, S + 40)
        for k in range(3): D.boite(img, 600 + k * 60, 720 - k * 6, 650 + k * 60, 730 - k * 6, (240, 240, 236), 2)  # feuilles punaisées
    elif lieu == "cabinet_medical":
        poubelle(img, 760, S + 40, (230, 232, 236)); plante_haute(img, 280, S + 40, 0.8)
        D.boite(img, 880, S - 420, 1040, S - 330, (250, 250, 250), 5, 8); D.texte(img, "GANTS", 880, S - 420, 1040, S - 330, (60, 120, 200), 26)
    elif lieu == "bar":
        for x in (180, 900):                                               # tabourets
            D.boite(img, x - 60, S - 40, x + 60, S - 10, (180, 50, 50), 5, 12); D.boite(img, x - 8, S - 10, x + 8, S + 130, (60, 60, 66), 3)
            D.boite(img, x - 50, S + 128, x + 50, S + 140, (60, 60, 66), 3)
        D.texte(img, "OPEN", 820, 160, 1040, 260, (120, 255, 200), 50, contour=4, c_contour=(30, 120, 90))
    elif lieu == "salle_sport":
        D.poly(img, [(80, S + 260), (520, S + 260), (500, S + 200), (100, S + 200)], D._variante((120, 70, 160), rng), 5)    # tapis de yoga
        cv2.circle(img, (900, S + 120), 90, TRAIT, -1, cv2.LINE_AA); cv2.circle(img, (900, S + 120), 84, D._variante((80, 160, 220), rng), -1, cv2.LINE_AA)  # ballon
        cv2.ellipse(img, (900, S + 120), (84, 30), 0, 0, 360, D.fonce((80, 160, 220), 0.8), 4, cv2.LINE_AA)
        extincteur(img, 600, S + 30)
    elif lieu == "magasin":
        D.boite(img, 40, 260, 340, 340, (60, 130, 210), 5, 8); D.texte(img, "Rayon 4", 40, 260, 340, 340, (255, 255, 255), 40)
        D.boite(img, 740, 260, 1040, 340, (60, 130, 210), 5, 8); D.texte(img, "Caisses", 740, 260, 1040, 340, (255, 255, 255), 40)
        x0, y0 = 60, S + 60                                                     # caddie (D3)
        for k in range(6): D.ligne(img, (x0 + k * 40, y0), (x0 + 20 + k * 34, y0 + 150), (150, 155, 165), 4)
        cv2.polylines(img, [np.array([(x0, y0), (x0 + 240, y0), (x0 + 220, y0 + 150), (x0 + 20, y0 + 150)], np.int32)], True, TRAIT, 6, cv2.LINE_AA)
        D.ligne(img, (x0 + 240, y0), (x0 + 290, y0 - 40), TRAIT, 8)
        for xx in (x0 + 40, x0 + 200): cv2.circle(img, (xx, y0 + 180), 18, TRAIT, -1, cv2.LINE_AA)
        D.boite(img, 820, S + 60, 1020, S + 200, (250, 220, 90), 5, 6); D.texte(img, "PROMO", 820, S + 60, 1020, S + 200, (220, 40, 40), 44)   # présentoir
    elif lieu == "classe":
        for k, l in enumerate("ABCDEFGHIJ"):                               # frise de l'alphabet
            x = 30 + k * 104; D.boite(img, x, 150, x + 90, 240, D._variante(((240, 120, 100), (120, 180, 230), (250, 210, 90), (140, 200, 140))[k % 4], rng), 4, 8)
            D.texte(img, l + l.lower(), x, 150, x + 90, 240, TRAIT, 40)
        cv2.circle(img, (1000, 600), 70, TRAIT, -1, cv2.LINE_AA); cv2.circle(img, (1000, 600), 64, (110, 170, 230), -1, cv2.LINE_AA)   # globe
        for pts in ([(970, 570), (1010, 560), (1020, 600), (990, 620)], [(1020, 630), (1040, 640), (1030, 660)]): D.poly(img, pts, (110, 180, 110), 0)
        D.ligne(img, (1000, 670), (1000, 760), TRAIT, 8); D.boite(img, 950, 760, 1050, 780, (150, 110, 70), 4)
        D.boite(img, 300, S + 120, 400, S + 220, D._variante((200, 70, 70), rng), 5, 14)   # cartable
    elif lieu == "restaurant":
        porte_manteau(img, 560, S + 40, rng); plante_haute(img, 1010, S + 40, 0.7)
    elif lieu == "rue":
        poubelle(img, 120, S + 210, (60, 120, 80)); banc(img, 300, 620, S + 230)
        panneau_rue(img, 760, S + 230, "STOP")
        cv2.ellipse(img, (540, S + 560), (110, 34), 0, 0, 360, (50, 52, 58), -1, cv2.LINE_AA)    # bouche d'égout
        for k in range(-3, 4): D.ligne(img, (540 + k * 26, S + 540), (540 + k * 26, S + 580), (35, 36, 40), 4)
        for _ in range(6):                                                 # feuilles mortes
            x, y = rng.uniform(40, 1040), rng.uniform(S + 40, S + 230)
            cv2.ellipse(img, (int(x), int(y)), (12, 7), rng.uniform(0, 180), 0, 360, D._variante((210, 140, 60), rng), -1, cv2.LINE_AA)
