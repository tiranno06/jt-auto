"""Lèvres synchronisées sur les SONS (et non plus seulement sur le volume de la voix) : chaque mot est découpé en sons du
français (phonétique simplifiée : « eau » = o, « ou » = ou, « ch » = ch, lettres muettes en fin de mot…), puis chaque son reçoit
sa forme de bouche (« viseme ») à l'instant exact où il est prononcé, grâce aux instants des mots (transcription) ou, à défaut, aux
groupes de sous-titres. Gratuit, sans IA.

Formes : A (grande ouverte), E (étirée), I (sourire serré), O (ronde), U (lèvres en avant), M (fermée : m, b, p),
F (lèvre sur les dents : f, v), S (dents serrées : s, z), T (petite ouverture, langue : t, d, n, l), CH (lèvres en avant, dents : ch, j)."""
import bisect, re, unicodedata

VOYELLES = "aàâeéèêëiîïoôöuùûüyœæ"
# graphies de plusieurs lettres (les plus longues d'abord) : (graphie, formes)
GRAPHIES = [("eaux", "O"), ("eau", "O"), ("aux", "O"), ("oeu", "O"), ("œu", "O"), ("ain", "E"), ("ein", "E"), ("oin", "UE"),
            ("ch", "CH"), ("ph", "F"), ("gn", "T"), ("qu", ""), ("gu", ""), ("ou", "U"), ("où", "U"), ("oû", "U"), ("oi", "UA"),
            ("oy", "UA"), ("au", "O"), ("ai", "E"), ("ei", "E"), ("eu", "O"), ("an", "A"), ("am", "A"), ("en", "A"), ("em", "A"),
            ("on", "O"), ("om", "O"), ("in", "E"), ("im", "E"), ("un", "E"), ("um", "E"), ("er", "E"), ("ez", "E"), ("et", "E"), ("es", "E")]
LETTRE = {**{c: "A" for c in "aàâ"}, **{c: "E" for c in "eéèêëæ"}, **{c: "I" for c in "iîïy"}, **{c: "O" for c in "oôöœ"},
          **{c: "U" for c in "uùûü"}, **{c: "M" for c in "mbp"}, **{c: "F" for c in "fv"}, **{c: "S" for c in "szçx"},
          **{c: "T" for c in "tdnl"}, "j": "CH", "w": "U"}
POIDS = {"A": 1.0, "E": 0.9, "I": 0.85, "O": 1.0, "U": 0.9, "M": 0.55, "F": 0.6, "S": 0.6, "T": 0.45, "CH": 0.65, "": 0.4}
NASALES = ("an", "am", "en", "em", "on", "om", "in", "im", "un", "um", "ain", "ein", "oin")
COURTS = {"est": "E", "et": "E", "les": "E", "des": "E", "mes": "E", "tes": "E", "ses": "E", "ces": "E", "il": "IT", "elle": "ET",
          "oui": "UI", "ok": "O", "eh": "E", "ah": "A", "oh": "O", "hein": "E", "bah": "MA", "ben": "MA", "mais": "ME", "non": "TO"}


def _sans_muettes(m):
    """Lettres muettes de fin de mot (« petit », « grands », « parle », « ils parlent ») et h muet."""
    m = re.sub(r"(?<!c)h", "", m)
    if len(m) > 4 and m.endswith("ent") and not m.endswith(("ment", "dent")): m = m[:-3] + "e"
    if len(m) > 2 and m.endswith(("er", "ez", "et")): return m
    while len(m) > 2 and m[-1] in "sxtdzp": m = m[:-1]
    if len(m) > 2 and m.endswith("e") and m[-2] not in VOYELLES: m = m[:-1]
    return m


def phonemes(mot):
    """Liste des formes de bouche d'un mot, dans l'ordre (consonnes « neutres » r, k, g, h : forme vide = garder la voisine)."""
    m = unicodedata.normalize("NFC", (mot or "").lower())
    m = re.sub(r"[^a-zàâçéèêëîïôöùûüœæ'-]", "", m).replace("-", "").split("'")[-1]
    if not m: return []
    if m in COURTS: return [c for c in re.findall(r"CH|[A-Z]", COURTS[m])]
    m = _sans_muettes(m)
    out, k = [], 0
    while k < len(m):
        for g, v in GRAPHIES:
            if m.startswith(g, k):
                if g in NASALES and k + len(g) < len(m) and (m[k + len(g)] in VOYELLES or m[k + len(g)] in "nm"): continue   # « ami », « bonne » : pas nasal
                if g in ("er", "ez", "et", "es") and k + len(g) < len(m): continue                # seulement en fin de mot
                out += re.findall(r"CH|[A-Z]", v) or [""]; k += len(g); break
        else:
            c = m[k]
            if c == "c": out.append("S" if k + 1 < len(m) and m[k + 1] in "eiyéèê" else "")
            elif c == "g": out.append("CH" if k + 1 < len(m) and m[k + 1] in "eiyéèê" else "")
            else: out.append(LETTRE.get(c, ""))
            k += 1
    sans_doublon = []
    for v in out:
        if not sans_doublon or v != sans_doublon[-1] or v == "": sans_doublon.append(v)
    return sans_doublon


def _mots_des_groupes(groupes):
    """Instants de chaque mot, répartis dans les groupes de sous-titres au prorata de leurs sons."""
    out = []
    for g in groupes or []:
        mots = str(g[0]).split()
        if not mots: continue
        poids = [max(0.5, sum(POIDS.get(v, 0.4) for v in phonemes(w))) for w in mots]; tot = sum(poids); t = float(g[1])
        for w, p in zip(mots, poids):
            d = (float(g[2]) - float(g[1])) * p / tot; out.append((w, t, t + d)); t += d
    return out


def chronologie(groupes, mots=None, t0=0.0):
    """Suite (début, fin, forme) de la réplique. mots : [(mot, début, fin)] relatifs au début de la réplique (transcription),
    sinon répartis dans les groupes de sous-titres (instants absolus)."""
    liste = [(w, t0 + float(a), t0 + float(b)) for w, a, b in mots] if mots and len(mots) >= 1 else _mots_des_groupes(groupes)
    seg = []
    for w, a, b in liste:
        ph = phonemes(w)
        if not ph or b <= a: continue
        poids = [POIDS.get(v, 0.4) for v in ph]; tot = sum(poids); t = a
        for v, p in zip(ph, poids):
            d = (b - a) * p / tot; seg.append((t, t + d, v)); t += d
    # consonnes « neutres » (r, k, g) : la forme de la voyelle voisine (coarticulation)
    for k, (a, b, v) in enumerate(seg):
        if v == "":
            voisin = next((seg[j][2] for j in (k + 1, k - 1) if 0 <= j < len(seg) and seg[j][2]), "E")
            seg[k] = (a, b, voisin)
    return seg


def forme(seg, tm):
    """Forme de bouche à l'instant tm (None entre deux mots : bouche au repos)."""
    if not seg: return None
    k = bisect.bisect_right([s[0] for s in seg], tm) - 1
    if k < 0: return None
    a, b, v = seg[k]
    if tm < b: return v
    if k + 1 < len(seg) and seg[k + 1][0] - b < 0.08: return v              # tout petit blanc entre deux mots : on garde la forme
    return None
