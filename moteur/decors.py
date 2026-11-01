"""Client des décors du moteur cartoon : demande à Modal (Stable Diffusion XL) un décor par scène et le met au format 1080x1920.
En cas de souci (Modal indisponible, modèle inaccessible), renvoie {} : le moteur cartoon utilise alors des fonds unis pastel."""
import hashlib, io, os, re
import numpy as np, cv2
from PIL import Image

W, H = 1080, 1920
BANQUE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "decors")   # lieux déjà dessinés, réutilisés tels quels

STYLE_VERSION = "v6"                                                       # v4 : décor agrandi par l'IA (net) + carte de profondeur ; les anciens ne sont plus repris
PROFONDEURS = {}                                                           # indice de scène -> profondeur (0 loin … 255 près), 1080x1920

def _cle(d):
    return hashlib.sha1((STYLE_VERSION + "|" + re.sub(r"[^a-z0-9]+", " ", d.lower()).strip()).encode()).hexdigest()[:16]

def lieux_connus(n=12):
    """Décors déjà dans la banque (pour que l'auteur réutilise exactement les mêmes lieux)."""
    try: idx = [l.rstrip("\n").split("\t", 1) for l in open(os.path.join(BANQUE, "index.tsv"), encoding="utf-8")]
    except OSError: return []
    return [d for _, d in idx[-n:]]

def _ranger(d, im, prof=None):
    os.makedirs(BANQUE, exist_ok=True); k = _cle(d)
    cv2.imwrite(os.path.join(BANQUE, k + ".jpg"), cv2.cvtColor(im, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
    if prof is not None: cv2.imwrite(os.path.join(BANQUE, k + "_prof.png"), cv2.resize(prof, (270, 480), interpolation=cv2.INTER_AREA))
    if getattr(_format, "panneaux", None):
        import json
        json.dump(_format.panneaux, open(os.path.join(BANQUE, k + "_panneaux.json"), "w"))
    with open(os.path.join(BANQUE, "index.tsv"), "a", encoding="utf-8") as f: f.write(f"{k}\t{d}\n")
    _compter()

LUMIERES = ("bright daylight", "warm golden evening light, lamps on", "night, dark blue ambience, warm lamp light", "lamps on", "daylight")
VIDES = set("a an the with of and on in at to its their wall light".split())

def _mots(d):
    d = d.lower()
    for l in LUMIERES: d = d.replace(l, " ")
    return {m for m in re.findall(r"[a-z]+", d) if m not in VIDES and len(m) > 2}

def _lumiere(d):
    d = d.lower()
    return "nuit" if "night" in d else "soir" if "evening" in d or "dusk" in d else "jour"

def voisin(d, seuil):
    """Décor de la banque qui ressemble le plus au lieu demandé (mêmes mots-clés, même moment de la journée), ou None."""
    try: idx = [l.rstrip("\n").split("\t", 1) for l in open(os.path.join(BANQUE, "index.tsv"), encoding="utf-8")]
    except OSError: return None
    m0, l0, best = _mots(d), _lumiere(d), None
    if not m0: return None
    for cle, desc in idx:
        f_ = os.path.join(BANQUE, cle + ".jpg")
        if not os.path.exists(f_) or _lumiere(desc) != l0 or ("[semi]" in desc) != ("[semi]" in d): continue   # même style de décor
        m1 = _mots(desc); s = len(m0 & m1) / max(1, len(m0 | m1))
        if best is None or s > best[0]: best = (s, cle)
    if best is None or best[0] < seuil: return None
    return cv2.cvtColor(cv2.imread(os.path.join(BANQUE, best[1] + ".jpg")), cv2.COLOR_BGR2RGB), best[1]

def varier(im, d):
    """Petite variante d'un décor réutilisé (miroir et légère nuance de couleur selon le lieu) : jamais deux fois exactement pareil."""
    h = int(hashlib.sha1(d.encode()).hexdigest()[:6], 16)
    if h % 2: im = im[:, ::-1].copy()
    hsv = cv2.cvtColor(im, cv2.COLOR_RGB2HSV).astype(np.int16)
    hsv[..., 0] = (hsv[..., 0] + (h % 9) - 4) % 180
    hsv[..., 1] = np.clip(hsv[..., 1] * (0.92 + (h % 17) / 100), 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)

COMPTEUR = os.path.join(BANQUE, "compteur.json")                         # {"2026-11": 12} : décors neufs fabriqués par mois

def generes_ce_mois():
    """Décors neufs fabriqués sur Modal ce mois-ci. Compteur tenu à part (decors/compteur.json) : la date des fichiers ne veut rien
    dire sur GitHub (chaque fabrication repart d'une copie neuve du dépôt : tous les fichiers semblaient « de ce mois », le budget
    paraissait toujours atteint et presque aucun décor neuf n'était fait)."""
    import datetime, json
    try: return int(json.load(open(COMPTEUR)).get(datetime.date.today().strftime("%Y-%m"), 0))
    except (OSError, ValueError, AttributeError): return 0

def _compter():
    import datetime, json
    try: c = json.load(open(COMPTEUR))
    except (OSError, ValueError): c = {}
    if not isinstance(c, dict): c = {}
    m = datetime.date.today().strftime("%Y-%m"); c[m] = int(c.get(m, 0)) + 1
    os.makedirs(BANQUE, exist_ok=True); json.dump(c, open(COMPTEUR, "w"))

def _png(im):
    """Image RGB (plan du décor dessiné) -> PNG, ou b"" ."""
    if im is None: return b""
    ok, b = cv2.imencode(".png", cv2.cvtColor(cv2.resize(im, (768, 1344), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
    return b.tobytes() if ok else b""

def _recadre(im, interp=cv2.INTER_CUBIC):
    s = max(W / im.shape[1], H / im.shape[0])
    im = cv2.resize(im, (int(im.shape[1] * s + 0.5), int(im.shape[0] * s + 0.5)), interpolation=cv2.INTER_AREA if s < 1 else interp)
    y0, x0 = (im.shape[0] - H) // 2, (im.shape[1] - W) // 2
    return np.ascontiguousarray(im[y0:y0 + H, x0:x0 + W])

def _format(png):
    im, pan = faux_textes(simplifier(_recadre(np.array(Image.open(io.BytesIO(png)).convert("RGB")))))
    _format.panneaux = pan
    return im

def _prof(png):
    """Carte de profondeur (PNG en niveaux de gris) au format 1080x1920, adoucie (c'est une carte, pas l'image : rien n'est flou)."""
    if not png: return None
    d = np.array(Image.open(io.BytesIO(png)).convert("L"))
    return cv2.GaussianBlur(_recadre(d, cv2.INTER_LINEAR), (0, 0), 6)

PANNEAUX = {}                                                              # indice de scène -> panneaux vidés [(x, y, w, h)] (gags écrits dedans)

def aplats(im):
    """Décor IA ramené au style des personnages : aplats de couleur doux (sans bandes), trait noir d'origine gardé net, contours accentués."""
    sm = cv2.pyrMeanShiftFiltering(cv2.resize(im, (im.shape[1] // 2, im.shape[0] // 2), interpolation=cv2.INTER_AREA), 6, 14)
    sm = cv2.resize(sm, (im.shape[1], im.shape[0]), interpolation=cv2.INTER_CUBIC)
    trait = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY) < 80
    out = sm.copy(); out[trait] = im[trait]
    return cv2.addWeighted(out, 1.25, cv2.GaussianBlur(out, (0, 0), 1.2), -0.25, 0)

def faux_textes(im):
    """Panneaux clairs couverts de petits traits sombres (faux texte illisible de l'IA) : vidés, le cadre reste. Renvoie (image, panneaux)."""
    g = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY); out = im.copy(); res = []
    clair = (g > max(215, np.percentile(g, 80) + 12)).astype(np.uint8)
    clair = cv2.morphologyEx(clair, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    cs, _ = cv2.findContours(clair, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cs:
        x, y, w, h = cv2.boundingRect(c); A = w * h
        if not (0.004 * g.size < A < 0.12 * g.size) or w < 80 or h < 40 or cv2.contourArea(c) < 0.75 * A: continue
        zone = g[y + 6:y + h - 6, x + 6:x + w - 6]; sombre = (zone < 110).astype(np.uint8)
        k, _l, st, _c = cv2.connectedComponentsWithStats(sombre)
        petits = sum(1 for i in range(1, k) if 8 < st[i, 4] < 0.01 * A and st[i, 3] < 0.4 * h)
        if petits >= 6 and sombre.mean() > 0.04:
            fondc = np.median(im[y + 6:y + h - 6, x + 6:x + w - 6][zone >= 110], axis=0)
            out[y + 6:y + h - 6, x + 6:x + w - 6] = fondc.astype(np.uint8); res.append((int(x + 6), int(y + 6), int(w - 12), int(h - 12)))
    return out, res

def simplifier(im):
    """Style des chaînes analysées : aplats lissés (moins de détails), couleurs plus claires et un léger flou,
    pour que les personnages blancs ressortent nettement devant le décor. Rendu détaillé : les personnages ont maintenant
    costumes, contours et ombres, le décor garde donc plus de détails (lissage et voile allégés)."""
    detail = (os.environ.get("RENDU_DETAILLE") or "1") != "0"
    if detail and (os.environ.get("DECOR_APLATS") or "1") != "0": return aplats(im)   # même style que les personnages
    im = cv2.edgePreservingFilter(im, flags=1, sigma_s=25 if detail else 70, sigma_r=0.2 if detail else 0.45)   # aplats, contours gardés nets
    if not detail: im = cv2.GaussianBlur(im, (0, 0), 1.6)                  # (rendu détaillé : AUCUN flou, consigne de l'auteur)
    voile = 0.12 if detail else 0.22
    return np.clip(im.astype(np.float32) * (1 - voile) + 255 * voile, 0, 255).astype(np.uint8)

def generer(decoupage, graine=7, delai=1200, lumiere="", plans=None):  # 1re fois : téléchargement des poids SDXL (~7 Go)
    """decoupage : scènes de l'auteur ; renvoie {indice de scène: image RGB uint8 1080x1920}.
    lumiere : ambiance de l'épisode choisie par le studio (« warm golden evening light, lamps on »…), ajoutée à chaque décor."""
    PROFONDEURS.clear(); PANNEAUX.clear()
    demandes = [(k, sc["decor"].strip() + (f", {lumiere}" if lumiere else "")) for k, sc in enumerate(decoupage or [])
                if sc.get("decor") and sc["decor"].strip().lower() not in ("plain", "uni", "")]
    if not demandes: return {}
    uniques = list(dict.fromkeys(d for _, d in demandes))                 # même lieu = même décor, généré une seule fois
    out, deja = {}, {}
    if os.environ.get("REFAIRE", "").endswith("|decors"): pass              # bouton « nouveaux décors » : on ne reprend pas la banque
    else:
        for d in uniques:
            f_ = os.path.join(BANQUE, _cle(d) + ".jpg")
            if os.path.exists(f_): deja[d] = cv2.cvtColor(cv2.imread(f_), cv2.COLOR_BGR2RGB)
    for k, d in demandes:
        if d in deja:
            out[k] = deja[d]; print(f"  décor {k} (lieu déjà connu) : {d[:70]}", flush=True)
            fp = os.path.join(BANQUE, _cle(d) + "_prof.png")
            if os.path.exists(fp): PROFONDEURS[k] = cv2.GaussianBlur(cv2.resize(cv2.imread(fp, 0), (W, H), interpolation=cv2.INTER_LINEAR), (0, 0), 6)
            fj = os.path.join(BANQUE, _cle(d) + "_panneaux.json")
            if os.path.exists(fj):
                import json
                try: PANNEAUX[k] = [tuple(r) for r in json.load(open(fj))]
                except (OSError, ValueError): pass
    uniques = [d for d in uniques if d not in deja]
    if not uniques: return out
    if not os.environ.get("REFAIRE", "").endswith("|decors"):              # D2 : lieu ressemblant déjà dans la banque -> réutilisé
        budget_ok = generes_ce_mois() < int(os.environ.get("DECORS_MOIS") or 60)   # D1 : budget Modal (décors neufs par mois)
        for d in list(uniques):
            proche = voisin(d, 0.55 if budget_ok else 0.25)
            if proche is None: continue
            im, cle = proche; im = varier(im, d)
            for k, d_ in demandes:
                if d_ == d:
                    out[k] = im; print(f"  décor {k} (lieu ressemblant de la banque{'' if budget_ok else ', budget Modal du mois atteint'}) : {d[:60]}", flush=True)
                    fp = os.path.join(BANQUE, cle + "_prof.png")
                    if os.path.exists(fp): PROFONDEURS[k] = cv2.GaussianBlur(cv2.resize(cv2.imread(fp, 0), (W, H), interpolation=cv2.INTER_LINEAR), (0, 0), 6)
            uniques.remove(d)
        if not uniques: return out
    try:
        import modal
        pl = [_png(plans.get(next(k for k, d_ in demandes if d_ == d))) if plans else b"" for d in uniques]   # plan dessiné de chaque décor
        D_ = modal.Cls.from_name("jt-decor", "Decor")()
        profs = {}
        try:                                                               # décor net (agrandi par l'IA) + profondeur
            res = D_.generer_net.spawn(uniques, graine, pl if any(pl) else None).get(timeout=delai)
            pngs = {d: r[0] for d, r in zip(uniques, res)}; profs = {d: r[1] for d, r in zip(uniques, res)}
        except Exception as e:                                             # ancienne version déployée : décor simple
            print(f"  décors nets indisponibles ({type(e).__name__} {str(e)[:100]}) : décors simples", flush=True)
            try: f = D_.generer.spawn(uniques, graine, pl if any(pl) else None)
            except TypeError: f = D_.generer.spawn(uniques, graine)
            pngs = dict(zip(uniques, f.get(timeout=delai)))
    except Exception as e:
        print(f"Décors indisponibles ({type(e).__name__} {str(e)[:150]}) : fonds unis.", flush=True); return out
    faits = set()
    for k, d in demandes:
        png = pngs.get(d)
        if png:
            try:
                out[k] = _format(png); print(f"  décor {k} : {d[:70]}", flush=True)
                if _format.panneaux: PANNEAUX[k] = list(_format.panneaux)
                pr = None
                try: pr = _prof(profs.get(d))
                except Exception: pr = None
                if pr is not None: PROFONDEURS[k] = pr
                if d not in faits: _ranger(d, out[k], pr); faits.add(d)
            except Exception as e: print(f"  décor {k} illisible : {e}", flush=True)
    return out


SEMI = set()                                                               # scènes dont le décor est semi-réaliste (dernier appel)

def generer_semi(sk, graine=7, scenes=None, delai=1200):
    """Décors « semi-réalistes » (moteur/semi_realiste.py, réglage STYLE_DECOR) : une peinture par lieu, cadrée pour que les pieds
    des personnages soient sur le sol libre. Banque à part (descriptions « [semi] … », déjà cadrées) ; lieu ressemblant réutilisé ;
    budget mensuel DECORS_MOIS comme les autres décors. Renvoie {scène: image 1080x1920} ; une scène absente = décor dessiné (croquis)."""
    import semi_realiste as SR, studio
    PROFONDEURS.clear(); PANNEAUX.clear(); SEMI.clear()
    dec = sk.get("decoupage") or []
    if not dec: return {}
    roles = [r for r in dict.fromkeys(x["p"] for x in sk.get("repliques", [])) if r != "narrateur"]
    try: lieux = studio.bible(sk, roles)["lieux"]
    except Exception: lieux = ["salon"]
    reps = sk.get("repliques") or []
    demandes = []                                                          # (scène, description, personnages à l'image)
    for k, sc in enumerate(dec):
        if scenes is not None and k not in scenes: continue
        lieu = lieux[min(k, len(lieux) - 1)] if lieux else "salon"
        if lieu == "voiture": continue                                     # intérieur de voiture : décor dessiné (volant au premier plan)
        n = len({reps[i]["p"] for i in sc.get("repliques", []) if 0 <= i < len(reps) and reps[i].get("p") != "narrateur"}) or len(roles) or 1
        demandes.append((k, SR.description(lieu, sc.get("decor", "")), max(1, min(3, n))))
    if not demandes: return {}
    out = {}
    def poser(k, im, prof):
        out[k] = im; SEMI.add(k)
        if prof is not None: PROFONDEURS[k] = cv2.GaussianBlur(prof, (0, 0), 6)
    refaire = os.environ.get("REFAIRE", "").endswith("|decors")
    budget_ok = generes_ce_mois() < int(os.environ.get("DECORS_MOIS") or 60)
    a_faire = []
    for k, d, n in demandes:
        f_ = os.path.join(BANQUE, _cle(d) + ".jpg"); fp = os.path.join(BANQUE, _cle(d) + "_prof.png")
        if not refaire and os.path.exists(f_):
            prof = cv2.resize(cv2.imread(fp, 0), (W, H)) if os.path.exists(fp) else None
            poser(k, cv2.cvtColor(cv2.imread(f_), cv2.COLOR_BGR2RGB), prof); print(f"  décor semi-réaliste {k} (lieu déjà connu) : {d[:70]}", flush=True); continue
        proche = None if refaire else voisin(d, 0.55 if budget_ok else 0.25)
        if proche is not None:                                             # (pas de miroir : le cadrage des pieds est gardé)
            im, cle = proche; fp = os.path.join(BANQUE, cle + "_prof.png")
            poser(k, im, cv2.resize(cv2.imread(fp, 0), (W, H)) if os.path.exists(fp) else None)
            print(f"  décor semi-réaliste {k} (lieu ressemblant de la banque) : {d[:60]}", flush=True); continue
        if budget_ok: a_faire.append((k, d, n))
        else: print(f"  décor semi-réaliste {k} : budget Modal du mois atteint, décor dessiné", flush=True)
    if not a_faire: return out
    uniques = list(dict.fromkeys(d for _, d, _ in a_faire))
    try:
        import modal
        D_ = modal.Cls.from_name("jt-decor", "Decor")()
        res = D_.generer_semi.spawn([d.replace("[semi]", "").strip() for d in uniques], graine, 2).get(timeout=delai)
    except Exception as e:
        print(f"Décors semi-réalistes indisponibles ({type(e).__name__} {str(e)[:150]}) : décors dessinés", flush=True); return out
    tirages = dict(zip(uniques, res))
    for k, d, n in a_faire:
        best = None
        for png, ppng in tirages.get(d) or []:
            try:
                im = np.array(Image.open(io.BytesIO(png)).convert("RGB")); pr = np.array(Image.open(io.BytesIO(ppng)).convert("L")) if ppng else None
                r = SR.cadrer(im, pr, n)
                if r and (best is None or r[2] < best[2]): best = r
            except Exception as e: print(f"  tirage illisible : {e}", flush=True)
        if best is None:
            print(f"  décor semi-réaliste {k} : aucun sol libre pour poser les pieds, décor dessiné : {d[:60]}", flush=True); continue
        im, pr, z = best; im, pan = faux_textes(im)
        if pan: PANNEAUX[k] = pan
        poser(k, im, pr); print(f"  décor semi-réaliste {k} (cadré ×{z:.2f}, pieds au sol) : {d[:60]}", flush=True)
        if not os.path.exists(os.path.join(BANQUE, _cle(d) + ".jpg")):
            _format.panneaux = pan; _ranger(d, im, pr)
    return out
