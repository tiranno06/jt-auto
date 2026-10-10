"""Petites actions de la régie sur une vidéo (workflow regie.yml) : 👍 / 👎, nouvelle légende.
Usage : ACTION=avis|legende FICHIER=… VALEUR=… python moteur/regie_action.py   (rejouable sans risque)"""
import json, os, re, sys

HIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "historique.json")

def main():
    action, nom, valeur = os.environ.get("ACTION", ""), os.environ.get("FICHIER", "").strip(), os.environ.get("VALEUR", "")
    if not re.fullmatch(r"[\w.-]+\.mp4", nom): print(f"Nom refusé : {nom!r}"); return 1
    hist = json.load(open(HIST, encoding="utf-8"))
    e = next((h for h in hist if h.get("fichier") == nom), None)
    if not e: print(f"{nom} introuvable"); return 0
    if action == "avis":
        e["avis"] = {"1": 1, "-1": -1}.get(valeur.strip(), 0); print(f"Avis {e['avis']:+d} sur « {e.get('titre')} »")
    elif action == "legende":
        if not valeur.strip(): print("Légende vide : rien changé"); return 0
        e["legende"] = valeur.strip()[:2200]; print(f"Nouvelle légende pour « {e.get('titre')} »")
    else:
        print(f"Action inconnue : {action}"); return 1
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return 0

if __name__ == "__main__":
    sys.exit(main())
