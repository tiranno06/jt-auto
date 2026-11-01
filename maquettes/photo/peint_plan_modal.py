"""Essai visuel (2) : peinture posée sur le plan dessiné du robot. seulement (demande de l'auteur, 1er novembre 2026) : décors PHOTO RÉALISTES avec le même modèle (Stable Diffusion XL
sur Modal), pour voir si ça plaît. App éphémère « modal run » : rien n'est déployé, le robot n'est pas touché."""
import io, modal

app = modal.App("jt-essai-peint-plan")
cache = modal.Volume.from_name("jt-cache", create_if_missing=True)
img = (modal.Image.debian_slim(python_version="3.11")
       .pip_install("torch==2.5.1", "diffusers>=0.32,<0.36", "transformers>=4.45,<5", "accelerate", "safetensors", "pillow")
       .env({"HF_HOME": "/cache/hf"}))
STYLE = ("{decor}, semi-realistic digital painting, animated movie background art, soft painterly brushstrokes, "
         "slightly simplified shapes, warm soft lighting, empty scene, no people, eye level, clean and sharp")
NEGATIF = ("people, person, human, face, animal, text, letters, words, logo, watermark, photo, photograph, photorealistic, hyperrealistic, "
           "3d render, blurry, out of focus, bokeh, depth of field, fisheye, distorted")
FORCES = [0.55, 0.68, 0.8]
DECORS = ["a cozy french living room with a grey sofa, a coffee table, a TV on a cabinet, a window with curtains, plants",
          "a small french apartment kitchen with white cabinets, a fridge, a table with two chairs, a window",
          "a teenager bedroom with an unmade bed, posters on the wall, a desk with a computer, a window",
          "a quiet french street in front of a bakery, sidewalk, parked cars, apartment buildings"]

@app.function(gpu="L40S", image=img, volumes={"/cache": cache}, timeout=1500)
def faire(plan: bytes, decor: str, forces: list, graine: int = 11) -> list:
    """Peint PAR-DESSUS le plan du décor dessiné par le robot (comme le robot le fait déjà) : le sol reste là où il pose les pieds."""
    import torch
    from PIL import Image
    from diffusers import StableDiffusionXLImg2ImgPipeline
    pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", torch_dtype=torch.float16,
                                                            variant="fp16", use_safetensors=True).to("cuda")
    init = Image.open(io.BytesIO(plan)).convert("RGB").resize((880, 1536))
    out = []
    for k, f in enumerate(forces):
        im = pipe(STYLE.format(decor=decor), negative_prompt=NEGATIF, image=init, strength=f, num_inference_steps=40, guidance_scale=6.5,
                  generator=torch.Generator("cuda").manual_seed(graine + k)).images[0]
        b = io.BytesIO(); im.save(b, format="PNG"); out.append(b.getvalue())
    return out

@app.local_entrypoint()
def main():
    import os
    plan = open("maquettes/photo/plan_salon.png", "rb").read()
    for f, p in zip(FORCES, faire.remote(plan, DECORS[0], FORCES)):
        open(f"maquettes/photo/peints/salon_sur_plan_{int(f * 100)}.png", "wb").write(p); print("décor", f, len(p))
