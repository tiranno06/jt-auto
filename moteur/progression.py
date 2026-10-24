"""Avancement de la fabrication en cours, lu en direct par le site (barre de progression, étape, temps restant).

Le robot publie son avancement comme un « statut » du commit de la fabrication (API GitHub, contexte progression-<n° du run>),
au plus une fois toutes les 5 s (temps réel). Description : « pourcentage|type|étape|heure de fin prévue (secondes epoch) ».
Sans jeton (essais sur un ordinateur) : rien n'est envoyé, la fabrication continue normalement."""
import json, os, time, urllib.request

_DERNIER = [0.0]
_ERREUR = [False]
PLAGE = [0.0, 100.0]                                                       # part de la barre donnée au rendu en cours (cartoon)
APRES = [150.0]                                                            # secondes estimées après le rendu (contrôle, archivage)
TYPE = ["Vidéo"]


def _envoyer(pct, texte, fin=None, etat="pending"):
    jeton, depot = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    sha, run = os.environ.get("GITHUB_SHA"), os.environ.get("GITHUB_RUN_ID")
    if not (jeton and depot and sha and run): return
    desc = f"{int(max(0, min(100, pct)))}|{TYPE[0]}|{texte}|{int(fin) if fin else ''}"[:140]
    corps = json.dumps({"state": etat, "context": f"progression-{run}", "description": desc}).encode()
    req = urllib.request.Request(f"https://api.github.com/repos/{depot}/statuses/{sha}", data=corps, method="POST",
                                 headers={"Authorization": f"Bearer {jeton}", "Accept": "application/vnd.github+json"})
    try: urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:                                                 # jamais bloquant, mais signalé une fois dans le journal
        if not _ERREUR[0]:
            _ERREUR[0] = True; detail = ""
            try: detail = e.read().decode()[:200]
            except Exception: pass
            print(f"Barre de progression du site : envoi impossible ({str(e)[:120]} {detail})", flush=True)


def etape(pct, texte, reste_s=None, forcer=False):
    """Nouvelle étape (ou point d'avancement). reste_s : temps restant estimé en secondes (sinon le site l'estime)."""
    maintenant = time.time()
    if not forcer and maintenant - _DERNIER[0] < 5: return             # temps réel : un point toutes les 5 s
    _DERNIER[0] = maintenant
    _envoyer(pct, texte, maintenant + reste_s if reste_s else None)


def rendu(fi, nf, debut):
    """Pendant le dessin des images : avancement dans la plage réservée, temps restant d'après la vitesse réelle."""
    if nf <= 0: return
    u = fi / nf; ecoule = time.time() - debut
    reste = ecoule / u * (1 - u) + APRES[0] if u > 0.02 else None      # + la suite (contrôle, archivage)
    etape(PLAGE[0] + (PLAGE[1] - PLAGE[0]) * u, f"Dessin des images : {fi}/{nf}", reste)


def fini(ok=True, texte=None):
    _envoyer(100 if ok else 0, texte or ("Vidéo prête, mise en ligne sur le site" if ok else "Pas de vidéo cette fois"), None,
             "success" if ok else "failure")
