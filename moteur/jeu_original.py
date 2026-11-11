"""Jeu copié sur la vidéo d'origine (choix de l'auteur du 11 novembre 2026, idées 1 et 3) : expressions du visage, mouvements de tête
et gestes des doigts des vraies personnes, recopiés sur nos personnages AU MÊME INSTANT.

Lecture (moteur/visages.py, MediaPipe, gratuit, sur la machine, 8 images/s) : pour chaque visage, ses expressions (sourire, sourcils
levés / froncés, yeux plissés / écarquillés, bouche bée, moue, joues gonflées), l'inclinaison de la tête, la tête levée / baissée,
la tête tournée, et le geste de la main la plus proche (index levé, pouce levé / baissé, V, main ouverte, poing).
Qui est qui : un visage suivi dans un plan (« piste ») appartient au personnage dont il dit les répliques (sa bouche bouge pendant
qu'elles sont dites) ; une piste muette visible en même temps qu'une autre est celle de l'autre personnage (dialogue à deux).
`extraire` (doublage, après la mise en scène) -> sk["_jeu_original"] ; `appliquer` (cartoon.pose, à chaque image) -> la pose.
Rien n'est recopié tel quel quand c'est déjà joué (émotion forte de la réplique, celui qui parle) : l'original nuance, il ne casse
jamais le jeu choisi. Réglages : JEU_ORIGINAL=0 (tout), MAINS=0 (gestes des doigts) ; dessin animé (aucun visage) : rien."""
import os, bisect
import numpy as np

PLAT_MAX = 0.78                                                            # au-delà : visage dessiné (dessin animé), pas une vraie personne
CLES = ("sourire", "haut", "bas", "plisse", "grand", "bee", "moue", "joues", "yaw", "roll", "pitch")
FORMES = {"Pointing_Up": "index", "Thumb_Up": "pouce", "Thumb_Down": "pouce_bas", "Victory": "deux", "Closed_Fist": "poing",
          "Open_Palm": "paume", "ILoveYou": "paume"}


def actif(): return os.environ.get("JEU_ORIGINAL", "1") != "0"


def _echantillon(v):
    b = v.get("bs") or {}
    m = lambda *n: float(np.mean([b.get(x, 0.0) for x in n]))
    return [m("mouthSmileLeft", "mouthSmileRight"), max(m("browInnerUp"), m("browOuterUpLeft", "browOuterUpRight")),
            m("browDownLeft", "browDownRight"), m("eyeSquintLeft", "eyeSquintRight"), m("eyeWideLeft", "eyeWideRight"),
            m("jawOpen"), m("mouthFrownLeft", "mouthFrownRight"), m("cheekPuff"),
            float(v.get("regard") or 0.0), float(v.get("roll") or 0.0), float(v.get("pitch") or 0.0)]


def roles_des_pistes(P, reps):
    """Piste -> rôle : celui dont la bouche bouge pendant ses répliques ; une piste muette visible en même temps qu'une piste d'un
    rôle connu est l'autre rôle (dialogue à deux)."""
    roles = list(dict.fromkeys(r.get("p") for r in reps if r.get("p") not in (None, "narrateur")))
    votes = [dict() for _ in P]
    for r in reps:
        if r.get("p") not in roles: continue
        deb, fin = float(r.get("_deb", 0)), float(r.get("_fin", 0))
        act = []
        for k, piste in enumerate(P):
            z = [v["bouche"] for t, v in piste["ech"] if deb - 0.1 <= t <= fin + 0.1]
            if len(z) >= 2: act.append((float(np.std(z) + 0.5 * np.mean(np.abs(np.diff(z)))), k))
        if not act: continue
        act.sort(reverse=True)
        if act[0][0] < 0.02 or (len(act) > 1 and act[1][0] > 0.8 * act[0][0]): continue   # bouches illisibles ou à égalité
        k = act[0][1]; votes[k][r["p"]] = votes[k].get(r["p"], 0.0) + act[0][0]
    out = [max(v, key=v.get) if v and max(v.values()) > 1.5 * sorted(list(v.values()) + [0])[-2] else None for v in votes]
    if len(roles) == 2:                                                    # pistes muettes : l'autre personnage
        for k, piste in enumerate(P):
            if out[k] is not None: continue
            ta = {round(t, 2) for t, _ in piste["ech"]}
            for j, autre in enumerate(P):
                if j != k and out[j] in roles and autre["plan"] == piste["plan"] and ta & {round(t, 2) for t, _ in autre["ech"]}:
                    out[k] = roles[1 - roles.index(out[j])]; break
    return out


def extraire(video, reps, journal=print):
    """{"expr": {rôle: [[t, sourire, haut, bas, plisse, grand, bee, moue, joues, yaw, roll, pitch]…]}, "mains": {rôle: [[deb, fin, forme]…]}}
    (vide si aucune vraie personne n'est lisible)."""
    if not actif() or not video or not os.path.exists(video): return {}
    import visages
    images = visages.lire(video)
    plats = [v.get("plat", 1.0) for _, _, vis in images for v in vis]
    if plats and float(np.median(plats)) >= PLAT_MAX:                      # visages peints en aplat : un dessin animé (mesuré : 0,84-0,92 ;
        journal(f"  jeu de l'original : visages dessinés (aplat {float(np.median(plats)):.2f}) : rien de recopié")   # vraie peau 0,58-0,74)
        return {}
    P = [p for p in visages.pistes(images) if len(p["ech"]) >= 8]          # visages suivis au moins 1 s (pas un dessin animé qui clignote)
    parole = sum(max(0.0, float(r.get("_fin", 0)) - float(r.get("_deb", 0))) for r in reps) or 1.0
    vu = len({round(t, 1) for p in P for t, _ in p["ech"]}) / visages.IPS
    if not P or vu < 0.25 * parole:
        journal("  jeu de l'original : pas assez de vrais visages (dessin animé, personne de dos…) : rien de recopié"); return {}
    lab = roles_des_pistes(P, reps)
    expr, mains = {}, {}
    for piste, role in zip(P, lab):
        if role is None: continue
        for t, v in piste["ech"]:
            l_ = expr.setdefault(role, [])
            if l_ and t - l_[-1][0] < 0.24: continue                       # 4 valeurs par seconde suffisent (sketch gardé léger)
            l_.append([round(t, 2)] + [round(x, 2) for x in _echantillon(v)])
            if v.get("main") in FORMES: mains.setdefault(role, []).append((t, FORMES[v["main"]]))
    out_m = {}
    for role, l in mains.items():                                          # gestes tenus au moins 0,5 s
        l.sort(); res = []
        for t, f in l:
            if res and res[-1][2] == f and t - res[-1][1] <= 0.3: res[-1][1] = round(t + 0.125, 2)
            else: res.append([round(t, 2), round(t + 0.125, 2), f])
        res = [x for x in res if x[1] - x[0] >= 0.5]
        if res: out_m[role] = res[:60]
    for role in expr: expr[role].sort()
    if expr or out_m:
        journal(f"  jeu de l'original lu : expressions de {', '.join(sorted(expr)) or 'personne'}"
                + (f", gestes des doigts : {', '.join(f'{r} {len(l)}' for r, l in out_m.items())}" if out_m else ""))
    return {"expr": expr, "mains": out_m}


class Jeu:
    """Lecture rapide pendant le dessin : valeurs lissées (0,4 s) à l'instant tm, écarts de la tête par rapport à sa moyenne."""
    def __init__(self, d):
        self.e = {}
        for role, l in ((d or {}).get("expr") or {}).items():
            a = np.array([x[:12] for x in l if len(x) >= 12], np.float32)
            if len(a) < 4: continue
            k = np.ones(3, np.float32) / 3
            v = np.stack([np.convolve(np.pad(a[:, j], 1, mode="edge"), k, "valid") for j in range(1, 12)], 1)
            v[:, 8:] -= np.median(v[:, 8:], axis=0)                       # la tête : seulement ses MOUVEMENTS (pas sa position de départ)
            v[:, 1:5] = np.clip(v[:, 1:5] - np.median(v[:, 1:5], axis=0), 0, 1)   # sourcils, yeux : l'écart à SON visage habituel
            self.e[role] = (a[:, 0].tolist(), v)
        self.m = {r: [tuple(x) for x in l] for r, l in ((d or {}).get("mains") or {}).items()}

    def valeurs(self, role, tm):
        if role not in self.e: return None
        ts, v = self.e[role]
        i = bisect.bisect_left(ts, tm)
        cand = [j for j in (i - 1, i) if 0 <= j < len(ts)]
        j = min(cand, key=lambda j: abs(ts[j] - tm))
        if abs(ts[j] - tm) > 0.35: return None                             # personne à l'image dans l'original à cet instant
        return dict(zip(CLES, (float(x) for x in v[j])))

    def main(self, role, tm):
        """(forme, force 0-1 pour lever le bras en douceur) du geste des doigts tenu à l'instant tm."""
        for a, b, f in self.m.get(role) or ():
            if a - 0.25 <= tm <= b + 0.25:
                u = min(1.0, (tm - a + 0.25) / 0.25, (b + 0.25 - tm) / 0.25)
                return f, max(0.0, u)
        return None, 0.0


# bras droit (angle du bras depuis la verticale vers le bas, puis de l'avant-bras) : bras tendu sur le côté à hauteur de poitrine (grosse tête : une main levée passait devant le visage)
BRAS_DOIGTS = {"index": (35, 58), "deux": (35, 58), "pouce": (35, 58), "pouce_bas": (35, 58), "paume": (35, 50), "poing": (35, 58)}


def appliquer(p, jeu, role, tm, parle, exagere=1.25):
    """Nuance la pose du moteur avec le jeu de l'original (modifie p)."""
    if jeu is None: return
    v = jeu.valeurs(role, tm)
    forte = p.get("emo") not in (None, "neutre", "ecoute")
    if v:
        k = max(0.8, min(1.6, exagere))
        if not forte:                                                     # émotion lue sur le visage (si rien de fort n'est déjà joué)
            if v["sourire"] > 0.55: p["emo"] = "joie"
            elif v["bas"] > 0.35 and v["sourire"] < 0.2: p["emo"] = "colere"
            elif v["grand"] > 0.3 and v["bee"] > 0.45 and not parle: p["emo"] = "choc"
            elif v["moue"] > 0.45 and v["sourire"] < 0.15: p["emo"] = "sceptique"
        p["sourcils_h"] = float(np.clip(p.get("sourcils_h", 0.0) + 1.6 * k * v["haut"] - 1.2 * k * v["bas"], -0.8, 1.5))
        if v["plisse"] > 0.25: p["paupiere"] = max(p.get("paupiere", 0.0), 0.35)
        if v["grand"] > 0.25: p["pupille"] = max(p.get("pupille", 1.0), 1.0 + 0.8 * v["grand"])
        p["tilt"] = float(p.get("tilt", 0.0) + np.clip(v["roll"] * 0.8 * k, -12, 12))                 # tête penchée
        p["tq"] = float(np.clip(p.get("tq", 0.0) + 0.5 * v["yaw"], -1.0, 1.0))                        # tête tournée
        rx, ry = p.get("regard") or (0.0, 0.0)
        p["regard"] = (float(rx), float(np.clip(ry + 1.6 * v["pitch"], -0.9, 0.9)))                   # tête baissée : regard baissé
    f, u = jeu.main(role, tm)
    if f and u > 0 and not p.get("main_d"):                                # geste des doigts (main droite, si elle ne tient rien)
        cible = BRAS_DOIGTS.get(f)
        b0 = p.get("bras_d") or (0, 0)
        if cible: p["bras_d"] = (b0[0] + (cible[0] - b0[0]) * u, b0[1] + (cible[1] - b0[1]) * u)
        p["doigts_d"] = f
