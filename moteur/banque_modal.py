"""Banque de voix sur GPU Modal : moteurs open source utilisables commercialement + contrôle qualité.
- Kyutai TTS 1.6B en/fr (poids CC BY 4.0) avec les voix françaises CML-TTS de la banque kyutai/tts-voices (CC BY 4.0) ;
- Zonos v0.1 (Apache 2.0), clonage des voix de casting (Multilingual LibriSpeech, CC BY 4.0) ;
- Whisper large-v3-turbo (MIT) : réécoute chaque réplique (texte bien prononcé ?) et donne l'instant exact de chaque mot ;
- UTMOS (SpeechMOS, MIT) : note le naturel de chaque prise (1 = robot, 5 = voix humaine) pour écarter les voix robotiques ;
- Kokoro 82M (Apache 2.0) : voix française de secours, avant Piper.
Déployé automatiquement par le robot : `modal deploy moteur/banque_modal.py`."""
import io, os, tempfile
import modal

app = modal.App("jt-banque")
cache = modal.Volume.from_name("jt-cache", create_if_missing=True)
ENV = {"HF_HOME": "/cache/hf", "TORCH_HOME": "/cache/torch"}

img_kyutai = (modal.Image.debian_slim(python_version="3.12").apt_install("ffmpeg")
              .pip_install("moshi==0.2.11", "torch", "sphn", "numpy", "soundfile", "huggingface_hub").env(ENV))
img_zonos = (modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg", "espeak-ng", "git")
             .pip_install("torch==2.5.1", "torchaudio==2.5.1", "numpy", "soundfile", "huggingface_hub")
             .pip_install("git+https://github.com/Zyphra/Zonos.git").env(ENV))
img_whisper = (modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg")
               .pip_install("torch==2.5.1", "torchaudio==2.5.1", "transformers>=4.45,<5", "accelerate", "numpy", "soundfile", "librosa").env(ENV))
img_kokoro = (modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg", "espeak-ng")
              .pip_install("kokoro>=0.9.4", "soundfile", "numpy").env(ENV))

def _wav(a, sr):
    import soundfile as sf
    buf = io.BytesIO(); sf.write(buf, a, sr, format="WAV", subtype="PCM_16"); return buf.getvalue()

# ------------------------------------------------------------------ Kyutai TTS
@app.cls(gpu="L4", image=img_kyutai, volumes={"/cache": cache}, timeout=1800, scaledown_window=60)
class Kyutai:
    @modal.enter()
    def charger(self):
        from moshi.models.loaders import CheckpointInfo
        from moshi.models.tts import DEFAULT_DSM_TTS_REPO, TTSModel
        self.m = TTSModel.from_checkpoint_info(CheckpointInfo.from_hf_repo(DEFAULT_DSM_TTS_REPO), n_q=32, temp=0.72, device="cuda")   # un peu plus de variation : intonation plus vivante
        cache.commit()

    @modal.method()
    def voix(self) -> list:
        """Voix françaises disponibles (CML-TTS, CC BY 4.0)."""
        from huggingface_hub import HfApi
        from moshi.models.tts import DEFAULT_DSM_TTS_VOICE_REPO
        f = HfApi().list_repo_files(DEFAULT_DSM_TTS_VOICE_REPO)
        noms = {x.split(".wav")[0] + ".wav" for x in f if x.startswith("cml-tts/fr/") and ".wav" in x}
        par_lecteur = {}                                                    # une seule version par lecteur (la version nettoyée si elle existe)
        for n in sorted(noms):
            cle = n.split("/")[-1].split("_")[0]
            if cle not in par_lecteur or "_enh" in n: par_lecteur[cle] = n
        return sorted(par_lecteur.values())

    @modal.method()
    def synthese(self, textes: list, voix: str) -> list:
        import numpy as np, torch
        try: chemin = voix if voix.endswith(".safetensors") else self.m.get_voice_path(voix)
        except Exception as e: raise RuntimeError(f"voix introuvable {voix} : {type(e).__name__} {str(e)[:200]}")
        attr = self.m.make_condition_attributes([chemin], cfg_coef=2.0); out = []
        for t in textes:
            try:
                res = self.m.generate([self.m.prepare_script([t], padding_between=1)], [attr])
                with self.m.mimi.streaming(1), torch.no_grad():
                    pcm = [np.clip(self.m.mimi.decode(fr[:, 1:, :]).cpu().numpy()[0, 0], -1, 1) for fr in res.frames[self.m.delay_steps:]]
                out.append(_wav(np.concatenate(pcm).astype("float32"), self.m.mimi.sample_rate))
            except Exception as e:
                print("kyutai:", e); out.append(b"")
        return out

# ------------------------------------------------------------------ Zonos
@app.cls(gpu="L4", image=img_zonos, volumes={"/cache": cache}, timeout=1800, scaledown_window=60)
class Zonos:
    @modal.enter()
    def charger(self):
        from zonos.model import Zonos as Z
        self.m = Z.from_pretrained("Zyphra/Zonos-v0.1-transformer", device="cuda"); cache.commit()

    @modal.method()
    def synthese(self, textes: list, reference: bytes, emotion: str = "neutre") -> list:
        import numpy as np, torch, torchaudio
        from zonos.conditioning import make_cond_dict
        p = os.path.join(tempfile.mkdtemp(), "ref.wav"); open(p, "wb").write(reference)
        wav, sr = torchaudio.load(p); spk = self.m.make_speaker_embedding(wav, sr)
        # émotions : bonheur, tristesse, dégoût, peur, surprise, colère, autre, neutre
        emo = {"neutre": [0.15, 0.05, 0.05, 0.05, 0.1, 0.05, 0.1, 0.45], "vif": [0.35, 0.05, 0.05, 0.05, 0.2, 0.05, 0.1, 0.15]}.get(emotion)
        out = []
        for t in textes:
            try:
                kw = dict(text=t, speaker=spk, language="fr-fr", speaking_rate=14.0)
                if emo: kw["emotion"] = emo
                cond = self.m.prepare_conditioning(make_cond_dict(**kw))
                codes = self.m.generate(cond, disable_torch_compile=True)          # sans compilation : évite plusieurs minutes d'attente
                a = self.m.autoencoder.decode(codes).cpu().numpy()[0, 0].astype("float32")
                out.append(_wav(a, self.m.autoencoder.sampling_rate))
            except Exception as e:
                print("zonos:", e); out.append(b"")
        return out

# ------------------------------------------------------------------ Whisper (contrôle qualité + minutage des mots)
@app.cls(gpu="L4", image=img_whisper, volumes={"/cache": cache}, timeout=1800, scaledown_window=60)
class Whisper:
    @modal.enter()
    def charger(self):
        import torch
        from transformers import pipeline
        self.p = pipeline("automatic-speech-recognition", model="openai/whisper-large-v3-turbo", torch_dtype=torch.float16, device="cuda")
        try:                                                                # juge du naturel d'une voix (UTMOS, MIT) : note de 1 (robot) à 5 (humain)
            self.mos = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True).to("cuda").eval()
        except Exception as e:
            print("UTMOS indisponible :", e); self.mos = None
        cache.commit()

    def _naturel(self, a):
        """Note de naturel UTMOS (1 = robot, 5 = voix humaine) d'un signal 16 kHz, ou None."""
        if self.mos is None or len(a) < 8000: return None
        import torch
        with torch.no_grad():
            return round(float(self.mos(torch.from_numpy(a[None, :]).float().cuda(), 16000).item()), 2)

    @modal.method()
    def ecouter(self, wavs: list) -> list:
        """Pour chaque wav : texte entendu et liste de mots [(mot, début, fin)] en secondes."""
        import io as _io, numpy as np, soundfile as sf, librosa
        out = []
        for o in wavs:
            try:
                a, sr = sf.read(_io.BytesIO(o), dtype="float32")
                if a.ndim > 1: a = a.mean(1)
                if sr != 16000: a = librosa.resample(a, orig_sr=sr, target_sr=16000)
                r = self.p({"raw": a, "sampling_rate": 16000}, return_timestamps="word", generate_kwargs={"language": "french", "task": "transcribe"})
                mots = [(c["text"].strip(), float(c["timestamp"][0] or 0), float(c["timestamp"][1] or c["timestamp"][0] or 0)) for c in r.get("chunks", [])]
                try: mos = self._naturel(a)
                except Exception as e: print("utmos:", e); mos = None
                out.append({"texte": r.get("text", "").strip(), "mots": mots, "mos": mos})
            except Exception as e:
                print("whisper:", e); out.append({"texte": "", "mots": [], "erreur": str(e)[:200]})
        return out


# ------------------------------------------------------------------ Kokoro (secours naturel avant Piper)
@app.cls(image=img_kokoro, volumes={"/cache": cache}, timeout=900, scaledown_window=60, cpu=4)
class Kokoro:
    @modal.enter()
    def charger(self):
        from kokoro import KPipeline
        self.p = KPipeline(lang_code="f"); cache.commit()                 # français (phonèmes espeak-ng)

    @modal.method()
    def synthese(self, textes: list, voix: str = "ff_siwis", vitesse: float = 1.05) -> list:
        import numpy as np
        out = []
        for t in textes:
            try:
                morceaux = [np.asarray(a, dtype="float32") for _, _, a in self.p(t, voice=voix, speed=vitesse)]
                out.append(_wav(np.concatenate(morceaux), 24000) if morceaux else b"")
            except Exception as e:
                print("kokoro:", e); out.append(b"")
        return out
