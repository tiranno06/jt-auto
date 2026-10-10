"""Client des décors du moteur cartoon : demande à Modal (Stable Diffusion XL) un décor par scène et le met au format 1080x1920.
En cas de souci (Modal indisponible, modèle inaccessible), renvoie {} : le moteur cartoon utilise alors des fonds unis pastel."""
import hashlib, io, os, re
import numpy as np, cv2
from PIL import Image

W, H = 1080, 1920
BANQUE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "decors")   # lieux déjà dessinés, réutilisés tels quels

def _cle(d):
    return hashlib.sha1(re.sub(r"[^a-z0-9]+", " ", d.lower()).strip().encode()).hexdigest()[:16]

def lieux_connus(n=12):
    """Décors déjà dans la banque (pour que l'auteur réutilise exactement les mêmes lieux)."""
    try: idx = [l.rstrip("\n").split("\t", 1) for l in open(os.path.join(BANQUE, "index.tsv"), encoding="utf-8")]
    except OSError: return []
    return [d for _, d in idx[-n:]]

def _ranger(d, im):
    os.makedirs(BANQUE, exist_ok=True); k = _cle(d)
    cv2.imwrite(os.path.join(BANQUE, k + ".jpg"), cv2.cvtColor(im, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
    with open(os.path.join(BANQUE, "index.tsv"), "a", encoding="utf-8") as f: f.write(f"{k}\t{d}\n")

def _format(png):
    im = np.array(Image.open(io.BytesIO(png)).convert("RGB"))
    s = max(W / im.shape[1], H / im.shape[0])
    im = cv2.resize(im, (int(im.shape[1] * s + 0.5), int(im.shape[0] * s + 0.5)), interpolation=cv2.INTER_CUBIC)
    y0, x0 = (im.shape[0] - H) // 2, (im.shape[1] - W) // 2
    return simplifier(np.ascontiguousarray(im[y0:y0 + H, x0:x0 + W]))

def simplifier(im):
    """Style des chaînes analysées : aplats lissés (moins de détails), couleurs plus claires et un léger flou,
    pour que les personnages blancs ressortent nettement devant le décor."""
    im = cv2.edgePreservingFilter(im, flags=1, sigma_s=70, sigma_r=0.45)
    im = cv2.GaussianBlur(im, (0, 0), 1.6)
    return np.clip(im.astype(np.float32) * 0.78 + 255 * 0.22, 0, 255).astype(np.uint8)

def generer(decoupage, graine=7, delai=1200):              # 1re fois : téléchargement des poids SDXL (~7 Go)
    """decoupage : scènes de l'auteur ; renvoie {indice de scène: image RGB uint8 1080x1920}."""
    demandes = [(k, sc["decor"].strip()) for k, sc in enumerate(decoupage or [])
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
        if d in deja: out[k] = deja[d]; print(f"  décor {k} (lieu déjà connu) : {d[:70]}", flush=True)
    uniques = [d for d in uniques if d not in deja]
    if not uniques: return out
    try:
        import modal
        f = modal.Cls.from_name("jt-decor", "Decor")().generer.spawn(uniques, graine)
        pngs = dict(zip(uniques, f.get(timeout=delai)))
    except Exception as e:
        print(f"Décors indisponibles ({type(e).__name__} {str(e)[:150]}) : fonds unis.", flush=True); return out
    faits = set()
    for k, d in demandes:
        png = pngs.get(d)
        if png:
            try:
                out[k] = _format(png); print(f"  décor {k} : {d[:70]}", flush=True)
                if d not in faits: _ranger(d, out[k]); faits.add(d)
            except Exception as e: print(f"  décor {k} illisible : {e}", flush=True)
    return out
