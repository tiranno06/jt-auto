"""Essai des outils d'écoute sur Modal (workflow modal.yml) : NeMo sur un dialogue à deux voix connues, Florence-2 sur un décor."""
import glob, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecoute

d = tempfile.mkdtemp(); f = os.path.join(d, "dial.wav")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "voix/presentateur.wav", "-i", "voix/invite.wav", "-i", "voix/presentateur.wav",
                "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1[a]", "-map", "[a]", "-ac", "1", "-ar", "22050", f], check=True)
sig = ecoute._lire(f)
n = len(sig) / ecoute.SR
mots = [{"w": "mot", "s": t, "e": t + 0.4, "voix": "speaker_0"} for t in [x * 0.5 for x in range(int(n * 2) - 1)]]
r = ecoute.nemo(mots, sig)
if r: print("NeMo :", [(round(m["s"], 1), m["voix"]) for m in r[::6]])
else: print("NeMo : aucun résultat")
im = sorted(glob.glob("decors/*.jpg"))[:2]
print("Florence-2 :", ecoute.decrire([open(x, "rb").read() for x in im]))
