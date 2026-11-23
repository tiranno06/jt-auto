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


DOSSIERS = [DOSSIER, os.path.join(ICI, "..", "episodes", "banc_voix")]   # (2e dossier : cas ajoutés par le robot, 23 novembre)
GENRES = {"H": "homme", "F": "femme", "h": "homme", "f": "femme", "homme": "homme", "femme": "femme"}


def cas(nom, ecapa=False, journal=lambda m: None, dossier=None):
    import doublage, equipe
    dossier = dossier or next((d for d in DOSSIERS if os.path.exists(os.path.join(d, nom + ".json"))), DOSSIER)
    D = json.load(open(os.path.join(dossier, nom + ".json"), encoding="utf-8"))
    sig = son(os.path.join(dossier, nom + ".opus"))
    gen = D.get("genres") or D["roles"]                                     # {rôle: homme / femme} (anciens cas : lettres H / F)
    sk = {"repliques": copy.deepcopy(D["repliques_robot"]), "doublage": {}, "decoupage": [{"repliques": list(range(len(D["repliques_robot"])))}],
          "studio": {"personnages": {r: {"genre_vu": GENRES.get(str(gen.get(r) or ""), "")} for r in D["roles"]}}}
    avant = score(sk["repliques"], D["verite"], D["roles"])
    j0 = doublage.journal; doublage.journal = journal
    try:
        n_s = doublage.scinder_melangees(sk, sig, 22050)
        if ecapa: n_h = equipe.voix_finales(sk, sig, 22050, None)
        else: n_h = equipe.hauteur_finale(sk, sk["repliques"], sorted(D["roles"]), sig, 22050, None, bavard=False)[1]
    finally: doublage.journal = j0
    return {"video": D.get("titre", nom), "avant": round(avant, 3), "apres": round(score(sk["repliques"], D["verite"], D["roles"]), 3),
            "coupees": n_s, "deplacees": n_h, "attendu": D.get("attendu")}


def tout(ecapa=False):
    return [cas(os.path.splitext(os.path.basename(f))[0], ecapa, dossier=os.path.dirname(f))
            for d in DOSSIERS for f in sorted(glob.glob(os.path.join(d, "*.json")))]


def ajouter(nom, titre, reps_robot, reps_vraies, audio, genres=None, journal=print):
    """Nouveau cas du banc (23 novembre, idée 10) : reps_robot = répliques faites par le robot, reps_vraies = qui dit vraiment quoi
    (« Corriger qui parle » de l'auteur, ou vidéo dont l'auteur a dit « les voix sont justes ») ; audio = son de la vidéo (même
    chronologie que les répliques). Le score obtenu aujourd'hui (moins 2 points) devient le minimum exigé par le test : une
    modification du robot qui ferait moins bien sur ce cas est refusée. Renvoie le résultat du cas, ou None."""
    d = DOSSIERS[1]; os.makedirs(d, exist_ok=True)
    garder = ("p", "t", "_deb", "_fin", "_mots")
    robot = [{k: r[k] for k in garder if k in r} for r in reps_robot if r.get("_deb") is not None and r.get("_fin") is not None]
    verite = [[round(float(r["_deb"]), 2), round(float(r["_fin"]), 2), r["p"], str(r.get("t") or "")[:60]] for r in reps_vraies
              if r.get("_deb") is not None and r.get("_fin") is not None and r.get("p") not in (None, "narrateur")]
    roles = sorted({v[2] for v in verite})
    if len(roles) != 2 or len(verite) < 6: journal(f"  banc d'essai : {nom} pas gardé (il faut 2 personnages et 6 répliques)"); return None
    r_ = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", audio, "-ac", "1", "-ar", "24000", "-c:a", "libopus", "-b:a", "24k",
                         os.path.join(d, nom + ".opus")], capture_output=True)                 # (libopus : 24 kHz ; relu à 22 050 Hz par son())
    if r_.returncode:
        journal(f"  banc d'essai : son illisible ({r_.stderr[:100]})")
        if os.path.exists(os.path.join(d, nom + ".opus")): os.remove(os.path.join(d, nom + ".opus"))
        return None
    D = {"titre": titre, "roles": {r: r for r in roles}, "genres": {r: (genres or {}).get(r, "") for r in roles},
         "verite": verite, "repliques_robot": robot}
    json.dump(D, open(os.path.join(d, nom + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    try: res = cas(nom, dossier=d)
    except Exception as e:
        journal(f"  banc d'essai : cas illisible ({str(e)[:100]})")
        for x in (".json", ".opus"): os.remove(os.path.join(d, nom + x))
        return None
    D["attendu"] = round(max(0.0, res["apres"] - 0.02), 3)
    json.dump(D, open(os.path.join(d, nom + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    journal(f"  banc d'essai des voix : « {titre} » ajouté ({round(100 * res['avant'])} % -> {round(100 * res['apres'])} % au bon personnage)")
    return res


def ajouter_juste(fichier, journal=print):
    """Bouton « ✅ Les voix sont justes » d'une fiche (banc.yml) : la vidéo, jugée juste par l'auteur, devient un cas du banc (robot =
    vérité) : une modification du robot qui la rendrait fausse est refusée par les tests."""
    import doublage
    base = os.path.splitext(os.path.basename(fichier))[0]
    sk = json.load(open(os.path.join(ICI, "..", "episodes", "sketchs", base + ".json"), encoding="utf-8"))
    if not sk.get("doublage"): journal("  banc d'essai : pas une vidéo sur un son TikTok"); return None
    doublage.depuis_sketch(sk)                                             # son d'origine re-téléchargé, mêmes coupes (sk["doublage"]["piste"])
    P_ = (sk.get("studio") or {}).get("personnages") or {}
    return ajouter(base, str(sk.get("titre_accroche") or sk.get("sujet") or base), sk["repliques"], sk["repliques"], sk["doublage"]["piste"],
                   {r: str((P_.get(r) or {}).get("genre_vu") or "") for r in P_}, journal)


if __name__ == "__main__" and "--ajouter" in sys.argv:
    sys.exit(0 if ajouter_juste(sys.argv[sys.argv.index("--ajouter") + 1]) else 1)

if __name__ == "__main__":
    for r in tout(ecapa="--ecapa" in sys.argv):
        print(f"{r['video']} : {round(100 * r['avant'])} % -> {round(100 * r['apres'])} % du temps de parole au bon personnage "
              f"({r['coupees']} bulle(s) coupée(s), {r['deplacees']} réplique(s) déplacée(s))")
