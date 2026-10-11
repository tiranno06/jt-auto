"""Le « studio » du moteur cartoon : direction artistique et réalisation, sans IA (gratuit) — Claude peut les enrichir s'il est disponible.

1. bible(sk, roles) : la bible de l'épisode, propre à cette vidéo.
   Lieu de chaque scène (catalogue de decor_dessin), heure (matin, jour, soir, nuit), lumière (côté, teinte, étalonnage),
   style de décor IA, garde-robe de chaque personnage selon le lieu et son rôle dans la scène (médecin, serveur, prof…),
   figurants à l'arrière-plan, gags écrits dans le décor, ambiances (vapeur, poussière dans la lumière, pluie, neige).
   Si l'auteur (Claude) a rempli sk["studio"], ses choix sont repris après vérification (catalogues fermés) ; sinon tout est
   déduit du texte (mots-clés, ponctuation) avec une graine propre à l'épisode : deux vidéos ne se ressemblent pas.
2. realiser(ph, places, B) : le storyboard, réplique par réplique, calé sur le minutage réel du son.
   Valeur de plan (large, moyen, serré, très serré, plongée, contre-plongée, par-dessus l'épaule), mouvement de caméra
   (fixe, avancée lente, recul, travelling, caméra à l'épaule, zoom choc), geste, réaction de celui qui écoute,
   regard caméra (façon « The Office ») sur les silences gênants.
3. moments(ph) : ce que dit le son (silences, cris, rires) pour caler les réactions et la caméra.
4. emotion_texte(texte, niveau) : émotion devinée sans indication de jeu (doublage sans Claude).
5. memoire : ce qui a été tourné (lieu, heure, plans) dans episodes/studio_memoire.json, pour varier d'une vidéo à l'autre."""
import hashlib, json, os, re
import numpy as np

import decor_dessin as DD
import marionnette as M

MOMENTS = ("matin", "jour", "soir", "nuit")
PLANS = ("large", "moyen", "serre", "tres_serre", "plongee", "contre_plongee", "epaule")
MOUVEMENTS = ("fixe", "avance", "recul", "travelling", "epaule", "zoom_choc")
REACTIONS = ("aucune", "regard_camera", "yeux_au_ciel", "sceptique", "choc", "rire", "gene", "soupir", "facepalm", "bras_croises")
STYLES_IA = {                                                              # ajouté à la description du décor envoyée à SDXL
    "matin": "soft pink morning light", "jour": "bright daylight", "soir": "warm golden evening light, lamps on",
    "nuit": "night, dark blue ambience, warm lamp light"}
ETALONNAGE = {"matin": (1.02, 0.99, 0.97), "jour": (1.0, 1.0, 1.0), "soir": (1.03, 0.99, 0.94), "nuit": (0.9, 0.93, 1.04)}
LUMIERE_LIEU = {"salon": -1, "cuisine": -1, "bureau": -1, "cabinet_medical": 1, "bar": 1, "chambre": 1, "salle_sport": -1,
                "magasin": -1, "classe": 1, "rue": -1, "restaurant": 1}

# gestes : (bras gauche, bras droit) en angles épaule / coude (0 = vers le bas, positif = vers l'extérieur droit), formes des mains
GESTES = {
    "croises":       (((22, 72), (-22, -72)), ("poing", "poing")),            # bras croisés : blasé, fier, « j'attends »
    "haussement":    (((-45, -85), (45, 85)), ("paume", "paume")),            # « bah quoi ? »
    "desespoir":     (((-165, -45), (165, 45)), ("ouverte", "ouverte")),      # bras levés vers la tête
    "pointe_d":      (((-18, 8), (98, -6)), ("ouverte", "index")),            # accusation vers la droite
    "pointe_g":      (((-98, 6), (18, -8)), ("index", "ouverte")),
    "poing":         (((-18, 8), (150, -130)), ("ouverte", "poing")),         # victoire, colère
    "mains_hanches": (((-40, 95), (40, -95)), ("poing", "poing")),
    "facepalm":      (((-18, 8), (160, 52)), ("ouverte", "paume")),           # main sur le visage
    "gratte_tete":   (((-18, 8), (165, 35)), ("ouverte", "ouverte")),         # perplexe
    "menton":        (((22, 72), (150, 70)), ("poing", "poing")),             # il réfléchit, main au menton
    "stop":          (((-18, 8), (100, -40)), ("ouverte", "paume")),          # « stop ! », « attends »
    "pouce":         (((-18, 8), (120, -95)), ("ouverte", "pouce")),          # « nickel »
    "compte":        (((-60, -50), (60, 70)), ("index", "paume")),            # il compte sur ses doigts
    "bras_ouverts":  (((-110, -20), (110, 20)), ("paume", "paume")),          # accueil, évidence
    "telephone":     (((-18, 8), (150, 75)), ("ouverte", "poing")),           # main à l'oreille
    "supplie":       (((-60, 75), (60, -75)), ("ouverte", "ouverte")),        # mains jointes
    "explique":      (((-60, -40), (70, -50)), ("paume", "index")),
}
POSES = {k: v[0] for k, v in GESTES.items()}

def _h(*xs):
    return int(hashlib.md5("|".join(map(str, xs)).encode()).hexdigest()[:8], 16)

# ------------------------------------------------------------------ émotion sans indication de jeu
def emotion_texte(texte, niveau=0.5):
    """Émotion devinée d'après la réplique (mots, ponctuation) et le volume de la voix : sert quand aucune indication [..] n'est donnée."""
    t = (texte or "").lower(); fort = niveau > 0.75
    if re.search(r"\b((ha|hi|hé)( ?(ha|hi|hé))+|mdr|ptdr|lol|je rigole)\b", t): return "rire"
    if re.search(r"\b(d[ée]sol[ée]|pardon|oups|euh+|bah? euh|enfin\b.*\benfin)", t): return "gene"
    if re.search(r"(non mais|t'es s[ée]rieux|c'est pas possible|j'en ai marre|ras le bol|n'importe quoi|tais[- ]toi|d[ée]gage)", t): return "colere" if not fort else "cri"
    if re.search(r"\b(quoi ?\?!|hein ?\?!|comment ?\?!|oh l[àa]|mon dieu|c'est pas vrai|s[ée]rieux ?\?)", t) or re.search(r"\?!|!\?", t): return "choc"
    if re.search(r"\b(g[ée]nial|trop bien|incroyable|youpi|enfin|g[ae]gn[ée]|yes|trop fort|j'adore)\b", t) and "!" in t: return "joie"
    if re.search(r"\b(j'te jure|tu crois|vraiment \?|ah bon|mouais|c'est [çc]a)\b", t): return "sceptique"
    if re.search(r"\b(je t'aime|mon c(oe|œ)ur|mon amour|je suis amoureu)", t): return "amour"
    if re.search(r"\b(pff+|bof|bon\.|super\.|tant pis|laisse tomber)\b", t) or t.rstrip().endswith("..."): return "blase"
    if re.search(r"\b(j'ai peur|au secours|vite|on va mourir|panique)\b", t): return "panique"
    if re.search(r"\b(snif|ouin|je pleure|c'est triste)\b", t): return "pleurs"
    if "!" in t and fort: return "cri"
    return "neutre"

def geste(texte, emo, k=0):
    """Geste choisi d'après la réplique (ponctuation, mots) quand l'émotion n'impose rien."""
    t = (texte or "").lower()
    if emo in ("blase", "fier"): return "croises" if k % 2 == 0 else "mains_hanches"
    if emo in ("pleurs", "panique"): return "desespoir"
    if emo == "gene": return "gratte_tete"
    if emo == "sceptique": return "menton" if k % 2 else "croises"
    if emo in ("colere", "cri") and "!" in t: return "pointe"
    if re.search(r"\b(stop|attends|arr[êe]te|calme[- ]toi|doucement)\b", t): return "stop"
    if re.search(r"\b(t[ée]l[ée]phone|allo|all[ôo]|appelle)\b", t): return "telephone"
    if re.search(r"\b(un|deux|trois|premi[èe]rement|d'abord|ensuite)\b.*\b(deux|trois|quatre|ensuite|puis)\b", t): return "compte"
    if re.search(r"\b(s'il te pla[îi]t|s'il vous pla[îi]t|pitié|je t'en supplie)\b", t): return "supplie"
    if re.search(r"\b(nickel|parfait|ok|d'accord|top|carr[ée])\b", t) and not t.rstrip().endswith("?"): return "pouce"
    if re.search(r"\b(toi|tu|t'|vous)\b", t) and "!" in t: return "pointe"
    if t.rstrip().endswith("?") and re.search(r"\b(quoi|pourquoi|comment|hein)\b", t): return "haussement"
    if re.search(r"\b(bienvenue|voil[àa]|regarde|tadam)\b", t): return "bras_ouverts"
    if re.search(r"\b(gagn[ée]|yes|enfin|trop fort)\b", t): return "poing"
    if re.search(r"\b(c'est (simple|facile)|en fait|parce que|tu vois)\b", t) and len(t) > 30: return "explique"
    if re.search(r"\b(oh non|la honte|pas possible)\b", t): return "facepalm"
    return None

# ------------------------------------------------------------------ garde-robe
PALETTE = [(220, 80, 70), (70, 120, 190), (90, 160, 110), (240, 180, 60), (150, 90, 170), (240, 130, 70), (60, 70, 100),
           (200, 200, 205), (120, 90, 60), (230, 140, 170), (60, 150, 160), (170, 50, 70)]
BAS_PALETTE = [(70, 100, 150), (50, 55, 70), (120, 100, 80), (90, 90, 100), (150, 130, 100), (40, 40, 48)]

# tenue « métier » du personnage qui mène la scène dans un lieu donné (les autres sont en tenue de ville)
METIERS = {
    "cabinet_medical": dict(haut="blouse", bas="pantalon", c_bas=(90, 100, 120), chaussures="ville", c_chaussures=(240, 240, 240), details=("stethoscope", "badge", "stylos")),
    "bureau": dict(haut="costume", c_haut=(60, 65, 90), bas="pantalon", c_bas=(60, 65, 90), chaussures="ville", c_chaussures=(40, 30, 25), details=("cravate", "badge", "montre")),
    "bar": dict(haut="chemise", c_haut=(30, 30, 36), bas="pantalon", c_bas=(30, 30, 36), chaussures="ville", c_chaussures=(30, 30, 30), details=("noeud_pap",)),
    "restaurant": dict(haut="tablier", c_haut=(250, 250, 250), c_tablier=(40, 40, 48), bas="pantalon", c_bas=(40, 40, 48), chaussures="ville", c_chaussures=(30, 30, 30), details=("noeud_pap",)),
    "salle_sport": dict(haut="debardeur", c_haut=(230, 60, 60), bas="short", c_bas=(40, 40, 48), chaussures="baskets", c_chaussures=(250, 250, 250), details=("montre",)),
    "magasin": dict(haut="polo", c_haut=(230, 60, 60), bas="pantalon", c_bas=(50, 55, 70), chaussures="baskets", c_chaussures=(40, 40, 48), details=("badge",)),
    "classe": dict(haut="gilet", c_haut=(150, 110, 80), c_dessous=(240, 240, 235), bas="pantalon", c_bas=(110, 100, 90), chaussures="ville", c_chaussures=(80, 50, 30), details=("lunettes_vue", "echarpe")),
    "cuisine": dict(haut="tablier", c_haut=(120, 160, 210), c_tablier=(250, 250, 245), bas="jean", c_bas=(70, 100, 150), chaussures="chaussons", c_chaussures=(220, 120, 140), details=()),
}
VILLE = {                                                                   # tenues de ville selon le lieu (et l'heure)
    "salle_sport": ("survetement", "debardeur"), "chambre": ("pyjama",), "bureau": ("chemise", "pull", "polo"),
    "bar": ("chemise", "tshirt", "pull"), "restaurant": ("chemise", "pull", "robe"), "rue": ("capuche", "pull", "tshirt", "chemise"),
}

def tenue(perso, role_scene, lieu, moment, graine):
    """Garde-robe d'un personnage pour l'épisode : métier s'il mène la scène dans un lieu « professionnel », sinon tenue de ville."""
    rng = np.random.default_rng(graine)
    if role_scene == "metier" and lieu in METIERS:
        c = dict(METIERS[lieu]); c.setdefault("c_haut", (246, 248, 252)); c.setdefault("motif", "uni")
        if perso == "noeud" and c["bas"] == "pantalon" and rng.random() < 0.5: c["bas"] = "jupe"
        return c
    if lieu == "chambre" or (moment == "nuit" and lieu == "salon" and rng.random() < 0.6): choix = ("pyjama",)
    else: choix = VILLE.get(lieu) or ("tshirt", "pull", "chemise", "capuche", "polo")
    haut = choix[int(rng.integers(len(choix)))]
    if haut == "robe" and perso != "noeud": haut = "chemise"
    c_haut = PALETTE[int(rng.integers(len(PALETTE)))]
    motif = "uni" if rng.random() < 0.6 else ("rayures", "carreaux", "pois")[int(rng.integers(3))]
    if haut == "pyjama": motif = ("rayures", "pois", "carreaux")[int(rng.integers(3))]
    if haut in ("capuche", "survetement", "debardeur"): motif = "uni"
    bas = "jogging" if haut in ("survetement", "capuche") and rng.random() < 0.6 else ("short" if haut == "debardeur" else
          ("jupe" if perso == "noeud" and rng.random() < 0.5 else ("jean" if rng.random() < 0.55 else "pantalon")))
    if haut == "pyjama": bas = "pantalon"
    c_bas = c_haut if haut in ("pyjama", "survetement") else BAS_PALETTE[int(rng.integers(len(BAS_PALETTE)))]
    chaus = "chaussons" if haut == "pyjama" else ("ballerines" if bas == "jupe" else ("baskets" if rng.random() < 0.6 else ("ville" if rng.random() < 0.7 else "bottes")))
    details = []
    if haut in ("tshirt", "capuche") and rng.random() < 0.5: details.append("logo")
    if rng.random() < 0.25: details.append("montre")
    if perso == "noeud" and rng.random() < 0.4: details.append("collier")
    if moment in ("matin", "soir") and lieu == "rue" and rng.random() < 0.5: details.append("echarpe")
    if haut == "chemise" and lieu == "bureau": details.append("cravate")
    return dict(haut=haut, c_haut=c_haut, motif=motif, c_motif=M._fonce(c_haut, 0.72) if motif != "pois" else (250, 250, 248),
                bas=bas, c_bas=c_bas, chaussures=chaus, c_chaussures=PALETTE[int(rng.integers(len(PALETTE)))] if chaus != "ville" else (50, 35, 25),
                details=tuple(details))

def _costume_valide(c):
    """Costume proposé par Claude, ramené aux catalogues de marionnette.py (sinon None)."""
    if not isinstance(c, dict) or c.get("haut") not in M.HAUTS: return None
    def col(v, d):
        try:
            v = [int(x) for x in v][:3]; return tuple(max(0, min(255, x)) for x in v) if len(v) == 3 else d
        except (TypeError, ValueError):
            return NOMS_COULEURS.get(str(v).lower(), d)
    out = dict(haut=c["haut"], c_haut=col(c.get("c_haut"), (120, 150, 200)), motif=c.get("motif") if c.get("motif") in M.MOTIFS else "uni",
               bas=c.get("bas") if c.get("bas") in M.BAS else "jean", c_bas=col(c.get("c_bas"), (70, 100, 150)),
               chaussures=c.get("chaussures") if c.get("chaussures") in M.CHAUSSURES else "baskets", c_chaussures=col(c.get("c_chaussures"), (240, 240, 240)),
               details=tuple(d for d in (c.get("details") or []) if d in M.DETAILS)[:5])
    out["c_motif"] = col(c.get("c_motif"), M._fonce(out["c_haut"], 0.72))
    return out

NOMS_COULEURS = {"rouge": (220, 60, 60), "bleu": (60, 110, 200), "bleu marine": (40, 50, 90), "vert": (80, 160, 100), "jaune": (245, 200, 60),
                 "orange": (240, 130, 60), "violet": (140, 80, 170), "rose": (240, 150, 180), "noir": (40, 40, 46), "blanc": (246, 246, 246),
                 "gris": (150, 150, 158), "marron": (130, 90, 60), "beige": (220, 200, 170), "kaki": (120, 130, 80), "bordeaux": (130, 40, 60)}

# ------------------------------------------------------------------ bible de l'épisode
def bible(sk, roles):
    """Direction artistique de l'épisode (voir le docstring du module). roles : rôles dessinés (presentateur, invite, envoyee)."""
    txt_global = " ".join([str(sk.get(k) or "") for k in ("sujet", "titre_accroche", "legende")] + [str((sk.get("doublage") or {}).get("contexte") or "")]
                          + [r.get("t", "") for r in sk.get("repliques", [])])
    graine = _h(txt_global, sk.get("sujet"))
    rng = np.random.default_rng(graine)
    S = sk.get("studio") if isinstance(sk.get("studio"), dict) else {}
    dec = [sc for sc in (sk.get("decoupage") or []) if sc.get("repliques")] or [{"repliques": list(range(len(sk.get("repliques", []))))}]
    t_low = txt_global.lower()
    # heure : imposée par Claude, sinon d'après le texte, sinon variée (en évitant de refaire la même que la dernière vidéo)
    moment = S.get("moment") if S.get("moment") in MOMENTS else None
    if not moment:
        if re.search(r"\b(nuit|minuit|dormir|insomnie|3 ?h du mat|cauchemar)\b", t_low): moment = "nuit"
        elif re.search(r"\b(soir|soirée|apéro|dîner|ce soir)\b", t_low): moment = "soir"
        elif re.search(r"\b(matin|réveil|petit[- ]déj|café du matin|lundi matin)\b", t_low): moment = "matin"
        else:
            deja = memoire_recente("moment")
            choix = [m for m in ("jour", "jour", "soir", "matin") if m != deja] or ["jour"]; moment = choix[int(rng.integers(len(choix)))]
    lieux = []
    for k, sc in enumerate(dec):
        l = None
        if isinstance(S.get("lieux"), list) and k < len(S["lieux"]) and S["lieux"][k] in DD.LIEUX: l = S["lieux"][k]
        decor_sc = " ".join(str(sc.get(c) or "") for c in ("decor", "scene", "titre"))      # la description du décor passe avant les répliques
        lignes_sc = [sk["repliques"][i]["t"] for i in sc.get("repliques", []) if i < len(sk.get("repliques", []))]
        texte_sc = " ".join(lignes_sc[:max(1, len(lignes_sc) // 2)] * 2 + lignes_sc[max(1, len(lignes_sc) // 2):])   # le début de la scène pose le lieu
        lieux.append(l or DD.lieu_de(decor_sc, "") or DD.lieu_de(texte_sc, "") or DD.lieu_de(t_low, "salon"))
    gags = [str(g)[:80] for g in (S.get("gags") or []) if str(g).strip()][:4]
    # qui mène chaque scène (le « métier » du lieu) : celui qui parle le plus de questions / le premier à parler
    costumes = {}
    for k, role in enumerate(roles):
        perso = M.ROLES.get(role, "bonnet")
        c = _costume_valide((S.get("costumes") or {}).get(role)) if isinstance(S.get("costumes"), dict) else None
        if c is None:
            lieu0 = lieux[0]; meneur = _meneur(sk, dec[0], roles)
            c = tenue(perso, "metier" if role == meneur else "client", lieu0, moment, graine + 17 * k)
        costumes[role] = c
    figurants = []
    if os.environ.get("FIGURANTS", "1") != "0":
        for k, l in enumerate(lieux):
            n = {"bar": 2, "restaurant": 2, "bureau": 1, "magasin": 1, "rue": 2, "salle_sport": 1, "classe": 0}.get(l, 0)
            for j in range(n):
                perso = ("lunettes", "meche")[j % 2]; act = {"bar": ("boit", "telephone"), "restaurant": ("mange", "boit"), "bureau": ("tape", "telephone"),
                                                            "magasin": ("cherche", "telephone"), "rue": ("marche", "telephone"), "salle_sport": ("souleve", "boit")}[l][j % 2]
                figurants.append(dict(scene=k, perso=perso, activite=act, x=(150, 930)[(j + graine) % 2] if n == 1 else (150, 930)[j],
                                      costume=tenue(perso, "client", l, moment, graine + 101 + j + 7 * k)))
    ambiances = set(a for a in (S.get("ambiances") or []) if a in ("vapeur", "poussiere", "pluie", "neige", "neon"))
    if re.search(r"\bpluie|pleu[tv]|rain|parapluie", t_low): ambiances.add("pluie")
    if re.search(r"\bneige|no[ëe]l|snow|hiver", t_low): ambiances.add("neige")
    if "cuisine" in lieux or "restaurant" in lieux: ambiances.add("vapeur")
    if moment in ("matin", "soir") and any(l not in ("rue",) for l in lieux): ambiances.add("poussiere")
    if "bar" in lieux: ambiances.add("neon")
    lum = LUMIERE_LIEU.get(lieux[0], -1)
    heure = {"matin": (8, 5), "jour": (14, 20), "soir": (19, 40), "nuit": (2, 15)}[moment]
    return dict(graine=graine, moment=moment, lieux=lieux, gags=gags, costumes=costumes, figurants=figurants, ambiances=sorted(ambiances),
                lumiere=lum, ombre=0.24 if moment != "nuit" else 0.32, etalonnage=ETALONNAGE[moment], heure=heure,
                style_ia=STYLES_IA[moment], plans=S.get("plans") if isinstance(S.get("plans"), list) else [],
                source="auteur" if S else "robot")

def _meneur(sk, sc, roles):
    """Rôle qui « tient la boutique » dans la scène : celui qui pose le plus de questions (médecin, prof, serveur…)."""
    score = {r: 0 for r in roles}
    for i in sc.get("repliques", []):
        if i >= len(sk.get("repliques", [])): continue
        r = sk["repliques"][i]
        if r.get("p") in score: score[r["p"]] += 2 * r.get("t", "").count("?") + 1
    return max(roles, key=lambda r: (score.get(r, 0), -roles.index(r))) if roles else None

# ------------------------------------------------------------------ ce que dit le son
def moments(ph):
    """Instants clés du son : silences (avant une réplique, ≥ 0,7 s), pics de voix (cris), rires. [(t, type, indice de réplique)]."""
    out = []
    for j, q in enumerate(ph):
        if j and q["deb"] - ph[j - 1]["fin"] >= 0.7: out.append((ph[j - 1]["fin"] + 0.15, "silence", j))
        lv = np.asarray(q.get("lv", []), float)
        if len(lv) and lv.max() > 0.92:
            k = int(np.argmax(lv)); out.append((q["deb"] + k / 30.0, "pic", j))
        if q.get("emo") == "rire" or q.get("rires"): out.append((q["deb"], "rire", j))
    return out

# ------------------------------------------------------------------ storyboard
def realiser(ph, places, B):
    """Ajoute à chaque réplique q : plan, mouvement, reaction, regard_camera (et respecte les choix de l'auteur s'il y en a)."""
    plans_auteur = {}
    for x in B.get("plans") or []:
        if isinstance(x, dict) and isinstance(x.get("replique"), int): plans_auteur[x["replique"]] = x
    silences = {j for t, ty, j in moments(ph) if ty == "silence"}
    for j, q in enumerate(ph):
        n = len(places.get(q["scene"], [])); dur = q["fin"] - q["deb"]; h = _h(B["graine"], j)
        nouvelle = j == 0 or ph[j - 1]["scene"] != q["scene"]
        plan, mouv = q.get("cam") or "large", "fixe"
        if q["p"] == "narrateur": plan = "large"
        elif nouvelle: plan, mouv = "large", ("recul" if j else "avance")
        elif q["emo"] in ("cri", "colere"): plan, mouv = "contre_plongee", "epaule"
        elif q["emo"] in ("pleurs", "soupir", "gene"): plan, mouv = ("plongee" if h % 2 else "serre"), "avance"
        elif q["emo"] in ("choc", "panique"): plan, mouv = "tres_serre", "zoom_choc"
        elif n >= 2:                                                       # dialogue : on varie les valeurs de plan d'une réplique à l'autre
            plan = ("serre", "epaule", "moyen", "serre", "epaule" if dur > 1.5 else "serre")[(j + h) % 5]
            mouv = ("fixe", "avance", "travelling")[h % 3] if plan != "epaule" else "fixe"
        elif plan == "serre" and dur > 3.0: mouv = "avance"
        if q.get("chute") and j == len(ph) - 1: plan, mouv = "serre", "avance"
        elif q.get("chute"): plan = "tres_serre" if h % 2 else "serre"
        if n <= 1 and plan in ("epaule",): plan = "serre"
        reaction = "aucune"
        if q["emo"] in ("cri", "colere"): reaction = ("choc", "bras_croises", "yeux_au_ciel")[h % 3]
        elif q["emo"] in ("blase", "sceptique"): reaction = ("sceptique", "yeux_au_ciel")[h % 2]
        elif q["emo"] == "gene" or q["texte"].rstrip().endswith("..."): reaction = "gene"
        elif q.get("chute"): reaction = ("regard_camera", "facepalm", "choc", "rire", "yeux_au_ciel")[h % 5]
        elif q["texte"].rstrip().endswith("?"): reaction = ("sceptique", "aucune", "aucune")[h % 3]
        if q.get("rires"): reaction = "rire"                               # des rires dans la bande son : celui qui écoute rit
        a = plans_auteur.get(q["i"]) or {}
        if a.get("plan") in PLANS: plan = a["plan"]
        if a.get("mouvement") in MOUVEMENTS: mouv = a["mouvement"]
        if a.get("reaction") in REACTIONS: reaction = a["reaction"]
        if a.get("geste") in GESTES: q["geste"] = a["geste"]
        q["plan"], q["mouvement"], q["reaction"] = plan, mouv, reaction
        q["regard_camera"] = bool(j in silences or (a.get("regard_camera") is True))
    return ph

# ------------------------------------------------------------------ mémoire du studio
MEMOIRE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "studio_memoire.json")

def _memoire():
    try:
        with open(MEMOIRE, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return []

def memoire_recente(cle):
    m = _memoire(); return (m[-1].get(cle) if m else None)

def memoriser(B, ph, duree, controle=""):
    """Ce qui a été tourné (pour varier les prochaines vidéos et comparer avec les vues) : 200 dernières vidéos."""
    m = _memoire()
    from collections import Counter
    m.append(dict(moment=B.get("moment"), lieux=B.get("lieux"), source=B.get("source"), duree=round(float(duree or 0), 1),
                  plans=dict(Counter(q.get("plan") for q in ph)), mouvements=dict(Counter(q.get("mouvement") for q in ph)),
                  costumes={r: c.get("haut") for r, c in (B.get("costumes") or {}).items()}, figurants=len(B.get("figurants") or []),
                  ambiances=B.get("ambiances"), controle=str(controle)[:200]))
    try:
        os.makedirs(os.path.dirname(MEMOIRE), exist_ok=True)
        with open(MEMOIRE, "w", encoding="utf-8") as f: json.dump(m[-200:], f, ensure_ascii=False, indent=1)
    except OSError: pass
