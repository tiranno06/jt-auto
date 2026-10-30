import sys, cv2, numpy as np
import croquis as C, serie2_outils as O
import vehicules as V
W, H = 3200, 2050
img = C.papier(W, H, 24)
X, Co, T, B = C.chapeau, O.coiffure, C.tenir, C.deco_buste
S = [("caserne", "La caserne", "jour", None, [
        dict(x=230, taille="grand", age="adulte", expr="heureux", bras=("ballants", "tenir"), haut="pull", c_haut=(200, 70, 40), c_bas=(200, 70, 40), chapeau=X("casque_pompier"), objet=T("lance"), extras=[B("bandes")], g=1),
        dict(x=850, taille="chibi", age="enfant", expr="emerveillement", bras=("ballants", "coeur"), c_haut=(240, 180, 60), extras=[Co("courts", (90, 60, 40))], g=2)],
      [(560, 560, "Je peux monter ?", 30, (100, 40))]),
     ("rue", "La rue (voiture de police)", "soir", ("police", 700, 40, 1), [
        dict(x=780, taille="chibi", age="adulte", expr="fache", bras=("hanches", "tenir"), haut="pull", c_haut=(40, 55, 100), c_bas=(40, 55, 100), chapeau=X("casquette_officier"), objet=T("talkie"), extras=[B("badge")], g=3),
        dict(x=300, taille="grand", age="ado", expr="honteux", bras=("ballants", "tete"), c_haut=(60, 60, 70), extras=[Co("courts", (40, 35, 35))], g=4)],
      [(760, 560, "Papiers, s'il vous plaît.", 26, (0, 40))]),
     ("ferme", "La ferme (tracteur)", "matin", ("tracteur", 560, 520, -1), [
        dict(x=270, taille="chibi", age="senior", expr="heureux", bras=("ballants", "tenir"), c_haut=(200, 80, 70), c_bas=(60, 90, 150), chapeau=X("chapeau_paille"), objet=T("fourche", 0.8), extras=[B("salopette"), O.moustache], g=5)],
      [(330, 640, "Debout les poules !", 30, (0, 40))]),
     ("garage", "Le garage", "jour", None, [
        dict(x=260, taille="chibi", age="adulte", expr="douteux", bras=("ballants", "tenir"), c_haut=(200, 60, 60), c_bas=(60, 90, 150), chapeau=X("casquette", (60, 90, 170)), objet=T("cle_molette"), extras=[B("salopette")], g=6),
        dict(x=790, taille="grand", age="adulte", expr="stress", bras=("joint", "joint"), haut="pull", c_haut=(110, 150, 200), extras=[Co("carre", (60, 40, 30))], g=7)],
      [(330, 640, "Ah… c'est le moteur.", 28, (0, 40)), (780, 520, "C'est grave ?", 30, (0, 40))])]
for i, (lieu, titre, moment, veh, persos, bulles) in enumerate(S):
    O.scene(img, 60 + i * 785, 60, lieu, persos, titre, moment, graine=31 + i, bulles=bulles, vehicule=veh)
O.texte(img, "Les véhicules des métiers", W / 2, 1450, 56, True)
x = 70
for nom, l in (("camion_pompier", 700), ("police", 640), ("ambulance", 640), ("tracteur", 520), ("fusee", 230)):
    im = V.VEHICULES[nom](1, l); hs = V.hauteur_sol(nom, l)
    sol = 1960 if nom != "fusee" else 1990
    O.poser(img, im, x, int(sol - hs), img); C.ombre_sol(img, (x + im.shape[1] / 2, sol + 4), im.shape[1] * 0.45)
    x += im.shape[1] + 30
cv2.imwrite(sys.argv[1], cv2.cvtColor(cv2.resize(img, (1600, 1025), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
