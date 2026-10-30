import sys, cv2, numpy as np
sys.path.insert(0, sys.argv[1]); import croquis as C
noms = [("heureux", "Heureux"), ("triste", "Triste"), ("surpris", "Surpris"), ("colere", "En colère"), ("fache", "Fâché"), ("etonne", "Étonné"), ("joie", "Plein de joie"),
        ("serein", "Serein"), ("honteux", "Honteux"), ("soucieux", "Soucieux"), ("douteux", "Douteux"), ("fatigue", "Fatigué"), ("satisfait", "Satisfait"), ("reveur", "Rêveur"), ("malicieux", "Malicieux")]
W, H = 760 * 2, 504 * 2
img = C.papier(W, H, 3)
for k, (e, lab) in enumerate(noms):
    cx, cy = 175 + (k % 5) * 290, 230 + (k // 5) * 320
    C.tete(img, (cx, cy), 95, e, graine=k, nez=False)
    cv2.putText(img, lab, (int(cx - len(lab) * 12), int(cy + 140)), cv2.FONT_HERSHEY_SIMPLEX, 1.1, C.ENCRE, 2, cv2.LINE_AA)
cv2.imwrite(sys.argv[2], cv2.cvtColor(cv2.resize(img, (760, 504), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
