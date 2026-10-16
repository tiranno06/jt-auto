"""Client des décors du moteur cartoon : demande à Modal (Stable Diffusion XL) un décor par scène et le met au format 1080x1920.
En cas de souci (Modal indisponible, modèle inaccessible), renvoie {} : le moteur cartoon utilise alors des fonds unis pastel."""
import hashlib, io, os, re
import numpy as np, cv2
from PIL import Image

W, H = 1080, 1920
BANQUE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "decors")   # lieux déjà dessinés, réutilisés tels quels

STYLE_VERSION = "v4"                                                       # v4 : décor agrandi par l'IA (net) + carte de profondeur ; les anciens ne sont plus repris
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
    with open(os.path.join(BANQUE, "index.tsv"), "a", encoding="utf-8") as f: f.write(f"{k}\t{d}\n")

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
    return simplifier(_recadre(np.array(Image.open(io.BytesIO(png)).convert("RGB"))))

def _prof(png):
    """Carte de profondeur (PNG en niveaux de gris) au format 1080x1920, adoucie (c'est une carte, pas l'image : rien n'est flou)."""
    if not png: return None
    d = np.array(Image.open(io.BytesIO(png)).convert("L"))
    return cv2.GaussianBlur(_recadre(d, cv2.INTER_LINEAR), (0, 0), 6)

def simplifier(im):
    """Style des chaînes analysées : aplats lissés (moins de détails), couleurs plus claires et un léger flou,
    pour que les personnages blancs ressortent nettement devant le décor. Rendu détaillé : les personnages ont maintenant
    costumes, contours et ombres, le décor garde donc plus de détails (lissage et voile allégés)."""
    detail = (os.environ.get("RENDU_DETAILLE") or "1") != "0"
    im = cv2.edgePreservingFilter(im, flags=1, sigma_s=25 if detail else 70, sigma_r=0.2 if detail else 0.45)   # aplats, contours gardés nets
    if not detail: im = cv2.GaussianBlur(im, (0, 0), 1.6)                  # (rendu détaillé : AUCUN flou, consigne de l'auteur)
    voile = 0.12 if detail else 0.22
    return np.clip(im.astype(np.float32) * (1 - voile) + 255 * voile, 0, 255).astype(np.uint8)

def generer(decoupage, graine=7, delai=1200, lumiere="", plans=None):  # 1re fois : téléchargement des poids SDXL (~7 Go)
    """decoupage : scènes de l'auteur ; renvoie {indice de scène: image RGB uint8 1080x1920}.
    lumiere : ambiance de l'épisode choisie par le studio (« warm golden evening light, lamps on »…), ajoutée à chaque décor."""
    PROFONDEURS.clear()
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
    uniques = [d for d in uniques if d not in deja]
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
                pr = None
                try: pr = _prof(profs.get(d))
                except Exception: pr = None
                if pr is not None: PROFONDEURS[k] = pr
                if d not in faits: _ranger(d, out[k], pr); faits.add(d)
            except Exception as e: print(f"  décor {k} illisible : {e}", flush=True)
    return out
