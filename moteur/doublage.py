"""Vidéo construite sur la bande son d'une vidéo TikTok (onglet Manuel → « Depuis une vidéo TikTok »).

1. yt-dlp récupère le son de la vidéo (et le nom du compte d'origine, pour le crédit dans la description) ;
2. ElevenLabs isole les voix (pour le mouvement des bouches) et transcrit avec qui parle et quand (Scribe, séparation des voix) ;
   repli : Whisper, une seule voix ;
3. Claude reconstitue la scène : quel personnage joue quelle voix, la situation, les décors, les émotions, le titre ;
4. le moteur cartoon anime Jojo, Kévin et Lila en play-back exact sur la bande son d'origine, gardée telle quelle (voix + musique).

preparer(url) -> (sk, audios, mots) prêts pour cartoon.rendre."""
import math, base64, json, os, re, subprocess, tempfile, wave
import reseau
import numpy as np

SR, SRM = 22050, 44100
DUREE_MAX = 180                                                            # au-delà de 3 min : refusé (coût des décors et du rendu)
ROLES = ("presentateur", "invite", "envoyee", "narrateur")
NOMS = {"presentateur": "Jojo", "invite": "Kévin", "envoyee": "Lila", "narrateur": "voix off"}

def journal(m): print(m, flush=True)

def _lire_wav(chemin):
    with wave.open(chemin) as w: return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768

def _vers_mono(src, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ac", "1", "-ar", str(SR), dst], check=True)
    return _lire_wav(dst)

def lien_valide(url):
    return bool(re.match(r"^https?://([a-z0-9-]+\.)*tiktok\.com/\S+$", (url or "").strip(), re.I))

VARIANTES = (["--impersonate", "chrome"], ["--extractor-args", "tiktok:api_hostname=api16-normal-c-useast1a.tiktokv.com"], [])

def _ytdlp(url, tmp):
    """yt-dlp, en imitant un vrai navigateur puis par l'API de l'appli TikTok (la page web bloque souvent les serveurs) -> (infos, fichier)."""
    import sys
    err = ""
    for v in VARIANTES:
        for f in os.listdir(tmp):
            if f.startswith("src."): os.remove(f"{tmp}/{f}")
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-warnings", "--socket-timeout", "30", *v, "-f", "best[acodec!=none][height<=1080]/best[acodec!=none]/bestaudio/best",
                            "-o", f"{tmp}/src.%(ext)s", "-j", "--no-simulate", url], capture_output=True, text=True, timeout=600)
        src = next((f"{tmp}/{f}" for f in os.listdir(tmp) if f.startswith("src.") and not f.endswith(".part")), None)
        if r.returncode == 0 and src:
            journal(f"  son téléchargé (yt-dlp {' '.join(v) or 'standard'})")
            return json.loads(r.stdout.strip().splitlines()[-1]), src
        err = (r.stderr or "").strip()[-200:]; journal(f"  yt-dlp {' '.join(v) or 'standard'} : échec ({err[:120]})")
    return None, err

def _tikwm(url, tmp):
    """Dernier recours : service public tikwm.com (lien direct du fichier de la vidéo)."""
    import urllib.parse, urllib.request
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
    req = urllib.request.Request("https://www.tikwm.com/api/?" + urllib.parse.urlencode({"url": url, "hd": "0"}), headers=ua)
    d = (json.loads(reseau.ouvrir(req, timeout=60)) or {}).get("data") or {}
    lien = d.get("play") or d.get("wmplay")
    if not lien: raise RuntimeError("tikwm : vidéo introuvable")
    if lien.startswith("/"): lien = "https://www.tikwm.com" + lien
    open(f"{tmp}/src.mp4", "wb").write(reseau.ouvrir(urllib.request.Request(lien, headers=ua), timeout=300))
    a = d.get("author") or {}
    journal("  son téléchargé (tikwm)")
    return {"uploader": a.get("unique_id"), "channel": a.get("nickname"), "duration": d.get("duration"), "webpage_url": url}, f"{tmp}/src.mp4"

def telecharger(url, tmp):
    """Son de la vidéo -> (infos, piste stéréo 44,1 kHz pour le montage, piste mono 22 kHz pour l'analyse)."""
    url = (url or "").strip()
    if not lien_valide(url): raise RuntimeError("il faut un lien de vidéo TikTok (https://www.tiktok.com/@compte/video/… ou https://vm.tiktok.com/…)")
    info, src = _ytdlp(url, tmp)
    if info is None:
        err = src
        try: info, src = _tikwm(url, tmp)
        except Exception as e:
            raise RuntimeError(f"téléchargement impossible (vidéo privée, supprimée, lien incorrect ou TikTok bloque le serveur) : {err[:200]} / {str(e)[:150]}")
    info["_fichier"] = src                                                 # la vidéo elle-même (image analysée par analyse_video)
    if float(info.get("duration") or 0) > DUREE_MAX: raise RuntimeError(f"vidéo trop longue ({info.get('duration')} s, {DUREE_MAX} s au plus)")
    piste = f"{tmp}/piste.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "2", "-ar", str(SRM), piste], check=True)
    mono = _vers_mono(piste, f"{tmp}/mono.wav")
    if len(mono) / SR > DUREE_MAX + 5: raise RuntimeError(f"vidéo trop longue ({len(mono) / SR:.0f} s, {DUREE_MAX} s au plus)")
    if np.abs(mono).max() < 0.01: raise RuntimeError("la vidéo n'a pas de son")
    return info, piste, mono

class _Rep:
    def __init__(self, contenu): self.content = contenu
    def json(self): return json.loads(self.content or b"{}")

def _multipart(chemin, fichiers, champs, timeout=600):
    """Envoi de fichier à ElevenLabs (multipart/form-data, bibliothèque standard uniquement)."""
    import urllib.error, urllib.request, uuid
    bord = uuid.uuid4().hex; corps = b""
    for k, v in champs.items():
        corps += f'--{bord}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, (nom, f, typ) in fichiers.items():
        corps += f'--{bord}\r\nContent-Disposition: form-data; name="{k}"; filename="{nom}"\r\nContent-Type: {typ}\r\n\r\n'.encode() + f.read() + b"\r\n"
    corps += f"--{bord}--\r\n".encode()
    req = urllib.request.Request("https://api.elevenlabs.io" + chemin, data=corps, method="POST",
                                 headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": f"multipart/form-data; boundary={bord}"})
    try: return _Rep(reseau.ouvrir(req, timeout=timeout))
    except urllib.error.HTTPError as e: raise RuntimeError(f"ElevenLabs {e.code} : {e.read()[:300]!r}")

def isoler(tmp):
    """Voix seules (sans musique ni bruits) : sert au mouvement des bouches et à la transcription. Repli : le son complet."""
    try:
        r = _multipart("/v1/audio-isolation", {"audio": ("son.wav", open(f"{tmp}/mono.wav", "rb"), "audio/wav")}, {})
        open(f"{tmp}/voix.mp3", "wb").write(r.content)
        v = _vers_mono(f"{tmp}/voix.mp3", f"{tmp}/voix.wav"); journal("  voix isolées (ElevenLabs)"); return v, f"{tmp}/voix.wav"
    except Exception as e:
        journal(f"  isolation des voix impossible ({str(e)[:150]}) : son complet utilisé"); return None, f"{tmp}/mono.wav"

def transcrire(chemin, mono):
    """Mots avec instants et voix : [{"w", "s", "e", "voix"}]. ElevenLabs Scribe (plusieurs voix), sinon Whisper (une voix)."""
    EVENEMENTS.clear()
    try:
        r = _multipart("/v1/speech-to-text", {"file": ("son.wav", open(chemin, "rb"), "audio/wav")},
                       {"model_id": "scribe_v1", "diarize": "true", "timestamps_granularity": "word", "tag_audio_events": "true"}).json()
        mots = [{"w": x["text"].strip(), "s": float(x["start"]), "e": float(x["end"]), "voix": x.get("speaker_id") or "speaker_0"}
                for x in r.get("words", []) if x.get("type", "word") == "word" and str(x.get("text", "")).strip()]
        EVENEMENTS[:] = [(float(x["start"]), float(x["end"]), str(x.get("text", "")).strip("() ").lower())       # rires, applaudissements…
                         for x in r.get("words", []) if x.get("type") == "audio_event" and x.get("start") is not None]
        if mots:
            journal(f"  transcription ElevenLabs : {len(mots)} mots, {len({m['voix'] for m in mots})} voix, langue {r.get('language_code')}"); return mots
    except Exception as e:
        journal(f"  transcription ElevenLabs impossible ({str(e)[:150]}) : Whisper")
    import voix_banque
    e_ = (voix_banque.ecouter([mono]) or [None])[0] or {}
    mots = [{"w": w, "s": float(s), "e": float(f), "voix": "speaker_0"} for w, s, f in (e_.get("mots") or [])]
    if not mots: mots = whisper_local(mono)                               # ni ElevenLabs ni Modal : Whisper gratuit sur la machine
    if not mots: raise RuntimeError("aucune parole reconnue dans la vidéo")
    return mots

def whisper_local(mono):
    """Repli 100 % gratuit : Whisper (faster-whisper, modèle « small ») tourne directement sur la machine GitHub, sans crédit."""
    try:
        from faster_whisper import WhisperModel
        from scipy.signal import resample_poly
        a = resample_poly(np.asarray(mono, np.float32), 320, 441).astype(np.float32)   # 22 050 Hz -> 16 000 Hz
        seg, _ = WhisperModel(os.environ.get("WHISPER_LOCAL", "small"), device="cpu", compute_type="int8").transcribe(
            a, language="fr", word_timestamps=True, vad_filter=True)
        mots = [{"w": w.word.strip(), "s": float(w.start), "e": float(w.end), "voix": "speaker_0"} for x in seg for w in (x.words or []) if w.word.strip()]
        journal(f"  transcription gratuite (Whisper sur la machine) : {len(mots)} mots"); return mots
    except Exception as e:
        journal(f"  Whisper gratuit indisponible ({str(e)[:150]})"); return []

def separer_voix(mots, sig):
    """Sans ElevenLabs (une seule voix reconnue) : on sépare les personnes d'après la hauteur de la voix, phrase par phrase
    (voix grave / voix aiguë), pour que chaque personnage ne dise que ses propres répliques. Gratuit."""
    if len({m["voix"] for m in mots}) > 1: return mots
    segs = []                                                              # morceaux fins : coupés à chaque petite pause ou fin de phrase
    for m in mots:
        if not segs or m["s"] - segs[-1]["mots"][-1]["e"] > 0.3 or re.search(r"[.!?…]$", segs[-1]["mots"][-1]["w"]): segs.append({"mots": [m]})
        else: segs[-1]["mots"].append(m)
    for s in segs: s["deb"], s["fin"] = s["mots"][0]["s"], s["mots"][-1]["e"]
    hz = []
    for s in segs:
        h = hauteurs(sig, [dict(s, voix="x")]).get("x"); hz.append(math.log(h) if h else None)
    v = [x for x in hz if x is not None]
    if len(v) < 2 or max(v) - min(v) < math.log(1.3): return mots         # une seule personne (ou voix trop proches)
    c = [min(v), max(v)]
    for _ in range(12):                                                    # deux groupes : voix grave, voix aiguë
        g = [[x for x in v if abs(x - c[0]) <= abs(x - c[1])], [x for x in v if abs(x - c[0]) > abs(x - c[1])]]
        c = [sum(g[k]) / len(g[k]) if g[k] else c[k] for k in (0, 1)]
    if c[1] - c[0] < math.log(1.25): return mots
    for s, x in zip(segs, hz):
        voix = "speaker_0" if x is None or abs(x - c[0]) <= abs(x - c[1]) else "speaker_1"
        for m in s["mots"]: m["voix"] = voix
    journal(f"  voix séparées par la hauteur (gratuit) : {round(math.exp(c[0]))} Hz et {round(math.exp(c[1]))} Hz")
    return mots

EVENEMENTS = []                                                            # événements sonores repérés par Scribe : (début, fin, nom)

def segments(mots):
    """Répliques : mots consécutifs d'une même voix, coupés aux longs silences et aux fins de phrase quand la réplique s'allonge."""
    out = []
    for m in mots:
        c = out[-1] if out else None
        nouvelle = (c is None or m["voix"] != c["voix"] or m["s"] - c["mots"][-1]["e"] > 0.9
                    or (len(c["mots"]) >= 10 and re.search(r"[.!?…]$", c["mots"][-1]["w"])) or len(c["mots"]) >= 28)
        if nouvelle: out.append({"voix": m["voix"], "mots": [m]})
        else: c["mots"].append(m)
    for s in out:
        s["t"] = re.sub(r"\s+([,.!?…])", r"\1", " ".join(m["w"] for m in s["mots"])).strip()
        s["deb"], s["fin"] = s["mots"][0]["s"], s["mots"][-1]["e"]
    return out

def hauteurs(voix_sig, segs):
    """Hauteur moyenne (Hz) de chaque voix : aide Claude à choisir qui joue qui (voix grave / aiguë)."""
    res = {}
    for v in {s["voix"] for s in segs}:
        f0, n = [], 1024
        for s in segs:
            if s["voix"] != v: continue
            a = voix_sig[int(s["deb"] * SR):int(s["fin"] * SR)]
            for i in range(0, len(a) - n, n):
                x = a[i:i + n] - a[i:i + n].mean()
                if np.abs(x).max() < 0.05: continue
                c = np.correlate(x, x, "full")[n - 1:]; lo, hi = SR // 400, SR // 70; k = lo + int(np.argmax(c[lo:hi]))
                if c[k] > 0.4 * c[0]: f0.append(SR / k)
        res[v] = round(float(np.median(f0))) if len(f0) >= 5 else None
    return res

CONSIGNE = """Voici la transcription de la bande son d'une vidéo TikTok (qui parle, quand, quoi). Nos personnages vont la « jouer » en play-back dans
un dessin animé : on ne change AUCUN mot ni AUCUN minutage, tu reconstitues seulement la scène autour du son.
Nos personnages (rôles) : presentateur, invite et envoyee, joués à chaque vidéo par des adultes différents (casting libre) dessinés
dans le style « toons » ; tout l'univers (lieu, tenues, plans, émotions, rythme) se construit autour de ce son : paroles, intonations,
émotions et ambiance.
Une voix qui commente sans être dans la scène peut être la voix off (narrateur : non dessinée).
Voix repérées (hauteur moyenne : moins de 165 Hz ≈ voix d'homme, plus de 165 Hz ≈ voix de femme ou d'enfant) :
{voix}
Transcription (n° de réplique, voix, début–fin en secondes, texte) :
{lignes}
Avec l'outil doublage :
- "casting" : pour CHAQUE voix ci-dessus, le personnage qui la joue : presentateur (= Jojo), invite (= Kévin), envoyee (= Lila) ou narrateur.
  Voix de femme → Lila ; deux voix différentes → deux personnages différents ; au plus 3 personnages dessinés.
- "contexte" : en 1 ou 2 phrases, la situation que tu reconstitues (qui, où, ce qui se passe), d'après ce qui est dit et le ton ;
- "d" : pour chaque réplique (même ordre, même nombre), l'émotion juste en indication anglaise entre crochets suivie du texte (« [annoyed] … ») ;
- "decoupage" : 1 à 4 scènes (indices des répliques, toutes couvertes, dans l'ordre ; "decor" EN ANGLAIS sans personnage : lieu précis + 2 ou 3 objets,
  cohérent avec ce qui est dit ; "titre" = carton court seulement si la scène change de moment ou de lieu) ;
- "sujet" (30 caractères max), "titre_accroche" (« POV : … » ou « Quand … », 40 caractères max), "legende" (1 phrase en français),
  "question" (pour les commentaires), "hashtags" (4 à 6, sans #) ;
{studio}"""

IMAGES = """

IMAGES CI-DESSUS : des images clés de la vidéo TikTok d'origine (dans l'ordre). Reconstruis notre scène À SON IMAGE, en la traduisant
dans notre dessin animé et dans nos listes : le lieu exact, le décor du premier plan à l'arrière-plan ("decor" en anglais, avec les objets
qu'on y voit), les objets tenus ("studio" → "objets" = [{{"replique", "objet"}}] pris dans la liste des objets ci-dessous), la tenue de
chaque personne (forme, couleur, motif, accessoires) et sa coiffure ("cheveux" parmi {coiffures} ; "c_cheveux" = couleur), son couvre-chef ("chapeau"), sa barbe, leurs mimiques et gestes (visage, bouche, yeux, bras, mains, jambes, pieds) pour les "plans" (geste, réaction),
la lumière et l'heure, et le rythme du montage d'origine ("cadence"). La personne la plus présente à l'image joue la voix la plus présente.
Objets possibles : telephone, billet, portefeuille, micro, verre, cafe, livre, cles, carte, facture, bouteille, haltere, seringue, parapluie,
telecommande, fleur, cadeau, pizza, croissant, tablette, lettre, journal, stylo, valise.
Mesures faites par le robot sur la vidéo : {mesures}
{banque}"""

def consigne(voix, lignes):
    import studio, decor_dessin as DD, marionnette as M, humain as H
    L = lambda xs: ", ".join(xs)
    return CONSIGNE.format(voix=voix, lignes=lignes, studio=studio.consigne_studio())

def _outil():
    import ecrire
    return {"name": "doublage", "description": "Mise en scène d'une bande son imposée.",
            "input_schema": ecrire._schema({
                "casting": {"type": "array", "items": ecrire._schema({"voix": {"type": "string"}, "role": {"type": "string", "enum": list(ROLES)}}, ["voix", "role"])},
                "contexte": {"type": "string"}, "d": {"type": "array", "items": {"type": "string"}},
                "decoupage": {"type": "array", "items": ecrire._schema({"repliques": {"type": "array", "items": {"type": "integer"}},
                                                                       "decor": {"type": "string"}, "titre": {"type": "string"}}, ["repliques"])},
                "sujet": {"type": "string"}, "titre_accroche": {"type": "string"}, "legende": {"type": "string"}, "question": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
                "studio": {"type": "object", "properties": {
                    "moment": {"type": "string"}, "lieux": {"type": "array", "items": {"type": "string"}},
                    "costumes": {"type": "object"}, "personnages": {"type": "object"}, "gags": {"type": "array", "items": {"type": "string"}},
                    "cadence": {"type": "string", "enum": ["rapide", "normal", "pose"]},
                    "ambiances": {"type": "array", "items": {"type": "string"}},
                    "plans": {"type": "array", "items": ecrire._schema({"replique": {"type": "integer"}, "plan": {"type": "string"}, "mouvement": {"type": "string"},
                                                                         "geste": {"type": "string"}, "reaction": {"type": "string"}}, ["replique"])},
                    "objets": {"type": "array", "items": ecrire._schema({"replique": {"type": "integer"}, "objet": {"type": "string"}}, ["replique", "objet"])}}}},
                ["casting", "d", "decoupage"])}

def _casting_defaut(segs, hz):
    """Sans Claude : voix aiguë -> Lila, les autres -> Jojo puis Kévin (par ordre d'apparition)."""
    ordre = list(dict.fromkeys(s["voix"] for s in segs)); res, hommes = {}, ["presentateur", "invite"]
    for v in ordre:
        if (hz.get(v) or 0) > 165 and "envoyee" not in res.values(): res[v] = "envoyee"
        else: res[v] = next((r for r in hommes if r not in res.values()), "presentateur")
    return res

def preparer(url):
    import ecrire
    tmp = tempfile.mkdtemp()
    journal(f"Vidéo depuis TikTok : {url}")
    info, piste, mono = telecharger(url, tmp)
    auteur = info.get("uploader") or info.get("uploader_id") or info.get("channel") or ""
    lien = info.get("webpage_url") or url.strip()
    duree = len(mono) / SR
    journal(f"  son récupéré : {duree:.1f} s, compte d'origine @{auteur}")
    visuel, cles = {}, []
    try:                                                                   # l'image de la vidéo : cadrages, personnes, habits, couleurs, lumière
        import analyse_video
        visuel, cles = analyse_video.analyser(info.get("_fichier") or "")
        journal("  image de la vidéo : " + analyse_video.texte(visuel))
    except Exception as e: journal(f"  analyse de l'image impossible ({str(e)[:150]}) : mise en scène d'après le son seul")
    voix_sig, chemin_voix = isoler(tmp)
    sig = voix_sig if voix_sig is not None and len(voix_sig) >= len(mono) * 0.9 else mono
    segs = segments(separer_voix(transcrire(chemin_voix, mono), sig))
    hz = hauteurs(sig, segs)
    journal(f"  {len(segs)} répliques, voix : {hz}")
    casting, m = _casting_defaut(segs, hz), {}
    try:
        if os.environ.get("CLAUDE_INDISPONIBLE") == "1": raise RuntimeError("Claude indisponible (crédit vérifié au départ)")
        import anthropic
        lignes = "\n".join(f"{k}. {s['voix']} ({s['deb']:.1f}–{s['fin']:.1f}) : {s['t']}" for k, s in enumerate(segs))
        vx = "\n".join(f"- {v} : {h or '?'} Hz, {sum(len(s['mots']) for s in segs if s['voix'] == v)} mots" for v, h in hz.items())
        contenu = consigne(vx, lignes)
        if visuel or cles:                                                 # Claude voit aussi la vidéo d'origine (images clés) et ses mesures
            import analyse_video, banque_visuelle
            import marionnette as M_
            contenu += IMAGES.format(mesures=analyse_video.texte(visuel), banque=banque_visuelle.consigne(), coiffures=", ".join(M_.COIFFURES))
            contenu = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(j).decode()}} for j in cles[:6]] \
                      + [{"type": "text", "text": contenu}]
        m = ecrire._appel(__import__('reseau').claude(), None, [{"role": "user", "content": contenu}], _outil(), max_tokens=8000)
        for c in ecrire._liste(m.get("casting")):
            if isinstance(c, dict) and c.get("voix") in hz and c.get("role") in ROLES: casting[c["voix"]] = c["role"]
        if m.get("contexte"): journal(f"  scène reconstituée : {m['contexte']}")
    except Exception as e:
        journal(f"  mise en scène automatique impossible ({str(e)[:150]}) : une seule scène, casting par la hauteur des voix")
    journal("  casting : " + ", ".join(f"{v} → {NOMS[r]}" for v, r in casting.items()))
    d = [str(x) for x in ecrire._liste(m.get("d"))]
    reps = []
    for k, s in enumerate(segs):
        r = {"p": casting.get(s["voix"], "presentateur"), "t": s["t"], "_deb": round(float(s["deb"]), 3), "_fin": round(float(s["fin"]), 3)}
        if k < len(d) and ecrire._mots_bruts(re.sub(r"\[[^\]]*\]", " ", d[k])) == ecrire._mots_bruts(s["t"]): r["d"] = d[k]
        reps.append(r)
    for o in ecrire._liste((m.get("studio") or {}).get("objets") if isinstance(m.get("studio"), dict) else []):   # objets vus dans la vidéo
        try:
            k_o = int(o.get("replique")); nom_o = str(o.get("objet", "")).lower()
            if 0 <= k_o < len(reps) and nom_o in ecrire.OBJETS: reps[k_o]["objet"] = nom_o
        except (AttributeError, TypeError, ValueError): pass
    if all(r["p"] == "narrateur" for r in reps): reps[0]["p"] = "presentateur"   # au moins un personnage à l'image
    reps[-1]["chute"] = True
    brut = {"sujet": m.get("sujet") or segs[0]["t"][:30], "repliques": [dict(r) for r in reps[:16]], "legende": m.get("legende") or segs[0]["t"][:120],
            "hashtags": ecrire._liste(m.get("hashtags")) or ["humour", "doublage", "pov"], "titre_accroche": m.get("titre_accroche") or "",
            "question": m.get("question") or "", "sources": [lien], "decoupage": []}
    sk = ecrire.valider(brut, {lien}, libre=True, minimum=1)
    sk["repliques"] = reps                                                 # toutes les répliques, texte complet (pas de limite de longueur)
    dec = [x for x in ecrire._liste(m.get("decoupage")) if isinstance(x, dict)]
    sk["decoupage"] = [dict(sc, scene=str(k + 1)) for k, sc in enumerate(ecrire._decoupage(dec, len(reps)))] or \
                      [{"scene": "1", "repliques": list(range(len(reps))), "lieu": "", "son": "", "duree": 0,
                        "decor": "" if os.environ.get("RENDU_DETAILLE", "1") != "0" else "cozy living room, sofa, coffee table, lamp"}]   # sans Claude : le studio devine le lieu
    if isinstance(m.get("studio"), dict): sk["studio"] = m["studio"]          # direction artistique de Claude (vérifiée par studio.bible)
    sk["sources"] = [lien]
    sk["doublage"] = {"piste": piste, "duree": round(duree, 2), "source": lien, "auteur": auteur, "contexte": m.get("contexte", ""),
                      "evenements": [list(e) for e in EVENEMENTS][:60], "visuel": visuel}
    if EVENEMENTS: journal(f"  événements sonores : {', '.join(sorted({e[2] for e in EVENEMENTS}))[:200]}")
    sk["fiche"] = {"note": 0, "decision": "vidéo manuelle (bande son d'une vidéo TikTok)", "decoupage": sk["decoupage"]}
    sk["_monte"] = True                                                    # pas de voix off de titre ni d'accroche rejouée : la bande son est imposée
    # voix de chaque réplique (pour les bouches) et instants des mots, relatifs au début de la réplique
    audios, mots = [], []
    for s in segs:
        a0, a1 = int(s["deb"] * SR), max(int(s["fin"] * SR) + int(0.05 * SR), int(s["deb"] * SR) + int(0.2 * SR))
        audios.append(np.asarray(sig[a0:a1], np.float32))
        mots.append([(x["w"], float(x["s"] - s["deb"]), float(x["e"] - s["deb"])) for x in s["mots"]])
    return sk, audios, mots

def credit(sk):
    d = sk.get("doublage") or {}
    return f"🎧 Son original : @{d['auteur']} — {d['source']}" if d.get("auteur") else f"🎧 Son original : {d.get('source', '')}"
