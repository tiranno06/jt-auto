"""Mode réaliste (option de la régie) : le sketch est filmé par une IA vidéo (Veo 3.1, via l'API ElevenLabs), voix comprises.

Le sketch écrit par le robot est découpé en plans de 4 à 8 secondes (limite de Veo). Chaque plan est décrit en anglais
(lieu, personnages toujours décrits de la même façon pour qu'on les reconnaisse d'un plan à l'autre, cadrage) avec les
répliques en français à faire jouer. Les plans sont collés, puis on ajoute le titre, les sous-titres (minutés par Whisper
sur le son réel), le filigrane et la signature Petits.Dramas.

Coût : chaque seconde de vidéo consomme des crédits ElevenLabs (affiché dans l'application ElevenLabs avant de générer).
rendre(sk, sortie, mini) -> durée (s) ; lève une exception si la génération échoue (le robot repasse alors en dessin animé)."""
import json, os, re, subprocess, tempfile, time, urllib.request
import numpy as np, cv2

ICI = os.path.dirname(os.path.abspath(__file__))
MODELE = os.environ.get("REALISTE_MODELE") or "veo-3.1-fast-generate-001"
RESOLUTION = os.environ.get("REALISTE_RESOLUTION") or "720p"
W, H, FPS = 1080, 1920, 30

PERSONNAGES = {
    "presentateur": ("JOJO", "a French man in his early thirties, stocky, short messy brown hair, three-day beard, orange knit beanie, grey hoodie"),
    "invite": ("KÉVIN", "a skinny French man in his early twenties, backwards blue baseball cap, white t-shirt, gold chain, goofy grin"),
    "envoyee": ("LILA", "a French woman in her late twenties, brown hair in a messy bun with a pink bow, beige trench coat, sharp eyes"),
}
ROLE_NOM = {"presentateur": "Jojo", "invite": "Kévin", "envoyee": "Lila"}

def _eleven(chemin, corps=None, timeout=120):
    req = urllib.request.Request("https://api.elevenlabs.io" + chemin, data=json.dumps(corps).encode() if corps is not None else None,
                                 headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
                                 method="POST" if corps is not None else "GET")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read() or b"{}")

def plans(sk, max_mots=20):
    """Découpe en plans : répliques consécutives d'une même scène, au plus ~20 mots (≈ 8 s de parole) par plan."""
    dec = sk.get("decoupage") or []; scene_de = {i: k for k, sc in enumerate(dec) for i in sc.get("repliques", [])}
    out, cur, n = [], [], 0
    for i, r in enumerate(sk["repliques"]):
        if r["p"] not in PERSONNAGES or r.get("teaser"): continue
        m = len(r["t"].split()); sc = scene_de.get(i, cur[-1][1] if cur else 0)
        if cur and (n + m > max_mots or sc != cur[-1][1]): out.append(cur); cur, n = [], 0
        cur.append((r, sc)); n += m
    if cur: out.append(cur)
    for g in out:                                                          # tous les personnages de la scène sont à l'image, même muets
        dans = list(dict.fromkeys(r["p"] for i, r in enumerate(sk["repliques"]) if r["p"] in PERSONNAGES and scene_de.get(i, 0) == g[0][1]))
        g.insert(0, ("_scene", dans))
    return out, dec

def _emotion(d):
    t = " ".join(re.findall(r"\[([^\]]{1,30})\]", d or ""))
    return t or "natural"

def prompt_plan(groupe, dec, k, total):
    roles = groupe[0][1]; groupe = groupe[1:]
    sc = groupe[0][1]; lieu = (dec[sc].get("decor") if sc < len(dec) else "") or "a small Paris apartment"
    persos = " ".join(f"{PERSONNAGES[r][0]} is {PERSONNAGES[r][1]}." for r in roles)
    lignes = " ".join(f'{PERSONNAGES[r["p"]][0]} ({_emotion(r.get("d"))}) says in French: « {r["t"]} »' for r, _ in groupe)
    fin = " Final beat: a frozen comedic reaction shot." if k == total - 1 else ""
    return (f"Photorealistic vertical 9:16 French sitcom scene, cinematic, natural light, handheld medium shots and close-ups, realistic faces and lip sync. "
            f"Location: {lieu}. {persos} They speak natural French with Parisian accents, comedic timing, expressive faces. {lignes}{fin} "
            f"No subtitles, no on-screen text, no music, no logos.")

def _attendre(gid, delai=900):
    t0 = time.time()
    while time.time() - t0 < delai:
        r = _eleven(f"/v1/flows/video/{gid}")
        if r.get("status") == "completed": return r["content_url"]
        if r.get("status") == "failed": raise RuntimeError(f"Veo : {r.get('failure_reason')} {r.get('error_message', '')[:200]}")
        time.sleep(10)
    raise RuntimeError("Veo : délai dépassé")

def generer_plans(liste, dec, graine, tmp):
    fichiers = []; ids = []
    for k, g in enumerate(liste):
        mots = sum(len(r["t"].split()) for r, _ in g[1:]); duree = 4 if mots <= 7 else 6 if mots <= 12 else 8
        corps = {"model_id": MODELE, "prompt": prompt_plan(g, dec, k, len(liste)), "aspect_ratio": "9:16", "duration_secs": duree,
                 "resolution": RESOLUTION, "generate_audio": True, "seed": graine,
                 "negative_prompt": "cartoon, animation, subtitles, captions, text, watermark, extra people, deformed faces"}
        rep = _eleven("/v1/flows/video", corps); ids.append(rep["id"])
        print(f"  plan {k + 1}/{len(liste)} demandé ({duree} s) : {rep['id']}", flush=True)
    for k, gid in enumerate(ids):                                          # les plans se calculent en parallèle chez ElevenLabs
        url = _attendre(gid); f = f"{tmp}/plan{k}.mp4"
        urllib.request.urlretrieve(url, f); fichiers.append(f); print(f"  plan {k + 1} reçu", flush=True)
    return fichiers

def rendre(sk, sortie, mini=False):
    import jt, marque, voix_banque
    tmp = tempfile.mkdtemp(); liste, dec = plans(sk)
    if not liste: raise RuntimeError("aucune réplique à filmer")
    fichiers = generer_plans(liste, dec, graine=abs(hash(sk.get("sujet", ""))) % 100000, tmp=tmp)
    # assemblage au format 1080x1920, 30 i/s, son uniformisé
    liste_txt = f"{tmp}/liste.txt"
    norm = []
    for k, f in enumerate(fichiers):
        g = f"{tmp}/n{k}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f, "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
                        "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", g], check=True); norm.append(g)
    open(liste_txt, "w").write("".join(f"file '{g}'\n" for g in norm))
    brut = f"{tmp}/brut.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", liste_txt, "-c", "copy", brut], check=True)
    # sous-titres calés sur le son réel (Whisper)
    son = f"{tmp}/son.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", brut, "-ac", "1", "-ar", str(voix_banque.SR), son], check=True)
    import wave
    with wave.open(son) as w: a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    ecoute = (voix_banque.ecouter([a]) or [None])[0] or {}
    mots = ecoute.get("mots") or []
    groupes, cur = [], []
    for m in mots:                                                         # groupes de 3 ou 4 mots, coupés à la ponctuation
        cur.append(m)
        if len(cur) >= 4 or re.search(r"[.!?,…]$", m[0]): groupes.append((" ".join(x[0] for x in cur), cur[0][1], cur[-1][2])); cur = []
    if cur: groupes.append((" ".join(x[0] for x in cur), cur[0][1], cur[-1][2]))
    duree = len(a) / voix_banque.SR
    titre = None
    if sk.get("titre_accroche"):
        import cartoon; titre = cartoon.titre(sk["titre_accroche"])
    fil = marque.filigrane(52); fin = marque.signature(W, H, sk.get("suite") or "Abonne-toi !")
    total = duree + 1.3
    cap = cv2.VideoCapture(brut)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", brut, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-af", "apad,loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", "-movflags", "+faststart", sortie],
                          stdin=subprocess.PIPE)
    for fi in range(int(total * FPS)):
        tm = fi / FPS
        if tm < duree:
            ok, img = cap.read()
            fr = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) if ok else np.zeros((H, W, 3), np.float32)
            jt.poser(fr, fil, 28, 118)
            if titre is not None and tm < 3.5: jt.poser(fr, titre, (W - titre.shape[1]) / 2, 190)
            g = next((x for x in groupes if x[1] <= tm < x[2] + 0.15), None)
            if g:
                c = jt.carton(g[0]); jt.poser(fr, c, (W - c.shape[1]) / 2, 1700 - c.shape[0] / 2)
            ff.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
        else:
            ff.stdin.write(fin.tobytes())
    ff.stdin.close(); ff.wait(); cap.release()
    print(f"Mode réaliste : {len(fichiers)} plans, {total:.1f} s", flush=True)
    return total
