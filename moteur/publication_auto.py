"""Publication automatique (onglet 🎵 TikTok du site) : l'auteur coche « À publier » sur les vidéos qu'il a vérifiées (variable
PUBLI_FILE, une vidéo par ligne, dans l'ordre où il les a cochées) ; chaque jour à l'heure PUBLI_HEURE (heure de Paris), si
PUBLI_AUTO = 1, la plus ancienne vidéo cochée et pas encore publiée part sur TikTok (workflow publier.yml, via Buffer).

Lancé par le Réveil de secours (garde.yml, toutes les 30 min) : dès qu'on est à moins de 35 min de l'heure (ou après), la
publication est demandée à Buffer POUR l'heure exacte (ou tout de suite si l'heure est passée). Une seule par jour : une
publication automatique déjà demandée aujourd'hui (réussie ou non) ferme la journée ; une vidéo en échec est sautée (la suivante part le lendemain)."""
import datetime, json, os, subprocess, sys
from zoneinfo import ZoneInfo

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PARIS = ZoneInfo("Europe/Paris")
AVANCE = 35                                                                # minutes : demande envoyée à Buffer un peu avant l'heure


def file_attente(brut, historique):
    """Vidéos cochées (dans l'ordre) qui existent et ne sont pas encore publiées. Une vidéo dont la publication a échoué est sautée
    (elle ne bloque pas les suivantes) : l'auteur la republie à la main depuis sa fiche."""
    connues = {h.get("fichier"): h for h in historique if h.get("fichier")}
    out = []
    for n in [x.strip() for x in str(brut or "").splitlines()]:
        if n and n in connues and connues[n].get("publie") is None and n not in out: out.append(n)
    return out


def profil(h):
    """Compte TikTok d'origine du son (@compte), ou "" pour un sketch."""
    import re
    m = re.search(r"tiktok\.com/@([\w.\-]+)", str((h or {}).get("source_audio") or " ".join((h or {}).get("sources") or [])))
    return "@" + m.group(1).lower() if m else ""


def alterner(file_, historique):
    """Jamais deux sons du même profil d'origine d'affilée (choix de l'auteur) : on part du profil de la dernière vidéo publiée et
    chaque vidéo suivante est la 1re de la file qui vient d'un AUTRE profil (sinon la 1re de la file)."""
    connues = {h.get("fichier"): h for h in historique if h.get("fichier")}
    pub = [h for h in historique if h.get("publie") is True]
    prec = profil(max(pub, key=lambda h: str(h.get("programmee") or h.get("fichier") or ""))) if pub else ""
    reste, out = list(file_), []
    while reste:
        n = next((x for x in reste if not prec or profil(connues.get(x)) != prec), reste[0])
        reste.remove(n); out.append(n); prec = profil(connues.get(n))
    return out


def heure(brut):
    try:
        h, m = str(brut or "18:00").strip().replace("h", ":").split(":")[:2]; h, m = int(h), int(m or 0)
        return (h, m) if 0 <= h < 24 and 0 <= m < 60 else (18, 0)
    except ValueError: return (18, 0)


def decision(maintenant, reglages, historique, deja_aujourdhui):
    """(fichier à publier ou None, « quand » pour Buffer (heure de Paris, ISO) ou "" = tout de suite, raison)."""
    if str(reglages.get("PUBLI_AUTO") or "0").strip() != "1": return None, "", "publication automatique coupée"
    h, m = heure(reglages.get("PUBLI_HEURE"))
    if str(reglages.get("PUBLI_HEURE_AUTO") or "0").strip() == "1":       # idée 20 : l'heure où nos vidéos font le plus de vues
        try: h, m = __import__("stats").meilleure_heure_publication(h), 0
        except Exception: pass
    cible = maintenant.replace(hour=h, minute=m, second=0, microsecond=0)
    if maintenant < cible - datetime.timedelta(minutes=AVANCE): return None, "", f"pas encore l'heure ({h:02d}:{m:02d})"
    if deja_aujourdhui: return None, "", "vidéo du jour déjà envoyée"
    f = alterner(file_attente(reglages.get("PUBLI_FILE"), historique), historique)
    if not f: return None, "", "aucune vidéo cochée en attente"
    quand = cible.strftime("%Y-%m-%dT%H:%M") if cible > maintenant + datetime.timedelta(minutes=6) else ""
    return f[0], quand, f"{len(f)} vidéo(s) en attente"


def _gh(*args):
    return subprocess.run(["gh", *args, "-R", os.environ["GITHUB_REPOSITORY"]], capture_output=True, text=True)


def deja_aujourdhui(maintenant):
    """Une publication automatique a-t-elle déjà été demandée aujourd'hui (heure de Paris) ?"""
    r = _gh("api", f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/publier.yml/runs?per_page=30",
            "-q", '[.workflow_runs[] | select(.display_title | startswith("Publication automatique")) | .created_at]')
    if r.returncode: raise RuntimeError(r.stderr[:200])
    jour = maintenant.date()
    for c in json.loads(r.stdout or "[]"):
        d = datetime.datetime.strptime(c, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).astimezone(PARIS)
        if d.date() == jour: return True
    return False


def main():
    maintenant = datetime.datetime.now(PARIS)
    reglages = {k: os.environ.get(k, "") for k in ("PUBLI_AUTO", "PUBLI_HEURE", "PUBLI_FILE", "PUBLI_HEURE_AUTO")}
    if reglages["PUBLI_AUTO"].strip() != "1": print("Publication automatique coupée."); return
    try: hist = json.load(open(os.path.join(RACINE, "episodes", "historique.json"), encoding="utf-8"))
    except (OSError, ValueError): hist = []
    fichier, quand, raison = decision(maintenant, reglages, hist, deja_aujourdhui(maintenant))
    if not fichier: print(f"Publication automatique : rien à faire ({raison})."); return
    r = _gh("workflow", "run", "publier.yml", "-f", f"fichier={fichier}", "-f", f"quand={quand}", "-f", "auto=1")
    print(f"Publication automatique : {fichier} {'programmée à ' + quand if quand else 'envoyée tout de suite'} ({raison})."
          if r.returncode == 0 else f"Publication automatique impossible : {r.stderr[:200]}")


if __name__ == "__main__":
    try: main()
    except Exception as e: print(f"Publication automatique : {str(e)[:200]}"); sys.exit(0)
