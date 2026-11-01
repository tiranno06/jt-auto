"""« Dis ce qui ne va pas, le robot corrige » (choix de l'auteur, 1er novembre 2026, idée 12).

L'auteur écrit (ou dicte) une remarque sur une vidéo TikTok déjà faite : « à 12 s c'est l'autre qui parle », « elle devrait être
dans une cuisine », « le chat doit être noir ». Le bouton du site lance emission.yml avec refaire = « fichier|remarque|texte » :
même son d'origine, mêmes répliques (comme « Corriger qui parle »), et la remarque est TRADUITE en corrections que le moteur sait
faire : changer qui dit une réplique, et les corrections du jury (lieu, casting, costume, plan, réaction, bruitage, jeu, figurant,
lieux séparés). L'IA lit la remarque avec les répliques minutées ; sans IA, des règles simples comprennent les cas courants
(« à 12 s c'est l'autre », « dans une cuisine », « c'est un chat »). La remarque est aussi gardée pour le jury (prochaines vidéos)."""
import json, re

ROLES = ("presentateur", "invite", "envoyee", "narrateur")


def _replique_a(sk, t):
    """Réplique dite à l'instant t (en secondes)."""
    reps = sk.get("repliques") or []
    for k, r in enumerate(reps):
        if float(r.get("_deb", -1)) - 0.3 <= t <= float(r.get("_fin", -1)) + 0.3: return k
    return min(range(len(reps)), key=lambda k: abs(float(reps[k].get("_deb", 0)) - t)) if reps else None


def regles(sk, texte):
    """Ce que des règles simples comprennent : ({n° de réplique: rôle}, [corrections du jury])."""
    import decor_dessin as DD, animaux
    t = str(texte or "").lower().replace("’", "'"); reps = sk.get("repliques") or []
    roles = [r for r in dict.fromkeys(x.get("p") for x in reps) if r in ROLES and r != "narrateur"]
    qui, corr = {}, []
    for m in re.finditer(r"(?:à|a|vers)\s*(\d+(?:[.,]\d+)?)\s*(?:s\b|sec|secondes?)", t):   # « à 12 s c'est l'autre qui parle »
        reste = t[m.end():m.end() + 80]
        if re.search(r"l'autre|pas (lui|elle)|mauvais (perso|personnage)|inverse|c'est (lui|elle) qui", reste):
            k = _replique_a(sk, float(m.group(1).replace(",", ".")))
            if k is not None and len(roles) >= 2:
                p = reps[k].get("p"); qui[k] = next((r for r in roles if r != p), p)
    if re.search(r"tout (est )?invers|toutes les r[ée]pliques sont invers|les deux sont invers", t) and len(roles) == 2:
        for k, r in enumerate(reps):
            if r.get("p") in roles: qui[k] = roles[1 - roles.index(r["p"])]
    m = re.search(r"(?:dans|à|au|en)\s+(?:une|un|la|le|l')?\s*([a-zéèêàç' -]{3,30})", t)
    if m and re.search(r"devrai|doit|plut[ôo]t|pas dans|il faut|mettre|met", t):
        l_ = DD.lieu_de(m.group(1), "")
        if l_: corr += [{"type": "lieu", "scene": k, "lieu": l_} for k in range(max(1, len(sk.get("decoupage") or [])))]
    for e, mm in animaux.MOTS.items():                                     # « c'est un chat », « Maurice est censé être un chat »
        if re.search(r"\b(c'est|est|sont|en|[êe]tre|devient|devenir)\s+(?:un|une|le|la)?\s*(?:" + mm + r")\b", t) and roles:
            corr.append({"type": "casting", "role": role_nomme(sk, texte, roles), "espece": e}); break
    return qui, corr


def role_nomme(sk, texte, roles):
    """Le personnage dont la remarque dit le NOM (« Maurice est un chat ») : celui à qui les autres parlent (son nom est dit par
    l'autre). Sans nom reconnu : le dernier rôle."""
    reps = sk.get("repliques") or []
    for nom in re.findall(r"\b([A-ZÉÈ][a-zéèêëàâîïôöûüç]{2,})\b", str(texte or "")):
        n_ = re.escape(nom.lower()); score = {r: 0.0 for r in roles}; dit = {r: 0 for r in roles}
        for x in reps:
            t_, p_ = str(x.get("t", "")).lower(), x.get("p")
            if p_ not in score or not re.search(r"\b" + n_ + r"\b", t_): continue
            dit[p_] += 1
            if re.search(r"(m'?appel\w*|je suis|moi c'est)\s+" + n_, t_): score[p_] += 2       # « arrête de m'appeler Maurice » : c'est lui
            elif re.search(r"(^|[.!?…]\s*|\b(oh|h[ée]|eh|allez|viens)\s+)" + n_ + r"\b|" + n_ + r"\s*[,!?]", t_):   # « Oh Maurice, … » : on lui parle
                for r in roles:
                    if r != p_: score[r] += 1
        if len(roles) >= 2 and sum(dit.values()):
            if max(score.values()) > 0: return max(roles, key=lambda r: score[r])
            return min(roles, key=lambda r: dit[r])                       # c'est l'autre qui l'appelle par son nom
    return roles[-1] if roles else "invite"


def parle_de_qui_parle(texte):
    """La remarque parle-t-elle vraiment de QUI dit les répliques (instants, « l'autre », « inversé ») ?"""
    t = str(texte or "").lower().replace("’", "'")
    return bool(re.search(r"\d+\s*(s\b|sec)|l'autre|invers|pas (lui|elle)|mauvais (perso|personnage)|c'est (lui|elle) qui|qui dit|r[ée]plique", t))


def interpreter(sk, texte):
    """Remarque -> ({n° de réplique: rôle}, [corrections]). L'IA d'abord (elle voit les répliques minutées), les règles sinon."""
    qui, corr = regles(sk, texte)
    try:
        import reseau, ecrire, qualite
        if not reseau.ia_disponible(): raise RuntimeError("aucune IA")
        reps = sk.get("repliques") or []
        lignes = "\n".join(f"{k}. ({float(r.get('_deb', 0)):.1f}–{float(r.get('_fin', 0)):.1f} s) {r.get('p')} : {str(r.get('t'))[:140]}" for k, r in enumerate(reps))[:7000]
        P = ((sk.get("studio") or {}).get("personnages") or {}) if isinstance(sk.get("studio"), dict) else {}
        outil = {"name": "corrections", "description": "Corrections à faire sur la vidéo.", "input_schema": ecrire._schema({
            "qui": {"type": "array", "items": ecrire._schema({"replique": {"type": "integer"}, "personnage": {"type": "string", "enum": list(ROLES)}}, ["replique", "personnage"])},
            "corrections": {"type": "array", "items": {"type": "object"}},
            "compris": {"type": "string"}}, ["qui", "corrections", "compris"])}
        txt = (f"L'auteur d'une chaîne TikTok a regardé une de nos vidéos (dessin animé joué en play-back sur le son d'une vidéo TikTok) et "
               f"dit ce qui ne va pas :\n« {texte} »\n\nRépliques (numéro, instants, personnage qui la dit, texte) :\n{lignes}\n"
               f"Personnages : {json.dumps(P, ensure_ascii=False)[:800]}\nLieux actuels : {[sc.get('lieu') or sc.get('decor') for sc in sk.get('decoupage') or []]}\n\n"
               "Traduis sa remarque en corrections, SANS rien inventer d'autre :\n"
               "- \"qui\" : les répliques à rendre à un autre personnage ({replique, personnage}) ;\n"
               "- \"corrections\" : au format du moteur : lieu {type:lieu, scene, lieu parmi " + ", ".join(__import__("decor_dessin").LIEUX) + "}, "
               "casting {type:casting, role, age, genre (h/f), taille, cheveux, barbe, espece (chat, chien, lapin, souris, oiseau, poisson, steak, "
               "pizza, oeuf, banane, voiture, frigo, telephone, verre, croissant)}, costume {type:costume, role, haut, c_haut [r,g,b]}, "
               "reaction {type:reaction, replique, reaction}, bruitage {type:bruitage, replique, son}, jeu {type:jeu, replique, emotion, geste, intensite}, "
               "figurant {type:figurant, avec, genre, age, geste}, lieux_separes {type:lieux_separes} ;\n- \"compris\" : en une phrase, ce que tu as compris.\n"
               "Réponds avec l'outil corrections.")
        r = ecrire._appel(reseau.claude(raisonner=True), None, [{"role": "user", "content": txt}], outil, max_tokens=1500)
        for x in ecrire._liste(r.get("qui")):
            try:
                k = int(x.get("replique")); p_ = str(x.get("personnage"))
                if 0 <= k < len(reps) and p_ in ROLES: qui[k] = p_
            except (AttributeError, TypeError, ValueError): pass
        ia_qui = {k: v for k, v in qui.items() if v != reps[k].get("p")}
        if ia_qui and not parle_de_qui_parle(texte) and len(ia_qui) > max(2, len(reps) // 3):   # « Maurice est un chat » ≠ tout inverser
            print(f"Remarque : l'IA voulait changer qui dit {len(ia_qui)} réplique(s) alors que la remarque n'en parle pas : refusé", flush=True)
            qui = dict(regles(sk, texte)[0])
        deja = {json.dumps(c, sort_keys=True) for c in corr}
        esp_regle = any(c.get("type") == "casting" and c.get("espece") for c in corr)   # espèce comprise par les règles : elle prime
        corr += [c for c in ecrire._liste(r.get("corrections")) if isinstance(c, dict) and c.get("type") in qualite.TYPES and json.dumps(c, sort_keys=True) not in deja
                 and not (esp_regle and c.get("type") == "casting" and c.get("espece"))]
        if r.get("compris"): print(f"Remarque comprise : {str(r['compris'])[:200]}", flush=True)
    except Exception as e: print(f"Remarque lue par les règles simples ({str(e)[:100]})", flush=True)
    print(f"Remarque de l'auteur : {len(qui)} réplique(s) à rendre à un autre personnage, {len(corr)} correction(s) : "
          + ", ".join(c.get("type", "?") for c in corr), flush=True)
    return qui, corr


def appliquer(sk, texte):
    """Applique la remarque au sketch (copie conseillée). Renvoie la liste lisible des changements."""
    import qualite
    qui, corr = interpreter(sk, texte)
    faits = []
    for k, r_ in qui.items():
        if 0 <= k < len(sk.get("repliques") or []) and sk["repliques"][k].get("p") != r_:
            sk["repliques"][k]["p"] = r_; faits.append(f"réplique {k + 1} -> {r_}")
    for c in corr:                                                         # espèce : pas encore dans qualite.corriger
        if c.get("type") == "casting" and c.get("espece"):
            S = sk.setdefault("studio", {}) if isinstance(sk.get("studio"), dict) or "studio" not in sk else {}
            if isinstance(S, dict): S.setdefault("personnages", {}).setdefault(c.get("role"), {})["espece"] = c["espece"]; faits.append(f"{c.get('role')} : {c['espece']}")
    faits += qualite.corriger(sk, [c for c in corr if not (c.get("type") == "casting" and set(c) <= {"type", "role", "espece"})])
    try:                                                                   # le jury la retient pour les prochaines vidéos
        import os
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "remarques_auteur.json")
        L = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else []
        import datetime
        if isinstance(L, list): L.append({"date": datetime.date.today().isoformat(), "remarque": str(texte)[:600], "source": "corriger"}); json.dump(L[-200:], open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception: pass
    return faits
