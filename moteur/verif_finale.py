"""Contrôle de la VIDÉO FINIE (demande de l'auteur, 31 octobre 2026, points 1, 6, 7, 8 et 9) : le dernier poste de l'équipe
regarde et écoute la vidéo telle qu'elle sera publiée.

  1. Synchro des bouches : pendant chaque réplique, c'est le personnage qui parle qui doit bouger (bouche, tête), pas celui qui
     écoute ; décalage général entre le son et l'image mesuré (mouvement des personnages contre force de la voix) et corrigé
     s'il dépasse 0,1 s (le son est recalé, l'image ne bouge pas).
  6. Liste de contrôle par l'IA (Gemini d'abord, gratuit) : une image toutes les 2 s, questions fixes (nombre de personnages,
     objet sans raison, voix et personnage du même genre, décor cohérent, sous-titre qui correspond…).
  7. Sous-titres vérifiés à l'oreille : le son de la vidéo finie est retranscrit et comparé au texte affiché, réplique par
     réplique (mot faux, sous-titre qui ne correspond pas, voix entendue sans sous-titre).
  8. Technique image par image : sauts d'image hors des coupes prévues, clignotements, personnages coupés ou qui se traversent
     (contrôle image du dessin).
  9. Feu rouge : tout défaut que le robot n'a pas pu corriger devient un point « ⚠️ à vérifier » (moment + problème) affiché sur le
     site ; la vidéo n'est publiée qu'après validation de l'auteur.
VERIF_FINALE=0 pour couper."""
import json, os, re, subprocess, tempfile, difflib
import numpy as np

L, H_ = 270, 480                                                           # images lues en petit (vitesse)
NATUREL = 0.05                                                             # retard normal du mouvement sur la voix (mesuré sur nos vidéos)


def journal(m): print(m, flush=True)


def _defaut(t, poste, quoi, grave=True): return {"t": None if t is None else round(float(t), 1), "poste": poste, "quoi": str(quoi)[:180], "grave": bool(grave)}


def _son(video, sr=16000):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0, sr


def _images(video):
    import cv2
    cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; out = []
    while True:
        ok, f = cap.read()
        if not ok: break
        out.append(cv2.cvtColor(cv2.resize(f, (L, H_), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.int16))
    return out, float(fps)


# ------------------------------------------------------------------ 1. synchro des bouches
def synchro(video, R, fr=None, fps=None, son=None):
    """Défauts de synchro + décalage son / image mesuré (s, > 0 : l'image est en retard sur le son)."""
    if fr is None: fr, fps = _images(video)
    if son is None: son = _son(video)
    sig, sr = son; out = []
    if not fr or not R.get("ph") or not R.get("xs"): return out, 0.0
    W0, H0 = 1080, 1920; k = L / W0
    def boite(sc, x):
        ty = (R.get("tetes_y") or {}).get(sc)
        y0, y1 = (int((ty - 160) * k), int((ty + 260) * k)) if ty else (int(H_ * 0.22), int(H_ * 0.62))
        return max(0, y0), min(H_, y1), max(0, int((x - 130) * k)), min(L, int((x + 130) * k))
    mouv = np.zeros(len(fr)); voix = np.zeros(len(fr))
    env = np.sqrt(np.convolve(sig ** 2, np.ones(int(sr / fps)) / int(sr / fps), "same")) if len(sig) else np.zeros(1)
    for i in range(len(fr)): voix[i] = env[min(len(env) - 1, int(i / fps * sr))]
    for q in R["ph"]:
        sc, p = q.get("scene"), q.get("p"); xs = (R["xs"].get(sc) or R["xs"].get(str(sc)) or {})
        if p not in xs or q.get("plan") not in (None, "large") or float(q["fin"]) - float(q["deb"]) < 0.5: continue
        a, b = int(float(q["deb"]) * fps) + 1, min(len(fr), int(float(q["fin"]) * fps))
        parle = boite(sc, xs[p]); autres = [boite(sc, x) for r, x in xs.items() if r != p and abs(x - xs[p]) > 200]
        S = A = 0.0
        for i in range(a, b):
            d = np.abs(fr[i] - fr[i - 1]) > 12
            if d.mean() > 0.08: continue                                   # changement de plan
            y0, y1, x0, x1 = parle; S += float(d[y0:y1, x0:x1].sum())
            for (y0, y1, x0, x1) in autres: A += float(d[y0:y1, x0:x1].sum()) / len(autres)
        if A > 1.5 * S + 40 and (b - a) > fps * 0.5:
            out.append(_defaut(q["deb"], "synchro", f"pendant la réplique de {p} (« {str(q.get('texte'))[:40]} »), c'est un autre personnage qui bouge"))
    for i in range(1, len(fr)):                                            # mouvement de tous les personnages (têtes, bustes)
        d = np.abs(fr[i] - fr[i - 1]) > 12
        if d.mean() <= 0.08: mouv[i] = float(d[int(H_ * 0.2):int(H_ * 0.65)].sum())
    decalage = 0.0
    if mouv.sum() > 0 and voix.std() > 0:
        m = (mouv - mouv.mean()) / (mouv.std() + 1e-9); v = (voix - voix.mean()) / (voix.std() + 1e-9)
        lags = range(-int(0.4 * fps), int(0.4 * fps) + 1)
        c = {l: float(np.mean(m[max(0, l):len(m) + min(0, l)] * v[max(0, -l):len(v) - max(0, l)])) for l in lags}
        best = max(c, key=c.get); nat = round(NATUREL * fps)                # la bouche suit naturellement la voix d'environ 0,05 s
        if c[best] > 0.12 and c[best] > 1.2 * max(c.get(nat, 0.0), 1e-6) and abs(best - nat) / fps >= 0.12: decalage = round((best - nat) / fps, 2)
    return out, decalage


def recaler(video, decalage):
    """Recale le son de decalage secondes (> 0 : l'image est en retard -> le son part plus tard). Renvoie True si fait."""
    tmp = video + ".recale.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-itsoffset", f"{decalage:.3f}", "-i", video, "-map", "0:v", "-map", "1:a",
                        "-c", "copy", "-shortest", tmp], capture_output=True)
    if r.returncode or not os.path.exists(tmp): return False
    os.replace(tmp, video); return True


# ------------------------------------------------------------------ 7. sous-titres vérifiés à l'oreille
def _nu(t): return [w for w in re.sub(r"[^\w'’ -]", " ", str(t).lower()).replace("’", "'").split() if w]


def sous_titres(video, R, son=None):
    """Le son de la vidéo finie est retranscrit et comparé au texte affiché de chaque réplique."""
    if son is None: son = _son(video)
    sig, sr = son; out = []
    tmp = tempfile.mkdtemp(); wav = os.path.join(tmp, "fin.wav")
    import wave
    with wave.open(wav, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes())
    import ecoute
    mots = ecoute.groq(wav)
    if not mots:
        import doublage
        from scipy.signal import resample_poly
        mots = doublage.whisper_local(resample_poly(sig, 441, 320).astype(np.float32))   # 16 kHz -> 22,05 kHz attendu
    if not mots: return out, None
    ph = R.get("ph") or []; vus = set(); scores = []
    for q in ph:
        if not q.get("texte") or q.get("p") == "narrateur": continue
        a, b = float(q["deb"]) - 0.35, float(q["fin"]) + 0.35
        idx = [i for i, m in enumerate(mots) if m["s"] >= a and m["e"] <= b + 0.2]
        vus.update(idx)
        att, ent = _nu(q["texte"]), _nu(" ".join(mots[i]["w"] for i in idx))
        if len(att) < 3: continue
        r = difflib.SequenceMatcher(None, att, ent).ratio(); scores.append(r)
        if r < 0.5: out.append(_defaut(q["deb"], "sous-titres", f"sous-titre « {str(q['texte'])[:50]} » mais on entend « {' '.join(ent)[:50]} »"))
    seuls, bloc = [], []
    for i, m in enumerate(mots):                                           # voix entendue sans sous-titre (3 mots ou plus d'affilée)
        if i in vus or m["s"] > (R.get("total") or 1e9) - 0.5:
            if len(bloc) >= 3: seuls.append(bloc)
            bloc = []; continue
        bloc.append(m)
    if len(bloc) >= 3: seuls.append(bloc)
    for bl in seuls[:4]: out.append(_defaut(bl[0]["s"], "sous-titres", f"on entend « {' '.join(m['w'] for m in bl)[:50]} » sans sous-titre", grave=False))
    return out, (round(float(np.mean(scores)), 2) if scores else None)


# ------------------------------------------------------------------ 8. technique image par image
def technique(video, R, fr=None, fps=None):
    if fr is None: fr, fps = _images(video)
    out = []
    if not fr: return out
    prevus = [float(x.get("t0") or 0) for x in R.get("plans") or []] + [t for tr in R.get("transitions") or [] for t in tr]
    fin = len(fr) / fps
    lum = np.array([float(f.mean()) for f in fr])
    sauts = []
    for i in range(1, len(fr)):
        t = i / fps
        if t > fin - 2.0 or t < 0.2: continue                              # début (titre) et fin en boucle : voulus
        d = float(np.mean(np.abs(fr[i] - fr[i - 1]) > 30))
        if d > 0.35 and not any(abs(t - p) < 0.25 for p in prevus): sauts.append(t)
    for t in sauts[:4]: out.append(_defaut(t, "technique", "saut d'image hors d'une coupe prévue"))
    clign = [i / fps for i in range(1, len(lum) - 1) if abs(lum[i] - lum[i - 1]) > 14 and abs(lum[i + 1] - lum[i]) > 14
             and np.sign(lum[i] - lum[i - 1]) != np.sign(lum[i + 1] - lum[i]) and i / fps < fin - 1.0]
    for t in clign[:3]: out.append(_defaut(t, "technique", "clignotement de l'image"))
    for d in (R.get("defauts_image") or [])[:6]:                           # contrôle image du dessin (têtes coupées, chevauchements…)
        out.append(_defaut(d.get("t"), "technique", f"{d.get('type', 'défaut').replace('_', ' ')} ({d.get('role', '')})", grave=False))
    return out


# ------------------------------------------------------------------ 6. liste de contrôle par l'IA
QUESTIONS = """Tu es contrôleur qualité. Voici des images d'une vidéo TikTok animée (style croquis, volontairement simple), une toutes les
2 secondes, numérotées (carré rouge). Ce que la vidéo doit montrer :
{contexte}
Pour CHAQUE image, réponds à ces questions et signale seulement ce qui ne va pas :
1. Le nombre de personnages principaux à l'image est-il bon ({nb} qui se parlent, plus les proches muets éventuels) ?
2. Un objet tenu ou un accessoire n'a-t-il rien à faire là (téléphone alors que personne n'appelle…) ?
3. Le personnage qui parle (voir le sous-titre attendu) a-t-il l'allure de sa voix (homme / femme, âge) ?
4. Le décor est-il le même d'une image à l'autre et cohérent avec l'histoire ?
5. Le sous-titre affiché correspond-il au texte attendu à ce moment ?
6. Un personnage est-il coupé, déformé, flottant, ou deux personnages se traversent-ils ?
Ne signale ni le style simple, ni les textes humoristiques du décor, ni les sous-titres qui n'affichent qu'une partie de la phrase.
Rends ta réponse avec l'outil controle : "defauts" = liste (image n°, question n°, problème)."""
OUTIL = {"name": "controle", "description": "Défauts relevés image par image.",
         "input_schema": {"type": "object", "properties": {"defauts": {"type": "array", "items": {"type": "object", "properties": {
             "image": {"type": "integer"}, "question": {"type": "integer"}, "probleme": {"type": "string"}}, "required": ["image", "probleme"]}}},
             "required": ["defauts"]}}


def liste_ia(video, sk, R):
    import base64, controle, ecrire, reseau
    if not reseau.ia_disponible(): return []
    total = float(R.get("total") or 0) or 60.0
    instants = [round(t, 1) for t in np.arange(1.0, total - 0.5, 2.0)][:32]
    ph = R.get("ph") or []
    noms = {"presentateur": "Jojo", "invite": "Kévin", "envoyee": "Lila"}
    fiches = R.get("fiches") or {}
    roles = sorted({q["p"] for q in ph if q.get("p") != "narrateur"})
    ctx = ["Personnages : " + " ; ".join(f"{noms.get(r, r)} ({'femme' if (fiches.get(r) or {}).get('genre') == 'f' else 'homme'}, "
                                        f"{(fiches.get(r) or {}).get('age', '?')} ans)" for r in roles),
           "Situation : " + str((sk.get("doublage") or {}).get("contexte") or sk.get("sujet") or "")[:200],
           "Lieu : " + ", ".join(str(l) for l in (R.get("lieux") or [])[:2])]
    for k, t in enumerate(instants):
        q = next((q for q in ph if float(q["deb"]) - 0.1 <= t <= float(q["fin"]) + 0.3), None)
        ctx.append(f"image {k + 1} ({t:.0f} s) : " + (f"{noms.get(q['p'], q['p'])} parle — « {str(q.get('texte'))[:70]} »" if q else "personne ne parle"))
    try:
        contenu = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(p).decode()}}
                   for p in controle.planches(video, instants)]
        contenu.append({"type": "text", "text": QUESTIONS.format(contexte="\n".join(ctx), nb=len(roles))})
        r = ecrire._appel(reseau.claude(), None, [{"role": "user", "content": contenu}], OUTIL, max_tokens=2500)
    except Exception as e:
        journal(f"  liste de contrôle par l'IA impossible ({str(e)[:120]})"); return []
    out = []
    for d in ecrire._liste(r.get("defauts")):
        try:
            n = int(d.get("image")) - 1
            if 0 <= n < len(instants): out.append(_defaut(instants[n], "contrôle IA", str(d.get("probleme") or ""), grave=False))
        except (AttributeError, TypeError, ValueError): pass
    return out[:10]


# ------------------------------------------------------------------ ensemble
def verifier(video, sk, R):
    """Tous les contrôles de la vidéo finie. Renvoie la liste des points « à vérifier » (moment, poste, problème)."""
    if os.environ.get("VERIF_FINALE", "1") == "0" or not R or not os.path.exists(video): return []
    points = []
    try:
        fr, fps = _images(video); son = _son(video)
        d1, dec = synchro(video, R, fr, fps, son)
        if dec and recaler(video, dec):
            journal(f"  [vidéo finie · synchro] son recalé de {dec:+.2f} s sur l'image"); son = _son(video)
        points += d1
        journal(f"  [vidéo finie · synchro] {'✔' if not d1 else '✘'} bouches du bon personnage" + (f" : {len(d1)} réplique(s) à revoir" if d1 else ""))
        d8 = technique(video, R, fr, fps); points += d8
        journal(f"  [vidéo finie · technique] {'✔' if not [d for d in d8 if d['grave']] else '✘'} sauts, clignotements, personnages ({len(d8)} remarque(s))")
        del fr
    except Exception as e: journal(f"  contrôle synchro / technique impossible ({str(e)[:120]})")
    try:
        d7, accord = sous_titres(video, R); points += d7
        journal(f"  [vidéo finie · sous-titres] {'✔' if not [d for d in d7 if d['grave']] else '✘'} sous-titres vérifiés à l'oreille"
                + (f" (accord {round(100 * accord)} %)" if accord is not None else ""))
    except Exception as e: journal(f"  contrôle des sous-titres impossible ({str(e)[:120]})")
    try:
        d6 = liste_ia(video, sk, R); points += d6
        journal(f"  [vidéo finie · contrôle IA] {len(d6)} remarque(s)")
    except Exception as e: journal(f"  liste de contrôle par l'IA impossible ({str(e)[:120]})")
    for l in sk.get("equipe") or []:                                       # défauts de l'équipe que personne n'a pu corriger
        if l.get("revoir"): points.append(_defaut(None, l.get("poste", "équipe"), f"{l.get('controle')} : {l.get('detail')}"))
    points.sort(key=lambda d: (not d["grave"], d["t"] if d["t"] is not None else -1))
    journal(f"Contrôle de la vidéo finie : {len(points)} point(s) à vérifier" + (" — " + " ; ".join(f"{d['t']} s {d['quoi'][:60]}" for d in points[:6]) if points else ""))
    return points[:20]
