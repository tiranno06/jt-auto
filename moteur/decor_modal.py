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
STYLE = ("{decor}, flat 2D cartoon background, empty scene, no people, thin black outlines, soft pastel flat colors, "
         "very minimalist, few objects, large simple shapes, cute webcomic style, eye level view")                       # décor en premier : SDXL ne lit qu'environ 77 jetons
NEGATIF = ("people, person, human, man, woman, child, character, face, animal, text, letters, words, logo, watermark, signature, "
           "photo, photorealistic, 3d render, realistic, noisy, cluttered, detailed, intricate, hatching, texture, dark, blurry")

@app.cls(gpu="L40S", image=img, volumes={"/cache": cache}, timeout=1200, scaledown_window=60)
class Decor:
    @modal.enter()
    def charger(self):
        import torch
        from diffusers import StableDiffusionXLPipeline
        self.pipe = StableDiffusionXLPipeline.from_pretrained(MODELE, torch_dtype=torch.float16, variant="fp16", use_safetensors=True).to("cuda")
        cache.commit()

    @modal.method()
    def generer(self, decors: list, graine: int = 7) -> list:
        """decors : descriptions en anglais (lieu + objets du gag). Renvoie des PNG 768x1344 (9:16)."""
        import torch
        out = []
        for k, d in enumerate(decors):
            try:
                im = self.pipe(STYLE.format(decor=d), negative_prompt=NEGATIF, height=1344, width=768, num_inference_steps=30,
                               guidance_scale=6.5, generator=torch.Generator("cuda").manual_seed(graine + k)).images[0]
                b = io.BytesIO(); im.save(b, format="PNG"); out.append(b.getvalue())
            except Exception as e:
                print("decor:", e); out.append(b"")
        return out
