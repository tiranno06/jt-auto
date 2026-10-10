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

def requete_post(canal, texte, url, mode, ia=True, service="tiktok", titre="", quand=None):
    if mode == "shareNow":
        planif = "mode: shareNow"
    else:
        quand = quand or (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        planif = f'mode: customScheduled\n      dueAt: "{quand}"'
    vignette = int(os.environ.get("COUVERTURE_MS") or 2500)
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
    r = subprocess.run(["gh", "release", "download", e["tag"], "-p", nom, "-p", txt, "-D", "sortie", "--clobber"], capture_output=True, text=True)
    if not os.path.exists(os.path.join("sortie", nom)): sys.exit(f"Vidéo introuvable dans la Release {e['tag']} : {r.stderr[:300]}")
    if e.get("legende") or not os.path.exists(os.path.join("sortie", txt)):   # la légende de l'historique fait foi (modifiable)
        open(os.path.join("sortie", txt), "w", encoding="utf-8").write(e.get("legende", ""))
    depot = os.environ.get("GITHUB_REPOSITORY"); serveur = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    url = f"{serveur}/{depot}/releases/download/{e['tag']}/{nom}"
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"video=sortie/{nom}\nlegende=sortie/{txt}\nurl={url}\n")
    print(f"Vidéo prête : {url}")

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
        e_ = next((h for h in json.load(open(HIST, encoding="utf-8")) if h.get("fichier") == os.path.basename(video)), {})
        os.environ.setdefault("TITRE_VIDEO", (e_.get("titre_affiche") or e_.get("titre") or "").strip())
        if e_.get("couverture_ms"): os.environ.setdefault("COUVERTURE_MS", str(int(e_["couverture_ms"])))
    except Exception: pass
    legende = open(legende_txt, encoding="utf-8").read().split("\n\nSources :")[0].strip()
    ok, erreur = False, None
    try:
        ok = publier(video, legende, url) is not None
    except Exception as e:
        erreur = str(e)[:300]; print(f"Publication automatique échouée : {erreur}")
    marquer(os.path.basename(video), ok, erreur, legende)
    if not ok:
        print("➡ Vidéo disponible sur le site pour publication en un clic.")
        sys.exit(1)
