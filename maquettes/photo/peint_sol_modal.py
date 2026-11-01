"""Essai visuel (3) : peinture avec un grand sol libre au premier plan (pieds posés au sol). seulement (demande de l'auteur, 1er novembre 2026) : décors PHOTO RÉALISTES avec le même modèle (Stable Diffusion XL
sur Modal), pour voir si ça plaît. App éphémère « modal run » : rien n'est déployé, le robot n'est pas touché."""
import io, modal

app = modal.App("jt-essai-peint-sol")
cache = modal.Volume.from_name("jt-cache", create_if_missing=True)
img = (modal.Image.debian_slim(python_version="3.11")
       .pip_install("torch==2.5.1", "diffusers>=0.32,<0.36", "transformers>=4.45,<5", "accelerate", "safetensors", "pillow")
       .env({"HF_HOME": "/cache/hf"}))
STYLE = ("{decor}, semi-realistic digital painting, animated movie background art, soft painterly brushstrokes, "
         "slightly simplified shapes, warm soft lighting, empty scene, no people, eye level, clean and sharp")
NEGATIF = ("people, person, human, face, animal, text, letters, words, logo, watermark, photo, photograph, photorealistic, hyperrealistic, "
           "3d render, blurry, out of focus, bokeh, depth of field, fisheye, distorted")
DECORS = ["a cozy french living room seen from the doorway, low camera, large empty wooden floor in the whole foreground, "
          "grey sofa and plants against the far wall, window with curtains, nothing in the foreground"] * 4

@app.function(gpu="L40S", image=img, volumes={"/cache": cache}, timeout=1500)
def faire(decors: list, graine: int = 11) -> list:
    import torch
    from diffusers import StableDiffusionXLPipeline
    pipe = StableDiffusionXLPipeline.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", torch_dtype=torch.float16,
                                                     variant="fp16", use_safetensors=True).to("cuda")
    out = []
    for k, d in enumerate(decors):
        im = pipe(STYLE.format(decor=d), negative_prompt=NEGATIF, height=1536, width=880, num_inference_steps=34, guidance_scale=6.5,
                  generator=torch.Generator("cuda").manual_seed(graine + k)).images[0]
        b = io.BytesIO(); im.save(b, format="PNG"); out.append(b.getvalue())
    return out

@app.local_entrypoint()
def main():
    import os
    os.makedirs("maquettes/photo/peints", exist_ok=True)  # 4 tirages du même salon
    for k, p in enumerate(faire.remote(DECORS)):
        open(f"maquettes/photo/peints/salon_sol_{k}.png", "wb").write(p); print("décor", k, len(p))
