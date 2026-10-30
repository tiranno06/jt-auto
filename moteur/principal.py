"""Une exécution du robot = une émission.
1. casting vocal (seulement la première fois)
2. idée et sketch écrits par Claude (sinon : réserve de sketchs de secours), ou bande son d'une vidéo TikTok (doublage)
3. voix (ElevenLabs, sinon Chatterbox sur Modal, sinon Piper)
4. décors IA (Modal) et rendu du dessin animé (moteur/cartoon.py) ; la publication TikTok est faite ensuite par moteur/publier.py"""
import json, os, re, sys, time, datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(RACINE)
from programme import format_du_jour

_hist = json.load(open("episodes/historique.json", encoding="utf-8")) if os.path.exists("episodes/historique.json") else []
FILIERE = "tiktok" if (os.environ.get("FILIERE") or "").strip() == "tiktok" else "sketch"   # « Sons TikTok » : filière à part
AUTO = os.environ.get("EVENEMENT") == "schedule"                         # fabrication déclenchée par le planning (pas un bouton)
if AUTO:                                                                  # nouvelle vérification au démarrage : évite un doublon si deux réveils se suivent
    import planning
    _go, _raison = planning.decision(file=False)                          # (créneau de la DEMANDE : une vidéo qui a attendu son tour le garde)
    if not _go: print(f"Planning : rien à faire ({_raison})"); sys.exit(0)
LOT = (os.environ.get("SERIE_LOT") or "").strip() == "1"                 # série d'un seul jet : tous les épisodes à la suite
if LOT: os.environ["EPISODES"] = "serie"
THEME = (os.environ.get("THEME") or "").strip()[:2000]                 # création manuelle depuis l'onglet « Manuel » de la régie
REFAIRE = (os.environ.get("REFAIRE") or "").strip()                      # « fichier.mp4|texte|voix|decors|qui » : bouton Refaire de la régie
QUI = {}                                                                   # « Corriger qui parle » (idée 6) : n° de réplique -> personnage
ANCIEN, SK_ANCIEN = None, None
if REFAIRE:
    _f, _, _mode = REFAIRE.partition("|"); _mode = _mode or "texte"
    _mode, _, _qui = _mode.partition("|")                                  # « qui|0=invite;3=presentateur »
    for _x in _qui.split(";"):
        _k, _, _r = _x.partition("=")
        if _k.strip().isdigit() and _r.strip(): QUI[int(_k)] = _r.strip()
    ANCIEN = next((h for h in _hist if h.get("fichier") == _f), None)
    _d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "sketchs")
    _p = next((x for x in (os.path.join(_d, os.path.splitext(_f)[0] + ".json"), os.path.join(_d, _f + ".json")) if os.path.exists(x)), "")
    SK_ANCIEN = json.load(open(_p, encoding="utf-8")) if _p else None     # (le sketch est rangé sans « .mp4 » dans son nom)
    if ANCIEN: os.environ["FORMAT"] = ANCIEN.get("format") if ANCIEN.get("format") in ("mini", "libre") else "mini"
    if _mode in ("voix", "decors", "qui") and SK_ANCIEN is None:
        print("Sketch d'origine non conservé (vidéo plus ancienne) : on refait une nouvelle version du texte.", flush=True); _mode = "texte"
    REFAIRE_MODE = _mode
    if _mode == "voix": os.environ["VOIX_NOUVELLES"] = "1"              # « juste la voix » : d'autres voix de la banque que la dernière fois
    if _mode == "decors": os.environ["DECOR_GRAINE"] = str(datetime.datetime.now().microsecond % 997 + 1)   # décors dessinés tirés à neuf
    if ANCIEN and _mode == "texte" and not THEME:                        # nouvelle version : même sujet, écrit à neuf
        THEME = ((ANCIEN.get("titre_affiche") or "") + " " + (ANCIEN.get("titre") or "")).strip() + " — " + (ANCIEN.get("accroche") or "")
else:
    REFAIRE_MODE = ""
if THEME and (os.environ.get("FORMAT") or "") not in ("mini", "libre"): os.environ["FORMAT"] = "mini"
os.environ["FORMAT"] = FORMAT = format_du_jour(os.environ.get("FORMAT"), _hist)
if FORMAT == "mini": os.environ["LONGUEUR"] = "eclair"                    # gag éclair : ~15 s
elif FORMAT == "libre": os.environ["LONGUEUR"] = "pro"                    # sketch long : 60 à 90 s (plus d'une minute garantie au montage)
import reseau
ECO = reseau.mode_eco()                                                   # réglage « Mode économique » (avant d'importer ecrire)
import actu, ecrire, voix, jt, serie, stats, secours

SR = 22050

def accelerer(a, f):
    """Débit accéléré (même hauteur de voix)."""
    import subprocess, tempfile, wave, numpy as np
    tmp = tempfile.mkdtemp()
    with wave.open(f"{tmp}/a.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmp}/a.wav", "-af", f"atempo={f:.3f}", f"{tmp}/b.wav"])
    if r.returncode: return a
    with wave.open(f"{tmp}/b.wav") as w: return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768

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

def limite_job():
    """Heure (secondes) à laquelle une 2e version du jury doit être finie : limite du job GitHub moins 25 min (vérification,
    archivage, site, historique). Sans DEBUT_JOB (essai sur un ordinateur) : pas de limite."""
    if (os.environ.get("RENDU") or "") == "essai_pause" and not EN_REPRISE[0]: return __import__("time").time() + 60   # essai : pause tout de suite
    try: return float(os.environ["DEBUT_JOB"]) + (float(os.environ.get("LIMITE_JOB_MIN") or 180) - 25) * 60
    except (KeyError, ValueError): return None


EN_REPRISE = [False]                                                       # cette fabrication est la reprise d'une fabrication en pause


def main():
    import progression as PR                                               # avancement en direct sur le site (barre de progression)
    PR.TYPE[0] = "tiktok" if (FILIERE == "tiktok" or THEME.startswith("TIKTOK::")) else "sketch"
    import reprise as RP
    SUITE_NOM, CHAINE_ORIG = RP.demandee(); S = None                        # reprise d'une fabrication mise en pause (limite de temps)
    if not SUITE_NOM:                                                      # relance par le garde d'une fabrication coupée par surprise :
        nom_p, S_p = RP.point_existant()                                   # on repart de son point de sauvegarde
        if S_p:
            SUITE_NOM, S = nom_p, S_p
            print(f"Relance : reprise depuis le point de sauvegarde {nom_p} ({len(S.get('faits') or [])} bloc(s) d'images déjà dessinés)", flush=True)
    EN_REPRISE[0] = bool(SUITE_NOM)
    if SUITE_NOM:
        os.environ["CHAINE"] = CHAINE_ORIG                                 # « 2/3 » d'une chaîne de vidéos TikTok, sinon vide
        try:
            S = RP.charger(SUITE_NOM)                                       # (reprise lancée par une fabrication en pause)
            print(f"Reprise de la fabrication en pause {SUITE_NOM} ({'2e version du jury' if S['phase'] == 'v2' else '1re version'}, "
                  f"{len(S.get('faits') or [])} bloc(s) d'images déjà dessinés)", flush=True)
        except Exception as e:
            print(f"Reprise {SUITE_NOM} impossible ({str(e)[:160]}) : la vidéo est refaite entièrement", flush=True); S = None
    PR.etape(3, "Reprise de la fabrication" if S else "Démarrage du robot", forcer=True)
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
    libre = True                                                           # toutes les vidéos sont des sketchs animés (gag éclair ou sketch long)
    print(f"Type de vidéo : {'gag éclair (~15 s)' if fmt == 'mini' else 'sketch long (+1 min)'}", flush=True)
    recents = [f"{h.get('titre', '')} : {h.get('accroche', '')}" for h in historique[-10:]]
    # 1. recherche : sujets candidats (articles des dernières 24 h, regroupés par sujet et classés par reprise médiatique)
    script = None; tiktok = None; DOUB = None; SECOURS = False
    import reseau
    CREDITS = reseau.verifier_credits()                                    # crédits vérifiés AU DÉPART : payant si possible, sinon gratuit tout de suite
    try: __import__("credits").enregistrer(dict(CREDITS, modal="ok" if modal_ok else "absent"))   # voyants du site à jour
    except Exception: pass
    def passer_en_secours(e):                                              # Claude ne répond pas (crédit épuisé) : outils gratuits
        print(f"Claude indisponible ({str(e)[:160]}) : bascule automatique sur un sketch de secours (outils gratuits pour l'écriture).", flush=True)
        try:
            import alerte
            alerte.alerter("Crédit Claude épuisé ?", "Claude ne répond pas : la vidéo est fabriquée avec un sketch de secours déjà écrit. "
                           "Rechargez le crédit sur console.anthropic.com pour revenir aux sketchs écrits par Claude.")
        except Exception: pass
    PR.etape(6, "Écoute du son TikTok" if (FILIERE == "tiktok" or THEME.startswith("TIKTOK::")) else "Recherche de l'idée", forcer=True)
    PROFIL_PREP = None                                                     # filière « Sons TikTok » (à part des sketchs) : une vidéo
    if FILIERE == "tiktok" and not THEME and not S:                        # au hasard d'un profil de la liste, jamais déjà utilisée
        import profils_tiktok, doublage
        print(f"Sons TikTok : vidéo tirée des profils {', '.join('@' + p for p in profils_tiktok.liste()) or '(aucun profil réglé)'}", flush=True)
        import locuteurs
        seuil_v = float(os.environ.get("VOIX_DIFFERENTES") or 0.6)          # au-delà : voix trop proches (même personne qui fait les deux)
        garde_v, t_v = None, time.time()
        for url_ in profils_tiktok.choisir(historique, essais=6):
            locuteurs.ETAT["ressemblance"] = None
            try: prep_ = doublage.preparer(url_)
            except Exception as e: print(f"  son de {url_} impossible ({str(e)[:160]}) : vidéo suivante", flush=True); continue
            r_ = locuteurs.ETAT.get("ressemblance")
            if r_ is None or r_ <= seuil_v or seuil_v >= 1:                 # voix bien différentes (ou une seule voix) : on la prend
                PROFIL_PREP = (url_, prep_); break
            print(f"  voix trop proches dans {url_} (ressemblance {r_:.2f}) : on cherche une vidéo aux voix bien différentes", flush=True)
            if garde_v is None or r_ < garde_v[0]: garde_v = (r_, url_, prep_)
            if time.time() - t_v > 25 * 60: break                          # pas plus de 25 min de recherche
        if PROFIL_PREP is None and garde_v:                                # que des voix proches : la plus nette (contrôle questions-réponses)
            PROFIL_PREP = garde_v[1:]; print(f"  aucune vidéo aux voix bien différentes : on garde {garde_v[1]} (ressemblance {garde_v[0]:.2f})", flush=True)
        if PROFIL_PREP is None:                                            # jamais de sketch à la place : les deux filières sont séparées
            print("Sons TikTok : aucune vidéo des profils utilisable cette fois (pas de vidéo).", flush=True)
            PR.fini(False, "Aucun son TikTok utilisable cette fois")
            t_ = "episodes/tentatives.json"; tent = lire(t_, [])
            tent.append({"date": datetime.datetime.now(ZoneInfo("Europe/Paris")).date().isoformat(), "heure": datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%H:%M"),
                         "auto": AUTO, "filiere": "tiktok", "note": 0, "titre": "aucun son TikTok utilisable"})
            json.dump(tent[-100:], open(t_, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            return
    if S:                                                                  # reprise : l'idée / le son déjà choisis
        candidats = S["candidats"]; tiktok = S.get("tiktok"); SECOURS = S.get("secours", False)
    elif PROFIL_PREP:
        tiktok = PROFIL_PREP[0]
        candidats = [([{"titre": "Bande son TikTok (profil)", "resume": tiktok, "lien": tiktok, "date": None, "source": "tiktok"}], "tiktok")]
    elif THEME.startswith("TIKTOK::"):                                     # vidéo construite sur la bande son d'une vidéo TikTok
        tiktok = THEME.split("::", 1)[1].strip()
        candidats = [([{"titre": "Bande son TikTok", "resume": tiktok, "lien": tiktok, "date": None, "source": "tiktok"}], "tiktok")]
    elif THEME:                                                              # vidéo manuelle : le thème (ou le script) tapé dans la régie
        mode_script = THEME.startswith("SCRIPT::"); texte = THEME.split("::", 1)[1].strip() if "::" in THEME[:12] else THEME
        print(f"Vidéo manuelle ({'script' if mode_script else 'idée'}) : « {texte[:200]} »", flush=True)
        if mode_script: script = texte
        candidats = [([{"titre": texte.splitlines()[0][:120], "resume": texte[:1500], "lien": "", "date": None, "source": "manuel"}], "manuel")]
    elif LOT and libre:                                                    # série d'un seul jet : la saison est planifiée, on fabrique l'épisode suivant
        try:
            if not serie.a_faire()[0]: serie.planifier(fmt, recents=[h.get("titre", "") for h in historique[-30:]])
            prevu, k_ep = serie.a_faire()
            candidats = [([{"titre": prevu["titre"], "resume": prevu["resume"], "lien": "", "date": None, "source": "série"}], "série")]
            print(f"Série d'un seul jet : épisode {k_ep} « {prevu['titre']} »", flush=True)
        except Exception as e:
            if not secours.claude_indisponible(e): raise
            passer_en_secours(e); SECOURS = True; candidats = [([{"titre": "secours", "resume": "", "lien": "", "date": None, "source": "secours"}], "secours")]
    elif libre and not os.environ.get("SKETCH_TEST", "").strip() and CREDITS.get("ia", CREDITS["claude"]) != "ok":   # aucune IA (Claude, Mistral, Gemini) : réserve de sketchs
        passer_en_secours(RuntimeError("crédit Claude épuisé ou clé absente (vérifié au départ)")); SECOURS = True
        candidats = [([{"titre": "secours", "resume": "", "lien": "", "date": None, "source": "secours"}], "secours")]
    elif libre and not os.environ.get("SKETCH_TEST", "").strip():
        try: candidats = [(c, "idée") for c in ecrire.idees_libres(recents=[f"{h.get('titre', '')} : {h.get('accroche', '')}" for h in historique[-30:]],
                                                                    consignes=stats.pour_idees())]
        except Exception as e:
            print(f"Idées de sketch impossibles : {e}", flush=True)
            if not secours.claude_indisponible(e): raise
            passer_en_secours(e); SECOURS = True; candidats = [([{"titre": "secours", "resume": "", "lien": "", "date": None, "source": "secours"}], "secours")]
        for k, (sel, _) in enumerate(candidats): print(f"Idée {k} : « {sel[0]['titre'][:110]} »", flush=True)
    else:                                                                  # sketch d'essai (SKETCH_TEST)
        candidats = [([{"titre": "essai", "resume": "", "lien": "", "date": None, "source": "essai"}], "essai")]
    if not candidats:
        print("Aucune idée de sketch obtenue : pas d'émission.", flush=True); return
    titres = candidats[0][0]
    recents = [f"{h.get('titre', '')} : {h.get('accroche', '')}" for h in historique[-10:]]
    from zoneinfo import ZoneInfo
    dimanche = datetime.datetime.now(ZoneInfo("Europe/Paris")).weekday() == 6 and os.environ.get("INFOS_DEMAIN", "1") != "0"
    gags = [h.get("running_gag") for h in historique[-15:] if h.get("running_gag")]
    test = os.environ.get("SKETCH_TEST", "").strip()
    if S:                                                                  # reprise : sketch, son et format déjà prêts
        import doublage
        sk, DOUB, fmt = S["sk"], S["DOUB"], S["fmt"]
    elif REFAIRE_MODE in ("voix", "decors", "qui"):                        # mêmes répliques : on refait seulement les voix / les décors
        sk = SK_ANCIEN; sk["_monte"] = True
        for k_, r_ in QUI.items():                                         # « Corriger qui parle » : chaque réplique au bon personnage
            if 0 <= k_ < len(sk.get("repliques") or []) and r_ in ("presentateur", "invite", "envoyee", "narrateur"): sk["repliques"][k_]["p"] = r_
        if QUI: print(f"Corriger qui parle : {len(QUI)} réplique(s) rendue(s) au bon personnage", flush=True)
        if sk.get("doublage") and REFAIRE_MODE == "qui":                  # son TikTok : on garde la bande son d'origine
            import doublage
            DOUB = list(doublage.depuis_sketch(sk)); fmt = "libre" if sk["doublage"].get("duree", 0) >= 60 else "mini"
        print(f"Refaire ({REFAIRE_MODE}) : « {sk.get('sujet')} », mêmes répliques", flush=True)
    elif tiktok:
        import doublage
        sk, *DOUB = PROFIL_PREP[1] if PROFIL_PREP else doublage.preparer(tiktok)   # (déjà préparé quand il vient d'un profil)
        fmt = "libre" if sk["doublage"]["duree"] >= 60 else "mini"         # rangée en vidéo longue au-delà d'une minute
    elif script:                                                           # script tapé : les répliques restent mot pour mot
        sk = ecrire.mettre_en_scene(script)
    elif test:                                                             # sketch écrit à la main (essai d'un style)
        ecrire.NB_MAX = 20
        sk = ecrire.valider(json.load(open(test, encoding="utf-8")), set(), libre)
        print(f"Sketch d'essai : {test}", flush=True)
    elif SECOURS:
        sk = secours.sketch(fmt)
    else:
        if THEME or LOT or REFAIRE: os.environ["FORCER_FABRICATION"] = "1"   # vidéo demandée explicitement : elle est fabriquée quoi qu'il arrive
        PR.etape(10, "Écriture du sketch", forcer=True)
        try:
            sk = ecrire.ecrire_sketch([c[0] for c in candidats], gags=gags, special=dimanche and not libre, recents=recents, libre=libre,
                                      serie=serie.contexte() if (libre and not THEME) else "", stats=stats.pour_auteur() if libre else "")
        except ecrire.QualiteInsuffisante as q:                             # sous la note minimale : pas de vidéo moyenne (voix et décors économisés)
            print(f"Pas de vidéo : {q} (réglage ⚙️ Écriture → note minimale).", flush=True)
            PR.fini(False, "Sketch pas assez drôle : nouvel essai au prochain réveil")
            print(f"Moteur humoristique : {ecrire.USAGE['appels']} appels Claude, {ecrire.USAGE['entree']} jetons lus, {ecrire.USAGE['sortie']} jetons écrits, coût {ecrire.USAGE.get('cout', 0):.2f} $", flush=True)
            t_ = "episodes/tentatives.json"; tent = lire(t_, [])
            tent.append({"date": datetime.datetime.now(ZoneInfo("Europe/Paris")).date().isoformat(), "heure": datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%H:%M"),
                         "auto": AUTO, "filiere": FILIERE, "note": round(q.note, 1), "titre": q.sk.get("sujet", ""),
                         "cout_usd": round(ecrire.USAGE.get("cout", 0), 3)})
            json.dump(tent[-100:], open(t_, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            try:
                import alerte
                alerte.alerter("Pas de vidéo cette fois", f"Meilleur sketch : {q.note:.0f}/100 (« {q.sk.get('sujet', '')} »), sous votre minimum de {ecrire.QUALITE_MIN}. "
                               "Rien n'a été fabriqué : crédits voix et décors économisés. Nouvel essai au prochain réveil (si la limite d'essais du créneau n'est pas atteinte).")
            except Exception: pass
            return
        except Exception as e:
            if not secours.claude_indisponible(e): raise
            passer_en_secours(e); SECOURS = True
            sk = secours.sketch(fmt)
        print(f"Moteur humoristique : {ecrire.USAGE['appels']} appels Claude, {ecrire.USAGE['entree']} jetons lus, {ecrire.USAGE['sortie']} jetons écrits, {ecrire.USAGE['recherches_web']} recherche(s) web", flush=True)
        titres = next((c[0] for c in candidats if c[0][0]["lien"] and c[0][0]["lien"] in sk.get("sources", [])), titres)
    print(f"Sketch : « {sk['sujet']} », {len(sk['repliques'])} répliques", flush=True)
    accroche_hist = S["accroche_hist"] if S else (sk["repliques"][0]["t"] if sk.get("repliques") else "")
    if LOT and serie.etat().get("titre"): sk["serie_titre"] = serie.etat()["titre"]   # l'épisode compte toujours dans la saison
    num = S["num"] if S else (serie.prochain()[0] if (libre and serie.actif() and sk.get("serie_titre") and not REFAIRE) else None)
    if num:                                                                # fin d'épisode : rendez-vous pour la suite (série)
        total_ep = len(serie.etat().get("plan") or []) or serie.taille()
        sk["suite"] = f"Épisode {num + 1} bientôt : abonne-toi !" if num < total_ep else "Fin de la saison : abonne-toi !"
    style_acc = S["style_acc"] if S else None
    if not DOUB and not sk.get("_monte") and not S:                        # deux styles d'accroche départagés par les vues
        try:
            import accroches; style_acc = accroches.choisir(sk, historique)
            if style_acc: print(f"Accroche ({style_acc}) : « {sk['titre_accroche']} »", flush=True)
        except Exception as e: print(f"Accroche : {e}", flush=True)
    if libre and sk.get("titre_accroche") and os.environ.get("VOIX_OFF", "1") != "0" and not sk.get("_monte") and (os.environ.get("RENDU") or "") != "realiste" and not S:
        titre_lu = sk["titre_accroche"].strip()                             # voix off d'ouverture : elle lit le titre « POV : … »
        if num: titre_lu = f"Épisode {num}. {titre_lu}"
        sk["repliques"].insert(0, {"p": "narrateur", "t": titre_lu, "d": "[excited] " + re.sub(r"\bPOV\b", "Pi-o-vi", titre_lu)})
        decaler(sk, 0)
    if libre and "teaser" in sk and os.environ.get("ACCROCHE", "0") == "1" and not sk.get("_monte") and not S:
        k = sk["teaser"] + (1 if sk["repliques"][0]["p"] == "narrateur" else 0)   # accroche choc : la réplique est rejouée en ouverture
        copie = dict(sk["repliques"][k]); copie.pop("chute", None); copie.pop("attente", None); copie.pop("chevauche", None)
        copie["teaser"] = k + 1                                           # indice de l'original une fois la copie insérée
        sk["repliques"].insert(0, copie); decaler(sk, 0)
    def voix_et_minutage():
        """Voix des répliques (ElevenLabs…), débit ajusté, minutage des mots."""
        PR.etape(22, "Voix des personnages", forcer=True)
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
        for i_, r_ in enumerate(sk["repliques"][:2]):                         # voix off du titre plus enlevée : on entre vite dans l'action
            if r_["p"] == "narrateur" and audios[i_] is not None:
                audios[i_] = accelerer(audios[i_], 1.15)
                if mots and mots[i_]: mots[i_] = [(m, d / 1.15, e / 1.15) for m, d, e in mots[i_]]
        if mots and sum(len(a) for a in audios) != avant:                         # débit accéléré : on recale les instants des mots
            f = avant / max(1, sum(len(a) for a in audios))
            mots = [[(m, d / f, e / f) for m, d, e in (x or [])] or None for x in mots]
        return audios, credits_voix, mots, moteur

    REALISTE = libre and not DOUB and not S and ((os.environ.get("RENDU") or "") == "realiste" or (AUTO and (os.environ.get("REALISTE_AUTO") or "0") == "1"))
    if S: audios, credits_voix, mots, moteur = S["audios"], S["credits_voix"], S["mots"], S["moteur"]   # reprise : voix déjà faites
    elif DOUB:                                                               # bande son d'origine : pas de voix à fabriquer
        audios, mots = DOUB; credits_voix = [f"bande son d'origine (@{sk['doublage']['auteur']})"]; moteur = "bande son TikTok"
    elif REALISTE: audios, credits_voix, mots, moteur = [], ["Veo 3.1 via ElevenLabs"], None, "Veo 3.1"   # le son vient de la vidéo réaliste
    else: audios, credits_voix, mots, moteur = voix_et_minutage()
    maintenant = datetime.datetime.now(ZoneInfo("Europe/Paris"))            # date ET heure de Paris (avant : date de Londres + heure de Paris,
    jour, heure = maintenant.date().isoformat(), maintenant.strftime("%Hh%M")     # une vidéo de 1 h 29 portait la date de la veille)
    pris = {h.get("fichier") for h in historique}; n = 1; base = f"sortie/{jour}_{heure}_emission"
    while os.path.basename(base) + ".mp4" in pris: n += 1; base = f"sortie/{jour}_{heure}_emission{n}"   # plusieurs émissions le même jour
    if S: base, jour = S["base"], S["jour"]                                # reprise : même vidéo, même nom
    os.makedirs("sortie", exist_ok=True)
    gag = None; duree = None; decors = {}; video_ok, rapport_video = True, ""
    QUALITE = {"Q": None, "corrigees": []}                                 # jury qualité de la vidéo (moteur/qualite.py)
    if REALISTE:                                                           # mode réaliste (option) : vraie vidéo IA, voix comprises
        try:
            import realiste
            duree = realiste.rendre(sk, base + ".mp4", mini=fmt == "mini")
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"Mode réaliste en échec ({str(e)[:200]}) : on bascule sur le dessin animé.", flush=True)
            REALISTE = False; audios, credits_voix, mots, moteur = voix_et_minutage()
    if libre and not REALISTE:                                             # sketch libre / gag éclair : moteur cartoon animé
        try:
            import cartoon, decors as decors_mod, studio as _st
            if not S and _st.separer_lieux(sk): print("Lieux séparés : chaque personnage a son propre décor (appel, visio, l'un ailleurs)", flush=True)
            if S: decors = S["decors"]                                     # reprise : décors déjà faits
            elif modal_ok and os.environ.get("DECORS", "1") != "0":
                lum = ""; plans_dec = None
                if cartoon.DETAIL:                                         # même lumière que la bible de l'épisode (heure, lampes)
                    try:
                        import studio, decor_dessin as DD
                        B0 = studio.bible(sk, [r for r in dict.fromkeys(x["p"] for x in sk.get("repliques", [])) if r != "narrateur"]); lum = B0["style_ia"]
                        plans_dec = {k: DD.dessiner(B0["lieux"][min(k, len(B0["lieux"]) - 1)], B0, graine=B0["graine"] % 9973 + k)["fond"]   # l'IA peint par-dessus notre plan
                                     for k in range(len(sk.get("decoupage") or []))}
                    except Exception as e: print(f"Bible du studio indisponible pour les décors IA : {e}", flush=True)
                PR.etape(32, "Décors", forcer=True)
                t_gpu = datetime.datetime.now(); decors = decors_mod.generer(sk.get("decoupage"), graine=len(historique) + 7 + (datetime.datetime.now().microsecond % 997 if REFAIRE_MODE == "decors" else 0), lumiere=lum, plans=plans_dec)
                GPU["s"] += (datetime.datetime.now() - t_gpu).total_seconds()
            try:                                                           # mode payant : ambiance sonore ElevenLabs de chaque lieu (une fois par lieu)
                import bruitages_eleven, studio as st_
                if cartoon.DETAIL and not DOUB and not S and os.environ.get("AMBIANCES_ELEVEN", "1") != "0":
                    for l_ in set(st_.bible(sk, [r for r in dict.fromkeys(x["p"] for x in sk.get("repliques", [])) if r != "narrateur"])["lieux"]): bruitages_eleven.ambiance_lieu(l_)
            except Exception as e: print(f"Ambiances ElevenLabs indisponibles : {e}", flush=True)
            import controle, qualite, copy
            reprise_v2 = bool(S and S["phase"] == "v2")                    # reprise pendant la 2e version du jury
            def etat_a_sauver(phase, faits, **plus):
                """Tout ce qu'il faut pour reprendre la fabrication ailleurs (et les fichiers à joindre)."""
                ctx = dict(phase=phase, faits=faits, sk=plus.get("sk", sk), DOUB=DOUB, fmt=fmt, candidats=candidats, tiktok=tiktok, secours=SECOURS,
                           num=num, style_acc=style_acc, accroche_hist=accroche_hist, audios=audios, credits_voix=credits_voix, mots=mots,
                           moteur=moteur, base=base, jour=jour, decors=plus.get("decors", decors))
                if phase == "v2": ctx.update(video_v1=base + ".mp4", duree=duree, tech=(tech_ok, rapport_tech), qualite=copy.deepcopy(QUALITE), **plus)
                d_ = (ctx["sk"].get("doublage") or {})
                return ctx, [c_ for _a, _b, c_ in faits] + ([base + ".mp4"] if phase == "v2" else []) + [d_.get("piste"), d_.get("video_origine")]
            def point(phase, **plus):
                """Point de sauvegarde avant de dessiner : si la machine est coupée par surprise, la relance repart du dernier bloc."""
                nom_p = RP.poser_point(*etat_a_sauver(phase, [], **plus), phase)
                cartoon.APRES_BLOC[0] = (lambda a_, b_, c_: RP.deposer_bloc(nom_p, a_, b_, c_)) if nom_p else None
            def pause(phase, faits, **plus):
                """Limite de temps de GitHub proche : tout est sauvegardé et une nouvelle machine reprend là où on en est."""
                ctx, fich = etat_a_sauver(phase, faits, **plus)
                PR.etape(PR.PLAGE[0], "Mise en pause : la suite repart sur une nouvelle machine", forcer=True)
                nom_ = RP.sauver(ctx, fich); RP.relancer(nom_, os.environ.get("CHAINE", ""))
                for t_ in RP.ENVOIS: t_.join(timeout=120)
                for n_ in (RP.nom_point("v1"), RP.nom_point("v2")): RP.nettoyer(n_)   # la pause a sa propre sauvegarde
                print(f"Fabrication mise en pause ({phase}, {len(faits)} bloc(s) déjà dessinés) : reprise {nom_} lancée", flush=True)
                if os.environ.get("GITHUB_OUTPUT"):
                    with open(os.environ["GITHUB_OUTPUT"], "a") as f_: f_.write("pause=1\n")
                PR._envoyer(PR.PLAGE[0], "En pause : reprise automatique sur une nouvelle machine", None, "success")
                raise RP.EnPause(nom_)
            if reprise_v2:                                                 # la 1re version est déjà faite et jugée
                import shutil; shutil.copy(S["video_v1"], base + ".mp4"); duree = S["duree"]
                for k_, v_ in S["etat_v1"].items(): setattr(cartoon, k_, v_)
                tech_ok, rapport_tech = S["tech"]
            else:
                PR.PLAGE[:] = [40, 86]; PR.etape(40, "Dessin des images", forcer=True)
                if not S and not test and os.environ.get("JURY", "1") != "0" and os.environ.get("PRE_JURY", "1") != "0":
                    try:                                                   # pré-jury : les règles sûres du jury appliquées AVANT de dessiner
                        import tempfile as _tf                             # (tête coupée, chevauchement, sous-titre sur un visage, chute
                        cartoon.rendre(copy.deepcopy(sk), _tf.mkdtemp(), audios, mots=mots, decors=copy.deepcopy(decors), mini=fmt == "mini", plans_seuls=True)
                        G_ = qualite.jury_gratuit(cartoon.RENDU, sk)        # sans zoom…) : la 2e version ne sert plus qu'aux remarques de l'IA
                        corr_ = [r_["correction"] for v_ in G_.values() for r_ in v_["remarques"]
                                 if isinstance(r_.get("correction"), dict) and r_["correction"].get("type") in ("plan", "reaction", "bruitage") and r_["poids"] >= 1.0]
                        faites_ = qualite.corriger(sk, corr_) if corr_ else []
                        if faites_: print("Pré-jury (avant de dessiner) : " + " ; ".join(faites_), flush=True); QUALITE["corrigees"] += faites_
                    except Exception as e: print(f"Pré-jury impossible ({str(e)[:120]})", flush=True)
                sk_avant, dec_avant = copy.deepcopy(sk), copy.deepcopy(decors)
                point("v1", sk=sk_avant, decors=dec_avant)
                try: duree = cartoon.rendre(sk, base + ".mp4", audios, mots=mots, decors=decors, mini=fmt == "mini", limite=limite_job(), deja=(S or {}).get("faits"))
                except cartoon.TempsDepasse as e: pause("v1", e.faits, sk=sk_avant, decors=dec_avant)
                tech_ok, rapport_tech = controle.technique(base + ".mp4", duree, cartoon.MINUTAGE[-1][1] if cartoon.MINUTAGE else None)     # contrôles gratuits (format, son, images noires)
            if not test and cartoon.RENDU and os.environ.get("JURY", "1") != "0":   # jury qualité : 5 critiques (gratuits + Claude s'il y a du crédit)
                PR.etape(88, "Contrôle qualité par le jury", 120, forcer=True)
                if reprise_v2: QUALITE.update(S["qualite"]); Q = QUALITE["Q"]
                else: QUALITE["Q"] = Q = qualite.evaluer(base + ".mp4", cartoon.RENDU, sk, "" if tech_ok else rapport_tech)
                video_ok, rapport_video = not Q["defauts_graves"], Q["rapport"]
                try: tours = max(0, min(2, int(os.environ.get("JURY_TOURS") or 1)))
                except ValueError: tours = 1
                try: seuil_j = float(os.environ.get("SEUIL_JURY") or 9.8)
                except ValueError: seuil_j = 9.8
                for tour in range(tours):                                  # corrections automatiques puis nouvelle version, on garde la meilleure
                    if reprise_v2 and tour < S["tour"]: continue           # (tours déjà faits avant la pause)
                    if reprise_v2 and tour == S["tour"]:                   # reprise : mêmes corrections, la 2e version continue où elle s'était arrêtée
                        sk2, dec2, faites, etat, deja2 = S["sk2"], S["dec2"], S["faites"], S["etat_v1"], S["faits"]
                        print(f"Reprise de la 2e version (tour {tour + 1}) : " + " ; ".join(faites), flush=True)
                    else:
                        if Q["note"] >= seuil_j or not Q["corrections"]: break
                        sk2 = copy.deepcopy(sk); faites = qualite.corriger(sk2, Q["corrections"])
                        if not faites: break
                        print(f"Corrections du jury (tour {tour + 1}) : " + " ; ".join(faites), flush=True)
                        dec2 = dict(decors)
                        for k_ in sk2.pop("_decors_a_refaire", []): dec2.pop(k_, None)
                        n_sc = len(sk2.get("decoupage") or [])
                        if _st.separer_lieux(sk2) and len(sk2.get("decoupage") or []) != n_sc or sk2.get("decoupage") != sk.get("decoupage"):
                            dec2 = {}                                      # nouveaux lieux : nouveaux décors (IA si possible)
                            if modal_ok and os.environ.get("DECORS", "1") != "0":
                                try: dec2 = decors_mod.generer(sk2.get("decoupage"), graine=len(historique) + 11)
                                except Exception as e: print(f"Nouveaux décors IA impossibles ({e}) : décors dessinés", flush=True)
                        etat = {k_: copy.copy(getattr(cartoon, k_)) for k_ in ("MINUTAGE", "PH", "BRUITAGES", "RENDU", "COUVERTURE", "COUVERTURE_MS")}
                        deja2 = None
                    sk2_avant, dec2_avant = copy.deepcopy(sk2), copy.deepcopy(dec2)
                    point("v2", tour=tour, sk2=sk2_avant, dec2=dec2_avant, faites=faites, etat_v1=etat)
                    try:
                        PR.PLAGE[:] = [90, 97]; PR.APRES[0] = 90; PR.etape(90, "Nouvelle version corrigée par le jury", forcer=True)
                        d2 = cartoon.rendre(sk2, base + "_v2.mp4", audios, mots=mots, decors=dec2, mini=fmt == "mini",
                                            reprise={"video": base + ".mp4", "rendu": copy.deepcopy(etat["RENDU"])}, limite=limite_job(), deja=deja2)
                        t2_ok, t2_rap = controle.technique(base + "_v2.mp4", d2, cartoon.MINUTAGE[-1][1] if cartoon.MINUTAGE else None)
                        Q2 = qualite.evaluer(base + "_v2.mp4", cartoon.RENDU, sk2, "" if t2_ok else t2_rap)
                    except cartoon.TempsDepasse as e:                      # plus le temps : la 2e version sera finie par une nouvelle machine
                        pause("v2", e.faits, tour=tour, sk2=sk2_avant, dec2=dec2_avant, faites=faites, etat_v1=etat)
                    except Exception as e:
                        print(f"Nouvelle version impossible ({str(e)[:160]}) : on garde la première.", flush=True); Q2, t2_ok = None, False
                    if Q2 and t2_ok and Q2["note"] > Q["note"]:
                        os.replace(base + "_v2.mp4", base + ".mp4"); sk.clear(); sk.update(sk2); duree, decors = d2, dec2
                        print(f"Version corrigée gardée : {Q['note']} → {Q2['note']}/10", flush=True)
                        QUALITE["corrigees"] += faites; QUALITE["Q"] = Q = Q2; video_ok, rapport_video = not Q["defauts_graves"], Q["rapport"]
                    else:
                        if os.path.exists(base + "_v2.mp4"): os.remove(base + "_v2.mp4")
                        for k_, v_ in etat.items(): setattr(cartoon, k_, v_)
                        print("La version corrigée n'est pas meilleure : on garde la première.", flush=True); break
                qualite.memoriser(Q, os.path.basename(base) + ".mp4", QUALITE["corrigees"])
            if not tech_ok: video_ok = False; rapport_video = (rapport_tech + " ; " + rapport_video).strip(" ;")
            B_ = sk.pop("_bible", None)
            if B_:                                                         # direction artistique : fiche de l'épisode + mémoire du studio
                import studio
                sk["realisation"] = {k: B_[k] for k in ("moment", "lieux", "gags", "ambiances", "source")}
                sk["realisation"]["tenues"] = {r: c.get("haut") for r, c in B_["costumes"].items()}
                sk["realisation"]["plans"] = [f"{q.get('plan')}/{q.get('mouvement')}" for q in cartoon.PH]
                studio.memoriser(B_, cartoon.PH, duree, rapport_video or ("ok" if video_ok else ""), fichier=os.path.basename(base) + ".mp4")
            if sk.get("doublage") and not test:                            # banque visuelle : ce qu'on a vu dans la vidéo d'origine et ce qu'on en a fait
                import banque_visuelle
                banque_visuelle.ajouter(sk["doublage"], sk.get("studio"), sk.get("realisation"), os.path.basename(base) + ".mp4")
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"Moteur cartoon en échec ({e}) : nouvel essai en rendu simple, sans décor IA.", flush=True); duree = None
            import cartoon
            cartoon.DETAIL = False                                         # secours : bonshommes simples, plans simples (la vidéo sort quand même)
            duree = cartoon.rendre(sk, base + ".mp4", audios, mots=mots, decors={}, mini=fmt == "mini")
    if (os.environ.get("APERCU_RAPIDE") or "") != "1":                     # fin en boucle : la dernière image se raccorde à la première
        try: duree = __import__("boucle").boucler(base + ".mp4")
        except Exception as e: print(f"fin en boucle impossible ({str(e)[:120]})", flush=True)
    credit = "Voix : " + " ; ".join(credits_voix) + "."
    if decors: credit += " Décors générés avec Stable Diffusion XL (CreativeML Open RAIL++-M)."
    if libre:                                                              # signature de la chaîne dans les hashtags
        sk["hashtags"] = list(dict.fromkeys(["petitsdramas"] + [h for h in sk["hashtags"] if h != "petitsdramas"]))[:7]
    if num: sk["legende"] = f"Épisode {num} · {sk['serie_titre']} — {sk['legende']}"
    legende = f"{sk['legende']}" + (f"\n\n{sk['question']}" if sk.get("question") else "") + (f"\n\n{doublage.credit(sk)}" if DOUB else "")   # crédit du son d'origine + "\n\n" + " ".join("#" + h for h in sk["hashtags"]) + "\n\nContenu généré par IA."     # outils et crédits : seulement dans l'historique, jamais dans la légende
    open(base + ".txt", "w", encoding="utf-8").write(legende + "\n\nSources :\n" + "\n".join(sk["sources"]) + "\n")
    os.makedirs("episodes", exist_ok=True)
    json.dump(sk, open(f"episodes/{jour}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    fiche = sk.get("fiche", {})
    if fiche: print(f"Qualité : {fiche.get('note', 0):.0f}/100 — {fiche.get('decision')}", flush=True)
    if (os.environ.get("APERCU_RAPIDE") or "") == "1": sk["sujet"] = "👀 Aperçu 10 s — " + str(sk.get("sujet") or "")   # aperçu : bien signalé
    historique.append(dict(date=jour, format=fmt, titre=sk["sujet"], sources=sk["sources"], note=fiche.get("note"), decision=fiche.get("decision"),
                           accroche=accroche_hist, mots=sorted(actu._mots(" ".join(fiche.get("titres_sujet") or [t["titre"] for t in titres])))[:40],
                           empreinte=sorted(actu.empreinte(" ".join((fiche.get("titres_sujet") or []) + [sk["sujet"]] + [r["t"] for r in sk.get("repliques", [])]))), voix=moteur, gag=bool(gag), controle_video=rapport_video[:500] or ("ok" if video_ok else ""), running_gag=sk.get("running_gag", ""), duree=round(duree, 1),
                           fichier=os.path.basename(base) + ".mp4", tag=f"emissions-{jour[:7]}", legende=legende, publie=None,
                           style_accroche=style_acc, couverture_ms=int((getattr(sys.modules.get("cartoon"), "COUVERTURE", None) or 2.5) * 1000),
                           outils=dict(claude=("secours" if SECOURS else CREDITS["claude"]), mistral=CREDITS.get("mistral", "absent"),
                                       gemini=CREDITS.get("gemini", "absent"), ia=", ".join(f"{k} ×{v}" for k, v in __import__("reseau").UTILISES.items()) or "aucune",
                                       voix=("tiktok" if DOUB else "elevenlabs" if "eleven" in str(moteur).lower() else "chatterbox" if "chatterbox" in str(moteur).lower() else "piper"),
                                       decors=("ia" if decors else "dessines"), eco=ECO)))
    if QUALITE["Q"]:                                                       # fiche du jury : notes, remarques, corrections faites
        Q_ = QUALITE["Q"]
        historique[-1]["jury"] = dict(note=Q_["note"], source=Q_["source"], notes={k: v["note"] for k, v in Q_["jury"].items()},
                                      remarques=[r_["probleme"][:140] for v in Q_["jury"].values() for r_ in v["remarques"]][:12],
                                      corrigees=QUALITE["corrigees"][:10], manques=Q_.get("manques_origine") or [])
    print("Outils utilisés : " + ", ".join(f"{k} = {v}" for k, v in historique[-1]["outils"].items()), flush=True)
    json.dump(historique[-200:], open("episodes/historique.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if THEME and not REFAIRE: historique[-1]["manuel"] = True; historique[-1]["theme"] = THEME[:300]
    if REFAIRE:
        historique[-1]["refait_de"] = REFAIRE.split("|")[0]
        if ANCIEN and ANCIEN.get("manuel"): historique[-1]["manuel"] = True
    if AUTO: historique[-1]["auto"] = True
    if test or (os.environ.get("APERCU_RAPIDE") or "") == "1" or (os.environ.get("RENDU") or "") == "essai_pause":
        historique[-1]["essai"] = True                                     # essai : rangé à part sur le site, effacé au bout de 3 jours
    if DOUB: historique[-1]["filiere"] = "tiktok"                         # vidéo sur un son TikTok : rangée à part des sketchs
    if DOUB: historique[-1]["source_audio"] = sk["doublage"]["source"]; historique[-1]["theme"] = "Bande son : " + sk["doublage"]["source"]
    historique[-1]["couts"] = couts(); print(f"Dépenses : {historique[-1]['couts']}", flush=True)
    if libre and duree:
        try:
            import cartoon as _c; historique[-1]["couverture_ms"] = _c.COUVERTURE_MS[0]
        except Exception: pass
    if sk.get("titre_accroche"): historique[-1]["titre_affiche"] = sk["titre_accroche"]
    os.makedirs("episodes/sketchs", exist_ok=True)                         # le sketch de chaque vidéo : « Refaire », exemples 👍
    json.dump(sk, open(f"episodes/sketchs/{os.path.basename(base)}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(historique[-200:], open("episodes/historique.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if libre and not test and not THEME:
        n_ep = serie.enregistrer(sk, os.path.basename(base) + ".mp4")
        if n_ep: print(f"Série « {sk['serie_titre']} » : épisode {n_ep} enregistré", flush=True)
        if LOT and serie.a_faire()[0]:                                     # épisode suivant : le robot se relance tout seul
            import subprocess
            r_ = subprocess.run(["gh", "api", "-X", "POST", f"repos/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/workflows/emission.yml/dispatches",
                                 "-f", "ref=main", "-f", f"inputs[format]={fmt}", "-f", "inputs[serie]=1"], capture_output=True, text=True)
            print(f"Épisode suivant {'lancé' if r_.returncode == 0 else 'impossible à lancer : ' + r_.stderr[:200]}", flush=True)
        elif LOT:
            print("Série complète : tous les épisodes sont fabriqués.", flush=True)
    sortie = os.environ.get("GITHUB_OUTPUT")
    if sortie:
        with open(sortie, "a") as f:
            f.write(f"video={base}.mp4\nlegende={base}.txt\nnom={os.path.basename(base)}.mp4\nmois={jour[:7]}\ntitre={sk['sujet']}\n"
                    f"qualite={'ok' if video_ok and (not fiche or (fiche.get('note') or 0) >= SEUIL_PUB) and not REFAIRE else 'faible'}\nnote={round(fiche.get('note') or 0)}\n")
    if sortie:
        with open(sortie, "a") as f: f.write(f"chaine={os.environ.get('CHAINE', '')}\n")
    for t_ in RP.ENVOIS: t_.join(timeout=300)                              # sauvegardes en cours terminées, puis effacées (vidéo finie)
    for n_ in [SUITE_NOM, RP.nom_point("v1"), RP.nom_point("v2")]:
        if n_: RP.nettoyer(n_)
    PR.fini(True)
    print(f"Quota de l'API GitHub : {__import__('quota').resume()}", flush=True)
    print(f"OK : {base}.mp4 ({duree:.0f} s)")

if __name__ == "__main__":
    import reprise as _RP
    try: main()
    except _RP.EnPause as e: print(f"Fabrication en pause : reprise {e} lancée sur une nouvelle machine.", flush=True)
