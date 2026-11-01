"""Notre propre IA de secours sur Modal (choix de l'auteur, 1er novembre 2026, idée 15) : un modèle LIBRE qui lit le texte ET les
images, Qwen2.5-VL 7B (Alibaba, licence Apache 2.0, usage commercial permis), servi par vLLM sur un GPU L4 (ou A10G) de Modal.
Il ne sert qu'en TOUT DERNIER recours, quand Claude, Mistral, Groq, Gemini et OpenRouter sont tous à court : la vidéo garde sa
mise en scène au lieu de tomber en « mode simple ». Coût : la machine ne tourne que pendant l'appel (arrêt 2 min après), soit
quelques centimes de crédit Modal par vidéo qui en a besoin. Poids du modèle gardés dans un volume (pas retéléchargés).
Déploiement : `modal deploy moteur/ia_modal.py` (workflow « IA de secours sur Modal » et chaque fabrication). IA_MODAL=0 pour couper.

Côté robot : reseau.claude() l'appelle comme les autres IA (fournisseur « modal ») ; il répond en texte, le JSON est relu par
ecrire._appel (pas d'outils natifs)."""
import json, os

MODELE = "Qwen/Qwen2.5-VL-7B-Instruct"
APP = "jt-ia"

try:
    import modal
    app = modal.App(APP)
    poids = modal.Volume.from_name("jt-ia-poids", create_if_missing=True)
    image = (modal.Image.debian_slim(python_version="3.12")
             .pip_install("vllm==0.9.2", "transformers==4.52.4", "huggingface_hub<1.0", "qwen-vl-utils==0.0.11", "pillow")   # versions qui vont ensemble
             .env({"HF_HOME": "/poids/hf", "VLLM_USE_V1": "1"}))

    @app.cls(gpu=["L4", "A10G"], image=image, volumes={"/poids": poids}, timeout=900, scaledown_window=120, max_containers=1)
    class IA:
        @modal.enter()
        def charger(self):
            from vllm import LLM
            self.llm = LLM(model=MODELE, max_model_len=16384, gpu_memory_utilization=0.92, limit_mm_per_prompt={"image": 6},
                           download_dir="/poids/hf")
            poids.commit()

        @modal.method()
        def repondre(self, messages: list, max_tokens: int = 2000) -> str:
            from vllm import SamplingParams
            out = self.llm.chat(messages, SamplingParams(temperature=0.5, max_tokens=max_tokens))
            return out[0].outputs[0].text
except ImportError:                                                        # (machine sans modal : seul le côté robot sert)
    modal = None


def appeler(kw):
    """Appel façon reseau._appel_openai : kw = demande « façon Claude ». Renvoie une réponse « façon Claude » (texte seul)."""
    from types import SimpleNamespace as NS
    import reseau
    if os.environ.get("IA_MODAL", "1") == "0" or not os.environ.get("MODAL_TOKEN_ID"): raise RuntimeError("modal 403 : IA de secours coupée")
    msgs, _ = reseau._messages_openai(kw, "modal")
    outils = [t for t in (kw.get("tools") or []) if isinstance(t, dict) and "input_schema" in t]
    if outils:                                                             # pas d'outils natifs : on demande le JSON dans le texte
        sch = json.dumps(outils[0]["input_schema"], ensure_ascii=False)[:6000]
        msgs.append({"role": "user", "content": f"Réponds UNIQUEMENT par un objet JSON valide qui respecte ce schéma (sans texte autour) : {sch}"})
    import modal as m_
    ia = m_.Cls.from_name(APP, "IA")()
    appel = ia.repondre.spawn(msgs, int(min(kw.get("max_tokens") or 2000, 4000)))
    try: txt = appel.get(timeout=float(os.environ.get("IA_MODAL_ATTENTE") or 600))   # jamais de fabrication bloquée : 10 min au plus
    except Exception:
        try: appel.cancel()
        except Exception: pass
        raise
    reseau.UTILISES["modal"] = reseau.UTILISES.get("modal", 0) + 1
    print("  IA de secours sur Modal (Qwen2.5-VL) utilisée", flush=True)
    return NS(content=[NS(type="text", text=txt)], stop_reason="end_turn", model=f"modal:{MODELE}", gratuit=True,
              usage=NS(input_tokens=0, output_tokens=0, cache_read_input_tokens=0, cache_creation_input_tokens=0, server_tool_use=None))


if __name__ == "__main__":                                                 # essai : python moteur/ia_modal.py
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("IA_MODAL", "1")
    r = appeler({"messages": [{"role": "user", "content": "Réponds en une phrase : quelle est la capitale de la France ?"}], "max_tokens": 60})
    print("Réponse :", r.content[0].text)
