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
