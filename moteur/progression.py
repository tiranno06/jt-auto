"""Avancement de la fabrication en cours, lu en direct par le site (barre de progression, étape, temps restant).

Toutes les 8 s au plus, le robot publie « pourcentage|type|étape|heure de fin prévue (secondes epoch) » (texte simple, sans
émoji : type = sketch ou tiktok) par deux voies, pour que la barre marche toujours :
1. un statut du commit de la fabrication (contexte progression-<n° du run>) ;
2. en secours, si GitHub refuse le statut : une « vérification » (check run) nommée progression-<n° du run>.
Sans jeton (essais sur un ordinateur) : rien n'est envoyé, la fabrication continue normalement."""
import json, os, re, time, urllib.request

_DERNIER = [0.0]
_ERREUR = {}
_CHECK = [None]                                                            # n° de la vérification de secours (créée au besoin)
PLAGE = [0.0, 100.0]                                                       # part de la barre donnée au rendu en cours (cartoon)
APRES = [150.0]                                                            # secondes estimées après le rendu (contrôle, archivage)
TYPE = ["sketch"]


def _api(methode, chemin, corps):
    jeton, depot = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    req = urllib.request.Request(f"https://api.github.com/repos/{depot}{chemin}", data=json.dumps(corps).encode(), method=methode,
                                 headers={"Authorization": f"Bearer {jeton}", "Accept": "application/vnd.github+json",
                                          "User-Agent": "petitsdramas-robot", "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=10).read() or b"{}")


def _signaler(voie, e):
    if voie in _ERREUR: return
    detail = ""
    try: detail = e.read().decode()[:200]
    except Exception: pass
    _ERREUR[voie] = True
    print(f"Barre de progression du site ({voie}) : envoi impossible ({str(e)[:120]} {detail})", flush=True)


def _envoyer(pct, texte, fin=None, etat="pending"):
    if not ((os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")) and os.environ.get("GITHUB_REPOSITORY")
            and os.environ.get("GITHUB_SHA") and os.environ.get("GITHUB_RUN_ID")): return
    sha, run = os.environ["GITHUB_SHA"], os.environ["GITHUB_RUN_ID"]
    texte = re.sub(r"[^\w\s'’:/().,%+-]", "", str(texte)).strip()          # texte simple (GitHub refuse certains caractères)
    if re.match(r"^\d+/\d+$", os.environ.get("CHAINE") or ""): texte = f"vidéo {os.environ['CHAINE']} : {texte}"   # vidéos à la chaîne
    desc = f"{int(max(0, min(100, pct)))}|{TYPE[0]}|{texte}|{int(fin) if fin else ''}"[:140]
    if "statut" not in _ERREUR:
        try: _api("POST", f"/statuses/{sha}", {"state": etat, "context": f"progression-{run}", "description": desc}); return
        except Exception as e: _signaler("statut", e)
    try:                                                                   # secours : vérification (check run) mise à jour
        sortie = {"title": desc, "summary": desc}
        if _CHECK[0] is None:
            _CHECK[0] = _api("POST", "/check-runs", {"name": f"progression-{run}", "head_sha": sha, "status": "in_progress", "output": sortie})["id"]
        else:
            fini_ = etat != "pending"
            _api("PATCH", f"/check-runs/{_CHECK[0]}", dict({"output": sortie}, **({"status": "completed", "conclusion": "success" if etat == "success" else "failure"} if fini_ else {})))
    except Exception as e: _signaler("vérification", e)


def etape(pct, texte, reste_s=None, forcer=False):
    """Nouvelle étape (ou point d'avancement). reste_s : temps restant estimé en secondes (sinon le site l'estime)."""
    maintenant = time.time()
    if not forcer and maintenant - _DERNIER[0] < 8: return                 # temps réel : un point toutes les 8 s (quota de l'API GitHub)
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
