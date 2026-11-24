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
            out.append(dict(_defaut(q["deb"], "synchro", f"pendant la réplique de {p} (« {str(q.get('texte'))[:40]} »), c'est un autre personnage qui bouge"), i=q.get("i")))
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


BOUCHE_MUETTE = 0.75


def bouches_muettes(R, fr, fps, mesures=None):
    """Contrôle final « bouche qui bouge quand on se tait » (choix de l'auteur du 23 novembre 2026, idée 13). Pour chaque personnage,
    le mouvement dans le bas de son visage (bouche, menton ; centre de la tête R["tetes_y"], place R["xs"]) est comparé pendant SES
    répliques (il parle) et pendant les répliques des autres (il écoute, plan large, sans changement de plan). Une bouche qui bouge
    presque autant en écoutant qu'en parlant (≥ 75 %) = la bouche de celui qui se tait est animée sur la voix de l'autre -> point grave,
    avec les répliques où c'est le plus fort. mesures : dict rempli avec les chiffres (essais). BOUCHE_MUETTE=0 pour couper."""
    if os.environ.get("BOUCHE_MUETTE", "1") == "0" or not fr or not R.get("ph") or not R.get("xs"): return []
    k = L / 1080.0; out = []
    def bouche(sc, x):
        ty = (R.get("tetes_y") or {}).get(sc) or (R.get("tetes_y") or {}).get(str(sc))
        if not ty: return None
        y0, y1 = int((ty + 15) * k), int((ty + 115) * k)
        return max(0, y0), min(H_, y1), max(0, int((x - 75) * k)), min(L, int((x + 75) * k))
    stats = {}                                                             # rôle -> {"parle": [somme, n], "ecoute": [somme, n], "pires": []}
    for q in R["ph"]:
        sc, p = q.get("scene"), q.get("p"); xs = (R["xs"].get(sc) or R["xs"].get(str(sc)) or {})
        if p not in xs or q.get("plan") not in (None, "large") or float(q["fin"]) - float(q["deb"]) < 0.5: continue
        a, b = int(float(q["deb"]) * fps) + 1, min(len(fr), int(float(q["fin"]) * fps))
        for r, x in xs.items():
            bx = bouche(sc, x)
            if not bx: continue
            y0, y1, x0, x1 = bx; S, n = 0.0, 0
            for i in range(a, b):
                d = np.abs(fr[i] - fr[i - 1]) > 12
                if d.mean() > 0.08: continue                               # changement de plan
                S += float(d[y0:y1, x0:x1].mean()); n += 1
            if not n: continue
            e = stats.setdefault(r, {"parle": [0.0, 0], "ecoute": [0.0, 0], "pires": []})
            cle = "parle" if r == p else "ecoute"
            e[cle][0] += S; e[cle][1] += n
            if cle == "ecoute": e["pires"].append((S / n, q))
    for r, e in stats.items():
        if e["parle"][1] < fps or e["ecoute"][1] < 2 * fps: continue      # trop peu d'images pour juger
        parle, ecoute = e["parle"][0] / e["parle"][1], e["ecoute"][0] / e["ecoute"][1]
        if mesures is not None: mesures[r] = (round(parle, 4), round(ecoute, 4))
        if parle < 0.004: continue                                         # bouche presque immobile même en parlant : rien à comparer
        if ecoute >= BOUCHE_MUETTE * parle:
            pires = sorted(e["pires"], key=lambda x: -x[0])[:3]
            q0 = pires[0][1] if pires else {}
            out.append(_defaut(q0.get("deb"), "bouches", f"la bouche {DE_ROLES.get(r, 'de ' + str(r))} bouge alors qu'il / elle se tait ({round(100 * ecoute / parle)} % "
                               f"du mouvement de quand il / elle parle), par ex. pendant « {str(q0.get('texte') or '')[:40]} »"))
    return out


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
    import locuteurs
    mots = locuteurs.sans_hallucinations(mots)                             # « Sous-titrage Société Radio-Canada » sur un silence…
    ph = R.get("ph") or []; vus = set(); scores = []; doutes = []
    for q in ph:
        if not q.get("texte") or q.get("p") == "narrateur": continue
        a, b = float(q["deb"]) - 0.35, float(q["fin"]) + 0.35
        idx = [i for i, m in enumerate(mots) if m["s"] >= a and m["e"] <= b + 0.2]
        vus.update(idx)
        att, ent = _nu(q["texte"]), _nu(" ".join(mots[i]["w"] for i in idx))
        if len(att) < 3: continue
        r = difflib.SequenceMatcher(None, att, ent).ratio(); scores.append(r)
        if r < 0.5: doutes.append((q, ent, r))
    ecoute_g = {}
    if doutes:                                                             # Gemini réécoute les seules répliques en désaccord (audit, idée 2) :
        try: ecoute_g = __import__("video_ia").ecouter(video, [(float(q["deb"]) - 0.3, float(q["fin"]) + 0.3) for q, _, _ in doutes]) or {}
        except Exception: ecoute_g = {}
    for k, (q, ent, r) in enumerate(doutes):
        g = ecoute_g.get(k)
        if g is not None and difflib.SequenceMatcher(None, _nu(q["texte"]), _nu(g)).ratio() >= 0.6:
            journal(f"  sous-titre « {str(q['texte'])[:40]} » confirmé par Gemini (la 2e transcription s'était trompée)"); continue
        sur = g is not None and len(_nu(g)) >= 3                           # Gemini entend lui aussi autre chose : défaut sûr
        out.append(_defaut(q["deb"], "sous-titres", f"sous-titre « {str(q['texte'])[:50]} » mais on entend « {(g if sur else ' '.join(ent))[:50]} »",
                           grave=(sur or g is None) and len(ent) >= 3 and r < 0.25))   # (une 2e écoute qui entend un peu autre chose n'est pas une erreur sûre)
    out += controle_karaoke(ph, mots)                                      # le mot en jaune = le mot entendu, au même instant
    seuls, bloc = [], []
    for i, m in enumerate(mots):                                           # voix entendue sans sous-titre (3 mots ou plus d'affilée)
        if i in vus or m["s"] > (R.get("total") or 1e9) - 0.5:
            if len(bloc) >= 3: seuls.append(bloc)
            bloc = []; continue
        bloc.append(m)
    if len(bloc) >= 3: seuls.append(bloc)
    for bl in seuls[:4]: out.append(_defaut(bl[0]["s"], "sous-titres", f"on entend « {' '.join(m['w'] for m in bl)[:50]} » sans sous-titre", grave=False))
    return out, (round(float(np.mean(scores)), 2) if scores else None)


def controle_karaoke(ph, mots, seuil=0.3):
    """Vrai contrôle du karaoké (demande de l'auteur du 15 novembre) : le son de la vidéo FINIE est réécouté ; chaque mot surligné est
    retrouvé parmi les mots entendus (même mot, dans la réplique) et on mesure l'écart entre l'instant où il passe en jaune et
    l'instant où on l'entend. Écart médian > 0,3 s sur la vidéo = point grave (« karaoké décalé ») ; sur une seule réplique = remarque."""
    import jt
    out, tous = [], []
    for q in ph:
        k = q.get("kara")
        if not k or not q.get("texte"): continue
        aff = [jt._nu_mot(w) for w in str(q["texte"]).split()]
        ent = [(jt._nu_mot(m["w"]), float(m["s"])) for m in mots if float(q["deb"]) - 0.5 <= float(m["s"]) <= float(q["fin"]) + 0.5]
        ecarts = []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, aff, [w for w, _ in ent], autojunk=False).get_opcodes():
            if op != "equal": continue
            for d in range(i2 - i1):
                if aff[i1 + d] and i1 + d < len(k): ecarts.append(abs(float(k[i1 + d][0]) - ent[j1 + d][1]))
        if len(ecarts) >= 3:
            med = float(np.median(ecarts)); tous += ecarts
            if med > seuil + 0.1: out.append(_defaut(q["deb"], "sous-titres", f"karaoké décalé de {med:.2f} s sur « {str(q['texte'])[:40]} »", grave=False))
    if len(tous) >= 8 and float(np.median(tous)) > seuil:
        out.append(_defaut(None, "sous-titres", f"karaoké décalé de {float(np.median(tous)):.2f} s en moyenne (mot en jaune ≠ mot entendu)"))
    elif tous: journal(f"  karaoké contrôlé à l'oreille : {len(tous)} mots, écart médian {float(np.median(tous)):.2f} s")
    return out


# ------------------------------------------------------------------ 8. technique image par image
def technique(video, R, fr=None, fps=None):
    if fr is None: fr, fps = _images(video)
    out = []
    if not fr: return out
    prevus = [float(x.get("t0") or 0) for x in R.get("plans") or []] + [t for tr in R.get("transitions") or [] for t in tr]
    if R.get("fin_carte"): prevus.append(float(R["fin_carte"]))           # carton de fin « Abonne-toi » : voulu (signalé à tort jusqu'ici)
    fin = len(fr) / fps
    lum = np.array([float(f.mean()) for f in fr])
    sauts = []
    for i in range(1, len(fr)):
        t = i / fps
        if t > fin - 3.6 or t < 0.2: continue                              # début (titre), carton de fin et fin en boucle : voulus
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


# Tri des remarques de l'IA de contrôle (audit du 17 novembre 2026 : 132 remarques relues, presque toutes fausses ou de goût).
_IA_FAUSSES = [
    r"expression|posture|émotion|emotion|attitude|pas assez|manque d|trop (neutre|calme|jeune|mature|enfantin)|devrait (montrer|avoir|tenir)",  # goût
    r"sous-titre|subtitle|texte (affiché|attendu|est)|le texte|mot affiché|écrit à l'écran|titre|pov",   # sous-titres : vérifiés à l'oreille
    r"(semble|est|ce qui est|cela semble|peut être) (correct|cohérent|acceptable|normal)|personne ne parle|aucun (personnage|texte|sous-titre|problème)",
    r"narrateur|voix off|silence|pause",
    r"m[êe]me apparence|se ressemblent|identiques?|style (simple|cohérent)|distinguer",                  # style croquis voulu
    r"\b(jojo|k[ée]vin|lila)\b|allure|âge|ans\b|une femme|un homme|féminin|masculin",                  # âge / genre : décidés par le vote des voix
    r"il manque (le|les|un|des) personnage|personnages? (absent|manqu)|devraient être présents|arrière-plan",   # personnes dont on parle
    r"question \d|non validée|décalés?|flott|décor change|téléphone",
]
_IA_GRAVES = r"dupliqu|en double|en trop|deux têtes|coupée? en deux|tête coupée|déform|membres? (en trop|manquant)|bras (dupliqu|en trop)"


def trier_ia(pb, fiches=None):
    """Remarque de l'IA de contrôle -> True (vrai défaut du dessin : bras en double, tête coupée…), False (remarque légère, gardée
    au journal), None (fausse alerte connue : sous-titres, goût, âge / genre, personnes absentes, animal voulu… écartée)."""
    if re.search(_IA_GRAVES, pb, re.I): return True
    if any(re.search(x, pb, re.I) for x in _IA_FAUSSES): return None
    if any((F or {}).get("espece") for F in (fiches or {}).values()) and re.search(r"\b(chat|chien|animal|animaux|lapin|souris|oiseau|poisson|objet)", pb, re.I): return None
    return False


def liste_ia(video, sk, R):
    import base64, controle, ecrire, reseau
    if not reseau.ia_disponible(): return []
    total = float(R.get("total") or 0) or 60.0
    instants = [round(t, 1) for t in np.arange(1.0, total - 0.5, 2.0)][:32]
    ph = R.get("ph") or []
    fiches = R.get("fiches") or {}
    roles = sorted({q["p"] for q in ph if q.get("p") != "narrateur"})
    noms = {r: f"le personnage {k + 1}" for k, r in enumerate(roles)}       # (plus de prénoms internes : « Kévin » faisait croire à un homme)
    def qui(r):
        F = fiches.get(r) or {}
        if F.get("espece"): return f"{noms[r]} (un {F['espece']} qui parle : VOULU)"
        return f"{noms[r]} ({'femme' if F.get('genre') == 'f' else 'homme'}, {F.get('age', '?')} ans)"
    ctx = ["Personnages : " + " ; ".join(qui(r) for r in roles),
           "Situation : " + str((sk.get("doublage") or {}).get("contexte") or sk.get("sujet") or "")[:200],
           "Lieu : " + ", ".join(str(l) for l in (R.get("lieux") or [])[:2])]
    for k, t in enumerate(instants):
        q = next((q for q in ph if float(q["deb"]) - 0.1 <= t <= float(q["fin"]) + 0.3), None)
        ctx.append(f"image {k + 1} ({t:.0f} s) : " + (f"{noms.get(q['p'], q['p'])} parle — « {str(q.get('texte'))[:70]} »" if q else "personne ne parle"))
    try:
        contenu = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(p).decode()}}
                   for p in controle.planches(video, instants)]
        contenu.append({"type": "text", "text": QUESTIONS.format(contexte="\n".join(ctx), nb=len(roles))})
        cl = reseau.claude()
        try: r = ecrire._appel(cl, None, [{"role": "user", "content": contenu}], OUTIL, max_tokens=2500)
        except Exception as e1:                                            # réponse vide ou illisible (registre des pannes du 19 novembre) :
            ia1 = str(getattr(cl, "dernier", "") or "")                    # une 2e IA regarde les mêmes images
            journal(f"  liste de contrôle : réponse inexploitable de {ia1 or 'l\'IA'} ({str(e1)[:60]}), 2e essai avec une autre IA")
            r = ecrire._appel(reseau.claude(exclure=(ia1,) if ia1 else ()), None, [{"role": "user", "content": contenu}], OUTIL, max_tokens=2500)
    except Exception as e:
        journal(f"  liste de contrôle par l'IA impossible ({str(e)[:120]})"); return []
    out = []
    for d in ecrire._liste(r.get("defauts")):
        try:
            n = int(d.get("image")) - 1
            pb = str(d.get("probleme") or "")
            g = trier_ia(pb, fiches)
            if g is None: continue
            if 0 <= n < len(instants): out.append(_defaut(instants[n], "contrôle IA", pb, grave=g))
        except (AttributeError, TypeError, ValueError): pass
    return out[:6]


# ------------------------------------------------------------------ ensemble
def verifier(video, sk, R):
    """Tous les contrôles de la vidéo finie. Renvoie la liste des points « à vérifier » (moment, poste, problème)."""
    if os.environ.get("VERIF_FINALE", "1") == "0" or not R or not os.path.exists(video): return []
    points = []; sautes = []; sk["_controles_sautes"] = sautes                # (note de confiance honnête, 23 novembre)
    try:
        fr, fps = _images(video); son = _son(video)
        d1, dec = synchro(video, R, fr, fps, son)
        if dec:                                                            # le son et l'image sortent du même calcul : un vrai décalage est
            journal(f"  [vidéo finie · synchro] décalage mesuré {dec:+.2f} s (mesure seulement : le son n'est jamais déplacé)")   # impossible ;
            # le 31 octobre, un « recalage » de +0,28 s sur une vidéo juste avait créé le décalage : on ne touche plus au son
        points += d1
        journal(f"  [vidéo finie · synchro] {'✔' if not d1 else '✘'} bouches du bon personnage" + (f" : {len(d1)} réplique(s) à revoir" if d1 else ""))
        d11 = bouches_muettes(R, fr, fps); points += d11                  # (23 novembre) bouche qui bouge quand on se tait
        journal(f"  [vidéo finie · bouches] {'✔' if not d11 else '✘'} bouche immobile quand le personnage se tait" + (f" : {d11[0]['quoi']}" if d11 else ""))
        d8 = technique(video, R, fr, fps); points += d8
        journal(f"  [vidéo finie · technique] {'✔' if not [d for d in d8 if d['grave']] else '✘'} sauts, clignotements, personnages ({len(d8)} remarque(s))")
        del fr
    except Exception as e: journal(f"  contrôle synchro / technique impossible ({str(e)[:120]})"); sautes.append("bouches et technique")
    try:
        d7, accord = sous_titres(video, R); points += d7
        journal(f"  [vidéo finie · sous-titres] {'✔' if not [d for d in d7 if d['grave']] else '✘'} sous-titres vérifiés à l'oreille"
                + (f" (accord {round(100 * accord)} %)" if accord is not None else ""))
    except Exception as e: journal(f"  contrôle des sous-titres impossible ({str(e)[:120]})"); sautes.append("sous-titres")
    try:
        d6 = liste_ia(video, sk, R); points += d6
        journal(f"  [vidéo finie · contrôle IA] {len(d6)} remarque(s)")
    except Exception as e: journal(f"  liste de contrôle par l'IA impossible ({str(e)[:120]})"); sautes.append("contrôle par l'IA")
    try:                                                                   # 3e contrôle de la vidéo finie (20 novembre, idée 25) : fidèle à l'audio ?
        import fiche_tournage
        pbs = fiche_tournage.fidelite(video, sk, R)
        if pbs is None and os.environ.get("FIDELITE", "1") != "0": sautes.append("fidélité à l'audio (Gemini n'a pas répondu)")
        if pbs is not None:
            for x in pbs:
                d_ = _defaut(x["t"], "fidélité à l'audio", x["probleme"], grave=True)
                if x.get("champ"): d_["correction"] = [{"champ": x["champ"], "valeur": x.get("valeur"), "raison": x["probleme"][:100]}]
                points.append(d_)
            journal(f"  [vidéo finie · fidélité à l'audio] {'✔' if not pbs else '✘'} Gemini a regardé et écouté la vidéo finie" + (f" : {len(pbs)} écart(s)" if pbs else ""))
    except Exception as e: journal(f"  contrôle de fidélité à l'audio impossible ({str(e)[:120]})"); sautes.append("fidélité à l'audio")
    try:                                                                   # voix et dessin (21 novembre) : la hauteur de chaque réplique
        d9 = voix_dessin(video, sk); points += d9                          # dans la vidéo finie, et homme / femme dessinés
        journal(f"  [vidéo finie · voix et dessin] {'✔' if not d9 else '✘'} chaque réplique sur la bonne voix, homme / femme d'après la voix"
                + (f" : {len(d9)} écart(s)" if d9 else ""))
    except Exception as e: journal(f"  contrôle voix et dessin impossible ({str(e)[:120]})"); sautes.append("voix et dessin")
    try:                                                                   # attribution (22 novembre) : l'IMAGE de l'original
        d10 = attribution_image(sk); points += d10                         # contre les répliques de la vidéo finie
        journal(f"  [vidéo finie · attribution] {'✔' if not d10 else '✘'} qui dit chaque phrase, comparé à l'image de l'original"
                + (f" : {d10[0]['quoi']}" if d10 else ""))
    except Exception as e: journal(f"  contrôle attribution impossible ({str(e)[:120]})"); sautes.append("attribution")
    try:                                                                   # scripte (23 novembre) : une question, la réponse par l'autre
        d11 = dialogue_logique(sk); points += d11
        if d11: journal(f"  [vidéo finie · dialogue] ✘ {d11[0]['quoi']}")
    except Exception as e: journal(f"  contrôle du dialogue impossible ({str(e)[:120]})")
    if sk.get("doublage") and not (sk["doublage"] or {}).get("vue") and os.environ.get("ATTRIBUTION", "1") != "0":
        sautes.append("qui parle d'après l'image de l'original (image illisible)")
    if sautes: journal(f"  contrôles qui n'ont pas pu se faire : {', '.join(sautes)} (note de confiance plafonnée)")
    for l in sk.get("equipe") or []:                                       # défauts de l'équipe que personne n'a pu corriger
        if l.get("revoir"): points.append(_defaut(None, l.get("poste", "équipe"), f"{l.get('controle')} : {l.get('detail')}"))
    points.sort(key=lambda d: (not d["grave"], d["t"] if d["t"] is not None else -1))
    legers = [d for d in points if not d["grave"]]; points = [d for d in points if d["grave"]]   # demande de l'auteur (6 novembre) : la vidéo
    if legers: journal(f"  {len(legers)} remarque(s) légère(s) gardée(s) au journal seulement : " + " ; ".join(f"{d['t']} s {d['quoi'][:50]}" for d in legers[:6]))
    journal(f"Contrôle de la vidéo finie : {len(points)} point(s) à vérifier" + (" — " + " ; ".join(f"{d['t']} s {d['quoi'][:60]}" for d in points[:6]) if points else ""))
    return points[:20]                                                     # sort propre : seuls les vrais défauts restent signalés


NOMS_ROLES = {"presentateur": "le présentateur", "invite": "l'invitée", "envoyee": "l'envoyée"}
DE_ROLES = {"presentateur": "du présentateur", "invite": "de l'invitée", "envoyee": "de l'envoyée"}


def voix_dessin(video, sk):
    """Contrôle final « voix et dessin » (audit du 21 novembre 2026) : sur le son de la vidéo FINIE, la hauteur de chaque réplique
    (equipe.hauteur_finale) ; une réplique nettement du côté de l'autre voix = point grave (le compte rendu la remet sur le bon
    personnage) ; et quand une voix est nettement aiguë (≥ 200 Hz) et l'autre nettement grave (≤ 170 Hz), le personnage à la voix
    aiguë dessiné en homme (ou l'inverse) = point grave. VOIX_DESSIN=0 pour couper."""
    import copy, equipe
    if os.environ.get("VOIX_DESSIN", "1") == "0" or not (sk or {}).get("doublage"): return []
    reps0 = sk.get("repliques") or []
    from collections import Counter
    roles = [r for r, _ in Counter(r.get("p") for r in reps0 if r.get("p") not in (None, "narrateur") and not r.get("_hors_champ")).most_common(2)]
    if len(roles) != 2 or len(reps0) < 6: return []
    son, sr = _son(video)
    sk2 = copy.deepcopy(sk); _c, n = equipe.hauteur_finale(sk2, sk2["repliques"], sorted(roles), son, sr, None, bavard=False)
    out = []
    for i, (a, b) in enumerate(zip(reps0, sk2["repliques"])):
        if a.get("p") != b.get("p"):
            d_ = _defaut(a.get("_deb"), "voix et dessin", f"réplique {i + 1} « {str(a.get('t') or '')[:50]} » : c'est la voix "
                         f"{DE_ROLES.get(b['p'], b['p'])}, pas {DE_ROLES.get(a['p'], a['p'])} (hauteur de la voix)")
            d_["qui"] = {"replique": i, "role": b["p"]}; out.append(d_)
    H = sk2.get("_hauteurs_roles") or {}
    if len(H) == 2:
        haut, bas = sorted(H, key=H.get, reverse=True)
        gen = {r: (((sk.get("_casting_final") or {}).get(r) or {}).get("fiche") or {}).get("genre") for r in H}
        age = {r: (((sk.get("_casting_final") or {}).get(r) or {}).get("fiche") or {}).get("age") or 30 for r in H}
        P_ = ((sk.get("studio") or {}).get("personnages") or {}) if isinstance(sk.get("studio"), dict) else {}
        vu = {r: str((P_.get(r) or {}).get("genre_vu") or "").lower()[:1] for r in H}
        vu = {r: ("f" if g in ("f", "w") else "h" if g in ("h", "m") else None) for r, g in vu.items()}
        meme_vu = vu.get(haut) and vu.get(haut) == vu.get(bas)             # deux hommes (ou deux femmes) vus par Gemini : l'écart = des cris
        import studio as _ST                                               # rôle joué par un acteur de l'autre sexe (audit du 23 nov.) :
        txt = {r: _ST.genre_texte(sk, r) for r in H}                       # les mots (« ma robe », « les meufs ») ne se discutent pas
        if _ST.un_acteur(sk): vu = {}; meme_vu = True
        if H[haut] >= 200 and H[bas] <= 170 and H[haut] >= 1.4 * H[bas] and H[haut] <= __import__("locuteurs").CRIS_HZ and not meme_vu \
                and not any(g_ and (f_ >= 4 or g_ == gen.get(r)) for r, (g_, f_) in txt.items()):
            if gen.get(haut) == "h" and age.get(haut, 30) >= 13 and vu.get(haut) != "h":
                d_ = _defaut(None, "voix et dessin", f"{NOMS_ROLES.get(haut, haut)} a une voix de femme ({H[haut]} Hz) mais est dessiné(e) en homme : c'est une femme")
                d_["genre"] = {"role": haut, "genre": "f"}; out.append(d_)
            if gen.get(bas) == "f" and vu.get(bas) != "f":
                d_ = _defaut(None, "voix et dessin", f"{NOMS_ROLES.get(bas, bas)} a une voix d'homme ({H[bas]} Hz) mais est dessiné(e) en femme : c'est un homme")
                d_["genre"] = {"role": bas, "genre": "h"}; out.append(d_)
    return out[:12]


ATTRIB_MAX = 0.2


def vue_fiable(sk):
    """Le témoin image dit-il QUI PARLE, ou seulement QUI EST À L'IMAGE ? (audit du 23 novembre 2026 : dans « organiser des plans »
    on ne voit qu'une personne pendant 26 s, puis l'autre, alors que les deux se parlent tout du long ; le témoin disait « 0 » puis
    « 1 » et le contrôle « attribution » criait à tort au mauvais personnage.) Fiable seulement s'il ALTERNE vraiment : au moins
    2 changements, au moins un tiers des changements de personne des répliques, et chaque personne sur 15 % des phrases."""
    vue = ((sk or {}).get("doublage") or {}).get("vue") or []
    v = [int(c) for a, b, c, w in sorted(vue, key=lambda x: float(x[0])) if c is not None and float(w) >= 0.3]
    if len(v) < 4 or len(set(v)) < 2: return False
    sw_v = sum(1 for x, y in zip(v, v[1:]) if x != y)
    from collections import Counter
    reps = sk.get("repliques") or []
    roles = [r for r, _ in Counter(r.get("p") for r in reps if r.get("p") not in (None, "narrateur") and not r.get("_hors_champ")).most_common(2)]
    rp = [r.get("p") for r in reps if r.get("p") in roles]
    sw_r = sum(1 for x, y in zip(rp, rp[1:]) if x != y)
    mini = min(Counter(v).values()) / len(v) if len(Counter(v)) >= 2 else 0
    return sw_v >= 2 and sw_v >= 0.33 * max(1, sw_r) and mini >= 0.15


def attribuer_par_image(sk, appliquer=True, journal=print):
    """Quand UN acteur joue tous les rôles (voix trop proches : la hauteur et l'empreinte vocale ne tranchent plus) et que l'image de
    l'original alterne vraiment (vue_fiable), c'est l'image qui dit qui parle : chaque réplique va au personnage que l'image montre
    parler, si elle est nette (certitude ≥ 0,5 et 2 fois plus de poids que l'autre). Jamais contre l'auteur ni contre une réplique
    confirmée par la hauteur de la voix ; la moitié des répliques au plus. Audit du 23 novembre 2026 (« Tu viens d'avoir 27 ans » :
    l'image avait raison sur 44 % des phrases et personne ne s'en servait). Renvoie {n° de réplique: rôle}. IMAGE_DECIDE=0 pour couper."""
    if os.environ.get("IMAGE_DECIDE", "1") == "0" or not vue_fiable(sk): return {}
    import studio as _ST
    if not _ST.un_acteur(sk): return {}
    from collections import Counter
    reps = sk.get("repliques") or []; vue = sk["doublage"]["vue"]
    roles = [r for r, _ in Counter(r.get("p") for r in reps if r.get("p") not in (None, "narrateur") and not r.get("_hors_champ")).most_common(2)]
    if len(roles) != 2: return {}
    votes = {}
    for a, b, c, w in vue:
        if c is None or int(c) not in (0, 1): continue
        for i, r in enumerate(reps):
            if r.get("p") not in roles or r.get("_deb") is None: continue
            o = min(float(b), float(r["_fin"])) - max(float(a), float(r["_deb"]))
            if o > 0.5 * (float(b) - float(a)):
                votes.setdefault(i, [0.0, 0.0])[int(c)] += float(w) * o
    if len(votes) < 4: return {}
    direct = sum(1 for i, (v0, v1) in votes.items() if (v0 > v1) == (reps[i]["p"] == roles[0]))
    sens = roles if direct >= len(votes) - direct else roles[::-1]       # personne 0 de l'image = quel rôle
    out = {}
    for i, (v0, v1) in votes.items():
        r = reps[i]
        if r.get("_auteur") or r.get("_hauteur_ok"): continue
        haut, bas = (0, 1) if v0 >= v1 else (1, 0)
        fort, faible = max(v0, v1), min(v0, v1)
        dur = max(0.2, float(r["_fin"]) - float(r["_deb"]))
        if fort < 0.5 * min(dur, 1.0) or fort < 2 * faible: continue
        if sens[haut] != r["p"]: out[i] = sens[haut]
    if len(out) > len(reps) / 2: return {}
    if appliquer and out:
        for i, role in out.items(): reps[i]["p"] = role; reps[i]["_image_ok"] = True
        journal(f"  [équipe · casting voix] ✔ un acteur joue tous les rôles : {len(out)} réplique(s) rendue(s) au personnage que l'image "
                f"montre parler (corrigé) : " + ", ".join(str(i + 1) for i in sorted(out)[:10]))
    return out


QUESTION_DEBUT = re.compile(r"^(pourquoi|comment|qu'est-ce|qu'est ce|est-ce que|est ce que|c'est qui|t'es o[uù]|tu fais quoi|tu veux|t'as|"
                            r"tu vas|tu peux|quoi|qui|o[uù]|combien|quand|t'es s[ée]rieux|s[ée]rieux)\b", re.I)
REPONSE_DEBUT = re.compile(r"^(oui|non|ouais|nan|bah|ben|parce que|pa'ce que|si|d'accord|ok|okay|je sais pas|j'sais pas|rien|personne|"
                           r"jamais|carr[ée]ment|grave|exactement|tranquille|t'inqui[èe]te)\b", re.I)


def est_question(t):
    t = str(t or "").strip().lower()
    return t.endswith("?") or bool(QUESTION_DEBUT.match(t)) or bool(re.search(r"\b(ou pas|hein|non)\s*[?.!]?$", t))


def dialogue_logique(sk):
    """Contrôle « scripte » de la vidéo finie (audit du 23 novembre 2026) : quand UN acteur fait toutes les voix et que l'image ne
    dit pas qui parle, rien ne voyait « Pourquoi tu veux savoir ? » / « Bah, je te demande, comme ça » dits par le MÊME personnage.
    Une question suivie d'une réponse (« oui », « bah », « parce que »…) ou d'une autre question du même personnage, 3 fois au
    moins et après la moitié des questions au moins = point grave « dialogue », avec les répliques en cause (le compte rendu les fait relire).
    DIALOGUE_LOGIQUE=0 pour couper."""
    if os.environ.get("DIALOGUE_LOGIQUE", "1") == "0": return []
    import studio as _ST
    if not _ST.un_acteur(sk): return []
    reps = [r for r in sk.get("repliques") or [] if r.get("p") not in (None, "narrateur") and not r.get("_hors_champ")]
    paires, memes = 0, []
    idx = {id(r): i for i, r in enumerate(sk.get("repliques") or [])}
    for a, b in zip(reps, reps[1:]):
        if not est_question(a.get("t")) or b.get("_auteur") or b.get("_hauteur_ok"): continue
        paires += 1                                                        # une question, puis la même personne qui enchaîne
        if a.get("p") == b.get("p") and (REPONSE_DEBUT.match(str(b.get("t") or "").strip()) or est_question(b.get("t"))):
            memes.append(idx[id(b)])
    if len(memes) < 3 or len(memes) < 0.5 * paires: return []
    R = sk.get("repliques")
    d_ = _defaut(R[memes[0]].get("_deb"), "dialogue",
                 f"{len(memes)} réponse(s) dites par le personnage qui vient de poser la question (répliques "
                 f"{', '.join(str(k + 1) for k in memes[:6])}) : c'est sans doute l'autre qui répond")
    d_["repliques_douteuses"] = memes
    return [d_]


def attribution_image(sk):
    """Contrôle final « attribution » (audit du 22 novembre 2026 : « Pire date amoureux » notée 22/22 et confiance 100 alors que 43 %
    de la parole était sur le mauvais personnage ; le témoin image disait déjà 27 % de désaccord, sous le seuil de 30 %). Compare,
    phrase par phrase, qui parle d'après l'IMAGE de l'original (sk["doublage"]["vue"] : Gemini, visages, mouvements, certitude ≥ 0,3)
    avec la réplique de la vidéo FINIE à ce moment-là (correspondance des deux personnes qui donne le plus d'accord). Les répliques
    confirmées par la hauteur de la voix (plus sûre que l'image) ou choisies par l'auteur ne comptent pas. Plus de 20 % de désaccord
    sur 4 phrases au moins = point grave, avec les répliques en cause. ATTRIBUTION=0 pour couper."""
    from collections import Counter
    if os.environ.get("ATTRIBUTION", "1") == "0": return []
    vue = ((sk or {}).get("doublage") or {}).get("vue") or []
    reps = sk.get("repliques") or []
    roles = [r for r, _ in Counter(r.get("p") for r in reps if r.get("p") not in (None, "narrateur") and not r.get("_hors_champ")).most_common(2)]
    if len(roles) != 2 or len(vue) < 4: return []
    if not vue_fiable(sk): return []                                       # l'image montre qui est là, pas qui parle (23 novembre)
    paires = []
    for a, b, c, w in vue:
        best, k_ = 0.0, None
        for i, r in enumerate(reps):
            if r.get("p") not in roles or r.get("_deb") is None: continue
            o = min(float(b), float(r["_fin"])) - max(float(a), float(r["_deb"]))
            if o > best: best, k_ = o, i
        if k_ is None or best < 0.5 * (float(b) - float(a)): continue
        r = reps[k_]
        if r.get("_hauteur_ok") or r.get("_auteur") or c is None: continue
        paires.append((int(c), roles.index(r["p"]), k_))
    if len(paires) < 4: return []
    accord = max(sum(1 for c, j, _ in paires if c == j), sum(1 for c, j, _ in paires if c != j))
    direct = sum(1 for c, j, _ in paires if c == j) >= sum(1 for c, j, _ in paires if c != j)
    contre = sorted({k for c, j, k in paires if (c == j) != direct})
    part = 1 - accord / len(paires)
    if part <= ATTRIB_MAX: return []
    d_ = _defaut(reps[contre[0]].get("_deb") if contre else None, "attribution",
                 f"l'image de l'original montre l'autre personne parler pendant {round(100 * part)} % des phrases "
                 f"(répliques {', '.join(str(k + 1) for k in contre[:6])})")
    d_["repliques_douteuses"] = contre
    import copy                                                            # correction directe possible (un acteur, image fiable)
    q = attribuer_par_image(copy.deepcopy(sk), appliquer=False, journal=lambda *_: None)
    if q: d_["qui_liste"] = {str(i): r_ for i, r_ in q.items()}
    return [d_]


def appliquer_voix(sk, points):
    """Compte rendu (principal.corriger_compte_rendu) : les points « voix et dessin » sont corrigés DIRECTEMENT (sans IA) : chaque
    réplique remise sur la voix entendue, et le genre du personnage d'après sa voix (menus « Changer les personnages », sauf si
    l'auteur a déjà choisi). Renvoie la liste lisible des changements."""
    faits, reps = [], sk.get("repliques") or []
    for d in points or []:
        for k_, r_ in (d.get("qui_liste") or {}).items():                 # « attribution » : l'image de l'original décide (un acteur)
            k_ = int(k_)
            if 0 <= k_ < len(reps) and not reps[k_].get("_auteur") and reps[k_].get("p") != r_:
                reps[k_]["p"] = r_; reps[k_]["_image_ok"] = True; faits.append(f"réplique {k_ + 1} -> {r_} (image de l'original)")
        q = d.get("qui")
        if isinstance(q, dict) and 0 <= int(q.get("replique", -1)) < len(reps) and not reps[int(q["replique"])].get("_auteur"):
            reps[int(q["replique"])]["p"] = q["role"]; reps[int(q["replique"])]["_voix_corrigee"] = True
            faits.append(f"réplique {int(q['replique']) + 1} -> {q['role']} (voix)")
        g = d.get("genre")
        if isinstance(g, dict) and g.get("role") and g.get("genre") in ("h", "f"):
            C_ = sk.setdefault("_casting_auteur", {})
            if not (C_.get(g["role"]) or {}).get("genre"):
                C_.setdefault(g["role"], {})["genre"] = g["genre"]; faits.append(f"{g['role']} : {'femme' if g['genre'] == 'f' else 'homme'} (voix)")
    return faits


def confiance(equipe, points, Q=None, sautes=None):
    """Note de confiance de la vidéo (0-100, choix de l'auteur) : 100 moins les défauts que personne n'a pu corriger (points à
    vérifier graves 12, autres 4 ; contrôles de l'équipe « à revoir » 8, autres ratés 2) et, si le jury note sous 6/10, 5 par point
    manquant. Sert au tri « les plus sûres d'abord » de l'onglet TikTok. Note honnête (23 novembre) : chaque contrôle important qui
    n'a pas pu se faire (sautes : Gemini absent, image de l'original illisible, contrôle en panne) retire 6 points et la note ne
    dépasse plus 90 (« Pire date » affichait 100 sans contrôle de l'attribution)."""
    sautes = [x for x in (sautes or []) if x]
    n = 100 - 6 * len(sautes) - 12 * sum(1 for d in points or [] if d.get("grave")) - 4 * sum(1 for d in points or [] if not d.get("grave"))
    n -= sum(8 if l.get("revoir") else 2 for l in equipe or [] if not l.get("ok"))
    try:
        if Q and float(Q.get("note") or 10) < 6: n -= int((6 - float(Q["note"])) * 5)
    except (TypeError, ValueError): pass
    return max(0, min(90 if sautes else 100, int(n)))
