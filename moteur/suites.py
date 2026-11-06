"""Sons TikTok en plusieurs parties (choix de l'auteur du 6 novembre 2026, idées 26 et 37).

26. Suivre les créateurs : quand un profil sort la « partie 2 » d'une vidéo dont on a déjà fait la partie 1, ce son passe en
    priorité au tirage (`bonus`) et la vidéo reprend les MÊMES personnages (même visage, même coiffure, même tenue) que notre
    partie 1 (`preparer` -> sk["_suite"], appliqué par studio.bible, rôle par rôle, homme avec homme et femme avec femme).
37. Fin « à suivre » : un son qui est une partie d'une série (« partie 1 », « pt 2 », « épisode 3 »…) finit sur « Partie N+1
    bientôt ! Abonne-toi » (carte de fin) et la description l'annonce : la meilleure raison de s'abonner.
Réglage SUITES=0 pour couper les deux."""
import glob, json, os, re

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_PARTIE = re.compile(r"(?:\bpartie|\bpart|\bpt|\b[ée]p(?:isode)?|\bchapitre)\s*\.?\s*(\d{1,2})\b|#partie(\d{1,2})\b|(?<![\d/])(\d)\s*/\s*([2-9])(?![\d/])", re.I)


def actif(): return os.environ.get("SUITES", "1") != "0"


def num_partie(titre):
    """N° de la partie d'après le titre de la vidéo d'origine (« Partie 2 », « pt2 », « épisode 3 », « 2/3 »), sinon None."""
    m = _PARTIE.search(str(titre or ""))
    if not m: return None
    if m.group(3) and int(m.group(3)) > int(m.group(4)): return None       # « 3/2 » : pas une partie (une date « 12/10 » non plus)
    n = int(m.group(1) or m.group(2) or m.group(3))
    return n if 1 <= n <= 30 else None


def profil(url):
    m = re.search(r"tiktok\.com/@([\w.\-]+)", str(url or "")); return m.group(1).lower() if m else ""


def faites(historique):
    """Parties déjà faites : {(profil, n° de partie): fichier de notre vidéo}."""
    out = {}
    for h in historique or []:
        n = num_partie(h.get("titre_source")); p = profil(h.get("source_audio"))
        if n and p and h.get("fichier"): out[(p, n)] = h["fichier"]
    return out


def bonus(v, pseudo, deja):
    """Points de potentiel en plus : la partie suivante d'une vidéo qu'on a déjà faite passe devant tout le monde."""
    if not actif(): return 0
    n = num_partie(v.get("titre"))
    return 60 if n and n >= 2 and (pseudo.lower(), n - 1) in deja else 0


def preparer(sk, historique, journal=print):
    """Après l'écoute : n° de partie (sk["_partie"]), fin « à suivre », et personnages de la partie précédente (sk["_suite"])."""
    if not actif(): return
    d = sk.get("doublage") or {}; n = num_partie(d.get("titre"))
    if not n: return
    sk["_partie"] = n
    sk["suite"] = f"Partie {n + 1} bientôt ! Abonne-toi"                    # carte de fin (cartoon : signature de la chaîne)
    journal(f"  vidéo en plusieurs parties : partie {n} (fin « Partie {n + 1} bientôt ! Abonne-toi »)")
    if n < 2: return
    fich = faites(historique).get((profil(d.get("source")), n - 1))
    if not fich: return
    try: ancien = json.load(open(os.path.join(RACINE, "episodes", "sketchs", os.path.splitext(fich)[0] + ".json"), encoding="utf-8"))
    except (OSError, ValueError): return
    if isinstance(ancien.get("_casting_final"), dict) and ancien["_casting_final"]:
        sk["_suite"] = ancien["_casting_final"]
        journal(f"  partie {n - 1} déjà faite ({fich}) : mêmes personnages repris")


def appliquer(sk, fiches, costumes, roles):
    """Dans studio.bible : chaque rôle reprend le personnage de la partie précédente de même genre (ordre de parole)."""
    S_ = sk.get("_suite")
    if not actif() or not isinstance(S_, dict): return 0
    ordre = list(dict.fromkeys(r.get("p") for r in sk.get("repliques") or [] if r.get("p") in roles))
    libres = [v for v in S_.values() if isinstance(v, dict) and isinstance(v.get("fiche"), dict)]
    n = 0
    for role in ordre:
        g = (fiches.get(role) or {}).get("genre")
        if (fiches.get(role) or {}).get("espece"): continue                  # animal ou objet : il garde le sien
        v = next((x for x in libres if x["fiche"].get("genre") == g and not x["fiche"].get("espece")), None)
        if v is None: continue
        libres.remove(v); fiches[role] = dict(v["fiche"])
        if isinstance(v.get("costume"), dict) and not (costumes.get(role) or {}).get("metier"): costumes[role] = dict(v["costume"])
        n += 1
    return n


def _json(x):
    return json.loads(json.dumps(x, default=lambda o: o.item() if hasattr(o, "item") else (list(o) if isinstance(o, (set, tuple)) else str(o))))


def garder(sk, B, roles):
    """Personnages de cette vidéo gardés dans son sketch (pour une éventuelle partie suivante)."""
    try:
        sk["_casting_final"] = _json({r: {"fiche": (B.get("fiches") or {}).get(r), "costume": (B.get("costumes") or {}).get(r)}
                                      for r in roles if (B.get("fiches") or {}).get(r)})
    except Exception: pass


def ligne_legende(sk):
    n = sk.get("_partie")
    return f"➡️ Partie {n + 1} bientôt sur la chaîne !" if n and actif() else ""
