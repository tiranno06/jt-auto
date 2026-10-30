"""Personnages du robot dessinés dans le style « croquis » (validé par l'auteur le 30 octobre 2026 ; STYLE_PERSO=croquis, défaut).

Le moteur (cartoon.py) commande chaque personnage par une « pose » (même format que les marionnettes et le style toon : bras en
angles, bouche synchronisée, forme des lèvres, regard, émotion, larmes, sueur, rougeur, costume du casting et du métier…) ; ce module
la traduit pour moteur/croquis.py :
- silhouette : le PETIT (grosse tête, petit corps habillé) ou le GRAND (stickman géant), pour tous les âges (choix de l'auteur) ;
  tirée une fois par personnage (fiche du casting, réglage SILHOUETTE = petit / grand / les deux) ;
- tête et pieds aux mêmes places que l'ancien style (cadrages, objets tenus, sous-titres et contrôle image inchangés) ;
- émotion -> expression croquis, bouche ouverte selon la voix en gardant l'expression, forme des lèvres selon le son ;
- vitesse : chaque personnage est dessiné dans un petit cadre autour de lui (jamais sur toute l'image)."""
import hashlib, math, os
import numpy as np

import croquis as C
import marionnette as M

SILHOUETTE = (os.environ.get("SILHOUETTE") or "les_deux").lower()          # petit | grand | les_deux

EMO = {"neutre": "neutre", "rire": "joie", "cri": "colere", "colere": "fache", "pleurs": "triste", "soupir": "ennui", "panique": "peur",
       "choc": "surpris", "blase": "ennui", "joie": "heureux", "fier": "fierte", "chuchote": "malicieux", "gene": "honteux",
       "sceptique": "douteux", "amour": "amour", "fatigue": "fatigue", "reflechit": "soucieux", "idee": "emerveillement", "chante": "heureux"}
FORME = {"dents": "colere", "triste": "triste", "grand_sourire": "heureux", "o": "surpris", "moue": "soucieux", "coin": "malicieux",
         "machoire": "surpris"}
SON = {"M": "m", "O": "o", "U": "o", "I": "i", "E": "i", "S": "i"}
COURT = ("tshirt", "t_shirt", "debardeur", "maillot", "maillot_foot", "polo", "tunique_med", "salopette", "kimono")
CHAPEAUX = {"casque_pompier", "casquette_officier", "casquette", "toque", "calot", "calot_infirmier", "beret", "casque_chantier",
            "chapeau_paille", "casque_audio", "casque_astronaute", "bonnet", "chapeau_cowboy", "chapeau", "melon", "chapeau_sorcier", "charlotte",
            "tricorne", "bob", "bandana", "couronne", "bonnet_noel", "casque_chevalier", "oreilles_lapin"}
COIFF = {"court": "courts", "raie": "courts", "rase": "courts", "court_texture": "courts", "banane": "courts", "frange": "carre",
         "degarni": "courts", "nuque": "courts", "meches": "courts", "herisse": "herisse", "boucles": "boucles", "afro": "afro",
         "long": "longs", "ondule": "longs", "tresses": "longs", "mi_long": "carre", "carre": "carre", "queue": "queue", "chignon": "chignon"}
DECO = {"stethoscope": "stetho", "badge": "badge", "noeud_pap": "noeud", "veste_pompier": "bandes", "salopette": "salopette", "blouse": "blouse",
        "bandes": "bandes", "cravate": "cravate", "cape": "cape", "logo": "logo", "bandelettes": "bandelettes", "antennes": "antennes",
        "crocs": "crocs", "nez_rouge": "nez_rouge", "cache_oeil": "cache_oeil", "sifflet": "sifflet", "boutons_or": "boutons_or",
        "ceinture": "ceinture", "dechire": "dechire", "barbe_blanche": "barbe_blanche", "gilet_jaune": "bandes", "costume": "cravate",
        "echarpe": "echarpe"}


def silhouette(F):
    """Le petit ou le grand : réglage SILHOUETTE, sinon tiré une fois pour ce personnage (même fiche = même silhouette)."""
    if F.get("silhouette") in ("petit", "grand"): return F["silhouette"]
    if SILHOUETTE in ("petit", "grand"): return SILHOUETTE
    cle = f"{F.get('genre')}|{F.get('age')}|{F.get('cheveux')}|{tuple(F.get('c_cheveux') or ())}|{F.get('visage')}"
    return "petit" if int(hashlib.md5(cle.encode()).hexdigest()[:6], 16) % 2 else "grand"


def _geom(F, p):
    """Proportions croquis calées sur l'ancien squelette : pieds en p['y'], tête au même endroit (debout)."""
    K = M.squelette(p); K0 = M.squelette(dict(p, assis=False, sq=0.0)) if (p.get("assis") or p.get("sq")) else K
    G = silhouette(F) == "grand"
    k_tete = 4.4 if G else 3.06                                             # hauteur pieds -> centre de la tête, en rayons de tête
    R = max(8.0, (p["y"] - K0["tete"][1]) / k_tete)
    ec = 1.0 + 0.8 * float(p.get("sq") or 0.0)                               # étiré / écrasé (dessin animé)
    L_j = R * (2.3 if G else 1.25) * ec; h_tr = R * (1.2 if G else 0.95) * ec; l_tr = R * (0.38 if G else 0.5) / ec ** 0.5
    L_b = R * (1.2 if G else 0.95)
    hanche = p["y"] - L_j * (0.55 if p.get("assis") else 1.0); cou = hanche - h_tr   # assis : vu de face, sur sa chaise
    penche = float(p.get("penche") or 0.0) * 0.12 + math.sin(math.radians(float(p.get("tilt") or 0.0))) * 0.25
    x = K["x"]; tc = (x + penche * R, cou - R * (0.9 if G else 0.86))
    eps = [(x - l_tr * (0.5 if G else 0.42), cou + R * 0.1), (x + l_tr * (0.5 if G else 0.42), cou + R * 0.1)]
    seg = L_b * 0.55; bras = []
    for e, ang in zip(eps, (p["bras_g"], p["bras_d"])):
        a1, a2 = math.radians(ang[0]), math.radians(ang[0] + ang[1])
        c = (e[0] + math.sin(a1) * seg, e[1] + math.cos(a1) * seg); m = (c[0] + math.sin(a2) * seg, c[1] + math.cos(a2) * seg)
        bras.append((e, c, m))
    return dict(G=G, R=R, x=x, tc=tc, bras=bras, ecrase=ec, penche=penche, L_j=L_j, l_tr=l_tr)


def reperes(F, p):
    """Centre et rayons de la tête, positions des deux mains (objets tenus, effets, contrôle image)."""
    g = _geom(F, p)
    return g["tc"], (g["R"], g["R"]), [g["bras"][0][2], g["bras"][1][2]]


def expression(p):
    e = EMO.get(p.get("emo") or "", None)
    if e is None: e = FORME.get(p.get("forme"), "neutre")
    if e == "fache" and float(p.get("rougeur") or 0) > 0.6: e = "colere"   # la colère monte : visage rouge, dents serrées
    y = p.get("yeux")
    if y == "etoiles": e = "emerveillement"
    elif y == "minuscules": e = "peur" if e in ("neutre", "surpris") else e
    elif y == "plisses" and e in ("neutre", "heureux"): e = "joie"
    return e


def _fx(p, e):
    fx = {"regard": tuple(p["regard"]) if p.get("regard") is not None and any(p["regard"]) else None}
    if p.get("yeux") == "roule": fx["regard"] = (0.0, -0.85)
    fx["leve"] = 1.0 if p.get("sourcils") == "hausses" else float(p.get("sourcils_h") or 0.0) * 0.5
    fx["son"] = SON.get(str(p.get("viseme") or "").upper(), "a")
    ef = set(p.get("effets") or ())
    if ef & {"larme", "larmes"}: fx["larmes"] = 0.8
    if ef & {"sueur", "goutte"}: fx["sueur"] = 0.8
    r = max(float(p.get("gene") or 0.0), float(p.get("rougeur") or 0.0) * (0.0 if e == "colere" else 0.6))
    if r > 0.05: fx["rouge"] = min(1.0, r)
    t = float(p.get("t") or 0.0); emo = p.get("emo")
    if float(p.get("bouche") or 0) <= 0.04:                                 # micro-expressions quand il se tait
        if emo == "gene": fx["micro"] = "mord"                             # se mord la lèvre
        elif emo in ("soupir", "blase") and (t % 3.2) < 1.1: fx["micro"] = "joues"   # soupir : joues gonflées
        elif emo == "sceptique": fx["micro"] = "rictus"
    if emo == "rire": fx["larmes"] = max(fx.get("larmes", 0), 0.45)        # larmes de rire
    return fx


def _tenue(F, C_):
    """Costume du casting / du métier -> haut, bas, chapeau, détails dans le style croquis."""
    haut = str(C_.get("haut") or "tshirt"); det = set(C_.get("details") or ()); tenue = str(C_.get("tenue") or "")
    h = "tshirt" if haut in COURT else "pull"
    bas = "short" if C_.get("bas") in ("short",) else "pantalon"
    if tenue in ("robe_mariee", "robe_soiree") or (haut == "robe" and tenue not in ("peignoir",) and not C_.get("metier")) or C_.get("bas") == "jupe": bas = "robe"
    if tenue == "maillot_bain":                                            # torse nu, short de bain : aucun détail de buste
        h = None; bas = "short"; det = {d for d in det if d in ("lunettes_vue", "lunettes_soleil", "montre")}
    det |= {"pyjama": set(), "peignoir": {"ceinture"}, "impermeable": {"boutons_or"}, "doudoune": {"echarpe"}, "uniforme": {"cravate"},
            "costume": {"cravate"}}.get(tenue, set())
    extras = [C.deco_buste(DECO[haut])] if haut in DECO else []
    extras += [C.deco_buste(DECO[d], tuple(C_["c_cravate"]) if d == "cravate" and C_.get("c_cravate") else None) for d in det if d in DECO and d != haut]
    if C_.get("barbe_blanche"): extras.append(C.deco_buste("barbe_blanche"))
    st = COIFF.get(str(F.get("cheveux") or ""), None)
    col = tuple(F.get("c_cheveux") or (70, 50, 40))
    if F.get("age", 30) >= 62 and st in ("courts", "carre"): st = "blancs"; col = (225, 225, 228)
    coiffe = C_.get("chapeau") in CHAPEAUX and C_.get("chapeau") not in ("casque_audio",)
    if coiffe and st in ("courts", "blancs", "herisse"): st = None                 # cheveux courts : cachés sous le chapeau
    coif = [C.coiffure(st, col)] if st and st != "herisse" else []
    if F.get("age", 30) >= 55: coif.append(C.rides)
    if F.get("barbe") == "moustache": coif.append(C.moustache)
    elif F.get("barbe") in ("trois_jours", "barbe", "bouc") and F.get("age", 30) >= 16: coif.append(C.mal_rase)
    lun = []
    if "lunettes_ski" in det: lun.append(C.chapeau("lunettes_ski"))
    if "lunettes_soleil" in det: lun.append(C.chapeau("lunettes_soleil"))
    elif F.get("lunettes") or "lunettes_vue" in det: lun.append(C.chapeau("lunettes"))
    ch = C_.get("chapeau")
    chap = C.chapeau({"calot_infirmier": "calot_croix"}.get(ch, ch), tuple(C_["c_chapeau"]) if C_.get("c_chapeau") else None) if ch in CHAPEAUX else None
    return dict(haut=h, c_haut=tuple(C_.get("c_haut") or (120, 160, 210)), bas=bas, c_bas=tuple(C_.get("c_bas") or (60, 80, 130)),
                chaussures=tuple(C_.get("c_chaussures") or (55, 52, 58)), extras=coif + lun + extras, chapeau=chap,
                rayures=((240, 240, 240), tuple(C_.get("c_motif") or (200, 60, 60))) if C_.get("motif") == "rayures" else
                        ((250, 250, 250), tuple(C_.get("c_haut") or (150, 180, 230))) if tenue == "pyjama" else
                        (tuple(int(v * 0.85) for v in (C_.get("c_haut") or (220, 60, 60))), tuple(C_.get("c_haut") or (220, 60, 60))) if tenue == "doudoune" else None,
                c_mains=(200, 50, 60) if "gants" in det else None, montre="montre" in det,
                teint=tuple(C_["teint"]) if C_.get("teint") else None,
                cheveux="herisse" if st == "herisse" else None)


def dessiner(img, F, p):
    """Dessine le personnage (fiche F, pose p au format du moteur) dans le style croquis. Renvoie (tête, (rx, ry))."""
    g = _geom(F, p); R = g["R"]; G = g["G"]
    e = expression(p); T = _tenue(F, dict(p.get("costume") or {}))
    tc = g["tc"]; marge = R * 2.6
    x0, y0 = int(max(0, g["x"] - marge * (1.0 if not G else 1.3) - R)), int(max(0, tc[1] - R * 2.4))
    x1, y1 = int(min(img.shape[1], g["x"] + marge * (1.0 if not G else 1.3) + R)), int(min(img.shape[0], p["y"] + R * 0.5))
    if x1 - x0 < 4 or y1 - y0 < 4: return tc, (R, R)
    zone = img[y0:y1, x0:x1]                                                # petit cadre autour du personnage (rapide)
    def dec(pt): return (pt[0] - x0, pt[1] - y0)
    bras = []
    for (e_, c_, m_) in g["bras"]:
        devant = math.hypot(m_[0] - tc[0], m_[1] - tc[1]) < R * 1.15 and m_[1] < tc[1] + R * 1.1   # main sur le visage : devant la tête
        bras.append(("pts", dec(c_), dec(m_), devant))
    ouv = float(p.get("bouche") or 0.0)
    cl = 1.0 if p.get("yeux") in ("fermes",) else float(p.get("paupiere") or 0.0) * 0.6
    peau = T.get("teint") or (tuple(p["peau"]) if p.get("peau") else None)   # zombie, extraterrestre, vampire : teint du costume
    if p.get("paleur"): peau = tuple(int(v * (1 - 0.15 * p["paleur"]) + 230 * 0.15 * p["paleur"]) for v in (peau or C.PEAU))
    if p.get("assis"):                                                     # chaise vue de face, sous le personnage
        C.chaise_face(zone, g["x"] - x0, p["y"] - y0, R, g["L_j"] * 0.55, g["l_tr"] * 2.6, tuple(p.get("c_chaise") or (160, 110, 70)))
    secousse = abs(math.sin(float(p.get("t") or 0) * 16)) * R * 0.05 if p.get("emo") == "rire" else 0.0   # le rire secoue le corps
    C.bonhomme(zone, g["x"] - x0, p["y"] - y0 - secousse, R, e, bras=tuple(bras), jambes=("assis_face", "assis_face") if p.get("assis") else ("debout", "debout"),
               taille="grand" if G else "chibi", graine=int(F.get("age", 30)) + len(str(F.get("cheveux"))),
               haut=T["haut"], c_haut=T["c_haut"], bas=T["bas"], c_bas=T["c_bas"], chaussures=T["chaussures"], cheveux=T["cheveux"],
               rayures=T["rayures"], teint=peau, profil=float(p.get("tq") or 0.0) * 0.6, extras=T["extras"], chapeau=T["chapeau"],
               ouv=ouv if ouv > 0.04 else None, cligne=min(1.0, cl), penche=g["penche"], fx=_fx(p, e), ecrase=g["ecrase"],
               c_mains=T["c_mains"], montre=T["montre"])
    return tc, (R, R)
