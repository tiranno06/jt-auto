"""La recette du succès (choix de l'auteur du 6 novembre 2026, idée 41).

Chaque jour (après les statistiques TikTok, stats.py), le robot compare les vues de nos vidéos selon ce qui les compose : profil
d'origine du son, lieu, durée, animal ou objet qui parle, nombre de personnages, heure de publication, type de couverture, style du
titre, vidéo en plusieurs parties. Un critère n'est retenu qu'avec 3 vidéos au moins. Résultat : episodes/recette.json, affiché sur
le site (onglet TikTok, « 📈 Ce qui marche »), et utilisé au tirage des sons (`bonus_son` : la durée qui marche le mieux passe
devant ; le profil l'était déjà par profils_tiktok.poids_profils). RECETTE=0 pour couper le bonus."""
import datetime, json, os, re

RACINE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FICHIER = os.path.join(RACINE, "episodes", "recette.json")
NOMS = {"profil": "Profil du son", "lieu": "Lieu", "duree": "Durée", "animal": "Animal ou objet qui parle", "persos": "Personnages",
        "heure": "Heure de publication", "couverture": "Couverture", "accroche": "Titre", "partie": "Vidéo en plusieurs parties"}


def tranche(d):
    d = float(d or 0)
    return "moins de 20 s" if d < 20 else "20 à 40 s" if d < 40 else "40 à 70 s" if d < 70 else "plus de 70 s"


def criteres(h):
    """(critère, valeur) d'une vidéo de l'historique."""
    out = []
    m = re.search(r"tiktok\.com/@([\w.\-]+)", str(h.get("source_audio") or ""))
    if m: out.append(("profil", "@" + m.group(1).lower()))
    R = h.get("recette") or {}
    if R.get("lieu"): out.append(("lieu", str(R["lieu"]).replace("_", " ")))
    if h.get("duree"): out.append(("duree", tranche(h["duree"])))
    if "animal" in R: out.append(("animal", "oui" if R["animal"] else "non"))
    if R.get("persos"): out.append(("persos", f"{R['persos']} personnage{'s' if R['persos'] > 1 else ''}"))
    p = str(h.get("programmee") or "")
    if re.match(r"\d{4}-\d\d-\d\dT\d\d", p):
        hh = int(p[11:13]); out.append(("heure", "matin" if hh < 12 else "midi" if hh < 14 else "après-midi" if hh < 18 else "soir"))
    if h.get("type_couverture"): out.append(("couverture", {"chute": "la chute", "reaction": "la réaction", "debut": "le début"}.get(h["type_couverture"], h["type_couverture"])))
    if h.get("style_accroche"): out.append(("accroche", {"pov": "« POV : … »", "question": "question au spectateur"}.get(h["style_accroche"], h["style_accroche"])))
    if "partie" in R: out.append(("partie", "oui" if R["partie"] else "non"))
    return out


def analyser(historique, mini=3):
    """{"moyenne", "videos", "plus", "moins", "par": {critère: [[valeur, vues moyennes, nombre, ×]]}} (vidéos aux vues connues)."""
    vids = [h for h in historique if h.get("vues") is not None and h.get("fichier") and not h.get("essai")]
    if not vids: return {"moyenne": 0, "videos": 0, "plus": [], "moins": [], "par": {}}
    moy = sum(int(h["vues"]) for h in vids) / len(vids) or 1
    acc = {}
    for h in vids:
        for c, v in criteres(h): acc.setdefault((c, v), []).append(int(h["vues"]))
    par = {}
    for (c, v), l in acc.items():
        if len(l) >= mini: par.setdefault(c, []).append([v, round(sum(l) / len(l)), len(l), round(sum(l) / len(l) / moy, 2)])
    for c in par: par[c].sort(key=lambda x: -x[1])
    tous = [(c, *x) for c, l in par.items() for x in l if len(l) >= 2]      # un critère compte s'il a au moins 2 valeurs à comparer
    plus = sorted([x for x in tous if x[4] >= 1.2], key=lambda x: -x[4])[:6]
    moins = sorted([x for x in tous if x[4] <= 0.8], key=lambda x: x[4])[:4]
    f = lambda x: {"critere": NOMS.get(x[0], x[0]), "valeur": x[1], "vues": x[2], "n": x[3], "fois": x[4]}
    return {"moyenne": round(moy), "videos": len(vids), "plus": [f(x) for x in plus], "moins": [f(x) for x in moins], "par": par}


def enregistrer(historique):
    r = analyser(historique); r["maj"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes")
    os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
    json.dump(r, open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return r


def bonus_son(v, recette=None):
    """Points de potentiel en plus (ou en moins, ±10) pour un son, d'après la durée qui marche le mieux chez nous."""
    if os.environ.get("RECETTE", "1") == "0" or not v.get("duree"): return 0
    if recette is None:
        try: recette = json.load(open(FICHIER, encoding="utf-8"))
        except (OSError, ValueError): return 0
    for val, _, n, fois in (recette.get("par") or {}).get("duree", []):
        if val == tranche(v["duree"]): return int(max(-10, min(10, round((fois - 1) * 20))))
    return 0
