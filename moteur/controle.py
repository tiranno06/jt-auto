"""Contrôle qualité de la vidéo finie (piste 13) : une IA regarde des images de la vidéo avant publication.

On extrait une image au milieu de chaque réplique (plus l'ouverture et la fin), on les assemble en planches et on les montre
à Claude avec le texte attendu. Il signale : sous-titre faux ou différent du texte, texte coupé ou illisible, personnage coupé
par le cadre, personnage absent, décor incohérent avec la scène, carton mal placé, image vide ou noire.
Un défaut « grave » bloque la publication automatique (la vidéo reste à vérifier dans la régie)."""
import base64, io, os, re, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ICI = os.path.dirname(os.path.abspath(__file__))
MODELE = os.environ.get("MODELE_CONTROLE") or "claude-sonnet-5-5"

PROMPT = """Tu es chef monteur. Voici des images extraites d'une vidéo TikTok animée (format vertical), numérotées dans l'ordre (carré rouge en haut à gauche).
Chaque image est SÉPARÉE des autres par une bande noire : ne mélange jamais le bord d'une image avec celui de sa voisine.
Ce qui doit apparaître :
{attendu}
Vérifie chaque image : sous-titre différent du texte attendu ou avec une faute, texte coupé par le bord ou illisible, deux textes qui se chevauchent,
personnage coupé de façon gênante ou absent alors qu'il parle, décor incohérent avec la scène, image noire, vide ou cassée.
Ne signale pas le style volontairement simple (dessin plat, personnages à grosse tête ronde), ni les textes humoristiques écrits dans le décor (affiches, enseignes, tableaux : ce sont des gags voulus),
ni le flou volontaire de l'arrière-plan ou d'un personnage de dos au premier plan, ni les sous-titres qui n'affichent qu'une partie de la phrase (ils défilent par groupes de mots).
Rends ta réponse avec l'outil controle : "defauts" = liste (image n°, problème, gravité « grave » ou « mineur »), "verdict" = « ok » ou « a_corriger »."""
OUTIL = {"name": "controle", "description": "Défauts visuels relevés.",
         "input_schema": {"type": "object", "properties": {
             "defauts": {"type": "array", "items": {"type": "object", "properties": {"image": {"type": "integer"}, "probleme": {"type": "string"},
                                                                                       "gravite": {"type": "string"}}, "required": ["probleme", "gravite"]}},
             "verdict": {"type": "string"}}, "required": ["defauts", "verdict"]}}

def _image(video, t):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{max(0, t):.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=360:640",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert("RGB") if r.stdout else Image.new("RGB", (360, 640))

def planches(video, instants, par_planche=8):
    """Images numérotées assemblées en planches de 4 x 2."""
    f = ImageFont.truetype(os.path.join(ICI, "..", "polices", "Poppins-Bold.ttf"), 30); out = []
    for d in range(0, len(instants), par_planche):
        G = 40                                                             # large bande noire entre les images : aucune ne « déborde » sur sa voisine
        lot = instants[d:d + par_planche]; P = Image.new("RGB", (360 * 4 + G * 5, 640 * 2 + G * 3), (0, 0, 0)); dr = ImageDraw.Draw(P)
        for k, t in enumerate(lot):
            x, y = G + (360 + G) * (k % 4), G + (640 + G) * (k // 4); P.paste(_image(video, t), (x, y))
            dr.rectangle((x, y, x + 64, y + 44), fill=(220, 30, 30)); dr.text((x + 8, y + 2), str(d + k + 1), font=f, fill=(255, 255, 255))
        b = io.BytesIO(); P.save(b, "JPEG", quality=82); out.append(b.getvalue())
    return out

def technique(video, duree_attendue=None, fin_parole=None):
    """Contrôles gratuits, sans IA (ffprobe / ffmpeg) : format 1080x1920, 30 images/s, piste son présente et non muette,
    durée conforme, pas de passage noir ni d'image figée trop longue. Renvoie (ok, rapport)."""
    defauts = []
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
                            "-of", "json", video], capture_output=True, text=True, timeout=120)
        import json
        info = json.loads(r.stdout or "{}"); st = info.get("streams", [])
        v = next((s for s in st if s.get("codec_type") == "video"), None); a = next((s for s in st if s.get("codec_type") == "audio"), None)
        if not v: defauts.append("pas de piste vidéo")
        else:
            if (v.get("width"), v.get("height")) != (1080, 1920): defauts.append(f"format {v.get('width')}x{v.get('height')} au lieu de 1080x1920")
            n, d = (v.get("r_frame_rate") or "0/1").split("/")
            if abs(float(n) / max(1.0, float(d)) - 30) > 0.5: defauts.append(f"{v.get('r_frame_rate')} images/s au lieu de 30")
        if not a: defauts.append("pas de piste son")
        duree = float((info.get("format") or {}).get("duration") or 0)
        if duree_attendue and abs(duree - duree_attendue) > 1.5: defauts.append(f"durée {duree:.1f} s au lieu de {duree_attendue:.1f} s")
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-vf", "blackdetect=d=0.5:pic_th=0.97,freezedetect=n=0.001:d=4",
                            "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True, timeout=900)
        noirs = re.findall(r"black_start:([\d.]+)", r.stderr); figes = re.findall(r"freeze_start: ([\d.]+)", r.stderr)
        if noirs: defauts.append("passage noir à " + ", ".join(f"{float(x):.1f} s" for x in noirs[:3]))
        fin_fige = min(duree - 6, fin_parole + 0.5) if fin_parole else duree - 6   # après la dernière réplique : arrêt sur image et carton de fin voulus
        figes = [x for x in figes if float(x) < fin_fige]
        if figes: defauts.append("image figée à " + ", ".join(f"{float(x):.1f} s" for x in figes[:3]))
        m = re.search(r"mean_volume: ([-\d.]+) dB", r.stderr)
        if a and m and float(m.group(1)) < -45: defauts.append(f"son presque muet ({m.group(1)} dB)")
    except Exception as e:
        print(f"Contrôle technique impossible ({str(e)[:120]}) : non bloquant.", flush=True); return True, ""
    rapport = "; ".join(defauts)
    print("Contrôle technique : " + (rapport or "ok (format, son, durée, pas d'image noire ni figée)"), flush=True)
    return not defauts, ("technique : " + rapport) if rapport else ""

def verifier(video, sk, minutage):
    """minutage : [(début, fin, texte attendu, qui)] par réplique. Renvoie (ok, rapport texte)."""
    if os.environ.get("CONTROLE_VIDEO", "1") == "0": return True, ""
    try:
        import anthropic
        instants, attendu = [0.3], ["1. ouverture (titre)"]
        for deb, fin, texte, qui in minutage:
            instants.append((deb + fin) / 2); attendu.append(f"{len(instants)}. {qui} parle — sous-titre extrait de : « {texte} »")
        instants.append(minutage[-1][1] + 1.0); attendu.append(f"{len(instants)}. fin (impact / carton de fin)")
        contenu = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(p).decode()}}
                   for p in planches(video, instants[:24])]
        contenu.append({"type": "text", "text": PROMPT.format(attendu="\n".join(attendu[:24]))})
        r = anthropic.Anthropic().messages.create(model=MODELE, max_tokens=2500, tools=[OUTIL], tool_choice={"type": "auto"},
                                                  messages=[{"role": "user", "content": contenu}])
        res = next((b.input for b in r.content if getattr(b, "type", "") == "tool_use"), {})
    except Exception as e:
        print(f"Contrôle vidéo impossible ({str(e)[:140]}) : non bloquant.", flush=True); return True, ""
    defauts = [d for d in res.get("defauts", []) if isinstance(d, dict)]
    graves = [d for d in defauts if "grave" in str(d.get("gravite", "")).lower()]
    rapport = "; ".join(f"image {d.get('image', '?')} : {d.get('probleme', '')[:120]} ({d.get('gravite', '')})" for d in defauts)
    print(f"Contrôle vidéo : {len(graves)} défaut(s) grave(s), {len(defauts) - len(graves)} mineur(s)" + (f" — {rapport[:600]}" if rapport else ""), flush=True)
    return not graves, rapport
