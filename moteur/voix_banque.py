"""Banque de voix : le robot pioche automatiquement la meilleure voix disponible pour chaque personnage,
parmi toutes les sources gratuites et utilisables commercialement, et vérifie chaque réplique.

Sources (activées automatiquement si disponibles) :
- ElevenLabs, modèle Eleven v4 (secret ELEVENLABS_API_KEY ; abonnement payant, licence commerciale), voix françaises de
  leur bibliothèque, avec indications de jeu entre crochets ([laughs], [sighs]…) ;
- Google Cloud TTS, voix « Chirp 3 HD » (secret GOOGLE_TTS_API_KEY ; 1 million de caractères gratuits par mois) ;
- Azure Speech, voix neuronales (secrets AZURE_SPEECH_KEY + AZURE_SPEECH_REGION ; 500 000 caractères gratuits par mois) ;
- Kyutai TTS (CC BY 4.0) avec les voix françaises CML-TTS (CC BY 4.0), sur Modal ;
- Zonos (Apache 2.0) et Chatterbox (MIT), qui clonent les voix du casting (Multilingual LibriSpeech, CC BY 4.0), sur Modal ;
- Piper / SIWIS (CC BY 4.0) en tout dernier recours.

Casting : une fois par semaine (ou dès qu'une nouvelle source apparaît), chaque voix lit une réplique test ; Whisper
la réécoute ; le robot garde, pour chaque personnage, la meilleure voix du bon genre et deux remplaçantes (voix/banque.json).
Chaque jour : chaque réplique est générée, nettoyée (silences), réécoutée par Whisper. Mot avalé, charabia ou blanc :
la prise est refaite ; si la voix échoue encore, tout le rôle passe sur la voix remplaçante. Whisper fournit aussi
l'instant de chaque mot pour caler les sous-titres."""
import base64, datetime, difflib, io, json, os, re, subprocess, tempfile, unicodedata, urllib.error, urllib.request, wave
import numpy as np
import voix_piper

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FICHE = os.path.join(RACINE, "voix", "banque.json")
SR = 22050
ROLES = {"presentateur": "h", "invite": "h", "envoyee": "f"}
TEST = {"presentateur": "Bonsoir. Le gouvernement a présenté son budget ce matin. Les députés, eux, cherchent encore les économies.",
        "invite": "Ce n'est pas un échec. C'est une réussite qui ne s'est pas encore produite. Nous restons très confiants.",
        "envoyee": "Je suis en direct de l'Assemblée. Ici, tout le monde attend. Personne ne sait vraiment quoi, mais tout le monde attend."}
PRIORITE = {"elevenlabs": 4.0, "google": 3.0, "azure": 2.8, "kyutai": 2.2, "zonos": 1.6, "chatterbox": 1.5}
GOOGLE = {"h": ["Charon", "Orus", "Fenrir", "Iapetus", "Algieba"], "f": ["Aoede", "Kore", "Leda", "Despina", "Erinome"]}
AZURE = {"h": ["fr-FR-HenriNeural", "fr-FR-RemyMultilingualNeural", "fr-FR-AlainNeural", "fr-FR-JeromeNeural"],
         "f": ["fr-FR-DeniseNeural", "fr-FR-VivienneMultilingualNeural", "fr-FR-BrigitteNeural", "fr-FR-CelesteNeural"]}
# débit par rôle : les voix de livres audio lisent trop lentement pour un sketch (accéléré sans changer la hauteur)
ENERGIE = {"presentateur": 1.12, "envoyee": 1.16, "invite": 1.14}

CREDITS = {"elevenlabs": "ElevenLabs (Eleven v4)", "google": "Google Cloud Text-to-Speech", "azure": "Microsoft Azure Speech",
           "kyutai": "Kyutai TTS (CC BY 4.0), voix CML-TTS (CC BY 4.0)", "zonos": "Zonos (Apache 2.0), voix Multilingual LibriSpeech (CC BY 4.0)",
           "chatterbox": "Chatterbox (MIT), voix Multilingual LibriSpeech (CC BY 4.0)", "piper": "Piper / SIWIS (CC BY 4.0)"}

def journal(*a): print(*a, flush=True)

PROPRES = ("elevenlabs", "google", "azure")                               # voix déjà propres : pas d'accélération ni d'effet studio
TAGS = re.compile(r"\[[^\]\[]{1,40}\]")
def sans_tags(t):
    """Retire les indications de jeu entre crochets ([laughs], [sighs]…) : seules les voix ElevenLabs les interprètent."""
    return re.sub(r"\s+", " ", TAGS.sub(" ", t or "")).strip()

ELEVEN_API = "https://api.elevenlabs.io"
ELEVEN_MODELE = os.environ.get("ELEVENLABS_MODELE") or "eleven_v4"
USAGES = ("conversational", "characters_animation", "social_media", "entertainment_tv", "advertisement", "narrative_story")

# ------------------------------------------------------------------ moteurs
def sources():
    s = []
    if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS", "1") != "0": s.append("elevenlabs")   # interrupteur de la régie
    if os.environ.get("GOOGLE_TTS_API_KEY"): s.append("google")
    if os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION"): s.append("azure")
    if os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET"):
        s += ["kyutai"] + (["zonos"] if os.environ.get("ZONOS") == "1" else []) + ["chatterbox"]   # Zonos : dépasse le délai sur Modal, désactivé par défaut
    return s

def _post(url, data, headers, timeout=60):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=timeout).read()

def google(voix, textes):
    out, cle = [], os.environ["GOOGLE_TTS_API_KEY"]
    for t in textes:
        try:
            corps = {"input": {"text": t}, "voice": {"languageCode": "fr-FR", "name": f"fr-FR-Chirp3-HD-{voix}"},
                     "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}}
            r = json.loads(_post(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={cle}", json.dumps(corps).encode(),
                                 {"Content-Type": "application/json"}))
            out.append(base64.b64decode(r["audioContent"]))
        except Exception as e:
            journal(f"    google {voix} : {str(e)[:120]}"); out.append(b"")
    return out

def _eleven(chemin, corps=None, binaire=False, timeout=120):
    req = urllib.request.Request(ELEVEN_API + chemin, data=json.dumps(corps).encode() if corps is not None else None,
                                 headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
                                 method="POST" if corps is not None else "GET")
    d = urllib.request.urlopen(req, timeout=timeout).read()
    return d if binaire else json.loads(d or b"{}")

CONTEXTE = {}                                                             # texte -> (réplique d'avant, réplique d'après) : intonation enchaînée
REGLAGES = {"stability": 0.4, "similarity_boost": 0.85, "use_speaker_boost": True}   # voix stable et bien articulée
_SANS_REGLAGES = set()                                                    # modèles qui refusent ces réglages

def elevenlabs(voix, textes):
    out = []
    for t in textes:
        if "elevenlabs" in EN_PANNE: out.append(b""); continue
        corps = {"text": t, "model_id": ELEVEN_MODELE}
        avant, apres = CONTEXTE.get(t, ("", ""))
        if avant: corps["previous_text"] = sans_tags(avant)[:500]
        if apres: corps["next_text"] = sans_tags(apres)[:500]
        if ELEVEN_MODELE not in _SANS_REGLAGES: corps["voice_settings"] = REGLAGES
        try:
            try:
                out.append(_eleven(f"/v1/text-to-speech/{voix}?output_format=mp3_44100_128", corps, binaire=True))
            except urllib.error.HTTPError as e:
                if e.code != 400 or ("voice_settings" not in corps and "previous_text" not in corps): raise
                journal(f"    elevenlabs : réglages refusés ({e.read().decode('utf-8', 'replace')[:120]}), nouvel essai sans")
                _SANS_REGLAGES.add(ELEVEN_MODELE)
                for k in ("voice_settings", "previous_text", "next_text"): corps.pop(k, None)
                out.append(_eleven(f"/v1/text-to-speech/{voix}?output_format=mp3_44100_128", corps, binaire=True))
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:200]
            journal(f"    elevenlabs {voix} : HTTP {e.code} {msg}")
            if e.code in (401, 402, 403, 429) or "quota" in msg.lower():  # crédit épuisé ou clé refusée : voix gratuites pour la suite
                EN_PANNE.add("elevenlabs"); journal("    ElevenLabs indisponible (crédit ou accès) : passage aux voix gratuites")
            out.append(b"")
        except Exception as e:
            journal(f"    elevenlabs {voix} : {str(e)[:120]}"); out.append(b"")
    return out

def dialogue(lignes, tmp):
    """Text to Dialogue (ElevenLabs, avec minutage) : [(voice_id, texte avec indications)] -> un clip par réplique (ou None).
    Toute la scène est jouée d'un seul tenant (par paquets de 2 000 caractères), puis découpée réplique par réplique."""
    import base64
    out = [None] * len(lignes); paquets, cur, n = [], [], 0
    for k, (v, t) in enumerate(lignes):
        if cur and n + len(t) > 1900: paquets.append(cur); cur, n = [], 0
        cur.append(k); n += len(t)
    if cur: paquets.append(cur)
    for j, pq in enumerate(paquets):
        corps = {"inputs": [{"text": lignes[k][1], "voice_id": lignes[k][0]} for k in pq], "model_id": ELEVEN_MODELE}
        if j: corps["previous_text"] = " ".join(sans_tags(lignes[k][1]) for k in paquets[j - 1])[-800:]
        if j + 1 < len(paquets): corps["future_text"] = " ".join(sans_tags(lignes[k][1]) for k in paquets[j + 1])[:800]
        try:
            r = _eleven("/v1/text-to-dialogue/with-timestamps?output_format=mp3_44100_128", corps, timeout=300)
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:200]; journal(f"  dialogue ElevenLabs : HTTP {e.code} {msg}")
            if e.code in (401, 402, 403, 429) or "quota" in msg.lower(): EN_PANNE.add("elevenlabs")
            return out
        except Exception as e:
            journal(f"  dialogue ElevenLabs indisponible : {str(e)[:120]}"); return out
        with open(f"{tmp}/dlg{j}.mp3", "wb") as f: f.write(base64.b64decode(r.get("audio_base64") or ""))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmp}/dlg{j}.mp3", "-ac", "1", "-ar", str(SR), f"{tmp}/dlg{j}.wav"], check=True)
        with wave.open(f"{tmp}/dlg{j}.wav") as w: a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        bornes = {}
        for sg in r.get("voice_segments") or []:
            k = sg.get("dialogue_input_index")
            if k is None or not 0 <= k < len(pq): continue
            d0, d1 = float(sg.get("start_time_seconds", 0)), float(sg.get("end_time_seconds", 0))
            b = bornes.get(k); bornes[k] = (min(b[0], d0), max(b[1], d1)) if b else (d0, d1)
        for k, (d0, d1) in bornes.items():
            morceau = a[max(0, int((d0 - 0.03) * SR)):int((d1 + 0.08) * SR)]
            if len(morceau) < int(0.25 * SR): continue
            try: out[pq[k]] = nettoyer(_vers_octets(morceau), f"{tmp}/dlg{j}_{k}", propre=True)
            except Exception as e: journal(f"  dialogue : découpe {pq[k]} impossible ({str(e)[:80]})")
        journal(f"  dialogue ElevenLabs : paquet {j + 1}/{len(paquets)}, {len(bornes)}/{len(pq)} répliques découpées")
    return out

def voix_eleven(n=4):
    """Voix françaises de la bibliothèque ElevenLabs pour le casting (n par genre), ajoutées au compte si besoin."""
    try:
        mes = {v.get("name"): v.get("voice_id") for v in _eleven("/v2/voices?page_size=100").get("voices", [])}
        lib = _eleven("/v1/shared-voices?language=fr&page_size=50&sort=usage_character_count_1y").get("voices", [])
    except Exception as e:
        journal(f"  ElevenLabs indisponible pour le casting : {str(e)[:120]}"); return []
    out = []
    for g, code in (("male", "h"), ("female", "f")):
        l = sorted([x for x in lib if x.get("gender") == g], key=lambda x: USAGES.index(x["use_case"]) if x.get("use_case") in USAGES else 9)
        for x in l[:n]:
            nom = f"JT {x.get('name', '')}"[:30]; vid = mes.get(nom)
            if not vid:
                try: vid = _eleven(f"/v1/voices/add/{x['public_owner_id']}/{x['voice_id']}", {"new_name": nom}).get("voice_id")
                except Exception as e: journal(f"  voix {nom} non ajoutée : {str(e)[:100]}"); continue
            if vid: out.append({"moteur": "elevenlabs", "voix": vid, "nom": x.get("name", ""), "genre": code})
    return out

def azure(voix, textes):
    out, cle, reg = [], os.environ["AZURE_SPEECH_KEY"], os.environ["AZURE_SPEECH_REGION"]
    for t in textes:
        t2 = t.replace("&", "et").replace("<", " ").replace(">", " ")
        ssml = f"<speak version='1.0' xml:lang='fr-FR'><voice name='{voix}'>{t2}</voice></speak>"
        try:
            out.append(_post(f"https://{reg}.tts.speech.microsoft.com/cognitiveservices/v1", ssml.encode("utf-8"),
                             {"Ocp-Apim-Subscription-Key": cle, "Content-Type": "application/ssml+xml",
                              "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm", "User-Agent": "robot-jt"}))
        except Exception as e:
            journal(f"    azure {voix} : {str(e)[:120]}"); out.append(b"")
    return out

EN_PANNE = set()                                                          # moteurs qui ont échoué pendant cette exécution

def _distant(app, cls, methode, *args, delai=600):
    """Appel Modal avec délai maximal : un moteur qui ne démarre pas ne bloque plus le robot."""
    import modal
    if cls in EN_PANNE: raise RuntimeError(f"{cls} en panne")
    try:
        f = getattr(modal.Cls.from_name(app, cls)(), methode).spawn(*args)
        return f.get(timeout=delai)
    except Exception as e:
        EN_PANNE.add(cls)
        try: f.cancel()
        except Exception: pass
        raise RuntimeError(f"{cls} : {type(e).__name__} {str(e)[:120]}")

def _ref(role):
    p = os.path.join(RACINE, "voix", f"{role}.wav")
    return open(p, "rb").read() if os.path.exists(p) else None

def kyutai(voix, textes):
    return _distant("jt-banque", "Kyutai", "synthese", textes, voix, delai=900)

def zonos(role, textes):
    import modal
    ref = _ref(role)
    if not ref: return [b""] * len(textes)
    return _distant("jt-banque", "Zonos", "synthese", textes, ref, "vif" if role != "presentateur" else "neutre", delai=420)

def chatterbox(role, textes):
    import modal
    ref = _ref(role); refs = {role: ref} if ref else {}
    jeu = {"presentateur": (0.6, 0.4), "envoyee": (0.75, 0.35), "invite": (0.85, 0.35)}.get(role, (0.7, 0.4))   # plus expressif
    res = _distant("jt-voix", "Voix", "synthese", [dict(texte=t, role=role, exag=jeu[0], cfg=jeu[1]) for t in textes], refs, delai=900)
    return [(r.get("wav", b"") if isinstance(r, dict) else r) for r in res]

def synthese(choix, textes):
    m, v = choix["moteur"], choix["voix"]
    try:
        if m != "elevenlabs": textes = [sans_tags(t) for t in textes]
        return {"elevenlabs": elevenlabs, "google": google, "azure": azure, "kyutai": kyutai, "zonos": zonos, "chatterbox": chatterbox}[m](v, textes)
    except Exception as e:
        journal(f"    moteur {m} indisponible : {str(e)[:160]}"); return [b""] * len(textes)

def ecouter(clips):
    """Réécoute par Whisper : [{"texte", "mots"}] (ou None si Whisper est indisponible)."""
    try:
        return _distant("jt-banque", "Whisper", "ecouter", [_vers_octets(a) for a in clips], delai=600)
    except Exception as e:
        journal(f"  Whisper indisponible ({str(e)[:120]}) : contrôle simplifié"); return None

# ------------------------------------------------------------------ audio
def _vers_octets(a, sr=SR):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()

def vif(a, facteur, tmp):
    """Débit accéléré (hauteur conservée) + légère compression : une voix plus énergique, moins « endormie »."""
    if facteur <= 1.001: return a
    with wave.open(f"{tmp}.v.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmp}.v.wav", "-af",
                    f"atempo={facteur:.3f},acompressor=threshold=-18dB:ratio=2.5:attack=5:release=60:makeup=1.5", f"{tmp}.v2.wav"], check=True)
    with wave.open(f"{tmp}.v2.wav") as w: return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768

def expressivite(a):
    """Variation de l'intonation (écart-type de la hauteur, en demi-tons) : une voix monotone sonne fatiguée."""
    fr, n = [], 1024
    for i in range(0, len(a) - n, n // 2):
        x = a[i:i + n] - a[i:i + n].mean()
        if np.abs(x).max() < 0.05: continue
        c = np.correlate(x, x, "full")[n - 1:]; lo, hi = SR // 400, SR // 60; k = lo + int(np.argmax(c[lo:hi]))
        if c[k] > 0.45 * c[0]: fr.append(12 * np.log2(SR / k / 100))
    return float(np.std(fr)) if len(fr) > 8 else 0.0

def nettoyer(octets, tmp, propre=False):
    """Décode, coupe les silences de début/fin, raccourcit les blancs internes, égalise le volume."""
    with open(f"{tmp}.in.wav", "wb") as f: f.write(octets)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmp}.in.wav", "-ac", "1", "-ar", str(SR), f"{tmp}.out.wav"], check=True)
    with wave.open(f"{tmp}.out.wav") as w: a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    h = int(0.01 * SR); n = max(1, len(a) // h)
    e = np.array([np.sqrt(np.mean(a[k * h:(k + 1) * h] ** 2)) for k in range(n)])
    v = e > 0.05 * (np.percentile(e, 95) + 1e-9)
    if v.any():
        i0, i1 = max(0, int(np.argmax(v)) - 3), min(n, n - int(np.argmax(v[::-1])) + 8); mor, k = [], i0
        while k < i1:
            j = k
            if not v[k]:
                while j < i1 and not v[j]: j += 1
                mor.append(a[k * h:(k + (min(j - k, 20) if j - k > 30 else j - k)) * h]); k = j
            else:
                while j < i1 and v[j]: j += 1
                mor.append(a[k * h:j * h]); k = j
        a = np.concatenate(mor) if mor else a
    r = min(len(a), int(0.015 * SR)); a = a.copy(); a[:r] *= np.linspace(0, 1, r); a[-r:] *= np.linspace(1, 0, r)
    if not propre: return voix_piper.studio(a, f"{tmp}.st", grave=False)
    rms = np.sqrt(np.mean(a[np.abs(a) > 0.01] ** 2)) if (np.abs(a) > 0.01).any() else 0.1
    return np.clip(a * (0.12 / max(rms, 1e-4)), -0.98, 0.98).astype(np.float32)

def f0(a):
    fr, n = [], 1024
    for i in range(0, len(a) - n, n):
        x = a[i:i + n] - a[i:i + n].mean()
        if np.abs(x).max() < 0.05: continue
        c = np.correlate(x, x, "full")[n - 1:]; lo, hi = SR // 400, SR // 60; k = lo + int(np.argmax(c[lo:hi]))
        if c[k] > 0.45 * c[0]: fr.append(SR / k)
    return float(np.median(fr)) if len(fr) > 5 else 0.0

# ------------------------------------------------------------------ contrôle qualité
_U = "zero un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize".split()
_D = {20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante", 60: "soixante"}
def _moins_cent(n):
    if n < 17: return _U[n]
    if n < 20: return "dix " + _U[n - 10]
    if n < 70: u = n % 10; return _D[n - u] + ("" if u == 0 else " et un" if u == 1 else " " + _U[u])
    if n < 80: return "soixante " + ("et onze" if n == 71 else _moins_cent(n - 60))
    return "quatre vingt" + ("s" if n == 80 else " " + _moins_cent(n - 80))
def _moins_mille(n):
    c, r = divmod(n, 100); t = "" if c == 0 else "cent" if c == 1 else _U[c] + " cent"
    return (t + (" " + _moins_cent(r) if r else "")).strip() or "zero"
def en_lettres(n):
    """Nombre entier en toutes lettres (français), jusqu'aux milliards."""
    if n == 0: return "zero"
    out = []
    for val, nom in ((10 ** 9, "milliard"), (10 ** 6, "million"), (1000, "mille")):
        q, n = divmod(n, val)
        if q: out.append("mille" if q == 1 and nom == "mille" else _moins_mille(q) + " " + nom + ("s" if q > 1 and nom != "mille" else ""))
    if n: out.append(_moins_mille(n))
    return " ".join(out)

def _norm(t):
    t = re.sub(r"(\d)[\s\u202f\u00a0.](?=\d{3}\b)", r"\1", t.lower())               # 3 000 / 3.000 -> 3000
    t = t.replace("%", " pour cent ").replace("€", " euros ")
    t = re.sub(r"\d+", lambda m: " " + en_lettres(int(m.group())) + " ", t)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    mots = re.sub(r"[^a-z ]+", " ", t).split()
    return [re.sub(r"(es|s|x|e|ent)$", "", m) if len(m) > 3 else m for m in mots]   # lettres muettes : « article » = « articles »

def note(texte, a, ecoute):
    """Score de qualité : ressemblance du texte entendu, blanc le plus long, débit plausible. Renvoie (ok, détails)."""
    texte = sans_tags(texte); dur = len(a) / SR; attendu = max(0.6, len(texte) * 0.06); debit = dur / attendu
    if ecoute is None:
        return 0.5 < debit < 1.9, {"debit": round(debit, 2)}
    sim = difflib.SequenceMatcher(None, _norm(texte), _norm(ecoute.get("texte", ""))).ratio()
    mots = ecoute.get("mots") or []
    blanc = max([mots[k + 1][1] - mots[k][2] for k in range(len(mots) - 1)] or [0])
    ok = sim >= 0.78 and blanc < 0.75 and 0.5 < debit < 1.9
    return ok, {"sim": round(sim, 2), "blanc": round(blanc, 2), "debit": round(debit, 2)}

# ------------------------------------------------------------------ casting automatique
def candidats():
    src = sources(); c = voix_eleven() if "elevenlabs" in src else []
    for g in "hf":
        if "google" in src: c += [{"moteur": "google", "voix": v, "genre": g} for v in GOOGLE[g]]
        if "azure" in src: c += [{"moteur": "azure", "voix": v, "genre": g} for v in AZURE[g]]
    if "kyutai" in src:
        try:
            kv = _distant("jt-banque", "Kyutai", "voix", delai=900)[:16]
            c += [{"moteur": "kyutai", "voix": v, "genre": "?"} for v in kv]
        except Exception as e:
            journal(f"  Kyutai indisponible pour le casting : {str(e)[:120]}")
    for r, g in ROLES.items():
        if "zonos" in src: c.append({"moteur": "zonos", "voix": r, "genre": g, "role": r})
        if "chatterbox" in src: c.append({"moteur": "chatterbox", "voix": r, "genre": g, "role": r})
    return c

def casting(forcer=False):
    src = sources(); signature = ",".join(src)
    if os.path.exists(FICHE) and not forcer:
        f = json.load(open(FICHE, encoding="utf-8"))
        age = (datetime.date.today() - datetime.date.fromisoformat(f.get("date", "2000-01-01"))).days
        if age < 7 and f.get("sources") == signature: return f
    if not src: return {"date": str(datetime.date.today()), "sources": "", "roles": {}}
    journal(f"Casting des voix (sources : {signature})…"); tmp = tempfile.mkdtemp(); essais = []
    for k, c in enumerate(candidats()):
        roles = [c["role"]] if c.get("role") else list(ROLES)
        texte = TEST[roles[0]] if len(roles) == 1 else TEST["presentateur"]
        o = synthese(c, [texte])[0]
        if not o: continue
        try:
            a = nettoyer(o, f"{tmp}/c{k}", propre=c["moteur"] in PROPRES)
            if c["moteur"] not in PROPRES: a = vif(a, ENERGIE.get(roles[0], 1.12), f"{tmp}/c{k}")
        except Exception: continue
        essais.append((c, texte, a))
    ecoutes = ecouter([a for _, _, a in essais]) or [None] * len(essais)
    fiches = []
    for (c, texte, a), e in zip(essais, ecoutes):
        ok, d = note(texte, a, e); hz = f0(a)
        genre = c["genre"] if c["genre"] != "?" else ("h" if 0 < hz < 165 else "f" if hz > 175 else "?")
        expr = expressivite(a)
        score = (PRIORITE[c["moteur"]] + (4 * d.get("sim", 0.8)) - max(0, d.get("blanc", 0) - 0.4)       # articulation : voix bien comprise par Whisper
                 - abs(np.log(max(d.get("debit", 1), 1e-3))) + 0.35 * min(expr, 4.0))         # bonus aux voix qui « jouent »
        d["expr"] = round(expr, 1)
        journal(f"  {c['moteur']:10s} {(c.get('nom') or c['voix'])[:38]:38s} genre {genre} f0 {hz:5.0f} {d} {'OK' if ok else 'refusée'} score {score:.2f}")
        if ok: fiches.append(dict(c, genre=genre, f0=round(hz), score=round(score, 2)))
    roles, pris = {}, set()
    for role, g in ROLES.items():                                          # chaque rôle : 3 voix du bon genre, distinctes des autres rôles
        liste = [f for f in sorted(fiches, key=lambda f: -f["score"]) if f["genre"] == g and (f.get("role") in (None, role))
                 and (f["moteur"], f["voix"]) not in pris]
        if role == "invite":                                               # l'invité doit sonner différemment du présentateur
            p0 = roles.get("presentateur", [{}])[0] if roles.get("presentateur") else {}
            liste.sort(key=lambda f: -(f["score"] + (0.3 if abs(f.get("f0", 0) - p0.get("f0", 0)) > 20 else 0)))
        roles[role] = liste[:3]
        if liste: pris.add((liste[0]["moteur"], liste[0]["voix"]))
        journal(f"  -> {role} : " + ", ".join(f"{f['moteur']}:{f['voix']}" for f in roles[role]))
    fiche = {"date": str(datetime.date.today()), "sources": signature, "roles": roles}
    os.makedirs(os.path.dirname(FICHE), exist_ok=True)
    json.dump(fiche, open(FICHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return fiche

# ------------------------------------------------------------------ génération du jour
def generer(repliques):
    """repliques : [{"p", "t", "d"}]. Renvoie (audios, mots, crédits) ou None si aucune source n'est disponible."""
    fiche = casting()
    if not fiche.get("roles") or not any(fiche["roles"].values()): return None
    tmp = tempfile.mkdtemp(); n = len(repliques)
    audios, mots, utilises = [None] * n, [None] * n, set()
    meilleures = {}                                                        # i -> (sim, clip, mots, moteur) : meilleure prise refusée
    dits = [r.get("d") or r["t"] for r in repliques]
    CONTEXTE.clear()
    for i, d in enumerate(dits):                                           # chaque réplique connaît la phrase d'avant et d'après
        CONTEXTE[d] = (dits[i - 1] if i else "", dits[i + 1] if i + 1 < n else "")
    pris = {(c["moteur"], c["voix"]) for r in {x["p"] for x in repliques} for c in fiche["roles"].get(r, [])[:1]}
    principales = {r: (v[0]["moteur"], v[0]["voix"]) for r, v in fiche["roles"].items() if v}
    def voix_de(role):
        if fiche["roles"].get(role):                                       # une voix fixe par personnage : jamais celle d'un autre
            autres = {v for r, v in principales.items() if r != role}
            return [c for c in fiche["roles"][role] if (c["moteur"], c["voix"]) not in autres] or fiche["roles"][role][:1]
        # voix off (« narrateur ») : une voix de la banque que n'utilise aucun personnage du sketch
        autres = [c for r in ("envoyee", "presentateur", "invite") for c in fiche["roles"].get(r, [])[1:]]
        libres = [c for c in autres if (c["moteur"], c["voix"]) not in pris]
        return (libres or autres or fiche["roles"].get("presentateur", []))[:3]
    # 1) toute la scène d'un seul tenant (Text to Dialogue d'ElevenLabs) : intonations enchaînées comme une vraie conversation
    casting_scene = {r: voix_de(r)[0] for r in {x["p"] for x in repliques} if voix_de(r)}
    if all(c["moteur"] == "elevenlabs" for c in casting_scene.values()) and os.environ.get("DIALOGUE", "1") != "0" and "elevenlabs" not in EN_PANNE:
        clips = dialogue([(casting_scene[r["p"]]["voix"], dits[i]) for i, r in enumerate(repliques)], tmp)
        valides = [(i, c) for i, c in enumerate(clips) if c is not None]
        ecoutes = ecouter([c for _, c in valides]) if valides else []
        for (i, c), e in zip(valides, ecoutes or [None] * len(valides)):
            ok, d = note(dits[i], c, e)
            journal(f"  voix {i} ({repliques[i]['p']}, dialogue) {d} {'OK' if ok else 'refaite seule'}")
            if ok: audios[i] = c; mots[i] = (e or {}).get("mots")
            elif d.get("blanc", 0) < 0.75 and 0.5 < d.get("debit", 1) < 1.9: meilleures[i] = (d.get("sim", 0), c, (e or {}).get("mots"), "elevenlabs")
        if any(a is not None for a in audios): utilises.add("elevenlabs")
    # 2) réplique par réplique pour ce qui reste (ou si le dialogue est indisponible)
    for role in sorted({r["p"] for r in repliques}):
        idx = [i for i, r in enumerate(repliques) if r["p"] == role]
        if all(audios[i] is not None for i in idx): continue
        for choix in voix_de(role):
            propre = choix["moteur"] in PROPRES; restant = [i for i in idx if audios[i] is None]; ok_role = True
            for tour in range(3):                                          # 1 prise + 2 reprises pour les répliques ratées
                textes = [repliques[i].get("d") or repliques[i]["t"] for i in restant]
                brut = synthese(choix, textes); clips = []
                for i, o in zip(restant, brut):
                    try:
                        c = nettoyer(o, f"{tmp}/{i}_{tour}", propre) if o else None
                        clips.append(vif(c, ENERGIE.get(role, 1.12), f"{tmp}/{i}_{tour}") if c is not None and not propre else c)
                    except Exception: clips.append(None)
                valides = [c for c in clips if c is not None]
                ecoutes = ecouter(valides) if valides else []
                it = iter(ecoutes or [None] * len(valides)); encore = []
                for i, c, t in zip(restant, clips, textes):
                    if c is None: encore.append(i); continue
                    e = next(it); ok, d = note(t, c, e)
                    journal(f"  voix {i} ({role}, {choix['moteur']}:{choix['voix'][:30]}, prise {tour + 1}) {d} {'OK' if ok else 'refaite'}")
                    if ok:
                        audios[i] = c; mots[i] = (e or {}).get("mots")
                    elif d.get("blanc", 0) < 0.75 and 0.5 < d.get("debit", 1) < 1.9 and d.get("sim", 0) > meilleures.get(i, (0,))[0]:
                        meilleures[i] = (d.get("sim", 0), c, (e or {}).get("mots"), choix["moteur"])
                    if not ok: encore.append(i)
                restant = [i for i in encore if audios[i] is None]
                if not restant: break
            if all(audios[i] is not None for i in idx):
                utilises.add(choix["moteur"]); break
            if all(audios[i] is not None or meilleures.get(i, (0,))[0] >= 0.6 for i in idx):   # garder SA voix plutôt que d'en changer
                for i in idx:
                    if audios[i] is None:
                        _, audios[i], mots[i], m = meilleures[i]; utilises.add(m)
                        journal(f"  voix {i} ({role}) : meilleure prise gardée pour ne pas changer la voix du personnage")
                utilises.add(choix["moteur"]); break
            journal(f"  {role} : la voix {choix['moteur']}:{choix['voix']} échoue, passage à la voix de remplacement")
            for i in restant: audios[i] = None; mots[i] = None
        for i in idx:                                                      # une réplique ratée ne fait plus tomber toute la banque :
            if audios[i] is None and meilleures.get(i, (0,))[0] >= 0.6:    # on garde sa meilleure prise si elle reste compréhensible
                _, audios[i], mots[i], m = meilleures[i]; utilises.add(m)
                journal(f"  voix {i} ({role}) : meilleure prise gardée (ressemblance {meilleures[i][0]})")
        if any(audios[i] is None for i in idx):
            return None                                                    # le robot basculera sur la chaîne de secours
    return audios, mots, sorted(CREDITS[m] for m in utilises)
