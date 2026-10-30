import sys, cv2, numpy as np, math
sys.path.insert(0, sys.argv[1]); import croquis as C
L = [("joie", "Joie", ("en_lair", "en_lair"), ("saut", "saut"), (235, 200, 70), {}),
     ("triste", "Tristesse", ("genoux", "genoux"), ("accroupi", "accroupi"), (80, 120, 180), {}),
     ("colere", "Colère", ("poing", "poing"), ("ecart", "ecart"), (205, 70, 65), {}),
     ("peur", "Peur", ("tremble", "tremble"), ("debout", "debout"), (110, 150, 200), {}),
     ("surpris", "Surprise", ("joues", "joues"), ("debout", "debout"), (230, 190, 70), {}),
     ("degout", "Dégoût", ("ballants", "ballants"), ("debout", "debout"), (110, 170, 100), {}),
     ("amour", "Amour", ("coeur", "coeur"), ("debout", "debout"), (110, 160, 210), {"coeurs": 1}),
     ("anxiete", "Anxiété", ("bouche", "bouche"), ("debout", "debout"), (120, 130, 150), {}),
     ("stress", "Stress", ("tete", "tete"), ("debout", "debout"), (230, 230, 225), {"gribouillis": 1}),
     ("fierte", "Fierté", ("hanches", "hanches"), ("debout", "debout"), (235, 195, 70), {"etincelle": 1}),
     ("culpabilite", "Culpabilité", ("tenir", "tenir"), ("debout", "debout"), (110, 120, 130), {}),
     ("espoir", "Espoir", ("joint", "joint"), ("debout", "debout"), (110, 170, 120), {"soleil": 1}),
     ("solitude", "Solitude", ("genoux", "genoux"), ("accroupi", "accroupi"), (70, 100, 160), {"nuage": 1}),
     ("excitation", "Excitation", ("en_lair", "poing"), ("course_av", "course_ar"), (60, 70, 120), {}),
     ("emerveillement", "Émerveillement", ("ballants", "ballants"), ("debout", "debout"), (80, 130, 200), {"etoiles": 1}),
     ("ennui", "Ennui", ("joues", "joues"), ("accroupi", "accroupi"), (60, 60, 80), {}),
     ("frustration", "Frustration", ("poing", "poing"), ("debout", "debout"), (240, 240, 235), {}),
     ("gratitude", "Gratitude", ("coeur", "coeur"), ("debout", "debout"), (235, 200, 70), {"coeur": 1})]
def coeur(img, c, r, col=(220, 70, 85)):
    pts = [(c[0] + r * 16 * math.sin(t) ** 3 / 16, c[1] - r * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 16) for t in np.linspace(0, 2 * math.pi, 40)]
    cv2.fillPoly(img, [C._pts(pts)], col, C.AA, 2); C.encre(img, pts, r * 0.12, ferme=True)
def etoile(img, c, r, col=(245, 205, 60)):
    pts = [(c[0] + (r if k % 2 == 0 else r * 0.3) * math.cos(math.radians(-90 + 45 * k)), c[1] + (r if k % 2 == 0 else r * 0.3) * math.sin(math.radians(-90 + 45 * k))) for k in range(8)]
    cv2.fillPoly(img, [C._pts(pts)], col, C.AA, 2); C.encre(img, pts, r * 0.1, ferme=True)
def extras(img, tc, R, d):
    if d.get("coeurs"):
        for u, v in ((-1.3, -0.4), (1.25, -0.7), (-1.15, 0.6), (1.3, 0.5)): coeur(img, (tc[0] + u * R, tc[1] + v * R), R * 0.16)
    if d.get("coeur"): coeur(img, (tc[0] + R * 1.2, tc[1] + R * 1.2), R * 0.13)
    if d.get("etoiles"):
        for u, v in ((-1.3, -0.8), (1.3, -0.6), (-1.2, 0.7), (1.35, 0.6), (0.2, -1.4)): etoile(img, (tc[0] + u * R, tc[1] + v * R), R * 0.15)
    if d.get("etincelle"): etoile(img, (tc[0] + R * 1.3, tc[1] + R * 0.2), R * 0.18)
    if d.get("soleil"):
        c = (tc[0] + R * 1.4, tc[1] - R * 1.0); cv2.circle(img, C._pts([c])[0], int(R * 0.22 * 4), (245, 200, 70), -1, C.AA, 2)
        for k in range(10): a = math.radians(k * 36); C.encre(img, [(c[0] + R * 0.3 * math.cos(a), c[1] + R * 0.3 * math.sin(a)), (c[0] + R * 0.45 * math.cos(a), c[1] + R * 0.45 * math.sin(a))], R * 0.03, coul=(230, 160, 40))
    if d.get("nuage"):
        c = (tc[0] + R * 1.2, tc[1] - R * 1.05)
        for u, v, r in ((-0.2, 0, 0.2), (0.1, -0.12, 0.25), (0.35, 0, 0.18)): cv2.circle(img, C._pts([(c[0] + u * R, c[1] + v * R)])[0], int(R * r * 4), (95, 115, 150), -1, C.AA, 2)
    if d.get("gribouillis"):
        rng = np.random.default_rng(3); pts = [(tc[0] + R * 0.6 * math.cos(t) + rng.normal(0, R * 0.08), tc[1] - R * 1.05 + R * 0.22 * math.sin(t * 1.0)) for t in np.linspace(0, 12 * math.pi, 60)]
        C.encre(img, pts, R * 0.025)
W, H = 776 * 2, 560 * 2
img = C.papier(W, H, 7)
cv2.putText(img, "Emotions", (70, 110), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 2.6, C.ENCRE, 5, cv2.LINE_AA)
for k, (e, lab, br, jb, ch, d) in enumerate(L):
    cx, sol = 155 + (k % 6) * 250, 380 + (k // 6) * 340
    tc = C.bonhomme(img, cx, sol, 56, e, bras=br, jambes=jb, c_haut=ch, c_bas=(60, 75, 110), graine=k, teint=(212, 228, 175) if e == "degout" else None)
    extras(img, tc, 56, d)
    cv2.putText(img, lab, (int(cx - len(lab) * 13), sol + 62), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.45, C.ENCRE, 3, cv2.LINE_AA)
cv2.imwrite(sys.argv[2], cv2.cvtColor(cv2.resize(img, (776, 560), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
