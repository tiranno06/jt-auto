"""Petites actions de la régie sur une vidéo (workflow regie.yml) : 👍 / 👎, nouvelle légende, note et remarque de l'auteur
(le jury qualité les retient pour les vidéos suivantes : episodes/remarques_auteur.json).
Usage : ACTION=avis|legende|remarque FICHIER=… VALEUR=… python moteur/regie_action.py   (rejouable sans risque)
remarque : VALEUR = « note|texte » (note de 1 à 10, facultative)."""
import json, os, re, sys

HIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "historique.json")
REMARQUES = os.path.join(os.path.dirname(HIST), "remarques_auteur.json")

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
    elif action == "remarque":
        note, _, texte = valeur.partition("|") if "|" in valeur else ("", "", valeur)
        try: note = max(1, min(10, int(note))) if note.strip() else None
        except ValueError: note = None
        texte = texte.strip()[:600]
        if note is None and not texte: print("Remarque vide : rien changé"); return 0
        if note is not None: e["note_auteur"] = note
        try: rem = json.load(open(REMARQUES, encoding="utf-8"))
        except (OSError, ValueError): rem = []
        import datetime
        cle = (nom, texte, note)
        if not any((r.get("fichier"), r.get("remarque"), r.get("note")) == cle for r in rem):   # rejouable sans doublon
            rem.append(dict(date=datetime.date.today().isoformat(), fichier=nom, titre=e.get("titre", ""), note=note, remarque=texte))
            if texte: e.setdefault("remarques_auteur", []).append(texte)
        json.dump(rem[-200:], open(REMARQUES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"Remarque de l'auteur sur « {e.get('titre')} » : note {note}, {texte[:80]!r}")
    else:
        print(f"Action inconnue : {action}"); return 1
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return 0

if __name__ == "__main__":
    sys.exit(main())
