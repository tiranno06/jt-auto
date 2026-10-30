import sys, cv2, numpy as np
import croquis as C, serie2_outils as O
W, H = 3000, 2000
img = C.papier(W, H, 22)
O.texte(img, "Actions et attitudes", W / 2, 14, 72, True)
A = [("Marcher", "heureux", ("course_ar", "course_av"), ("marche_av", "marche_ar"), None),
     ("Courir", "joie", ("course_av", "course_ar"), ("course_av", "course_ar"), None),
     ("Sauter de joie", "joie", ("en_lair", "en_lair"), ("saut", "saut"), None),
     ("Assis", "serein", ("genoux", "genoux"), ("assis", "assis"), "chaise"),
     ("Bras croisés", "fache", ("croises", "croises"), ("debout", "debout"), None),
     ("Mains aux hanches", "douteux", ("hanches", "hanches"), ("ecart", "ecart"), None),
     ("Au téléphone", "neutre", ("ballants", "joues"), ("debout", "debout"), "telephone"),
     ("Main à la bouche", "surpris", ("ballants", "bouche"), ("debout", "debout"), None),
     ("Réfléchit", "soucieux", ("croises", "menton"), ("debout", "debout"), None)]
coifs = [O.coiffure("courts", (90, 60, 40)), O.coiffure("queue", (150, 90, 50)), O.coiffure("courts", (40, 35, 35)), O.coiffure("longs", (60, 40, 30)),
         O.coiffure("carre", (180, 120, 60)), O.coiffure("boucles", (50, 35, 30)), O.coiffure("courts", (60, 45, 35)), O.coiffure("longs", (200, 150, 70)), O.coiffure("courts", (30, 30, 30))]
cols = [(240, 180, 60), (230, 110, 150), (90, 130, 190), (150, 110, 200), (200, 70, 70), (120, 170, 120), (60, 60, 70), (250, 200, 80), (110, 150, 200)]
for ligne, (taille, nom, R) in enumerate((("chibi", "Le petit", 112), ("grand", "Le grand", 86))):
    y_sol = 860 + ligne * 1000
    O.texte(img, nom, 60, y_sol - 730 if ligne == 0 else y_sol - 800, 50, True, centre=False)
    for k, (lab, e, bras, jambes, acc) in enumerate(A):
        x = 175 + k * 330
        if acc == "chaise": O.chaise(img, x + R * 0.1, y_sol, R * (1.0 if taille == "chibi" else 0.9), h=R * (1.25 if taille == "chibi" else 2.3) * 0.55 - R * 0.05)
        C.bonhomme(img, x, y_sol, R, e, bras=bras, jambes=jambes, taille=taille, graine=k + 20 * ligne, c_haut=cols[k],
                   c_bas=(60, 80, 130), extras=[coifs[k]], objet=C.tenir("telephone", 0.9) if acc == "telephone" else None)
        if jambes[0] not in ("saut",): C.ombre_sol(img, (x, y_sol + 6), R * 0.9)
        else: C.ombre_sol(img, (x, y_sol + 6), R * 0.6)
        O.texte(img, lab, x, y_sol + 34, 34)
cv2.imwrite(sys.argv[1], cv2.cvtColor(cv2.resize(img, (1500, 1000), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
