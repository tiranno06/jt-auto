"""Essai VIDÉO du décor « peinture semi-réaliste » (demande de l'auteur, 1er novembre 2026), sans rien brancher dans le robot :
le début de la vidéo « Maurice » (mêmes répliques, même son, mêmes personnages croquis), rendu par le vrai moteur (cartoon.rendre)
devant le salon peint par l'IA, sans aquarelle ni petits détails animés dessinés.
Usage : python maquettes/photo/essai_video.py <vidéo d'origine .mp4 (pour le son)> <sortie .mp4> [nombre de répliques]"""
import json, os, subprocess, sys, tempfile
import numpy as np, cv2
D = os.path.dirname(os.path.abspath(__file__)); M = os.path.join(D, "..", "..", "moteur")
sys.path.insert(0, M)
os.environ.update(DECOR_CROQUIS="0", DECOR_VIVANT="0", SAISON="0", DESSIN_PARTAGE="0", PYTHONHASHSEED="0", IPS=os.environ.get("IPS", "30"))
import doublage, cartoon

src, sortie = sys.argv[1], sys.argv[2]; n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
sk = json.load(open(os.path.join(D, "..", "..", "episodes", "sketchs", "2026-11-01_12h20_emission.json"), encoding="utf-8"))
sk["repliques"] = sk["repliques"][:n]; sk["decoupage"] = [dict(sk["decoupage"][0], repliques=list(range(n)))]
sk["repliques"][-1]["chute"] = True
if os.environ.get("CHAT", "1") != "0":                                     # Maurice en chat, comme la vidéo postée
    sk.setdefault("studio", {}).setdefault("personnages", {}).setdefault("presentateur", {})["espece"] = "chat"
wav = os.path.join(tempfile.mkdtemp(), "son.wav")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-ac", "1", "-ar", str(doublage.SR), wav], check=True)
import soundfile as sf
mono, _ = sf.read(wav, dtype="float32")
fin = float(sk["repliques"][-1]["_fin"]) + 0.6                         # bande son d'origine coupée après la dernière réplique gardée
piste = os.path.join(os.path.dirname(wav), "piste.wav")                # piste d'origine : stéréo au bon échantillonnage (comme le robot)
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-t", f"{fin:.2f}", "-ac", "2", "-ar", str(cartoon.SRM), "-c:a", "pcm_s16le", piste], check=True)
sk["doublage"]["piste"] = piste; sk["doublage"]["duree"] = fin; sk["doublage"].pop("video_origine", None)
audios, mots = [], []
for r in sk["repliques"]:
    a0 = int(float(r["_deb"]) * doublage.SR); a1 = max(int(float(r["_fin"]) * doublage.SR) + int(0.05 * doublage.SR), a0 + int(0.2 * doublage.SR))
    audios.append(np.asarray(mono[a0:a1], np.float32))
    mots.append([(str(w), float(a), float(b)) for w, a, b in r["_mots"]] if r.get("_mots") else None)
fond = cv2.cvtColor(cv2.imread(os.path.join(D, "peints", "peint_0.png")), cv2.COLOR_BGR2RGB)
h, w = fond.shape[:2]; c = max(0, int(w - h * 1080 / 1920) // 2)
fond = cv2.resize(fond[:, c:w - c], (1080, 1920), interpolation=cv2.INTER_LANCZOS4)
duree = cartoon.rendre(sk, sortie, audios, mots=mots, decors={0: fond}, mini=True)
print(f"vidéo d'essai : {sortie} ({duree:.1f} s)")
