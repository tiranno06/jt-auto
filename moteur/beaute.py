"""Note de beauté d'une image : prédicteur esthétique LAION v1 (CLIP ViT-B/16 + une couche ; LAION, licence MIT ; poids
shunk031/aesthetics-predictor-v1-vit-base-patch16 en safetensors, chargés SANS code extérieur). Choix de l'auteur du 11 novembre
2026, idée 13 : parmi les 3 décors tirés par l'IA pour un même lieu, le robot garde celui qui est cadrable (pieds au sol) ET le plus
réussi, au lieu du seul cadrage le moins zoomé. Note ~1 à 10 (plus haut = plus beau), ~0,3 s par image sur la machine.
Absent -> None (on garde l'ancien choix). BEAUTE=0 pour couper."""
import json, os
import numpy as np

DEPOT = "shunk031/aesthetics-predictor-v1-vit-base-patch16"
_M = {}


def _modele():
    if "m" in _M: return _M["m"]
    import torch
    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file
    from transformers import CLIPVisionConfig, CLIPVisionModelWithProjection, CLIPImageProcessor
    c = json.load(open(hf_hub_download(DEPOT, "config.json")))
    cfg = CLIPVisionConfig(**{k: c[k] for k in ("hidden_size", "intermediate_size", "num_hidden_layers", "num_attention_heads", "image_size",
                                                "patch_size", "projection_dim", "hidden_act", "layer_norm_eps", "num_channels") if k in c})
    vis = CLIPVisionModelWithProjection(cfg).eval()
    poids = load_file(hf_hub_download(DEPOT, "model.safetensors"))
    vis.load_state_dict({k: v for k, v in poids.items() if not k.startswith("predictor.")}, strict=False)
    tete = torch.nn.Linear(cfg.projection_dim, 1)
    tete.load_state_dict({"weight": poids["predictor.weight"], "bias": poids["predictor.bias"]})
    proc = CLIPImageProcessor.from_pretrained(DEPOT)
    _M["m"] = (proc, vis, tete.eval())
    return _M["m"]


def note(img):
    """Note de beauté (float) d'une image RGB (tableau numpy ou PIL), ou None."""
    if os.environ.get("BEAUTE", "1") == "0" or _M.get("echec"): return None
    try:
        import torch
        from PIL import Image
        proc, vis, tete = _modele()
        im = img if isinstance(img, Image.Image) else Image.fromarray(np.asarray(img, np.uint8))
        with torch.no_grad():
            e = vis(**proc(images=im.convert("RGB"), return_tensors="pt")).image_embeds
            e = e / e.norm(dim=-1, keepdim=True)
            return round(float(tete(e)[0, 0]), 3)
    except Exception as ex:
        print(f"  note de beauté indisponible ({str(ex)[:100]})", flush=True); _M["echec"] = True
        return None


def choisir(candidats):
    """candidats = [(zoom du cadrage, note de beauté ou None, objet)] -> l'objet gardé : le plus beau parmi les cadrages pas plus
    de 25 % plus zoomés que le meilleur (un zoom fort grossit le grain de l'image) ; sans notes, le moins zoomé (comme avant)."""
    if not candidats: return None
    zmin = min(z for z, _, _ in candidats)
    ok = [c for c in candidats if c[0] <= zmin * 1.25]
    if all(n is not None for _, n, _ in ok) and len(ok) > 1:
        return max(ok, key=lambda c: (c[1], -c[0]))[2]
    return min(candidats, key=lambda c: c[0])[2]
