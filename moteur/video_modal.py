"""Plan gag généré par IA : Wan 2.2 TI2V-5B (licence Apache 2.0), texte → vidéo, sur un GPU Modal.
Déployé automatiquement par le robot : `modal deploy moteur/video_modal.py`.
Appelé par moteur/principal.py ; si quoi que ce soit échoue, la vidéo sort simplement sans plan gag.
Coût indicatif : quelques minutes de GPU L40S par jour, couvertes par les crédits gratuits mensuels de Modal."""
import io, os, tempfile
import modal

app = modal.App("jt-video")
cache = modal.Volume.from_name("jt-cache", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.11")
         .apt_install("ffmpeg")
         .pip_install("torch==2.5.1", "diffusers>=0.35.1", "transformers>=4.49,<5", "accelerate", "ftfy",
                      "sentencepiece", "imageio", "imageio-ffmpeg", "numpy")
         .env({"HF_HOME": "/cache/hf", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}))
MODELE = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
NEGATIF = ("photorealistic, 3d render, realistic skin, text, subtitles, letters, watermark, logo, blurry, low quality, "
           "jpeg artifacts, deformed, extra limbs, extra fingers, bad hands, bad face, static, frozen, cluttered background")

@app.cls(gpu="L40S", image=image, volumes={"/cache": cache}, timeout=1800, scaledown_window=60)
class Video:
    @modal.enter()
    def charger(self):
        import torch
        from diffusers import WanPipeline, AutoencoderKLWan
        vae = AutoencoderKLWan.from_pretrained(MODELE, subfolder="vae", torch_dtype=torch.float32)
        self.pipe = WanPipeline.from_pretrained(MODELE, vae=vae, torch_dtype=torch.bfloat16).to("cuda")
        for f in ("enable_tiling", "enable_slicing"):                         # décodage par morceaux : évite le manque de mémoire
            try: getattr(self.pipe.vae, f)()
            except Exception: pass
        cache.commit()

    @modal.method()
    def plan(self, prompt: str, secondes: float = 4.0, graine: int = 0) -> bytes:
        """Renvoie une vidéo MP4 verticale (704 x 1280, 24 i/s) de 2 à 5 s."""
        import torch
        from diffusers.utils import export_to_video
        n = int(max(2.0, min(5.0, secondes)) * 24); n = (n - 1) // 4 * 4 + 1          # le modèle attend 4k+1 images
        g = torch.Generator("cuda").manual_seed(int(graine))
        torch.cuda.empty_cache()
        images = self.pipe(prompt=prompt + " Vibrant flat colors, clean cel animation, smooth comedic motion, vertical framing.",
                           negative_prompt=NEGATIF, height=1280, width=704, num_frames=n,
                           guidance_scale=5.0, num_inference_steps=40, generator=g).frames[0]
        chemin = os.path.join(tempfile.mkdtemp(), "plan.mp4")
        export_to_video(images, chemin, fps=24)
        return open(chemin, "rb").read()

def generer(prompt, secondes, sortie, graine=0):
    """Appel depuis le robot (GitHub Actions). Renvoie le chemin du clip, ou None en cas d'échec."""
    try:
        Video = modal.Cls.from_name("jt-video", "Video")
        octets = Video().plan.remote(prompt, float(secondes), int(graine))
        open(sortie, "wb").write(octets)
        return sortie if os.path.getsize(sortie) > 10000 else None
    except Exception as e:
        print(f"Plan gag IA indisponible ({e}) : la vidéo sortira sans.", flush=True)
        return None
