"""Expressions lues sur les DESSINS ANIMÉS d'origine (choix de l'auteur du 23 novembre 2026, idée 14). Le jeu copié sur l'original
(moteur/jeu_original.py, MediaPipe) ne lit que les vraies personnes : sur un dessin animé (la plupart de nos sons : vignianimation,
yan_animation0, kodanimation…) il ne recopiait rien. Ici, Gemini regarde une image de l'original au milieu de chaque réplique (14 au
plus, en UN seul appel) et dit, pour le personnage de gauche et celui de droite : qui parle, son émotion et sa force (1-3).
Le côté de chaque rôle se déduit de « qui parle » (le personnage qui dit la réplique). Résultat : sk["_jeu_dessin"] =
{rôle: [[début, fin, émotion, force]…]} ; `appliquer` (cartoon.pose) joue cette émotion sur nos personnages, celui qui parle ET celui
qui écoute, seulement si rien de fort n'est déjà joué (l'original nuance, il ne casse jamais le jeu choisi). JEU_DESSIN=0 pour couper."""
import os

EMOS = {"joie": "joie", "rire": "rire", "colere": "colere", "cri": "cri", "triste": "pleurs", "peur": "panique", "surprise": "choc",
        "choc": "choc", "gene": "gene", "sceptique": "sceptique", "degout": "sceptique", "ennui": "blase", "fier": "fier", "amour": "amour",
        "neutre": None}

QUESTION = """Voici {n} images tirées d'un dessin animé TikTok (un dialogue), numérotées de 0 à {m} dans l'ordre. Pour CHAQUE image, dis
qui parle (le personnage de gauche ou de droite : bouche ouverte, il s'adresse à l'autre) et l'expression du visage de chaque
personnage. Émotions possibles : joie, rire, colere, cri, triste, peur, surprise, gene, sceptique, degout, ennui, fier, amour, neutre.
Force : 1 (légère) à 3 (très forte). Réponds en JSON : {{"images": [{{"i": 0, "parle": "gauche|droite|?",
"gauche": {{"emotion": "...", "force": 1}}, "droite": {{"emotion": "...", "force": 1}}}}, ...]}}. S'il n'y a qu'un personnage, mets
"droite" à null."""


def actif(): return os.environ.get("JEU_DESSIN", "1") != "0"


def choisir_repliques(reps, n=14):
    ok = [(k, r) for k, r in enumerate(reps) if r.get("p") not in (None, "narrateur") and not r.get("_hors_champ")
          and r.get("_deb") is not None and float(r["_fin"]) - float(r["_deb"]) >= 0.8]
    if len(ok) <= n: return ok
    pas = len(ok) / n
    return [ok[int(j * pas)] for j in range(n)]


def interpreter(rep, choisies):
    """Réponse de Gemini -> {rôle: [[deb, fin, émotion, force]]}. Le côté de chaque rôle = vote « qui parle »."""
    images = (rep or {}).get("images") if isinstance(rep, dict) else None
    if not isinstance(images, list): return {}
    vote = {}                                                              # (rôle, côté) -> voix
    for x in images:
        try: i = int(x.get("i")); cote = str(x.get("parle") or "").lower()
        except (AttributeError, TypeError, ValueError): continue
        if 0 <= i < len(choisies) and cote in ("gauche", "droite"):
            role = choisies[i][1]["p"]; vote[(role, cote)] = vote.get((role, cote), 0) + 1
    roles = sorted({r["p"] for _, r in choisies})
    if len(roles) != 2: return {}
    a, b = roles
    direct = vote.get((a, "gauche"), 0) + vote.get((b, "droite"), 0)
    inverse = vote.get((a, "droite"), 0) + vote.get((b, "gauche"), 0)
    if max(direct, inverse) < 3 or max(direct, inverse) < 2 * min(direct, inverse): return {}   # côtés pas nets : rien
    cote_de = {a: "gauche", b: "droite"} if direct >= inverse else {a: "droite", b: "gauche"}
    out = {}
    for x in images:
        try: i = int(x.get("i"))
        except (AttributeError, TypeError, ValueError): continue
        if not 0 <= i < len(choisies): continue
        r = choisies[i][1]; deb, fin = float(r["_deb"]), float(r["_fin"])
        for role, cote in cote_de.items():
            e = x.get(cote) if isinstance(x.get(cote), dict) else None
            emo = EMOS.get(str((e or {}).get("emotion") or "").lower().strip())
            if not emo: continue
            try: force = max(1, min(3, int((e or {}).get("force") or 1)))
            except (TypeError, ValueError): force = 1
            out.setdefault(role, []).append([round(deb, 2), round(fin, 2), emo, force])
    return out


def extraire(video, reps, journal=print, regarder=None):
    if not actif() or not video or not os.path.exists(video): return {}
    choisies = choisir_repliques(reps)
    if len(choisies) < 4: return {}
    import cv2
    cap = cv2.VideoCapture(video); ims = []
    for _, r in choisies:
        cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * (float(r["_deb"]) + float(r["_fin"])) / 2)
        ok, im = cap.read()
        if not ok: cap.release(); return {}
        ims.append(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
    cap.release()
    q = QUESTION.format(n=len(ims), m=len(ims) - 1)
    rep = (regarder or (lambda ims_, q_: __import__("fiche_tournage")._gemini_images(ims_, q_, timeout=120)))(ims, q)
    out = interpreter(rep, choisies)
    if out: journal(f"  jeu du dessin animé lu par Gemini : {', '.join(f'{r} {len(l)} expression(s)' for r, l in out.items())}")
    else: journal("  jeu du dessin animé : Gemini n'a pas pu lire les expressions (rien de recopié)")
    return out


def appliquer(p, jeu, role, tm, parle):
    """Émotion vue dans le dessin animé d'origine, si rien de fort n'est déjà joué (modifie p)."""
    if not jeu or p.get("emo") not in (None, "neutre", "ecoute"): return
    for deb, fin, emo, force in jeu.get(role) or ():
        if deb - 0.2 <= tm <= fin + 0.2:
            if parle or force >= 2 or emo in ("joie", "rire", "sceptique", "gene", "choc"):   # celui qui écoute : réactions nettes seulement
                p["emo"] = emo
            return
