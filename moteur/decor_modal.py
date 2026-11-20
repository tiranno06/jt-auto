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
         "bright colors, many props, lived-in details, blank posters, TikTok cartoon style, eye level, sharp")                       # décor en premier : SDXL ne lit qu'environ 77 jetons
NEGATIF = ("people, person, human, man, woman, child, character, face, animal, text, letters, words, logo, watermark, signature, "
           "photo, photorealistic, 3d render, realistic, noisy, hatching, grainy texture, gradient shading, dark, blurry, out of focus, depth of field, bokeh, "
           "writing, lettering, captions, gibberish text, signs with words, typography")
STYLE_SEMI = ("{decor}, semi-realistic digital painting, animated movie background art, soft painterly brushstrokes, "
              "slightly simplified shapes, warm soft lighting, low camera, furniture against the far wall, nothing in the foreground, empty scene, no people, sharp")
NEGATIF_SEMI = ("people, person, human, face, animal, text, letters, words, logo, watermark, photo, photograph, photorealistic, hyperrealistic, "
                "3d render, blurry, out of focus, bokeh, depth of field, fisheye, distorted, furniture in the foreground, table in the foreground")
# agrandisseur IA (Real-ESRGAN « anime », licence BSD-3) : décor plus fin et plus net ; profondeur (Depth Anything V2 Small, Apache-2.0)
AGRANDISSEUR = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"
PROFONDEUR = "depth-anything/Depth-Anything-V2-Small-hf"
CONTROLNET = "diffusers/controlnet-depth-sdxl-1.0-small"                   # composition copiée sur la vidéo d'origine (idée 10, 20 novembre)

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
            return Image.fromarray(y).resize((1100, 1920), Image.LANCZOS)    # même proportion (le client recadre en 1080x1920)
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
                    init = Image.open(io.BytesIO(plan)).convert("RGB").resize((880, 1536))
                    im = self.retouche(STYLE.format(decor=" ".join(str(d).split()[:42])), negative_prompt=NEGATIF, image=init, strength=0.62, num_inference_steps=36,
                                       guidance_scale=6.5, generator=g).images[0]
                else:
                    im = self.pipe(STYLE.format(decor=" ".join(str(d).split()[:42])), negative_prompt=NEGATIF, height=1536, width=880, num_inference_steps=32,
                                   guidance_scale=6.5, generator=g).images[0]
                b = io.BytesIO(); im.save(b, format="PNG"); out.append(b.getvalue())
            except Exception as e:
                print("decor:", e); out.append(b"")
        return out

    @modal.method()
    def generer_semi(self, decors: list, graine: int = 7, n: int = 2, guides: list = None) -> list:
        """Décors « semi-réalistes » (réglage STYLE_DECOR, choix de l'auteur du 1er novembre 2026) : peinture façon fond de film
        d'animation, avec un grand sol libre devant (le robot y pose les pieds : moteur/semi_realiste.py). n tirages par décor ;
        pour chaque décor : [(png net 1100x1920, png profondeur)].
        guides (20 novembre, idée 10) : pour chaque décor, (png de la vidéo d'origine, boîtes des personnes en fraction) ou None :
        les premiers tirages reprennent la COMPOSITION de l'original (carte de profondeur de l'image, personnes effacées, ControlNet
        « depth » de SDXL, influence douce) ; le dernier tirage reste libre (au cas où l'original n'a pas de sol libre)."""
        import torch
        from PIL import Image
        out = []
        for k, d in enumerate(decors):
            tirages = []
            guide = (guides or [None] * len(decors))[k] if guides else None
            carte = self._carte_guide(guide) if guide else None
            for j in range(max(1, n)):
                try:
                    g = torch.Generator("cuda").manual_seed(graine + 101 * k + j)
                    invite = STYLE_SEMI.format(decor=" ".join(str(d).split()[:40]))
                    if carte is not None and j < max(1, n) - 1 and self._controlnet() is not None:
                        im = self.cn_pipe(invite, negative_prompt=NEGATIF_SEMI, image=carte, height=1536, width=880, num_inference_steps=34,
                                          guidance_scale=6.5, controlnet_conditioning_scale=0.45, control_guidance_end=0.6, generator=g).images[0]
                    else:
                        im = self.pipe(invite, negative_prompt=NEGATIF_SEMI, height=1536, width=880,
                                       num_inference_steps=34, guidance_scale=6.5, generator=g).images[0]
                    b = io.BytesIO(); im.resize((1100, 1920), Image.LANCZOS).save(b, format="PNG")   # pas l'agrandisseur « anime » : il donnait un style BD
                    tirages.append((b.getvalue(), self._profondeur(im)))
                except Exception as e:
                    print("decor semi:", e)
            out.append(tirages)
        return out

    def _controlnet(self):
        """ControlNet « depth » de SDXL (diffusers, licence openrail++), chargé une fois, au premier décor guidé ; None si absent."""
        if getattr(self, "_cn_essaye", False): return getattr(self, "cn_pipe", None)
        self._cn_essaye = True
        try:
            import torch
            from diffusers import ControlNetModel, StableDiffusionXLControlNetPipeline
            cn = ControlNetModel.from_pretrained(CONTROLNET, torch_dtype=torch.float16, use_safetensors=True).to("cuda")
            self.cn_pipe = StableDiffusionXLControlNetPipeline(**self.pipe.components, controlnet=cn)
            cache.commit()
        except Exception as e:
            print("ControlNet indisponible :", e); self.cn_pipe = None
        return self.cn_pipe

    def _carte_guide(self, guide):
        """Image de l'original -> carte de profondeur 880x1536 où les personnes sont effacées (remplacées par le fond de leur ligne)."""
        if self.prof is None: return None
        import numpy as np
        from PIL import Image
        try:
            png, boites = guide[0], guide[1] if len(guide) > 1 else []
            im = Image.open(io.BytesIO(png)).convert("RGB").resize((880, 1536))
            dp = np.asarray(self.prof(im.resize((518, 924)))["depth"], np.float32)
            dp = np.asarray(Image.fromarray(dp).resize((880, 1536)), np.float32)
            for b in boites or []:
                x0, y0, x1, y1 = int(b[0] * 880), int(b[1] * 1536), int(b[2] * 880), int(b[3] * 1536)
                x0, x1 = max(0, x0 - 20), min(880, x1 + 20); y0, y1 = max(0, y0 - 20), min(1536, y1 + 20)
                if x1 <= x0 or y1 <= y0: continue
                g_ = dp[y0:y1, max(0, x0 - 30):x0].mean(1) if x0 > 0 else None; d_ = dp[y0:y1, x1:min(880, x1 + 30)].mean(1) if x1 < 880 else None
                bord = g_ if d_ is None else d_ if g_ is None else (g_ + d_) / 2
                if bord is not None: dp[y0:y1, x0:x1] = bord[:, None]
            dp = (dp - dp.min()) / max(1e-6, dp.max() - dp.min()) * 255
            return Image.fromarray(dp.astype(np.uint8)).convert("RGB")
        except Exception as e:
            print("carte de composition :", e); return None

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
