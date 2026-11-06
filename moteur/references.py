"""Images de référence (choix de l'auteur du 6 novembre 2026, idée 46) : 10 images types du dessin (petit et grand personnage,
femme, ado, senior, animal, métier, assis, deux personnages, décor croquis) comparées à chaque changement du code par les tests
(TestImagesDeReference). Un personnage cassé par une modification (bras qui disparaît, visage décalé, couleur fausse) fait échouer
les tests AVANT de fabriquer une vidéo.

Quand un changement du dessin est VOULU (validé par l'auteur) : refaire les images de référence avec
    python moteur/references.py --refaire
puis les regarder (tests/references/*.png) avant de les enregistrer."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "references")


def _perso(F, emo="neutre", bouche=0.0, costume=None, x=300, y=1050, assis=False, **pose):
    import marionnette as M, humain as HU, croquis as C, perso_croquis as P
    img = C.papier(600, 1100, graine=3)
    p = dict(M.pose_neutre(), x=x, y=y, s=1.0, t=0.0, emo=emo, bouche=bouche, costume=costume or {}, assis=assis, **pose)
    P.dessiner(img, F, HU._pose(F, p) if not F.get("espece") else p)
    return img


def images():
    """{nom: image BGR} : toujours les mêmes images pour le même code."""
    import humain as HU
    out = {}
    out["01_petit_joie"] = _perso(dict(HU.creer(2, genre="h", age=30), silhouette="petit"), "joie", 0.6,
                                  {"haut": "capuche", "c_haut": (90, 130, 190), "chapeau": "casquette"})
    out["02_grand_colere"] = _perso(dict(HU.creer(5, genre="h", age=40), silhouette="grand"), "colere", 0.8,
                                    {"haut": "chemise", "c_haut": (40, 40, 160), "bas": "jean"})
    out["03_femme_surprise"] = _perso(dict(HU.creer(7, genre="f", age=28, cheveux="queue"), silhouette="petit"), "surprise", 0.5,
                                      {"haut": "tshirt", "c_haut": (160, 80, 200), "bas": "jupe"})
    out["04_ado_triste"] = _perso(dict(HU.creer(11, genre="h", age=15), silhouette="grand"), "triste", 0.0,
                                  {"haut": "sweat", "c_haut": (60, 160, 60), "chapeau": "bonnet"})
    out["05_senior"] = _perso(dict(HU.creer(13, genre="f", age=72), silhouette="petit"), "neutre", 0.3,
                              {"haut": "gilet", "c_haut": (120, 120, 160), "details": ["lunettes_vue"]})
    out["06_chat"] = _perso(dict(HU.creer(1, genre="h", age=30), espece="chat"), "joie", 0.4)
    out["07_pompier"] = _perso(dict(HU.creer(17, genre="h", age=35), silhouette="grand"), "neutre", 0.2,
                               {"haut": "veste_pompier", "c_haut": (40, 40, 40), "chapeau": "casque_pompier", "metier": "pompier"})
    out["08_assis"] = _perso(dict(HU.creer(19, genre="f", age=45), silhouette="petit"), "joie", 0.0,
                             {"haut": "pull", "c_haut": (30, 120, 200)}, assis=True)
    import marionnette as M, croquis as C, perso_croquis as P
    img = C.papier(1080, 1100, graine=4)                                   # deux personnages côte à côte, bras écartés
    for g, x, emo in ((23, 300, "fache"), (29, 780, "gene")):
        F = dict(HU.creer(g, genre="h" if g == 23 else "f", age=30), silhouette="grand" if g == 23 else "petit")
        p = dict(M.pose_neutre(), x=x, y=1050, s=1.0, t=0.0, emo=emo, bouche=0.3, costume={"haut": "tshirt", "c_haut": (200, 120, 40)})
        P.dessiner(img, F, HU._pose(F, p))
    out["09_deux_persos"] = img
    try:
        import decor_dessin as DD, cv2
        d = DD.dessiner("salon", None, graine=7)["fond"]
        d = np.ascontiguousarray(np.asarray(d)[..., :3])
        out["10_decor_salon"] = cv2.resize(C.croquifier(d, C.papier(d.shape[1], d.shape[0], 40), graine=0), (540, 960), interpolation=cv2.INTER_AREA)
    except Exception as e: print(f"décor de référence impossible ({e})")
    import cv2                                                             # moitié de la taille : assez pour voir un dessin cassé
    return {k: cv2.resize(v, (v.shape[1] // 2, v.shape[0] // 2), interpolation=cv2.INTER_AREA) for k, v in out.items()}


def ecart(a, b):
    """(écart moyen, part des pixels nettement différents) entre deux images de même taille."""
    if a.shape != b.shape: return 255.0, 1.0
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(2)
    return float(d.mean()), float((d > 24).mean())


def lire(nom):
    """Image de référence enregistrée (dans le même ordre de couleurs que le dessin), ou None."""
    import cv2
    im = cv2.imread(os.path.join(DOSSIER, nom + ".png"))
    return None if im is None else cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


def refaire():
    import cv2
    os.makedirs(DOSSIER, exist_ok=True)
    for nom, im in images().items():
        cv2.imwrite(os.path.join(DOSSIER, nom + ".png"), cv2.cvtColor(im, cv2.COLOR_RGB2BGR)); print("référence :", nom)


if __name__ == "__main__":
    if "--refaire" in sys.argv: refaire()
    else:
        import cv2
        for nom, im in images().items():
            ref = lire(nom)
            print(nom, "absente" if ref is None else "écart moyen %.2f, %.2f %% de pixels différents" % (ecart(im, ref)[0], 100 * ecart(im, ref)[1]))
