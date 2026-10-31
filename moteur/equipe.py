"""L'équipe de fabrication des sons TikTok (demande de l'auteur, 31 octobre 2026) : chaque poste a son contrôleur, qui vérifie le
travail AVANT de le passer au poste suivant, corrige ce qu'il peut tout seul et note le reste dans le bulletin de la vidéo
(sk["equipe"], journal de fabrication). Puis viennent le pré-jury, le contrôle image par image et le jury (qualite.py).

  1. Ingé son       : transcription complète (pas de boucle de Whisper, pas de mots impossibles, pas de voix sans texte).
  2. Casting voix   : qui dit chaque phrase. Trois témoins votent : le SON (empreinte vocale), le TEXTE (questions / réponses,
                      relu par l'IA) et l'IMAGE de la vidéo d'origine (qui bouge quand la phrase est dite, regard.py). Quand ils ne
                      sont pas d'accord, le fil du dialogue est repris phrase par phrase avec les trois.
  3. Scripte        : cohérence (une réplique = une seule personne, un appel seulement si le son en parle, téléphone en main
                      seulement s'il en est question, voix de femme = personnage féminin, autant de personnages que de voix).
  4. Monteur        : synchronisation (répliques dans l'ordre, sans chevauchement d'un même personnage, mots dans leur réplique,
                      rien au-delà de la fin du son)."""
import os, re
from collections import Counter

VOIX_SEULE_MAX = 0.85        # dans un dialogue, une voix qui dit plus de 85 % du texte : à revérifier
DESACCORD_MAX = 0.3          # plus de 30 % des phrases où l'image contredit le son : on reprend le fil


def journal(m): print(m, flush=True)


class Bulletin:
    def __init__(self): self.lignes = []
    def note(self, poste, controle, ok, detail="", revoir=False):
        """revoir=True : un défaut que le contrôleur n'a pas pu corriger seul -> « ⚠️ à vérifier » sur le site."""
        self.lignes.append({"poste": poste, "controle": controle, "ok": bool(ok), "detail": str(detail)[:200], "revoir": bool(revoir and not ok)})
        journal(f"  [équipe · {poste}] {'✔' if ok else '✘'} {controle}{' : ' + str(detail) if detail else ''}")
    def resume(self):
        ko = [l for l in self.lignes if not l["ok"]]
        return f"{len(self.lignes) - len(ko)}/{len(self.lignes)} contrôles bons" + (f" ; à revoir : {', '.join(l['controle'] for l in ko)}" if ko else "")


# ------------------------------------------------------------------ 1. ingé son
def inge_son(mots, B):
    if not mots: B.note("ingé son", "transcription", False, "aucun mot"); return mots
    import locuteurs
    seuls = 0                                                              # « ? » ou « ... » isolés : collés au mot d'avant
    for i in range(len(mots) - 1, 0, -1):
        if not re.search(r"\w", mots[i]["w"]):
            mots[i - 1] = dict(mots[i - 1], w=mots[i - 1]["w"] + mots[i]["w"].strip(), e=max(mots[i - 1]["e"], mots[i]["e"])); del mots[i]; seuls += 1
    if seuls: journal(f"  [équipe · ingé son] {seuls} signe(s) de ponctuation isolé(s) recollé(s)")
    n0 = len(mots); mots = locuteurs.sans_boucles(mots)
    B.note("ingé son", "pas de phrase répétée en boucle", n0 == len(mots), f"{n0 - len(mots)} mot(s) retiré(s)" if n0 != len(mots) else "")
    rapides = [m for m in mots if m["e"] - m["s"] < 0.03 and len(re.sub(r"\W", "", m["w"])) > 3]
    B.note("ingé son", "mots à une vitesse possible", len(rapides) <= 0.05 * len(mots), f"{len(rapides)} mot(s) trop courts" if rapides else "")
    trous = [(round(a["e"], 1), round(b["s"], 1)) for a, b in zip(mots, mots[1:]) if b["s"] - a["e"] > 6]
    B.note("ingé son", "pas de long passage sans texte", not trous, f"blancs {trous[:3]}" if trous else "")
    return mots


# ------------------------------------------------------------------ 2. casting voix
def casting_voix(mots, video, B, relire, scinder):
    """Qui dit chaque phrase : le son a déjà parlé (pyannote, ECAPA, vérification mot par mot) ; le contrôleur fait voter le texte
    et l'image et reprend le fil du dialogue quand ils contredisent le son. relire / scinder : fonctions de doublage.py."""
    import locuteurs, regard
    ph = locuteurs.phrases(mots)
    voix = Counter(m["voix"] for m in mots); r_ = locuteurs.ETAT.get("ressemblance")
    vue = None
    try: vue = regard.temoin(video, mots, ph) if len(ph) >= 3 else None
    except Exception as e: journal(f"  témoin image impossible ({str(e)[:100]})")
    if vue: B.note("casting voix", "témoin image (qui bouge dans l'original)", True, f"{sum(1 for c, _ in vue if c is not None)}/{len(ph)} phrases lisibles")
    seule = len(voix) == 1
    if r_ is not None: journal(f"  ressemblance des deux voix : {r_:.2f} (au-delà de {locuteurs.DOUTE} : le dialogue décide avec le son)")
    raison = None
    if seule: raison = "une seule voix entendue"
    elif r_ is not None and r_ > locuteurs.DOUTE: raison = f"voix proches ({r_:.2f})"
    elif len(voix) == 2:
        d = locuteurs.desaccord_image(mots, vue, ph)
        if d > DESACCORD_MAX: raison = f"l'image contredit le son sur {round(100 * d)} % des phrases"
        B.note("casting voix", "le son et l'image sont d'accord", d <= DESACCORD_MAX, f"{round(100 * d)} % de désaccord" if vue else "pas d'image lisible")
    if raison:
        ia = relire(mots, une_voix=seule)
        cotes = Counter(c for c, w in (vue or []) if c is not None and w >= 0.15)
        deux_a_l_image = len(cotes) == 2 and min(cotes.values()) >= 2      # sans IA : l'image montre deux personnes qui parlent tour à tour
        if ia or (vue and (not seule or deux_a_l_image)):
            avis = None if seule or (r_ is not None and r_ > locuteurs.PROCHES) else 1.2
            mots = locuteurs.fil_dialogue(mots, ia, avis=avis, vue=vue)
            B.note("casting voix", "fil du dialogue repris (son + texte + image)", True, raison)
        elif seule: B.note("casting voix", "deux personnes trouvées", False, "une seule voix et pas de relecture possible : un seul personnage parle", revoir=True)
    elif len(voix) == 2:
        n0 = Counter(m["voix"] for m in mots)
        mots = scinder(mots)
        if Counter(m["voix"] for m in mots) != n0: B.note("casting voix", "voix dominante partagée (même voix pour deux personnes)", True)
    n = Counter(m["voix"] for m in mots)
    part = max(n.values()) / max(1, sum(n.values()))
    questions = sum(1 for p in ph if mots[p[-1]]["w"].endswith("?"))
    B.note("casting voix", "parole répartie entre les personnages", len(n) > 1 or questions < 2,
           f"{len(n)} voix, la plus bavarde dit {round(100 * part)} %")
    if len(n) > 1 and part > VOIX_SEULE_MAX and questions >= 3:
        B.note("casting voix", "dialogue équilibré", False, f"une voix dit {round(100 * part)} % d'un dialogue à {questions} questions", revoir=True)
    return mots


# ------------------------------------------------------------------ 3. scripte
def scripte(sk, segs, hz, B):
    import studio
    reps = sk.get("repliques") or []
    dbl = [k for k, s in enumerate(segs) if re.search(r"\?\s+\S", s.get("t", "")) and not (s.get("mots") and all(m.get("sure", 0) >= 0.5 for m in s["mots"]))]
    B.note("scripte", "une réplique = une seule personne", not dbl, f"répliques {dbl[:6]} : question et réponse ensemble" if dbl else "", revoir=True)
    S = sk.get("studio") if isinstance(sk.get("studio"), dict) else {}
    if S.get("lieux_separes") and not studio.appel_devine(sk):
        B.note("scripte", "appel seulement si le son en parle", False, "lieux séparés de l'IA refusés"); S.pop("lieux_separes", None)
    tel = [k for k, r in enumerate(reps) if r.get("objet") == "telephone" and not re.search(r"t[ée]l[ée]phone|portable|appel|allô|allo|message|photo|insta|snap", r.get("t", "").lower())]
    if studio.appel_devine(sk): tel = []                                   # un appel : le téléphone a toute sa place
    for k in tel: reps[k].pop("objet", None)
    B.note("scripte", "téléphone en main seulement s'il en est question", not tel, f"retiré sur {len(tel)} réplique(s)" if tel else "")
    nb_voix = len({s["voix"] for s in segs}); nb_roles = len({r["p"] for r in reps if r["p"] != "narrateur"})
    B.note("scripte", "autant de personnages que de voix", nb_roles >= min(nb_voix, 3), f"{nb_voix} voix, {nb_roles} personnage(s)")
    return sk


# ------------------------------------------------------------------ 4. monteur
def monteur(sk, duree, B, segs=None):
    """Monteur : vérifie ET corrige la synchronisation avant le dessin (segs = segments du son, même ordre que les répliques) :
    mots hors de leur réplique (la réplique s'élargit), rien après la fin du son, répliques remises dans l'ordre du son (découpage
    renuméroté), un personnage qui se chevauche lui-même (la 1re réplique s'arrête où commence la suivante)."""
    reps = sk.get("repliques") or []
    S_ = segs if segs is not None and len(segs) == len(reps) else None
    def caler(k, deb=None, fin=None):
        if deb is not None:
            reps[k]["_deb"] = round(float(deb), 3)
            if S_: S_[k]["deb"] = float(deb)
        if fin is not None:
            reps[k]["_fin"] = round(float(fin), 3)
            if S_: S_[k]["fin"] = float(fin)
    # 1) chaque mot dans sa réplique
    mal = []
    for k, r in enumerate(reps):
        if S_ and S_[k].get("mots"):
            a, b = min(float(m["s"]) for m in S_[k]["mots"]), max(float(m["e"]) for m in S_[k]["mots"])
        elif r.get("_mots"):
            a, b = float(r["_deb"]) + min(w[1] for w in r["_mots"]), float(r["_deb"]) + max(w[2] for w in r["_mots"])
        else: continue
        if a < float(r["_deb"]) - 0.05 or b > float(r["_fin"]) + 0.3:
            mal.append(k); caler(k, deb=min(a, float(r["_deb"])), fin=max(b, float(r["_fin"])))
    B.note("monteur", "chaque mot dans sa réplique (lèvres et sous-titres calés)", True, f"{len(mal)} réplique(s) élargie(s) autour de leurs mots" if mal else "")
    # 2) durée et fin du son
    vides = [k for k, r in enumerate(reps) if float(r["_fin"]) <= float(r["_deb"])]
    for k in vides: caler(k, fin=float(reps[k]["_deb"]) + 0.25)
    B.note("monteur", "chaque réplique a une durée", True, f"{len(vides)} corrigée(s)" if vides else "")
    hors = [k for k, r in enumerate(reps) if duree and float(r["_fin"]) > duree + 0.5]
    for k in hors: caler(k, fin=max(float(reps[k]["_deb"]) + 0.2, float(duree)))
    B.note("monteur", "rien après la fin du son", True, f"{len(hors)} réplique(s) raccourcie(s)" if hors else "")
    # 3) ordre du son
    ordre = sorted(range(len(reps)), key=lambda k: (float(reps[k]["_deb"]), k))
    if ordre != list(range(len(reps))):
        chute = any(r.get("chute") for r in reps)
        nouveau = {old: new for new, old in enumerate(ordre)}
        reps[:] = [reps[k] for k in ordre]
        if S_: S_[:] = [S_[k] for k in ordre]
        for r in reps: r.pop("chute", None)
        if chute and reps: reps[-1]["chute"] = True
        for sc in sk.get("decoupage") or []:
            sc["repliques"] = sorted(nouveau[i] for i in sc.get("repliques") or [] if i in nouveau)
        n_dep = sum(1 for k, o in enumerate(ordre) if k != o)
        B.note("monteur", "répliques dans l'ordre du son", True, f"{n_dep} réplique(s) remise(s) à leur place")
    else: B.note("monteur", "répliques dans l'ordre du son", True)
    # 4) un personnage ne parle jamais deux fois en même temps
    chev, reste = [], []
    for k in range(1, len(reps)):
        p_ = next((j for j in range(k - 1, -1, -1) if reps[j]["p"] == reps[k]["p"]), None)
        if p_ is None or float(reps[k]["_deb"]) >= float(reps[p_]["_fin"]) - 0.05: continue
        if float(reps[k]["_deb"]) - 0.02 - float(reps[p_]["_deb"]) >= 0.15: chev.append(k); caler(p_, fin=float(reps[k]["_deb"]) - 0.02)
        else: reste.append(k)
    B.note("monteur", "un personnage ne parle jamais deux fois en même temps", not reste,
           (f"{len(chev)} corrigé(s)" if chev else "") + (f" ; répliques {reste[:6]} à revoir" if reste else ""), revoir=True)
    return sk


def deux_transcriptions(mots, autre, B, troisieme=None):
    """Ingé son : le même son transcrit par deux outils (Groq et le Whisper de la machine). Là où ils entendent un mot différent, l'IA
    choisit d'après le sens de la phrase (sinon on garde le premier) ; les instants des mots ne changent pas. Taux d'accord noté."""
    import difflib
    nu = lambda w: re.sub(r"[^\w'’-]", "", str(w).lower())
    a, b = [nu(m["w"]) for m in mots], [nu(m["w"]) for m in autre]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    egaux = sum(bl.size for bl in sm.get_matching_blocks()); accord = egaux / max(1, len(a))
    doutes = []                                                            # (indices dans mots, mots de l'autre transcription)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "replace" and i2 - i1 == j2 - j1 and i2 - i1 <= 4: doutes.append((list(range(i1, i2)), [autre[j]["w"] for j in range(j1, j2)]))
    choix, votes = {}, 0
    if doutes and troisieme:                                               # 3e écoute : la majorité tranche, l'IA seulement pour le reste
        try: c = troisieme() or []
        except Exception: c = []
        if c:
            cw = [nu(m["w"]) for m in c]; vu = {}
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, cw, autojunk=False).get_opcodes():
                if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
                    for i, j in zip(range(i1, i2), range(j1, j2)): vu[i] = cw[j]
            for k, (idx, alt) in enumerate(doutes):
                if not all(i in vu for i in idx): continue
                trois = [vu[i] for i in idx]
                if trois == [nu(w) for w in alt]: choix[k] = "B"; votes += 1
                elif trois == [a[i] for i in idx]: choix[k] = "A"; votes += 1
    reste = [k for k in range(len(doutes)) if k not in choix]
    if reste:
        ia = _arbitrer(mots, [doutes[k] for k in reste])
        for n_, k in enumerate(reste):
            if n_ in ia: choix[k] = ia[n_]
    for k, (idx, alt) in enumerate(doutes):
        if choix.get(k) == "B":
            for i, w in zip(idx, alt):                                     # le mot de B, avec la ponctuation de A
                fin = re.search(r"[.,!?…;:]*$", mots[i]["w"]).group()
                mots[i] = dict(mots[i], w=re.sub(r"[.,!?…;:]+$", "", w.strip()) + fin)
    B.note("ingé son", "deux transcriptions d'accord", accord >= 0.85,
           f"{round(100 * accord)} % de mots identiques, {len(doutes)} doute(s)" + (f", {votes} tranché(s) par une 3e écoute" if votes else "")
           + f", {sum(1 for v in choix.values() if v == 'B')} corrigé(s)")
    return mots


def _arbitrer(mots, doutes):
    """L'IA choisit, pour chaque doute, la version qui a du sens dans la phrase : {n° du doute: "A" | "B"}."""
    import ecrire, reseau
    if not reseau.ia_disponible(): return {}
    lignes = []
    for k, (idx, alt) in enumerate(doutes[:40]):
        g, d = max(0, idx[0] - 8), min(len(mots), idx[-1] + 9)
        avant = " ".join(m["w"] for m in mots[g:idx[0]]); apres = " ".join(m["w"] for m in mots[idx[-1] + 1:d])
        lignes.append(f"{k}. …{avant} [A : {' '.join(mots[i]['w'] for i in idx)} | B : {' '.join(alt)}] {apres}…")
    outil = {"name": "choix", "description": "La bonne version de chaque passage.",
             "input_schema": ecrire._schema({"choix": {"type": "array", "items": ecrire._schema({"n": {"type": "integer"}, "version": {"type": "string", "enum": ["A", "B"]}}, ["n", "version"])}}, ["choix"])}
    txt = ("Deux logiciels ont transcrit le même dialogue en français (sketch TikTok, langage parlé, argot). Pour chaque passage, "
           "dis quelle version (A ou B) est la bonne, d'après le sens de la phrase :\n\n" + "\n".join(lignes))
    try: r = ecrire._appel(reseau.claude(raisonner=True), None, [{"role": "user", "content": txt}], outil, max_tokens=2000)
    except Exception as e: journal(f"  arbitrage des deux transcriptions impossible ({str(e)[:100]})"); return {}
    out = {}
    for x in ecrire._liste(r.get("choix")):
        try:
            if x.get("version") in ("A", "B"): out[int(x.get("n"))] = x["version"]
        except (AttributeError, TypeError, ValueError): pass
    return out
