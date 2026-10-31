"""Suppression d'une vidéo demandée depuis la régie (bouton ✕) : retire l'émission de l'historique (donc du site)
et efface le fichier vidéo et sa légende des Releases GitHub. Usage : FICHIER=2026-10-10_11h59_emission.mp4 python moteur/supprimer.py"""
import json, os, re, subprocess, sys

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HIST = os.path.join(RACINE, "episodes", "historique.json")

def essai(h):
    """Vidéo d'essai (aperçu 10 s, sketch d'essai, essai de pause) : rangée à part, effacée au bout de 3 jours."""
    return bool(h.get("essai")) or str(h.get("titre", "")).startswith("👀 Aperçu")


def menage_essais(jours=3):
    """Ménage quotidien (garde.yml) : les vidéos d'essai de plus de 3 jours sont effacées (historique + Releases)."""
    import datetime
    hist = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else []
    limite = (datetime.date.today() - datetime.timedelta(days=jours)).isoformat()
    vieux = [h for h in hist if essai(h) and h.get("fichier") and str(h.get("date", "")) < limite]
    for h in vieux:
        os.environ["FICHIER"] = h["fichier"]; main()
    print(f"Ménage des essais : {len(vieux)} vidéo(s) d'essai de plus de {jours} jours effacée(s)"); return 0


def main():
    nom = os.environ.get("FICHIER", "").strip()
    if nom == "ESSAIS": return menage_essais()
    if not re.fullmatch(r"[\w.-]+\.mp4", nom): print(f"Nom de fichier refusé : {nom!r}"); return 1
    hist = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else []
    e = next((h for h in hist if h.get("fichier") == nom), None)
    if not e: print(f"{nom} introuvable dans l'historique (déjà supprimée ?)"); return 0
    tag = e.get("tag") or f"emissions-{nom[:7]}"
    for f in (nom, nom.replace(".mp4", ".txt"), nom.replace(".mp4", "_web.mp4"), nom.replace(".mp4", ".jpg")):
        r = subprocess.run(["gh", "release", "delete-asset", tag, f, "-y"], capture_output=True, text=True)
        print(f"  {f} : {'effacé' if r.returncode == 0 else 'absent ou déjà effacé'}")
    hist = [h for h in hist if h.get("fichier") != nom]                    # l'empreinte du sujet part aussi : il pourra être refait
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Supprimée : « {e.get('titre', '')} » ({nom})"); return 0

if __name__ == "__main__":
    sys.exit(main())
