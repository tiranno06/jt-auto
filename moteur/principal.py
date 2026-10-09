"""Une exécution du robot = une émission.
1. casting vocal (seulement la première fois)
2. actualité politique des dernières 36 h (RSS)
3. sketch écrit par Claude (un seul sujet, puis passe de « script doctor »)
4. voix (Chatterbox sur Modal, sinon Piper)
5. plan gag IA (Wan 2.2 sur Modal, facultatif)
6. rendu studio (moteur/jt.py) ; la publication TikTok est faite ensuite par moteur/publier.py (étape du workflow)"""
import json, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(RACINE)
import actu, ecrire, voix, jt

SR = 22050

def resserrer(audios, sk, cible=None):
    """Durée maximale (réglage « courte » : 30 s) : si les voix dépassent, on accélère légèrement le débit (jusqu'à +18 %)."""
    import subprocess, tempfile, wave, numpy as np
    cible = cible or {"courte": 29.0, "normale": 40.0, "longue": 55.0}.get(ecrire.LONGUEUR, 29.0)
    total = sum(len(a) for a in audios) / SR + sum(0.45 if r.get("chute") else 0.06 for r in sk["repliques"]) + sum(r.get("attente", 0) for r in sk["repliques"]) + 1.0
    if total <= cible: return audios
    f = min(1.18, total / cible); print(f"Durée estimée {total:.1f} s : débit accéléré ×{f:.2f}", flush=True)
    sortie, tmp = [], tempfile.mkdtemp()
    for i, a in enumerate(audios):
        with wave.open(f"{tmp}/{i}.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmp}/{i}.wav", "-af", f"atempo={f:.3f}", f"{tmp}/{i}b.wav"], check=True)
        with wave.open(f"{tmp}/{i}b.wav") as w: sortie.append(np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768)
    return sortie

def lire(p, d):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d

def main():
    historique = lire("episodes/historique.json", [])
    modal_ok = bool(os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET"))
    if modal_ok:
        try:
            import casting
            casting.casting()
        except Exception as e:
            print(f"Casting impossible ({e}) : on continuera avec la voix de secours.", flush=True)
    deja = {l for h in historique for l in h.get("sources", [])}
    mots_recents = {m for h in historique[-3:] for m in h.get("mots", [])}
    titres, info = actu.sujet_du_jour(deja_vus=deja, mots_recents=mots_recents)
    if titres:
        print(f"Sujet du jour ({info}) : « {titres[0]['titre']} »", flush=True)
    else:
        print(f"Pas de sujet dominant ({info}) : titres politiques récents", flush=True)
        titres = actu.titres_recents(deja_vus=deja)
    if len(titres) < 1:
        print("Pas assez d'actualité exploitable aujourd'hui : pas d'émission."); return
    sk = ecrire.ecrire_sketch(titres)
    print(f"Sketch : « {sk['sujet']} », {len(sk['repliques'])} répliques", flush=True)
    audios, moteur = voix.generer(sk["repliques"], jt.VOIX)
    print(f"Voix : {moteur}", flush=True)
    audios = resserrer(audios, sk)
    jour = datetime.date.today().isoformat()
    pris = {h.get("fichier") for h in historique}; n = 1; base = f"sortie/{jour}_emission"
    while os.path.basename(base) + ".mp4" in pris: n += 1; base = f"sortie/{jour}_emission{n}"   # plusieurs émissions le même jour
    os.makedirs("sortie", exist_ok=True)
    gag = None
    if modal_ok and sk.get("gag") and os.environ.get("PLAN_GAG", "1") != "0":
        import video_modal
        i = sk["gag"]["replique"]
        gag = video_modal.generer(sk["gag"]["prompt"], len(audios[i]) / SR + 0.6, base + "_gag.mp4", graine=len(historique))
        print(f"Plan gag IA : {'oui' if gag else 'non'}", flush=True)
    duree = jt.rendre(sk, base + ".mp4", audios, gag=gag)
    credit = ("Voix : Multilingual LibriSpeech (CC BY 4.0), transformées, synthèse Chatterbox."
              if moteur == "chatterbox" else "Voix : Piper / SIWIS (CC BY 4.0).")
    if gag: credit += " Plan « reconstitution » généré avec Wan 2.2."
    legende = f"{sk['legende']}\n\n" + " ".join("#" + h for h in sk["hashtags"]) + f"\n\nContenu généré par IA. {credit}"
    open(base + ".txt", "w", encoding="utf-8").write(legende + "\n\nSources :\n" + "\n".join(sk["sources"]) + "\n")
    os.makedirs("episodes", exist_ok=True)
    json.dump(sk, open(f"episodes/{jour}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    historique.append(dict(date=jour, titre=sk["sujet"], sources=sk["sources"], mots=sorted(actu._mots(" ".join(t["titre"] for t in titres)))[:40], voix=moteur, gag=bool(gag), duree=round(duree, 1),
                           fichier=os.path.basename(base) + ".mp4", tag=f"emissions-{jour[:7]}", legende=legende, publie=None))
    json.dump(historique[-200:], open("episodes/historique.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sortie = os.environ.get("GITHUB_OUTPUT")
    if sortie:
        with open(sortie, "a") as f:
            f.write(f"video={base}.mp4\nlegende={base}.txt\nnom={os.path.basename(base)}.mp4\nmois={jour[:7]}\ntitre={sk['sujet']}\n")
    print(f"OK : {base}.mp4 ({duree:.0f} s)")

if __name__ == "__main__":
    main()
