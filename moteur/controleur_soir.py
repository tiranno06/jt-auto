"""Robot « contrôleur du soir » (choix de l'auteur du 22 novembre 2026). Vers 21 h (heure de Paris), lancé par le garde
(controleur.yml), il réécoute les vidéos TikTok du jour pas encore publiées, avec les contrôles des voix d'AUJOURD'HUI (une vidéo
fabriquée le matin a pu l'être avant une correction du robot) :
1. bonne voix sur le bon personnage : hauteur de la voix de chaque réplique sur le son de la vidéo finie (verif_finale.voix_dessin) ;
2. homme / femme : personnage à voix de femme dessiné en homme, ou l'inverse (même contrôle) ;
3. bulles mélangées : une réplique dite par deux personnes (doublage.scinder_melangees, sur une copie).
Une vidéo avec un problème est refaite toute seule (« Refaire » compte rendu : mêmes contrôles et corrections que le bouton « 🛠️ Corriger
les problèmes signalés ») : 3 vidéos au plus par soir (CONTROLE_SOIR_MAX). La version refaite REMPLACE l'ancienne dans la liste
(deuxieme_chance.remplacement). Chaque vidéo n'est contrôlée qu'une fois par VERSION des contrôles (historique "controle_soir" :
"version") : quand les contrôles des voix sont améliorés (VERSION + 1), TOUTES les vidéos pas encore publiées sont revérifiées, les plus
récentes d'abord (22 novembre : « Pire date amoureux », faite avant les contrôles de hauteur de voix, n'avait jamais été revérifiée).
CONTROLE_SOIR_VIDEOS vidéos réécoutées par soir au plus (12). CONTROLEUR_SOIR=0 pour couper."""
import copy, datetime, json, os, re, subprocess, sys, tempfile

ICI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ICI)
HIST = os.path.join(ICI, "..", "episodes", "historique.json")
SKETCHS = os.path.join(ICI, "..", "episodes", "sketchs")


def maxi():
    try: return max(0, int(os.environ.get("CONTROLE_SOIR_MAX") or 3))
    except ValueError: return 3


def aujourdhui():
    from zoneinfo import ZoneInfo
    return datetime.datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()


VERSION = 4                                                                # + 1 à chaque amélioration des contrôles des voix


def nb_videos():
    try: return max(1, int(os.environ.get("CONTROLE_SOIR_VIDEOS") or 12))
    except ValueError: return 12


def deja_vue(h):
    c = h.get("controle_soir")
    return isinstance(c, dict) and int(c.get("version") or 1) >= VERSION


def candidats(historique, jour=None):
    """Vidéos TikTok pas publiées, pas des essais, pas encore contrôlées avec la version actuelle des contrôles : celles du jour
    d'abord, puis les plus récentes (CONTROLE_SOIR_VIDEOS au plus)."""
    out = [h for h in historique if h.get("filiere") == "tiktok" and not h.get("essai") and h.get("publie") is not True
           and h.get("fichier") and not deja_vue(h)]
    out.sort(key=lambda h: str(h.get("fichier")), reverse=True)
    return out[:nb_videos()]


def sketch(fichier):
    b = os.path.splitext(fichier)[0]
    for p in (os.path.join(SKETCHS, b + ".json"), os.path.join(SKETCHS, fichier + ".json")):
        if os.path.exists(p): return json.load(open(p, encoding="utf-8"))
    return None


def telecharger(h, dossier):
    """Version légère (même son) sinon pleine qualité, depuis les archives (releases)."""
    f = h["fichier"]; tag = h.get("tag") or f"emissions-{f[:7]}"
    for nom in ([f.replace(".mp4", "_web.mp4")] if h.get("web") else []) + [f]:
        r = subprocess.run(["gh", "release", "download", tag, "-p", nom, "-D", dossier, "--clobber"], capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(os.path.join(dossier, nom)): return os.path.join(dossier, nom)
    return None


def controler(video, sk):
    """Points graves trouvés (même format que verif_finale) : voix, homme / femme, bulles mélangées."""
    import verif_finale, doublage
    pts = verif_finale.voix_dessin(video, sk) + verif_finale.attribution_image(sk)
    try:
        son, sr = verif_finale._son(video)
        sk2 = copy.deepcopy(sk); n = doublage.scinder_melangees(sk2, son, sr)
        if n: pts.append(verif_finale._defaut(None, "voix et dessin", f"{n} bulle(s) où deux personnes parlent : à couper en deux"))
    except Exception as e: print(f"  bulles mélangées non vérifiées ({str(e)[:100]})", flush=True)
    return pts


A_REFAIRE = "sortie/.a_refaire"


def lancer(fichier):
    """Noté dans sortie/.a_refaire : controleur.yml enregistre d'abord l'historique, PUIS lance « Refaire » (la fabrication lit
    l'historique à jour)."""
    os.makedirs(os.path.dirname(A_REFAIRE), exist_ok=True)
    open(A_REFAIRE, "a", encoding="utf-8").write(fichier + "\n"); return True   # (« |soir » ajouté par controleur.yml)


def main(controler_=controler, telecharger_=telecharger, lancer_=lancer, jour=None):
    if os.environ.get("CONTROLEUR_SOIR", "1") == "0": print("Contrôleur du soir coupé (CONTROLEUR_SOIR=0)"); return 0
    hist = json.load(open(HIST, encoding="utf-8"))
    cands = candidats(hist, jour)
    print(f"Contrôleur du soir : {len(cands)} vidéo(s) du jour à revérifier", flush=True)
    refaites = 0
    for h in cands:
        sk = sketch(h["fichier"])
        if not sk or not sk.get("doublage"): h["controle_soir"] = {"date": aujourdhui(), "resultat": "sketch non gardé", "version": VERSION}; continue
        tmp = tempfile.mkdtemp(); v = telecharger_(h, tmp)
        if not v: print(f"  {h['fichier']} : vidéo introuvable dans les archives", flush=True); continue
        try: pts = controler_(v, sk)
        except Exception as e: print(f"  {h['fichier']} : contrôle impossible ({str(e)[:120]})", flush=True); continue
        c = {"date": aujourdhui(), "problemes": len(pts), "version": VERSION}
        if pts:
            print(f"  ❌ {h['fichier']} « {h.get('titre_affiche') or h.get('titre')} » : " + " ; ".join(p["quoi"] for p in pts[:4]), flush=True)
            av = [p for p in h.get("a_verifier") or [] if isinstance(p, dict)]
            h["a_verifier"] = av + [dict(p, poste="contrôleur du soir · " + p.get("poste", "")) for p in pts if p["quoi"] not in {x.get("quoi") for x in av}]
            if h.get("refait_par_soir"):                                   # déjà refaite par ce robot : jamais en boucle
                print("     -> déjà refaite une fois par le contrôleur : laissée à l'auteur (badge « À vérifier »)", flush=True)
            elif refaites < maxi() and lancer_(h["fichier"]):
                refaites += 1; c["refaite"] = True; print("     -> refaite automatiquement (la nouvelle version remplacera celle-ci)", flush=True)
            else:
                print("     -> pas refaite ce soir (limite atteinte) : reprise demain, badge « À vérifier » sur le site", flush=True)
                continue                                                   # pas notée « contrôlée » : refaite un autre soir
        else: print(f"  ✅ {h['fichier']} : voix, homme / femme et bulles bons", flush=True)
        h["controle_soir"] = c
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Contrôleur du soir fini : {refaites} vidéo(s) refaite(s)", flush=True)
    return refaites


if __name__ == "__main__":
    main()
