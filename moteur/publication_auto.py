"""Publication automatique (onglet 🎵 TikTok du site) : l'auteur coche « À publier » sur les vidéos qu'il a vérifiées (variable
PUBLI_FILE, une vidéo par ligne, dans l'ordre où il les a cochées) ; chaque jour à l'heure PUBLI_HEURE (heure de Paris), si
PUBLI_AUTO = 1, la plus ancienne vidéo cochée et pas encore publiée part sur TikTok (workflow publier.yml, via Buffer).

Lancé par le Réveil de secours (garde.yml, toutes les 30 min) : dès qu'on est à moins de 35 min de l'heure (ou après), la
publication est demandée à Buffer POUR l'heure exacte (ou tout de suite si l'heure est passée). Une par créneau : chaque
publication automatique déjà demandée aujourd'hui (réussie ou non) compte pour un créneau ; une vidéo en échec est sautée.
Deuxième heure (choix de l'auteur, 1er novembre 2026) : PUBLI_DEUX = 1 et PUBLI_HEURE2 -> deux vidéos par jour."""
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


_LIEUX = {}


def lieu(h):
    """Lieu de la vidéo (recette du succès, sinon la réalisation gardée dans son sketch), "" si inconnu."""
    if not h: return ""
    l = (h.get("recette") or {}).get("lieu")
    if l: return str(l)
    f = str(h.get("fichier") or "")
    if f not in _LIEUX:
        try: _LIEUX[f] = str(((json.load(open(os.path.join(RACINE, "episodes", "sketchs", f.replace(".mp4", "") + ".json"), encoding="utf-8"))
                               .get("realisation") or {}).get("lieux") or [""])[0] or "")
        except (OSError, ValueError, IndexError): _LIEUX[f] = ""
    return _LIEUX[f]


def alterner(file_, historique):
    """Variété du fil (choix de l'auteur) : jamais deux sons du même profil d'origine d'affilée, et (idée 8 du 11 novembre) si
    possible jamais deux fois le même lieu de suite. On part de la dernière vidéo publiée ; chaque vidéo suivante est la 1re de la
    file qui change de profil ET de lieu, sinon la 1re qui change de profil, sinon la 1re de la file."""
    connues = {h.get("fichier"): h for h in historique if h.get("fichier")}
    pub = [h for h in historique if h.get("publie") is True]
    dern = max(pub, key=lambda h: str(h.get("programmee") or h.get("fichier") or "")) if pub else None
    prec, prec_l = profil(dern), lieu(dern)
    reste, out = list(file_), []
    while reste:
        autre = lambda x: not prec or profil(connues.get(x)) != prec
        n = next((x for x in reste if autre(x) and (not prec_l or lieu(connues.get(x)) != prec_l)), None) \
            or next((x for x in reste if autre(x)), reste[0])
        reste.remove(n); out.append(n); prec, prec_l = profil(connues.get(n)), lieu(connues.get(n))
    return out


def _vues_a(points, h):
    """Vues à l'âge h (heures) d'après la courbe [[âge, vues]…] (interpolation ; None si la courbe n'y arrive pas encore)."""
    pts = sorted((float(a), float(v)) for a, v in points or [])
    if not pts or pts[-1][0] < h * 0.8: return None
    for (a0, v0), (a1, v1) in zip(pts, pts[1:]):
        if a0 <= h <= a1: return v0 + (v1 - v0) * (h - a0) / max(1e-6, a1 - a0)
    return pts[-1][1] if pts[-1][0] <= h else pts[0][1] * h / max(1e-6, pts[0][0])


def decolle(historique, courbes, maintenant_ts, heures=6, facteur=2.0):
    """Vidéo qui décolle (audit du 17 novembre 2026, idée 11) : publiée il y a moins de 48 h et plus de `facteur` fois la médiane
    des vues des autres vidéos au même âge (`heures` après publication). Renvoie son entrée d'historique, ou None."""
    if os.environ.get("DECOLLE", "1") == "0" or not courbes: return None
    import statistics
    connues = {h.get("fichier"): h for h in historique if h.get("fichier")}
    ref = [v for v in (_vues_a(e.get("p"), heures) for e in courbes.values()) if v is not None]
    if len(ref) < 4: return None
    med = max(30.0, statistics.median(ref))
    best = None
    for k, e in courbes.items():
        if k not in connues or maintenant_ts - float(e.get("date") or 0) > 48 * 3600: continue
        pts = [p for p in e.get("p") or [] if float(p[0]) <= heures + 1]
        if not pts or float(pts[-1][0]) < heures * 0.5: continue
        v = float(pts[-1][1]) * heures / max(heures * 0.5, min(heures, float(pts[-1][0])))   # projeté à `heures` si encore jeune
        if v > facteur * med and (best is None or v > best[0]): best = (v, connues[k])
    return best[1] if best else None


def avancer(file_, chaud, historique):
    """La vidéo en attente du même créateur (sinon du même lieu) que la vidéo qui décolle passe en tête de la file."""
    if not chaud or not file_: return file_
    connues = {h.get("fichier"): h for h in historique if h.get("fichier")}
    p, l = profil(chaud), lieu(chaud)
    n = next((x for x in file_ if p and profil(connues.get(x)) == p), None) or next((x for x in file_ if l and lieu(connues.get(x)) == l), None)
    return [n] + [x for x in file_ if x != n] if n else file_


def heure(brut):
    try:
        h, m = str(brut or "18:00").strip().replace("h", ":").split(":")[:2]; h, m = int(h), int(m or 0)
        return (h, m) if 0 <= h < 24 and 0 <= m < 60 else (18, 0)
    except ValueError: return (18, 0)


FRANCO_DEF = "22:30"


def jour_franco(date):
    """Un jour sur deux (jours impairs depuis le 1er janvier 1970, même calcul que le site) : créneau francophonie."""
    return (date.toordinal() - 719163) % 2 == 1


def creneaux(reglages, jour=None, date=None):
    """Heures de publication du jour (heure de Paris) : PUBLI_HEURE (ou l'heure des statistiques) et, si PUBLI_DEUX = 1, la
    deuxième heure PUBLI_HEURE2 (choix de l'auteur, 1er novembre 2026 : deux vidéos par jour). Triées, sans doublon."""
    h, m = heure(reglages.get("PUBLI_HEURE"))
    if str(reglages.get("PUBLI_HEURE_AUTO") or "0").strip() == "1":       # idée 20 : l'heure où nos vidéos font le plus de vues
        try: h, m = __import__("stats").meilleure_heure_publication(h, jour), 0   # (idée 17 : l'heure qui marche CE jour de la semaine)
        except Exception as _e: __import__("pannes").avale(_e)
    out = [(h, m)]
    if str(reglages.get("PUBLI_DEUX") or "0").strip() == "1":
        h2 = heure(str(reglages.get("PUBLI_HEURE2") or "").strip() or "12:00")   # (même défaut que le site)
        if abs((h2[0] * 60 + h2[1]) - (h * 60 + m)) >= 60: out.append(h2)    # au moins une heure d'écart
    out = sorted(out)
    # Créneau francophonie (choix de l'auteur du 21 novembre 2026, idée 1) : un jour sur deux, la DERNIÈRE vidéo du jour part le
    # soir (22 h 30 par défaut, heure de Paris = 16 h 30 au Québec, 21 h 30 en Afrique de l'Ouest) ; même nombre de vidéos par jour,
    # et le bloc « 📈 Ce qui marche » compare les vues des deux créneaux. PUBLI_FRANCO=0 pour couper.
    if date is not None and str(reglages.get("PUBLI_FRANCO") or "1").strip() != "0" and jour_franco(date):
        hf = heure(str(reglages.get("PUBLI_HEURE_FRANCO") or "").strip() or FRANCO_DEF)
        autres = out[:-1]
        if all(abs((hf[0] * 60 + hf[1]) - (x[0] * 60 + x[1])) >= 60 for x in autres): out = sorted(autres + [hf])
    return out


def decision(maintenant, reglages, historique, deja_aujourdhui, courbes=None):
    """(fichier à publier ou None, « quand » pour Buffer (heure de Paris, ISO) ou "" = tout de suite, raison).
    deja_aujourdhui : nombre de publications automatiques déjà demandées aujourd'hui (True = 1). Une vidéo par créneau du jour."""
    if str(reglages.get("PUBLI_AUTO") or "0").strip() != "1": return None, "", "publication automatique coupée"
    cibles = [maintenant.replace(hour=h, minute=m, second=0, microsecond=0) for h, m in creneaux(reglages, maintenant.weekday(), maintenant.date())]
    atteints = [c for c in cibles if maintenant >= c - datetime.timedelta(minutes=AVANCE)]
    if not atteints: return None, "", f"pas encore l'heure ({cibles[0].strftime('%H:%M')})"
    n = int(deja_aujourdhui)
    if n >= len(atteints):
        return None, "", ("vidéo du jour déjà envoyée" if len(cibles) == 1 else f"{n} vidéo(s) déjà envoyée(s) aujourd'hui" +
                          (f", la suivante à {cibles[n].strftime('%H:%M')}" if n < len(cibles) else ""))
    f = alterner(file_attente(reglages.get("PUBLI_FILE"), historique), historique)
    if not f: return None, "", "aucune vidéo cochée en attente"
    chaud = None
    try:
        C = json.load(open(os.path.join(RACINE, "episodes", "courbes.json"), encoding="utf-8")) if courbes is None else courbes
        chaud = decolle(historique, C, maintenant.timestamp())
    except (OSError, ValueError): pass
    f2 = avancer(f, chaud, historique)
    vogue = f2[0] != f[0]; f = f2
    cible = atteints[n]                                                    # le créneau suivant pas encore servi
    quand = cible.strftime("%Y-%m-%dT%H:%M") if cible > maintenant + datetime.timedelta(minutes=6) else ""
    return f[0], quand, f"{len(f)} vidéo(s) en attente" + (f", créneau {n + 1}/{len(cibles)}" if len(cibles) > 1 else "") \
        + (f" ; 🚀 « {chaud.get('fichier')} » décolle : la suite du même créateur / sujet passe devant" if vogue else "")


def a_rediffuser(historique, maintenant, jours=90):
    """Rediffusion automatique (choix de l'auteur du 6 novembre, idée 40) : quand aucune vidéo cochée n'attend, la vidéo publiée il y a
    plus de 3 mois qui a fait le plus de vues repart (jamais une vidéo déjà rediffusée ces 3 derniers mois). REDIFFUSION=0 pour couper."""
    if os.environ.get("REDIFFUSION", "1") == "0": return None
    limite = (maintenant - datetime.timedelta(days=jours)).date().isoformat()
    ok = [h for h in historique if h.get("fichier") and h.get("publie") is True and not h.get("essai") and h.get("vues")
          and str(h.get("programmee") or h.get("date") or "9999")[:10] <= limite
          and str(h.get("rediffusee") or "0000")[:10] <= limite]
    return max(ok, key=lambda h: int(h.get("vues") or 0))["fichier"] if ok else None


def _gh(*args):
    """gh avec le dépôt : « -R » pour les commandes (workflow run…), mais JAMAIS pour « gh api », qui le refuse (le dépôt est déjà
    dans l'adresse) : c'est ce « -R » qui faisait échouer toute publication automatique depuis le début."""
    rep = [] if args and args[0] == "api" else ["-R", os.environ["GITHUB_REPOSITORY"]]
    return subprocess.run(["gh", *args, *rep], capture_output=True, text=True)


def deja_aujourdhui(maintenant):
    """Nombre de publications automatiques déjà demandées aujourd'hui (heure de Paris)."""
    r = _gh("api", f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/publier.yml/runs?per_page=30",
            "-q", '[.workflow_runs[] | select(.display_title | startswith("Publication automatique")) | .created_at]')
    if r.returncode: raise RuntimeError(r.stderr[:200])
    jour = maintenant.date(); n = 0
    for c in json.loads(r.stdout or "[]"):
        d = datetime.datetime.strptime(c, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).astimezone(PARIS)
        if d.date() == jour: n += 1
    return n


def main():
    maintenant = datetime.datetime.now(PARIS)
    reglages = {k: os.environ.get(k, "") for k in ("PUBLI_AUTO", "PUBLI_HEURE", "PUBLI_FILE", "PUBLI_HEURE_AUTO", "PUBLI_DEUX", "PUBLI_HEURE2", "PUBLI_FRANCO", "PUBLI_HEURE_FRANCO")}
    if reglages["PUBLI_AUTO"].strip() != "1": print("Publication automatique coupée."); return
    try: hist = json.load(open(os.path.join(RACINE, "episodes", "historique.json"), encoding="utf-8"))
    except (OSError, ValueError): hist = []
    fichier, quand, raison = decision(maintenant, reglages, hist, deja_aujourdhui(maintenant))
    redif = False
    if not fichier and raison == "aucune vidéo cochée en attente":          # idée 40 : la meilleure vidéo d'il y a 3 mois repart
        fichier = a_rediffuser(hist, maintenant); redif = bool(fichier)
        if redif: raison = "rediffusion (aucune vidéo cochée en attente)"
    if not fichier: print(f"Publication automatique : rien à faire ({raison})."); return
    r = _gh("workflow", "run", "publier.yml", "-f", f"fichier={fichier}", "-f", f"quand={quand}", "-f", "auto=1",
            *(["-f", "forcer=oui", "-f", "rediffusion=1"] if redif else []))
    print(f"Publication automatique : {fichier} {'programmée à ' + quand if quand else 'envoyée tout de suite'} ({raison})."
          if r.returncode == 0 else f"Publication automatique impossible : {r.stderr[:200]}")


if __name__ == "__main__":
    try: main()
    except Exception as e: print(f"Publication automatique : {str(e)[:200]}"); sys.exit(0)
