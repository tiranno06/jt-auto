"""Planche de comparaison : à gauche le décor actuel (croquis), à droite le décor photo, mêmes personnages croquis."""
import sys, os, cv2, numpy as np
sys.path[:0] = [os.path.join(os.path.dirname(__file__), "..", "croquis"), os.path.join(os.path.dirname(__file__), "..", "..", "moteur")]
import croquis as C, serie2_outils as O
LIEUX = [("salon", "Salon"), ("cuisine", "Cuisine"), ("chambre", "Chambre"), ("rue", "Rue")]
PERSOS = [dict(x=330, taille="chibi", age="adulte", expr="fache", bras=("hanches", "ballants"), c_haut=(200, 70, 60), extras=[O.coiffure("carre", (60, 40, 30))], g=1),
          dict(x=760, taille="grand", age="ado", expr="honteux", bras=("ballants", "tete"), haut="pull", c_haut=(70, 110, 170), extras=[O.coiffure("courts", (40, 35, 35))], g=2)]
w, h = 720, 1280

def persos(img, x0, y0):
    k = w / 1080
    for p in PERSOS:
        R = O.AGES[p["taille"]][p["age"]] * k * 1.4; sol = y0 + 1500 * k; x = x0 + p["x"] * k
        C.ombre_sol(img, (x, sol + 4), R * 0.9)
        C.bonhomme(img, x, sol, R, p["expr"], bras=p["bras"], taille=p["taille"], graine=p["g"], haut=p.get("haut", "tshirt"),
                   c_haut=p["c_haut"], c_bas=(60, 80, 130), extras=p["extras"])
    O.bulle(img, x0 + 330 * k, y0 + 560 * k, "Tu as encore pris mon pull ?!", 26, (0, 40))

for i, (lieu, titre) in enumerate(LIEUX):
    W, H = 1600, 1460
    img = C.papier(W, H, 24)
    O.scene(img, 60, 60, lieu, PERSOS, "Aujourd'hui (croquis)", graine=31 + i,
            bulles=[(330, 560, "Tu as encore pris mon pull ?!", 26, (0, 40))])
    f = os.path.join(os.path.dirname(__file__), "decors", f"photo_{i}.png")
    ph = cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2RGB) if os.path.exists(f) else np.full((1536, 880, 3), 200, np.uint8)
    hh, ww = ph.shape[:2]; c = int(ww - hh * w / h) // 2                  # recadrage 9:16
    ph = cv2.resize(ph[:, max(0, c):ww - max(0, c)], (w, h), interpolation=cv2.INTER_AREA)
    x0 = 820; img[60:60 + h, x0:x0 + w] = ph
    persos(img, x0, 60)
    C.encre(img, [(x0, 60), (x0 + w, 60), (x0 + w, 60 + h), (x0, 60 + h)], 4, ferme=True, effile=False)
    O.texte(img, "Décor photo réaliste", x0 + w / 2, 60 + h + 14, 40, True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "visuels"), exist_ok=True)
    cv2.imwrite(os.path.join(os.path.dirname(__file__), "visuels", f"{i + 1}_{lieu}.jpg"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print("ok", lieu)
