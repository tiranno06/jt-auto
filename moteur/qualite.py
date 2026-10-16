"""Contrôle qualité complet de la vidéo finie : un jury de 5 critiques qui donnent clairement leur avis pour la rendre plus drôle et
meilleure, puis le robot applique lui-même les corrections qu'il sait faire et refait la vidéo (on garde la mieux notée).

Les 5 critiques (note sur 10, au plus 3 remarques précises chacun, avec le moment) :
- humoriste : vannes, chute, timing, réactions, bruitages sur les vannes ;
- réalisateur : rythme des plans, serré / large, celui qui parle bien filmé, réactions, mouvements de caméra ;
- directeur artistique : âge, sexe, allure des personnages, décors, cohérence avec l'histoire, personnes dont on parle ;
- ingénieur du son : blancs, bruitages, volume ;
- spectateur TikTok : accroche, moments creux, durée, lisibilité des sous-titres, fin.
Deux versions : GRATUITE (règles calculées sur ce que le moteur a vraiment monté : marche toujours, sans crédit) et CLAUDE (mode
payant : il regarde les images de la vidéo et, pour un lien TikTok, celles de la vidéo d'origine à côté, pour lister ce qui manque).
Corrections possibles (appliquées au « studio » du sketch avant de refaire la vidéo) : plan, reaction, bruitage, casting, figurant,
lieux_separes, lieu, costume. La mémoire (episodes/qualite_memoire.json) garde les critiques ; les erreurs qui reviennent deviennent
des règles données à Claude, et le poids de chaque critique s'ajuste selon les vues TikTok."""
import base64, copy, datetime, json, math, os, re
from collections import Counter

ICI = os.path.dirname(os.path.abspath(__file__))
MEMOIRE = os.path.join(ICI, "..", "episodes", "qualite_memoire.json")
CRITIQUES = ("humoriste", "realisateur", "directeur_artistique", "son", "spectateur")
NOMS = {"humoriste": "Humoriste", "realisateur": "Réalisateur", "directeur_artistique": "Directeur artistique", "son": "Ingénieur du son",
        "spectateur": "Spectateur TikTok"}
TYPES = ("plan", "reaction", "bruitage", "casting", "figurant", "lieux_separes", "lieu", "costume", "jeu")
MODELE = os.environ.get("MODELE_CONTROLE") or "claude-sonnet-5-5"


def _rq(critique, moment, probleme, correction=None, poids=1.0, categorie=""):
    return dict(critique=critique, moment=None if moment is None else round(float(moment), 1), probleme=probleme,
                correction=correction, poids=poids, categorie=categorie or critique)


def _mots(t): return re.findall(r"[\wÀ-ÿ'-]+", t or "")


# ------------------------------------------------------------------ jury gratuit : règles sur le montage réel
def jury_gratuit(R, sk, rapport_tech=""):
    """R = cartoon.RENDU (répliques minutées, plans, fiches, bruitages…). Renvoie {critique: {"note", "remarques"}}."""
    import studio, decor_dessin as DD
    ph = R.get("ph") or []; plans = R.get("plans") or []; fiches = R.get("fiches") or {}; total = float(R.get("total") or 1)
    doub = bool(R.get("doublage")); br = R.get("bruitages") or []; places = R.get("places") or {}; mini = bool(R.get("mini"))
    rq = []
    if not ph: return {c: {"note": 5.0, "remarques": []} for c in CRITIQUES}
    parlees = [q for q in ph if q["p"] != "narrateur"]
    # --- défauts visibles repérés image par image (positions des têtes à l'écran)
    di = R.get("defauts_image") or []; vus_ = set()
    qui = {q["i"]: q["p"] for q in ph}
    for d in di:
        cle = (d["type"], d.get("i"))
        if cle in vus_ or d.get("i") is None: continue
        vus_.add(cle)
        if d["type"] == "tete_coupee":
            lui = d["role"] == qui.get(d["i"])                              # celui qui parle coupé : on recule ; un autre : plan serré
            rq.append(_rq("realisateur", d["t"], f"tête de {d['role']} coupée par le bord de l'image ({d.get('plan')})",
                          {"type": "plan", "replique": d["i"], "plan": ("large" if d.get("plan") == "moyen" else "moyen") if lui else "serre",
                           "cible": qui.get(d["i"]), "mouvement": "fixe" if lui else "avance"}, 1.3, "tete_coupee"))
        elif d["type"] == "chevauchement":
            rq.append(_rq("directeur_artistique", d["t"], f"deux personnages l'un sur l'autre ({d['role']})",
                          {"type": "plan", "replique": d["i"], "plan": "serre", "cible": qui.get(d["i"]), "mouvement": "avance"}, 1.2, "chevauchement"))
        elif d["type"] == "sous_titre_visage":
            rq.append(_rq("spectateur", d["t"], f"le sous-titre cache le visage de {d['role']}",
                          {"type": "plan", "replique": d["i"], "plan": "moyen", "cible": qui.get(d["i"]), "mouvement": "fixe"}, 1.0, "sous_titre_visage"))
    # --- humoriste
    chutes = [q for q in ph if q.get("chute")]
    for q in chutes:
        if not any(abs(t - q["fin"]) < 0.9 for _, t, _ in br) and q is not ph[-1]:
            rq.append(_rq("humoriste", q["fin"], f"la vanne « {q['texte'][:50]} » tombe sans accent sonore",
                          {"type": "bruitage", "replique": q["i"], "son": "vine_boom"}, 1.0, "vanne_sans_bruitage"))
        voit_reac = any(p_["i"] == q["i"] and p_["cible"] != q["p"] for p_ in plans) or q.get("reaction") not in (None, "aucune")
        if not voit_reac and len(places.get(q["scene"], [])) > 1:
            rq.append(_rq("humoriste", q["fin"], f"on ne voit pas la réaction à la vanne « {q['texte'][:40]} »",
                          {"type": "reaction", "replique": q["i"], "reaction": "regard_camera" if q is ph[-1] else "choc"}, 1.2, "vanne_sans_reaction"))
    fin = ph[-1]
    if len(_mots(fin["texte"])) > 16:
        rq.append(_rq("humoriste", fin["deb"], "la chute finale est trop longue : la vanne se dilue", None, 0.8, "chute_longue"))
    if not any(p_["i"] == fin["i"] and p_["mouvement"] in ("zoom_choc", "vertige") for p_ in plans) and fin["p"] != "narrateur":
        rq.append(_rq("humoriste", fin["deb"], "la chute finale mérite un zoom choc sur celui qui la dit",
                      {"type": "plan", "replique": fin["i"], "plan": "tres_serre", "cible": fin["p"], "mouvement": "zoom_choc"}, 0.8, "chute_sans_zoom"))
    if not doub:
        longues = [q for q in parlees if len(_mots(q["texte"])) > (14 if mini else 22)]
        if len(longues) > max(1, len(parlees) // 4):
            rq.append(_rq("humoriste", longues[0]["deb"], f"{len(longues)} répliques trop longues : on perd le rythme du ping-pong", None, 0.8, "repliques_longues"))
    # --- réalisateur
    coupes = len(plans) / total * 10
    cible_coupes = (len((R.get("coupes_origine") or [])) / total * 10) if R.get("coupes_origine") else (3.5 if mini else 2.8)
    if coupes < cible_coupes * 0.6:
        rq.append(_rq("realisateur", None, f"montage trop lent : {coupes:.1f} plans toutes les 10 s (il en faudrait ~{cible_coupes:.1f})", None, 1.0, "montage_lent"))
    for q in parlees:
        dur = max(0.01, q["fin"] - q["deb"]); vu = 0.0
        for p_ in plans:
            a, b = max(p_["t0"], q["deb"]), min(p_["t1"], q["fin"])
            if b > a and (p_["cible"] == q["p"] or p_["plan"] in ("large", "moyen")): vu += b - a
        if vu / dur < 0.5 and dur > 1.0:
            rq.append(_rq("realisateur", q["deb"], f"on voit trop peu {q['p']} pendant qu'il parle (« {q['texte'][:40]} »)",
                          {"type": "plan", "replique": q["i"], "plan": "serre", "cible": q["p"], "mouvement": "avance"}, 1.2, "parle_hors_champ"))
            break
    courts = [p_ for p_ in plans if p_["t1"] - p_["t0"] < 0.45]
    if len(courts) > 2: rq.append(_rq("realisateur", courts[0]["t0"], f"{len(courts)} plans trop courts (moins d'une demi-seconde)", None, 0.6, "plans_courts"))
    suite = 1
    for a, b in zip(plans, plans[1:]):
        suite = suite + 1 if (a["plan"], a["cible"]) == (b["plan"], b["cible"]) else 1
        if suite >= 3: rq.append(_rq("realisateur", b["t0"], "trois plans identiques d'affilée : ça manque de variété", None, 0.6, "plans_repetes")); break
    reac = [p_ for p_ in plans if any(q["i"] == p_["i"] and q["p"] != p_["cible"] and q["p"] != "narrateur" for q in ph)]
    if len(reac) < max(1, int(total / 15)) and max((len(v) for v in places.values()), default=1) > 1:
        q = max(parlees, key=lambda z: z["fin"] - z["deb"]) if parlees else ph[0]
        rq.append(_rq("realisateur", q["deb"], "pas assez de plans de réaction de celui qui écoute",
                      {"type": "reaction", "replique": q["i"], "reaction": "sceptique"}, 0.9, "peu_de_reactions"))
    mvts = Counter(p_["mouvement"] for p_ in plans)
    if len(mvts) <= 2 and len(plans) > 6: rq.append(_rq("realisateur", None, "caméra peu vivante : presque toujours le même mouvement", None, 0.5, "camera_monotone"))
    # --- directeur artistique
    textes = {r: " ".join(q["texte"] for q in ph if q["p"] == r).lower() for r in fiches}
    for r, F in fiches.items():
        autres = " ".join(v for k, v in textes.items() if k != r)
        if re.search(r"\b(fiston|mon fils|ma fille|mon gar[çc]on)\b", autres) and F.get("age", 30) >= 18:
            rq.append(_rq("directeur_artistique", None, f"{r} est appelé « fiston / mon fils » mais il est dessiné en adulte",
                          {"type": "casting", "role": r, "age": 15}, 1.3, "age_incoherent"))
        if F.get("age", 30) < 16 and F.get("barbe"):
            rq.append(_rq("directeur_artistique", None, f"{r} est un enfant : jamais de barbe", {"type": "casting", "role": r, "barbe": ""}, 1.3, "barbe_enfant"))
        vg = (sk.get("_voix_genre") or {}).get(r)
        if vg and F.get("genre") and vg != F["genre"]:
            rq.append(_rq("directeur_artistique", None, f"{r} a une voix {'de femme' if vg == 'f' else 'd’homme'} mais il est dessiné {'en homme' if vg == 'f' else 'en femme'}",
                          {"type": "casting", "role": r, "genre": vg}, 1.5, "genre_incoherent"))
    lieux = R.get("lieux") or []
    for k, l in enumerate(lieux):
        txt = " ".join(q["texte"] for q in ph if q["scene"] == k)
        devine = DD.lieu_de(txt, "")
        if devine and devine != l and len(re.findall(devine[:4], txt.lower())) >= 1 and not R.get("decors_ia"):
            rq.append(_rq("directeur_artistique", None, f"la scène {k + 1} parle de « {devine} » mais le décor est « {l} »",
                          {"type": "lieu", "scene": k, "lieu": devine}, 0.8, "decor_incoherent"))
    tout = " ".join(q["texte"] for q in ph).lower()
    if not R.get("compagnons") and re.search(r"\b(elle|la dame|une femme|une fille|il|le type|un mec) (me|te|nous) (fait|regarde|attend|suit|appelle)\b", tout):
        q = next(q for q in ph if re.search(r"\b(me|te|nous) (fait|regarde|attend|suit|appelle)\b", q["texte"].lower()))
        f_ = bool(re.search(r"\b(elle|la dame|une femme|une fille)\b", tout))
        rq.append(_rq("directeur_artistique", q["deb"], "l'histoire parle d'une personne qu'on ne voit pas : il faut la montrer à côté",
                      {"type": "figurant", "avec": q["p"] if q["p"] != "narrateur" else (list(fiches) or ["presentateur"])[0], "genre": "f" if f_ else "h",
                       "age": 28, "geste": "signe" if "signe" in tout else "attend"}, 1.0, "personne_invisible"))
    if not R.get("separes") and len(re.findall(studio.APPEL, tout)) >= 2:
        rq.append(_rq("directeur_artistique", None, "ils se parlent au téléphone : chacun devrait être dans son propre décor",
                      {"type": "lieux_separes"}, 1.2, "appel_meme_lieu"))
    # --- son
    trous = [(a["fin"], b["deb"]) for a, b in zip(ph, ph[1:]) if b["deb"] - a["fin"] > 1.4]
    if trous and not doub: rq.append(_rq("son", trous[0][0], f"blanc de {trous[0][1] - trous[0][0]:.1f} s sans rien : ça casse le rythme", None, 0.8, "blanc_long"))
    dens = len(br) / total * 10
    if dens < 0.8 and not doub:
        cand = [q for q in parlees if q is not ph[-1] and not any(abs(t - q["fin"]) < 1.0 for _, t, _ in br)]
        q = max(cand, key=lambda z: (z["texte"].rstrip().endswith(("!", "?")), len(z["texte"]))) if cand else None
        rq.append(_rq("son", q["fin"] if q else None, f"peu de bruitages ({len(br)} en {total:.0f} s) : la vidéo manque de relief",
                      {"type": "bruitage", "replique": q["i"], "son": "boing" if q["texte"].rstrip().endswith("!") else "bulle"} if q else None, 0.8, "peu_de_bruitages"))
    if dens > 4.5: rq.append(_rq("son", None, "trop de bruitages : ils fatiguent l'oreille", None, 0.6, "trop_de_bruitages"))
    if rapport_tech and "ok" not in rapport_tech[:3]: rq.append(_rq("son", None, f"contrôle technique : {rapport_tech[:120]}", None, 1.5, "technique"))
    # --- spectateur TikTok
    q0 = ph[0]
    if q0["deb"] > 0.8: rq.append(_rq("spectateur", 0, f"la première parole arrive à {q0['deb']:.1f} s : on scrolle avant", None, 1.0, "accroche_lente"))
    if not doub and len(_mots(q0["texte"])) > 14 and not q0["texte"].rstrip().endswith(("?", "!")):
        rq.append(_rq("spectateur", 0, "la première réplique est longue et plate : l'accroche doit piquer dès la 1re seconde", None, 0.9, "accroche_plate"))
    for q in ph:
        d_ = max(0.3, q["fin"] - q["deb"])
        if len(q["texte"]) / d_ > 24: rq.append(_rq("spectateur", q["deb"], "sous-titres trop rapides à lire", None, 0.5, "sous_titres_rapides")); break
    if mini and total > 30: rq.append(_rq("spectateur", None, f"{total:.0f} s pour un gag éclair : trop long", None, 0.8, "trop_long"))
    if not mini and not doub and total < 40: rq.append(_rq("spectateur", None, f"{total:.0f} s pour un sketch long : trop court", None, 0.5, "trop_court"))
    jury = {}
    for c in CRITIQUES:
        l = sorted([x for x in rq if x["critique"] == c], key=lambda x: -x["poids"])
        jury[c] = {"note": round(max(2.0, 10.0 - sum(1.8 * x["poids"] for x in l)), 1), "remarques": l[:3]}
    return jury


# ------------------------------------------------------------------ jury IA (Claude, sinon Gemini / Mistral) : il regarde la vidéo (et l'original)
PROMPT = """Tu es un jury de 5 critiques exigeants d'une chaîne TikTok d'humour en dessin animé (personnages « toons » : grosse tête ronde
blanche, trait noir épais). Voici des images de NOTRE vidéo (numérotées, dans l'ordre, avec l'instant en secondes){origine}.
Texte et minutage :
{texte}
Mesures du robot : {mesures}
Remarques déjà trouvées par nos règles gratuites : {gratuit}{auteur}
Chaque critique donne CLAIREMENT son avis pour rendre la vidéo plus DRÔLE et meilleure : une note sur 10 et au plus 3 remarques
précises (moment en secondes, problème, et si possible une CORRECTION que le robot sait appliquer, de type : plan {{replique, plan, cible,
mouvement}}, reaction {{replique, reaction}}, bruitage {{replique, son}}, casting {{role, age, genre, taille, cheveux, barbe}},
figurant {{avec, genre, age, geste, haut, c_haut, description}}, lieux_separes {{rôle: décor en anglais}}, lieu {{scene, lieu}}, costume {{role, haut, c_haut}},
jeu {{replique, emotion, geste, intensite 1 à 3}} pour une grimace ou un geste plus exagéré).
- humoriste : les vannes font-elles rire ? la chute tombe-t-elle au bon moment ? où ajouter une réaction, un regard caméra, un bruitage ?
- realisateur : rythme des plans, serré / large, celui qui parle bien filmé, réactions, mouvements, faux raccords ;
- directeur_artistique : âge, sexe, taille et allure des personnages (un « fiston » est un ado ; jamais de grosse barbe ; jamais de barbe
  pour un enfant), tenues, décors, cohérence avec l'histoire, personnes dont on parle qu'on devrait voir, lieux différents (appel) ;
- son : synchronisation voix / lèvres, bruitages bien placés, volumes, blancs (jamais de rires enregistrés) ;
- spectateur : accroche dans la 1re seconde, moments d'ennui, envie de commenter ou de partager, fin ;
- TOUS : la FINESSE de l'image comme une chaîne pro en 4K ramenée en 1080p — traits nets et lisses, détails des personnages,
  décor du même style que les personnages (aplats, trait noir), aucun texte illisible dans le décor, aucun flou, couleurs
  harmonieuses ; signale chaque faiblesse visible dans "defauts" (gravité « mineur » ou « grave »).
{consigne_origine}Valeurs possibles — plan : {plans} ; mouvement : {mouvements} ; reaction : {reactions} ; son : {sons} ; geste : coucou, signe, danse, attend,
telephone, rit, boit ; lieu : {lieux}. Signale aussi les défauts d'image (sous-titre faux, texte coupé, personnage coupé en deux en plan serré,
image vide, deux personnages l'un sur l'autre, objet qui flotte dans le vide, main ou bras qui traverse un meuble ou un corps, faux raccord
d'une image à l'autre, personnage qui sort du décor) dans "defauts" avec la gravité « grave » ou « mineur ». Le style simple, les gags écrits dans le décor et les plans de réaction sont voulus.
Réponds avec l'outil jury."""
OUTIL = {"name": "jury", "description": "Avis des 5 critiques.", "input_schema": {"type": "object", "properties": {
    "critiques": {"type": "array", "items": {"type": "object", "properties": {
        "critique": {"type": "string", "enum": list(CRITIQUES)}, "note": {"type": "number"},
        "remarques": {"type": "array", "items": {"type": "object", "properties": {
            "moment": {"type": "number"}, "probleme": {"type": "string"}, "correction": {"type": "object"}}, "required": ["probleme"]}}},
        "required": ["critique", "note", "remarques"]}},
    "manques_origine": {"type": "array", "items": {"type": "string"}},
    "defauts": {"type": "array", "items": {"type": "object", "properties": {"image": {"type": "integer"}, "probleme": {"type": "string"},
                                                                          "gravite": {"type": "string"}}, "required": ["probleme", "gravite"]}}},
    "required": ["critiques", "defauts"]}}


def _instants(ph, total, n=16):
    t = [0.4] + [(q["deb"] + q["fin"]) / 2 for q in ph] + [max(0.5, total - 0.6)]
    if len(t) > n: t = [t[int(k * (len(t) - 1) / (n - 1))] for k in range(n)]
    return t


def jury_claude(video, R, sk, gratuit):
    """Mode payant : None si Claude est indisponible (crédit, clé, erreur)."""
    if os.environ.get("CONTROLE_VIDEO", "1") == "0" or not __import__("reseau").ia_disponible(): return None   # Claude, sinon Gemini / Mistral
    try:
        import controle, studio, bruitages, decor_dessin as DD
        ph = R.get("ph") or []; total = float(R.get("total") or 1)
        inst = _instants(ph, total)
        contenu = [{"type": "text", "text": "NOTRE VIDÉO : instants " + ", ".join(f"{k + 1} = {t:.1f} s" for k, t in enumerate(inst))}]
        contenu += [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(p).decode()}} for p in controle.planches(video, inst)]
        orig = ((sk.get("doublage") or {}).get("video_origine") or "")
        origine, consigne_o = "", ""
        if orig and os.path.exists(orig):                                  # lien TikTok : la vidéo d'origine aux MÊMES instants
            contenu.append({"type": "text", "text": "VIDÉO TIKTOK D'ORIGINE, aux mêmes instants :"})
            contenu += [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(p).decode()}} for p in controle.planches(orig, inst)]
            origine = ", puis celles de la VIDÉO TIKTOK D'ORIGINE aux mêmes instants"
            consigne_o = ("COMPARE avec l'original : liste dans \"manques_origine\" tout ce qu'on voit ou entend dans l'original et qui manque ou ne colle "
                          "pas chez nous (personnes, âge, sexe, lieux, objets, gestes, suite des plans, ambiance) et propose la correction qui le recrée.\n")
        texte = "\n".join(f"{q['deb']:.1f}–{q['fin']:.1f} s · {q['p']} : {q['texte']}" for q in ph)[:6000]
        mesures = f"durée {total:.0f} s, {len(R.get('plans') or [])} plans, bruitages {[(n, round(t, 1)) for n, t, _ in (R.get('bruitages') or [])][:20]}, " \
                  f"personnages {{{', '.join(f'{r}: {F.get(chr(103) + 'enre')}/{F.get(chr(97) + 'ge')} ans' for r, F in (R.get('fiches') or {}).items())}}}, lieux {R.get('lieux')}"
        gr = "; ".join(f"{NOMS[c]} : {x['probleme']}" for c in CRITIQUES for x in gratuit[c]["remarques"])[:1500] or "aucune"
        contenu.append({"type": "text", "text": PROMPT.format(origine=origine, texte=texte, mesures=mesures, gratuit=gr, consigne_origine=consigne_o, auteur="",
                                                              plans=", ".join(studio.PLANS), mouvements=", ".join(studio.MOUVEMENTS), reactions=", ".join(studio.REACTIONS),
                                                              sons=", ".join(bruitages.CATALOGUE), lieux=", ".join(DD.LIEUX)) + regles_apprises()})
        r = __import__("reseau").claude().messages.create(model=MODELE, max_tokens=4000, tools=[OUTIL], tool_choice={"type": "tool", "name": "jury"},
                                                         messages=[{"role": "user", "content": contenu}])
        res = next((b.input for b in r.content if getattr(b, "type", "") == "tool_use"), None)
        try:
            import ecrire; ecrire.compter(r, MODELE)
        except Exception: pass
        return res
    except Exception as e:
        print(f"Jury Claude indisponible ({str(e)[:140]}) : jury gratuit seul.", flush=True); return None


# ------------------------------------------------------------------ évaluation complète
def evaluer(video, R, sk, rapport_tech=""):
    """Jury gratuit toujours, jury Claude en plus quand il y a du crédit. Renvoie dict(note, jury, corrections, defauts_graves,
    manques_origine, rapport, source)."""
    g = jury_gratuit(R, sk, rapport_tech)
    jury, source, graves, manques = g, "gratuit", [], []
    c = jury_claude(video, R, sk, g)
    if isinstance(c, dict) and c.get("critiques"):
        jury, source = {}, "ia"
        for x in c["critiques"]:
            if isinstance(x, dict) and x.get("critique") in CRITIQUES:
                rem = [dict(critique=x["critique"], moment=r_.get("moment"), probleme=str(r_.get("probleme", ""))[:200],
                            correction=r_.get("correction") if isinstance(r_.get("correction"), dict) else None, poids=1.0, categorie=x["critique"])
                       for r_ in (x.get("remarques") or [])[:3] if isinstance(r_, dict)]
                try: note = float(x.get("note"))
                except (TypeError, ValueError): note = 6.0
                jury[x["critique"]] = {"note": round(min(10.0, max(0.0, note)), 1), "remarques": rem}
        for k in CRITIQUES:                                                # un critique oublié par Claude : l'avis gratuit
            jury.setdefault(k, g[k])
        for k in CRITIQUES:                                                # les corrections sûres des règles gratuites restent proposées
            deja = {json.dumps(r_.get("correction"), sort_keys=True) for r_ in jury[k]["remarques"]}
            for r_ in g[k]["remarques"]:
                if r_.get("correction") and r_["poids"] >= 1.2 and json.dumps(r_["correction"], sort_keys=True) not in deja: jury[k]["remarques"].append(r_)
        graves = [d for d in c.get("defauts") or [] if isinstance(d, dict) and "grave" in str(d.get("gravite", "")).lower()]
        manques = [str(m)[:160] for m in (c.get("manques_origine") or []) if not re.search(r"rires? (enregistr|du public|en bo[iî]te)|laugh", str(m).lower())][:8]   # jamais de rires enregistrés
    P = poids_critiques()
    note = round(sum(jury[k]["note"] * P.get(k, 1.0) for k in CRITIQUES) / sum(P.get(k, 1.0) for k in CRITIQUES), 1)
    corrections = [r_["correction"] for k in CRITIQUES for r_ in jury[k]["remarques"] if isinstance(r_.get("correction"), dict) and r_["correction"].get("type") in TYPES]
    rapport = " | ".join(f"{NOMS[k]} {jury[k]['note']}/10 : " + "; ".join((f"{r_['moment']} s " if r_.get("moment") is not None else "") + r_["probleme"]
                                                                          for r_ in jury[k]["remarques"]) for k in CRITIQUES)
    print(f"Jury qualité ({source}) : {note}/10 — {rapport[:900]}", flush=True)
    if manques: print("Manque par rapport à la vidéo d'origine : " + " ; ".join(manques), flush=True)
    corrections += corrections_des_remarques(sk, R, [r_["probleme"] for k in CRITIQUES for r_ in jury[k]["remarques"]] + manques, corrections)
    return dict(note=note, jury=jury, corrections=corrections, defauts_graves=graves, manques_origine=manques, rapport=rapport, source=source)


# ------------------------------------------------------------------ corrections automatiques
SEPARES_TXT = r"(chez lui|chez elle|son salon|dans (le|son) salon|canap[ée]|s[ée]par[ée]|deux (lieux|d[ée]cors)|m[êe]me endroit|tous les deux dans|au t[ée]l[ée]phone|split)"
INVISIBLE_TXT = r"(on ne (la |le )?voit (pas|jamais)|qu'on ne voit pas|pas assez (clairement )?visible|n'appara[iî]t pas|absente?|l'int[ée]grer|la montrer|le montrer|à c[ôo]t[ée] de lui)"

def corrections_des_remarques(sk, R, textes, deja):
    """Les critiques écrivent en clair ce qui manque (« le père doit être chez lui », « on ne voit pas la dame ») : on en tire les
    corrections que le moteur sait faire (un décor chacun, la personne dessinée à côté), même quand l'IA n'a pas rempli la case."""
    import studio
    t = " ".join(str(x) for x in textes).lower(); types = {c.get("type") for c in deja if isinstance(c, dict)}; out = []
    parlants = [r for r in dict.fromkeys(x["p"] for x in sk.get("repliques") or []) if r != "narrateur"]
    if "lieux_separes" not in types and not (R or {}).get("separes") and not sk.get("_separes") and len(parlants) >= 2 and re.search(SEPARES_TXT, t):
        out.append({"type": "lieux_separes"})
    if "figurant" not in types and not (R or {}).get("compagnons") and re.search(INVISIBLE_TXT, t):
        f = studio.figurants_devines(sk)
        if f: out.append(dict(f[0], type="figurant"))
    if out: print("Corrections tirées des remarques du jury : " + ", ".join(c["type"] for c in out), flush=True)
    return out
def corriger(sk, corrections):
    """Applique les corrections au « studio » du sketch (copie conseillée). Renvoie la liste des corrections appliquées (texte)."""
    import studio, bruitages, decor_dessin as DD
    S = sk.setdefault("studio", {}) if isinstance(sk.get("studio"), dict) or "studio" not in sk else {}
    if not isinstance(sk.get("studio"), dict): sk["studio"] = S
    reps = sk.get("repliques") or []; faites, vues = [], set()
    for c in corrections[:8]:
        cle = json.dumps(c, sort_keys=True, ensure_ascii=False)
        if cle in vues: continue
        vues.add(cle); t = c.get("type")
        try:
            if t == "plan" and 0 <= int(c["replique"]) < len(reps) and c.get("plan") in studio.PLANS:
                S["decoupe"] = [d for d in (S.get("decoupe") or []) if isinstance(d, dict) and d.get("replique") != int(c["replique"])]
                S["decoupe"].append({"replique": int(c["replique"]), "plans": [{"debut": 0.0, "plan": c["plan"], "cible": c.get("cible"), "mouvement": c.get("mouvement")}]})
                faites.append(f"plan {c['plan']} sur la réplique {int(c['replique']) + 1}")
            elif t == "reaction" and 0 <= int(c["replique"]) < len(reps) and c.get("reaction") in studio.REACTIONS:
                S["plans"] = [x for x in (S.get("plans") or []) if isinstance(x, dict) and x.get("replique") != int(c["replique"])] + \
                             [{"replique": int(c["replique"]), "reaction": c["reaction"]}]
                faites.append(f"réaction « {c['reaction']} » à la réplique {int(c['replique']) + 1}")
            elif t == "bruitage" and 0 <= int(c["replique"]) < len(reps) and c.get("son") in bruitages.CATALOGUE:
                S["bruitages"] = [x for x in (S.get("bruitages") or []) if isinstance(x, dict) and x.get("replique") != int(c["replique"])] + \
                                 [{"replique": int(c["replique"]), "son": c["son"]}]
                faites.append(f"bruitage « {c['son']} » à la réplique {int(c['replique']) + 1}")
            elif t == "casting" and c.get("role"):
                P = S.setdefault("personnages", {}); d = P.setdefault(c["role"], {})
                for k in ("age", "genre", "taille", "cheveux", "barbe", "corpulence"):
                    if k in c: d[k] = c[k]
                if c.get("barbe") == "" and isinstance(S.get("costumes"), dict) and isinstance(S["costumes"].get(c["role"]), dict):
                    S["costumes"][c["role"]]["details"] = [x for x in S["costumes"][c["role"]].get("details") or [] if "barbe" not in x and x != "moustache"]
                faites.append(f"casting de {c['role']} : " + ", ".join(f"{k} {c[k]}" for k in ("age", "genre", "taille", "barbe") if k in c))
            elif t == "figurant" and c.get("avec"):
                S["figurants"] = (S.get("figurants") or [])[:2] + [{k: c[k] for k in ("avec", "genre", "age", "geste", "haut", "c_haut", "bas", "description") if k in c}]
                faites.append(f"personne ajoutée à côté de {c['avec']} ({c.get('geste', 'attend')})")
            elif t == "lieux_separes" and not sk.get("_separes"):
                sep = {k: v for k, v in c.items() if k not in ("type",) and isinstance(v, str)}
                parlants = [r for r in dict.fromkeys(x["p"] for x in reps) if r != "narrateur"]
                S["lieux_separes"] = sep if len(sep) >= 2 else {r: "" for r in parlants[:2]}; S.setdefault("moyen", "telephone")
                if not isinstance(S.get("lieux_de"), dict): S["lieux_de"] = studio.lieux_devines(sk, list(S["lieux_separes"])[:2])
                faites.append("un décor pour chaque personnage (lieux séparés)")
            elif t == "lieu" and c.get("lieu") in DD.LIEUX:
                k = int(c.get("scene", 0)); L = list(S.get("lieux") or [])
                while len(L) <= k: L.append(None)
                L[k] = c["lieu"]; S["lieux"] = L; sk.setdefault("_decors_a_refaire", []).append(k)
                faites.append(f"décor de la scène {k + 1} : {c['lieu']}")
            elif t == "jeu" and 0 <= int(c["replique"]) < len(reps):
                S["jeu"] = [x for x in (S.get("jeu") or []) if isinstance(x, dict) and x.get("replique") != int(c["replique"])] + \
                           [{k: c[k] for k in ("replique", "emotion", "geste", "intensite") if k in c}]
                faites.append(f"jeu plus marqué à la réplique {int(c['replique']) + 1}")
            elif t == "costume" and c.get("role"):
                C = S.setdefault("costumes", {}); d = C.setdefault(c["role"], {})
                for k in ("haut", "c_haut", "bas", "c_bas", "chapeau", "chaussures"):
                    if k in c: d[k] = c[k]
                faites.append(f"tenue de {c['role']}")
        except (KeyError, TypeError, ValueError):
            continue
    return faites


# ------------------------------------------------------------------ mémoire : le robot apprend de ses critiques
def _lire():
    try:
        with open(MEMOIRE, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return []


def memoriser(Q, fichier, corrigees=None):
    m = _lire()
    m.append(dict(date=datetime.date.today().isoformat(), fichier=fichier, note=Q["note"], source=Q["source"],
                  notes={k: Q["jury"][k]["note"] for k in CRITIQUES},
                  categories=[r_.get("categorie") or k for k in CRITIQUES for r_ in Q["jury"][k]["remarques"]],
                  remarques=[r_["probleme"][:140] for k in CRITIQUES for r_ in Q["jury"][k]["remarques"]][:15],
                  manques=Q.get("manques_origine") or [], corrigees=corrigees or []))
    try:
        os.makedirs(os.path.dirname(MEMOIRE), exist_ok=True)
        with open(MEMOIRE, "w", encoding="utf-8") as f: json.dump(m[-300:], f, ensure_ascii=False, indent=1)
    except OSError: pass


LIBELLES = {"vanne_sans_bruitage": "des vannes sans accent sonore", "vanne_sans_reaction": "des vannes sans plan de réaction",
            "chute_longue": "des chutes trop longues", "chute_sans_zoom": "des chutes sans zoom choc", "repliques_longues": "des répliques trop longues",
            "montage_lent": "un montage trop lent", "parle_hors_champ": "celui qui parle trop peu filmé", "plans_courts": "des plans trop courts",
            "plans_repetes": "des plans répétés", "peu_de_reactions": "trop peu de réactions", "camera_monotone": "une caméra monotone",
            "age_incoherent": "des âges qui ne collent pas au dialogue", "barbe_enfant": "des barbes sur des enfants",
            "genre_incoherent": "un sexe qui ne colle pas à la voix", "decor_incoherent": "des décors qui ne collent pas à l'histoire",
            "personne_invisible": "des personnes dont on parle mais qu'on ne voit pas", "appel_meme_lieu": "des appels où les deux sont au même endroit",
            "blanc_long": "des blancs trop longs", "peu_de_bruitages": "trop peu de bruitages", "trop_de_bruitages": "trop de bruitages",
            "tete_coupee": "des têtes coupées par le bord de l'image", "chevauchement": "des personnages l'un sur l'autre",
            "sous_titre_visage": "des sous-titres sur les visages",
            "accroche_lente": "une accroche trop lente", "accroche_plate": "une accroche plate", "sous_titres_rapides": "des sous-titres trop rapides"}


REMARQUES_AUTEUR = os.path.join(os.path.dirname(MEMOIRE), "remarques_auteur.json")

def remarques_auteur(n=10):
    """Les dernières remarques écrites par l'auteur sur le site (prioritaires sur tout le reste)."""
    try: r = json.load(open(REMARQUES_AUTEUR, encoding="utf-8"))
    except (OSError, ValueError): return []
    return [x for x in r if isinstance(x, dict) and x.get("remarque")][-n:]

def regles_apprises(n=30):
    """Les erreurs qui reviennent dans les dernières vidéos, à éviter dès l'écriture et la mise en scène (consigne pour Claude),
    et les remarques de l'auteur (prioritaires)."""
    m = _lire()[-n:]
    c = Counter(x for e in m for x in set(e.get("categories") or []) if x in LIBELLES)
    freq = [LIBELLES[k] for k, v in c.most_common(6) if v >= 3]
    out = ("\nERREURS QUI REVIENNENT dans nos dernières vidéos (à éviter absolument) : " + ", ".join(freq) + ".") if freq else ""
    ra = remarques_auteur()
    if ra: out += "\nREMARQUES DE L'AUTEUR DE LA CHAÎNE sur nos dernières vidéos (à respecter EN PRIORITÉ) : " + " ; ".join(
        f"« {x['remarque'][:200]} »" + (f" (note {x['note']}/10)" if x.get("note") else "") for x in ra) + "."
    return out


def poids_critiques():
    """Poids de chaque critique dans la note globale : plus ses notes suivent les vues TikTok de nos vidéos, plus il compte."""
    try:
        import banque_visuelle; vues = banque_visuelle._vues()
    except Exception: vues = {}
    m = [e for e in _lire() if e.get("fichier") in vues and e.get("notes")]
    if len(m) < 6: return {k: 1.0 for k in CRITIQUES}
    v = [math.log1p(vues[e["fichier"]]) for e in m]; out = {}
    for k in CRITIQUES:
        x = [float(e["notes"].get(k, 6)) for e in m]
        mx, mv = sum(x) / len(x), sum(v) / len(v)
        cov = sum((a - mx) * (b - mv) for a, b in zip(x, v)); sx = math.sqrt(sum((a - mx) ** 2 for a in x)); sv = math.sqrt(sum((b - mv) ** 2 for b in v))
        r = cov / (sx * sv) if sx and sv else 0.0
        out[k] = round(min(1.6, max(0.5, 1.0 + r)), 2)
    return out
