"""Personnages NON HUMAINS (remarque de l'auteur du 31 octobre 2026 : le steak du micro-ondes et le chat Maurice dessinés en humains).

Un rôle peut être un animal ou un objet qui parle, dessiné dans le style croquis avec le MÊME visage que nos personnages (yeux,
sourcils, expressions, bouche synchronisée sur la voix, larmes, sueur, rougeur) : chat, chien, steak, pizza, œuf, banane, ou un objet
quelconque (forme arrondie colorée). Tête au même endroit que les humains (cadrages, sous-titres et contrôles inchangés), pattes ou
petits bras en bâton qui suivent les gestes du moteur.
Qui est quoi : l'IA le dit ("personnages" → "espece"), sinon le dialogue (« je suis un chat » = celui qui parle ; « mon chat, … »,
« t'es un chat », « sale chat » = celui à qui l'on parle). ESPECES=0 pour couper (tout le monde redevient humain)."""
import math, os, re
import numpy as np
import cv2

import croquis as C

AA = cv2.LINE_AA
# couleurs en BGR (comme tout le dessin croquis)
ANIMAUX = {"chat": dict(poil=(70, 150, 230), museau=(225, 235, 246)), "chien": dict(poil=(80, 125, 175), museau=(220, 232, 242)),
           "lapin": dict(poil=(222, 222, 230), museau=(246, 246, 250)), "souris": dict(poil=(160, 155, 158), museau=(222, 218, 224)),
           "oiseau": dict(poil=(70, 195, 245), museau=None)}
OBJETS = {"steak": (70, 80, 160), "pizza": (90, 200, 245), "oeuf": (246, 248, 250), "banane": (80, 220, 245), "poisson": (40, 140, 240),
          "voiture": (55, 55, 205), "frigo": (238, 238, 242), "telephone": (48, 46, 52), "verre": (240, 236, 228), "croissant": (75, 165, 228),
          "objet": (200, 190, 180)}
ESPECES = tuple(ANIMAUX) + tuple(OBJETS)
MOTS = {"chat": r"chat|chaton|minou|matou|minet", "chien": r"chien|chienne|chiot|toutou|clebs", "lapin": r"lapin|lapine|lapinou",
        "souris": r"souris|\brat\b|ratounet", "oiseau": r"oiseau|pigeon|perroquet|poussin|canari|moineau|perruche",
        "poisson": r"poisson|poisson rouge", "steak": r"steak|bifteck|viande", "pizza": r"pizza", "oeuf": r"[œo]euf", "banane": r"banane",
        "voiture": r"voiture|bagnole", "frigo": r"frigo|frigidaire|r[ée]frig[ée]rateur", "telephone": r"t[ée]l[ée]phone|portable|smartphone|iphone",
        "verre": r"verre", "croissant": r"croissant"}
PARLE_A = ("chat", "chien", "lapin", "souris", "oiseau", "poisson")        # ceux à qui l'on parle (« mon chat, … ») ; les objets : « je suis un… »
NOIR = r"(chat|chaton|chien) noir|noir comme"


def espece_valide(e):
    """« chat », « Chat », « animal:chat », « objet:steak », « steak haché »… -> une espèce connue (ou None pour un humain)."""
    if os.environ.get("ESPECES", "1") == "0": return None
    t = str(e or "").lower().strip()
    if not t or t in ("humain", "human", "personne", "homme", "femme", "aucune", "none"): return None
    t = t.split(":", 1)[-1]
    for nom, mm in MOTS.items():
        if re.search(r"\b(?:" + mm + r")", t): return nom
    if t.startswith(("objet", "object", "chose", "thing")) or e and str(e).lower().startswith("objet:"): return "objet"
    return None


def qui_est(sk):
    """{rôle: espèce} d'après le dialogue seul (prudent : il faut une phrase claire)."""
    if os.environ.get("ESPECES", "1") == "0": return {}
    reps = [r for r in (sk.get("repliques") or []) if isinstance(r, dict)]
    roles = [r for r in dict.fromkeys(x.get("p") for x in reps) if r and r != "narrateur"]
    votes = {}
    def voter(role, e, n):
        if role in roles: votes.setdefault(role, {}).setdefault(e, 0); votes[role][e] += n
    def autre(i):
        moi = reps[i].get("p")
        for j in (i + 1, i - 1, i + 2, i - 2):
            if 0 <= j < len(reps) and reps[j].get("p") not in (moi, "narrateur", None): return reps[j]["p"]
        return next((r for r in roles if r != moi), None)
    for i, r in enumerate(reps):
        t = " " + str(r.get("t") or "").lower().replace("’", "'") + " "
        for e, mm in MOTS.items():
            art = r"(?:un |une |le |la |ton |ta |votre )" + ("?" if e in PARLE_A else "")    # objet : « je suis un téléphone » (jamais « je suis au téléphone »)
            adj = r"(?:(?!au |aux |en |dans |sur |à |a |chez |avec |sous |pas |plus |dessus |devant |derri[èe]re )\w+ )?"
            if re.search(r"\b(je suis|j'suis|chuis|moi,? je suis|en tant que)\s+" + art + adj + r"(?:" + mm + r")s?\b", t): voter(r.get("p"), e, 3)
            if re.search(r"\b(t'es|tu es|vous [êe]tes|espèce de|sale)\s+(?:un |une |le |la |qu'un |qu'une )" + ("?" if e in PARLE_A else "") + adj + r"(?:" + mm + r")s?\b", t) or \
               (e in PARLE_A and re.search(r"(^\s*|[,!?.]\s*|\b(?:oh|eh|hé|allez|viens)\s+)(?:[\w-]+\s*,\s*)?(?:mon |ma |petit |gros |sale )?(?:" + mm + r")\s*([,!?.]|t'es|tu es|viens|arr[êe]te)", t)):
                voter(autre(i), e, 1)                                      # on lui parle (« mon chat, … », « sale chien ») : aussi des mots doux
                                                                           # ou des insultes entre humains -> il faut un 2e indice
    out = {}
    for role, v in votes.items():
        e, n = max(v.items(), key=lambda kv: kv[1])
        if n >= 2 and len(out) < len(roles) - 1 + (1 if len(roles) == 1 else 0): out[role] = e   # au moins un humain quand ils sont deux
    return out


def couleur(espece, texte=""):
    if espece in ANIMAUX and re.search(NOIR, str(texte).lower()): return (42, 40, 44)
    return ANIMAUX[espece]["poil"] if espece in ANIMAUX else OBJETS.get(espece, OBJETS["objet"])


# ------------------------------------------------------------------ dessin
def _fond(img, pts, coul, R, graine, ombre=True):
    cv2.fillPoly(img, [C._pts(pts)], coul, AA, 2)
    if ombre:
        m = cv2.bitwise_and(C.masque(img.shape, pts), C.masque(img.shape, pts))
        C.hachures(img, cv2.bitwise_and(m, cv2.erode(m, np.ones((3, 3), np.uint8))), -50, R * 0.09, R * 0.016, tuple(int(v * 0.6) for v in coul), 0.35, graine)


def _visage(img, c, R, expr, fx, ouv, cligne, rng, museau=None):
    if museau is not None:                                                 # museau clair : la bouche se voit même sur un poil foncé
        cv2.ellipse(img, C._pts([(c[0], c[1] + R * 0.5)])[0], (int(R * 0.5 * 4), int(R * 0.34 * 4)), 0, 0, 360, museau, -1, AA, 2)
    C.visage(img, c, R, expr, (fx or {}).get("regard") or (0, 0), rng, 0.0, nez_vu=museau is None, ouv=ouv, cligne=cligne, fx=fx)


def _relatif(epaule, bras_humain, k):
    """Même geste que le bras humain (coude, main), mais partant de « epaule » et k fois plus court."""
    e_, c_, m_ = bras_humain
    return (epaule, (epaule[0] + (c_[0] - e_[0]) * k, epaule[1] + (c_[1] - e_[1]) * k), (epaule[0] + (m_[0] - e_[0]) * k, epaule[1] + (m_[1] - e_[1]) * k))


def _pattes(img, bras, larg, coul, ep, R, rond=True):
    for e_, c_, m_ in bras:
        C.membre(img, [e_, c_, m_], larg, coul, ep)
        if rond:
            cv2.circle(img, C._pts([m_])[0], int(R * 0.16 * 4), C.ENCRE, -1, AA, 2); cv2.circle(img, C._pts([m_])[0], int(R * 0.13 * 4), coul, -1, AA, 2)
        else: C.main(img, m_, R * 0.14, 0, "ouverte", ep)




def _collier(img, tc, R, bas_tete, graine, ep):
    """Collier rouge (ou bleu, vert…) avec une médaille dorée, au cou de l'animal."""
    c = ((50, 50, 200), (190, 110, 40), (60, 160, 70), (160, 60, 160))[graine % 4]
    arc = C.cercle_pts((tc[0], bas_tete - R * 0.12), R * 0.55, R * 0.16, 20, 160, 24)
    C.encre(img, arc, R * 0.16, coul=C.ENCRE, effile=False); C.encre(img, arc, R * 0.11, coul=c, effile=False)
    m = (tc[0], bas_tete + R * 0.12)
    cv2.circle(img, C._pts([m])[0], int(R * 0.1 * 4), C.ENCRE, -1, AA, 2); cv2.circle(img, C._pts([m])[0], int(R * 0.075 * 4), (60, 200, 240), -1, AA, 2)


def _noeud(img, c, r, coul=(140, 90, 235)):
    """Petit nœud (sur la tête d'une « fille », ou nœud papillon)."""
    for s_ in (-1, 1):
        aile = [(c[0], c[1]), (c[0] + s_ * r, c[1] - r * 0.55), (c[0] + s_ * r, c[1] + r * 0.55)]
        cv2.fillPoly(img, [C._pts(aile)], coul, AA, 2); C.encre(img, aile, r * 0.12, ferme=True)
    cv2.circle(img, C._pts([c])[0], int(r * 0.28 * 4), C.ENCRE, -1, AA, 2); cv2.circle(img, C._pts([c])[0], int(r * 0.2 * 4), coul, -1, AA, 2)


def dessiner(img, espece, x, sol, tc, R, bras, expr="neutre", ouv=None, cligne=0.0, fx=None, graine=0, coul=None,
             chapeau=None, lunettes=(), fille=False):
    """Dessine l'animal / l'objet dans img (coordonnées du petit cadre). tc = centre de la tête (même place que pour un humain).
    chapeau / lunettes : fonctions (img, centre, R) du style croquis (costume, métier) ; fille : petit nœud sur la tête."""
    rng = np.random.default_rng(graine); ep = R * 0.045; coul = tuple(coul or couleur(espece))
    C.ombre_sol(img, (x, sol), R * 0.95)
    if espece in ANIMAUX:
        A = ANIMAUX[espece]; museau = A["museau"] or (235, 240, 246)
        bas_tete = tc[1] + R * 0.85; h = max(R * 0.6, sol - bas_tete)
        oiseau = espece == "oiseau"
        corps = C.cercle_pts((x, bas_tete + h * 0.5), R * (0.68 if oiseau else 0.72), h * (0.48 if oiseau else 0.55), n=60)
        if espece in ("chat", "chien"):                                    # longue queue
            C.membre(img, C.courbe((x + R * 0.6, sol - R * 0.25), (x + R * 1.5, sol - R * 0.4), (x + R * 1.25, sol - h * 0.95), 16), R * 0.16, coul, ep)
        elif espece == "souris":                                           # queue fine et rose qui ondule
            C.membre(img, C.courbe((x + R * 0.55, sol - R * 0.2), (x + R * 1.7, sol + R * 0.05), (x + R * 1.5, sol - h * 0.7), 18), R * 0.05, (170, 160, 230), ep * 0.7)
        elif oiseau:                                                       # plumes de la queue
            q = [(x + R * 0.45, bas_tete + h * 0.7), (x + R * 1.15, bas_tete + h * 0.95), (x + R * 0.95, bas_tete + h * 0.55)]
            cv2.fillPoly(img, [C._pts(q)], tuple(int(v * 0.8) for v in coul), AA, 2); C.encre(img, q, ep, ferme=True)
        if oiseau:                                                         # pattes fines orange à trois doigts
            for s_ in (-1, 1):
                a_ = (x + s_ * R * 0.22, bas_tete + h * 0.95); b_ = (x + s_ * R * 0.25, sol - R * 0.02)
                C.encre(img, [a_, b_], R * 0.06, coul=(40, 140, 240))
                for d_ in (-0.16, 0.0, 0.16): C.encre(img, [b_, (b_[0] + R * d_ + s_ * R * 0.05, sol)], R * 0.045, coul=(40, 140, 240))
        _fond(img, corps, coul, R, graine); C.encre(img, corps, ep, ferme=True, rng=rng)
        if oiseau:                                                         # ventre clair
            v = C.cercle_pts((x, bas_tete + h * 0.58), R * 0.42, h * 0.32, n=40); cv2.fillPoly(img, [C._pts(v)], museau, AA, 2)
        else:
            for s_ in (-1, 1):                                             # pattes avant posées au sol
                pp = C.cercle_pts((x + s_ * R * 0.32, sol - R * 0.08), R * 0.24, R * 0.13, n=24)
                cv2.fillPoly(img, [C._pts(pp)], museau, AA, 2); C.encre(img, pp, ep * 0.8, ferme=True)
        if espece == "lapin":                                              # queue en pompon
            cv2.circle(img, C._pts([(x + R * 0.7, sol - R * 0.3)])[0], int(R * 0.2 * 4), C.ENCRE, -1, AA, 2)
            cv2.circle(img, C._pts([(x + R * 0.7, sol - R * 0.3)])[0], int(R * 0.17 * 4), (250, 250, 252), -1, AA, 2)
        b2 = [b_ for b_ in bras if b_[2][1] < b_[0][1] + R * 0.6]           # patte (ou aile) levée pour un geste
        _pattes(img, [_relatif((x + (R * 0.45 if b_[2][0] > b_[0][0] or b_[0][0] > x else -R * 0.45), bas_tete + h * 0.25), b_, 0.7) for b_ in b2],
                R * (0.22 if oiseau else 0.17), tuple(int(v * 0.85) for v in coul) if oiseau else coul, ep, R)
        if espece == "chat":                                               # oreilles pointues (derrière la tête)
            for s_ in (-1, 1):
                o = [(tc[0] + s_ * R * 0.25, tc[1] - R * 0.85), (tc[0] + s_ * R * 0.92, tc[1] - R * 1.25), (tc[0] + s_ * R * 0.88, tc[1] - R * 0.35)]
                cv2.fillPoly(img, [C._pts(o)], coul, AA, 2); C.encre(img, o, ep, ferme=True)
                oi = [(tc[0] + s_ * R * 0.42, tc[1] - R * 0.8), (tc[0] + s_ * R * 0.82, tc[1] - R * 1.05), (tc[0] + s_ * R * 0.8, tc[1] - R * 0.55)]
                cv2.fillPoly(img, [C._pts(oi)], (170, 160, 235), AA, 2)
        elif espece == "lapin":                                            # longues oreilles dressées
            for s_ in (-1, 1):
                o = C.cercle_pts((tc[0] + s_ * R * 0.38, tc[1] - R * 1.45), R * 0.24, R * 0.75, n=30, rot=s_ * 10)
                cv2.fillPoly(img, [C._pts(o)], coul, AA, 2); C.encre(img, o, ep, ferme=True)
                oi = C.cercle_pts((tc[0] + s_ * R * 0.38, tc[1] - R * 1.42), R * 0.11, R * 0.55, n=24, rot=s_ * 10)
                cv2.fillPoly(img, [C._pts(oi)], (175, 165, 238), AA, 2)
        elif espece == "souris":                                           # grandes oreilles rondes
            for s_ in (-1, 1):
                o = C.cercle_pts((tc[0] + s_ * R * 0.82, tc[1] - R * 0.78), R * 0.48, n=40)
                cv2.fillPoly(img, [C._pts(o)], coul, AA, 2); C.encre(img, o, ep, ferme=True)
                cv2.circle(img, C._pts([(tc[0] + s_ * R * 0.82, tc[1] - R * 0.78)])[0], int(R * 0.3 * 4), (175, 165, 238), -1, AA, 2)
        tete = C.cercle_pts(tc, R, R * 0.92, n=80)
        _fond(img, tete, coul, R, graine)
        if espece == "chat":                                               # rayures du chat tigré
            for k in (-1, 0, 1):
                C.encre(img, C.courbe((tc[0] + k * R * 0.25, tc[1] - R * 0.9), (tc[0] + k * R * 0.2, tc[1] - R * 0.7), (tc[0] + k * R * 0.28, tc[1] - R * 0.55), 6),
                        R * 0.04, coul=tuple(int(v * 0.7) for v in coul))
        if oiseau:                                                         # houppette sur la tête
            for d_ in (-0.15, 0.0, 0.15):
                C.encre(img, C.courbe((tc[0] + R * d_, tc[1] - R * 0.88), (tc[0] + R * (d_ * 2), tc[1] - R * 1.25), (tc[0] + R * (d_ * 2 + 0.15), tc[1] - R * 1.3), 8), R * 0.05)
        _visage(img, tc, R, expr, fx, ouv, cligne, rng, None if oiseau else museau)
        nez = (tc[0], tc[1] + R * 0.3)
        if oiseau:                                                         # bec orange (la bouche reste visible dessous)
            bec = [(nez[0] - R * 0.18, nez[1] - R * 0.05), (nez[0] + R * 0.18, nez[1] - R * 0.05), (nez[0], nez[1] + R * 0.16)]
            cv2.fillPoly(img, [C._pts(bec)], (40, 150, 245), AA, 2); C.encre(img, bec, ep * 0.7, ferme=True)
        elif espece in ("chat", "lapin", "souris"):
            tri = [(nez[0] - R * 0.1, nez[1] - R * 0.05), (nez[0] + R * 0.1, nez[1] - R * 0.05), (nez[0], nez[1] + R * 0.07)]
            cv2.fillPoly(img, [C._pts(tri)], (150, 130, 235), AA, 2); C.encre(img, tri, ep * 0.6, ferme=True)
            for s_ in (-1, 1):                                             # moustaches
                for k, dy in enumerate((-0.06, 0.04, 0.14)):
                    C.encre(img, [(nez[0] + s_ * R * 0.42, nez[1] + R * dy), (nez[0] + s_ * R * 1.12, nez[1] + R * (dy * 2.2 - 0.04))], R * 0.018)
        else:
            cv2.ellipse(img, C._pts([nez])[0], (int(R * 0.15 * 4), int(R * 0.1 * 4)), 0, 0, 360, C.ENCRE, -1, AA, 2)
        C.encre(img, tete, R * 0.05, ferme=True, rng=rng)
        if espece == "chien":                                              # oreilles tombantes (par-dessus le contour)
            for s_ in (-1, 1):
                o = C.cercle_pts((tc[0] + s_ * R * 0.92, tc[1] - R * 0.05), R * 0.26, R * 0.58, n=30, rot=s_ * 18)
                cv2.fillPoly(img, [C._pts(o)], tuple(int(v * 0.72) for v in coul), AA, 2); C.encre(img, o, ep, ferme=True)
        if espece in ("chat", "chien"): _collier(img, tc, R, bas_tete, graine, ep)   # animal de compagnie : collier et médaille
        for l_ in lunettes or (): l_(img, tc, R)
        if chapeau: chapeau(img, tc, R)
        elif fille: _noeud(img, (tc[0] + R * 0.55, tc[1] - R * 0.8), R * 0.28)
        return
    # --- objet qui parle : le corps EST la tête (grand visage), petits bras et jambes en bâton
    Rb = R * 1.18; face = tc; haut = tc[1] - Rb * 0.9; jambes, bras_ok = True, True; ep_x = 0.88 * Rb
    if espece == "steak":
        pts = [(tc[0] + Rb * (1.05 + 0.08 * math.sin(3 * t)) * math.cos(t), tc[1] + Rb * 0.82 * (1 + 0.06 * math.cos(5 * t)) * math.sin(t))
               for t in np.linspace(0, 2 * math.pi, 70)]; ep_x = 0.95 * Rb; haut = tc[1] - Rb * 0.82
    elif espece == "pizza":
        pts = [(tc[0] - Rb * 1.05, tc[1] - Rb * 0.75), (tc[0] + Rb * 1.05, tc[1] - Rb * 0.75), (tc[0], tc[1] + Rb * 1.05)]
        face = (tc[0], tc[1] - Rb * 0.15); ep_x = 0.5 * Rb; haut = tc[1] - Rb * 0.75
    elif espece == "oeuf":
        pts = [(tc[0] + Rb * 0.82 * math.cos(t), tc[1] + Rb * (0.95 if math.sin(t) > 0 else 1.15) * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 70)]
        ep_x = 0.8 * Rb; haut = tc[1] - Rb * 1.15
    elif espece == "banane":
        pts = C.courbe((tc[0] - Rb * 1.0, tc[1] - Rb * 0.9), (tc[0] + Rb * 0.25, tc[1] - Rb * 0.25), (tc[0] + Rb * 0.55, tc[1] + Rb * 1.0), 24) + \
              C.courbe((tc[0] + Rb * 0.05, tc[1] + Rb * 1.05), (tc[0] - Rb * 0.75, tc[1] + Rb * 0.25), (tc[0] - Rb * 1.0, tc[1] - Rb * 0.9), 24)
        face = (tc[0] - Rb * 0.25, tc[1]); ep_x = 0.5 * Rb
    elif espece == "poisson":                                              # il flotte au-dessus du sol (pas de jambes)
        pts = C.cercle_pts(tc, Rb * 1.05, Rb * 0.78, n=70); jambes = False; ep_x = 0.7 * Rb; haut = tc[1] - Rb * 0.78
        q = [(tc[0] + Rb * 0.9, tc[1]), (tc[0] + Rb * 1.6, tc[1] - Rb * 0.6), (tc[0] + Rb * 1.6, tc[1] + Rb * 0.6)]
        cv2.fillPoly(img, [C._pts(q)], tuple(int(v * 0.8) for v in coul), AA, 2); C.encre(img, q, ep, ferme=True)
        d_ = [(tc[0] - Rb * 0.3, tc[1] - Rb * 0.7), (tc[0] + Rb * 0.1, tc[1] - Rb * 1.15), (tc[0] + Rb * 0.45, tc[1] - Rb * 0.62)]
        cv2.fillPoly(img, [C._pts(d_)], tuple(int(v * 0.8) for v in coul), AA, 2); C.encre(img, d_, ep, ferme=True)
        for k in range(3):                                                 # bulles
            cv2.circle(img, C._pts([(tc[0] - Rb * (0.6 + 0.25 * k), tc[1] - Rb * (1.2 + 0.35 * k))])[0], int(R * (0.07 + 0.03 * k) * 4), C.ENCRE, max(1, int(ep * 0.6)), AA, 2)
        face = (tc[0] - Rb * 0.2, tc[1])
    elif espece == "voiture":                                              # carrosserie + toit vitré, deux roues au sol ; pas de bras
        bas = sol - R * 0.32; L_ = Rb * 1.85
        pts = [(tc[0] - L_, bas), (tc[0] - L_, tc[1] + Rb * 0.25), (tc[0] - L_ * 0.62, tc[1] + Rb * 0.2), (tc[0] - L_ * 0.48, tc[1] - Rb * 0.95),
               (tc[0] + L_ * 0.48, tc[1] - Rb * 0.95), (tc[0] + L_ * 0.62, tc[1] + Rb * 0.2), (tc[0] + L_, tc[1] + Rb * 0.25), (tc[0] + L_, bas)]
        jambes = bras_ok = False; haut = tc[1] - Rb * 0.95
    elif espece == "frigo":
        pts = [(tc[0] - Rb * 0.85, tc[1] - Rb * 1.05), (tc[0] + Rb * 0.85, tc[1] - Rb * 1.05), (tc[0] + Rb * 0.85, tc[1] + Rb * 1.6), (tc[0] - Rb * 0.85, tc[1] + Rb * 1.6)]
        ep_x = 0.85 * Rb; haut = tc[1] - Rb * 1.05
    elif espece == "telephone":
        pts = [(tc[0] + Rb * 0.72 * np.sign(math.cos(t)) * abs(math.cos(t)) ** 0.25, tc[1] + Rb * 1.15 * np.sign(math.sin(t)) * abs(math.sin(t)) ** 0.25)
               for t in np.linspace(0, 2 * math.pi, 80)]
        ep_x = 0.72 * Rb; haut = tc[1] - Rb * 1.15
    elif espece == "verre":
        pts = [(tc[0] - Rb * 0.95, tc[1] - Rb * 0.95), (tc[0] + Rb * 0.95, tc[1] - Rb * 0.95), (tc[0] + Rb * 0.7, tc[1] + Rb * 1.0), (tc[0] - Rb * 0.7, tc[1] + Rb * 1.0)]
        ep_x = 0.82 * Rb; haut = tc[1] - Rb * 0.95
    elif espece == "croissant":
        ext = C.cercle_pts((tc[0], tc[1] + Rb * 0.35), Rb * 1.2, Rb * 1.0, 195, 345, 30)
        int_ = C.cercle_pts((tc[0], tc[1] + Rb * 0.75), Rb * 0.8, Rb * 0.55, 340, 200, 30)
        pts = ext + int_; face = (tc[0], tc[1] - Rb * 0.15); ep_x = 0.9 * Rb; haut = tc[1] - Rb * 0.65
    else:
        pts = [(tc[0] + Rb * 0.95 * np.sign(math.cos(t)) * abs(math.cos(t)) ** 0.6, tc[1] + Rb * 0.9 * np.sign(math.sin(t)) * abs(math.sin(t)) ** 0.6)
               for t in np.linspace(0, 2 * math.pi, 72)]
    if jambes:
        bas_obj = max(p_[1] for p_ in pts) - Rb * 0.1
        for s_ in (-1, 1):
            a = (tc[0] + s_ * Rb * 0.32, bas_obj); b = (x + s_ * R * 0.42, sol - R * 0.05)
            if b[1] - a[1] > R * 0.1:
                C.membre(img, [a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), b], R * 0.07, (252, 252, 250), ep)
            C.pied(img, b, R * 0.15, s_, (55, 52, 58), ep)
    _fond(img, pts, coul, R, graine, ombre=espece not in ("verre", "telephone"))
    if espece == "steak":                                                  # gras et marques du grill
        C.encre(img, C.courbe((tc[0] - Rb * 0.95, tc[1] + Rb * 0.1), (tc[0] - Rb * 0.6, tc[1] + Rb * 0.75), (tc[0] + Rb * 0.2, tc[1] + Rb * 0.78), 14),
                R * 0.09, coul=(225, 232, 245))
        for k in (-1, 0, 1):
            C.encre(img, [(tc[0] + k * Rb * 0.45 - Rb * 0.3, tc[1] - Rb * 0.65), (tc[0] + k * Rb * 0.45 + Rb * 0.25, tc[1] - Rb * 0.15)], R * 0.06, coul=(35, 40, 70))
    elif espece == "pizza":
        cv2.fillPoly(img, [C._pts([pts[0], pts[1], ((pts[0][0] + pts[1][0]) / 2, pts[0][1] + Rb * 0.18)])], (60, 140, 205), AA, 2)   # croûte
        for dx, dy in ((-0.5, -0.35), (0.45, -0.3), (0.0, 0.55)):
            cv2.circle(img, C._pts([(tc[0] + dx * Rb, tc[1] + dy * Rb)])[0], int(Rb * 0.13 * 4), (50, 60, 190), -1, AA, 2)
    elif espece == "oeuf":
        cv2.circle(img, C._pts([(tc[0] + Rb * 0.45, tc[1] - Rb * 0.55)])[0], int(Rb * 0.08 * 4), (255, 255, 255), -1, AA, 2)
    elif espece == "banane":
        C.encre(img, [pts[0], (pts[0][0] - Rb * 0.12, pts[0][1] - Rb * 0.18)], R * 0.09, coul=(40, 70, 90))
    elif espece == "poisson":                                              # écailles
        for k in range(3):
            for j in range(2):
                C.encre(img, C.cercle_pts((tc[0] + Rb * (0.25 + 0.22 * k), tc[1] + Rb * (-0.2 + 0.35 * j)), Rb * 0.13, None, 300, 420, 8), R * 0.025,
                        coul=tuple(int(v * 0.65) for v in coul))
    elif espece == "voiture":                                              # vitre (le visage), pare-chocs, phares, roues
        vitre = [(tc[0] - Rb * 0.95, tc[1] + Rb * 0.15), (tc[0] - Rb * 0.78, tc[1] - Rb * 0.8), (tc[0] + Rb * 0.78, tc[1] - Rb * 0.8), (tc[0] + Rb * 0.95, tc[1] + Rb * 0.15)]
        cv2.fillPoly(img, [C._pts(vitre)], (235, 225, 200), AA, 2); C.encre(img, vitre, ep, ferme=True)
        for s_ in (-1, 1):
            cv2.circle(img, C._pts([(tc[0] + s_ * Rb * 1.5, tc[1] + Rb * 0.55)])[0], int(R * 0.16 * 4), (150, 235, 250), -1, AA, 2)
            r_ = C.cercle_pts((tc[0] + s_ * Rb * 1.25, sol - R * 0.32), R * 0.38, n=36)
            cv2.fillPoly(img, [C._pts(r_)], (40, 38, 42), AA, 2)
            cv2.circle(img, C._pts([(tc[0] + s_ * Rb * 1.25, sol - R * 0.32)])[0], int(R * 0.15 * 4), (190, 190, 195), -1, AA, 2)
        C.encre(img, [(tc[0] - Rb * 1.85, sol - R * 0.75), (tc[0] + Rb * 1.85, sol - R * 0.75)], R * 0.05)
    elif espece == "frigo":                                                # porte du congélateur et poignées
        C.encre(img, [(tc[0] - Rb * 0.85, tc[1] + Rb * 0.75), (tc[0] + Rb * 0.85, tc[1] + Rb * 0.75)], ep)
        for y_ in (tc[1] + Rb * 0.45, tc[1] + Rb * 1.0):
            C.encre(img, [(tc[0] + Rb * 0.62, y_), (tc[0] + Rb * 0.62, y_ + Rb * 0.25)], R * 0.08, coul=(170, 170, 175))
        cv2.circle(img, C._pts([(tc[0] - Rb * 0.5, tc[1] + Rb * 1.15)])[0], int(R * 0.1 * 4), (60, 60, 210), -1, AA, 2)   # aimant
    elif espece == "telephone":                                            # écran allumé (le visage dessus)
        ec = [(tc[0] - Rb * 0.6, tc[1] - Rb * 0.95), (tc[0] + Rb * 0.6, tc[1] - Rb * 0.95), (tc[0] + Rb * 0.6, tc[1] + Rb * 0.95), (tc[0] - Rb * 0.6, tc[1] + Rb * 0.95)]
        cv2.fillPoly(img, [C._pts(ec)], (240, 222, 196), AA, 2)
        C.encre(img, [(tc[0] - Rb * 0.15, tc[1] - Rb * 1.05), (tc[0] + Rb * 0.15, tc[1] - Rb * 1.05)], R * 0.05, coul=(20, 20, 22))
    elif espece == "verre":                                                # eau, reflet
        lvl = tc[1] + Rb * 0.15
        eau = [(tc[0] - Rb * (0.95 - 0.25 * (lvl - pts[0][1]) / (Rb * 1.95)), lvl), (tc[0] + Rb * (0.95 - 0.25 * (lvl - pts[0][1]) / (Rb * 1.95)), lvl), pts[2], pts[3]]
        cv2.fillPoly(img, [C._pts(eau)], (230, 200, 150), AA, 2)
        C.encre(img, [(tc[0] - Rb * 0.7, tc[1] - Rb * 0.75), (tc[0] - Rb * 0.55, tc[1] + Rb * 0.7)], R * 0.06, coul=(255, 255, 255))
    elif espece == "croissant":                                            # nervures du feuilletage
        for k in (-0.55, -0.15, 0.25, 0.65):
            C.encre(img, [(tc[0] + Rb * k, tc[1] - Rb * 0.6), (tc[0] + Rb * (k + 0.1), tc[1] + Rb * 0.15)], R * 0.04, coul=(40, 110, 170))
    _visage(img, face, R * 0.85, expr, fx, ouv, cligne, rng)
    C.encre(img, pts, R * 0.05, ferme=True, rng=rng)
    for l_ in lunettes or (): l_(img, face, R * 0.85)
    if chapeau: chapeau(img, (tc[0], haut + R * (0.35 if espece == "pizza" else 0.72)), R)
    elif fille and espece not in ("voiture",): _noeud(img, (tc[0] + Rb * 0.5, haut + R * 0.1), R * 0.28)
    if bras_ok:
        _pattes(img, [_relatif((tc[0] + (ep_x if b_[0][0] > x else -ep_x), tc[1] + Rb * 0.15), b_, 0.75 * R / max(1.0, math.dist(b_[0], b_[1]) + math.dist(b_[1], b_[2])) * 1.6)
                      for b_ in bras], R * (0.12 if espece == "poisson" else 0.07), tuple(int(v * 0.8) for v in coul) if espece == "poisson" else (252, 252, 250),
                     ep, R, rond=espece == "poisson")
