"""Voix naturelles Chatterbox Multilingual (MIT, français) sur un GPU Modal.
Déployé automatiquement par le robot : `modal deploy moteur/voix_modal.py`.
Appelé ensuite par moteur/voix.py. Les crédits gratuits mensuels de Modal couvrent normalement l'usage."""
import io, os, tempfile
import modal

app = modal.App("jt-voix")
cache = modal.Volume.from_name("jt-cache", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.11")
         .apt_install("ffmpeg")
         .pip_install("chatterbox-tts", "numpy", "soundfile")
         .env({"HF_HOME": "/cache/hf"}))

@app.cls(gpu="L4", image=image, volumes={"/cache": cache}, timeout=1800, scaledown_window=60)
class Voix:
    @modal.enter()
    def charger(self):
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        try:
            self.m = ChatterboxMultilingualTTS.from_pretrained(device="cuda", t3_model="v3")
        except TypeError:
            self.m = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
        cache.commit()

    @modal.method()
    def synthese(self, lignes: list, references: dict) -> list:
        """lignes : [{"texte", "role", "exag", "cfg"}] ; references : {role: octets wav}. Renvoie des wav (octets)."""
        import numpy as np, soundfile as sf
        dossier = tempfile.mkdtemp(); refs = {}
        for role, octets in references.items():
            refs[role] = os.path.join(dossier, f"{role}.wav")
            with open(refs[role], "wb") as f: f.write(octets)
        sorties = []
        for l in lignes:
            kw = dict(language_id="fr", exaggeration=float(l.get("exag", 0.5)), cfg_weight=float(l.get("cfg", 0.5)))
            if l.get("role") in refs: kw["audio_prompt_path"] = refs[l["role"]]
            wav = self.m.generate(l["texte"], **kw)
            a = wav.squeeze().detach().cpu().numpy().astype("float32")
            buf = io.BytesIO(); sf.write(buf, a, self.m.sr, format="WAV", subtype="PCM_16")
            sorties.append(buf.getvalue())
        return sorties
