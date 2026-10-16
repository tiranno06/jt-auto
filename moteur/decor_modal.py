"""Décors du moteur cartoon, générés sur GPU Modal avec Stable Diffusion XL 1.0 (Stability AI, licence CreativeML Open RAIL++-M :
usage commercial autorisé, téléchargement libre). Uniquement les décors : les personnages sont dessinés et animés par marionnette.py.
Style imposé : dessin 2D plat, trait noir, couleurs pastel douces, sans personne ni texte.
Déployé automatiquement par le robot : `modal deploy moteur/decor_modal.py`."""
import io
import modal

app = modal.App("jt-decor")
cache = modal.Volume.from_name("jt-cache", create_if_missing=True)
img = (modal.Image.debian_slim(python_version="3.11")
       .pip_install("torch==2.5.1", "diffusers>=0.32,<0.36", "transformers>=4.45,<5", "accelerate", "safetensors", "pillow", "spandrel>=0.4,<1")
       .env({"HF_HOME": "/cache/hf"}))

MODELE = "stabilityai/stable-diffusion-xl-base-1.0"
STYLE = ("{decor}, detailed 2D cartoon background, empty scene, no people, clean thick black outlines, flat cel shading, "
         "bright colors, many props, lived-in details, TikTok cartoon style, eye level, sharp")                       # décor en premier : SDXL ne lit qu'environ 77 jetons
NEGATIF = ("people, person, human, man, woman, child, character, face, animal, text, letters, words, logo, watermark, signature, "
           "photo, photorealistic, 3d render, realistic, noisy, hatching, grainy texture, gradient shading, dark, blurry, out of focus, depth of field, bokeh")
# agrandisseur IA (Real-ESRGAN « anime », licence BSD-3) : décor plus fin et plus net ; profondeur (Depth Anything V2 Small, Apache-2.0)
AGRANDISSEUR = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"
PROFONDEUR = "depth-anything/Depth-Anything-V2-Small-hf"

@app.cls(gpu="L40S", image=img, volumes={"/cache": cache}, timeout=1200, scaledown_window=60)
class Decor:
    @modal.enter()
    def charger(self):
        import torch
        from diffusers import StableDiffusionXLPipeline, StableDiffusionXLImg2ImgPipeline
        self.pipe = StableDiffusionXLPipeline.from_pretrained(MODELE, torch_dtype=torch.float16, variant="fp16", use_safetensors=True).to("cuda")
        self.retouche = StableDiffusionXLImg2ImgPipeline(**self.pipe.components)  # même modèle : « peint par-dessus » un plan de décor
        self.agr, self.prof = None, None
        try:                                                               # agrandisseur : facultatif (le décor sort quand même)
            import os, urllib.request, spandrel
            f = "/cache/esrgan_anime6b.pth"
            if not os.path.exists(f): urllib.request.urlretrieve(AGRANDISSEUR, f)
            self.agr = spandrel.ModelLoader().load_from_file(f).cuda().eval().half()
        except Exception as e: print("agrandisseur indisponible :", e)
        try:
            from transformers import pipeline
            self.prof = pipeline("depth-estimation", model=PROFONDEUR, device=0)
        except Exception as e: print("profondeur indisponible :", e)
        cache.commit()

    def _net(self, im):
        """Agrandit x4 avec l'IA puis ramène à 1080x1920 : traits plus nets, aucun flou."""
        if self.agr is None: return im
        import numpy as np, torch
        from PIL import Image
        try:
            x = torch.from_numpy(np.asarray(im.convert("RGB"), np.float32) / 255).permute(2, 0, 1)[None].cuda().half()
            with torch.no_grad(): y = self.agr(x)
            y = (y[0].float().clamp(0, 1).permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
            return Image.fromarray(y).resize((1097, 1920), Image.LANCZOS)    # même proportion (le client recadre en 1080x1920)
        except Exception as e:
            print("agrandissement :", e); return im

    def _profondeur(self, im):
        """Carte de profondeur (blanc = près, noir = loin) pour faire glisser le premier plan plus vite que le fond."""
        if self.prof is None: return b""
        import numpy as np
        try:
            d = np.asarray(self.prof(im.convert("RGB").resize((518, 924)))["depth"], np.float32)
            d = (d - d.min()) / max(1e-6, d.max() - d.min()) * 255
            from PIL import Image
            b = io.BytesIO(); Image.fromarray(d.astype(np.uint8)).resize((540, 960)).save(b, format="PNG"); return b.getvalue()
        except Exception as e:
            print("profondeur :", e); return b""

    @modal.method()
    def generer(self, decors: list, graine: int = 7, plans: list = None) -> list:
        return self._faire(decors, graine, plans)

    def _faire(self, decors, graine=7, plans=None):
        """decors : descriptions en anglais (lieu + objets du gag). plans : PNG du décor dessiné par le robot (ou b"") : l'IA peint
        PAR-DESSUS ce plan (fenêtre, comptoir, lampes restent à leur place). Renvoie des PNG 768x1344 (9:16)."""
        import torch
        from PIL import Image
        out = []
        for k, d in enumerate(decors):
            try:
                g = torch.Generator("cuda").manual_seed(graine + k); plan = (plans or [b""] * len(decors))[k] if plans else b""
                if plan:
                    init = Image.open(io.BytesIO(plan)).convert("RGB").resize((768, 1344))
                    im = self.retouche(STYLE.format(decor=" ".join(str(d).split()[:42])), negative_prompt=NEGATIF, image=init, strength=0.62, num_inference_steps=36,
                                       guidance_scale=6.5, generator=g).images[0]
                else:
                    im = self.pipe(STYLE.format(decor=" ".join(str(d).split()[:42])), negative_prompt=NEGATIF, height=1344, width=768, num_inference_steps=30,
                                   guidance_scale=6.5, generator=g).images[0]
                b = io.BytesIO(); im.save(b, format="PNG"); out.append(b.getvalue())
            except Exception as e:
                print("decor:", e); out.append(b"")
        return out

    @modal.method()
    def generer_net(self, decors: list, graine: int = 7, plans: list = None) -> list:
        """Comme generer, puis décor agrandi par l'IA (1080x1920, net) et sa carte de profondeur : [(png, png_profondeur)]."""
        from PIL import Image
        out = []
        for png in self._faire(decors, graine, plans):
            if not png: out.append((b"", b"")); continue
            im = Image.open(io.BytesIO(png)); net = self._net(im)
            b = io.BytesIO(); net.save(b, format="PNG"); out.append((b.getvalue(), self._profondeur(im)))
        return out
