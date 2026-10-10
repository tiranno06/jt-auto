"""Client des décors du moteur cartoon : demande à Modal (FLUX.1-schnell) un décor par scène et le met au format 1080x1920.
En cas de souci (Modal indisponible, modèle inaccessible), renvoie {} : le moteur cartoon utilise alors des fonds unis pastel."""
import io
import numpy as np, cv2
from PIL import Image

W, H = 1080, 1920

def _format(png):
    im = np.array(Image.open(io.BytesIO(png)).convert("RGB"))
    s = max(W / im.shape[1], H / im.shape[0])
    im = cv2.resize(im, (int(im.shape[1] * s + 0.5), int(im.shape[0] * s + 0.5)), interpolation=cv2.INTER_CUBIC)
    y0, x0 = (im.shape[0] - H) // 2, (im.shape[1] - W) // 2
    return np.ascontiguousarray(im[y0:y0 + H, x0:x0 + W])

def generer(decoupage, graine=7, delai=1500):              # 1re fois : téléchargement des poids FLUX (~30 Go)
    """decoupage : scènes de l'auteur ; renvoie {indice de scène: image RGB uint8 1080x1920}."""
    demandes = [(k, sc["decor"]) for k, sc in enumerate(decoupage or [])
                if sc.get("decor") and sc["decor"].strip().lower() not in ("plain", "uni", "")]
    if not demandes: return {}
    try:
        import modal
        f = modal.Cls.from_name("jt-decor", "Decor")().generer.spawn([d for _, d in demandes], graine)
        pngs = f.get(timeout=delai)
    except Exception as e:
        print(f"Décors indisponibles ({type(e).__name__} {str(e)[:150]}) : fonds unis.", flush=True); return {}
    out = {}
    for (k, d), png in zip(demandes, pngs):
        if png:
            try: out[k] = _format(png); print(f"  décor {k} : {d[:70]}", flush=True)
            except Exception as e: print(f"  décor {k} illisible : {e}", flush=True)
    return out
