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
Ne signale pas le style volontairement simple (dessin plat, bonshommes blancs) ni les sous-titres qui n'affichent qu'une partie de la phrase (ils défilent par groupes de mots).
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
