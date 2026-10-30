"""Écoute et regard sur GPU Modal (idées 25 et 30 de l'auteur), outils utilisables commercialement :
- NeMo (NVIDIA, Apache 2.0 ; modèles TitaNet-large et MarbleNet en CC BY 4.0) : « qui parle quand », meilleur que pyannote sur les
  voix proches ; utilisé quand la transcription n'a trouvé qu'une seule voix (avant pyannote et l'empreinte ECAPA) ;
- Florence-2 large (Microsoft, MIT) : décrit en détail les images clés de la vidéo d'origine (lieu, personnes, habits, objets)
  quand aucune IA ne peut regarder les images (quota Gemini épuisé, pas de crédit Claude).
Déployé automatiquement par le robot : `modal deploy moteur/ecoute_modal.py`."""
import io, json, os, tempfile
import modal

app = modal.App("jt-ecoute")
cache = modal.Volume.from_name("jt-cache", create_if_missing=True)
ENV = {"HF_HOME": "/cache/hf", "TORCH_HOME": "/cache/torch", "NEMO_CACHE_DIR": "/cache/nemo"}
CONF = "https://raw.githubusercontent.com/NVIDIA/NeMo/v2.1.0/examples/speaker_tasks/diarization/conf/inference/diar_infer_telephonic.yaml"

img_nemo = (modal.Image.debian_slim(python_version="3.10").apt_install("ffmpeg", "libsndfile1", "build-essential", "wget")
            .pip_install("torch==2.5.1", "torchaudio==2.5.1", "Cython", "packaging")
            .pip_install("nemo_toolkit[asr]==2.1.0").run_commands(f"wget -q -O /opt/diar.yaml {CONF}").env(ENV))
img_florence = (modal.Image.debian_slim(python_version="3.11")
                .pip_install("torch==2.5.1", "transformers==4.46.3", "accelerate", "einops", "timm", "pillow", "numpy<2").env(ENV))


@app.cls(gpu="T4", image=img_nemo, volumes={"/cache": cache}, timeout=900, scaledown_window=60)
class Nemo:
    @modal.method()
    def diariser(self, wav: bytes, voix: int = 0) -> list:
        """Tours de parole [(début, fin, voix)] d'un son WAV (voix = nombre de personnes si on le sait, 0 = à deviner)."""
        from omegaconf import OmegaConf
        from nemo.collections.asr.models import ClusteringDiarizer
        d = tempfile.mkdtemp(); f = os.path.join(d, "son.wav"); open(f, "wb").write(wav)
        man = os.path.join(d, "manifest.json")
        json.dump({"audio_filepath": f, "offset": 0, "duration": None, "label": "infer", "text": "-",
                   "num_speakers": voix or None, "rttm_filepath": None, "uem_filepath": None}, open(man, "w"))
        cfg = OmegaConf.load("/opt/diar.yaml")
        cfg.diarizer.manifest_filepath = man; cfg.diarizer.out_dir = d; cfg.num_workers = 0
        cfg.diarizer.oracle_vad = False; cfg.diarizer.clustering.parameters.oracle_num_speakers = bool(voix)
        cfg.diarizer.clustering.parameters.max_num_speakers = 4
        cfg.diarizer.speaker_embeddings.model_path = "titanet_large"; cfg.diarizer.vad.model_path = "vad_multilingual_marblenet"
        ClusteringDiarizer(cfg=cfg).diarize(); cache.commit()
        tours = []
        for l in open(os.path.join(d, "pred_rttms", "son.rttm")):
            x = l.split()
            if len(x) >= 8 and x[0] == "SPEAKER": tours.append((round(float(x[3]), 3), round(float(x[3]) + float(x[4]), 3), x[7]))
        return sorted(tours)


@app.cls(gpu="T4", image=img_florence, volumes={"/cache": cache}, timeout=900, scaledown_window=60)
class Florence:
    @modal.enter()
    def charger(self):
        import torch
        from unittest.mock import patch
        from transformers import AutoModelForCausalLM, AutoProcessor
        from transformers.dynamic_module_utils import get_imports
        def sans_flash(f): return [i for i in get_imports(f) if i != "flash_attn"]   # flash_attn inutile ici (et absent)
        with patch("transformers.dynamic_module_utils.get_imports", sans_flash):
            self.m = AutoModelForCausalLM.from_pretrained("microsoft/Florence-2-large", trust_remote_code=True, torch_dtype=torch.float16).to("cuda").eval()
        self.p = AutoProcessor.from_pretrained("microsoft/Florence-2-large", trust_remote_code=True)
        cache.commit()

    @modal.method()
    def decrire(self, images: list) -> list:
        """Description détaillée (en anglais) de chaque image JPEG."""
        import torch
        from PIL import Image
        out, tache = [], "<MORE_DETAILED_CAPTION>"
        for j in images:
            im = Image.open(io.BytesIO(j)).convert("RGB")
            x = self.p(text=tache, images=im, return_tensors="pt").to("cuda", torch.float16)
            with torch.inference_mode():
                ids = self.m.generate(input_ids=x["input_ids"], pixel_values=x["pixel_values"], max_new_tokens=200, num_beams=3, do_sample=False)
            t = self.p.batch_decode(ids, skip_special_tokens=False)[0]
            out.append(str(self.p.post_process_generation(t, task=tache, image_size=im.size).get(tache, "")).strip())
        return out
