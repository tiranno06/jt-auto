import sys, cv2, numpy as np
sys.path.insert(0, sys.argv[1]); import croquis as C
X = C.chapeau; T = C.tenir; B = C.deco_buste
L = [("Pompier", "heureux", (210, 70, 40), X("casque_pompier"), T("lance"), [B("bandes")]),
     ("Policier", "neutre", (40, 55, 100), X("casquette_officier"), T("talkie"), [B("badge")]),
     ("Médecin", "neutre", (248, 248, 246), None, T("porte_bloc"), [B("blouse"), B("stetho")]),
     ("Infirmier(ère)", "heureux", (120, 180, 225), X("calot_croix"), T("seringue"), []),
     ("Enseignant", "neutre", (150, 110, 80), None, T("livre"), [X("lunettes")]),
     ("Chef cuisinier", "heureux", (250, 250, 248), X("toque"), T("poele"), [B("boutons")]),
     ("Boulanger", "heureux", (235, 210, 170), X("calot"), T("baguettes"), []),
     ("Ingénieur", "neutre", (110, 150, 200), X("casque_chantier"), T("plans"), []),
     ("Électricien", "neutre", (110, 150, 200), X("casque_chantier"), T("tournevis"), []),
     ("Plombier", "heureux", (200, 60, 60), X("casquette", (60, 90, 170)), T("cle_molette"), [B("salopette")]),
     ("Mécanicien", "neutre", (70, 100, 160), None, T("cle_molette"), [B("salopette")]),
     ("Vétérinaire", "heureux", (248, 248, 246), None, T("porte_bloc"), [B("blouse"), B("stetho")]),
     ("Artiste", "malicieux", (235, 230, 215), X("beret"), T("palette"), [B("taches")]),
     ("Musicien", "heureux", (90, 140, 200), None, T("guitare", 0.8), []),
     ("Serveur", "neutre", (35, 35, 42), None, T("plateau"), [B("noeud")]),
     ("Pilote", "neutre", (35, 45, 80), X("casquette_officier", (35, 45, 80)), None, [X("lunettes_soleil"), B("badge")]),
     ("Scientifique", "neutre", (248, 248, 246), None, T("eprouvette"), [X("lunettes"), B("blouse")]),
     ("Web développeur", "neutre", (70, 70, 80), X("casque_audio"), T("ordinateur"), []),
     ("Agriculteur", "heureux", (200, 80, 70), X("chapeau_paille"), T("fourche", 0.8), [B("salopette")]),
     ("Astronaute", "emerveillement", (238, 240, 245), X("casque_astronaute"), None, [B("badge")])]
W, H = 1536 * 2, 520 * 2
img = C.papier(W, H, 9)
cv2.putText(img, "Differents metiers", (70, 110), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 2.6, C.ENCRE, 5, cv2.LINE_AA)
for k, (lab, e, ch, chap, outil, deco) in enumerate(L):
    cx, sol = 150 + (k % 10) * 300, 470 + (k // 10) * 480
    cb = (60, 90, 150) if any(d.__qualname__ for d in deco) and lab in ("Plombier", "Mécanicien", "Agriculteur") else (55, 60, 75)
    C.bonhomme(img, cx, sol, 82, e, bras=("ballants", "tenir"), c_haut=ch, c_bas=cb, graine=k, haut="pull" if lab in ("Médecin", "Vétérinaire", "Scientifique", "Policier", "Pilote", "Serveur", "Pompier", "Chef cuisinier", "Astronaute") else "tshirt",
               chapeau=chap, objet=outil, extras=deco)
    cv2.putText(img, lab, (int(cx - len(lab) * 13), sol + 62), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.4, C.ENCRE, 3, cv2.LINE_AA)
cv2.imwrite(sys.argv[2], cv2.cvtColor(cv2.resize(img, (1536, 520), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
