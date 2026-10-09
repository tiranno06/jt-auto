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
        def note(a, sr, texte):
            """Contrôle qualité : durée plausible pour le texte et pas de long blanc au milieu (sinon la prise est refaite)."""
            dur = len(a) / sr; attendu = max(0.6, len(texte) * 0.068); ratio = dur / attendu
            h = int(0.02 * sr); e = np.array([np.sqrt(np.mean(a[k:k + h] ** 2)) for k in range(0, max(1, len(a) - h), h)])
            v = e > 0.06 * (np.percentile(e, 95) + 1e-9); idx = np.where(v)[0]; blanc = 0.0
            if len(idx) > 1:
                run = 0
                for x in v[idx[0]:idx[-1]]:
                    run = run + 1 if not x else 0; blanc = max(blanc, run * 0.02)
            return abs(np.log(max(ratio, 1e-3))) + max(0.0, blanc - 0.45) * 2, round(ratio, 2), round(blanc, 2)
        sorties = []
        for l in lignes:
            kw = dict(language_id="fr", exaggeration=float(l.get("exag", 0.5)), cfg_weight=float(l.get("cfg", 0.5)))
            if l.get("role") in refs: kw["audio_prompt_path"] = refs[l["role"]]
            meilleur = None
            for essai, temp in enumerate((0.6, 0.5, 0.7)):
                k2 = dict(kw, temperature=temp)
                try:
                    try: wav = self.m.generate(l["texte"], **k2)
                    except TypeError: wav = self.m.generate(l["texte"], **kw)
                except Exception:
                    continue
                a = wav.squeeze().detach().cpu().numpy().astype("float32")
                sc, ratio, blanc = note(a, self.m.sr, l["texte"])
                if meilleur is None or sc < meilleur[0]: meilleur = (sc, a, dict(essais=essai + 1, ratio=ratio, blanc=blanc))
                if sc < 0.35: break                                          # prise correcte : on garde
            if meilleur is None: sorties.append({"wav": b"", "info": {"echec": True}}); continue
            buf = io.BytesIO(); sf.write(buf, meilleur[1], self.m.sr, format="WAV", subtype="PCM_16")
            sorties.append({"wav": buf.getvalue(), "info": meilleur[2]})
        return sorties
