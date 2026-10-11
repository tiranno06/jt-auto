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
    (r"\b(plage|vacances|camping|tropiques|hawa[iï]|cocktail)", dict(haut="hawai", c_haut=(60, 170, 200), motif="fleurs", c_motif=(250, 120, 140), bas="short",
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
            vh = (sk.get("_voix_hz") or {}).get(role); g = ("f" if vh > 165 else "h") if vh else GENRE_ROLE.get(role)
            costumes[role] = appliquer_theme(costumes[role], T, g, k == 0)
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
                source=("auteur" if S else "robot") + ("+image" if V else ""), c_mur=c_mur, rythme=rythme, fiches=fiches)

def _humain():
    import humain
    return humain

GENRE_ROLE = {"presentateur": "h", "invite": "h", "envoyee": "f"}           # sketchs écrits : Jojo, Kévin, Lila (accords du texte)
COIFFURES_HUMAINS = {"carre": "carre", "long": "long", "queue": "queue", "chignon": "chignon", "boucles": "boucles", "court": "court",
                     "meches": "court", "nuque": "court", "couronne": "chauve", "aucune": "chauve", "raie": "raie", "rase": "rase", "mi_long": "mi_long", "chauve": "chauve"}
COIFFURES_HUMAINS.update({c: c for c in M.GR.COIFFURES})

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
        genre = d.get("genre") if d.get("genre") in ("h", "f") else None
        if not genre and doub and voix.get(role): genre = "f" if voix[role] > 165 else "h"
        if not genre and not doub: genre = GENRE_ROLE.get(role)
        age = None
        try: age = int(d["age"]) if d.get("age") else None
        except (TypeError, ValueError): age = None
        autres = " ".join(v for r, v in lignes.items() if r != role)          # comment les autres l'appellent
        if not age:
            if re.search(r"\b(mamie|papy|grand-m[èe]re|grand-p[èe]re)\b", autres): age = 70
            elif re.search(r"\b(maman|papa|m[èe]re|p[èe]re)\b", autres): age = 46
            elif re.search(r"\b(mon fils|ma fille|mon ch[ée]ri|ma ch[ée]rie|mes enfants)\b", lignes[role]) and "maman" not in tout: age = 44
            elif re.search(r"\b(prof|monsieur|madame|docteur|docteure)\b", autres): age = 45
            elif re.search(r"\b(mec|frérot|wesh|grave|trop styl[ée])\b", lignes[role]): age = 24
        c = costumes.get(role) or {}
        style = COIFFURES_HUMAINS.get(c.get("cheveux") or "") or (d.get("cheveux") if d.get("cheveux") in H_.COIFFURES_H + H_.COIFFURES_F else None)
        det = c.get("details") or ()
        fiche = H_.creer(graine + 31 * k, genre=genre, age=age, cheveux=style, c_cheveux=c.get("c_cheveux"),
                         corpulence=d.get("corpulence") if isinstance(d.get("corpulence"), (int, float)) else None,
                         lunettes="rondes" if "lunettes_vue" in det else None,
                         barbe=next((b for b in M.GR.BARBES if b in det), None) or ("moustache" if "moustache" in det else ("trois_jours" if "barbe" in det else None)))
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
