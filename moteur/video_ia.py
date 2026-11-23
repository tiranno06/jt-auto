"""Gemini regarde la vidéo d'origine EN ENTIER, image et son (choix de l'auteur, 1er novembre 2026, idée 1) : avant, l'IA ne voyait
que quelques images fixes. Il dit qui sont les personnages, où l'on est, et QUI DIT CHAQUE PHRASE (bouche qui bouge, place à
l'écran, coupes). Consigne clé (remarque de l'auteur) : une MÊME personne peut jouer 2 ou 3 personnages (autre vêtement, perruque,
accessoire, voix changée, côté de l'écran, regard à gauche puis à droite, coupes alternées) : on compte les PERSONNAGES, pas les
acteurs. Dans un dessin animé : celui dont la bouche bouge.

API Gemini « native » (la vidéo est envoyée dans la demande, réduite en 360p, 20 Mo au plus), clé gratuite GEMINI_API_KEY, même
quota que les autres appels Gemini (sauté s'il est épuisé). Sert de témoin dans l'équipe (casting voix) et à la mise en scène
(lieu, personnages, espèce). VIDEO_IA=0 pour couper."""
import base64, json, os, re, subprocess, tempfile, urllib.request

VOULUS = ("gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.5-flash-lite")


class _Modeles:
    """Modèles Gemini pour la vidéo / le son : ceux qui existent encore chez Google (reseau.gemini_disponibles, lus une fois)."""
    def __iter__(self):
        try: return iter(__import__("reseau").gemini_disponibles(VOULUS))
        except Exception: return iter(VOULUS)


MODELES = _Modeles()
DERNIER = {}
PASSAGERES = ("503", "429", "500", "502", "504", "overloaded", "unavailable", "timed out", "timeout", "too many")
DERNIERE_ERREUR = [""]


def generer(corps, timeout=240, tours=3, pause=20.0, max_modeles=None, valide=None, journal=None, quoi="Gemini"):
    """Appel PATIENT à Gemini (audit du 23 novembre 2026 : sur 10 vidéos, Gemini « surchargé » (503) ou « trop de demandes » (429) a
    privé 5 vidéos du témoin qui regarde l'original et du contrôle « fidélité » ; on abandonnait après un seul essai rapide). Chaque
    modèle est essayé ; si TOUS ont refusé pour une raison passagère, on attend (20 s, puis 40 s) et on refait un tour (3 tours au
    plus, GEMINI_TOURS). Quota du jour épuisé = Gemini coupé pour la fabrication. Renvoie la réponse JSON (dict) ou None."""
    cle = os.environ.get("GEMINI_API_KEY")
    if not cle: return None
    import reseau, time
    if "gemini" in reseau.HORS_SERVICE: return None
    try: tours = max(1, int(os.environ.get("GEMINI_TOURS") or tours))
    except ValueError: pass
    err = ""
    for tour in range(tours):
        modeles = list(MODELES)[:max_modeles] if max_modeles else list(MODELES)
        passager = False
        for modele in modeles:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent",
                                         data=json.dumps(corps).encode(), method="POST", headers={"Content-Type": "application/json", "x-goog-api-key": cle})
            try:
                d = json.loads(reseau.ouvrir(req, timeout=timeout, essais=1))
                txt = "".join(p.get("text", "") for c in d.get("candidates") or [] for p in (c.get("content") or {}).get("parts") or [])
                m = re.search(r"\{.*\}", txt, re.S)
                res = json.loads(m.group(0)) if m else None
                if isinstance(res, dict) and (valide is None or valide(res)):
                    reseau.UTILISES["gemini"] = reseau.UTILISES.get("gemini", 0) + 1
                    res.setdefault("_modele", modele)
                    return res
                err = "réponse vide ou incomplète"; passager = True
            except Exception as e:
                err = str(e)[:160]; reseau.gemini_mort(modele, err)
                if any(x in err.lower() for x in ("quota", "exhausted", "per day")): reseau.HORS_SERVICE.add("gemini"); DERNIERE_ERREUR[0] = err; return None
                if any(x in err.lower() for x in PASSAGERES): passager = True
                if journal: journal(f"  {quoi} : {modele} n'a pas répondu ({err[:90]})")
        if not passager or tour == tours - 1: break
        attente = pause * (tour + 1)
        print(f"  {quoi} : Gemini surchargé, nouvel essai dans {attente:.0f} s (tour {tour + 2}/{tours})", flush=True)
        time.sleep(attente)
    DERNIERE_ERREUR[0] = err
    return None                                                               # dernière analyse (mise en scène, espèces)


def _petite(chemin):
    """Vidéo réduite (360p, 6 images/s, son mono) pour tenir dans une demande ; None si impossible."""
    d = tempfile.mkdtemp(); out = os.path.join(d, "v.mp4")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", chemin, "-vf", "scale=-2:360,fps=6", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "32", "-c:a", "aac", "-b:a", "48k", "-ac", "1", "-t", "180", out], capture_output=True)
    return out if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) < 18e6 else None


CONSIGNE = """Tu regardes ET écoutes cette vidéo TikTok (souvent un sketch ou un dessin animé doublé en français). Voici ses phrases,
numérotées, avec leurs instants :
{phrases}

Dis-moi :
- "personnages" : chaque PERSONNAGE qui parle ou qu'on voit, avec une lettre (A, B, C…) : "description" (âge, genre, allure,
  vêtements, couleur des cheveux), "cote" (gauche, droite, centre ou varie), "espece" (humain, ou chat, chien, lapin, souris,
  oiseau, poisson, steak, pizza, oeuf, banane, voiture, frigo, telephone, verre, croissant, ou "objet:<nom>"), "visible" (false
  si on ne fait que l'ENTENDRE sans jamais le voir à l'image : message vocal, téléphone, télé, radio, voix derrière une porte ;
  une personne dont on PARLE sans l'entendre n'est PAS un personnage).
  ATTENTION : une MÊME personne (ou un même doubleur) joue souvent 2 ou 3 personnages : autre vêtement, perruque, accessoire,
  voix déguisée, côté de l'écran, regard tourné à gauche puis à droite, coupes qui alternent. Ce sont alors des PERSONNAGES
  DIFFÉRENTS : compte les personnages, pas les acteurs ;
- "meme_interprete" : true si une même personne joue plusieurs personnages ;
- "phrases" : pour CHAQUE numéro de phrase, la lettre du personnage qui la DIT (celui dont la bouche bouge à ce moment, ou que
  l'on voit parler ; dans un dessin animé, le personnage dont la bouche est animée), et "sur" de 0 à 1 (ta certitude) ;
- "lieu" : un mot parmi {lieux} ;
- "resume" : l'histoire en 2 phrases (qui fait quoi, la chute).
Réponds UNIQUEMENT en JSON : {{"personnages": [{{"id": "A", "description": "...", "cote": "...", "espece": "...", "visible": true}}], "meme_interprete": false,
"phrases": [{{"n": 0, "qui": "A", "sur": 0.9}}], "lieu": "...", "resume": "..."}}"""


def analyser(chemin, mots, ph):
    """Analyse de la vidéo entière ; None si impossible (pas de clé, quota, vidéo trop lourde). Garde le résultat dans DERNIER."""
    DERNIER.clear()
    cle = os.environ.get("GEMINI_API_KEY")
    if os.environ.get("VIDEO_IA", "1") == "0" or not cle or not chemin or not os.path.exists(chemin) or not ph: return None
    import reseau, decor_dessin as DD
    if "gemini" in reseau.HORS_SERVICE: return None
    v = _petite(chemin)
    if not v: return None
    lignes = "\n".join(f"{j}. ({mots[p[0]]['s']:.1f}–{mots[p[-1]]['e']:.1f} s) {' '.join(mots[i]['w'] for i in p)[:160]}" for j, p in enumerate(ph))
    corps = {"contents": [{"parts": [{"inline_data": {"mime_type": "video/mp4", "data": base64.b64encode(open(v, "rb").read()).decode()}},
                                     {"text": CONSIGNE.format(phrases=lignes[:9000], lieux=", ".join(DD.LIEUX))}]}],
             "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"}}
    res = generer(corps, timeout=240, valide=lambda r: bool(r.get("phrases")), quoi="vidéo d'origine")
    if res:
        res["_ph"] = [(mots[p[0]]["s"], mots[p[-1]]["e"]) for p in ph]
        DERNIER.update(res)
        n_p = len([p for p in res.get("personnages") or [] if isinstance(p, dict) and p.get("visible") is not False])
        print(f"  Gemini a regardé la vidéo entière ({res.get('_modele')}) : {n_p} personnage(s)"
              + (", une même personne en joue plusieurs" if res.get("meme_interprete") else "") + f", lieu « {res.get('lieu', '?')} »", flush=True)
        return res
    err = DERNIERE_ERREUR[0]
    print(f"  Gemini n'a pas pu regarder la vidéo ({err or 'réponse vide'})", flush=True)
    return None


def vue(res, n_ph):
    """Témoin au format de regard.temoin : [(personnage 0/1/2… ou None, certitude)] + nombre de personnages qui parlent."""
    if not res: return None, 0
    lettres = {}
    out = [(None, 0.0)] * n_ph
    for x in res.get("phrases") or []:
        try:
            n = int(x.get("n")); q = str(x.get("qui") or "").strip().upper()[:1]
            s = float(x.get("sur") if x.get("sur") is not None else 0.7)
        except (TypeError, ValueError, AttributeError): continue
        if 0 <= n < n_ph and q.isalpha():
            lettres.setdefault(q, len(lettres)); out[n] = (lettres[q], max(0.0, min(1.0, s)))
    caches = {str(p.get("id", "")).upper()[:1] for p in res.get("personnages") or [] if isinstance(p, dict) and p.get("visible") is False}
    return (out if sum(1 for c, _ in out if c is not None) >= 3 else None), len([q for q in lettres if q not in caches])


def visibles():
    """Nombre de personnages que Gemini VOIT à l'image (ceux qu'on entend seulement sont exclus), ou None."""
    P = [p for p in (DERNIER.get("personnages") or []) if isinstance(p, dict)] if DERNIER else []
    return len([p for p in P if p.get("visible") is not False]) or None if P else None


def voix_hors_champ(mots):
    """Voix dont les phrases sont dites, d'après Gemini, par un personnage qu'on ENTEND seulement (message vocal, téléphone…)."""
    res = DERNIER
    if not res: return set()
    caches = {str(p.get("id", "")).upper()[:1] for p in res.get("personnages") or [] if isinstance(p, dict) and p.get("visible") is False}
    if not caches: return set()
    from collections import Counter
    import locuteurs
    ph = locuteurs.phrases(mots); dans, tout = Counter(), Counter(m["voix"] for m in mots)
    for x in res.get("phrases") or []:
        try: n = int(x.get("n")); q = str(x.get("qui") or "").strip().upper()[:1]
        except (TypeError, ValueError, AttributeError): continue
        if 0 <= n < len(ph) and q in caches:
            for i in ph[n]: dans[mots[i]["voix"]] += 1
    return {v for v, k in dans.items() if k >= 0.6 * tout[v]}


def especes_par_voix(mots):
    """{voix: espèce} pour les personnages NON humains vus par Gemini (la voix qui dit le plus de leurs phrases)."""
    res = DERNIER
    if not res: return {}
    import animaux
    esp = {str(p.get("id", "")).upper()[:1]: animaux.espece_valide(p.get("espece")) for p in res.get("personnages") or [] if isinstance(p, dict)}
    out = {}
    for lettre, e in esp.items():
        if not e: continue
        compte = {}
        for x in res.get("phrases") or []:
            try:
                if str(x.get("qui", "")).upper()[:1] != lettre: continue
                a, b = res["_ph"][int(x["n"])]
            except (KeyError, IndexError, TypeError, ValueError): continue
            for m in mots:
                if a - 0.05 <= m["s"] <= b + 0.05: compte[m["voix"]] = compte.get(m["voix"], 0) + 1
        if compte:
            v = max(compte, key=compte.get)
            if v not in out: out[v] = e
    return out


def genres_vus():
    """Genres (« h » / « f ») des personnages VISIBLES que Gemini a vus dans l'original, un par personnage (liste)."""
    out = []
    for p in (DERNIER or {}).get("personnages") or []:
        if not isinstance(p, dict) or p.get("visible") is False or str(p.get("espece") or "humain") not in ("humain", ""): continue
        d = str(p.get("description") or "").lower()
        f_ = re.search(r"\b(femme|fille|dame|m[èe]re|maman|s[œo]eur|grand-m[èe]re|mamie|copine|woman|girl|female)\b", d)
        h_ = re.search(r"\b(homme|gar[çc]on|monsieur|p[èe]re|papa|fr[èe]re|grand-p[èe]re|papi|copain|man|boy|male)\b", d)
        if bool(f_) != bool(h_): out.append("f" if f_ else "h")
    return out


def genres_par_voix(mots):
    """{voix: « h » / « f »} : ce que Gemini a VU (homme / femme) pour le personnage qui dit le plus de phrases de cette voix."""
    res = DERNIER
    if not res: return {}
    gen = {}
    for p in res.get("personnages") or []:
        if not isinstance(p, dict): continue
        d = str(p.get("description") or "").lower()
        f_ = re.search(r"\b(femme|fille|dame|m[èe]re|maman|s[œo]eur|grand-m[èe]re|mamie|copine|woman|girl|female|elle)\b", d)
        h_ = re.search(r"\b(homme|gar[çc]on|monsieur|p[èe]re|papa|fr[èe]re|grand-p[èe]re|papi|copain|man|boy|male|il)\b", d)
        if bool(f_) != bool(h_): gen[str(p.get("id", "")).upper()[:1]] = "f" if f_ else "h"
    out = {}
    for lettre, g in gen.items():
        compte = {}
        for x in res.get("phrases") or []:
            try:
                if str(x.get("qui", "")).upper()[:1] != lettre: continue
                a, b = res["_ph"][int(x["n"])]
            except (KeyError, IndexError, TypeError, ValueError): continue
            for m in mots:
                if a - 0.05 <= m["s"] <= b + 0.05: compte[m["voix"]] = compte.get(m["voix"], 0) + 1
        if compte:
            v = max(compte, key=compte.get)
            if v not in out: out[v] = g
    return out


def texte():
    """Ce que Gemini a vu, pour la consigne de mise en scène."""
    r = DERNIER
    if not r: return ""
    pers = "; ".join(f"{p.get('id')} : {p.get('description', '')} ({p.get('cote', '?')}, {p.get('espece', 'humain')})"
                     for p in r.get("personnages") or [] if isinstance(p, dict))[:1200]
    return (f"\nCe que Gemini a vu en regardant TOUTE la vidéo d'origine : {str(r.get('resume', ''))[:500]} Lieu : {r.get('lieu', '?')}. "
            f"Personnages : {pers}." + (" Une même personne joue plusieurs personnages." if r.get("meme_interprete") else "") + "\n")


ECOUTE = """Écoute ce son (dialogue en français parlé, souvent de l'argot ou un dessin animé doublé). Pour CHAQUE passage ci-dessous,
écris EXACTEMENT les mots prononcés entre ces deux instants (rien d'inventé, pas de correction du langage parlé ; "" si personne ne parle) :
{passages}
Réponds UNIQUEMENT en JSON : {{"passages": [{{"n": 0, "texte": "..."}}]}}"""


def ecouter(chemin, passages):
    """Gemini ÉCOUTE le son (audit du 17 novembre 2026, idée 2 : 80 sous-titres signalés faux) sur les seuls passages en doute :
    passages = [(début, fin)] -> {n° du passage: texte entendu}. Son réduit (mono 32 kb/s) envoyé dans la demande ; {} si impossible."""
    cle = os.environ.get("GEMINI_API_KEY")
    if os.environ.get("ECOUTE_GEMINI", "1") == "0" or not cle or not passages or not chemin or not os.path.exists(chemin): return {}
    import reseau
    if "gemini" in reseau.HORS_SERVICE: return {}
    d = tempfile.mkdtemp(); son = os.path.join(d, "s.mp3")
    # Seulement les passages en doute (± 0,6 s), mis bout à bout : un son 5 à 10 fois plus court, Gemini répond vite (registre des
    # pannes du 21 novembre : le son ENTIER faisait dépasser le délai, « The read operation timed out », écoute perdue).
    morceaux, pos, places = [], 0.0, []
    for a, b in passages[:40]:
        a0, b0 = max(0.0, float(a) - 0.6), float(b) + 0.6
        if morceaux and a0 <= morceaux[-1][1]: morceaux[-1][1] = max(morceaux[-1][1], b0)
        else: morceaux.append([a0, b0])
    for a, b in passages[:40]:                                             # instants des passages dans le son raccourci
        acc = 0.0
        for a0, b0 in morceaux:
            if a0 <= float(a) <= b0: places.append((acc + float(a) - a0, acc + float(b) - a0)); break
            acc += b0 - a0
        else: places.append((float(a), float(b)))
    filtre = "".join(f"[0:a]atrim={a0:.2f}:{b0:.2f},asetpts=PTS-STARTPTS[a{k}];" for k, (a0, b0) in enumerate(morceaux)) + \
        "".join(f"[a{k}]" for k in range(len(morceaux))) + f"concat=n={len(morceaux)}:v=0:a=1[s]"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", chemin, "-filter_complex", filtre, "-map", "[s]", "-ac", "1", "-ar", "16000",
                        "-b:a", "32k", son], capture_output=True)
    if r.returncode or not os.path.exists(son):                           # (repli : le son entier, comme avant)
        places = [(float(a), float(b)) for a, b in passages[:40]]
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", chemin, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", "-t", "200", son], capture_output=True)
    if r.returncode or not os.path.exists(son) or os.path.getsize(son) > 15e6: return {}
    lignes = "\n".join(f"{k}. de {a:.1f} s à {b:.1f} s" for k, (a, b) in enumerate(places))
    corps = {"contents": [{"parts": [{"inline_data": {"mime_type": "audio/mp3", "data": base64.b64encode(open(son, "rb").read()).decode()}},
                                     {"text": ECOUTE.format(passages=lignes)}]}],
             "generationConfig": {"temperature": 0.0, "response_mime_type": "application/json"}}
    res = generer(corps, timeout=90, tours=2, valide=lambda r: isinstance(r.get("passages"), list), quoi="écoute des passages")
    if not res: print(f"  Gemini n'a pas pu écouter ({DERNIERE_ERREUR[0][:80]})", flush=True); return {}
    return lire_ecoute(json.dumps(res), len(passages))


def lire_ecoute(txt, n):
    """Réponse de Gemini -> {n° du passage: texte}."""
    m = re.search(r"\{.*\}", txt or "", re.S)
    try: res = json.loads(m.group(0)) if m else {}
    except ValueError: return {}
    out = {}
    for x in res.get("passages") or [] if isinstance(res, dict) else []:
        try:
            k = int(x.get("n"))
            if 0 <= k < n and isinstance(x.get("texte"), str): out[k] = x["texte"].strip()
        except (AttributeError, TypeError, ValueError): pass
    return out
