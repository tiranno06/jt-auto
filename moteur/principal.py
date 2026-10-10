"""Une exécution du robot = une émission.
1. casting vocal (seulement la première fois)
2. actualité politique des dernières 36 h (RSS)
3. sketch écrit par Claude (un seul sujet, puis passe de « script doctor »)
4. voix (Chatterbox sur Modal, sinon Piper)
5. plan gag IA (Wan 2.2 sur Modal, facultatif)
6. rendu studio (moteur/jt.py) ; la publication TikTok est faite ensuite par moteur/publier.py (étape du workflow)"""
import json, os, re, sys, datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(RACINE)
from programme import format_du_jour

_hist = json.load(open("episodes/historique.json", encoding="utf-8")) if os.path.exists("episodes/historique.json") else []
AUTO = os.environ.get("EVENEMENT") == "schedule"                         # fabrication déclenchée par le planning (pas un bouton)
if AUTO:                                                                  # nouvelle vérification au démarrage : évite un doublon si deux réveils se suivent
    import planning
    _go, _raison = planning.decision()
    if not _go: print(f"Planning : rien à faire ({_raison})"); sys.exit(0)
THEME = (os.environ.get("THEME") or "").strip()[:2000]                 # création manuelle depuis l'onglet « Manuel » de la régie
REFAIRE = (os.environ.get("REFAIRE") or "").strip()                      # « fichier.mp4|texte|voix|decors » : bouton Refaire de la régie
ANCIEN, SK_ANCIEN = None, None
if REFAIRE:
    _f, _, _mode = REFAIRE.partition("|"); _mode = _mode or "texte"
    ANCIEN = next((h for h in _hist if h.get("fichier") == _f), None)
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "sketchs", _f + ".json")
    SK_ANCIEN = json.load(open(_p, encoding="utf-8")) if os.path.exists(_p) else None
    if ANCIEN: os.environ["FORMAT"] = ANCIEN.get("format") if ANCIEN.get("format") in ("mini", "libre", "actu") else "mini"
    if _mode in ("voix", "decors") and SK_ANCIEN is None:
        print("Sketch d'origine non conservé (vidéo plus ancienne) : on refait une nouvelle version du texte.", flush=True); _mode = "texte"
    REFAIRE_MODE = _mode
    if ANCIEN and _mode == "texte" and not THEME:                        # nouvelle version : même sujet, écrit à neuf
        THEME = ((ANCIEN.get("titre_affiche") or "") + " " + (ANCIEN.get("titre") or "")).strip() + " — " + (ANCIEN.get("accroche") or "")
else:
    REFAIRE_MODE = ""
if THEME and (os.environ.get("FORMAT") or "") not in ("mini", "libre"): os.environ["FORMAT"] = "mini"
os.environ["FORMAT"] = FORMAT = format_du_jour(os.environ.get("FORMAT"), _hist)
if FORMAT == "mini": os.environ["LONGUEUR"] = "eclair"                    # gag éclair : ~15 s
elif FORMAT == "libre": os.environ["LONGUEUR"] = "pro"                    # sketch long : 60 à 90 s (plus d'une minute garantie au montage)
import actu, ecrire, voix, jt, serie, stats

SR = 22050

def resserrer(audios, sk, cible=None):
    """Durée maximale (réglage « courte » : 30 s) : si les voix dépassent, on accélère légèrement le débit (jusqu'à +18 %)."""
    import subprocess, tempfile, wave, numpy as np
    if ecrire.LONGUEUR == "monetisable": return audios                    # format long : jamais accéléré
    cible = cible or {"eclair": 23.0, "pro": 86.0, "courte": 25.0, "normale": 35.0, "longue": 50.0}.get(ecrire.LONGUEUR, 86.0)
    total = sum(len(a) for a in audios) / SR + sum(0.45 if r.get("chute") else 0.06 for r in sk["repliques"]) + sum(r.get("attente", 0) for r in sk["repliques"]) + 1.0
    if total <= cible: return audios
    f = min(1.06, total / cible)                                          # au-delà, les voix deviennent difficiles à comprendre; print(f"Durée estimée {total:.1f} s : débit accéléré ×{f:.2f}", flush=True)
    sortie, tmp = [], tempfile.mkdtemp()
    for i, a in enumerate(audios):
        with wave.open(f"{tmp}/{i}.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmp}/{i}.wav", "-af", f"atempo={f:.3f}", f"{tmp}/{i}b.wav"], check=True)
        with wave.open(f"{tmp}/{i}b.wav") as w: sortie.append(np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768)
    return sortie

GPU = {"s": 0.0}
try: SEUIL_PUB = float(os.environ.get("SEUIL_PUBLICATION") or 80)        # note minimale pour la publication automatique (régie)
except ValueError: SEUIL_PUB = 80.0                                                          # secondes de GPU Modal (décors)

def couts():
    """Dépenses de cette vidéo : Claude (dollars, calculés sur les jetons), ElevenLabs (caractères = crédits), GPU Modal (secondes)."""
    try:
        import voix_banque; car = voix_banque.CARACTERES["elevenlabs"]
    except Exception: car = 0
    return {"claude_usd": round(ecrire.USAGE.get("cout", 0.0), 3), "claude_jetons": ecrire.USAGE["entree"] + ecrire.USAGE["sortie"],
            "cache_lu": ecrire.USAGE.get("cache_lu", 0), "eleven_caracteres": car, "gpu_s": round(GPU["s"])}

def decaler(sk, pos):
    """Une réplique a été insérée en `pos` : on décale les indices du découpage et du plan gag."""
    for sc in sk.get("decoupage") or []: sc["repliques"] = [i + 1 if i >= pos else i for i in sc.get("repliques", [])]
    if sk.get("gag") and sk["gag"]["replique"] >= pos: sk["gag"]["replique"] += 1

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
    mots_recents = {m for h in historique[-5:] for m in h.get("mots", [])}
    depuis = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
    sujets_recents = [h["empreinte"] if h.get("empreinte") else
                      sorted(actu.empreinte(" ".join([h.get("titre", ""), h.get("accroche", "")])))
                      for h in historique if h.get("date", "") >= depuis]
    fmt = FORMAT                                                           # résolu au démarrage (cycle 3 + 1 par défaut)
    libre = fmt in ("libre", "mini")
    print(f"Type de vidéo : {'gag éclair (~15 s)' if fmt == 'mini' else 'sketch long (+1 min)' if libre else 'JT actu du jour'}", flush=True)
    recents = [f"{h.get('titre', '')} : {h.get('accroche', '')}" for h in historique[-10:]]
    # 1. recherche : sujets candidats (articles des dernières 24 h, regroupés par sujet et classés par reprise médiatique)
    script = None
    if THEME:                                                              # vidéo manuelle : le thème (ou le script) tapé dans la régie
        mode_script = THEME.startswith("SCRIPT::"); texte = THEME.split("::", 1)[1].strip() if "::" in THEME[:12] else THEME
        print(f"Vidéo manuelle ({'script' if mode_script else 'idée'}) : « {texte[:200]} »", flush=True)
        if mode_script: script = texte
        candidats = [([{"titre": texte.splitlines()[0][:120], "resume": texte[:1500], "lien": "", "date": None, "source": "manuel"}], "manuel")]
    elif libre and not os.environ.get("SKETCH_TEST", "").strip():
        try: candidats = [(c, "idée") for c in ecrire.idees_libres(recents=[f"{h.get('titre', '')} : {h.get('accroche', '')}" for h in historique[-30:]],
                                                                    consignes=stats.pour_idees())]
        except Exception as e:
            print(f"Idées de sketch impossibles : {e}", flush=True); raise
        for k, (sel, _) in enumerate(candidats): print(f"Idée {k} : « {sel[0]['titre'][:110]} »", flush=True)
    else:
      try:
        candidats = actu.candidats_du_jour(deja_vus=deja, mots_recents=mots_recents, n=6, sujets_recents=sujets_recents)
      except Exception as e:
        print(f"Recherche d'actualité en erreur : {e}", flush=True); candidats = []
      for k, (sel, info) in enumerate(candidats):
        print(f"Candidat {k} ({info}) : « {sel[0]['titre'][:110]} »", flush=True)
    if not candidats and not libre:
        print("Aucun sujet repris par plusieurs médias : repli sur les titres politiques récents.", flush=True)
        try: t = actu.titres_recents(deja_vus=deja)
        except Exception as e: print(f"Repli impossible : {e}", flush=True); t = []
        candidats = [(t, "titres récents")] if t else []
    if not candidats:
        print("Aucune idée de sketch obtenue : pas d'émission." if libre else
              "Recherche d'actualité impossible (flux indisponibles ou vides) : pas d'émission aujourd'hui.", flush=True); return
    titres = candidats[0][0]
    recents = [f"{h.get('titre', '')} : {h.get('accroche', '')}" for h in historique[-10:]]
    from zoneinfo import ZoneInfo
    dimanche = datetime.datetime.now(ZoneInfo("Europe/Paris")).weekday() == 6 and os.environ.get("INFOS_DEMAIN", "1") != "0"
    gags = [h.get("running_gag") for h in historique[-15:] if h.get("running_gag")]
    test = os.environ.get("SKETCH_TEST", "").strip()
    if REFAIRE_MODE in ("voix", "decors"):                                 # mêmes répliques : on refait seulement les voix / les décors
        sk = SK_ANCIEN; sk["_monte"] = True
        print(f"Refaire ({REFAIRE_MODE}) : « {sk.get('sujet')} », mêmes répliques", flush=True)
    elif script:                                                           # script tapé : les répliques restent mot pour mot
        sk = ecrire.mettre_en_scene(script)
    elif test:                                                             # sketch écrit à la main (essai d'un style)
        ecrire.NB_MAX = 20
        sk = ecrire.valider(json.load(open(test, encoding="utf-8")), set(), libre)
        print(f"Sketch d'essai : {test}", flush=True)
    else:
        sk = ecrire.ecrire_sketch([c[0] for c in candidats], gags=gags, special=dimanche and not libre, recents=recents, libre=libre,
                                  serie=serie.contexte() if (libre and not THEME) else "", stats=stats.pour_auteur() if libre else "")
        print(f"Moteur humoristique : {ecrire.USAGE['appels']} appels Claude, {ecrire.USAGE['entree']} jetons lus, {ecrire.USAGE['sortie']} jetons écrits, {ecrire.USAGE['recherches_web']} recherche(s) web", flush=True)
        titres = next((c[0] for c in candidats if c[0][0]["lien"] and c[0][0]["lien"] in sk.get("sources", [])), titres)
    print(f"Sketch : « {sk['sujet']} », {len(sk['repliques'])} répliques", flush=True)
    accroche_hist = sk["repliques"][0]["t"] if sk.get("repliques") else ""
    num = serie.prochain()[0] if (libre and serie.actif() and sk.get("serie_titre") and not REFAIRE) else None
    if libre and sk.get("titre_accroche") and os.environ.get("VOIX_OFF", "1") != "0" and not sk.get("_monte"):
        titre_lu = sk["titre_accroche"].strip()                             # voix off d'ouverture : elle lit le titre « POV : … »
        if num: titre_lu = f"Épisode {num}. {titre_lu}"
        sk["repliques"].insert(0, {"p": "narrateur", "t": titre_lu, "d": "[excited] " + re.sub(r"\bPOV\b", "Pi-o-vi", titre_lu)})
        decaler(sk, 0)
    if libre and "teaser" in sk and os.environ.get("ACCROCHE", "0") == "1" and not sk.get("_monte"):
        k = sk["teaser"] + (1 if sk["repliques"][0]["p"] == "narrateur" else 0)   # accroche choc : la réplique est rejouée en ouverture
        copie = dict(sk["repliques"][k]); copie.pop("chute", None); copie.pop("attente", None); copie.pop("chevauche", None)
        copie["teaser"] = k + 1                                           # indice de l'original une fois la copie insérée
        sk["repliques"].insert(0, copie); decaler(sk, 0)
    teaser = sk["repliques"][0].get("teaser") if sk.get("repliques") else None
    if teaser is not None:                                                # la réplique rejouée n'est enregistrée qu'une fois
        reste = sk["repliques"][1:]
        audios, credits_voix, mots = voix.generer(reste, jt.VOIX)
        audios = [audios[teaser - 1]] + list(audios); mots = [mots[teaser - 1]] + list(mots) if mots else mots
    else:
        audios, credits_voix, mots = voix.generer(sk["repliques"], jt.VOIX)
    moteur = " + ".join(credits_voix)
    print(f"Voix : {moteur}", flush=True)
    avant = sum(len(a) for a in audios)
    audios = resserrer(audios, sk)
    if mots and sum(len(a) for a in audios) != avant:                         # débit accéléré : on recale les instants des mots
        f = avant / max(1, sum(len(a) for a in audios))
        mots = [[(m, d / f, e / f) for m, d, e in (x or [])] or None for x in mots]
    jour = datetime.date.today().isoformat()
    heure = datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%Hh%M")      # nom unique même si l'historique a été remis à zéro
    pris = {h.get("fichier") for h in historique}; n = 1; base = f"sortie/{jour}_{heure}_emission"
    while os.path.basename(base) + ".mp4" in pris: n += 1; base = f"sortie/{jour}_{heure}_emission{n}"   # plusieurs émissions le même jour
    os.makedirs("sortie", exist_ok=True)
    gag = None; duree = None; decors = {}; video_ok, rapport_video = True, ""
    if libre:                                                              # sketch libre / gag éclair : moteur cartoon animé
        try:
            import cartoon, decors as decors_mod
            if modal_ok and os.environ.get("DECORS", "1") != "0":
                t_gpu = datetime.datetime.now(); decors = decors_mod.generer(sk.get("decoupage"), graine=len(historique) + 7 + (datetime.datetime.now().microsecond % 997 if REFAIRE_MODE == "decors" else 0))
                GPU["s"] += (datetime.datetime.now() - t_gpu).total_seconds()
            duree = cartoon.rendre(sk, base + ".mp4", audios, mots=mots, decors=decors, mini=fmt == "mini")
            if not test and cartoon.MINUTAGE:                              # piste 13 : une IA regarde la vidéo finie
                import controle
                video_ok, rapport_video = controle.verifier(base + ".mp4", sk, cartoon.MINUTAGE)
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"Moteur cartoon en échec ({e}) : rendu de secours avec le moteur JT.", flush=True); duree = None
    if duree is None and modal_ok and sk.get("gag") and os.environ.get("PLAN_GAG", "1") != "0":
        import video_modal
        i = sk["gag"]["replique"]
        gag = video_modal.generer(sk["gag"]["prompt"], len(audios[i]) / SR + 0.6, base + "_gag.mp4", graine=len(historique))
        print(f"Plan gag IA : {'oui' if gag else 'non'}", flush=True)
    if duree is None: duree = jt.rendre(sk, base + ".mp4", audios, gag=gag, mots=mots)
    credit = "Voix : " + " ; ".join(credits_voix) + "."
    if gag: credit += " Plan « reconstitution » généré avec Wan 2.2."
    if decors: credit += " Décors générés avec Stable Diffusion XL (CreativeML Open RAIL++-M)."
    if libre:                                                              # signature de la chaîne dans les hashtags
        sk["hashtags"] = list(dict.fromkeys(["petitsdramas"] + [h for h in sk["hashtags"] if h != "petitsdramas"]))[:7]
    if num: sk["legende"] = f"Épisode {num} · {sk['serie_titre']} — {sk['legende']}"
    legende = f"{sk['legende']}" + (f"\n\n{sk['question']}" if sk.get("question") else "") + "\n\n" + " ".join("#" + h for h in sk["hashtags"]) + "\n\nContenu généré par IA."     # outils et crédits : seulement dans l'historique, jamais dans la légende
    open(base + ".txt", "w", encoding="utf-8").write(legende + "\n\nSources :\n" + "\n".join(sk["sources"]) + "\n")
    os.makedirs("episodes", exist_ok=True)
    json.dump(sk, open(f"episodes/{jour}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    fiche = sk.get("fiche", {})
    if fiche: print(f"Qualité : {fiche.get('note', 0):.0f}/100 — {fiche.get('decision')}", flush=True)
    historique.append(dict(date=jour, format=fmt, titre=sk["sujet"], sources=sk["sources"], note=fiche.get("note"), decision=fiche.get("decision"),
                           accroche=accroche_hist, mots=sorted(actu._mots(" ".join(fiche.get("titres_sujet") or [t["titre"] for t in titres])))[:40],
                           empreinte=sorted(actu.empreinte(" ".join((fiche.get("titres_sujet") or []) + [sk["sujet"]] + [r["t"] for r in sk.get("repliques", [])]))), voix=moteur, gag=bool(gag), controle_video=rapport_video[:500] or ("ok" if video_ok else ""), running_gag=sk.get("running_gag", ""), duree=round(duree, 1),
                           fichier=os.path.basename(base) + ".mp4", tag=f"emissions-{jour[:7]}", legende=legende, publie=None))
    json.dump(historique[-200:], open("episodes/historique.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if THEME and not REFAIRE: historique[-1]["manuel"] = True; historique[-1]["theme"] = THEME[:300]
    if REFAIRE:
        historique[-1]["refait_de"] = REFAIRE.split("|")[0]
        if ANCIEN and ANCIEN.get("manuel"): historique[-1]["manuel"] = True
    if AUTO: historique[-1]["auto"] = True
    historique[-1]["couts"] = couts(); print(f"Dépenses : {historique[-1]['couts']}", flush=True)
    os.makedirs("episodes/sketchs", exist_ok=True)                         # le sketch de chaque vidéo : « Refaire », exemples 👍
    json.dump(sk, open(f"episodes/sketchs/{os.path.basename(base)}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(historique[-200:], open("episodes/historique.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if libre and not test and not THEME:
        n_ep = serie.enregistrer(sk, os.path.basename(base) + ".mp4")
        if n_ep: print(f"Série « {sk['serie_titre']} » : épisode {n_ep} enregistré", flush=True)
    sortie = os.environ.get("GITHUB_OUTPUT")
    if sortie:
        with open(sortie, "a") as f:
            f.write(f"video={base}.mp4\nlegende={base}.txt\nnom={os.path.basename(base)}.mp4\nmois={jour[:7]}\ntitre={sk['sujet']}\n"
                    f"qualite={'ok' if video_ok and (not fiche or (fiche.get('note') or 0) >= SEUIL_PUB) and not REFAIRE else 'faible'}\nnote={round(fiche.get('note') or 0)}\n")
    print(f"OK : {base}.mp4 ({duree:.0f} s)")

if __name__ == "__main__":
    main()
