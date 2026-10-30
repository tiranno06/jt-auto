"""Écoute gratuite du son TikTok (idées 23, 24, 26, 27, 28, 31 de l'auteur) : chaque outil a son repli, rien ne bloque la vidéo.
- Demucs (MIT, sur la machine) : voix seules, sans la musique, quand l'isolation ElevenLabs n'a plus de crédit (DEMUCS=0 pour couper) ;
- Groq (clé gratuite GROQ_API_KEY) : transcription Whisper large-v3-turbo en quelques secondes, avec l'instant de chaque mot ;
- calage des mots (wav2vec2 français Apache 2.0 + alignement forcé de torchaudio, comme WhisperX) : chaque mot recalé au centième de seconde sur la voix,
  pour les lèvres et les sous-titres (ALIGNEMENT=0 pour couper) ;
- émotion de la voix (SpeechBrain wav2vec2 IEMOCAP, Apache 2.0) : colère, joie, tristesse entendues -> visage (EMOTION_VOIX=0) ;
- bruits de l'original (CLAP LAION, Apache 2.0) : rires, cris, sirène, aboiement, sonnerie, porte, klaxon… (CLAP=0 pour couper).
Les modèles sont gardés dans le cache du workflow (~/.cache/huggingface, ~/.cache/torch)."""
import json, math, os, re, subprocess, tempfile, time, unicodedata, urllib.request, uuid
import numpy as np

SR = 22050


def journal(t):
    print(t, flush=True)


def _wav(sig, sr, chemin):
    import scipy.io.wavfile as W
    W.write(chemin, sr, (np.clip(np.asarray(sig, np.float32), -1, 1) * 32767).astype(np.int16))
    return chemin


def _lire(chemin, sr=SR):
    """Fichier son -> mono float32 à sr Hz (ffmpeg)."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", chemin, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def _r16(sig, sr=SR):
    from scipy.signal import resample_poly
    g = math.gcd(16000, sr)
    return resample_poly(np.asarray(sig, np.float32), 16000 // g, sr // g).astype(np.float32)


# ------------------------------------------------------------------ 23 : Demucs (voix sans la musique)
def demucs(tmp, delai=900):
    """Voix seules par Demucs (htdemucs, deux pistes : voix / reste) à partir de tmp/mono.wav. Renvoie (signal, chemin) ou (None, None)."""
    if os.environ.get("DEMUCS", "1") == "0": return None, None
    src = os.path.join(tmp, "mono.wav"); out = os.path.join(tmp, "demucs")
    try:
        t0 = time.time()
        subprocess.run(["python", "-m", "demucs.separate", "--two-stems", "vocals", "-n", "htdemucs", "-d", "cpu", "-j", "2", "-o", out, src],
                       check=True, capture_output=True, timeout=delai)
        f = os.path.join(out, "htdemucs", "mono", "vocals.wav")
        sig = _lire(f); chemin = os.path.join(tmp, "voix.wav"); _wav(sig, SR, chemin)
        journal(f"  voix isolées gratuitement (Demucs, {time.time() - t0:.0f} s)"); return sig, chemin
    except Exception as e:
        msg = getattr(e, "stderr", b"") or b""
        journal(f"  Demucs indisponible ({(msg.decode(errors='ignore')[-150:] if msg else str(e)[:150]).strip()})"); return None, None


# ------------------------------------------------------------------ 31 : Groq (Whisper ultra-rapide, gratuit)
def groq(chemin, langue="fr"):
    """Mots [{"w", "s", "e", "voix"}] par Whisper large-v3-turbo chez Groq (clé gratuite GROQ_API_KEY) ; [] si impossible."""
    cle = os.environ.get("GROQ_API_KEY")
    if not cle: return []
    try:
        import reseau
        tmp = tempfile.mkdtemp(); mp3 = os.path.join(tmp, "son.mp3")            # 25 Mo au plus chez Groq : MP3 léger
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", chemin, "-ac", "1", "-ar", "16000", "-b:a", "64k", mp3], check=True)
        bord = uuid.uuid4().hex; corps = b""
        for k, v in (("model", "whisper-large-v3-turbo"), ("language", langue), ("response_format", "verbose_json"),
                     ("timestamp_granularities[]", "word"), ("timestamp_granularities[]", "segment"), ("temperature", "0")):
            corps += f"--{bord}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        corps += (f"--{bord}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"son.mp3\"\r\nContent-Type: audio/mpeg\r\n\r\n").encode() \
                 + open(mp3, "rb").read() + f"\r\n--{bord}--\r\n".encode()
        req = urllib.request.Request("https://api.groq.com/openai/v1/audio/transcriptions", data=corps, method="POST",
                                     headers={"Authorization": f"Bearer {cle}", "Content-Type": f"multipart/form-data; boundary={bord}"})
        r = json.loads(reseau.ouvrir(req, timeout=180, essais=2).read())
        mots = [{"w": str(x.get("word", "")).strip(), "s": float(x["start"]), "e": float(x["end"]), "voix": "speaker_0"}
                for x in r.get("words") or [] if str(x.get("word", "")).strip()]
        mots = ponctuer(mots, r.get("segments") or [])
        if mots: journal(f"  transcription Groq (Whisper, gratuit) : {len(mots)} mots")
        return mots
    except Exception as e:
        journal(f"  transcription Groq impossible ({str(e)[:150]})"); return []


def ponctuer(mots, segs):
    """Les mots de Groq n'ont pas la ponctuation : on la reprend du texte de chaque segment (même ordre des mots)."""
    i = 0
    for s in segs:
        for tok in str(s.get("text", "")).split():
            nu = re.sub(r"[^\w'’-]", "", tok)
            if not nu: continue
            for j in range(i, min(len(mots), i + 3)):                      # le mot correspondant, tout près
                if re.sub(r"[^\w'’-]", "", mots[j]["w"]).lower() == nu.lower():
                    mots[j]["w"] = tok; i = j + 1; break
    return mots


# ------------------------------------------------------------------ 24 : calage des mots (alignement forcé, façon WhisperX)
MODELE_FA = "jonatasgrosman/wav2vec2-large-xlsr-53-french"                 # celui de WhisperX pour le français (Apache 2.0)
_FA = {}
def _lettres(mot, voc):
    t = mot.lower().replace("’", "'").replace("œ", "oe").replace("æ", "ae")
    j = [voc[c] for c in t if c in voc and c not in ("|", "'")]
    if not j:                                                              # lettre inconnue : version sans accent
        t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
        j = [voc[c] for c in t if c in voc and c not in ("|", "'")]
    return j


def aligner(mots, sig, sr=SR, marge=0.25):
    """Recale chaque mot sur la voix (alignement forcé wav2vec2, comme WhisperX). On aligne phrase par phrase (morceaux séparés par
    un silence) ; le texte et l'ordre des mots ne changent jamais, un mot sans lettre (chiffres) garde ses instants, aucun mot n'est
    déplacé de plus d'une seconde. Renvoie les mots (instants corrigés) ; en cas de souci, les mots tels quels."""
    if os.environ.get("ALIGNEMENT", "1") == "0" or not mots: return mots
    try:
        import torch, torchaudio
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        if "m" not in _FA:
            _FA["p"] = Wav2Vec2Processor.from_pretrained(MODELE_FA); _FA["m"] = Wav2Vec2ForCTC.from_pretrained(MODELE_FA).eval()
            _FA["v"] = {k.lower(): v for k, v in _FA["p"].tokenizer.get_vocab().items() if len(k) == 1}
        mod, voc, blanc = _FA["m"], _FA["v"], _FA["p"].tokenizer.pad_token_id or 0
        a16 = _r16(sig, sr); t0 = time.time(); bouges = []
        morceaux, cur = [], [0]
        for k in range(1, len(mots)):
            if mots[k]["s"] - mots[k - 1]["e"] > 0.5 or len(cur) >= 25: morceaux.append(cur); cur = []
            cur.append(k)
        morceaux.append(cur)
        for idx in morceaux:
            ok = [k for k in idx if _lettres(mots[k]["w"], voc)]
            if not ok: continue
            deb = max(0.0, mots[idx[0]]["s"] - marge); fin = min(len(a16) / 16000, mots[idx[-1]]["e"] + marge)
            bout = a16[int(deb * 16000):int(fin * 16000)]
            if len(bout) < 1600: continue
            x = _FA["p"](bout, sampling_rate=16000, return_tensors="pt").input_values
            with torch.inference_mode(): em = torch.log_softmax(mod(x).logits, -1)
            jetons = [_lettres(mots[k]["w"], voc) for k in ok]
            if sum(map(len, jetons)) >= em.shape[1]: continue
            ali, sc = torchaudio.functional.forced_align(em, torch.tensor([sum(jetons, [])], dtype=torch.int32), blank=blanc)
            spans = torchaudio.functional.merge_tokens(ali[0], sc[0].exp(), blank=blanc)
            pas = len(bout) / em.shape[1] / 16000; p = 0
            for k, j in zip(ok, jetons):
                s_ = spans[p:p + len(j)]; p += len(j)
                if not s_: continue
                ns, ne = deb + s_[0].start * pas, deb + s_[-1].end * pas
                if abs(ns - mots[k]["s"]) < 1.0 and ne > ns:
                    bouges.append(abs(ns - mots[k]["s"])); mots[k]["s"], mots[k]["e"] = round(ns, 3), round(ne, 3)
        for k in range(1, len(mots)):                                      # jamais deux mots qui se chevauchent
            if mots[k]["s"] < mots[k - 1]["e"]: mots[k - 1]["e"] = max(mots[k - 1]["s"] + 0.02, mots[k]["s"])
        if bouges: journal(f"  mots recalés sur la voix ({len(bouges)} mots, écart moyen {1000 * sum(bouges) / len(bouges):.0f} ms, {time.time() - t0:.0f} s)")
    except Exception as e:
        journal(f"  calage des mots impossible ({str(e)[:150]}) : instants de la transcription gardés")
    return mots


# ------------------------------------------------------------------ 26 : émotion entendue dans la voix
EMO_VOIX = {"ang": "angry", "hap": "happy", "sad": "sigh"}                 # étiquettes lues par cartoon.emotion
_EMO = {}
def emotions(sig, segs, sr=SR, seuil=0.75):
    """{n° de réplique: étiquette} pour les répliques où la voix exprime nettement une émotion (colère, joie, tristesse)."""
    if os.environ.get("EMOTION_VOIX", "1") == "0" or not segs: return {}
    try:
        import torch
        if "c" not in _EMO:
            from speechbrain.inference.interfaces import foreign_class
            _EMO["c"] = foreign_class(source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP", pymodule_file="custom_interface.py",
                                      classname="CustomEncoderWav2vec2Classifier", run_opts={"device": "cpu"},
                                      savedir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outils", "emotion_voix"))
        c = _EMO["c"]; a16 = _r16(sig, sr); out = {}; t0 = time.time()
        for k, s in enumerate(segs):
            bout = a16[int(s["deb"] * 16000):int(s["fin"] * 16000)]
            if len(bout) < 8000: continue                                  # moins d'une demi-seconde : on ne devine pas
            with torch.inference_mode(): prob, score, _, lab = c.classify_batch(torch.from_numpy(bout[:16000 * 12]).unsqueeze(0))
            nom = str(lab[0]); p = float(torch.softmax(prob[0], -1).max()) if prob.dim() > 1 else float(score[0].exp())
            if nom in EMO_VOIX and p >= seuil: out[k] = EMO_VOIX[nom]
        journal(f"  émotions entendues dans la voix : {len(out)} réplique(s) ({time.time() - t0:.0f} s)" + (f" {sorted(set(out.values()))}" if out else ""))
        return out
    except Exception as e:
        journal(f"  émotion de la voix indisponible ({str(e)[:150]})"); return {}


# ------------------------------------------------------------------ 27 + 28 : rires, cris et bruits de l'original (CLAP)
BRUITS = {"laughter": "a person laughing", "scream": "a person screaming", "crying": "a person crying", "applause": "applause",
          "siren": "a siren", "dog": "a dog barking", "cat": "a cat meowing", "phone": "a phone ringing", "door": "a door knock or slam",
          "horn": "a car horn", "baby": "a baby crying", "music": "music playing", "rain": "rain", "thunder": "thunder",
          "glass": "glass breaking", "gunshot": "a gunshot", "kiss": "a kiss", "speech": "a person talking"}
_CLAP = {}
HUMAINS = ("laughter", "scream", "crying")                                 # sons de la voix : plus discrets pour CLAP (seuil plus bas)
def bruits(sig, sr=SR, fen=2.0, pas=1.0):
    """[(début, fin, nom)] des bruits reconnus dans le son d'origine (rires, cris, sirène…), au même format que les événements Scribe."""
    if os.environ.get("CLAP", "1") == "0" or sig is None or len(sig) < sr: return []
    try:
        import torch
        from transformers import ClapModel, ClapProcessor
        if "m" not in _CLAP:
            _CLAP["p"] = ClapProcessor.from_pretrained("laion/clap-htsat-unfused"); _CLAP["m"] = ClapModel.from_pretrained("laion/clap-htsat-unfused").eval()
            with torch.inference_mode():
                t = _CLAP["p"](text=[f"the sound of {v}" for v in BRUITS.values()], return_tensors="pt", padding=True)
                e = _CLAP["m"].get_text_features(**t); _CLAP["t"] = torch.nn.functional.normalize(getattr(e, "pooler_output", e), dim=-1)
        from scipy.signal import resample_poly
        a = resample_poly(np.asarray(sig, np.float32), 480, int(sr / 100)).astype(np.float32) if sr != 48000 else np.asarray(sig, np.float32)
        t0 = time.time(); debuts = np.arange(0, max(0.0, len(a) / 48000 - fen) + 1e-6, pas); out = []
        noms = list(BRUITS)
        for i in range(0, len(debuts), 16):                                 # par lots de 16 fenêtres de 2 s
            lot = [a[int(d * 48000):int((d + fen) * 48000)] for d in debuts[i:i + 16]]
            with torch.inference_mode():
                x = _CLAP["p"](audio=lot, sampling_rate=48000, return_tensors="pt")
                e = _CLAP["m"].get_audio_features(**x); e = torch.nn.functional.normalize(getattr(e, "pooler_output", e), dim=-1)
                p = (e @ _CLAP["t"].T).numpy()                             # ressemblance son / description (cosinus)
            for d, pr in zip(debuts[i:i + 16], p):                         # seuils réglés sur ESC-50 (vrais bruits) et nos dialogues
                k = int(np.argmax(pr)); nom = noms[k]                       # avec musique : la musique seule ne dépasse pas 0,17
                fond = max(pr[noms.index("speech")], pr[noms.index("music")])
                if nom in ("speech", "music") or pr[k] < (0.13 if nom in HUMAINS else 0.25) or pr[k] - fond < 0.04: continue
                if out and out[-1][2] == nom and d - out[-1][1] <= pas + 0.01: out[-1] = (out[-1][0], round(float(d + fen), 2), nom)
                else: out.append((round(float(d), 2), round(float(d + fen), 2), nom))
        journal(f"  bruits de l'original (CLAP, {time.time() - t0:.0f} s) : " + (", ".join(sorted({n for _, _, n in out})) or "aucun"))
        return out
    except Exception as e:
        journal(f"  reconnaissance des bruits indisponible ({str(e)[:150]})"); return []


def jeu_entendu(reps, segs, emo, evts):
    """Indications de jeu tirées de l'écoute, posées sur les répliques SANS indication de l'IA : émotion de la voix, rire ou cri
    entendu pendant la réplique. Le texte ne change jamais (seule l'étiquette entre crochets est ajoutée)."""
    n = 0
    for k, (r, s) in enumerate(zip(reps, segs)):
        if r.get("d"): continue
        tag = None
        for d_, f_, nom in evts:
            if d_ < s["fin"] and f_ > s["deb"] and nom in ("laughter", "scream", "crying"): tag = {"laughter": "laughing", "scream": "shouting", "crying": "crying"}[nom]
        tag = tag or emo.get(k)
        if tag: r["d"] = f"[{tag}] {r['t']}"; n += 1
    if n: journal(f"  jeu d'acteur entendu dans le son : {n} réplique(s) (émotion de la voix, rires, cris)")
    return reps


# ------------------------------------------------------------------ 25 et 30 : NeMo et Florence-2 sur Modal (moteur/ecoute_modal.py)
def _modal(cls):
    if not os.environ.get("MODAL_TOKEN_ID") or os.environ.get("ECOUTE_MODAL", "1") == "0": return None
    import modal
    return modal.Cls.from_name("jt-ecoute", cls)()


def nemo(mots, sig, sr=SR, voix=0):
    """Qui parle quand, par NeMo (Modal) : renvoie les mots avec leur voix, ou None si NeMo n'a pas tranché (une seule voix, erreur)."""
    try:
        c = _modal("Nemo")
        if c is None: return None
        import io, scipy.io.wavfile as W
        buf = io.BytesIO(); W.write(buf, 16000, (np.clip(_r16(sig, sr), -1, 1) * 32767).astype(np.int16))
        t0 = time.time(); tours = [tuple(x) for x in c.diariser.remote(buf.getvalue(), voix)]
        n = len({p for _, _, p in tours})
        journal(f"  voix séparées par NeMo : {n} voix, {len(tours)} tours de parole ({time.time() - t0:.0f} s)")
        if n < 2: return None
        import locuteurs
        return locuteurs.mots_par_tours([dict(m) for m in mots], tours)
    except Exception as e:
        journal(f"  NeMo indisponible ({str(e)[:150]})"); return None


def decrire(images):
    """Descriptions (anglais) des images clés par Florence-2 (Modal) ; [] si impossible."""
    try:
        c = _modal("Florence")
        if c is None or not images: return []
        t0 = time.time(); d = [str(x) for x in c.decrire.remote(list(images)[:8])]
        journal(f"  images de l'original décrites par Florence-2 ({len(d)} images, {time.time() - t0:.0f} s)"); return d
    except Exception as e:
        journal(f"  Florence-2 indisponible ({str(e)[:150]})"); return []
