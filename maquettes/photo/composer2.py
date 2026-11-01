"""Planche 2 (moins photo réaliste) : photo / photo adoucie par le code (gratuit) / peinture semi-réaliste (IA), mêmes personnages."""
import sys, os, cv2, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(D, "..", "croquis"), os.path.join(D, "..", "..", "moteur")]
import croquis as C, serie2_outils as O
LIEUX = ["salon", "cuisine", "chambre", "rue"]
PERSOS = [dict(x=330, taille="chibi", age="adulte", expr="fache", bras=("hanches", "ballants"), c_haut=(200, 70, 60), extras=[O.coiffure("carre", (60, 40, 30))], g=1),
          dict(x=760, taille="grand", age="ado", expr="honteux", bras=("ballants", "tete"), haut="pull", c_haut=(70, 110, 170), extras=[O.coiffure("courts", (40, 35, 35))], g=2)]
w, h = 600, 1066

def adoucir(rgb):
    """Photo rendue « un peu peinte » : détails fins lissés, aplats doux, couleurs un peu plus chaudes et vives."""
    s = cv2.stylization(rgb, sigma_s=45, sigma_r=0.3)
    s = cv2.addWeighted(s, 0.8, cv2.bilateralFilter(rgb, 9, 60, 9), 0.2, 0)
    hsv = cv2.cvtColor(s, cv2.COLOR_RGB2HSV).astype(np.float32); hsv[..., 1] *= 1.18; hsv[..., 2] = hsv[..., 2] * 0.95 + 14
    s = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
    s *= np.array([1.04, 1.0, 0.94]); return np.clip(s, 0, 255).astype(np.uint8)

def charger(f):
    if not os.path.exists(f): return None
    ph = cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2RGB); hh, ww = ph.shape[:2]; c = max(0, int(ww - hh * w / h) // 2)
    return cv2.resize(ph[:, c:ww - c], (w, h), interpolation=cv2.INTER_AREA)

def panneau(img, x0, y0, fond, titre):
    img[y0:y0 + h, x0:x0 + w] = fond; k = w / 1080
    for p in PERSOS:
        R = O.AGES[p["taille"]][p["age"]] * k * 1.4; sol = y0 + 1760 * k; x = x0 + p["x"] * k      # pieds au premier plan, sur le sol
        C.ombre_sol(img, (x, sol + 4), R * 0.9)
        C.bonhomme(img, x, sol, R, p["expr"], bras=p["bras"], taille=p["taille"], graine=p["g"], haut=p.get("haut", "tshirt"),
                   c_haut=p["c_haut"], c_bas=(60, 80, 130), extras=p["extras"])
    O.bulle(img, x0 + 330 * k, y0 + 760 * k, "Tu as encore pris mon pull ?!", 22, (0, 40))
    C.encre(img, [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)], 4, ferme=True, effile=False)
    O.texte(img, titre, x0 + w / 2, y0 + h + 12, 34, True)

os.makedirs(os.path.join(D, "visuels2"), exist_ok=True)
for i, lieu in enumerate(LIEUX):
    ph = charger(os.path.join(D, "decors", f"photo_{i}.png")); pe = charger(os.path.join(D, "peints", f"peint_{i}.png"))
    img = C.papier(3 * w + 4 * 50, h + 140, 24)
    panneau(img, 50, 40, ph, "1. Photo (essai d'avant)")
    panneau(img, 100 + w, 40, adoucir(ph), "2. Photo adoucie")
    panneau(img, 150 + 2 * w, 40, pe if pe is not None else np.full_like(ph, 200), "3. Peinture semi-réaliste")
    cv2.imwrite(os.path.join(D, "visuels2", f"{i + 1}_{lieu}.jpg"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print("ok", lieu)
