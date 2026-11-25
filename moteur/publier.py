"""Publication TikTok automatique.
Ordre de préférence :
  1. Buffer (plan gratuit + API) : BUFFER_API_KEY — la vidéo doit être accessible par une URL publique
     (le robot utilise l'URL de la Release GitHub, d'où un dépôt public) ;
  2. Upload-Post (payant) : UPLOAD_POST_API_KEY + UPLOAD_POST_USER ;
  3. sinon rien : la vidéo reste dans les Releases.
Usage : python moteur/publier.py <video.mp4> <legende.txt> <url_publique_de_la_video>"""
import os, sys, json, uuid, mimetypes, datetime, urllib.request

# ------------------------------------------------------------------ Buffer (gratuit)
BUFFER = "https://api.buffer.com"

def _gql(requete, cle):
    req = urllib.request.Request(BUFFER, data=json.dumps({"query": requete}).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/json"})
    rep = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
    if rep.get("errors"): raise RuntimeError(f"Buffer : {rep['errors']}")
    return rep["data"]

def canaux(cle):
    """Comptes connectés à Buffer : {service: id} (tiktok, youtube, instagram…)."""
    out = {}
    if os.environ.get("BUFFER_CHANNEL_ID"): out["tiktok"] = os.environ["BUFFER_CHANNEL_ID"]
    for o in _gql("query { account { organizations { id name } } }", cle)["account"]["organizations"]:
        for c in _gql('query { channels(input: { organizationId: %s }) { id name service } }' % json.dumps(o["id"]), cle)["channels"]:
            out.setdefault(str(c.get("service", "")).lower(), c["id"])
    return out

def canal_tiktok(cle):
    c = canaux(cle).get("tiktok")
    if not c: raise RuntimeError("Aucun compte TikTok connecté à Buffer")
    return c

def _quand():
    """Heure de publication choisie dans l'appli (heure de Paris, ex. 2026-10-12T18:30) -> UTC ; None = tout de suite."""
    q = (os.environ.get("QUAND") or "").strip()
    if not q: return None
    from zoneinfo import ZoneInfo
    try: d = datetime.datetime.fromisoformat(q).replace(tzinfo=ZoneInfo("Europe/Paris"))
    except ValueError: return None
    if d <= datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5): return None
    return d.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _meta(service, ia, titre):
    if not ia: return ""
    if service == "tiktok": return "metadata: { tiktok: { isAiGenerated: true } }"
    if service == "youtube":
        return ('metadata: { youtube: { title: %s, isAiGenerated: true, madeForKids: false, categoryId: "23", privacy: public, notifySubscribers: true } }'
                % json.dumps(titre[:95], ensure_ascii=False))
    if service == "instagram": return "metadata: { instagram: { type: reel, shouldShareToFeed: true, isAiGenerated: true } }"
    return ""

def _couverture_ms(url):
    """Instant de couverture choisi par le moteur pour cette vidéo (historique), sinon réglage COUVERTURE_MS (2,5 s)."""
    try:
        nom = os.path.basename(str(url).split("?")[0])
        for h in reversed(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "historique.json"), encoding="utf-8"))):
            if h.get("fichier") == nom and h.get("couverture_ms"): return int(h["couverture_ms"])
    except Exception as _e: __import__("pannes").avale(_e)
    return int(os.environ.get("COUVERTURE_MS") or 2500)

def requete_post(canal, texte, url, mode, ia=True, service="tiktok", titre="", quand=None):
    if mode == "shareNow":
        planif = "mode: shareNow"
    else:
        quand = quand or (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        planif = f'mode: customScheduled\n      dueAt: "{quand}"'
    vignette = _couverture_ms(url)
    return f"""mutation {{
  createPost(input: {{
      text: {json.dumps(texte, ensure_ascii=False)}
      channelId: {json.dumps(canal)}
      schedulingType: automatic
      {planif}
      {_meta(service, ia, titre)}
      assets: [{{ video: {{ url: {json.dumps(url)}, metadata: {{ thumbnailOffset: {vignette} }} }} }}]
  }}) {{
    ... on PostActionSuccess {{ post {{ id }} }}
    ... on MutationError {{ message }}
  }}
}}"""

def _poster(cle, canal, service, legende, url, titre, quand):
    essais = ([("customScheduled", True), ("customScheduled", False)] if quand else
              [("shareNow", True), ("customScheduled", True), ("shareNow", False)])  # option « contenu généré par IA » cochée
    derniere = None
    for mode, ia in essais:
        try:
            rep = _gql(requete_post(canal, legende[:2200], url, mode, ia, service, titre, quand), cle)["createPost"]
            if rep.get("post"):
                print(f"Buffer {service} : publication {'programmée le ' + quand if quand else 'lancée'} ({mode}), post {rep['post']['id']}"
                      + ("" if ia else " — SANS l'étiquette IA (refusée par Buffer) : à cocher dans l'appli"))
                return rep
            derniere = rep.get("message")
        except Exception as e:
            derniere = e
        print(f"Buffer {service}, mode {mode}{'' if ia else ' sans étiquette IA'} refusé : {derniere}")
    raise RuntimeError(f"Buffer a refusé la publication {service} : {derniere}")

def publier_buffer(url, legende, titre=""):
    """TikTok toujours ; YouTube Shorts et Instagram Reels si activés dans la régie (et connectés à Buffer)."""
    cle = os.environ["BUFFER_API_KEY"]; c = canaux(cle); quand = _quand()
    if "tiktok" not in c: raise RuntimeError("Aucun compte TikTok connecté à Buffer")
    rep = _poster(cle, c["tiktok"], "tiktok", legende, url, titre, quand)
    for service, var in (("youtube", "PUBLIER_YOUTUBE"), ("instagram", "PUBLIER_INSTAGRAM")):
        if os.environ.get(var) != "1": continue
        if service not in c: print(f"{service} activé dans la régie mais aucun compte {service} connecté à Buffer : ignoré"); continue
        try: _poster(cle, c[service], service, legende, url, titre, quand)
        except Exception as e: print(f"{service} : {str(e)[:200]}")
    return rep

# ------------------------------------------------------------------ État réel des envois (Buffer)
_TYPES = {}

def _type(cle, nom):
    """Champs d'un type de l'API Buffer (lus une fois) : [(nom, genre, type, args obligatoires ?)]."""
    if nom not in _TYPES:
        q = ('query { __type(name: %s) { fields { name args { type { kind } } type { kind name ofType { kind name ofType { kind name } } } } } }'
             % json.dumps(nom))
        out = []
        for f in (_gql(q, cle).get("__type") or {}).get("fields") or []:
            t = f["type"]
            while t.get("ofType") and t["kind"] in ("NON_NULL", "LIST"): t = t["ofType"]
            out.append((f["name"], t["kind"], t.get("name"), any(a["type"]["kind"] == "NON_NULL" for a in f.get("args") or [])))
        _TYPES[nom] = out
    return _TYPES[nom]

def _selection(cle, nom, profond=1):
    """Tous les champs simples d'un type (et un niveau d'objets : erreur, notification…) pour une requête GraphQL."""
    morceaux = []
    for n, genre, t, oblig in _type(cle, nom):
        if oblig: continue
        if genre in ("SCALAR", "ENUM"): morceaux.append(n)
        elif genre == "OBJECT" and profond > 0 and t:
            sous = _selection(cle, t, profond - 1)
            if sous: morceaux.append(f"{n} {{ {sous} }}")
    return " ".join(morceaux)

def etat_post(cle, ident):
    """Tout ce que Buffer dit d'un envoi : statut (scheduled, sending, sent, error…), erreur, lien TikTok…"""
    return _gql("query { post(input: { id: %s }) { %s } }" % (json.dumps(ident), _selection(cle, "Post")), cle).get("post") or {}

def etat_canaux(cle):
    """Comptes connectés avec tout ce que Buffer en dit (déconnecté, file en pause, verrouillé…)."""
    out = []
    for o in _gql("query { account { organizations { id name } } }", cle)["account"]["organizations"]:
        out += _gql('query { channels(input: { organizationId: %s }) { %s } }' % (json.dumps(o["id"]), _selection(cle, "Channel", 0)), cle)["channels"]
    return out

# ------------------------------------------------------------------ Upload-Post (payant)
def publier_upload_post(video, legende):
    cle, utilisateur = os.environ["UPLOAD_POST_API_KEY"], os.environ["UPLOAD_POST_USER"]
    champs = [("user", utilisateur), ("platform[]", "tiktok"), ("title", legende[:2200]),
              ("privacy_level", os.environ.get("TIKTOK_VISIBILITE", "PUBLIC_TO_EVERYONE")), ("is_aigc", "true")]
    limite = uuid.uuid4().hex; corps = b""
    for nom, val in champs:
        corps += f"--{limite}\r\nContent-Disposition: form-data; name=\"{nom}\"\r\n\r\n{val}\r\n".encode()
    corps += (f"--{limite}\r\nContent-Disposition: form-data; name=\"video\"; filename=\"{os.path.basename(video)}\"\r\n"
              f"Content-Type: video/mp4\r\n\r\n").encode() + open(video, "rb").read() + f"\r\n--{limite}--\r\n".encode()
    req = urllib.request.Request("https://api.upload-post.com/api/upload", data=corps, method="POST",
                                 headers={"Authorization": f"Apikey {cle}", "Content-Type": f"multipart/form-data; boundary={limite}"})
    rep = urllib.request.urlopen(req, timeout=600).read().decode(); print("Upload-Post :", rep[:300]); return rep

def publier_parties(url1, legende, titre=""):
    """Son long en deux parties (idée 5 du 21 novembre) : la partie 1 à l'heure prévue, la partie 2 PARTIES_ECART heures après
    (même compte TikTok, par Buffer). Renvoie la réponse de la partie 1."""
    import parties
    cle = os.environ["BUFFER_API_KEY"]; c = canaux(cle)
    if "tiktok" not in c: raise RuntimeError("Aucun compte TikTok connecté à Buffer")
    quand = _quand(); titre = titre or os.environ.get("TITRE_VIDEO", "")
    rep = _poster(cle, c["tiktok"], "tiktok", parties.legende_partie(legende, 1), url1, titre, quand)
    base = datetime.datetime.strptime(quand, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc) if quand else datetime.datetime.now(datetime.timezone.utc)
    q2 = (base + datetime.timedelta(hours=parties.ecart_heures())).strftime("%Y-%m-%dT%H:%M:%SZ")
    try: _poster(cle, c["tiktok"], "tiktok", parties.legende_partie(legende, 2), url1.replace("_p1.mp4", "_p2.mp4"), titre + " (partie 2)", q2)
    except Exception as e: print(f"Partie 2 non programmée ({str(e)[:200]}) : à publier à la main depuis le site")
    return rep


def publier(video, legende, url):
    if os.environ.get("BUFFER_API_KEY"):
        return publier_buffer(url, legende, os.environ.get("TITRE_VIDEO", ""))
    if os.environ.get("UPLOAD_POST_API_KEY") and os.environ.get("UPLOAD_POST_USER"):
        return publier_upload_post(video, legende)
    print("Aucun service de publication configuré : la vidéo reste dans les Releases.")

HIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "historique.json")

def preparer():
    """Pour le bouton du site : retrouve la vidéo demandée (FICHIER) dans l'historique, la télécharge depuis
    la Release du mois et donne au workflow le chemin de la vidéo, de la légende et l'URL publique."""
    import subprocess
    nom = os.environ.get("FICHIER", "").strip(); forcer = os.environ.get("FORCER", "non").lower() in ("oui", "true", "1")
    hist = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else []
    e = next((h for h in hist if h.get("fichier") == nom), None)
    if not e: sys.exit(f"Vidéo inconnue : {nom}")
    if e.get("publie") is True and not forcer:
        print(f"{nom} est déjà publiée : rien à faire (choisir « forcer = oui » pour republier)."); return
    os.makedirs("sortie", exist_ok=True)
    txt = nom.replace(".mp4", ".txt")
    P_ = e.get("parties") or []
    if len(P_) == 2 and __import__("parties").actif() and os.environ.get("BUFFER_API_KEY") and os.environ.get("REDIFFUSION_RUN") != "1":
        r = subprocess.run(["gh", "release", "download", e["tag"], "-p", P_[0], "-p", P_[1], "-D", "sortie", "--clobber"], capture_output=True, text=True)
        if all(os.path.exists(os.path.join("sortie", p_)) for p_ in P_):     # son long (idée 5) : la partie 1 maintenant, la 2 ensuite
            open(os.path.join("sortie", P_[0].replace(".mp4", ".txt")), "w", encoding="utf-8").write(e.get("legende", ""))
            depot = os.environ.get("GITHUB_REPOSITORY"); serveur = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"video=sortie/{P_[0]}\nlegende=sortie/{P_[0].replace('.mp4', '.txt')}\nurl={serveur}/{depot}/releases/download/{e['tag']}/{P_[0]}\n")
            print(f"Vidéo en deux parties : {P_[0]} puis {P_[1]}"); return
        print("Parties introuvables dans les archives : la vidéo complète est publiée")
    r = subprocess.run(["gh", "release", "download", e["tag"], "-p", nom, "-p", txt, "-D", "sortie", "--clobber"], capture_output=True, text=True)
    if not os.path.exists(os.path.join("sortie", nom)): sys.exit(f"Vidéo introuvable dans la Release {e['tag']} : {r.stderr[:300]}")
    if e.get("legende") or not os.path.exists(os.path.join("sortie", txt)):   # la légende de l'historique fait foi (modifiable)
        open(os.path.join("sortie", txt), "w", encoding="utf-8").write(e.get("legende", ""))
    if os.environ.get("REDIFFUSION_RUN") == "1":                             # rediffusion (idée 40) : la vidéo est présentée comme telle
        t_ = open(os.path.join("sortie", txt), encoding="utf-8").read()
        open(os.path.join("sortie", txt), "w", encoding="utf-8").write(REDIF + "\n\n" + t_)
    depot = os.environ.get("GITHUB_REPOSITORY"); serveur = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    url = f"{serveur}/{depot}/releases/download/{e['tag']}/{nom}"
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"video=sortie/{nom}\nlegende=sortie/{txt}\nurl={url}\n")
    print(f"Vidéo prête : {url}")

REDIF = "♻️ On la remet pour ceux qui l'ont ratée 😂"

STATUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sortie", "statut_publication.json")

def marquer(fichier=None, ok=None, erreur=None, legende=None):
    """Note dans l'historique si la vidéo est publiée (rejoué tel quel si l'historique a changé entre-temps)."""
    if fichier is None:
        if not os.path.exists(STATUT): return
        d = json.load(open(STATUT, encoding="utf-8")); fichier, ok, erreur, legende = d["fichier"], d["publie"], d["erreur"], d.get("legende")
    else:
        os.makedirs(os.path.dirname(STATUT), exist_ok=True)
        json.dump({"fichier": fichier, "publie": ok, "erreur": erreur, "legende": legende}, open(STATUT, "w", encoding="utf-8"))
    if os.path.exists(HIST):
        hist = json.load(open(HIST, encoding="utf-8"))
        for e in hist:
            if e.get("fichier") == fichier:
                e["publie"] = ok; e["erreur"] = erreur
                if ok and legende: e["legende_publiee"] = legende[:300]               # texte réellement envoyé (sert aux statistiques)
                if ok and os.environ.get("QUAND"): e["programmee"] = os.environ["QUAND"]
                if ok and os.environ.get("REDIFFUSION_RUN") == "1":         # rediffusion : pas deux fois en 3 mois
                    import datetime as _d; e["rediffusee"] = (os.environ.get("QUAND") or _d.date.today().isoformat())[:10]
        json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    if sys.argv[1:] == ["--preparer"]:
        preparer(); sys.exit(0)
    if sys.argv[1:] == ["--marquer"]:
        marquer(); sys.exit(0)
    if sys.argv[1:] == ["--schema"]:                                       # repère le champ « contenu IA » de l'API Buffer
        cle = os.environ.get("BUFFER_API_KEY")
        q = "query { __schema { types { name kind enumValues { name } inputFields { name type { name kind ofType { name kind } } } } } }"
        try:
            for t in _gql(q, cle)["__schema"]["types"]:
                champs = t.get("inputFields") or []
                if t.get("kind") == "ENUM" and any(k in t["name"].lower() for k in ("youtube", "posttype", "sharemode")):
                    print(t["name"], "=", ", ".join(v["name"] for v in t.get("enumValues") or []))
                if any(k in t["name"].lower() for k in ("tiktok", "metadata", "createpost", "postinput")) or any("ai" in (c["name"] or "").lower() for c in champs):
                    print(t["name"], ":", ", ".join(f"{c['name']}<{(c['type'].get('name') or (c['type'].get('ofType') or {}).get('name'))}>" for c in champs))
        except Exception as e: print(f"Schéma Buffer illisible : {str(e)[:300]}")
        sys.exit(0)
    if sys.argv[1:2] == ["--diagnostic"]:                                  # état réel des derniers envois et du compte TikTok
        cle = os.environ.get("BUFFER_API_KEY")
        for c in etat_canaux(cle): print("Canal :", json.dumps(c, ensure_ascii=False)[:1500])
        print("Champs d'un envoi :", [f[0] for f in _type(cle, "Post")])
        print("Requêtes possibles :", [(f[0], f[3]) for f in _type(cle, "Query")])
        for i in sys.argv[2:]:
            try: print("Envoi", i, ":", json.dumps(etat_post(cle, i), ensure_ascii=False)[:3000])
            except Exception as e: print("Envoi", i, "illisible :", str(e)[:500])
        sys.exit(0)
    if sys.argv[1:] == ["--canaux"]:                                       # vérification : comptes connectés à Buffer (sans rien publier)
        cle = os.environ.get("BUFFER_API_KEY")
        if not cle: print("BUFFER_API_KEY absente des secrets GitHub."); sys.exit(0)
        try:
            for o in _gql("query { account { organizations { id name } } }", cle)["account"]["organizations"]:
                for c in _gql('query { channels(input: { organizationId: %s }) { id name service } }' % json.dumps(o["id"]), cle)["channels"]:
                    print(f"Buffer : compte {c.get('service')} « {c.get('name')} »" + ("  ← utilisé pour TikTok" if str(c.get("service", "")).lower() == "tiktok" else ""))
        except Exception as e: print(f"Buffer inaccessible : {str(e)[:300]}")
        sys.exit(0)
    video, legende_txt, url = sys.argv[1:4]
    try:                                                                   # titre (YouTube) et image de couverture depuis l'historique
        e_ = next((h for h in json.load(open(HIST, encoding="utf-8")) if h.get("fichier") == os.path.basename(video).replace("_p1.mp4", ".mp4")), {})
        os.environ.setdefault("TITRE_VIDEO", (e_.get("titre_affiche") or e_.get("titre") or "").strip())
        if e_.get("couverture_ms"): os.environ.setdefault("COUVERTURE_MS", str(int(e_["couverture_ms"])))
    except Exception as _e: __import__("pannes").avale(_e)
    legende = open(legende_txt, encoding="utf-8").read().split("\n\nSources :")[0].strip()
    try: legende = __import__("legende").completer(legende, video.replace("_p1.mp4", ".mp4"))   # jamais de lien ; hashtags ajoutés aux anciennes vidéos
    except Exception as e: print(f"légende gardée telle quelle ({str(e)[:120]})")
    ok, erreur = False, None
    partie1 = os.path.basename(video).endswith("_p1.mp4")
    try:
        if partie1: ok = publier_parties(url, legende) is not None
        else: ok = publier(video, legende, url) is not None
    except Exception as e:
        erreur = str(e)[:300]; print(f"Publication automatique échouée : {erreur}")
    marquer(os.path.basename(video).replace("_p1.mp4", ".mp4"), ok, erreur, legende)
    if not ok:
        print("➡ Vidéo disponible sur le site pour publication en un clic.")
        sys.exit(1)
