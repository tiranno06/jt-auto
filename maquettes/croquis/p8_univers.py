import sys, cv2, numpy as np
import croquis as C, serie2_outils as O
W, H = 3200, 1500
img = C.papier(W, H, 23)
X, Co = C.chapeau, O.coiffure
S = [("salon", "La famille", "soir", [
        dict(x=200, taille="grand", age="adulte", expr="fache", bras=("hanches", "hanches"), c_haut=(90, 130, 190), extras=[Co("courts", (60, 45, 35))], g=1),
        dict(x=530, taille="chibi", age="enfant", expr="honteux", bras=("ballants", "bouche"), c_haut=(240, 180, 60), extras=[Co("courts", (90, 60, 40))], g=2),
        dict(x=870, taille="chibi", age="senior", expr="heureux", c_haut=(140, 170, 140), haut="pull", extras=[Co("chignon", (225, 225, 228)), X("lunettes"), O.rides], g=3)],
      [(250, 470, "C'était qui ?!", 34, (-10, 40)), (640, 600, "Pas moi !", 30, (-60, 40))]),
     ("classe", "Le lycée", "matin", [
        dict(x=260, taille="chibi", age="ado", expr="malicieux", bras=("ballants", "telephone"), c_haut=(150, 110, 200), extras=[Co("longs", (60, 40, 30))], objet=C.tenir("telephone", 0.9), g=4),
        dict(x=780, taille="grand", age="adulte", expr="colere", bras=("croises", "croises"), c_haut=(150, 110, 80), haut="pull", extras=[Co("courts", (50, 40, 35)), X("lunettes")], g=5)],
      [(700, 540, "Le portable !", 36, (40, 40))]),
     ("bureau", "Le travail", "jour", [
        dict(x=280, taille="grand", age="adulte", expr="stress", bras=("tete", "tete"), c_haut=(250, 250, 248), extras=[Co("courts", (30, 30, 30))], g=6),
        dict(x=780, taille="chibi", age="adulte", expr="douteux", bras=("hanches", "menton"), c_haut=(60, 60, 70), haut="pull", extras=[Co("carre", (180, 120, 60))], g=7)],
      [(380, 560, "La réunion, c'est maintenant ?", 28, (-60, 40)), (790, 700, "Depuis 10 min.", 30, (0, 40))]),
     ("restaurant", "Le couple", "soir", [
        dict(x=300, taille="chibi", age="adulte", expr="amour", bras=("coeur", "coeur"), c_haut=(200, 70, 70), extras=[Co("longs", (200, 150, 70))], g=8),
        dict(x=760, taille="grand", age="adulte", expr="surpris", bras=("ballants", "bouche"), c_haut=(40, 40, 46), haut="pull", extras=[Co("courts", (60, 45, 35)), C.deco_buste("noeud")], g=9)],
      [(300, 640, "Tu as oublié ?", 32, (0, 40)), (740, 500, "…notre anniversaire ?!", 28, (20, 40))])]
for i, (lieu, titre, moment, persos, bulles) in enumerate(S):
    O.scene(img, 60 + i * 785, 60, lieu, persos, titre, moment, graine=11 + i, bulles=bulles)
cv2.imwrite(sys.argv[1], cv2.cvtColor(cv2.resize(img, (1600, 750), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
