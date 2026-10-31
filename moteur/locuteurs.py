"""Qui parle quand, même quand deux voix se ressemblent (gratuit, sur la machine).

La transcription (ElevenLabs, sinon Whisper) découpe les mots, mais confond parfois deux voix proches : un seul personnage parle
alors avec les deux voix. Ici, on recoupe le son en morceaux fins (à chaque petite pause ou fin de phrase), on calcule
l'« empreinte » de chaque morceau — timbre (coefficients MFCC : moyenne et variation), hauteur, brillance, débit — puis on regroupe
les morceaux qui se ressemblent (classification hiérarchique). Le nombre de voix (1 à 3) est choisi d'après la netteté des groupes,
en tenant compte du dialogue (questions / réponses, « papa, … ») qui annonce un échange. Si l'empreinte vocale ECAPA (SpeechBrain)
est installée, elle remplace le calcul MFCC (encore plus précise)."""
import math, os, re
import numpy as np

SR = 22050


def _mel(n_fft, sr, n=40, fmin=60, fmax=7600):
    hz = lambda m: 700 * (10 ** (m / 2595) - 1); mel = lambda f: 2595 * math.log10(1 + f / 700)
    pts = np.array([hz(m) for m in np.linspace(mel(fmin), mel(fmax), n + 2)]); bins = np.floor((n_fft + 1) * pts / sr).astype(int)
    fb = np.zeros((n, n_fft // 2 + 1))
    for k in range(1, n + 1):
        a, b, c = bins[k - 1], bins[k], bins[k + 1]
        for j in range(a, b): fb[k - 1, j] = (j - a) / max(1, b - a)
        for j in range(b, c): fb[k - 1, j] = (c - j) / max(1, c - b)
    return fb


_FB = {}


def empreinte_mfcc(seg, sr=16000):
    """Vecteur d'empreinte d'un morceau de voix (sans IA) : timbre, hauteur, brillance."""
    x = np.asarray(seg, np.float32)
    if len(x) < int(0.25 * sr): return None
    x = np.append(x[0], x[1:] - 0.97 * x[:-1])
    n_fft, hop, win = 512, 160, 400
    nfr = 1 + (len(x) - win) // hop
    if nfr < 8: return None
    idx = np.arange(win)[None, :] + hop * np.arange(nfr)[:, None]
    fr = x[idx] * np.hamming(win)
    sp = np.abs(np.fft.rfft(fr, n_fft)) ** 2
    en = sp.sum(1); garde = en > np.percentile(en, 35)                     # trames de voix (les plus fortes)
    if garde.sum() < 6: return None
    sp = sp[garde]
    fb = _FB.setdefault((n_fft, sr), _mel(n_fft, sr))
    lm = np.log(sp @ fb.T + 1e-10)
    n = lm.shape[1]; dct = np.cos(np.pi / n * (np.arange(n)[:, None] + 0.5) * np.arange(20)[None, :])
    mf = (lm @ dct)[:, 1:]                                                # 19 coefficients (sans l'énergie)
    mf -= 0.0
    f = np.fft.rfftfreq(n_fft, 1 / sr)
    centre = (sp * f).sum(1) / (sp.sum(1) + 1e-10)
    pente = np.polyfit(np.log(f[1:] + 1), np.log(sp[:, 1:].mean(0) + 1e-10), 1)[0]
    ac = [np.correlate(r, r, "full")[win - 1:] for r in fr[garde][::3]]   # hauteur (autocorrélation)
    lo, hi = sr // 400, sr // 70
    h = [sr / (lo + int(np.argmax(a[lo:hi]))) for a in ac if a[0] > 0 and a[lo + int(np.argmax(a[lo:hi]))] > 0.35 * a[0]]
    hz = math.log(np.median(h)) if len(h) >= 3 else 0.0
    return np.concatenate([mf.mean(0), mf.std(0), [hz * 4, math.log(np.median(centre) + 1), pente]])


def _ecapa():
    if os.environ.get("ECAPA", "1") == "0": return None
    try:
        from speechbrain.inference.speaker import EncoderClassifier
        return EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", run_opts={"device": "cpu"},
                                              savedir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outils", "ecapa"))
    except Exception: return None


def _empreintes(ch, s16):
    """Empreinte de chaque morceau : ECAPA si elle est installée (toutes ou aucune), sinon timbre MFCC. Renvoie (morceaux, X, méthode)."""
    enc = _ecapa()
    if enc is not None:
        try:
            import torch
            E, ok = [], []
            for c in ch:
                seg = s16[int(c["deb"] * 16000):int(c["fin"] * 16000) + 1600]
                if len(seg) < 4000: continue
                with torch.no_grad(): e = enc.encode_batch(torch.tensor(seg, dtype=torch.float32)[None]).squeeze().numpy()
                E.append(e / (np.linalg.norm(e) + 1e-9)); ok.append(c)
            if len(ok) >= 4: return ok, np.array(E), "ECAPA"
        except Exception as e: print(f"  empreinte ECAPA impossible ({str(e)[:100]}) : timbre MFCC", flush=True)
    E, ok = [], []
    for c in ch:
        e = empreinte_mfcc(s16[int(c["deb"] * 16000):int(c["fin"] * 16000) + 1600])
        if e is not None: E.append(e); ok.append(c)
    return ok, (np.array(E)[:, list(range(19)) + [38, 39, 40]] if E else np.zeros((0, 22))), "timbre MFCC"   # timbre moyen + hauteur + brillance


def morceaux(mots, ecart=0.25, max_d=4.0):
    """Morceaux fins : nouveau morceau à chaque petite pause, fin de phrase ou au bout de 4 s."""
    out = []
    for m in mots:
        c = out[-1] if out else None
        if (c is None or m["s"] - c["mots"][-1]["e"] > ecart or re.search(r"[.!?…]$", c["mots"][-1]["w"]) or m["s"] - c["mots"][0]["s"] > max_d):
            out.append({"mots": [m]})
        else: c["mots"].append(m)
    for c in out: c["deb"], c["fin"] = c["mots"][0]["s"], c["mots"][-1]["e"]; c["t"] = " ".join(m["w"] for m in c["mots"])
    return out


def _silhouette(X, lab):
    k = len(set(lab))
    if k < 2: return 0.0
    D = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(-1)); s = []
    for i in range(len(X)):
        a_ = D[i, lab == lab[i]]; a_ = a_[a_ > 0].mean() if (lab == lab[i]).sum() > 1 else 0.0
        b_ = min(D[i, lab == l].mean() for l in set(lab) if l != lab[i])
        s.append((b_ - a_) / max(a_, b_, 1e-9))
    return float(np.mean(s))


def _echange(chunks):
    """Le texte annonce-t-il un dialogue (questions, réponses, interpellations) ?"""
    t = " ".join(c["t"] for c in chunks).lower()
    return t.count("?") + len(re.findall(r"(^|[.!?]\s)(oui|non|ouais|bah|ben|mais|quoi|attends)\b", t)) + len(re.findall(r"\b(papa|maman|fiston|mec|madame|monsieur)\s*[,!?]", t))


def regrouper(X, kmax=3, bonus2=0.0, durees=None):
    """Classification hiérarchique (Ward) : nombre de voix choisi par la netteté des groupes (silhouette)."""
    from scipy.cluster.hierarchy import linkage, fcluster
    if len(X) < 3: return np.zeros(len(X), int), 1, 0.0
    Z = linkage(X, "ward"); best = (np.zeros(len(X), int), 1, 0.0)
    for k in range(2, min(kmax, len(X) - 1) + 1):
        lab = fcluster(Z, k, "maxclust") - 1
        if min(np.bincount(lab)) < max(2, round(0.15 * len(X))): continue   # un groupe minuscule : du bruit, pas une voix
        if durees is not None and min(sum(d for d, l in zip(durees, lab) if l == g) for g in range(k)) < 0.15 * sum(durees): continue
        sc = _silhouette(X, lab) + (bonus2 if k == 2 else 0.0)
        seuil = 0.10 if k == 2 else 0.16
        if sc > seuil and sc > best[2] + (0.04 if best[1] > 1 else 0): best = (lab, k, sc)
    return best


def rediariser(mots, sig, sr=SR):
    """Réattribue les voix des mots quand la transcription en a confondu (deux voix proches = une seule). Renvoie les mots."""
    voix0 = {m["voix"] for m in mots}
    if len(voix0) >= 2:                                                   # la transcription voit déjà plusieurs voix : on ne recompte
        from collections import Counter                                   # que si l'une d'elles « parle » presque tout (voix fusionnées)
        d = Counter()
        for m in mots: d[m["voix"]] += m["e"] - m["s"]
        if max(d.values()) < 0.8 * sum(d.values()): return mots
    ch = [c for c in morceaux(mots) if c["fin"] - c["deb"] >= 0.25]
    if len(ch) < 4: return mots
    from scipy.signal import resample_poly
    s16 = resample_poly(np.asarray(sig, np.float32), 320, 441) if sr == 22050 else np.asarray(sig, np.float32)
    ok, X, methode = _empreintes(ch, s16)
    if len(ok) < 4: return mots
    if methode != "ECAPA": X = (X - X.mean(0)) / (X.std(0) + 1e-6)         # MFCC : mesures remises à la même échelle (ECAPA : telles quelles)
    bonus = 0.04 if _echange(ok) >= 2 else 0.0
    lab, k, sc = regrouper(X, 3, bonus, [c["fin"] - c["deb"] for c in ok])
    if k <= 1 and len(voix0) == 1 and _echange(ok) >= 3:                 # le son ne tranche pas (même voix ?) mais c'est un dialogue :
        return tours_de_parole(mots, s16)                                  # on suit le fil des questions / réponses
    if k <= 1 or (k <= len(voix0) and _accord(ok, lab) > 0.85): return mots   # rien de plus net que la transcription : on la garde
    nom = {}
    for c, l in zip(ok, lab):
        v = nom.setdefault(int(l), f"speaker_{len(nom)}")
        for m in c["mots"]: m["voix"] = v
    tout = {id(m) for c in ok for m in c["mots"]}                          # morceaux trop courts : la voix du voisin le plus proche
    for i, m in enumerate(mots):
        if id(m) in tout: continue
        voisin = min((x for x in mots if id(x) in tout), key=lambda x: abs(x["s"] - m["s"]), default=None)
        if voisin: m["voix"] = voisin["voix"]
    print(f"  voix re-séparées par leur empreinte ({methode}) : {k} voix (netteté {sc:.2f})", flush=True)
    return mots


def _accord(ch, lab):
    """Part des morceaux où l'ancienne voix et le nouveau groupe concordent (au mieux)."""
    from collections import Counter
    paires = Counter((c["mots"][0]["voix"], int(l)) for c, l in zip(ch, lab))
    meilleur = {}
    for (v, l), n in paires.most_common():
        if v not in meilleur and l not in meilleur.values(): meilleur[v] = l
    return sum(paires[(v, l)] for v, l in meilleur.items()) / max(1, len(ch))


REPONSE = re.compile(r"^(oui|non|ouais|nan|bah|ben|mais|quoi|hein|attends|d'accord|ok|okay|si|pourquoi|comment|ah|oh|eh|tu|vous|toi|t'es)\b", re.I)
VOC_ENFANT = r"(^|[.!?…]\s+)(papa|maman)\s*,|,\s*(papa|maman)\s*([.!?…]|$)"
VOC_PARENT = r"\b(fiston|mon fils|ma fille|mon gar[çc]on|ma puce|mon grand)\b"


def tours_de_parole(mots, s16=None):
    """Repli gratuit quand le son ne sépare pas deux voix (même personne qui fait les deux voix) : on suit le fil du dialogue.
    Changement de personne après une question, sur une réponse (« oui », « non », « mais »…), après une interpellation, ou sur un
    saut de hauteur de voix ; pas de changement au milieu d'une phrase ni dans un enchaînement sans pause. Les répliques qui
    disent « papa, … » vont à l'enfant, celles qui disent « fiston » au parent."""
    ch = morceaux(mots, ecart=0.3, max_d=8.0)
    if len(ch) < 3: return mots
    hz = []
    for c in ch:
        h = None
        if s16 is not None:
            seg = s16[int(c["deb"] * 16000):int(c["fin"] * 16000)]
            e = empreinte_mfcc(seg) if len(seg) > 4000 else None
            h = e[38] / 4 if e is not None and e[38] else None
        hz.append(h)
    lab = [0]
    for i in range(1, len(ch)):
        a, b = ch[i - 1], ch[i]; sc = 0.0; ta, tb = a["t"].rstrip(), b["t"].strip()
        if ta.endswith("?"): sc += 2.0                                      # après une question, l'autre répond
        if REPONSE.search(tb): sc += 1.2                                    # « oui », « non », « mais »… : une réponse
        if re.search(VOC_ENFANT, tb.lower()) or re.search(VOC_PARENT, tb.lower()): sc += 0.8
        if hz[i] is not None and hz[i - 1] is not None: sc += min(2.0, abs(hz[i] - hz[i - 1]) * 8)      # saut de hauteur (log)
        if b["deb"] - a["fin"] < 0.15: sc -= 1.5                           # même souffle
        if ta.endswith((",", "…")) and not ta.endswith("?"): sc -= 1.0     # phrase pas finie
        lab.append(1 - lab[-1] if sc >= 2.0 else lab[-1])
    if len(set(lab)) < 2: return mots
    enfant = [l for c, l in zip(ch, lab) if re.search(VOC_ENFANT, c["t"].lower())]
    parent = [l for c, l in zip(ch, lab) if re.search(VOC_PARENT, c["t"].lower())]
    for c, l in zip(ch, lab):
        for m in c["mots"]: m["voix"] = f"speaker_{l}"
    print(f"  voix trop proches : répliques réparties d'après le fil du dialogue (questions, réponses{', papa / fiston' if enfant or parent else ''})", flush=True)
    return mots


def _fenetres(s16, t0, t1, enc, long_=0.8, pas=0.2):
    """Empreintes sur une fenêtre glissante (0,8 s tous les 0,2 s) : [(centre, vecteur normé)]."""
    out = []
    t = t0
    while t + long_ / 2 <= t1 + 0.2:
        a, b = max(0, int((t - long_ / 2) * 16000)), int((t + long_ / 2) * 16000); seg = s16[a:b]
        if len(seg) >= int(0.5 * 16000):
            if enc is not None:
                import torch
                with torch.no_grad(): e = enc.encode_batch(torch.tensor(seg, dtype=torch.float32)[None]).squeeze().numpy()
            else:
                e = empreinte_mfcc(seg)
                e = None if e is None else e[list(range(19)) + [38, 39, 40]]
            if e is not None: out.append((t, np.asarray(e, np.float64)))
        t += pas
    return out


_P = {"son": 10.0, "avis": 0.1, "pause": 0.6, "court": 1.4, "colle": 1.5}   # réglages du fil des voix (banc d'essai)


def _frontiere(mots, p):
    """Entre le mot p-1 et le mot p : 2 = fin de phrase (. ? ! …), 1 = vraie pause, 0 = milieu de phrase."""
    if re.search(r"[.!?…]$", mots[p - 1]["w"]): return 2
    return 1 if mots[p]["s"] - mots[p - 1]["e"] > 0.35 else 0


DEBUTS = set("""ouais oui non nan bah ben euh hum mais ah oh eh hé hein et alors donc bon voilà ok okay attends attendez écoute écoutez
quoi quand pourquoi comment combien qui que qu où il elle ils elles on je j tu t vous nous moi toi lui c ça ce cette ces y le la l les un une
des mon ma mes ton ta tes son sa ses notre votre vas va allez arrête arrêtez putain wesh tiens franchement sérieux sérieusement sinon enfin
parce puis là ici excuse excusez désolé désolée merci salut bonjour bonsoir pardon d s n m regarde regardez dis dites faut est
avec pour sans si""".split())


def fins_de_phrase(mots):
    """La transcription gratuite (Groq / Whisper) oublie souvent les points : « …un poisson rouge Mais pourquoi… ». Un mot courant qui
    commence par une majuscule au milieu du texte (Mais, Ouais, Il, C'…) ouvre une nouvelle phrase : on remet un point sur le mot
    d'avant. Les noms propres (Chloé, Pomme Dauphine) ne sont pas dans la liste : rien ne change pour eux."""
    for i in range(1, len(mots)):
        w, av = str(mots[i]["w"]).strip(), str(mots[i - 1]["w"]).strip()
        if not w or not w[0].isupper() or not av or re.search(r"[.!?…,;:]$", av): continue
        tete = re.split(r"['’ -]", re.sub(r"[^\w'’ -]", "", w).lower())[0]
        if tete in DEBUTS: mots[i - 1]["w"] = av + "."
    return mots


def sans_boucles(mots, n_min=3, duree_max=0.12):
    """Whisper (gratuit) tourne parfois en boucle à la fin d'un son : « Oh mais non je suis sale. Oh mais non je suis sale. Oh mais
    non… », trois fois en une seconde. Un bloc de 3 mots ou plus répété juste après lui-même, dit à une vitesse impossible (moins de
    0,12 s par mot), n'est gardé qu'une fois. Une vraie répétition (« non non non », dite à vitesse normale) reste."""
    nu = lambda m: re.sub(r"[^\w'’-]", "", str(m["w"]).lower())
    out = list(mots); i = 0
    while i < len(out):
        fait = False
        for n in range(min(12, (len(out) - i) // 2), n_min - 1, -1):
            a, b = out[i:i + n], out[i + n:i + 2 * n]
            if [nu(m) for m in a] != [nu(m) for m in b]: continue
            if (b[-1]["e"] - b[0]["s"]) / n >= duree_max: continue
            j = i + 2 * n
            while [nu(m) for m in out[j:j + n]] == [nu(m) for m in a]: j += n
            del out[i + n:j]; fait = True; break
        if not fait: i += 1
    if len(out) < len(mots): print(f"  transcription : {len(mots) - len(out)} mot(s) répété(s) en boucle retiré(s)", flush=True)
    return out


def _minuscule(w):
    """Le mot commence par une minuscule : la phrase continue (Whisper met une majuscule à chaque nouvelle phrase)."""
    w = re.sub(r"^[^\w]+", "", str(w))
    return bool(w) and w[0].islower()


def caler_sur_phrases(mots, lab, portee=3):
    """Les changements de personne tombent sur une fin de phrase (sinon une pause) : l'empreinte vocale glisse souvent d'un ou deux
    mots (« Je m'en bats | les couilles »). Un changement ailleurs est déplacé sur la fin de phrase la plus proche (3 mots au plus)."""
    lab = list(lab); n = len(lab)
    for p in range(1, n):
        if lab[p] == lab[p - 1]: continue
        niv = _frontiere(mots, p)
        if niv == 2: continue
        suite = _minuscule(mots[p]["w"])                                   # « J'ai un peu dépassé | l'objectif fixé. » : même personne
        if suite: niv = 0
        for voulu in ((2,) if niv == 1 or suite else (2, 1)):
            ecart = lambda q: sum(1 for r in range(min(p, q), max(p, q)) if not re.match(r"^['’-]", mots[r]["w"]))   # « m 'en » = un mot
            cands = sorted((q for q in range(max(1, p - 4 * portee), min(n, p + 4 * portee + 1))
                            if q != p and _frontiere(mots, q) >= voulu and ecart(q) <= (2 * portee if suite else portee)), key=lambda q: (ecart(q), q))
            fait = False
            for q in cands:
                a_, b_ = min(p, q), max(p, q)
                if any(lab[r] != lab[r - 1] for r in range(a_ + 1, b_ + 1) if r != p): continue   # un autre changement entre les deux
                if q > p: lab[p:q] = [lab[p - 1]] * (q - p)
                else: lab[q:p] = [lab[p]] * (p - q)
                fait = True; break
            if fait: break
    return lab


def affiner(mots, sig, sr=SR):
    """Qui parle, MOT PAR MOT (gratuit) : la transcription colle parfois la fin d'une phrase de l'un au début de celle de l'autre,
    ou range un morceau sur la mauvaise voix ; la voix « saute » alors d'un personnage à l'autre. On compare chaque mot (empreinte
    vocale autour du mot) à l'empreinte moyenne de chaque voix, puis on choisit le fil le plus probable (Viterbi) : changer de
    personne coûte cher au milieu d'une phrase, peu après une pause ou une question. Chaque mot reçoit aussi sa « certitude »
    (m["sure"], 0 à 1) : sert à refuser qu'une IA qui ne lit que le texte déplace une réplique dont la voix est sûre."""
    voix = sorted({m["voix"] for m in mots}); ETAT["ressemblance"] = None
    if len(voix) < 2 or len(mots) < 6 or os.environ.get("AFFINER_VOIX", "1") == "0": return mots
    from scipy.signal import resample_poly
    s16 = resample_poly(np.asarray(sig, np.float32), 320, 441) if sr == 22050 else np.asarray(sig, np.float32)
    enc = _ecapa()
    F = _fenetres(s16, mots[0]["s"], mots[-1]["e"], enc)
    if len(F) < 6: return mots
    T = np.array([t for t, _ in F]); X = np.array([e for _, e in F])
    if enc is None: X = (X - X.mean(0)) / (X.std(0) + 1e-6)
    X = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    # empreinte de chaque mot : fenêtres centrées dans le mot (sinon la plus proche)
    W = []
    for m in mots:
        idx = np.where((T >= m["s"] - 0.05) & (T <= m["e"] + 0.05))[0]
        if not len(idx): idx = [int(np.argmin(np.abs(T - (m["s"] + m["e"]) / 2)))]
        w = X[idx].mean(0); W.append(w / (np.linalg.norm(w) + 1e-9))
    W = np.array(W); depart = [m["voix"] for m in mots]; lab_v = list(depart); n = len(mots)
    for _tour in range(3):                                                 # 2-3 tours : empreintes des voix recalculées sur le fil trouvé
        voix = sorted(set(lab_v)); k = len(voix)
        if k < 2: break
        C = []
        for v in voix:
            sel = [i for i in range(n) if lab_v[i] == v]
            c = W[sel].mean(0); C.append(c / (np.linalg.norm(c) + 1e-9))
        C = np.array(C)
        if os.environ.get("VOIX_DEBUG"): print("  ressemblance des voix :", np.round(C @ C.T, 3).tolist(), flush=True)
        if k == 2 and enc is not None: ETAT["ressemblance"] = round(float(C[0] @ C[1]), 3)   # (mesure valable avec ECAPA seulement)
        if k == 2 and float(C[0] @ C[1]) > 0.97: break                     # deux « voix » identiques : le son ne tranche pas
        S = W @ C.T                                                        # ressemblance de chaque mot à chaque voix
        S = (S - S.mean(1, keepdims=True)) / (S.std() + 1e-9)
        ini = np.array([voix.index(v) for v in lab_v])
        cout = np.zeros((n, k)); arr = np.zeros((n, k), int)
        for i in range(n):
            d = max(0.05, min(0.6, mots[i]["e"] - mots[i]["s"]))
            e = S[i] * _P["son"] * d / 0.3 + _P["avis"] * (np.arange(k) == ini[i])   # le son du mot + un peu l'avis de départ
            if i == 0: cout[i] = e; continue
            pause = mots[i]["s"] - mots[i - 1]["e"]; fin = re.search(r"[.!?…]$", mots[i - 1]["w"]) is not None
            pen = _P["pause"] if (pause > 0.35 or (fin and pause > 0.08)) else _P["court"] if (pause > 0.15 or fin) else _P["colle"]
            for j in range(k):
                cand = cout[i - 1] - pen * (np.arange(k) != j)
                arr[i, j] = int(np.argmax(cand)); cout[i, j] = cand[arr[i, j]] + e[j]
        lab = [int(np.argmax(cout[-1]))]
        for i in range(n - 1, 0, -1): lab.append(arr[i, lab[-1]])
        lab = lab[::-1]
        neuf = [voix[l] for l in lab]
        for i in range(n):
            tri = np.sort(S[i])[::-1]; mien = S[i][lab[i]]
            mots[i]["sure"] = round(float(min(1.0, max(0.0, (mien - (tri[1] if tri[0] == mien else tri[0]) + 0.5) / 1.5))), 2)
        temps = {v: sum(mots[i]["e"] - mots[i]["s"] for i in range(n) if neuf[i] == v) for v in voix}
        petite = [v for v in voix if temps[v] < 0.1 * sum(temps.values())]   # une « voix » presque muette : morceaux d'une autre
        if petite and k > 2:
            v0 = petite[0]; garde = [v for v in voix if v != v0]
            proche = garde[int(np.argmax([C[voix.index(v0)] @ C[voix.index(w)] for w in garde]))]
            neuf = [proche if x == v0 else x for x in neuf]; print(f"  une voix en trop (presque muette) rattachée à la plus proche", flush=True)
        if neuf == lab_v: break
        lab_v = neuf
    if ETAT["ressemblance"] is not None and ETAT["ressemblance"] > PROCHES and len(set(lab_v)) == 2:
        for m in mots: m["sure"] = 0.0                                     # voix trop proches : le son ne tranche pas, on ne touche à rien
        print(f"  voix trop proches (ressemblance {ETAT['ressemblance']:.2f}) : vérification mot par mot laissée de côté", flush=True)
        return mots
    lab_v = caler_sur_phrases(mots, lab_v)
    noms = {v: f"speaker_{q}" for q, v in enumerate(dict.fromkeys(lab_v))}   # numéros dans l'ordre d'apparition
    change = sum(1 for a, b in zip(depart, lab_v) if a != b)
    for m, v in zip(mots, lab_v): m["voix"] = noms[v]
    if change: print(f"  voix vérifiées mot par mot : {change} mot(s) remis sur la bonne voix", flush=True)
    return mots


def mots_par_tours(mots, tours):
    """Chaque mot reçoit la personne qui parle le plus longtemps pendant ce mot (tours = [(début, fin, personne)]) ; un mot hors de
    tout tour prend la personne du tour le plus proche. Personnes renommées speaker_0, speaker_1… dans l'ordre d'apparition."""
    if not tours: return mots
    noms = {}
    for m in mots:
        rec = {}
        for a, b, p in tours:
            r = min(b, m["e"]) - max(a, m["s"])
            if r > 0: rec[p] = rec.get(p, 0) + r
        p = max(rec, key=rec.get) if rec else min(tours, key=lambda x: min(abs(x[0] - m["e"]), abs(x[1] - m["s"])))[2]
        m["voix"] = noms.setdefault(p, f"speaker_{len(noms)}")
    return mots


def pyannote(mots, sig, sr=SR):
    """Qui parle quand, par pyannote (outil spécialisé, gratuit) : seulement si le secret HF_TOKEN (clé Hugging Face gratuite) est
    réglé et l'outil installé ; sinon None (on garde l'empreinte vocale ECAPA). Renvoie les mots avec leur voix."""
    jeton = os.environ.get("HF_TOKEN")
    if not jeton or os.environ.get("PYANNOTE", "1") == "0": return None
    try:
        import torch
        from pyannote.audio import Pipeline
    except Exception: return None
    pipe = None
    for nom in ("pyannote/speaker-diarization-community-1", "pyannote/speaker-diarization-3.1"):
        try:
            try: pipe = Pipeline.from_pretrained(nom, token=jeton)
            except TypeError: pipe = Pipeline.from_pretrained(nom, use_auth_token=jeton)
            if pipe is not None: break
        except Exception as e: print(f"  pyannote {nom} indisponible ({str(e)[:100]})", flush=True)
    if pipe is None: return None
    from scipy.signal import resample_poly
    s16 = resample_poly(np.asarray(sig, np.float32), 320, 441) if sr == 22050 else np.asarray(sig, np.float32)
    res = pipe({"waveform": torch.tensor(s16, dtype=torch.float32)[None], "sample_rate": 16000}, min_speakers=1, max_speakers=4)
    ann = getattr(res, "speaker_diarization", res)
    tours = [(float(t.start), float(t.end), str(p)) for t, _, p in ann.itertracks(yield_label=True)]
    if len({p for _, _, p in tours}) < 1: return None
    print(f"  voix séparées par pyannote : {len({p for _, _, p in tours})} voix, {len(tours)} tours de parole", flush=True)
    return mots_par_tours([dict(m) for m in mots], tours)



SUITE = re.compile(r"^(et|donc|puis|parce|alors|enfin|sinon|ou|que|qui)\b", re.I)
_Q = {"change": 0.0, "fini": 1.5, "question": 2.0, "reponse": 1.0, "suite": 1.5, "echo": 1.0, "ia": 2.0, "avis": 0.3, "minuscule": 2.5}   # fil du dialogue
PROCHES = 0.7                                                              # ressemblance des 2 voix au-delà de laquelle le son ne tranche plus
DOUTE = 0.55                                                               # entre DOUTE et PROCHES : le son aide, le dialogue décide avec lui
ETAT = {"ressemblance": None}                                              # dernière mesure (affiner)


def phrases(mots):
    """Phrases : coupées à chaque fin de phrase (. ? ! …) ou vraie pause (0,35 s) ; une phrase de plus de 8 s est recoupée sur une
    virgule suivie d'une petite pause. Renvoie des listes d'indices de mots."""
    out = [[]]
    for i, m in enumerate(mots):
        if out[-1]:
            p = m["s"] - mots[i - 1]["e"]; long_ = m["s"] - mots[out[-1][0]]["s"]
            if p > 0.35 or (long_ > 8 and p > 0.15 and mots[i - 1]["w"].endswith(",")): out.append([])
        out[-1].append(i)
        if re.search(r"[.!?…]$", m["w"]): out.append([])
    return [p for p in out if p]


def _mots_txt(mots, p): return [re.sub(r"[^\w'-]", "", mots[i]["w"].lower()) for i in p]


def indices_dialogue(mots, ph):
    """Ce que dit le TEXTE entre deux phrases : > 0 = l'autre personne parle, < 0 = la même continue. Dans un dialogue, après une
    phrase finie l'autre parle souvent ; après une question, l'autre répond ; « oui », « non », « bah », « mais »… = une réponse ;
    « Comme un homme ? » qui reprend les derniers mots de l'autre = une réaction ; une phrase coupée sur une virgule (ou qui
    repart sur « et », « donc »…) = la suite de la même personne."""
    out = [0.0]
    for j in range(1, len(ph)):
        fin = mots[ph[j - 1][-1]]["w"]; debut = " ".join(mots[i]["w"] for i in ph[j]).strip()
        pause = mots[ph[j][0]]["s"] - mots[ph[j - 1][-1]]["e"]; s = 0.0
        if re.search(r"[.!?…]$", fin) and not fin.endswith("..."): s += _Q["fini"]
        if fin.endswith("?"): s += _Q["question"]
        if REPONSE.search(debut) or re.match(r"^(voilà|exactement|carrément|grave|jamais|bon)\b", debut, re.I): s += _Q["reponse"]
        if not re.search(r"[.!?…]$", fin) or fin.endswith(","):           # phrase pas finie (coupée par une pause)
            s -= _Q["suite"] * (1.0 if pause < 0.8 else 0.5)
        if SUITE.search(debut) and not fin.endswith("?"): s -= 0.5 * _Q["suite"]
        if _minuscule(debut) and not re.search(r"[.!?]$", fin): s -= _Q["minuscule"]   # « …dépassé » / « l'objectif fixé. » : la suite
        a, b = _mots_txt(mots, ph[j - 1])[-4:], _mots_txt(mots, ph[j])[:4]
        if len([w for w in b if w and w in a]) >= 2: s += _Q["echo"]       # reprend les mots de l'autre
        out.append(s)
    return out


def _viterbi2(em, tr):
    """Fil le plus probable à 2 personnes : em[j] = (score pers. 0, score pers. 1), tr[j] = bonus pour changer avant la phrase j."""
    n = len(em); cout = np.array(em[0], float); arr = np.zeros((n, 2), int)
    for j in range(1, n):
        neuf = np.zeros(2)
        for b in range(2):
            rester, changer = cout[b], cout[1 - b] + tr[j]
            arr[j, b] = b if rester >= changer else 1 - b; neuf[b] = max(rester, changer) + em[j][b]
        cout = neuf
    lab = [int(np.argmax(cout))]
    for j in range(n - 1, 0, -1): lab.append(arr[j, lab[-1]])
    return lab[::-1]


def fil_dialogue(mots, ia=None, avis=None):
    """Contrôle « questions-réponses » quand les deux voix se ressemblent trop pour que le son tranche (même personne qui fait les
    deux voix) : qui dit chaque PHRASE, d'après la logique du dialogue (indices_dialogue), l'avis de l'IA qui a lu le dialogue
    phrase par phrase (ia = liste 0/1 par phrase, ou None) et, un peu, les voix trouvées avant. Deux personnes seulement."""
    voix0 = sorted({m["voix"] for m in mots})
    if len(voix0) > 2: return mots
    ph = phrases(mots)
    if len(ph) < 3: return mots
    avant = [int(np.argmax(np.bincount([voix0.index(mots[i]["voix"]) for i in p], minlength=2))) for p in ph]
    ia = [x if x in (0, 1) else None for x in (ia or [])][:len(ph)] + [None] * max(0, len(ph) - len(ia or []))
    connus = [(a, b) for a, b in zip(avant, ia) if b is not None]
    if connus and sum(a == b for a, b in connus) < len(connus) / 2: ia = [None if b is None else 1 - b for b in ia]   # mêmes numéros
    avis = _Q["avis"] if avis is None else avis                            # poids des voix trouvées avant (le son)
    em = [tuple(avis * (a == q) + (_Q["ia"] * (b == q) if b is not None else 0.0) for q in (0, 1)) for a, b in zip(avant, ia)]
    tr = [_Q["change"] + s for s in indices_dialogue(mots, ph)]
    lab = _viterbi2(em, tr)
    if len(set(lab)) < 2: return mots
    noms = {}
    for q in lab: noms.setdefault(q, f"speaker_{len(noms)}")
    av = [m["voix"] for m in mots]
    for j, p in enumerate(ph):
        for i in p: mots[i]["voix"] = noms[lab[j]]; mots[i]["sure"] = 0.0      # le son ne tranche pas : jamais « sûr »
    change = sum(1 for a, m in zip(av, mots) if a != m["voix"])
    print(f"  contrôle questions-réponses ({'avec' if connus else 'sans'} relecture de l'IA) : {len(ph)} phrases, {change} mot(s) changé(s) de voix", flush=True)
    return mots
