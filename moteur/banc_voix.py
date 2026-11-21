"""Banc d'essai permanent des voix (choix de l'auteur du 21 novembre 2026, idée 16) : de vraies vidéos dont on sait QUI dit QUOI
(tests/banc_voix/*.json : vérité phrase par phrase + répliques telles que le robot les avait faites ; *.opus : le son). À chaque
modification du robot, `python moteur/banc_voix.py` (ou le test TestBancVoix) mesure le temps de parole attribué au bon personnage,
avant et après les contrôles des voix (bulles mélangées coupées, hauteur, et l'empreinte vocale avec --ecapa) : une correction qui
en casse une autre se voit tout de suite. Ajouter une vidéo : son .opus + .json (même forme) dans tests/banc_voix."""
import copy, glob, json, os, subprocess, sys
import numpy as np
ICI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ICI)
DOSSIER = os.path.join(ICI, "..", "tests", "banc_voix")


def son(chemin, sr=22050):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", chemin, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


def score(reps, verite, roles):
    """Part du temps de parole (phrases de vérité) dite par le bon personnage."""
    bon = tot = 0.0
    for a, b, qui, _t in verite:
        for r in reps:
            o = min(b, float(r["_fin"])) - max(a, float(r["_deb"]))
            if o <= 0: continue
            tot += o
            if roles.get(r.get("p")) == qui: bon += o
    return bon / tot if tot else 0.0


def cas(nom, ecapa=False, journal=lambda m: None):
    import doublage, equipe
    D = json.load(open(os.path.join(DOSSIER, nom + ".json"), encoding="utf-8"))
    sig = son(os.path.join(DOSSIER, nom + ".opus"))
    genres = {"H": "homme", "F": "femme"}
    sk = {"repliques": copy.deepcopy(D["repliques_robot"]), "doublage": {}, "decoupage": [{"repliques": list(range(len(D["repliques_robot"])))}],
          "studio": {"personnages": {r: {"genre_vu": genres.get(g, "")} for r, g in D["roles"].items()}}}
    avant = score(sk["repliques"], D["verite"], D["roles"])
    j0 = doublage.journal; doublage.journal = journal
    try:
        n_s = doublage.scinder_melangees(sk, sig, 22050)
        if ecapa: n_h = equipe.voix_finales(sk, sig, 22050, None)
        else: n_h = equipe.hauteur_finale(sk, sk["repliques"], sorted(D["roles"]), sig, 22050, None, bavard=False)[1]
    finally: doublage.journal = j0
    return {"video": D.get("titre", nom), "avant": round(avant, 3), "apres": round(score(sk["repliques"], D["verite"], D["roles"]), 3),
            "coupees": n_s, "deplacees": n_h}


def tout(ecapa=False):
    return [cas(os.path.splitext(os.path.basename(f))[0], ecapa) for f in sorted(glob.glob(os.path.join(DOSSIER, "*.json")))]


if __name__ == "__main__":
    for r in tout(ecapa="--ecapa" in sys.argv):
        print(f"{r['video']} : {round(100 * r['avant'])} % -> {round(100 * r['apres'])} % du temps de parole au bon personnage "
              f"({r['coupees']} bulle(s) coupée(s), {r['deplacees']} réplique(s) déplacée(s))")
