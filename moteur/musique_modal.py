"""Musiques d'ambiance générées par IA, gratuites et utilisables commercialement (S2) : ACE-Step (Apache 2.0) sur un GPU Modal.
On fabrique UNE fois une petite bibliothèque de boucles instrumentales par humeur (sons/musique/<humeur>_<n>.wav) avec le
workflow « Musiques d'ambiance » ; le robot pioche ensuite dedans à chaque vidéo (gratuit, rapide). Sans bibliothèque,
il garde la nappe synthétisée de moteur/sons_modernes.py.
(MusicGen n'est pas utilisé : ses poids sont « non commercial ».)"""
import io
import modal

app = modal.App("jt-musique")
cache = modal.Volume.from_name("jt-cache", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.10").apt_install("ffmpeg", "git")
         .pip_install("torch==2.5.1", "torchaudio==2.5.1", "soundfile", "numpy")
         .pip_install("git+https://github.com/ace-step/ACE-Step.git")
         .env({"HF_HOME": "/cache/hf", "TORCH_HOME": "/cache/torch"}))

# styles par humeur du sketch (instrumental, discret, adapté à de l'humour sur TikTok)
STYLES = {
    "neutre": "lofi, chill, soft piano, light drums, warm, instrumental, background music, 90 bpm",
    "joie": "upbeat, funny, ukulele, whistling, claps, bouncy, comedy, instrumental, 115 bpm",
    "tension": "suspense, comedic tension, pizzicato strings, ticking, sneaky, cartoon, instrumental, 100 bpm",
    "triste": "sad violin, soft piano, melancholic, slow, dramatic comedy, instrumental, 70 bpm",
}


@app.cls(gpu="L4", image=image, volumes={"/cache": cache}, timeout=3600, scaledown_window=60)
class Musique:
    @modal.enter()
    def charger(self):
        from acestep.pipeline_ace_step import ACEStepPipeline
        self.p = ACEStepPipeline(checkpoint_dir="/cache/acestep", dtype="bfloat16", torch_compile=False)
        cache.commit()

    @modal.method()
    def boucle(self, humeur: str, duree: float = 45.0, graine: int = 1) -> bytes:
        """Une boucle instrumentale (wav 44,1 kHz) pour l'humeur donnée."""
        import os, tempfile
        dossier = tempfile.mkdtemp(); sortie = os.path.join(dossier, "m.wav")
        self.p(audio_duration=duree, prompt=STYLES.get(humeur, STYLES["neutre"]), lyrics="[instrumental]",
               infer_step=60, guidance_scale=15.0, manual_seeds=[graine], save_path=sortie)
        fichiers = [os.path.join(dossier, f) for f in os.listdir(dossier) if f.endswith(".wav")]
        return open(fichiers[0], "rb").read() if fichiers else b""


@app.local_entrypoint()
def bibliotheque(par_humeur: int = 3):
    """modal run moteur/musique_modal.py : remplit sons/musique (3 boucles par humeur)."""
    import os
    dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sons", "musique"); os.makedirs(dossier, exist_ok=True)
    m = Musique()
    for humeur in STYLES:
        for k in range(par_humeur):
            chemin = os.path.join(dossier, f"{humeur}_{k}.wav")
            if os.path.exists(chemin): continue
            o = m.boucle.remote(humeur, 45.0, 100 + k)
            if o: open(chemin, "wb").write(o); print("musique :", chemin)
