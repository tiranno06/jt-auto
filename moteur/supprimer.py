"""Suppression d'une vidéo demandée depuis la régie (bouton ✕) : retire l'émission de l'historique (donc du site)
et efface le fichier vidéo et sa légende des Releases GitHub. Usage : FICHIER=2026-10-10_11h59_emission.mp4 python moteur/supprimer.py"""
import json, os, re, subprocess, sys

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HIST = os.path.join(RACINE, "episodes", "historique.json")

def main():
    nom = os.environ.get("FICHIER", "").strip()
    if not re.fullmatch(r"[\w.-]+\.mp4", nom): print(f"Nom de fichier refusé : {nom!r}"); return 1
    hist = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else []
    e = next((h for h in hist if h.get("fichier") == nom), None)
    if not e: print(f"{nom} introuvable dans l'historique (déjà supprimée ?)"); return 0
    tag = e.get("tag") or f"emissions-{nom[:7]}"
    for f in (nom, nom.replace(".mp4", ".txt")):
        r = subprocess.run(["gh", "release", "delete-asset", tag, f, "-y"], capture_output=True, text=True)
        print(f"  {f} : {'effacé' if r.returncode == 0 else 'absent ou déjà effacé'}")
    hist = [h for h in hist if h.get("fichier") != nom]                    # l'empreinte du sujet part aussi : il pourra être refait
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Supprimée : « {e.get('titre', '')} » ({nom})"); return 0

if __name__ == "__main__":
    sys.exit(main())
