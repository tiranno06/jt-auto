"""Banque de voix : le robot pioche automatiquement la meilleure voix disponible pour chaque personnage,
parmi toutes les sources gratuites et utilisables commercialement, et vérifie chaque réplique.

Sources (activées automatiquement si disponibles) :
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
import base64, datetime, difflib, io, json, os, re, subprocess, tempfile, unicodedata, urllib.request, wave
import numpy as np
import voix_piper

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FICHE = os.path.join(RACINE, "voix", "banque.json")
SR = 22050
ROLES = {"presentateur": "h", "invite": "h", "envoyee": "f"}
TEST = {"presentateur": "Bonsoir. Le gouvernement a présenté son budget ce matin. Les députés, eux, cherchent encore les économies.",
        "invite": "Ce n'est pas un échec. C'est une réussite qui ne s'est pas encore produite. Nous restons très confiants.",
        "envoyee": "Je suis en direct de l'Assemblée. Ici, tout le monde attend. Personne ne sait vraiment quoi, mais tout le monde attend."}
PRIORITE = {"google": 3.0, "azure": 2.8, "kyutai": 2.2, "zonos": 1.6, "chatterbox": 1.5}
GOOGLE = {"h": ["Charon", "Orus", "Fenrir", "Iapetus", "Algieba"], "f": ["Aoede", "Kore", "Leda", "Despina", "Erinome"]}
AZURE = {"h": ["fr-FR-HenriNeural", "fr-FR-RemyMultilingualNeural", "fr-FR-AlainNeural", "fr-FR-JeromeNeural"],
         "f": ["fr-FR-DeniseNeural", "fr-FR-VivienneMultilingualNeural", "fr-FR-BrigitteNeural", "fr-FR-CelesteNeural"]}
# débit par rôle : les voix de livres audio lisent trop lentement pour un sketch (accéléré sans changer la hauteur)
ENERGIE = {"presentateur": 1.12, "envoyee": 1.16, "invite": 1.14}

CREDITS = {"google": "Google Cloud Text-to-Speech", "azure": "Microsoft Azure Speech",
           "kyutai": "Kyutai TTS (CC BY 4.0), voix CML-TTS (CC BY 4.0)", "zonos": "Zonos (Apache 2.0), voix Multilingual LibriSpeech (CC BY 4.0)",
           "chatterbox": "Chatterbox (MIT), voix Multilingual LibriSpeech (CC BY 4.0)", "piper": "Piper / SIWIS (CC BY 4.0)"}

def journal(*a): print(*a, flush=True)

# ------------------------------------------------------------------ moteurs
def sources():
    s = []
    if os.environ.get("GOOGLE_TTS_API_KEY"): s.append("google")
    if os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION"): s.append("azure")
    if os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET"): s += ["kyutai", "zonos", "chatterbox"]
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
        return {"google": google, "azure": azure, "kyutai": kyutai, "zonos": zonos, "chatterbox": chatterbox}[m](v, textes)
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
    return re.sub(r"[^a-z ]+", " ", t).split()

def note(texte, a, ecoute):
    """Score de qualité : ressemblance du texte entendu, blanc le plus long, débit plausible. Renvoie (ok, détails)."""
    dur = len(a) / SR; attendu = max(0.6, len(texte) * 0.06); debit = dur / attendu
    if ecoute is None:
        return 0.5 < debit < 1.9, {"debit": round(debit, 2)}
    sim = difflib.SequenceMatcher(None, _norm(texte), _norm(ecoute.get("texte", ""))).ratio()
    mots = ecoute.get("mots") or []
    blanc = max([mots[k + 1][1] - mots[k][2] for k in range(len(mots) - 1)] or [0])
    ok = sim >= 0.78 and blanc < 0.75 and 0.5 < debit < 1.9
    return ok, {"sim": round(sim, 2), "blanc": round(blanc, 2), "debit": round(debit, 2)}

# ------------------------------------------------------------------ casting automatique
def candidats():
    src = sources(); c = []
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
            a = nettoyer(o, f"{tmp}/c{k}", propre=c["moteur"] in ("google", "azure"))
            if c["moteur"] not in ("google", "azure"): a = vif(a, ENERGIE.get(roles[0], 1.12), f"{tmp}/c{k}")
        except Exception: continue
        essais.append((c, texte, a))
    ecoutes = ecouter([a for _, _, a in essais]) or [None] * len(essais)
    fiches = []
    for (c, texte, a), e in zip(essais, ecoutes):
        ok, d = note(texte, a, e); hz = f0(a)
        genre = c["genre"] if c["genre"] != "?" else ("h" if 0 < hz < 165 else "f" if hz > 175 else "?")
        expr = expressivite(a)
        score = (PRIORITE[c["moteur"]] + (2 * d.get("sim", 0.8)) - max(0, d.get("blanc", 0) - 0.4)
                 - abs(np.log(max(d.get("debit", 1), 1e-3))) + 0.35 * min(expr, 4.0))         # bonus aux voix qui « jouent »
        d["expr"] = round(expr, 1)
        journal(f"  {c['moteur']:10s} {c['voix'][:38]:38s} genre {genre} f0 {hz:5.0f} {d} {'OK' if ok else 'refusée'} score {score:.2f}")
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
    for role in sorted({r["p"] for r in repliques}):
        idx = [i for i, r in enumerate(repliques) if r["p"] == role]
        for choix in fiche["roles"].get(role, []):
            propre = choix["moteur"] in ("google", "azure"); restant = list(idx); ok_role = True
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
                    if not ok: encore.append(i)
                restant = [i for i in encore if audios[i] is None]
                if not restant: break
            if all(audios[i] is not None for i in idx):
                utilises.add(choix["moteur"]); break
            journal(f"  {role} : la voix {choix['moteur']}:{choix['voix']} échoue, passage à la voix de remplacement")
            for i in idx: audios[i] = None; mots[i] = None
        if any(audios[i] is None for i in idx):
            return None                                                    # le robot basculera sur la chaîne de secours
    return audios, mots, sorted(CREDITS[m] for m in utilises)
