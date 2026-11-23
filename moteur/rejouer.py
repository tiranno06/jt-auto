"""Nouvelle version d'une vidéo qui a marché (choix de l'auteur du 23 novembre 2026, idée 8). Une fois par semaine au plus, après le
relevé des statistiques (stats.yml) : parmi les vidéos TikTok publiées il y a plus de 2 mois (REJOUER_JOURS, 60), la plus vue
(au moins 2 fois la médiane des vues et dans les 10 meilleures), jamais déjà rejouée, est refaite sur le même son avec de NOUVEAUX
décors (« Refaire » decors|rejouer : autre décor, autre couverture). La nouvelle version :
- ne remplace pas l'ancienne (déjà publiée : les deux restent, deuxieme_chance.remplacement) ;
- porte "rejoue_de" et "publier_auto" : elle entre toute seule dans la file de publication (publication_auto.file_attente et le
  site), en dernier, sans que l'auteur coche « À publier ».
L'ancienne est marquée "rejouee" (date). episodes/rejouer.json garde la date du dernier lancement. REJOUER=0 pour couper."""
import datetime, json, os, statistics, subprocess, sys

ICI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ICI)
HIST = os.path.join(ICI, "..", "episodes", "historique.json")
ETAT = os.path.join(ICI, "..", "episodes", "rejouer.json")


def jours():
    try: return max(14, int(os.environ.get("REJOUER_JOURS") or 60))
    except ValueError: return 60


def choisir(historique, aujourdhui):
    """La vidéo à rejouer (ligne d'historique) ou None."""
    pub = [h for h in historique if h.get("filiere") == "tiktok" and h.get("publie") is True and not h.get("essai")
           and h.get("fichier") and isinstance(h.get("vues"), (int, float))]
    if len(pub) < 5: return None
    med = statistics.median(h["vues"] for h in pub)
    top = sorted(pub, key=lambda h: -h["vues"])[:10]
    limite = (aujourdhui - datetime.timedelta(days=jours())).isoformat()
    deja = {h.get("rejoue_de") for h in historique if h.get("rejoue_de")}
    ok = [h for h in top if h["vues"] >= 2 * med and not h.get("rejouee") and h["fichier"] not in deja and not h.get("rejoue_de")
          and str(h.get("programmee") or h.get("date") or "9999")[:10] <= limite]
    return ok[0] if ok else None


def main(aujourdhui=None, lancer=None):
    if os.environ.get("REJOUER", "1") == "0": return None
    aujourdhui = aujourdhui or datetime.date.today()
    try: E = json.load(open(ETAT, encoding="utf-8"))
    except (OSError, ValueError): E = {}
    if E.get("date") and (aujourdhui - datetime.date.fromisoformat(E["date"])).days < 7: return None   # une par semaine au plus
    hist = json.load(open(HIST, encoding="utf-8"))
    h = choisir(hist, aujourdhui)
    if not h: print("Vidéo à rejouer : aucune pour l'instant"); return None
    ok = (lancer or (lambda f: subprocess.run(["gh", "workflow", "run", "emission.yml", "-R", os.environ.get("GITHUB_REPOSITORY", ""),
                                               "--ref", "main", "-f", f"refaire={f}|decors|rejouer"]).returncode == 0))(h["fichier"])
    if not ok: print("Vidéo à rejouer : lancement impossible"); return None
    h["rejouee"] = aujourdhui.isoformat()
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"date": aujourdhui.isoformat(), "fichier": h["fichier"]}, open(ETAT, "w", encoding="utf-8"))
    print(f"Vidéo à rejouer : « {h.get('titre_affiche') or h.get('titre')} » ({h['vues']} vues) refaite avec de nouveaux décors")
    return h["fichier"]


if __name__ == "__main__":
    try: main()
    except Exception as e: print(f"vidéo à rejouer impossible ({str(e)[:150]})")
