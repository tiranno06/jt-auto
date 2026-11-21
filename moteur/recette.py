"""La recette du succès (choix de l'auteur du 6 novembre 2026, idée 41).

Chaque jour (après les statistiques TikTok, stats.py), le robot compare les vues de nos vidéos selon ce qui les compose : profil
d'origine du son, lieu, durée, animal ou objet qui parle, nombre de personnages, heure de publication, type de couverture, style du
titre, vidéo en plusieurs parties. Un critère n'est retenu qu'avec 3 vidéos au moins. Résultat : episodes/recette.json, affiché sur
le site (onglet TikTok, « 📈 Ce qui marche »), et utilisé au tirage des sons (`bonus_son` : la durée qui marche le mieux passe
devant ; le profil l'était déjà par profils_tiktok.poids_profils ; depuis le 15 novembre aussi les SUJETS qui marchent : `bonus_sujet`).
RECETTE=0 pour couper le bonus."""
import datetime, json, os, re

RACINE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FICHIER = os.path.join(RACINE, "episodes", "recette.json")
NOMS = {"profil": "Profil du son", "lieu": "Lieu", "duree": "Durée", "animal": "Animal ou objet qui parle", "persos": "Personnages",
        "heure": "Heure de publication", "couverture": "Couverture", "accroche": "Titre", "partie": "Vidéo en plusieurs parties",
        "creneau": "Créneau", "anglais": "Sous-titres"}
ESSAIS = ("creneau", "anglais")                                            # essais du 21 novembre (vues dans le monde) : toujours montrés
DEBUT_ESSAIS = "2026-11-21"
PREMIER_ESSAI = 1000                                                       # vues : au-delà, TikTok a élargi la diffusion


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
        if p[:10] >= DEBUT_ESSAIS:                                         # idée 1 du 21 novembre : créneau francophonie (21 h et plus)
            out.append(("creneau", "🌍 francophonie (21 h et plus)" if hh >= 21 else "habituel"))
    if h.get("filiere") == "tiktok" and str(h.get("date") or "")[:10] >= DEBUT_ESSAIS:   # idée 3 : sous-titres anglais ou non
        out.append(("anglais", "français + anglais" if h.get("anglais") else "français seul"))
    if h.get("type_couverture"): out.append(("couverture", {"chute": "la chute", "reaction": "la réaction", "debut": "le début"}.get(h["type_couverture"], h["type_couverture"])))
    if h.get("style_accroche"): out.append(("accroche", {"pov": "« POV : … »", "question": "question au spectateur"}.get(h["style_accroche"], h["style_accroche"])))
    if "partie" in R: out.append(("partie", "oui" if R["partie"] else "non"))
    return out


def analyser(historique, mini=3):
    """{"moyenne", "videos", "plus", "moins", "par": {critère: [[valeur, vues moyennes, nombre, ×]]}} (vidéos aux vues connues)."""
    vids = [h for h in historique if h.get("vues") is not None and h.get("fichier") and not h.get("essai")]
    if not vids: return {"moyenne": 0, "videos": 0, "plus": [], "moins": [], "par": {}, "essais": {}, "sorties": sorties([])}
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
    essais = {}                                                            # essais en cours : montrés dès 1 vidéo de chaque côté
    for c in ESSAIS:
        l_ = {v: l for (c_, v), l in acc.items() if c_ == c}
        if l_: essais[NOMS[c]] = sorted([[v, round(sum(l) / len(l)), len(l)] for v, l in l_.items()], key=lambda x: -x[1])
    return {"moyenne": round(moy), "videos": len(vids), "plus": [f(x) for x in plus], "moins": [f(x) for x in moins], "par": par,
            "essais": essais, "sorties": sorties(vids)}


def sorties(vids):
    """Vidéos sorties du « premier essai » de TikTok (idée 7 du 21 novembre : rétention) : au moins 1 000 vues et 3 fois la médiane.
    {"seuil", "n", "videos": [titre, vues, fichier], "communs": [[critère, valeur, part]]} : ce qu'elles ont en commun."""
    if not vids: return {"seuil": PREMIER_ESSAI, "n": 0, "videos": [], "communs": []}
    v_ = sorted(int(h["vues"]) for h in vids); med = v_[len(v_) // 2]
    seuil = max(PREMIER_ESSAI, 3 * med)
    S = sorted([h for h in vids if int(h["vues"]) >= seuil], key=lambda h: -int(h["vues"]))
    communs = []
    if len(S) >= 3:
        cnt = {}
        for h in S:
            for c, v in set(criteres(h)): cnt[(c, v)] = cnt.get((c, v), 0) + 1
        part_tous = {}
        for h in vids:
            for c, v in set(criteres(h)): part_tous[(c, v)] = part_tous.get((c, v), 0) + 1
        for (c, v), n in cnt.items():
            p_s, p_t = n / len(S), part_tous[(c, v)] / len(vids)
            if p_s >= 0.6 and p_s >= p_t + 0.2: communs.append([NOMS.get(c, c), v, round(p_s, 2)])   # plus fréquent que d'habitude
        communs.sort(key=lambda x: -x[2])
    return {"seuil": seuil, "n": len(S), "videos": [[str(h.get("titre") or "")[:60], int(h["vues"]), h.get("fichier")] for h in S[:8]],
            "communs": communs[:6]}


VIDES = set("""avec dans pour sans plus moins tout tous toute toutes cette cette comme quand alors parce mais elle elles ils nous vous leur
leurs être avoir fait faire petit petite grand grande trop très bien encore juste aussi vraiment titre partie video vidéo tiktok pourtoi
fyp foryou foryoupage viral humour drole drôle sketch animation dessin dessinanime avait savait était etait allait voulait
pouvait faisait disait quelqu""".split())


def mots_titre(t):
    """Sujets d'un titre de son TikTok : hashtags et mots de 5 lettres ou plus (sans les mots vides ni les hashtags génériques)."""
    t = str(t or "").lower()
    m = set(re.findall(r"#([\wà-ÿ]{4,30})", t)) | set(re.findall(r"\b([a-zà-ÿ]{5,20})\b", re.sub(r"#[\wà-ÿ]+", " ", t)))
    return {x for x in m if x not in VIDES and not x.isdigit()}


def mots_gagnants(historique, mini=3):
    """Idée 18 du 15 novembre : les SUJETS qui marchent chez nous (mots et hashtags du titre du son repris, 3 vidéos au moins) :
    {mot: ×vues par rapport à la moyenne}."""
    vids = [h for h in historique if h.get("vues") is not None and h.get("titre_source") and not h.get("essai")]
    if len(vids) < 6: return {}
    moy = sum(int(h["vues"]) for h in vids) / len(vids) or 1
    acc = {}
    for h in vids:
        for w in mots_titre(h["titre_source"]): acc.setdefault(w, []).append(int(h["vues"]))
    return {w: round(sum(l) / len(l) / moy, 2) for w, l in acc.items() if len(l) >= mini and len(l) < 0.8 * len(vids)}


def bonus_sujet(v, recette=None):
    """Points de potentiel (±15) pour un son dont le titre parle d'un sujet qui marche (ou qui ne marche pas) chez nous."""
    if os.environ.get("RECETTE", "1") == "0": return 0, []
    if recette is None:
        try: recette = json.load(open(FICHIER, encoding="utf-8"))
        except (OSError, ValueError): return 0, []
    M = recette.get("mots") or {}
    vus = [w for w in mots_titre(v.get("titre")) if w in M]
    if not vus: return 0, []
    return int(max(-15, min(15, round(sum((M[w] - 1) * 12 for w in vus))))), vus


def enregistrer(historique):
    r = analyser(historique); r["maj"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes")
    r["mots"] = mots_gagnants(historique)
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
