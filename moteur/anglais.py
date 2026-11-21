"""Sous-titres anglais en plus du français (choix de l'auteur du 21 novembre 2026, idée 3 de l'analyse « vues partout dans le
monde ») : une petite ligne anglaise AU-DESSUS du sous-titre français, pour qu'une personne qui ne parle pas français suive
l'histoire (TikTok ne peut pas traduire un texte incrusté dans l'image).

Traduction par l'IA (gratuite d'abord : `reseau.claude()`), consigne : garder l'humour, anglais parlé naturel, court ; acceptée
seulement si elle donne une ligne par réplique. Rien n'est inventé : sans traduction propre, la vidéo garde le français seul.

Réglage SOUS_TITRES_EN : « 0 » = jamais, « 1 » = toujours ; vide (par défaut) = ESSAI sur les 10 prochaines vidéos TikTok
(historique "anglais"), puis plus rien tant que l'auteur ne choisit pas « 1 » : le bloc « 📈 Ce qui marche » compare les vues
des vidéos avec et sans anglais."""
import os, re

ESSAI = 10


def actif(historique=None):
    v = (os.environ.get("SOUS_TITRES_EN") or "").strip()
    if v in ("0", "1"): return v == "1"
    faites = sum(1 for h in (historique or []) if h.get("anglais") and not h.get("essai"))
    return faites < ESSAI


CONSIGNE = """Traduis en anglais ces répliques d'un petit dialogue comique (sous-titres d'une vidéo TikTok en dessin animé).
Règles : anglais parlé naturel et court (comme un vrai sous-titre), garde l'humour et le ton (argot -> argot anglais équivalent,
insultes adoucies au même niveau), garde les prénoms, ne rajoute rien, ne résume pas. Une traduction par réplique, même ordre,
même nombre ({n}).

{lignes}"""


def _propre(t):
    t = re.sub(r"\[[^\]]*\]", "", str(t or "")).replace("\n", " ")
    return re.sub(r"\s+", " ", t).strip().strip('"').strip()


def traduire(textes):
    """Liste des traductions (même longueur) ou None."""
    import ecrire, reseau
    textes = [str(t or "").strip() for t in textes]
    if not textes or not reseau.ia_disponible(): return None
    lignes = "\n".join(f"{k}. {t}" for k, t in enumerate(textes))
    outil = {"name": "traduction", "description": "Traduction anglaise de chaque réplique.",
             "input_schema": ecrire._schema({"lignes": {"type": "array", "items": ecrire._schema(
                 {"n": {"type": "integer"}, "en": {"type": "string"}}, ["n", "en"])}}, ["lignes"])}
    for essai in range(2):
        try:
            cl = reseau.claude() if not essai else reseau.claude(exclure=("mistral",))
            r = ecrire._appel(cl, None, [{"role": "user", "content": CONSIGNE.format(n=len(textes), lignes=lignes)}], outil, max_tokens=4000)
        except Exception as e:
            print(f"  sous-titres anglais : traduction impossible ({str(e)[:100]})", flush=True); continue
        out = [None] * len(textes)
        for x in ecrire._liste((r or {}).get("lignes")):
            try:
                n = int(x.get("n")); en = _propre(x.get("en"))
                if 0 <= n < len(textes) and en: out[n] = en[:220]
            except (AttributeError, TypeError, ValueError): pass
        manque = [k for k, t in enumerate(textes) if re.search(r"\w", t) and not out[k]]
        if not manque and any(out): return [o or "" for o in out]
    return None


def preparer(sk, historique=None):
    """sk["_anglais"] = traduction de chaque réplique (vidéos sur un son TikTok), si le réglage le veut."""
    if sk.get("_anglais") is not None or not actif(historique): return sk.get("_anglais")
    reps = sk.get("repliques") or []
    en = traduire([r.get("t") for r in reps]) if reps else None
    if en:
        sk["_anglais"] = en; print(f"  sous-titres anglais : {sum(1 for x in en if x)} réplique(s) traduite(s)", flush=True)
    else: print("  sous-titres anglais : pas de traduction propre, français seul", flush=True)
    return en


def repartir(en, groupes):
    """Coupe la traduction d'une réplique en autant de morceaux que de groupes de sous-titres français (au prorata de leur
    longueur) : chaque morceau s'affiche en même temps que son groupe. Renvoie [texte anglais par groupe]."""
    mots = str(en or "").split()
    if not mots or not groupes: return [""] * len(groupes)
    if len(groupes) == 1 or len(mots) <= 3: return [" ".join(mots)] + [None] * (len(groupes) - 1)   # None = garder le précédent
    longs = [max(1, len(g[0])) for g in groupes]; tot = sum(longs)
    out, k, cum = [], 0, 0
    for j, L in enumerate(longs):
        cum += L
        fin = len(mots) if j == len(longs) - 1 else max(k, round(len(mots) * cum / tot))
        out.append(" ".join(mots[k:fin])); k = fin
    # un morceau vide (groupe très court) : il garde le texte du précédent
    return [o if o else None for o in out]
