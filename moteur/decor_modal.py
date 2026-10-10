"""Décors du moteur cartoon, générés sur GPU Modal avec FLUX.1-schnell (Black Forest Labs, licence Apache 2.0, usage commercial autorisé).
Uniquement les décors : les personnages sont dessinés et animés par marionnette.py. Style imposé : dessin 2D plat, trait noir,
couleurs pastel douces, sans personne ni texte. Déployé automatiquement par le robot : `modal deploy moteur/decor_modal.py`."""
import io
import modal

app = modal.App("jt-decor")
cache = modal.Volume.from_name("jt-cache", create_if_missing=True)
img = (modal.Image.debian_slim(python_version="3.11")
       .pip_install("torch==2.5.1", "diffusers>=0.32,<0.36", "transformers>=4.45,<5", "accelerate", "sentencepiece", "protobuf", "pillow")
       .env({"HF_HOME": "/cache/hf"}))

STYLE = ("flat 2D cartoon background illustration, {decor}, completely empty scene, no people, no characters, no animals, no text, no letters, "
         "simple clean shapes, thin clean black outlines, soft muted pastel colors, minimal details, cozy cute webcomic style, "
         "front view at eye level, the floor fills the lower third, plenty of empty space in the middle")

@app.cls(gpu="L40S", image=img, volumes={"/cache": cache}, timeout=1200, scaledown_window=60)
class Decor:
    @modal.enter()
    def charger(self):
        import torch
        from diffusers import FluxPipeline
        self.pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16).to("cuda")
        cache.commit()

    @modal.method()
    def generer(self, decors: list, graine: int = 7) -> list:
        """decors : descriptions en anglais (« a small cozy bar with wooden tables »). Renvoie des PNG 768x1344 (9:16)."""
        import torch
        out = []
        for k, d in enumerate(decors):
            try:
                im = self.pipe(STYLE.format(decor=d), height=1344, width=768, num_inference_steps=4, guidance_scale=0.0,
                               max_sequence_length=256, generator=torch.Generator("cuda").manual_seed(graine + k)).images[0]
                b = io.BytesIO(); im.save(b, format="PNG"); out.append(b.getvalue())
            except Exception as e:
                print("decor:", e); out.append(b"")
        return out
