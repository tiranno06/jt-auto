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
        champs = {"model_id": "scribe_v1", "diarize": "true", "timestamps_granularity": "word", "tag_audio_events": "true"}
        r = _multipart("/v1/speech-to-text", {"file": ("son.wav", open(chemin, "rb"), "audio/wav")}, champs).json()
        mots = [{"w": x["text"].strip(), "s": float(x["start"]), "e": float(x["end"]), "voix": x.get("speaker_id") or "speaker_0"}
                for x in r.get("words", []) if x.get("type", "word") == "word" and str(x.get("text", "")).strip()]
        import locuteurs
        if mots and len({m["voix"] for m in mots}) == 1 and locuteurs._echange(locuteurs.morceaux(mots)) >= 3:
            try:                                                           # une seule voix mais un vrai dialogue : on redemande pour 2 voix
                r2 = _multipart("/v1/speech-to-text", {"file": ("son.wav", open(chemin, "rb"), "audio/wav")}, dict(champs, num_speakers="2")).json()
                m2 = [{"w": x["text"].strip(), "s": float(x["start"]), "e": float(x["end"]), "voix": x.get("speaker_id") or "speaker_0"}
                      for x in r2.get("words", []) if x.get("type", "word") == "word" and str(x.get("text", "")).strip()]
                if len({m["voix"] for m in m2}) >= 2: journal("  2e écoute ElevenLabs (2 voix annoncées) : voix proches séparées"); mots, r = m2, r2
            except Exception as e: journal(f"  2e écoute ElevenLabs impossible ({str(e)[:100]})")
        EVENEMENTS[:] = [(float(x["start"]), float(x["end"]), str(x.get("text", "")).strip("() ").lower())       # rires, applaudissements…
                         for x in r.get("words", []) if x.get("type") == "audio_event" and x.get("start") is not None]
        if mots:
            journal(f"  transcription ElevenLabs : {len(mots)} mots, {len({m['voix'] for m in mots})} voix, langue {r.get('language_code')}")
            SOURCE_MOTS[0] = "elevenlabs"; return mots
    except Exception as e:
        journal(f"  transcription ElevenLabs impossible ({str(e)[:150]}) : Whisper")
    SOURCE_MOTS[0] = "whisper"
    import ecoute
    mots = ecoute.groq(chemin)                                             # Groq : Whisper gratuit en quelques secondes (clé GROQ_API_KEY)
    if mots: return mots
    import voix_banque
    e_ = (voix_banque.ecouter([mono]) or [None])[0] or {}
    mots = [{"w": w, "s": float(s), "e": float(f), "voix": "speaker_0"} for w, s, f in (e_.get("mots") or [])]
    if not mots: mots = whisper_local(mono)                               # ni ElevenLabs ni Modal : Whisper gratuit sur la machine
    if not mots: raise RuntimeError("aucune parole reconnue dans la vidéo")
    return mots

def whisper_local(mono):
    """Repli 100 % gratuit : Whisper (faster-whisper, modèle « large-v3-turbo » : bien moins de fautes que « small », ponctuation
    juste) tourne directement sur la machine GitHub, sans crédit (modèle gardé en cache par le workflow)."""
    try:
        from faster_whisper import WhisperModel
        from scipy.signal import resample_poly
        a = resample_poly(np.asarray(mono, np.float32), 320, 441).astype(np.float32)   # 22 050 Hz -> 16 000 Hz
        seg, _ = WhisperModel(os.environ.get("WHISPER_LOCAL", "large-v3-turbo"), device="cpu", compute_type="int8").transcribe(
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
SOURCE_MOTS = [""]                                                         # qui a transcrit : elevenlabs (mots déjà précis) ou whisper

def segments(mots):
    """Répliques : mots consécutifs d'une même voix, coupés aux longs silences et aux fins de phrase quand la réplique s'allonge."""
    out = []
    for m in mots:
        c = out[-1] if out else None
        nouvelle = (c is None or m["voix"] != c["voix"] or m["s"] - c["mots"][-1]["e"] > 0.9
                    or (len(c["mots"]) >= 10 and re.search(r"[.!?…]$", c["mots"][-1]["w"])) or len(c["mots"]) >= 28
                    or c["mots"][-1]["w"].endswith("?"))                   # après une question : nouvelle réplique (souvent l'autre répond)
        if nouvelle: out.append({"voix": m["voix"], "mots": [m]})
        else: c["mots"].append(m)
    for s in out:
        s["t"] = re.sub(r"\s+([,.!?…])", r"\1", " ".join(m["w"] for m in s["mots"])).strip()
        s["deb"], s["fin"] = s["mots"][0]["s"], s["mots"][-1]["e"]
    return out

def voix_sure(seg, seuil=0.5):
    """La voix de cette réplique est-elle reconnue avec certitude (empreinte vocale mot par mot, locuteurs.affiner) ?"""
    v = [x["sure"] for x in seg.get("mots", []) if x.get("sure") is not None]
    return bool(v) and sum(v) / len(v) >= seuil

RELIRE = """Voici la transcription d'un dialogue entre DEUX personnes (sketch TikTok), découpée en phrases numérotées. Les deux voix se
ressemblent trop : le son ne dit pas qui parle. Pour CHAQUE phrase, dis qui la prononce : "A" ou "B" (A = la personne qui dit la
phrase 0). Raisonne sur le fil du dialogue, comme un scénariste :
- une question appelle presque toujours la réponse de l'AUTRE ; « oui », « non », « bah », « mais », « voilà », « ok » en début de
  phrase répondent souvent à l'autre ;
- une phrase qui reprend les mots de l'autre (« Comme un homme ? ») est la réaction de l'autre ;
- qui s'adresse à qui : « papa », « maman » sont dits par l'enfant, « fiston », « ma fille » par le parent ; « vous » / « nous » ;
- chacun garde son point de vue du début à la fin (celui qui défend une idée continue de la défendre, celui qui ne comprend pas
  continue de poser des questions) ;
- une même personne peut dire plusieurs phrases de suite (phrase coupée, « et… », « donc… », tirade) ; une phrase qui commence
  par une minuscule est la suite de la phrase d'avant (même personne).
Dis aussi en quelques mots qui est A et qui est B (ex. « A : le père, B : le fils »), et combien de personnes parlent vraiment
("nombre" : 1 si c'est un monologue, une seule personne du début à la fin ; sinon 2).

{lignes}
"""

def relire_dialogue(mots, une_voix=False):
    """Contrôle « questions-réponses » par l'IA (Gemini d'abord, gratuit) quand les voix se ressemblent trop : elle lit le dialogue
    PHRASE PAR PHRASE (phrases de locuteurs.phrases) et dit qui dit chaque phrase. Renvoie une liste 0/1 (0 = A), ou None."""
    import ecrire, locuteurs, reseau
    if os.environ.get("RELIRE_DIALOGUE", "1") == "0" or not reseau.ia_disponible(): return None
    ph = locuteurs.phrases(mots)
    if len(ph) < 3: return None
    txt = [re.sub(r"\s+([,.!?…'’-])", r"\1", " ".join(mots[i]["w"] for i in p)) for p in ph]   # « j 'ai » -> « j'ai »
    lignes = "\n".join(f"{k}. {t}" for k, t in enumerate(txt))
    outil = {"name": "dialogue", "description": "Qui dit chaque phrase du dialogue.",
             "input_schema": ecrire._schema({"personnes": {"type": "string"}, "nombre": {"type": "integer"},
                                             "phrases": {"type": "array", "items": ecrire._schema({"n": {"type": "integer"}, "qui": {"type": "string", "enum": ["A", "B"]}}, ["n", "qui"])}},
                                            ["phrases"])}
    try:
        r = ecrire._appel(reseau.claude(raisonner=True), None, [{"role": "user", "content": RELIRE.format(lignes=lignes)}], outil, max_tokens=4000)
    except Exception as e:
        journal(f"  relecture du dialogue par l'IA impossible ({str(e)[:120]})"); return None
    ia = [None] * len(ph)
    for x in ecrire._liste(r.get("phrases")):
        try:
            n = int(x.get("n"))
            if 0 <= n < len(ph) and x.get("qui") in ("A", "B"): ia[n] = 0 if x["qui"] == "A" else 1
        except (AttributeError, TypeError, ValueError): pass
    if sum(x is not None for x in ia) < len(ph) / 2: return None
    try: seul = int(r.get("nombre") or 2) == 1
    except (TypeError, ValueError): seul = False
    if une_voix and (seul or len({x for x in ia if x is not None}) < 2):   # une seule voix ET l'IA lit un monologue : on n'invente personne
        journal("  relecture du dialogue par l'IA : une seule personne parle"); return None
    journal(f"  relecture du dialogue par l'IA : {sum(x is not None for x in ia)}/{len(ph)} phrases ({str(r.get('personnes') or '')[:80]})")
    return ia

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
- "roles" (IMPORTANT quand deux voix se ressemblent ou qu'une même personne fait plusieurs voix) : la reconnaissance a pu donner la
  MÊME voix à deux personnages. Relis le dialogue (qui pose la question, qui répond, qui dit « papa », qui dit « fiston »…) et donne pour
  chaque réplique le rôle qui la dit vraiment : [{{"replique": n, "role": …}}] — seulement pour les répliques à corriger.
  Les répliques marquées « voix sûre » ont été reconnues à l'empreinte vocale : ne les change jamais.
  Voix de femme → Lila ; deux voix différentes → deux personnages différents ; au plus 3 personnages dessinés.
- "contexte" : en 1 ou 2 phrases, la situation que tu reconstitues (qui, où, ce qui se passe), d'après ce qui est dit et le ton ;
- "texte" : pour chaque réplique (même ordre, même nombre), le texte avec SEULEMENT les mots mal entendus par la reconnaissance
  vocale corrigés (mots inventés, argot, noms, liaisons : « mille ballons rien » → « mille balles ou rien »), sans reformuler ni
  résumer, ponctuation juste ; recopie la réplique telle quelle si elle est correcte ;
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
chaque personne (forme, couleur, motif, accessoires) et sa coiffure ("cheveux" parmi {coiffures} ; "c_cheveux" = couleur), son couvre-chef ("chapeau"), sa barbe, leurs mimiques et gestes (visage, bouche, yeux, bras, mains, jambes, pieds) pour le "jeu" de CHAQUE réplique (émotion, geste, intensité : exagère-les un peu, style toons) et les "plans" (geste, réaction),
la lumière et l'heure, et le rythme du montage d'origine ("cadence"). OBLIGATOIRE : "studio" → "decors_vus" = {{rôle: décor EN ANGLAIS tel qu'on
le voit DERRIÈRE cette personne dans la vidéo d'origine (lieu précis + 5 à 8 objets précis avec leur couleur + lumière, 40 mots au plus)}}. La personne la plus présente à l'image joue la voix la plus présente.
Recrée TOUT ce que montre la vidéo, à notre sauce : chaque personne avec son âge, son genre, sa taille et son allure ("personnages"),
les lieux (si les personnes ne sont pas au même endroit, "lieux_separes" : un décor pour chacune), les personnes muettes qu'on voit ou
dont on parle ("figurants"), et la suite des plans de la vidéo d'origine (serré / large, sur qui, avec quel geste) dans "decoupe"
et "plans", aux mêmes moments que ses coupes ({coupes}).
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
                "roles": {"type": "array", "items": ecrire._schema({"replique": {"type": "integer"}, "role": {"type": "string", "enum": list(ROLES)}}, ["replique", "role"])},
                "contexte": {"type": "string"}, "d": {"type": "array", "items": {"type": "string"}},
                "texte": {"type": "array", "items": {"type": "string"}},
                "decoupage": {"type": "array", "items": ecrire._schema({"repliques": {"type": "array", "items": {"type": "integer"}},
                                                                       "decor": {"type": "string"}, "titre": {"type": "string"}}, ["repliques"])},
                "sujet": {"type": "string"}, "titre_accroche": {"type": "string"}, "legende": {"type": "string"}, "question": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
                "studio": {"type": "object", "properties": {
                    "moment": {"type": "string"}, "lieux": {"type": "array", "items": {"type": "string"}},
                    "costumes": {"type": "object"}, "metiers": {"type": "object"}, "personnages": {"type": "object"}, "gags": {"type": "array", "items": {"type": "string"}},
                    "cadence": {"type": "string", "enum": ["rapide", "normal", "pose"]},
                    "ambiances": {"type": "array", "items": {"type": "string"}},
                    "plans": {"type": "array", "items": ecrire._schema({"replique": {"type": "integer"}, "plan": {"type": "string"}, "mouvement": {"type": "string"},
                                                                         "geste": {"type": "string"}, "reaction": {"type": "string"}}, ["replique"])},
                    "objets": {"type": "array", "items": ecrire._schema({"replique": {"type": "integer"}, "objet": {"type": "string"}}, ["replique", "objet"])}}}},
                ["casting", "d", "decoupage"])}

HOMME_DIT = r"\b(fiston|mon fils|mon gar[çc]on|fr[ée]rot|mon fr[èe]re|mec|mon pote|monsieur|papa|mon ch[ée]ri|mon grand)\b"
FEMME_DIT = r"\b(ma fille|ma puce|madame|maman|ma ch[ée]rie|ma belle|ma s[œo]eur|ma grande|ma copine)\b"
HOMME_SOI = r"\bje suis (s[ûu]r|content|pr[êe]t|d[ée]sol[ée]|fatigu[ée]|perdu|mort|grand|petit)\b(?!e)"
FEMME_SOI = r"\bje suis (s[ûu]re|contente|pr[êe]te|d[ée]sol[ée]e|fatigu[ée]e|perdue|morte|grande|petite)\b"

def genre_des_voix(segs, hz):
    """Homme ou femme pour chaque voix, sans Claude : d'abord les MOTS (comment les autres l'appellent : « fiston », « papa, »,
    « ma puce »… ; comment elle parle d'elle : « je suis sûre ») puis la hauteur (voix nettement aiguë = femme)."""
    voix = list(dict.fromkeys(s["voix"] for s in segs)); out = {}
    for v in voix:
        a_lui = " ".join(s["t"] for s in segs if s["voix"] != v).lower() if len(voix) == 2 else ""   # à deux : on s'adresse à l'autre
        lui = " ".join(s["t"] for s in segs if s["voix"] == v).lower()
        h_ = len(re.findall(HOMME_DIT, a_lui)) + len(re.findall(HOMME_SOI, lui)); f_ = len(re.findall(FEMME_DIT, a_lui)) + len(re.findall(FEMME_SOI, lui))
        if h_ != f_: out[v] = "h" if h_ > f_ else "f"
        else: out[v] = "f" if (hz.get(v) or 0) > 190 else "h"                 # 165-190 Hz : souvent un homme (ado, voix qui monte)
    return out

def _casting_defaut(segs, hz):
    """Sans Claude : la voix de femme -> Lila, les autres -> Jojo puis Kévin (par ordre d'apparition)."""
    ordre = list(dict.fromkeys(s["voix"] for s in segs)); res, hommes = {}, ["presentateur", "invite"]; g = genre_des_voix(segs, hz)
    for v in ordre:
        if g.get(v) == "f" and "envoyee" not in res.values(): res[v] = "envoyee"
        else: res[v] = next((r for r in hommes if r not in res.values()), "presentateur")
    return res

def corriger_textes(segs, textes):
    """Texte de chaque réplique corrigé par l'IA (mots mal entendus par la reconnaissance vocale), accepté seulement s'il reste très
    proche de ce qui a été entendu (pas de réécriture) ; quand le nombre de mots est le même, les mots minutés (bouches) suivent."""
    import difflib, ecrire
    out = []
    for k, s in enumerate(segs):
        t = textes[k].strip() if k < len(textes) and isinstance(textes[k], str) else ""
        a, b = " ".join(ecrire._mots_bruts(s["t"])), " ".join(ecrire._mots_bruts(t))
        if not t or not b or abs(len(a.split()) - len(b.split())) > 3 or difflib.SequenceMatcher(None, a, b).ratio() < 0.6: out.append(s["t"]); continue
        if t != s["t"]:
            mots_t = t.split()
            if len(mots_t) == len(s["mots"]):
                for m_, w in zip(s["mots"], mots_t): m_["w"] = w
        out.append(t)
    n = sum(1 for o, s in zip(out, segs) if o != s["t"])
    if n: journal(f"  sous-titres : {n} réplique(s) corrigée(s) (mots mal entendus par la reconnaissance vocale)")
    return out

def casting_unique(casting, segs, hz):
    """Deux voix différentes = deux personnages différents : si l'IA donne la même personne à deux voix, la voix qui parle le moins
    reçoit un personnage libre (du bon genre si possible). Sinon un personnage parlerait tantôt avec une voix d'homme, tantôt de femme."""
    g = genre_des_voix(segs, hz); res = dict(casting)
    poids = {v: sum(len(s["mots"]) for s in segs if s["voix"] == v) for v in res}
    rang = lambda v: ((g.get(v) == "f") == (res[v] == "envoyee"), poids[v])   # garde le rôle : la voix du bon genre, puis la plus bavarde
    for v in sorted(res, key=rang, reverse=True):
        autres = [w for w in res if w != v and res[w] == res[v] and rang(w) >= rang(v)]
        if res[v] == "narrateur" or not autres: continue
        pris = set(res.values())
        libres = [r for r in (("envoyee", "presentateur", "invite") if g.get(v) == "f" else ("presentateur", "invite", "envoyee")) if r not in pris]
        if libres:
            journal(f"  {v} et {autres[0]} jouaient tous deux {NOMS[res[v]]} : {v} → {NOMS[libres[0]]} (deux voix = deux personnages)")
            res[v] = libres[0]
    return res

def scinder_voix_dominante(mots, part=0.7):
    """Deux voix trouvées, mais l'une dit plus de 70 % du texte : souvent DEUX personnes jouées par la même voix (« Fierté familiale » :
    les deux copains ont la même voix, seuls les vieux qu'on montre ont une voix aiguë). L'IA relit les phrases de la voix dominante ;
    si c'est un vrai dialogue (pas un monologue), elles sont réparties entre deux personnes, la petite voix devient une 3e personne."""
    import locuteurs
    from collections import Counter
    n = Counter(m["voix"] for m in mots)
    if len(n) != 2 or len(mots) < 30: return mots
    dom, nb = n.most_common(1)[0]
    if nb < part * len(mots): return mots
    sous = [m for m in mots if m["voix"] == dom]
    ia = relire_dialogue(sous, une_voix=True)
    if not ia: return mots
    petite = next(v for v in n if v != dom)
    for m in mots:
        if m["voix"] == petite: m["voix"] = "speaker_x"
    for m in sous: m["voix"] = "speaker_0"
    locuteurs.fil_dialogue(sous, ia)                                       # (modifie les mots de la voix dominante sur place)
    if len({m["voix"] for m in sous}) < 2:                                 # finalement une seule personne : on remet comme avant
        for m in mots: m["voix"] = dom if m["voix"] != "speaker_x" else petite
        return mots
    for m in mots:
        if m["voix"] == "speaker_x": m["voix"] = "speaker_2"
    journal("  voix dominante partagée entre deux personnes (même voix, dialogue) ; l'autre voix devient une 3e personne")
    return mots

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
    import ecoute
    if voix_sig is None:                                                   # plus de crédit ElevenLabs : Demucs, gratuit sur la machine
        v_, c_ = ecoute.demucs(tmp)
        if v_ is not None: voix_sig, chemin_voix = v_, c_
    sig = voix_sig if voix_sig is not None and len(voix_sig) >= len(mono) * 0.9 else mono
    import equipe
    B = equipe.Bulletin()                                                  # l'équipe : chaque poste contrôlé avant le suivant
    mots = equipe.inge_son(transcrire(chemin_voix, mono), B)
    if SOURCE_MOTS[0] != "elevenlabs":
        mots = ecoute.aligner(mots, sig)                                   # chaque mot recalé sur la voix (lèvres, sous-titres)
        __import__("locuteurs").fins_de_phrase(mots)                       # points oubliés par Whisper (« …rouge Mais pourquoi… »)
    if not EVENEMENTS: EVENEMENTS[:] = ecoute.bruits(mono)                 # rires, cris, sirène, aboiement… entendus dans l'original
    try:                                                                   # pyannote (si la clé Hugging Face gratuite est réglée) :
        import locuteurs                                                   # meilleure séparation des voix que la transcription gratuite
        if len({m["voix"] for m in mots}) == 1:                            # NeMo (Modal) d'abord, puis pyannote
            p_ = ecoute.nemo(mots, sig) or locuteurs.pyannote(mots, sig)
            if p_: mots = p_
    except Exception as e: journal(f"  pyannote impossible ({str(e)[:120]})")
    try:                                                                   # voix proches confondues : on les re-sépare par leur empreinte
        import locuteurs; mots = locuteurs.rediariser(mots, sig)
    except Exception as e: journal(f"  re-séparation des voix impossible ({str(e)[:120]})")
    mots = separer_voix(mots, sig)                                         # dernier recours : la hauteur (voix grave / aiguë)
    try:                                                                   # qui parle, mot par mot (la voix ne saute plus d'un perso à l'autre)
        import locuteurs; mots = locuteurs.affiner(mots, sig)
    except Exception as e: journal(f"  vérification mot par mot impossible ({str(e)[:120]})")
    try:                                                                   # casting voix : le son, le texte et l'image votent
        mots = equipe.casting_voix(mots, info.get("_fichier") or "", B, relire_dialogue, scinder_voix_dominante)
    except Exception as e: journal(f"  contrôle du casting des voix impossible ({str(e)[:120]})")
    segs = segments(mots)
    hz = hauteurs(sig, segs)
    emo_voix = ecoute.emotions(sig, segs)                                  # colère, joie, tristesse entendues dans la voix
    journal(f"  {len(segs)} répliques, voix : {hz}")
    audio = {}
    try:                                                                   # le son de la vidéo : voix, débit, musique, bruitages… (banque)
        import analyse_audio
        audio = analyse_audio.analyser(mono, voix_sig, segs, hz, EVENEMENTS)
        journal("  son de la vidéo : " + analyse_audio.texte(audio))
    except Exception as e: journal(f"  analyse du son impossible ({str(e)[:150]})")
    casting, m = _casting_defaut(segs, hz), {}
    try:
        if not __import__("reseau").ia_disponible(): raise RuntimeError("aucune IA disponible (crédits vérifiés au départ)")
        import anthropic
        lignes = "\n".join(f"{k}. {s['voix']}{' (voix sûre)' if voix_sure(s) else ''} ({s['deb']:.1f}–{s['fin']:.1f}) : {s['t']}" for k, s in enumerate(segs))
        vx = "\n".join(f"- {v} : {h or '?'} Hz, {sum(len(s['mots']) for s in segs if s['voix'] == v)} mots" for v, h in hz.items())
        contenu = consigne(vx, lignes)
        if audio: contenu += "\nMesures du son de la vidéo (gratuites) : " + __import__("analyse_audio").texte(audio) + "\n"
        if visuel or cles:                                                 # Claude voit aussi la vidéo d'origine (images clés) et ses mesures
            import analyse_video, banque_visuelle
            import marionnette as M_
            contenu += IMAGES.format(mesures=analyse_video.texte(visuel), banque=banque_visuelle.consigne(), coiffures=", ".join(M_.COIFFURES),
                                     coupes=", ".join(f"{c:.1f} s" for c in (visuel.get("coupes") or [])[:40]) or "aucune coupe repérée")
            o_ = __import__("reseau").ordre_ia(True)
            if cles and "claude" not in o_ and "gemini" not in o_:         # personne pour bien regarder les images : Florence-2 les décrit
                desc = ecoute.decrire(cles[:6])
                if desc: contenu += "\nCe que montrent les images clés (description automatique, en anglais) :\n" + "\n".join(f"- image {k + 1} : {t}" for k, t in enumerate(desc)) + "\n"
            contenu = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(j).decode()}} for j in cles[:6]] \
                      + [{"type": "text", "text": contenu}]
        m = ecrire._appel(__import__('reseau').claude(), None, [{"role": "user", "content": contenu}], _outil(), max_tokens=8000)
        for c in ecrire._liste(m.get("casting")):
            if isinstance(c, dict) and c.get("voix") in hz and c.get("role") in ROLES: casting[c["voix"]] = c["role"]
        if m.get("contexte"): journal(f"  scène reconstituée : {m['contexte']}")
        casting = casting_unique(casting, segs, hz)
    except Exception as e:
        journal(f"  mise en scène automatique impossible ({str(e)[:150]}) : une seule scène, casting par la hauteur des voix")
    journal("  casting : " + ", ".join(f"{v} → {NOMS[r]}" for v, r in casting.items()))
    d = [" ".join(map(str, x)) if isinstance(x, list) else str(x) for x in ecrire._liste(m.get("d"))]   # l'IA gratuite met parfois [["…"]]
    corrige = corriger_textes(segs, [str(x) for x in ecrire._liste(m.get("texte"))])   # sous-titres sans fautes de reconnaissance
    reps = []
    for k, s in enumerate(segs):
        r = {"p": casting.get(s["voix"], "presentateur"), "t": corrige[k], "_deb": round(float(s["deb"]), 3), "_fin": round(float(s["fin"]), 3)}
        if k < len(d) and ecrire._mots_bruts(re.sub(r"\[[^\]]*\]", " ", d[k])) in (ecrire._mots_bruts(s["t"]), ecrire._mots_bruts(corrige[k])): r["d"] = d[k]
        reps.append(r)
    for o in ecrire._liste((m.get("studio") or {}).get("objets") if isinstance(m.get("studio"), dict) else []):   # objets vus dans la vidéo
        try:
            k_o = int(o.get("replique")); nom_o = str(o.get("objet", "")).lower()
            if 0 <= k_o < len(reps) and nom_o in ecrire.OBJETS: reps[k_o]["objet"] = nom_o
        except (AttributeError, TypeError, ValueError): pass
    corr, refus = 0, 0
    for x in ecrire._liste(m.get("roles")):                                # Claude : la bonne personne réplique par réplique (voix proches)
        try:
            k_r = int(x.get("replique"))
            if 0 <= k_r < len(reps) and x.get("role") in ROLES and reps[k_r]["p"] != x["role"]:
                if voix_sure(segs[k_r]): refus += 1; continue              # la voix est reconnue : l'IA (qui lit le texte) ne la déplace pas
                reps[k_r]["p"] = x["role"]; corr += 1
        except (AttributeError, TypeError, ValueError): pass
    if corr: journal(f"  Claude a réattribué {corr} réplique(s) à la bonne personne (voix proches)")
    if refus: journal(f"  {refus} réattribution(s) de l'IA refusée(s) : la voix de ces répliques est reconnue avec certitude")
    ecoute.jeu_entendu(reps, segs, emo_voix, EVENEMENTS)                   # sans indication de l'IA : le jeu entendu dans le son
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
    if isinstance(m.get("studio"), dict):
        P_ = m["studio"].get("personnages")
        if isinstance(P_, list):                                           # l'IA gratuite donne parfois une liste sans les rôles :
            C_ = m["studio"].get("costumes")                               # même ordre que ses costumes (sinon ordre d'apparition)
            ordre = [r for r in (C_ if isinstance(C_, dict) else {}) if r in ROLES] or list(dict.fromkeys(r["p"] for r in reps if r["p"] != "narrateur"))
            m["studio"]["personnages"] = {r: f for r, f in zip(ordre, P_) if isinstance(f, dict)}
        sk["studio"] = m["studio"]                                         # direction artistique de Claude (vérifiée par studio.bible)
        try:
            import studio as _st
            g_v = genre_des_voix(segs, hz); g_r = {}
            for v, r in casting.items(): g_r.setdefault(r, g_v.get(v))
            if _st.accorder_roles(sk, g_r): journal("  descriptions des personnages remises sur les bons rôles (âge, genre de la voix)")
            vus = sk["studio"].get("decors_vus") if isinstance(sk["studio"].get("decors_vus"), dict) else {}
            for sc in sk.get("decoupage") or []:                           # décor trop vague : celui vu dans la vidéo d'origine
                qui = [reps[i]["p"] for i in sc.get("repliques", []) if i < len(reps)]
                v_ = next((vus[r] for r in sorted(set(qui), key=qui.count, reverse=True) if vus.get(r)), None)
                if v_ and len(str(sc.get("decor") or "").split()) < 8: sc["decor"] = re.sub(r"[^\w\s,.'-]", "", str(v_))[:240]
        except Exception as e: journal(f"  accord des rôles impossible ({str(e)[:100]})")
    sk["sources"] = [lien]
    sk["doublage"] = {"piste": piste, "duree": round(duree, 2), "source": lien, "auteur": auteur, "contexte": m.get("contexte", ""),
                      "evenements": [list(e) for e in EVENEMENTS][:60], "visuel": visuel, "audio": audio,
                      "video_origine": info.get("_fichier") or ""}                    # (contrôle qualité : comparaison avec l'original)
    if audio:                                                              # émotions de jeu données par Claude
        from collections import Counter
        audio["emotions"] = dict(Counter(m.lower() for x in d for m in re.findall(r"\[([^\]]{2,25})\]", x)).most_common(8))
    if EVENEMENTS: journal(f"  événements sonores : {', '.join(sorted({e[2] for e in EVENEMENTS}))[:200]}")
    sk["fiche"] = {"note": 0, "decision": "vidéo manuelle (bande son d'une vidéo TikTok)", "decoupage": sk["decoupage"]}
    sk["_monte"] = True                                                    # pas de voix off de titre ni d'accroche rejouée : la bande son est imposée
    # voix de chaque réplique (pour les bouches) et instants des mots, relatifs au début de la réplique
    audios, mots = [], []
    for s in segs:
        a0, a1 = int(s["deb"] * SR), max(int(s["fin"] * SR) + int(0.05 * SR), int(s["deb"] * SR) + int(0.2 * SR))
        audios.append(np.asarray(sig[a0:a1], np.float32))
        mots.append([(x["w"], float(x["s"] - s["deb"]), float(x["e"] - s["deb"])) for x in s["mots"]])
    for r, m_ in zip(sk["repliques"], mots): r["_mots"] = [[w, round(a, 3), round(b, 3)] for w, a, b in m_]   # gardés : « Corriger qui parle »
    try:                                                                   # scripte (cohérence) et monteur (synchronisation)
        equipe.scripte(sk, segs, hz, B); equipe.monteur(sk, duree, B)
    except Exception as e: journal(f"  contrôles de l'équipe impossibles ({str(e)[:120]})")
    sk["equipe"] = B.lignes
    journal(f"  bulletin de l'équipe : {B.resume()}")
    return sk, audios, mots


def depuis_sketch(sk):
    """« Corriger qui parle » (idée 6) : refait le son d'une vidéo TikTok déjà fabriquée, avec les MÊMES répliques (instants gardés
    dans le sketch) : le son d'origine est re-téléchargé et recoupé réplique par réplique. Renvoie (audios, mots) comme preparer."""
    d = sk.get("doublage") or {}
    tmp = tempfile.mkdtemp(); info, piste, mono = telecharger(d.get("source") or (sk.get("sources") or [""])[0], tmp)
    d["piste"] = piste; sk["doublage"] = d
    audios, mots = [], []
    for r in sk["repliques"]:
        deb, fin = float(r.get("_deb", 0)), float(r.get("_fin", 0))
        a0, a1 = int(deb * SR), max(int(fin * SR) + int(0.05 * SR), int(deb * SR) + int(0.2 * SR))
        audios.append(np.asarray(mono[a0:a1], np.float32))
        mots.append([(str(w), float(a), float(b)) for w, a, b in r["_mots"]] if r.get("_mots") else None)
    journal(f"  son d'origine repris pour {len(audios)} répliques (mêmes instants)")
    return audios, mots

def credit(sk):
    d = sk.get("doublage") or {}
    return f"🎧 Son original : @{d['auteur']}" if d.get("auteur") else "🎧 Son original : TikTok"   # jamais de lien (choix de l'auteur)
