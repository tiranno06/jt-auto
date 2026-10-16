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
MOUVEMENTS = ("fixe", "avance", "recul", "travelling", "epaule", "zoom_choc", "vertige")
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

# ------------------------------------------------------------------ intonation (hauteur et énergie de la voix)
def prosodie(a, sr=22050, fps=30):
    """Hauteur de la voix (Hz, 0 quand elle ne chante pas : consonnes, silences) et énergie, image par image (1/30 s)."""
    a = np.asarray(a, np.float32); hop = sr // fps; n = max(1, len(a) // hop); N = 1024
    f0 = np.zeros(n, np.float32); en = np.zeros(n, np.float32)
    lo, hi = sr // 420, sr // 65
    seuil = 0.08 * (np.percentile(np.abs(a), 99) + 1e-6) if len(a) else 1
    for i in range(n):
        seg = a[i * hop:i * hop + N]
        if len(seg) < N // 2: break
        seg = seg - seg.mean(); en[i] = float(np.sqrt(np.mean(seg ** 2)))
        if en[i] < seuil: continue
        X = np.fft.rfft(seg * np.hanning(len(seg)), 2 * N); ac = np.fft.irfft(np.abs(X) ** 2)[:N]
        if ac[0] <= 0: continue
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.35 * ac[0]: f0[i] = sr / k
    return f0, en

def intonation(f0, ref):
    """Hauteur relative à la voix habituelle du personnage (en « quarts d'octave » : +1 ≈ 3 demi-tons plus aigu), lissée et
    maintenue sur les consonnes. Renvoie (courbe par image, résumé : moyenne, étendue, montée finale)."""
    z = np.zeros(len(f0), np.float32); v = f0 > 0
    if not v.any() or not ref: return z, dict(moy=0.0, etendue=0.0, fin=0.0)
    z[v] = 12 * np.log2(f0[v] / ref) / 3
    der = 0.0
    for i in range(len(z)):                                                # on garde la dernière valeur chantée
        if v[i]: der = z[i]
        else: z[i] = der * 0.9; der = z[i]
    z = np.convolve(z, np.ones(5) / 5, "same").astype(np.float32)
    zv = z[v]; fin = float(np.mean(zv[-6:]) - np.mean(zv[max(0, len(zv) - 18):max(1, len(zv) - 6)])) if len(zv) >= 12 else 0.0
    return z, dict(moy=float(np.mean(zv)), etendue=float(np.percentile(zv, 90) - np.percentile(zv, 10)), fin=fin)

# ------------------------------------------------------------------ émotion sans indication de jeu
def emotion_texte(texte, niveau=0.5, ton=None):
    """Émotion devinée d'après la réplique (mots, ponctuation), le volume et l'intonation de la voix (ton = résumé d'intonation) :
    sert quand aucune indication [..] n'est donnée."""
    e = _emotion_mots(texte, niveau)
    if e != "neutre" or not ton: return e
    t = (texte or "").strip()
    if ton["moy"] > 1.0 and niveau > 0.6: return "cri" if "!" in t else ("choc" if ton["fin"] > 0.5 else "joie")   # voix haute et forte
    if ton["fin"] > 0.9 and not t.endswith("?"): return "sceptique"         # ça monte à la fin sans être une question : « ah bon… »
    if ton["etendue"] > 2.4 and niveau > 0.5: return "joie"                 # voix très mélodieuse, animée
    if ton["moy"] < -0.7 and niveau < 0.45: return "blase"                  # voix basse et molle
    return "neutre"

def _emotion_mots(texte, niveau=0.5):
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
    "administration": dict(haut="chemise", c_haut=(248, 248, 246), bas="pantalon", c_bas=(45, 45, 50), chaussures="ville", c_chaussures=(30, 30, 30), details=("badge", "ceinture", "lunettes_vue")),
    "cuisine": dict(haut="tablier", c_haut=(120, 160, 210), c_tablier=(250, 250, 245), bas="jean", c_bas=(70, 100, 150), chaussures="chaussons", c_chaussures=(220, 120, 140), details=()),
}
VILLE = {                                                                   # tenues de ville selon le lieu (et l'heure)
    "salle_sport": ("survetement", "debardeur"), "chambre": ("pyjama",), "bureau": ("chemise", "pull", "polo", "col_roule"),
    "bar": ("chemise", "tshirt", "pull", "blouson", "hawai", "col_roule"), "restaurant": ("chemise", "pull", "robe", "col_roule"),
    "rue": ("capuche", "pull", "tshirt", "chemise", "doudoune", "blouson"),
}
CHAPEAUX_RUE = ("bonnet", "casquette", "beret", "bob", "chapeau")          # couvre-chefs de ville (dehors surtout)

# thèmes d'époque ou de métier reconnus dans le texte : la tenue de TOUS les personnages suit (comme les chaînes « toons »)
THEMES = [
    (r"pr[ée]histo|cro-?magnon|caverne|homme des cavernes|mammouth|n[ée]andert", dict(haut="tunique", c_haut=(160, 110, 60), motif="taches", c_motif=(100, 65, 35),
        bas="", chaussures="", cheveux={"h": "herisse", "f": "ondule"}, barbe="barbe_pleine")),
    (r"\b(roi|reine|versailles|marquis|marquise|comtesse|louis xi|xviii|18e si[èe]cle|r[ée]volution fran|napol[ée]on|aristo)", dict(haut="redingote", c_haut=(40, 80, 160),
        c_dessous=(235, 185, 80), bas="pantalon", c_bas=(40, 80, 160), chaussures="ville", c_chaussures=(30, 30, 30), cheveux={"h": "anglaises", "f": "anglaises"},
        robe_f=dict(haut="robe", c_haut=(240, 180, 200), motif="uni"), chapeau_h="tricorne", c_chapeau=(35, 35, 45))),
    (r"\b(police|policier|flic|gendarme|commissariat|garde à vue|contr[ôo]le d'identit)", dict(haut="uniforme", c_haut=(40, 55, 100), bas="pantalon", c_bas=(40, 55, 100),
        chaussures="ville", c_chaussures=(20, 20, 20), chapeau="casquette", c_chapeau=(40, 55, 100), un_seul=True)),
    (r"\b(chantier|ma[çc]on|btp|ouvrier)", dict(haut="tshirt", c_haut=(240, 140, 40), bas="jean", c_bas=(70, 90, 120), chaussures="bottes", c_chaussures=(90, 60, 40),
        chapeau="casque_chantier", un_seul=True)),
    (r"\b(chef cuisinier|cuisinier|top chef|p[âa]tissier|boulanger)", dict(haut="tablier", c_haut=(250, 250, 250), c_tablier=(250, 250, 250), bas="pantalon", c_bas=(50, 50, 55),
        chaussures="ville", chapeau="toque", un_seul=True)),
    (r"\b(plage|vacances|camping|tropiques|hawa[iï]|bronzer)", dict(haut="hawai", c_haut=(60, 170, 200), motif="fleurs", c_motif=(250, 120, 140), bas="short",
        c_bas=(230, 220, 190), chaussures="chaussons", chapeau="bob", c_chapeau=(240, 230, 200))),
    (r"\b(prince|princesse|ch[âa]teau|couronn)", dict(chapeau="couronne", un_seul=True)),
]

def theme(t_low):
    for motif, c in THEMES:
        if re.search(motif, t_low): return c
    return None

def appliquer_theme(c, T, genre, premier):
    """Tenue d'un personnage d'après le thème T (le premier rôle seulement pour les thèmes « un_seul » : le policier, le chef…)."""
    if not T or (T.get("un_seul") and not premier): return c
    c = dict(c)
    for k, v in T.items():
        if k in ("cheveux", "barbe", "robe_f", "chapeau_h", "un_seul"): continue
        if v == "": c.pop(k, None)
        else: c[k] = v
    if genre == "f" and T.get("robe_f"): c.update(T["robe_f"]); c.pop("chapeau", None); c["bas"] = "jupe"
    if genre == "h" and T.get("chapeau_h"): c["chapeau"] = T["chapeau_h"]
    if T.get("cheveux"): c["cheveux"] = T["cheveux"].get(genre or "h")
    if T.get("barbe") and genre == "h": c["details"] = tuple(c.get("details") or ()) + (T["barbe"],)
    return c

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
    if rng.random() < 0.3 and haut in ("tshirt", "pull", "chemise", "hawai", "col_roule") and motif == "uni":     # imprimés dessinés
        motif = ("fleurs", "losanges", "chevrons", "etoiles", "palmiers")[int(rng.integers(5))] if haut != "hawai" else "fleurs"
    if haut == "hawai": motif = ("fleurs", "palmiers")[int(rng.integers(2))]
    details = []
    if rng.random() < 0.25: details.append(("sac_bandouliere", "casque_audio", "bretelles")[int(rng.integers(3))] if lieu in ("rue", "bar", "magasin") else "montre")
    if perso == "noeud" and rng.random() < 0.5: details.append("boucles_oreilles")
    if rng.random() < 0.15: details.append("bracelet")
    chapeau = None
    if lieu == "rue" and rng.random() < (0.6 if moment in ("matin", "soir", "nuit") else 0.35): chapeau = CHAPEAUX_RUE[int(rng.integers(len(CHAPEAUX_RUE)))]
    elif haut in ("capuche", "survetement", "doudoune") and rng.random() < 0.25: chapeau = ("bonnet", "casquette")[int(rng.integers(2))]
    if haut in ("tshirt", "capuche") and rng.random() < 0.5: details.append("logo")
    if rng.random() < 0.25: details.append("montre")
    if perso == "noeud" and rng.random() < 0.4: details.append("collier")
    if moment in ("matin", "soir") and lieu == "rue" and rng.random() < 0.5: details.append("echarpe")
    if haut == "chemise" and lieu == "bureau": details.append("cravate")
    return dict(haut=haut, c_haut=c_haut, motif=motif, c_motif=M._fonce(c_haut, 0.72) if motif != "pois" else (250, 250, 248),
                bas=bas, c_bas=c_bas, chaussures=chaus, c_chaussures=PALETTE[int(rng.integers(len(PALETTE)))] if chaus != "ville" else (50, 35, 25),
                details=tuple(details), **({"chapeau": chapeau, "c_chapeau": PALETTE[int(rng.integers(len(PALETTE)))]} if chapeau else {}),
                **({"c_dessous": (245, 245, 245)} if haut == "blouson" else {}))

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
               details=tuple(d for d in (c.get("details") or []) if d in M.DETAILS)[:6])
    if c.get("chapeau") in M.CHAPEAUX: out["chapeau"] = c["chapeau"]; out["c_chapeau"] = col(c.get("c_chapeau"), (60, 60, 70))
    out["c_motif"] = col(c.get("c_motif"), M._fonce(out["c_haut"], 0.72))
    if c.get("cheveux") in M.COIFFURES: out["cheveux"] = c["cheveux"]
    if c.get("c_cheveux"): out["c_cheveux"] = col(c.get("c_cheveux"), (110, 75, 45))
    return out

NOMS_COULEURS = {"rouge": (220, 60, 60), "bleu": (60, 110, 200), "bleu marine": (40, 50, 90), "vert": (80, 160, 100), "jaune": (245, 200, 60),
                 "blond": (232, 196, 120), "chatain": (130, 85, 50), "châtain": (130, 85, 50), "brun": (70, 45, 32), "roux": (200, 100, 50),
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
    V = (sk.get("doublage") or {}).get("visuel") or {}                    # ce que montre l'image de la vidéo d'origine (analyse_video)
    dec = [sc for sc in (sk.get("decoupage") or []) if sc.get("repliques")] or [{"repliques": list(range(len(sk.get("repliques", []))))}]
    t_low = txt_global.lower()
    # heure : imposée par Claude, sinon d'après le texte, sinon variée (en évitant de refaire la même que la dernière vidéo)
    moment = S.get("moment") if S.get("moment") in MOMENTS else None
    if not moment:
        if re.search(r"\b(nuit|minuit|dormir|insomnie|3 ?h du mat|cauchemar)\b", t_low): moment = "nuit"
        elif re.search(r"\b(soir|soirée|apéro|dîner|ce soir)\b", t_low): moment = "soir"
        elif re.search(r"\b(matin|réveil|petit[- ]déj|café du matin|lundi matin)\b", t_low): moment = "matin"
        elif V.get("moment") in MOMENTS: moment = V["moment"]                 # la lumière de la vidéo d'origine
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
    # effets « cinéma » de l'épisode : tirés au hasard (graine de l'épisode) pour varier d'une vidéo à l'autre, mêlés au style d'avant
    cine = {k: bool(rng.random() < p_) for k, p_ in proba_cine().items()}  # les effets des vidéos qui marchent reviennent plus souvent
    if isinstance(S.get("cine"), dict): cine.update({k: bool(v) for k, v in S["cine"].items() if k in CINE_PROBA})   # choix de Claude (mode payant)
    assis = {}                                                             # qui est assis (bureau, salon, guichet…) : une chaise est dessinée avec lui
    for k_, l_ in enumerate(lieux):
        presents = [r for r in roles if any(i < len(sk.get("repliques", [])) and sk["repliques"][i]["p"] == r for i in (dec[k_].get("repliques", []) if k_ < len(dec) else []))] or roles
        if l_ in LIEUX_ASSIS and (len(roles) >= 2 or sk.get("_separes")) and rng.random() < 0.55: assis[k_] = presents[int(rng.integers(len(presents)))]
    # qui mène chaque scène (le « métier » du lieu) : celui qui parle le plus de questions / le premier à parler
    costumes = {}
    for k, role in enumerate(roles):
        perso = M.ROLES.get(role, "bonnet")
        c = _costume_valide((S.get("costumes") or {}).get(role)) if isinstance(S.get("costumes"), dict) else None
        if c is None:
            lieu0 = lieux[0]; meneur = _meneur(sk, dec[0], roles)
            c = tenue(perso, "metier" if role == meneur else "client", lieu0, moment, graine + 17 * k)
        costumes[role] = c
    T = theme(t_low)                                                      # thème d'époque / de métier : la tenue suit (sauf costume imposé par Claude)
    if T:
        for k, role in enumerate(roles):
            if isinstance(S.get("costumes"), dict) and (S.get("costumes") or {}).get(role): continue
            P0 = S.get("personnages") if isinstance(S.get("personnages"), dict) else {}
            costumes[role] = appliquer_theme(costumes[role], T, genre_voix(sk, role, P0.get(role) if isinstance(P0.get(role), dict) else {}), k == 0)
    # les personnes de la vidéo d'origine habillent nos personnages : la plus présente à l'image joue la voix la plus présente
    if V.get("personnes"):
        mots = {r: sum(len(x.get("t", "").split()) for x in sk.get("repliques", []) if x.get("p") == r) for r in roles}
        demande = (S.get("costumes") or {}) if isinstance(S.get("costumes"), dict) else {}
        for role, pers in zip(sorted(roles, key=lambda r: -mots.get(r, 0)), V["personnes"]):
            c = costumes[role] = dict(costumes[role])
            if pers.get("habit") and "c_haut" not in (demande.get(role) or {}):
                c["c_haut"] = tuple(int(v) for v in pers["habit"]); c["c_motif"] = M._fonce(c["c_haut"], 0.72)
            if pers.get("cheveux") and "c_cheveux" not in (demande.get(role) or {}): c["c_cheveux"] = tuple(int(v) for v in pers["cheveux"])
    figurants = []
    if os.environ.get("FIGURANTS", "1") != "0":
        for k, l in enumerate(lieux):
            n = {"bar": 2, "restaurant": 2, "bureau": 1, "magasin": 1, "rue": 2, "salle_sport": 1, "classe": 0, "administration": 2, "palais": 1}.get(l, 0)
            for j in range(n):
                perso = ("lunettes", "meche")[j % 2]; act = {"bar": ("boit", "telephone"), "restaurant": ("mange", "boit"), "bureau": ("tape", "telephone"),
                                                            "magasin": ("cherche", "telephone"), "rue": ("marche", "telephone"), "salle_sport": ("souleve", "boit"),
                                                            "administration": ("telephone", "cherche"), "palais": ("boit", "boit")}[l][j % 2]
                figurants.append(dict(scene=k, perso=perso, activite=act, x=(150, 930)[(j + graine) % 2] if n == 1 else (150, 930)[j],
                                      costume=tenue(perso, "client", l, moment, graine + 101 + j + 7 * k)))
    fiches = casting(sk, roles, costumes, S, graine)
    for k, f_ in enumerate(figurants): f_["fiche"] = _humain().creer(graine + 500 + 7 * k)
    figurants += compagnons(sk, dec, lieux, moment, graine)                # personnages muets voulus par l'histoire (Claude)
    ambiances = set(a for a in (S.get("ambiances") or []) if a in ("vapeur", "poussiere", "pluie", "neige", "neon"))
    if re.search(r"\bpluie|pleu[tv]|rain|parapluie", t_low): ambiances.add("pluie")
    if re.search(r"\bneige|no[ëe]l|snow|hiver", t_low): ambiances.add("neige")
    if "cuisine" in lieux or "restaurant" in lieux: ambiances.add("vapeur")
    if moment in ("matin", "soir") and any(l not in ("rue",) for l in lieux): ambiances.add("poussiere")
    if "bar" in lieux: ambiances.add("neon")
    lum = LUMIERE_LIEU.get(lieux[0], -1)
    c_mur = None
    if V.get("mur"):                                                       # la couleur dominante du décor de la vidéo, éclaircie pour nos murs
        c_mur = tuple(int(0.7 * (v + (255 - v) * 0.3) + 0.3 * d) for v, d in zip(V["mur"], DD.COULEURS_MUR.get(lieux[0], (230, 220, 210))))
    rythme = None                                                          # montage et cadrages : ceux de la vidéo, sinon ceux de la banque
    try:
        import banque_visuelle
        rythme = banque_visuelle.rythme(V) if V.get("plans") else banque_visuelle.tendances().get("rythme")
    except Exception: pass
    heure = {"matin": (8, 5), "jour": (14, 20), "soir": (19, 40), "nuit": (2, 15)}[moment]
    return dict(graine=graine, moment=moment, lieux=lieux, gags=gags, costumes=costumes, figurants=figurants, ambiances=sorted(ambiances),
                lumiere=lum, ombre=0.24 if moment != "nuit" else 0.32, etalonnage=ETALONNAGE[moment], heure=heure,
                style_ia=STYLES_IA[moment], plans=S.get("plans") if isinstance(S.get("plans"), list) else [],
                source=("auteur" if S else "robot") + ("+image" if V else ""), c_mur=c_mur, rythme=rythme, fiches=fiches,
                cadence=S.get("cadence") if S.get("cadence") in CADENCES else None, assis=assis, cine=cine, decoupe=_decoupe_claude(S, roles),
                coupes_origine=[float(c) for c in (V.get("coupes") or []) if isinstance(c, (int, float))] if sk.get("doublage") else [])

def _humain():
    import humain
    return humain

GENRE_ROLE = {"presentateur": "h", "invite": "h", "envoyee": "f"}           # sketchs écrits : Jojo, Kévin, Lila (accords du texte)
COIFFURES_HUMAINS = {"carre": "carre", "long": "long", "queue": "queue", "chignon": "chignon", "boucles": "boucles", "court": "court",
                     "meches": "court", "nuque": "court", "couronne": "chauve", "aucune": "chauve", "raie": "raie", "rase": "rase", "mi_long": "mi_long", "chauve": "chauve"}
COIFFURES_HUMAINS.update({c: c for c in M.GR.COIFFURES})

def genre_voix(sk, role, d=None):
    """Homme ou femme : TOUJOURS d'après la voix entendue. Sketch écrit : voix fixes des rôles (Jojo, Kévin : homme ; Lila : femme).
    Doublage : voix mesurée réplique par réplique quand elle est nette, sinon le choix de Claude, sinon la hauteur moyenne."""
    d = d or {}
    if sk.get("doublage") is None: return GENRE_ROLE.get(role) or (d.get("genre") if d.get("genre") in ("h", "f") else None)
    g = (sk.get("_voix_genre") or {}).get(role) or (d.get("genre") if d.get("genre") in ("h", "f") else None)
    vh = (sk.get("_voix_hz") or {}).get(role)
    return g or (("f" if vh > 165 else "h") if vh else None)

def casting(sk, roles, costumes, S, graine):
    """Casting libre : une fiche de personnage adulte par rôle, différente à chaque vidéo.
    Genre : la voix (doublage : moins de 165 Hz ≈ homme), sinon le prénom du sketch écrit ; âge, corpulence… : ce que Claude a vu
    ou décidé (« personnages »), sinon le texte (mamie, papa, étudiant…), sinon le hasard de la graine de l'épisode.
    Coiffure et couleur des cheveux, lunettes, barbe : la tenue de l'épisode (vidéo d'origine, Claude)."""
    H_ = _humain(); voix = sk.get("_voix_hz") or {}; doub = bool(sk.get("doublage"))
    P_ = S.get("personnages") if isinstance(S.get("personnages"), dict) else {}
    lignes = {r: " ".join(x.get("t", "") for x in sk.get("repliques", []) if x.get("p") == r).lower() for r in roles}
    tout = " ".join(lignes.values())
    out = {}
    for k, role in enumerate(roles):
        d = P_.get(role) if isinstance(P_.get(role), dict) else {}
        genre = genre_voix(sk, role, d)
        age = None
        try: age = int(d["age"]) if d.get("age") else None
        except (TypeError, ValueError): age = None
        autres = " ".join(v for r, v in lignes.items() if r != role)          # comment les autres l'appellent
        # enfant / ado d'après le dialogue : on l'appelle « fiston », « mon fils »… ou il appelle l'autre « papa », « maman »
        voc = r"(^|[.!?…]\s+)(papa|maman)\s*,|,\s*(papa|maman)\s*([.!?…]|$)"   # « Papa, … » ou « …, papa. » : on parle À son parent
        parent = bool(re.search(voc, autres))
        petit = not parent and (bool(re.search(r"\b(fiston|mon fils|ma fille|mon gar[çc]on|ma puce|mon grand|ma grande|mon bébé)\b", autres))
                                or bool(re.search(voc, lignes[role])))
        if parent and not age: age = 46
        if petit and not (age and age < 18): age = 15 if not re.search(r"\b(doudou|tétine|maternelle|CP|CE1|dessin animé)\b", tout) else 8
        if not age:
            if re.search(r"\b(mamie|papy|grand-m[èe]re|grand-p[èe]re)\b", autres): age = 70
            elif re.search(r"\b(maman|papa|m[èe]re|p[èe]re)\b", autres): age = 46
            elif re.search(r"\b(mon fils|ma fille|mon ch[ée]ri|ma ch[ée]rie|mes enfants)\b", lignes[role]) and "maman" not in tout: age = 44
            elif re.search(r"\b(prof|monsieur|madame|docteur|docteure)\b", autres): age = 45
            elif re.search(r"\b(mec|frérot|wesh|grave|trop styl[ée])\b", lignes[role]): age = 24
        c = costumes.get(role) or {}
        style = COIFFURES_HUMAINS.get(c.get("cheveux") or "") or (d.get("cheveux") if d.get("cheveux") in tuple(H_.COIFF_M) + ("chauve",) else None)
        det = c.get("details") or ()
        if age and age < 18 and genre != "f": style = style if style in H_.COURTS_JEUNE_H else None   # ado : coiffure de son âge
        fiche = H_.creer(graine + 31 * k, genre=genre, age=age, cheveux=style, c_cheveux=c.get("c_cheveux"),
                         corpulence=d.get("corpulence") if isinstance(d.get("corpulence"), (int, float)) else None,
                         lunettes="rondes" if "lunettes_vue" in det else None,
                         barbe=next((b for b in M.GR.BARBES if b in det), None) or ("moustache" if "moustache" in det else ("trois_jours" if "barbe" in det else
                               (d.get("barbe") if d.get("barbe") in M.GR.BARBES + ("moustache", "trois_jours") else None))))
        try:                                                               # taille vue dans la vidéo ou décidée par Claude (1 = adulte moyen)
            if d.get("taille"): fiche["taille"] = float(np.clip(float(d["taille"]), 0.55, 1.25)) * (1.04 if fiche["genre"] == "h" else 0.97)
        except (TypeError, ValueError): pass
        out[role] = fiche
    return out

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
            choix = ("serre", "epaule", "moyen", "serre", "epaule" if dur > 1.5 else "serre")
            ry_ = B.get("rythme") or {}
            if ry_.get("serre", 0) > 0.6: choix = ("serre", "tres_serre", "epaule", "serre", "tres_serre")    # la vidéo d'origine filme de près
            elif ry_.get("large", 0) > 0.6: choix = ("moyen", "large", "epaule", "moyen", "large")             # … ou de loin
            plan = choix[(j + h) % 5]
            mouvs = ("fixe", "avance", "travelling")
            cam_ = ry_.get("camera") or {}
            if cam_: mouvs = tuple(m_ for m_, v_ in sorted(cam_.items(), key=lambda x: -x[1]) if v_ > 0.12 and m_ in MOUVEMENTS) or mouvs
            mouv = mouvs[h % len(mouvs)] if plan != "epaule" else "fixe"
        elif plan == "serre" and dur > 3.0: mouv = "avance"
        if q.get("chute") and j == len(ph) - 1: plan, mouv = "serre", "avance"
        elif q.get("chute"): plan = "tres_serre" if h % 2 else "serre"
        if n <= 1 and plan in ("epaule",): plan = "serre"
        reaction = "aucune"
        if q["emo"] in ("cri", "colere"): reaction = ("choc", "bras_croises", "yeux_au_ciel")[h % 3]
        elif q["emo"] in ("blase", "sceptique"): reaction = ("sceptique", "yeux_au_ciel")[h % 2]
        elif q["emo"] == "gene" or q["texte"].rstrip().endswith("..."): reaction = "gene"
        elif q.get("chute"): reaction = ("regard_camera", "facepalm", "choc", "rire", "yeux_au_ciel")[h % 5]
        elif (B.get("rythme") or {}).get("sourires", 0) > 0.35 and h % 3 == 0: reaction = "rire"         # ça sourit beaucoup dans la vidéo
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

CINE_PROBA = {"focus": 0.0, "vertige": 0.7, "tiers": 0.65, "etalonnage": 0.9, "profondeur": 0.0, "grain": 0.7, "reflets": 0.5, "son": 1.0}   # flous retirés (auteur)
def proba_cine():
    """Probabilités des effets cinéma, ajustées par les vues TikTok : un effet présent dans les vidéos les plus vues revient plus souvent."""
    p = dict(CINE_PROBA)
    try:
        import banque_visuelle; vues = banque_visuelle._vues()
        m = [(e.get("cine") or {}, vues[e["fichier"]]) for e in _memoire() if e.get("fichier") in vues and e.get("cine")]
        for k in p:
            avec = [v for c, v in m if c.get(k)]; sans = [v for c, v in m if not c.get(k)]
            if len(avec) >= 3 and len(sans) >= 3:
                r = (sum(avec) / len(avec) + 1) / (sum(sans) / len(sans) + 1)
                p[k] = float(np.clip(p[k] * r ** 0.5, 0.15, 0.95))
    except Exception: pass
    return p

# ------------------------------------------------------------------ personnages dans des lieux différents (appel, visio, message…)
APPEL = r"\b(all[ôo]|je t'appelle|tu m'appelles|au t[ée]l[ée]phone|tu m'entends|je t'entends( pas| mal)?|je raccroche|raccroche|t'es o[ùu]|tu es o[ùu]|" \
        r"je suis (au|à la|à l'|devant|sur le|chez)|je te rappelle|en visio|ça capte|r[ée]seau|ma batterie)\b"

def separer_lieux(sk):
    """Quand les personnages ne sont PAS au même endroit (au téléphone, en visio, l'un chez lui et l'autre en ville), chacun a
    son propre décor : une scène par personnage, et le montage passe de l'un à l'autre au rythme des répliques (coupe franche).
    Claude le dit (studio → "lieux_separes" : {rôle: décor en anglais}, "moyen" : telephone / visio / message) ; sans Claude,
    le robot le devine aux mots de l'appel (allô, t'es où, je suis au…). Modifie sk (découpage, objets) ; renvoie True si séparés."""
    if sk.get("_separes"): return True
    reps = sk.get("repliques") or []
    S = sk.get("studio") if isinstance(sk.get("studio"), dict) else {}
    parlants = [r for r in dict.fromkeys(x["p"] for x in reps) if r != "narrateur"]
    sep = S.get("lieux_separes") if isinstance(S.get("lieux_separes"), dict) else {}
    sep = {r: (v.get("decor") if isinstance(v, dict) else str(v or "")) for r, v in sep.items() if r in parlants}
    moyen = str(S.get("moyen") or "").lower()
    texte = " ".join(x.get("t", "") for x in reps).lower()
    if len(sep) < 2 and not S.get("lieux_separes") and len(parlants) >= 2 and len(re.findall(APPEL, texte)) >= 2:
        sep = {r: "" for r in parlants[:2]}; moyen = moyen or "telephone"            # repli gratuit : un appel deviné aux mots
    if len(sep) < 2: return False
    ordre = list(sep); scene_de = {r: k for k, r in enumerate(ordre)}
    dec = [{"scene": str(k + 1), "repliques": [], "lieu": "", "son": "", "duree": 0, "decor": re.sub(r"[^\w\s,.'-]", "", sep[r])[:160]} for k, r in enumerate(ordre)]
    k_prec = 0
    for i, x in enumerate(reps):
        k_prec = scene_de.get(x["p"], k_prec); dec[k_prec]["repliques"].append(i)     # voix off et 3e personnage : là où l'on est
    dec = [d for d in dec if d["repliques"]]
    if len(dec) < 2: return False
    lieux_role = S.get("lieux_de") if isinstance(S.get("lieux_de"), dict) else {}
    if lieux_role: S["lieux"] = [lieux_role.get(r) for r in ordre if any(reps[i]["p"] == r for i in range(len(reps)))]
    else: S.pop("lieux", None)                                                     # les anciens lieux ne correspondent plus aux scènes
    sk["decoupage"] = [dict(d, scene=str(k + 1)) for k, d in enumerate(dec)]
    if moyen in ("telephone", "visio", "tel", "téléphone", "appel"):              # chacun son téléphone en main
        for x in reps:
            if x["p"] != "narrateur" and not x.get("objet"): x["objet"] = "telephone"
    sk["_separes"] = True
    if S: sk["studio"] = S
    return True

def compagnons(sk, dec, lieux, moment, graine):
    """Personnages muets qui jouent dans la scène (vus dans la vidéo ou suggérés par l'histoire) : « une femme très apprêtée lui
    fait signe à côté de sa voiture »… Claude : studio → "figurants" : [{"avec": rôle, "genre", "age", "geste": coucou / signe /
    danse / attend / telephone / rit / boit, "haut", "c_haut", "description"}]. Dessinés près du personnage, à sa taille."""
    S = sk.get("studio") if isinstance(sk.get("studio"), dict) else {}
    out = []
    for k, f in enumerate([f for f in (S.get("figurants") or []) if isinstance(f, dict)][:3]):
        avec = f.get("avec"); reps = sk.get("repliques") or []
        sc = next((j for j, d in enumerate(dec) if any(i < len(reps) and reps[i]["p"] == avec for i in d.get("repliques", []))), None)
        if sc is None: continue
        geste = str(f.get("geste") or "attend").lower()
        geste = geste if geste in ("coucou", "signe", "danse", "attend", "telephone", "rit", "boit") else "attend"
        c = tenue("meche", "client", lieux[min(sc, len(lieux) - 1)], moment, graine + 301 + k)
        cv = _costume_valide({x: f[x] for x in ("haut", "c_haut", "bas", "c_bas", "chaussures", "chapeau", "details") if x in f})
        if cv: c.update(cv)
        try: age = int(f.get("age") or 0) or None
        except (TypeError, ValueError): age = None
        out.append(dict(scene=sc, avec=avec, activite=geste, compagnon=True, costume=c, perso="meche", x=0,
                        fiche=_humain().creer(graine + 700 + 13 * k, genre=f.get("genre") if f.get("genre") in ("h", "f") else None, age=age),
                        description=str(f.get("description") or "")[:120]))
    return out

LIEUX_ASSIS = ("bureau", "salon", "restaurant", "administration", "classe", "bar", "cabinet_medical", "palais")
# gestes à deux, déclenchés par les mots de la réplique (le personnage s'approche, sa main atteint vraiment l'autre)
GESTES_DUO = [("tope", r"\b(tope|bravo|yes|trop bien|on l'a fait|g[ée]nial|check|bien jou[ée])\b"),
              ("epaule", r"\b(calme-toi|t'inqui[eè]te|courage|d[ée]sol[ée]e?|mon pote|ma belle|mon grand|ça va aller|pas grave)\b"),
              ("donne", r"\b(tiens|prends[- ]le|prends[- ]la|voil[àa] (ton|ta|tes|le|la)|cadeau pour toi)\b"),
              ("pousse", r"\b(d[ée]gage|pousse-toi|va-t'en|sors d'ici|laisse-moi passer)\b")]

def geste_duo(texte):
    t = (texte or "").lower()
    for nom, motif in GESTES_DUO:
        if re.search(motif, t): return nom
    return None

# ------------------------------------------------------------------ consigne de direction artistique pour Claude (mode payant)
CADENCES = {"rapide": 0.72, "normal": 1.0, "pose": 1.35}

def consigne_studio():
    """Bloc « studio » des consignes de Claude (doublage TikTok et sketchs écrits) : tout ce que le moteur sait dessiner et monter.
    Les listes viennent du code : chaque nouveauté (tenue, coiffure, lieu, plan…) y apparaît d'elle-même."""
    import decor_dessin as DD, humain as H_, bruitages as BR_
    BRUITAGES_TENDANCE = list(BR_.CATALOGUE)
    L = ", ".join
    return f"""- "studio" : la direction artistique de la vidéo. Le moteur dessine tout lui-même dans le style « toons » des chaînes TikTok :
  personnages ADULTES à grosse tête ronde blanche posée sur le col, yeux en ovales noirs, épaules carrées, trait noir épais, avec le
  MAXIMUM DE DÉTAILS (tenues, coiffures, barbes, chapeaux, accessoires, rides, maquillage, décors remplis d'objets). Choisis UNIQUEMENT
  dans les listes :
  "moment" = matin, jour, soir ou nuit ; "lieux" = un lieu par scène parmi {L(DD.LIEUX)} ;
  "costumes" = pour chaque rôle dessiné (presentateur, invite, envoyee) la tenue qui raconte qui il est dans la scène :
  "haut" parmi {L(M.HAUTS)}, "c_haut" = une couleur parmi {L(NOMS_COULEURS)}, "motif" parmi {L(M.MOTIFS)}, "bas" parmi {L(M.BAS)},
  "chaussures" parmi {L(M.CHAUSSURES)}, "details" (0 à 5) parmi {L(M.DETAILS)},
  "chapeau" (facultatif) parmi {L(M.CHAPEAUX)} avec "c_chapeau" (couleur), "cheveux" parmi {L(M.COIFFURES)} et "c_cheveux" (couleur) ;
  époque ou métier évident : habille-les en conséquence (préhistoire : tunique motif taches + barbe_pleine + cheveux herisse ; roi, reine,
  Versailles : redingote ou robe + anglaises + tricorne ou couronne ; police : uniforme + casquette ; chantier : casque_chantier ;
  cuisinier : tablier + toque ; plage : hawai motif fleurs + bob…) ;
  "personnages" = pour chaque rôle dessiné, la personne qui le joue (casting libre, différent à chaque vidéo) : "genre" (h ou f),
  "age" (nombre), "taille" (1 = adulte moyen ; ado ≈ 0.8 ; enfant ≈ 0.65), "corpulence" (0 = mince à 1 = fort),
  "cheveux" parmi {L(sorted(set(H_.COIFFURES_H + H_.COIFFURES_F + M.GR.COIFFURES)))}, "barbe" parmi {L(M.GR.BARBES + ("moustache", "trois_jours"))}.
  L'ÂGE, le genre et la taille doivent coller au DIALOGUE, à la voix et à la vidéo : celui qu'on appelle « fiston », « mon fils »,
  « ma puce », ou qui dit « papa, … », « maman, … » est un ADO (13-16 ans : plus petit, cheveux courts de son âge, JAMAIS de barbe)
  ou un enfant si le contexte le dit ; ses parents sont plus âgés ; un patron, un client, un prof… ont l'âge du rôle ;
  "lieux_separes" (seulement si les personnages ne sont PAS au même endroit : au téléphone, en visio, par message, l'un chez lui et
  l'autre en ville) = {{rôle: décor EN ANGLAIS de l'endroit où IL se trouve, précis et détaillé}} ; "lieux_de" = {{rôle: lieu parmi
  {L(DD.LIEUX)}}} ; "moyen" = telephone, visio ou message. Le moteur donne alors un décor à chacun et passe de l'un à l'autre à
  chaque réplique (coupe franche), sans jamais les mettre ensemble ;
  "figurants" (facultatif, au plus 3) = les personnes MUETTES dont l'histoire parle ou qu'on voit dans la vidéo, qui jouent dans la
  scène à côté d'un personnage : [{{"avec": rôle, "description", "genre", "age", "geste": coucou, signe (« viens »), danse, attend,
  telephone, rit ou boit, "haut", "c_haut", "bas", "chapeau", "details"}}] (ex. : une femme très apprêtée en tenue de mère Noël qui
  fait signe au fils à côté de sa voiture). Imagine tous ces détails de l'histoire SANS qu'on te les demande ;
  "gags" = 1 à 3 textes très courts et drôles écrits dans le décor (affiche, tableau, enseigne, post-it), liés à la situation ;
  "ambiances" parmi vapeur, poussiere, pluie, neige, neon ;
  "cadence" = rapide, normal ou pose : le rythme du montage (rapide pour les disputes et les échanges vifs, pose pour l'émotion) ;
  "plans" = pour les répliques importantes (n° de réplique) : "plan" parmi {L(PLANS)}, "mouvement" parmi {L(MOUVEMENTS)},
  "geste" parmi {L(GESTES)}, "reaction" de celui qui écoute parmi {L(REACTIONS)}. Le moteur découpe déjà chaque réplique en plusieurs
  plans (serrés, larges, réactions de celui qui écoute), calés sur la voix, avec des mouvements de caméra et des passages fluides
  (coupe, glissé, filé, zoom) : ton choix fixe le premier plan de la réplique et les moments forts (serré ou très serré pour les
  chutes, contre-plongée pour celui qui s'énerve, plongée pour celui qui se fait écraser, regard caméra pour les silences gênants) ;
  "decoupe" (facultatif, comme un vrai storyboard) = pour les répliques que tu veux monter toi-même : {{"replique": n, "plans": [
  {{"debut": fraction de la réplique entre 0 et 1, "plan": …, "cible": rôle filmé (celui qui parle ou celui qui écoute),
  "mouvement": … ou vertige, "passage": coupe, glisse, file ou zoom}}, …]}} — alterne serré / large, montre les réactions ;
  "cine" (facultatif) = effets de l'épisode, vrai ou faux : vertige, tiers (règle des tiers), etalonnage (couleur selon
  l'émotion), grain, reflets, son (ambiance, musique) — l'image reste toujours NETTE (aucun flou sur les personnages ni le décor) ;
  "bruitages" (facultatif) = bruitages « tendance » des vidéos d'humour TikTok, au plus un par réplique et pas plus d'un toutes les
  3 secondes : [{{"replique": n, "son": …}}] avec son parmi {L(BRUITAGES_TENDANCE)} (vine_boom/dun_dun : vanne ou révélation,
  klaxon_clown : quelqu'un se ridiculise, sifflet_chute : échec, criquets/os_craque : blanc gênant, violon_triste : fausse tristesse,
  caisse : argent, clavier/glitch : ordinateur ou bug…) ; JAMAIS de rires enregistrés."""

# ------------------------------------------------------------------ découpage : plusieurs plans par réplique, calés sur le son
SERRES = ("serre", "tres_serre", "epaule", "plongee", "contre_plongee")
LARGES = ("large", "moyen")
DUREE_PLAN = {"cri": 0.8, "colere": 0.9, "panique": 0.8, "choc": 0.95, "rire": 1.1, "joie": 1.2, "sceptique": 1.4,
              "pleurs": 2.4, "soupir": 2.2, "triste": 2.4, "fatigue": 2.4, "gene": 1.7}

def _coupe_sur_le_son(lv, fps, t_deb, t_ideal, marge=0.28):
    """Instant de coupe proche de t_ideal : de préférence dans un creux de la voix (entre deux mots), sinon sur une attaque (un mot appuyé)."""
    k0 = int((t_ideal - marge - t_deb) * fps); k1 = int((t_ideal + marge - t_deb) * fps)
    k0, k1 = max(1, k0), min(len(lv) - 2, k1)
    if k1 <= k0: return t_ideal
    seg = np.asarray(lv[k0:k1], np.float32); i = int(np.argmin(seg))
    if seg[i] < 0.25: return t_deb + (k0 + i) / fps                       # une respiration, un blanc entre deux mots
    d = np.diff(np.asarray(lv[k0 - 1:k1], np.float32)); i = int(np.argmax(d))
    return t_deb + (k0 + i) / fps                                          # sinon : on coupe sur l'attaque d'un mot

PASSAGES = ("coupe", "glisse", "file", "zoom")

def _decoupe_claude(S, roles):
    """Découpage plan par plan proposé par Claude (mode payant), vérifié : {n° de réplique: [plans]}."""
    out = {}
    for d in (S.get("decoupe") or []) if isinstance(S.get("decoupe"), list) else []:
        try:
            n = int(d.get("replique")); pl = []
            for x in d.get("plans") or []:
                deb = float(x.get("debut", 0)); plan = x.get("plan") if x.get("plan") in PLANS else None
                if not plan or not 0 <= deb < 1: continue
                pl.append(dict(debut=deb, plan=plan, cible=x.get("cible") if x.get("cible") in roles else None,
                               mouvement=x.get("mouvement") if x.get("mouvement") in MOUVEMENTS else None,
                               passage=x.get("passage") if x.get("passage") in PASSAGES else None))
            if pl: out[n] = sorted(pl, key=lambda x: x["debut"])[:6]
        except (AttributeError, TypeError, ValueError): continue
    return out

REACTION_MAX = 1.0                                                         # plan de réaction : 1 s au plus pendant que l'autre parle

def decouper(ph, places, B, fps=30):
    """Montage dynamique : chaque réplique est découpée en plusieurs plans selon son énergie et son émotion (dispute : coupes rapides,
    émotion : plans longs), en alternant plans serrés et plans larges, celui qui parle et celui qui écoute, avec un mouvement de
    caméra par plan et un « passage » d'un plan à l'autre (coupe franche, glissé, filé, zoom). Les coupes tombent entre deux mots
    ou sur un mot appuyé. Renvoie la liste des plans : dict(t0, t1, scene, cible, plan, mouvement, force, passage, i)."""
    ry_ = B.get("rythme") or {}
    ref = float(ry_.get("duree_plan") or 2.0)                              # durée moyenne des plans de la vidéo d'origine
    k_ref = float(np.clip(ref / 2.0, 0.6, 1.4))
    k_ref *= CADENCES.get(B.get("cadence"), 1.0)                          # rythme voulu par Claude (mode payant)
    plans, prec = [], None
    for j, q in enumerate(ph):
        sc = q["scene"]; roles = places.get(sc, []); autres = [r for r in roles if r != q["p"]]
        t0 = q["deb"] - (0.08 if j and ph[j - 1]["scene"] == sc else 0.0)     # on coupe un poil AVANT que la voix démarre : plus fluide
        t1 = ph[j + 1]["deb"] - 0.08 if j + 1 < len(ph) and ph[j + 1]["scene"] == sc else max(q["fin"], t0 + 0.3)
        if j + 1 < len(ph) and ph[j + 1]["scene"] != sc: t1 = q["fin"] + 0.05
        lv = np.asarray(q.get("lv") if q.get("lv") is not None else [0.5], np.float32)
        energie = float(np.mean(lv)) if len(lv) else 0.4
        d_cible = DUREE_PLAN.get(q["emo"], 1.35) * (1.2 - 0.45 * min(1.0, energie)) * k_ref
        if q.get("chute") or q["p"] == "narrateur" or j == len(ph) - 1: d_cible = 99   # la chute se joue en un seul plan
        n = max(1 if (t1 - t0) < 1.6 or d_cible > 50 else 2, int(round((t1 - t0) / max(0.7, d_cible))))
        dc = (B.get("decoupe") or {}).get(q["i"])                          # storyboard de Claude pour cette réplique
        if dc:
            dc = [x for x in dc if x["debut"] < 0.95] or dc[:1]; dc[0] = dict(dc[0], debut=0.0)
            coupes = [t0] + [_coupe_sur_le_son(lv, fps, q["deb"], t0 + (t1 - t0) * x["debut"], 0.2) for x in dc[1:]] + [t1]
        else:
            coupes = [t0] + [_coupe_sur_le_son(lv, fps, q["deb"], t0 + (t1 - t0) * k / n) for k in range(1, n)] + [t1]
            orig = [c for c in B.get("coupes_origine") or [] if t0 + 0.5 < c < t1 - 0.5]   # doublage : les coupes de la vidéo d'origine
            if orig: coupes = [t0] + orig + [t1]
        coupes = sorted(set(round(c, 3) for c in coupes))
        for k in range(len(coupes) - 1):
            a_, b_ = coupes[k], coupes[k + 1]
            if b_ - a_ < 0.45 and plans and k: plans[-1]["t1"] = b_; continue   # jamais de plan trop court
            h = _h(B.get("graine", 0), j, k)
            if k == 0: cible, plan = q["p"], q.get("plan") or "serre"       # 1er plan de la réplique : celui du storyboard
            else:
                options = []
                if autres and q["p"] != "narrateur": options += [("ecoute", "serre"), ("ecoute", "tres_serre")]   # la réaction de celui qui écoute
                if len(roles) >= 2: options += [("parle", "moyen"), ("parle", "large"), ("parle", "epaule")]
                options += [("parle", "tres_serre"), ("parle", "serre")]
                if q["emo"] in ("cri", "colere"): options += [("parle", "contre_plongee")] * 2
                if q["emo"] in ("pleurs", "triste", "gene", "soupir"): options += [("parle", "plongee")]
                serre_avant = prec and prec["plan"] in SERRES
                bons = [o for o in options if (o[1] in LARGES) == bool(serre_avant) or o[0] == "ecoute"] or options   # on alterne serré / large
                bons = [o for o in bons if not prec or (o[1], (q["p"] if o[0] == "parle" else autres[0] if autres else q["p"])) != (prec["plan"], prec["cible"])] or bons
                o = bons[h % len(bons)]
                cible, plan = (q["p"] if o[0] == "parle" or not autres else autres[h % len(autres)]), o[1]
            if dc and k < len(dc):                                          # le plan choisi par Claude l'emporte
                plan = dc[k]["plan"]; cible = dc[k]["cible"] if dc[k]["cible"] in roles else cible
            if plan == "epaule" and len(roles) < 2: plan = "serre"
            if prec and prec["scene"] == sc and prec["cible"] == cible and prec["plan"] == plan:   # pas deux fois le même cadre
                plan = "moyen" if plan in SERRES and len(roles) >= 2 else ("tres_serre" if plan != "tres_serre" else "serre")
            # mouvement du plan, selon l'énergie de la voix et l'émotion
            cine = B.get("cine") or {}
            if q["emo"] in ("choc", "panique") and k == 0 and cine.get("vertige"): mouv = "vertige"      # effet vertige (travelling compensé)
            elif q["emo"] in ("cri", "colere", "panique"): mouv = ("zoom_choc" if k == 0 else "epaule")
            elif q["emo"] in ("pleurs", "triste", "soupir", "gene"): mouv = "avance"
            elif plan in LARGES: mouv = ("travelling", "avance", "recul")[h % 3]
            else: mouv = ("avance", "travelling", "fixe", "avance", "recul")[h % 5]
            if k == 0 and q.get("mouvement") in MOUVEMENTS and q.get("mouvement") != "fixe" and mouv != "vertige": mouv = q["mouvement"]
            if dc and k < len(dc) and dc[k]["mouvement"]: mouv = dc[k]["mouvement"]
            force = float(np.clip(0.6 + 0.8 * energie, 0.5, 1.4))
            # passage depuis le plan précédent
            if not prec or prec["scene"] != sc: passage = "coupe"
            elif prec["cible"] == cible and (prec["plan"] in LARGES) != (plan in LARGES): passage = "zoom" if energie > 0.55 else "glisse"
            elif prec["cible"] != cible and q["emo"] in ("cri", "colere", "panique", "choc") and h % 2: passage = "file"
            elif prec["cible"] != cible: passage = ("coupe", "coupe", "file", "glisse")[h % 4] if energie > 0.4 else ("coupe", "glisse")[h % 2]
            else: passage = "glisse"
            if dc and k < len(dc) and dc[k]["passage"] and prec and prec["scene"] == sc: passage = dc[k]["passage"]
            tiers = bool((B.get("cine") or {}).get("tiers") and plan in ("serre", "tres_serre", "contre_plongee") and h % 2)   # sujet au tiers de l'image
            prec = dict(t0=a_, t1=b_, scene=sc, cible=cible, plan=plan, mouvement=mouv, force=force, passage=passage, i=q["i"], j=j, tiers=tiers)
            plans.append(prec)
            if cible != q["p"] and q["p"] in roles and b_ - a_ > REACTION_MAX + 0.45:   # réaction courte, puis retour sur celui qui parle
                m_ = _coupe_sur_le_son(lv, fps, q["deb"], a_ + REACTION_MAX, 0.15)
                if a_ + 0.6 <= m_ <= b_ - 0.45:
                    prec["t1"] = m_
                    prec = dict(prec, t0=m_, t1=b_, cible=q["p"], plan="moyen" if plan in SERRES and len(roles) >= 2 else "serre",
                                mouvement="avance", passage="coupe", tiers=False)
                    plans.append(prec)
    for k in range(1, len(plans)):                                         # pas de trou entre deux plans d'une même scène
        if plans[k]["scene"] == plans[k - 1]["scene"]: plans[k - 1]["t1"] = plans[k]["t0"]
    return plans

# ------------------------------------------------------------------ mémoire du studio
MEMOIRE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "studio_memoire.json")

def _memoire():
    try:
        with open(MEMOIRE, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return []

def memoire_recente(cle):
    m = _memoire(); return (m[-1].get(cle) if m else None)

def memoriser(B, ph, duree, controle="", fichier=None):
    """Ce qui a été tourné (pour varier les prochaines vidéos et comparer avec les vues) : 200 dernières vidéos."""
    m = _memoire()
    from collections import Counter
    m.append(dict(moment=B.get("moment"), lieux=B.get("lieux"), source=B.get("source"), duree=round(float(duree or 0), 1),
                  plans=dict(Counter(q.get("plan") for q in ph)), mouvements=dict(Counter(q.get("mouvement") for q in ph)),
                  costumes={r: c.get("haut") for r, c in (B.get("costumes") or {}).items()}, figurants=len(B.get("figurants") or []),
                  ambiances=B.get("ambiances"), controle=str(controle)[:200], fichier=fichier, cine=B.get("cine"), cadence=B.get("cadence")))
    try:
        os.makedirs(os.path.dirname(MEMOIRE), exist_ok=True)
        with open(MEMOIRE, "w", encoding="utf-8") as f: json.dump(m[-200:], f, ensure_ascii=False, indent=1)
    except OSError: pass
