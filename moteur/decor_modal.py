"""Décors du moteur cartoon, générés sur GPU Modal avec Stable Diffusion XL 1.0 (Stability AI, licence CreativeML Open RAIL++-M :
usage commercial autorisé, téléchargement libre). Uniquement les décors : les personnages sont dessinés et animés par marionnette.py.
Style imposé : dessin 2D plat, trait noir, couleurs pastel douces, sans personne ni texte.
Déployé automatiquement par le robot : `modal deploy moteur/decor_modal.py`."""
import io
import modal

app = modal.App("jt-decor")
cache = modal.Volume.from_name("jt-cache", create_if_missing=True)
img = (modal.Image.debian_slim(python_version="3.11")
       .pip_install("torch==2.5.1", "diffusers>=0.32,<0.36", "transformers>=4.45,<5", "accelerate", "safetensors", "pillow")
       .env({"HF_HOME": "/cache/hf"}))

MODELE = "stabilityai/stable-diffusion-xl-base-1.0"
STYLE = ("{decor}, detailed 2D cartoon background, empty scene, no people, thick black outlines, flat bright colors, "
         "many props and furniture, lived-in details, TikTok cartoon animation style, eye level view")                       # décor en premier : SDXL ne lit qu'environ 77 jetons
NEGATIF = ("people, person, human, man, woman, child, character, face, animal, text, letters, words, logo, watermark, signature, "
           "photo, photorealistic, 3d render, realistic, noisy, hatching, grainy texture, gradient shading, dark, blurry")

@app.cls(gpu="L40S", image=img, volumes={"/cache": cache}, timeout=1200, scaledown_window=60)
class Decor:
    @modal.enter()
    def charger(self):
        import torch
        from diffusers import StableDiffusionXLPipeline, StableDiffusionXLImg2ImgPipeline
        self.pipe = StableDiffusionXLPipeline.from_pretrained(MODELE, torch_dtype=torch.float16, variant="fp16", use_safetensors=True).to("cuda")
        self.retouche = StableDiffusionXLImg2ImgPipeline(**self.pipe.components)  # même modèle : « peint par-dessus » un plan de décor
        cache.commit()

    @modal.method()
    def generer(self, decors: list, graine: int = 7, plans: list = None) -> list:
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
                    im = self.retouche(STYLE.format(decor=d), negative_prompt=NEGATIF, image=init, strength=0.62, num_inference_steps=36,
                                       guidance_scale=6.5, generator=g).images[0]
                else:
                    im = self.pipe(STYLE.format(decor=d), negative_prompt=NEGATIF, height=1344, width=768, num_inference_steps=30,
                                   guidance_scale=6.5, generator=g).images[0]
                b = io.BytesIO(); im.save(b, format="PNG"); out.append(b.getvalue())
            except Exception as e:
                print("decor:", e); out.append(b"")
        return out
