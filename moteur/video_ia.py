"""Gemini regarde la vidéo d'origine EN ENTIER, image et son (choix de l'auteur, 1er novembre 2026, idée 1) : avant, l'IA ne voyait
que quelques images fixes. Il dit qui sont les personnages, où l'on est, et QUI DIT CHAQUE PHRASE (bouche qui bouge, place à
l'écran, coupes). Consigne clé (remarque de l'auteur) : une MÊME personne peut jouer 2 ou 3 personnages (autre vêtement, perruque,
accessoire, voix changée, côté de l'écran, regard à gauche puis à droite, coupes alternées) : on compte les PERSONNAGES, pas les
acteurs. Dans un dessin animé : celui dont la bouche bouge.

API Gemini « native » (la vidéo est envoyée dans la demande, réduite en 360p, 20 Mo au plus), clé gratuite GEMINI_API_KEY, même
quota que les autres appels Gemini (sauté s'il est épuisé). Sert de témoin dans l'équipe (casting voix) et à la mise en scène
(lieu, personnages, espèce). VIDEO_IA=0 pour couper."""
import base64, json, os, re, subprocess, tempfile, urllib.request

MODELES = ("gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest")
DERNIER = {}                                                               # dernière analyse (mise en scène, espèces)


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
  oiseau, poisson, steak, pizza, oeuf, banane, voiture, frigo, telephone, verre, croissant, ou "objet:<nom>").
  ATTENTION : une MÊME personne (ou un même doubleur) joue souvent 2 ou 3 personnages : autre vêtement, perruque, accessoire,
  voix déguisée, côté de l'écran, regard tourné à gauche puis à droite, coupes qui alternent. Ce sont alors des PERSONNAGES
  DIFFÉRENTS : compte les personnages, pas les acteurs ;
- "meme_interprete" : true si une même personne joue plusieurs personnages ;
- "phrases" : pour CHAQUE numéro de phrase, la lettre du personnage qui la DIT (celui dont la bouche bouge à ce moment, ou que
  l'on voit parler ; dans un dessin animé, le personnage dont la bouche est animée), et "sur" de 0 à 1 (ta certitude) ;
- "lieu" : un mot parmi {lieux} ;
- "resume" : l'histoire en 2 phrases (qui fait quoi, la chute).
Réponds UNIQUEMENT en JSON : {{"personnages": [{{"id": "A", "description": "...", "cote": "...", "espece": "..."}}], "meme_interprete": false,
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
    err = ""
    for modele in MODELES:
        req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent",   # clé dans l'en-tête
                                     data=json.dumps(corps).encode(), method="POST", headers={"Content-Type": "application/json", "x-goog-api-key": cle})
        try:
            d = json.loads(reseau.ouvrir(req, timeout=240, essais=2))
            txt = "".join(p.get("text", "") for c in d.get("candidates") or [] for p in (c.get("content") or {}).get("parts") or [])
            m = re.search(r"\{.*\}", txt, re.S)
            res = json.loads(m.group(0)) if m else None
            if isinstance(res, dict) and res.get("phrases"):
                reseau.UTILISES["gemini"] = reseau.UTILISES.get("gemini", 0) + 1
                res["_ph"] = [(mots[p[0]]["s"], mots[p[-1]]["e"]) for p in ph]
                DERNIER.update(res)
                n_p = len([p for p in res.get("personnages") or [] if isinstance(p, dict)])
                print(f"  Gemini a regardé la vidéo entière ({modele}) : {n_p} personnage(s)"
                      + (", une même personne en joue plusieurs" if res.get("meme_interprete") else "") + f", lieu « {res.get('lieu', '?')} »", flush=True)
                return res
        except Exception as e:
            err = str(e)[:160]
            if any(x in err.lower() for x in ("quota", "exhausted", "per day")): reseau.HORS_SERVICE.add("gemini"); break
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
    return (out if sum(1 for c, _ in out if c is not None) >= 3 else None), len(lettres)


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


def texte():
    """Ce que Gemini a vu, pour la consigne de mise en scène."""
    r = DERNIER
    if not r: return ""
    pers = "; ".join(f"{p.get('id')} : {p.get('description', '')} ({p.get('cote', '?')}, {p.get('espece', 'humain')})"
                     for p in r.get("personnages") or [] if isinstance(p, dict))[:1200]
    return (f"\nCe que Gemini a vu en regardant TOUTE la vidéo d'origine : {str(r.get('resume', ''))[:500]} Lieu : {r.get('lieu', '?')}. "
            f"Personnages : {pers}." + (" Une même personne joue plusieurs personnages." if r.get("meme_interprete") else "") + "\n")
