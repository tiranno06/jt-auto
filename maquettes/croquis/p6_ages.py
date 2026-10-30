import sys, cv2, numpy as np
import croquis as C, serie2_outils as O
W, H = 3000, 2000
img = C.papier(W, H, 21)
O.texte(img, "Les deux silhouettes, pour tous les âges", W / 2, 14, 72, True)
pers = [("enfant", "Enfant", "heureux", O.coiffure("courts", (90, 60, 40)), (240, 180, 60), (70, 95, 150), []),
        ("enfant", "Enfant", "joie", O.coiffure("queue", (150, 90, 50)), (230, 110, 150), (70, 95, 150), []),
        ("ado", "Ado", "douteux", O.coiffure("courts", (40, 35, 35)), (60, 60, 70), (60, 80, 130), [C.chapeau("casquette", (200, 60, 60))]),
        ("ado", "Ado", "malicieux", O.coiffure("longs", (60, 40, 30)), (150, 110, 200), (40, 40, 50), []),
        ("adulte", "Adulte", "neutre", O.coiffure("courts", (60, 45, 35)), (90, 130, 190), (55, 60, 75), []),
        ("adulte", "Adulte", "heureux", O.coiffure("carre", (180, 120, 60)), (200, 70, 70), (55, 60, 75), []),
        ("senior", "Senior", "serein", O.coiffure("blancs", (225, 225, 228)), (150, 130, 100), (90, 90, 100), [C.chapeau("lunettes"), O.rides, O.moustache]),
        ("senior", "Senior", "heureux", O.coiffure("chignon", (225, 225, 228)), (140, 170, 140), (110, 90, 130), [C.chapeau("lunettes"), O.rides])]
for ligne, (taille, nom) in enumerate((("chibi", "Le petit (grosse tête, petit corps habillé)"), ("grand", "Le grand (stickman géant, longues jambes)"))):
    y_sol = 860 + ligne * 1000
    O.texte(img, nom, 60, y_sol - 730 if ligne == 0 else y_sol - 800, 50, True, centre=False)
    for k, (age, lab, e, coif, ch, cb, ext) in enumerate(pers):
        x = 200 + k * 372
        R = O.AGES[taille][age]
        C.bonhomme(img, x, y_sol, R, e, bras=("ballants", "salut" if k in (1, 5) else "ballants"), taille=taille, graine=k + 10 * ligne,
                   haut="pull" if age == "senior" else "tshirt", c_haut=ch, c_bas=cb, extras=[coif] + ext)
        C.ombre_sol(img, (x, y_sol + 6), R * 0.9)
        O.texte(img, lab, x, y_sol + 34, 40)
cv2.imwrite(sys.argv[1], cv2.cvtColor(cv2.resize(img, (1500, 1000), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
