"""Site de pilotage (GitHub Pages, appli installable) en 4 onglets :
- Accueil : un seul bouton « Créer une vidéo » (lien TikTok, mon texte ou idée automatique ; court ou long),
  le suivi de la fabrication en cours et les 3 dernières vidéos ;
- Vidéos : une seule liste filtrable, avec publication (workflow publier.yml via Buffer), partage manuel, refaire, supprimer ;
- Statistiques : la chaîne, vidéos les plus vues, dépenses du mois, alertes ;
- Réglages : groupes repliables (crédits et outils, publication, style, écriture, avancé).
Les boutons du robot utilisent un jeton GitHub personnel, saisi une fois et gardé uniquement dans le navigateur.
Usage : python moteur/site.py  (dans le workflow, après la publication)"""
import html, json, os, shutil, subprocess

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE = os.path.join(RACINE, "site")
NB = int(os.environ.get("SITE_NB_VIDEOS", "15"))          # vidéos gardées par catégorie
PLEINES = int(os.environ.get("SITE_PLEINES", "6"))                                                # les plus récentes en pleine qualité (partage manuel), les autres allégées
PLAFOND_PLEINES = 650e6                                    # GitHub Pages refuse au-delà de 1 Go : on reste toujours bien en dessous
PLAFOND_SITE = 930e6
CACHE_WEB = os.path.join(RACINE, ".cache_site")            # versions allégées gardées d'une mise à jour à l'autre (cache du workflow)

def recuperer(e, dest):
    """Copie la vidéo depuis sortie/ ou la télécharge depuis la Release du mois."""
    local = os.path.join(RACINE, "sortie", e["fichier"])
    if os.path.exists(local): shutil.copy(local, dest); return True
    r = subprocess.run(["gh", "release", "download", e.get("tag") or f"emissions-{e['fichier'][:7]}", "-p", e["fichier"], "-D", os.path.dirname(dest), "--clobber"],
                       capture_output=True, text=True)
    if r.returncode: print(f"  vidéo introuvable {e['fichier']} : {r.stderr.strip()[:200]}")
    return os.path.exists(dest)

def allegee(e, dest):
    """Version légère pour regarder dans l'appli (720p, 30 images/s, ~5 Mo) : la vidéo pleine qualité reste dans les Releases
    (c'est elle qui est publiée). Gardée en cache d'une mise à jour du site à l'autre."""
    import tempfile
    os.makedirs(CACHE_WEB, exist_ok=True); c = os.path.join(CACHE_WEB, e["fichier"])
    if os.path.exists(c) and os.path.getsize(c) > 40e6: os.remove(c)        # un original rangé là par erreur : on refait la version légère
    if not os.path.exists(c):
        brut = os.path.join(tempfile.mkdtemp(), e["fichier"])               # téléchargé sous son vrai nom, hors du cache
        if not recuperer(e, brut): print(f"  {e['fichier']} : original introuvable"); return False
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", brut, "-vf", "scale=720:-2,fps=30", "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "27", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", c + ".tmp.mp4"], capture_output=True, text=True)
        if r.returncode == 0: os.replace(c + ".tmp.mp4", c)
        else: print(f"  version légère impossible pour {e['fichier']} : {r.stderr.strip()[:160]}")
        shutil.rmtree(os.path.dirname(brut), ignore_errors=True)
        if r.returncode: return False
    shutil.copy(c, dest); return True

def affiche(video, image, t=4.0):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                    "-vf", "scale=360:-2", "-q:v", "4", image])

def origine(e):
    """D'où vient la vidéo : « tiktok » (rejouée sur le son d'une vidéo TikTok), « texte » (idée ou script tapé) ou « auto »."""
    theme = str(e.get("theme") or "")
    if e.get("filiere") == "tiktok" or e.get("source_audio") or theme.startswith(("Bande son", "TIKTOK::")): return "tiktok"
    manuelle = e.get("manuel") or theme or str(e.get("decision") or "").startswith("vidéo manuelle")
    return "texte" if manuelle else "auto"

def repliques_de(e):
    """Répliques d'une vidéo TikTok (personnage, texte) pour « Corriger qui parle » : lues dans le sketch gardé de la vidéo."""
    if origine(e) != "tiktok": return []
    f = os.path.join(RACINE, "episodes", "sketchs", os.path.splitext(e["fichier"])[0] + ".json")
    try: sk = json.load(open(f, encoding="utf-8"))
    except (OSError, ValueError): return []
    return [[str(r.get("p", "")), str(r.get("t", ""))[:110]] for r in (sk.get("repliques") or [])][:60]


def construire():
    hist = json.load(open(os.path.join(RACINE, "episodes", "historique.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(RACINE, "episodes", "historique.json")) else []
    shutil.rmtree(SITE, ignore_errors=True); os.makedirs(os.path.join(SITE, "videos"))
    liste = []
    comptes = {}; total = 0; pleines = 0
    for e in reversed([h for h in hist if h.get("fichier")]):
        cat = "tiktok" if origine(e) == "tiktok" else "manuel" if e.get("manuel") else "court" if e.get("format") == "mini" else "long"
        if comptes.get(cat, 0) >= NB: continue                             # jusqu'à NB vidéos par onglet
        dest = os.path.join(SITE, "videos", e["fichier"])
        ok = False
        if pleines < PLEINES and recuperer(e, dest):                       # les plus récentes : pleine qualité (si le poids le permet)
            if total + os.path.getsize(dest) <= PLAFOND_PLEINES: ok = True; pleines += 1
            else: os.remove(dest)
        if not ok: ok = allegee(e, dest)
        if not ok: continue
        if total + os.path.getsize(dest) > PLAFOND_SITE:                   # jamais au-delà de la limite de GitHub Pages : la vidéo reste
            os.remove(dest); print(f"  {e['fichier']} : site plein, lue depuis les Releases"); continue   # visible (lue depuis les Releases)
        total += os.path.getsize(dest); comptes[cat] = comptes.get(cat, 0) + 1
        poster = e["fichier"].replace(".mp4", ".jpg"); affiche(dest, os.path.join(SITE, "videos", poster), (e.get("couverture_ms") or 4000) / 1000)
        liste.append(dict(titre=e.get("titre", ""), date=e.get("date", ""), fichier=e["fichier"], poster=poster, origine=origine(e),
                          essai=bool(e.get("essai")) or str(e.get("titre", "")).startswith("👀 Aperçu"),
                          legende=e.get("legende", ""), publie=e.get("publie"), vues=e.get("vues"),
                          format=e.get("format", ""), manuel=bool(e.get("manuel")), avis=e.get("avis", 0), note=e.get("note"), note_auteur=e.get("note_auteur"),
                          programmee=e.get("programmee"), couts=e.get("couts") or {}, duree=e.get("duree"),
                          likes=e.get("likes"), commentaires=e.get("commentaires"), partages=e.get("partages"),
                          voix_secours=("piper" in str(e.get("voix", "")).lower()),
                          source=e.get("source_audio") or "", reps=repliques_de(e)))
    faites = [h for h in hist if h.get("fichier")]
    vraies = [e for e in faites if not e.get("betisier")]                  # le bêtisier n'utilise aucun outil : il ne compte pas
    derniere = vraies[-1] if vraies else {}                                # voyants des outils payants : d'après la dernière vidéo
    outils = {"outils": derniere.get("outils") if isinstance(derniere.get("outils"), dict) else None,
              "date": derniere.get("date", ""), "titre": derniere.get("titre", "")}
    import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import marque
    nom = marque.NOM                                                       # nom de la chaîne
    conf = {"depot": os.environ.get("GITHUB_REPOSITORY", ""), "branche": os.environ.get("GITHUB_REF_NAME") or "main"}
    try:
        import profils_tiktok; conf["profils_connus"] = profils_tiktok.connus()   # liste de départ de l'onglet TikTok
        conf["heure_stats"] = __import__("stats").meilleure_heure_publication()   # heure de publication conseillée par les vues
        conf["abos_morts"] = sorted(__import__("alerte").morts())         # appareils qui ne reçoivent plus les alertes (empreintes)
    except Exception: conf["profils_connus"] = []
    try: st = json.load(open(os.path.join(RACINE, "episodes", "stats.json"), encoding="utf-8"))
    except (OSError, ValueError): st = {}
    try: alertes = json.load(open(os.path.join(RACINE, "episodes", "alertes.json"), encoding="utf-8"))[-15:]
    except (OSError, ValueError): alertes = []
    resume = {"compte": st.get("compte", ""), "maj": st.get("maj", ""), "videos": len(st.get("videos", [])),
              "vues": sum(v.get("vues", 0) for v in st.get("videos", [])), "liees": sum(1 for v in st.get("videos", []) if v.get("fichier")),
              "abonnes": st.get("abonnes"), "abonnes_hist": (st.get("abonnes_hist") or [])[-24 * 8:]}
    page = (PAGE.replace("__NOM__", html.escape(nom)).replace("__CONF__", json.dumps(conf)).replace("__STATS__", json.dumps(resume, ensure_ascii=False))
            .replace("__OUTILS__", json.dumps(outils, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__ALERTES__", json.dumps(alertes, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__DATA__", json.dumps(liste, ensure_ascii=False).replace("</", "<\\/")))
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(page)
    open(os.path.join(SITE, "derniere.txt"), "w").write((liste[0]["fichier"] if liste else "") + "\n")   # contrôle après mise en ligne
    print(f"Site : {total / 1e6:.0f} Mo de vidéos ({pleines} en pleine qualité)")
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    application(nom)
    print(f"Site : {len(liste)} vidéos")

# ------------------------------------------------------------------ application installable (PWA)
def icone(taille, marge=0.0):
    """Icône de l'appli = logo de la chaîne (tête de Jojo en plein petit drame, fond jaune à rayons)."""
    import marque
    return marque.logo(taille, marge=marge)

def application(nom):
    for g, f in (("500", "Poppins-Medium.ttf"), ("700", "Poppins-Bold.ttf")):          # police servie par le site lui-même (plus rapide)
        shutil.copy(os.path.join(RACINE, "polices", f), os.path.join(SITE, f"poppins-{g}.ttf"))
    for t in (192, 512):
        icone(t).save(os.path.join(SITE, f"logo-{t}.png"))
        icone(t, marge=0.1).save(os.path.join(SITE, f"logo-{t}-maskable.png"))
    icone(180).save(os.path.join(SITE, "logo-apple.png"))
    manifeste = {"name": f"{nom} — régie", "short_name": nom, "lang": "fr", "start_url": "./", "scope": "./", "id": "./?petits-dramas",
                 "display": "standalone", "orientation": "portrait", "background_color": "#0e0f17", "theme_color": "#ffd028",
                 "description": "Vérifier et publier les vidéos Petits.Dramas sur TikTok.",
                 # idée 1 : dans l'appli TikTok, « Partager » → Petits.Dramas : le lien arrive dans l'onglet TikTok, prêt à fabriquer
                 "share_target": {"action": "./?partage=1", "method": "GET", "params": {"title": "titre", "text": "texte", "url": "lien"}},
                 "icons": [{"src": f"logo-{t}.png", "sizes": f"{t}x{t}", "type": "image/png", "purpose": "any"} for t in (192, 512)] +
                          [{"src": f"logo-{t}-maskable.png", "sizes": f"{t}x{t}", "type": "image/png", "purpose": "maskable"} for t in (192, 512)]}
    json.dump(manifeste, open(os.path.join(SITE, "manifest.webmanifest"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(SITE, "sw.js"), "w").write(SW)

# Service worker : l'appli s'ouvre même hors connexion (dernière version de la page), sans jamais mettre en cache
# les vidéos (trop lourdes) ni les appels à GitHub.
SW = r"""const CACHE = "regie-v27";
const COQUILLE = ["./", "manifest.webmanifest", "logo-192.png", "logo-512.png", "poppins-500.ttf", "poppins-700.ttf"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(COQUILLE))); self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== CACHE).map(x => caches.delete(x))))); self.clients.claim(); });
const garder = (req, r) => { if (r && r.ok) { const c = r.clone(); caches.open(CACHE).then(x => x.put(req, c)); } return r; };
self.addEventListener("push", e => {
  let d = {}; try { d = e.data.json(); } catch (_) { d = { titre: "Petits.Dramas", texte: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.titre || "Petits.Dramas", { body: d.texte || "", icon: "logo-192.png", badge: "logo-192.png", data: { lien: d.lien || "./" } }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window" }).then(l => l.length ? l[0].focus() : self.clients.openWindow(e.notification.data.lien || "./")));
});
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || /\.(mp4|json|txt)$/.test(u.pathname)) return;
  if (e.request.mode === "navigate" || u.pathname.endsWith("/") || u.pathname.endsWith(".html")) {
    // page : toujours la plus récente si le réseau répond en moins de 3 s, sinon la copie gardée (ouverture instantanée hors ligne)
    e.respondWith(new Promise(ok => {
      let fini = false; const copie = () => caches.match(e.request).then(r => r || caches.match("./"));
      const minuteur = setTimeout(() => copie().then(r => { if (r && !fini) { fini = true; ok(r); } }), 6000);
      fetch(e.request, { cache: "no-store" }).then(r => { garder(e.request, r); if (!fini) { fini = true; clearTimeout(minuteur); ok(r); } })
        .catch(() => copie().then(r => { if (!fini) { fini = true; clearTimeout(minuteur); ok(r || Response.error()); } }));
    }));
    return;
  }
  // images, polices, icônes : copie gardée tout de suite, mise à jour en arrière-plan
  e.respondWith(caches.match(e.request).then(c => { const f = fetch(e.request).then(r => garder(e.request, r)).catch(() => c); return c || f; }));
});
"""

PAGE = r"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#0e0f17"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes">
<link rel="manifest" href="manifest.webmanifest"><link rel="icon" href="logo-192.png"><link rel="apple-touch-icon" href="logo-apple.png">
<title>__NOM__ — régie</title><meta name="apple-mobile-web-app-title" content="__NOM__">
<link rel="preload" href="poppins-700.ttf" as="font" type="font/ttf" crossorigin>
<style>
@font-face{font-family:Poppins;font-weight:500;font-display:swap;src:url(poppins-500.ttf) format("truetype")}
@font-face{font-family:Poppins;font-weight:700;font-display:swap;src:url(poppins-700.ttf) format("truetype")}
:root{--bg:#0e0f17;--carte:#181a26;--ligne:#2a2d3d;--texte:#f2f2f6;--doux:#9a9db0;--jaune:#ffd628;--rouge:#e3203a;--vert:#2fbf71;--orange:#ff9f1a;--bleu:#5aa9ff}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--texte);font-family:Poppins,system-ui,sans-serif;overflow-x:hidden}
header{padding:18px 16px 2px;text-align:center}
h1{margin:0;font-size:22px;color:var(--jaune);letter-spacing:.5px;text-shadow:0 2px 0 var(--rouge)}
.sous{color:var(--doux);font-size:13px;margin-top:4px}
main{max-width:560px;margin:0 auto;padding:8px 16px 80px}
.panneau{background:var(--carte);border:2px solid var(--ligne);border-radius:16px;padding:14px;margin:12px 0}
.auto{display:flex;align-items:center;gap:12px;margin:12px 0}
.auto .txt{flex:1;min-width:0}.auto b{display:block;font-size:15px}.auto small{color:var(--doux);font-size:12px;line-height:1.4;display:block}
.inter{position:relative;width:62px;height:34px;flex:none;border-radius:999px;background:#3a3d50;border:0;cursor:pointer;transition:background .2s}
.inter::after{content:"";position:absolute;top:4px;left:4px;width:26px;height:26px;border-radius:50%;background:#fff;transition:left .2s}
.inter.on{background:var(--vert)}.inter.on::after{left:32px}.inter:disabled{opacity:.45;cursor:wait}
details{margin-top:10px;font-size:13px;color:var(--doux)}summary{cursor:pointer;color:var(--bleu)}
.jeton{display:flex;gap:8px;margin-top:8px}
input,textarea{flex:1;min-width:0;font:inherit;font-size:15px;padding:11px;border-radius:10px;border:1px solid var(--ligne);background:#0e0f17;color:var(--texte)}
.carte{position:relative;display:flex;gap:12px;background:var(--carte);border:2px solid var(--ligne);border-radius:16px;padding:10px;margin:10px 0;cursor:pointer;transition:border-color .15s,transform .1s}
.carte:active{transform:scale(.99)}.carte.choisie{border-color:var(--jaune)}
.croix{position:absolute;top:8px;right:8px;width:34px;height:34px;border-radius:50%;border:none;background:rgba(0,0,0,.35);color:#fff;font-size:18px;line-height:34px;cursor:pointer;padding:0}
.croix:hover{background:#d33}.carte.supprimee{opacity:.35;pointer-events:none}
.apub{margin-top:8px;display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:999px;border:2px solid var(--ligne);background:transparent;color:inherit;font-size:14px;font-weight:700;cursor:pointer;max-width:100%}
.apub.on{background:var(--jaune);border-color:var(--jaune);color:#111}
.pulse{animation:pulse 1.2s ease-in-out 4}@keyframes pulse{50%{transform:scale(1.04);box-shadow:0 0 0 6px rgba(255,208,40,.35)}}
label.coche{display:flex;align-items:center;gap:10px;padding:8px 0;font-size:16px}label.coche input{width:22px;height:22px;flex:none;margin:0}
.carte img{width:84px;height:150px;object-fit:cover;border-radius:10px;flex:none;background:#000}
.carte.petite{padding:8px;margin:8px 0}.carte.petite img{width:54px;height:96px;border-radius:8px}
.infos{flex:1;min-width:0;display:flex;flex-direction:column;gap:6px;padding-right:30px}
.carte.petite .infos{padding-right:0}
.titre{font-weight:700;font-size:16px;line-height:1.25;overflow-wrap:anywhere}.date{color:var(--doux);font-size:13px}
.badge{align-self:flex-start;font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px}
.ok{background:rgba(47,191,113,.15);color:var(--vert)}.ko{background:rgba(227,32,58,.15);color:#ff6b7d}.att{background:rgba(255,159,26,.15);color:var(--orange)}
.etat{font-size:12px;color:var(--doux)}
.vide{text-align:center;color:var(--doux);margin:40px 0}
#barre{position:fixed;left:0;right:0;bottom:0;z-index:10;max-height:88vh;overflow-y:auto;background:rgba(14,15,23,.97);border-top:1px solid var(--ligne);padding:12px 16px calc(12px + env(safe-area-inset-bottom));backdrop-filter:blur(8px)}
.int{max-width:560px;margin:0 auto}
#choix{font-size:13px;color:var(--doux);margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:44px}
button{font:inherit;border:0;border-radius:14px;cursor:pointer}
#publier{width:100%;padding:15px;font-size:17px;font-weight:700;background:linear-gradient(90deg,#25f4ee,#fe2c55);color:#fff}
#publier:disabled{opacity:.4;cursor:not-allowed}
#publier.confirmer{background:var(--jaune);color:#111}
.ligne2{display:flex;gap:8px;margin-top:8px}
#plus{margin-top:8px;font-size:14px}#plus summary{cursor:pointer;color:var(--bleu);padding:6px 0}
#plus input{width:100%;margin-top:6px}
.alerte{background:#3a1d22;border:1px solid var(--rouge);border-radius:12px;padding:10px 12px;margin:0 0 12px;font-size:13px;overflow-wrap:anywhere;word-break:break-word}
.alerte.ok{background:#16301f;border-color:var(--vert)}
.barres{display:flex;flex-direction:column;gap:6px}.barres div{display:flex;align-items:center;gap:8px;font-size:12px}
.barres span.b{height:12px;background:var(--jaune);border-radius:6px;min-width:2px}
.chiffres{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.chiffres div{background:var(--carte);border:1px solid var(--ligne);border-radius:12px;padding:10px;min-width:0;overflow-wrap:anywhere}
.chiffres b{display:block;font-size:20px;color:var(--jaune)}
.second.actif{border-color:var(--jaune);color:var(--jaune)}
.second{flex:1;padding:11px 6px;font-size:13px;background:var(--carte);color:var(--texte);border:1px solid var(--ligne)}
.second:disabled{opacity:.4}
#suivi{font-size:13px;margin-top:8px;min-height:18px;color:var(--doux)}
#cote{position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:30;overflow:auto}
.cote-int{display:flex;gap:10px;padding:46px 10px 16px;justify-content:center;flex-wrap:wrap}
.cote-col{flex:1 1 300px;max-width:420px;color:#fff;text-align:center}.cote-col iframe,.cote-col video{width:100%;aspect-ratio:9/16;border:0;border-radius:12px;background:#000;margin-top:6px}
#coteFermer{position:fixed;top:10px;right:12px;z-index:31;width:auto;padding:6px 12px}
.qui{display:flex;gap:8px;align-items:center;margin:5px 0;font-size:.92em}.qui select{flex:0 0 auto;width:auto;margin:0}.qui span{flex:1;min-width:0}
.qui.change span{font-weight:700}
#toast{position:fixed;top:16px;left:50%;transform:translateX(-50%);background:var(--jaune);color:#111;font-weight:700;padding:10px 16px;border-radius:12px;display:none;z-index:20;max-width:90vw;text-align:center}
.onglets{position:sticky;top:0;z-index:5;display:flex;gap:6px;max-width:560px;margin:0 auto;padding:8px 12px;background:var(--bg)}
.onglet{flex:1;min-width:0;padding:6px 2px;font-size:min(13px,3.3vw);line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:700;background:var(--carte);color:var(--doux);border:1px solid var(--ligne);display:flex;flex-direction:column;align-items:center;gap:2px}
.onglet .ic{font-size:18px;line-height:1}.onglet .nom{max-width:100%;overflow:hidden;text-overflow:ellipsis}   /* icône au-dessus du nom : jamais de texte qui dépasse */
.onglet.actif{background:var(--jaune);color:#111;border-color:var(--jaune)}
h2{margin:0 0 10px;font-size:17px}
h3{margin:18px 0 4px;font-size:15px;color:var(--jaune)}
label{display:block;font-size:13px;color:var(--doux);margin:12px 0}
label>input,label>select,label>textarea{display:block;width:100%;box-sizing:border-box;margin-top:6px}   /* la case reste dans son cadre */
select{display:block;width:100%;margin-top:6px;font:inherit;font-size:15px;padding:11px;border-radius:10px;border:1px solid var(--ligne);background:#0e0f17;color:var(--texte)}
label .jeton{margin-top:6px}
.note{font-size:12.5px;color:var(--doux);line-height:1.45}
.prog{margin:10px 0 4px}.prog .haut{display:flex;justify-content:space-between;gap:8px;font-size:13.5px;font-weight:600}
.prog .barre{height:14px;border-radius:8px;background:var(--ligne);overflow:hidden;margin:6px 0 4px}
.prog .plein{height:100%;border-radius:8px;background:linear-gradient(90deg,#25f4ee,#fe2c55);transition:width 1s linear}
.prog.ok .plein{background:#2ecc71}.prog.ko .plein{background:#e74c3c}
.prog .bas{display:flex;justify-content:space-between;gap:8px;font-size:12.5px;color:var(--doux)}
.action{display:block;width:100%;margin:8px 0;padding:14px;font-size:15px;font-weight:700;background:var(--carte);color:var(--texte);border:1px solid var(--ligne)}
.action:disabled{opacity:.45}
.lien{display:block;padding:11px 0;color:var(--bleu);text-decoration:none;border-bottom:1px solid var(--ligne);font-size:14px}.lien:last-child{border:0}
.gros{display:block;width:100%;padding:20px;font-size:20px;font-weight:700;background:var(--jaune);color:#111;border-radius:18px;box-shadow:0 4px 0 var(--rouge)}
.gros:active{transform:translateY(2px);box-shadow:0 2px 0 var(--rouge)}
.lancer{background:linear-gradient(90deg,#25f4ee,#fe2c55);color:#fff;box-shadow:none;font-size:18px;padding:16px;margin-top:14px}
.opts{display:grid;gap:8px;margin:6px 0}.opts.deux{grid-template-columns:1fr 1fr}
.opt{display:flex;align-items:center;gap:12px;width:100%;text-align:left;padding:13px;background:var(--bg);border:2px solid var(--ligne);color:var(--texte);font-size:15px;font-weight:700}
.opt small{display:block;font-weight:500;color:var(--doux);font-size:12px}.opt .ico{font-size:24px;flex:none}
.opt.on{border-color:var(--jaune);background:#22221a}
.etape{font-size:13px;color:var(--doux);margin:14px 0 2px;font-weight:700}
#bandeauCnx{display:flex;align-items:center;gap:10px}#bandeauCnx span{flex:1}
details.groupe{background:var(--carte);border:2px solid var(--ligne);border-radius:16px;padding:12px 14px;margin:12px 0;color:var(--texte);font-size:inherit}
details.groupe>summary{list-style:none;color:var(--texte);font-size:17px;font-weight:700;display:flex;align-items:center;gap:8px}
details.groupe>summary::-webkit-details-marker{display:none}
details.groupe>summary::after{content:"▾";margin-left:auto;color:var(--doux);transition:transform .2s}
details.groupe[open]>summary::after{transform:rotate(180deg)}
.voyant{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--ligne);font-size:14px}
.voyant span.t{flex:1;min-width:0}.voyant a{color:var(--bleu);font-size:13px;text-decoration:none;flex:none}
.point{width:14px;height:14px;border-radius:50%;flex:none;background:#5a5d70}.point.vert{background:var(--vert)}.point.rouge{background:var(--rouge)}.point.orange{background:var(--orange)}
.filtres{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 6px}
.filtres .chip.on{background:var(--jaune);color:#111;border-color:var(--jaune)}
textarea{resize:vertical}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 10px}
.chip{padding:8px 12px;border-radius:999px;font-size:13px;background:var(--carte);color:var(--texte);border:1px solid var(--ligne)}
#jours .chip{width:40px;padding:8px 0;color:var(--doux)} #jours .chip.on{background:var(--jaune);color:#111;border-color:var(--jaune)}
.creneau{display:flex;gap:6px;align-items:center;margin:6px 0}
.creneau .heure{display:flex;gap:4px;flex:0 0 130px} .creneau .heure select{flex:1;padding:10px 2px;margin:0} .creneau select{flex:1;min-width:0;margin:0} .creneau .second{flex:0 0 42px;padding:9px 0}
.auto-h{flex:0 0 130px;font-weight:700;color:var(--jaune);text-align:center}
label>textarea{display:block;width:100%;margin-top:6px;box-sizing:border-box}
video{width:100%;border-radius:12px;margin:0 0 8px;max-height:34vh;background:#000;display:none}
#cadreVideo{position:relative}
#fermer{position:absolute;top:-4px;right:0;width:40px;height:40px;padding:0;border-radius:50%;font-size:20px;font-weight:700;line-height:40px;background:rgba(0,0,0,.65);color:#fff;border:1px solid rgba(255,255,255,.35);z-index:2}
@media (max-width:899px){body:not(.lecture) #barre{display:none}}
@media (min-width:900px){
  body[data-onglet="videos"] header, body[data-onglet="videos"] main{margin-right:420px}
  .onglets{max-width:560px;margin-left:auto;margin-right:auto}
  body[data-onglet="videos"] .onglets{margin-left:24px;margin-right:444px;max-width:none}
  main{max-width:760px;padding:8px 24px 40px !important}
  body[data-onglet="videos"] main{max-width:none}
  #liste{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:0 14px}
  #barre{left:auto;right:0;top:0;bottom:0;width:420px;max-height:none;border-top:0;border-left:1px solid var(--ligne);overflow:auto;padding:24px;display:flex;align-items:flex-start}
  #barre .int{width:100%}
  #barre video{max-height:62vh}
  body:not(.lecture) #fermer{display:none}
}
@media (max-width:380px){.opts.deux{grid-template-columns:1fr}}
</style></head><body data-onglet="accueil">
<header><h1><img src="logo-192.png" alt="" style="width:44px;height:44px;border-radius:12px;vertical-align:-10px;margin-right:10px">__NOM__</h1><div class="sous">Régie de la chaîne</div>
<button id="installer" style="display:none;margin-top:10px;padding:9px 16px;font-size:14px;font-weight:700;background:var(--jaune);color:#111">📲 Installer l'application</button></header>
<nav class="onglets"><button class="onglet actif" data-o="accueil"><span class="ic">🏠</span><span class="nom">Accueil</span></button><button class="onglet" data-o="videos"><span class="ic">🎬</span><span class="nom">Vidéos</span></button><button class="onglet" data-o="tiktok"><span class="ic">🎵</span><span class="nom">TikTok</span></button><button class="onglet" data-o="stats"><span class="ic">📊</span><span class="nom">Stats</span></button><button class="onglet" data-o="config"><span class="ic">⚙️</span><span class="nom">Réglages</span></button></nav>
<main>
 <!-- ======================================================== ACCUEIL -->
 <div id="o-accueil">
  <section class="panneau" id="bandeauCnx" style="display:none"><span class="note">🔑 Connectez la régie une fois pour lancer et publier des vidéos.</span><button class="second" id="allerCnx" style="flex:none;padding:10px 14px">Connecter</button></section>
  <div id="alerteCredit"></div>
  <section class="panneau" id="nouveauTk" style="display:none"></section>
  <button class="gros" id="creerBtn">➕ Créer une vidéo</button>
  <section class="panneau" id="creer" style="display:none">
    <div class="etape">1. À partir de quoi ?</div>
    <div class="opts">
      <button class="opt on" data-src="texte"><span class="ico">✍️</span><span>Mon texte<small>Une idée ou un script que je tape</small></span></button>
      <button class="opt" data-src="idee"><span class="ico">💡</span><span>Idée automatique<small>Le robot choisit le sujet</small></span></button>
    </div>
    <div id="mTexteBloc">
      <label>Ce que je tape<select id="mMode">
        <option value="idee">💡 Une idée : le robot écrit le sketch</option>
        <option value="script">📝 Mon script : joué mot pour mot</option></select></label>
      <label id="mTexteL"><span id="mAide">Idée / thème de la vidéo</span><textarea id="mTexte" rows="5" maxlength="1800" placeholder="Ex. : Jojo essaie de résilier son abonnement de salle de sport, mais le conseiller ne le laisse jamais partir."></textarea></label>
      <label id="mStyleL">Ton<select id="mStyle"><option value="">Comme d'habitude (humour noir)</option><option value="Ton encore plus absurde et délirant.">Plus absurde</option><option value="Ton plus méchant et plus cash.">Plus méchant</option><option value="Ton plus tendre, humour bienveillant.">Plus tendre</option></select></label>
    </div>
    <p class="note" id="mAutoNote" style="display:none">Le robot trouve un sujet tout seul et écrit le sketch.</p>
    <div class="etape">2. Quelle durée ?</div>
    <div class="opts deux">
      <button class="opt on" data-fmt="mini"><span class="ico">⚡</span><span>Court<small>Gag éclair, 15-25 s</small></span></button>
      <button class="opt" data-fmt="libre"><span class="ico">🎭</span><span>Long<small>Sketch, plus d'1 min</small></span></button>
    </div>
    <label class="ligne"><input type="checkbox" id="mApercu"> Aperçu rapide (10 secondes, environ 8 min) : pour juger le style avant la vraie vidéo</label>
    <button class="gros lancer" id="mCreer">🎬 Lancer la fabrication</button>
  </section>
  <section class="panneau"><h2>⏳ Fabrication en cours</h2><div class="progressions"></div><div id="mSuivi" class="note" data-libre="1">Aucune fabrication lancée depuis cet appareil.</div></section>
  <section class="panneau"><h2>🆕 Dernières vidéos</h2><div id="recents"></div>
    <button class="second" id="toutVoir" style="width:100%;margin-top:4px">Voir toutes les vidéos</button></section>
 </div>
 <!-- ======================================================== VIDÉOS -->
 <div id="o-videos" style="display:none">
  <div class="filtres" id="filtres">
    <button class="chip on" data-f="tout">Toutes</button><button class="chip" data-f="court">⚡ Courtes</button><button class="chip" data-f="long">🎭 Longues</button>
    <button class="chip" data-f="texte">✍️ Depuis un texte</button><button class="chip" data-f="essais" title="Aperçus et essais : effacés tout seuls au bout de 3 jours">🧪 Essais</button></div>
  <div id="enteteTk" style="display:none" class="panneau"><b>🎵 Vidéos sur des sons TikTok</b> <button class="second" id="retourTk" style="flex:none;padding:8px 12px">← Onglet TikTok</button></div>
  <div id="liste"></div>
 </div>
 <!-- ======================================================== SONS TIKTOK (à part des sketchs) -->
 <div id="o-tiktok" style="display:none">
  <section class="panneau"><h2>⏳ Fabrication en cours</h2><div class="progressions"><p class="note">Aucune fabrication en cours.</p></div></section>
  <section class="panneau"><h2>🔗 Une vidéo sur un son TikTok</h2>
    <label>Lien de la vidéo TikTok<input id="tkLien" type="url" inputmode="url" placeholder="https://www.tiktok.com/@compte/video/…"></label>
    <button class="second" id="tkColler" style="width:100%;margin:6px 0">📋 Coller le lien TikTok (copié dans l'appli TikTok)</button>
    <p class="note">3 min au plus. Nos personnages rejouent le son ; le compte d'origine est crédité. ⚠️ Sans accord du créateur, TikTok peut couper le son : privilégiez vos vidéos ou des sons libres.</p>
    <button class="gros lancer" id="tkCreer">🎬 Fabriquer sur ce son</button>
    <div id="tkSuivi" class="note"></div></section>
  <section class="panneau"><h2>🎵 Mes profils TikTok</h2>
    <p class="note">Un profil par ligne (@pseudo ou lien du profil). Le robot y prend une vidéo au hasard, jamais déjà utilisée, et fabrique la vidéo sur son son.</p>
    <label>Profils<div class="jeton"><textarea data-var="PROFILS_TIKTOK" data-def="" data-texte="1" maxlength="3000" rows="5" placeholder="@profil1&#10;@profil2&#10;https://www.tiktok.com/@profil3"></textarea><button class="second" data-enr="PROFILS_TIKTOK" style="flex:none;padding:10px 14px">OK</button></div></label>
    <button class="second" id="tkConnus" style="width:100%;margin-bottom:6px">➕ Ajouter les profils déjà connus</button>
    <p class="note" id="tkConnusNote"></p>
    <button class="action" id="tkHasard">🎲 Une vidéo maintenant (son au hasard des profils)</button>
    <div id="tkSuiviH" class="note"></div>
    <div class="jeton" style="align-items:center"><button class="action" id="tkSerie" style="margin:0">🎲 Plusieurs vidéos à la chaîne</button>
      <input id="tkNb" type="number" min="1" max="10" value="3" inputmode="numeric" aria-label="Nombre de vidéos à la chaîne" style="flex:none;width:72px;text-align:center;font-size:17px;font-weight:700"></div>
    <p class="note">Choisissez le nombre (1 à 10) puis touchez le bouton : le robot fabrique ces vidéos l'une après l'autre, chacune sur un son différent pris au hasard dans vos profils. Inutile d'attendre la fin d'une vidéo.</p>
    <div id="tkSuiviS" class="note"></div></section>
  <section class="panneau"><h2>⏰ Vidéos TikTok automatiques</h2>
    <p class="note">Planning à part : il ne touche jamais au planning des sketchs.</p>
    <div class="auto"><div class="txt"><b>Activées</b><small>Une vidéo sur un son des profils à chaque heure ci-dessous.</small></div><button class="inter" data-var="FREQUENCE_TIKTOK" data-def="0" data-bascule="1"></button></div>
    <label>Heures (séparées par « ; »)<div class="jeton"><input data-var="HEURE_TIKTOK" data-def="14:00" data-texte="1" maxlength="60" placeholder="ex. 14:00 ; 21:30"><button class="second" data-enr="HEURE_TIKTOK" style="flex:none;padding:10px 14px">OK</button></div></label>
    <p class="note">Vidéo prête 20 à 40 min après l'heure. S'il n'y a aucun son utilisable, pas de vidéo cette fois (jamais de sketch à la place).</p></section>
  <section class="panneau" id="pubAuto"><h2>📤 Publication automatique</h2>
    <p class="note">Cochez « À publier » sur les vidéos que vous avez vérifiées : chaque jour à l'heure choisie, le robot publie sur TikTok la plus ancienne vidéo cochée pas encore publiée (dans l'ordre où vous les avez cochées).</p>
    <div class="auto"><div class="txt"><b>Activée</b><small>Une vidéo cochée publiée par jour, même appli fermée.</small></div><button class="inter" data-var="PUBLI_AUTO" data-def="0" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Heure choisie par les statistiques</b><small>L'heure où vos vidéos font le plus de vues (sinon l'heure fixe ci-dessous).</small></div><button class="inter" data-var="PUBLI_HEURE_AUTO" data-def="0" data-bascule="1"></button></div>
    <label>Heure de publication (heure de Paris)<div class="jeton"><input data-var="PUBLI_HEURE" data-def="18:00" data-texte="1" maxlength="5" type="time" placeholder="18:00"><button class="second" data-enr="PUBLI_HEURE" style="flex:none;padding:10px 14px">OK</button></div></label>
    <p class="note" id="pubResume"></p></section>
  <section class="panneau"><h2>🎬 Mes vidéos TikTok</h2><div id="listeTk"></div></section>
 </div>
 <!-- ======================================================== STATISTIQUES -->
 <div id="o-stats" style="display:none"></div>
 <!-- ======================================================== RÉGLAGES -->
 <div id="o-config" style="display:none">
  <section class="panneau" id="cfgConnexion"><h2>🔑 Connecter la régie</h2>
    <p class="note">À faire une seule fois par appareil : collez votre clé GitHub de régie (elle reste dans ce navigateur).
    Pas de clé ? <a style="color:var(--bleu)" href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">Créer la clé</a> : dépôt <b>jt-auto</b>, droits <b>Actions</b> et <b>Variables</b> en « Read and write ».</p>
    <div class="jeton"><input id="jeton2" type="password" placeholder="github_pat_…" autocomplete="off"><button class="second" id="garder2" style="flex:none;padding:10px 14px">Connecter</button></div>
  </section>
  <p class="note" id="cfgEtat"></p>
  <details class="groupe" open><summary>🗂️ Onglets affichés</summary>
    <p class="note">Décochez les onglets que vous n'utilisez pas (sur tous vos appareils). 🎵 TikTok et ⚙️ Réglages restent toujours là.</p>
    <label class="coche"><input type="checkbox" data-onglet-vu="accueil"> 🏠 Accueil</label>
    <label class="coche"><input type="checkbox" data-onglet-vu="videos"> 🎬 Vidéos (sketchs)</label>
    <label class="coche"><input type="checkbox" data-onglet-vu="stats"> 📊 Stats</label>
  </details>

  <details class="groupe" open><summary>💳 Crédits et outils <span id="resumeOutils"></span></summary>
    <p class="note" id="outilsDate"></p>
    <div id="voyants"></div>
    <button class="action" id="verifCredits">🔍 Vérifier maintenant (Claude, Mistral, Gemini, ElevenLabs, Modal)</button>
    <p class="note" id="suiviCredits"></p>
    <div class="auto"><div class="txt"><b>💰 Mode économique</b><small>Garde Claude, ElevenLabs et les décors IA, mais dépense environ 3 à 5 fois moins de crédit Claude : Sonnet au lieu d'Opus, 1 premier jet, 2 réécritures au plus, sans public test ni tendances.</small></div><button class="inter" data-var="MODE_ECO" data-def="0" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Voix ElevenLabs</b><small>Voix réalistes (rires, colère). Coupé : voix gratuites.</small></div><button class="inter" data-var="ELEVENLABS" data-def="1" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Décors générés par IA</b><small>Un décor par scène (Modal). Coupé : décors dessinés.</small></div><button class="inter" data-var="DECORS" data-def="1" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Contrôle de la vidéo finie</b><small>Claude regarde la vidéo avant publication ; défaut grave = pas de publication auto.</small></div><button class="inter" data-var="CONTROLE_VIDEO" data-def="1" data-bascule="1"></button></div>
    <p class="note">Sans crédit, le robot passe tout seul aux outils gratuits : la vidéo sort quand même.</p>
  </details>

  <details class="groupe"><summary>📤 Publication</summary>
    <div class="auto">
      <div class="txt"><b id="autoTitre">Publication automatique</b><small id="autoAide">Connectez la régie pour utiliser ce réglage.</small></div>
      <button class="inter" id="inter" aria-label="Publication automatique" disabled></button>
    </div>
    <h3>Programme</h3>
    <label>Type des vidéos automatiques<select id="selFormat" class="perso">
      <option value="cycle">⭐ Cycle : 3 gags éclair puis 1 sketch long</option>
      <option value="seq">🧩 Ma séquence (je compose l'ordre)</option>
      <option value="mini">⚡ Gags éclair uniquement</option>
      <option value="libre">🎭 Sketchs longs uniquement</option></select></label>
    <div id="seqBloc" style="display:none">
      <p class="note">L'ordre se répète en boucle. Touchez une étiquette pour la retirer.</p>
      <div id="seqChips" class="chips"></div>
      <div class="ligne2"><button class="second perso" data-ajout="mini">+ ⚡ Gag</button><button class="second perso" data-ajout="libre">+ 🎭 Long</button></div>
      <button class="action perso" id="seqEnr">Enregistrer la séquence</button>
    </div>
    <h3>Planning</h3>
    <label>Rythme<select data-var="FREQUENCE" data-def="1"><option value="1">Tous les jours cochés</option><option value="2">Un jour sur deux</option><option value="3">Un jour sur trois</option><option value="0">⏸ Pause (le robot ne produit plus)</option><option value="2x" hidden>Deux par jour (ancien réglage)</option></select></label>
    <p class="note" style="margin-bottom:4px">Jours de fabrication</p>
    <div id="jours" class="chips"></div>
    <p class="note" style="margin-bottom:4px">Heures (Paris) et type de vidéo</p>
    <div id="creneaux"></div>
    <div class="ligne2"><button class="second perso" id="ajCreneau">+ Un créneau</button><button class="second perso" id="ajAuto">+ Créneau 📊 auto</button></div>
    <button class="action perso" id="planEnr">Enregistrer le planning</button>
    <p class="note">Vidéo prête 20 à 40 min après l'heure. « 📊 auto » : l'heure qui fait le plus de vues.</p>
    <h3>Plateformes</h3>
    <p class="note">TikTok toujours. Les autres : connectez d'abord le compte dans Buffer.</p>
    <div class="auto"><div class="txt"><b>YouTube Shorts</b><small>Publie aussi sur YouTube.</small></div><button class="inter" data-var="PUBLIER_YOUTUBE" data-def="0" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Instagram Reels</b><small>Compte Instagram professionnel requis.</small></div><button class="inter" data-var="PUBLIER_INSTAGRAM" data-def="0" data-bascule="1"></button></div>
    <label>Compte TikTok de la chaîne (pour les statistiques)<div class="jeton"><input data-var="TIKTOK_COMPTE" data-def="" data-texte="1" maxlength="40" placeholder="votre pseudo, sans @"><button class="second" data-enr="TIKTOK_COMPTE" style="flex:none;padding:10px 14px">OK</button></div></label>
    <p class="note" id="statsEtat"></p>
  </details>

  <details class="groupe"><summary>🎨 Style</summary>
    <label>Personnages<select data-var="PERSONNAGES" data-def="humains"><option value="humains">Adultes style toons, différents à chaque vidéo (recommandé)</option><option value="marionnettes">Anciennes marionnettes de la chaîne</option></select></label>
    <label>Montage<select data-var="MONTAGE" data-def="large"><option value="large">Plan large : les personnages toujours à l'image, caméra fixe (recommandé)</option><option value="dynamique">Dynamique : beaucoup de plans, zooms et caméra vivante</option><option value="simple">Simple : un plan par réplique</option></select></label>
    <div class="auto"><div class="txt"><b>Rendu détaillé</b><small>Tenues, visages, décors et plans soignés (gratuit).</small></div><button class="inter" data-var="RENDU_DETAILLE" data-def="1" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Accroche choc en ouverture</b><small>La réplique la plus intrigante dès la 1re seconde.</small></div><button class="inter" data-var="ACCROCHE" data-def="0" data-bascule="1"></button></div>
    <label>Voix des personnages<select data-var="VOIX_PERSOS" data-def="bibliotheque"><option value="bibliotheque">Voix de la bibliothèque ElevenLabs</option><option value="sur_mesure">🎙️ Voix sur mesure de la chaîne</option></select></label>
    <label>Prononciation (mots mal lus)<div class="jeton"><textarea data-var="PRONONCIATION" data-def="" data-texte="1" maxlength="1500" rows="2" placeholder="Ex. : Kévin=Kévinne ; Lidl=Lidle"></textarea><button class="second" data-enr="PRONONCIATION" style="flex:none;padding:10px 14px">OK</button></div></label>
    <p class="note">Une règle « mot=comment il se dit », séparées par « ; ».</p>
  </details>

  <details class="groupe"><summary>✍️ Écriture</summary>
    <label>Ton de l'humour<select data-var="TON" data-def="clash"><option value="clash">Clash, mauvaise foi assumée (recommandé)</option><option value="farfelu">Farfelu et ironique</option><option value="piquant">Satire piquante</option><option value="absurde">Absurde total</option></select></label>
    <label>Auteur (modèle Claude)<select data-var="MODELE_CLAUDE" data-def="claude-opus-5-5"><option value="claude-opus-5-5">Opus (le plus drôle, recommandé)</option><option value="claude-sonnet-5-5">Sonnet (économique)</option></select></label>
    <label>Note minimale pour fabriquer<select data-var="QUALITE_MIN" data-def="85"><option value="90">90/100</option><option value="85">85/100 (recommandé)</option><option value="80">80/100</option><option value="75">75/100</option><option value="70">70/100</option><option value="0">Toujours fabriquer</option></select></label>
    <label>Réécritures au plus<select data-var="MAX_REECRITURES" data-def="4"><option value="4">4 (recommandé)</option><option value="2">2 (économique)</option><option value="6">6 (le plus exigeant)</option></select></label>
    <div class="auto"><div class="txt"><b>Public test</b><small>3 spectateurs virtuels critiquent le sketch pour l'améliorer.</small></div><button class="inter" data-var="PUBLIC_TEST" data-def="1" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>S'inspirer des tendances</b><small>Regarde les sujets qui buzzent cette semaine.</small></div><button class="inter" data-var="TENDANCES" data-def="1" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Petites étapes en économique</b><small>Idées, jury et relecture sur un modèle moins cher.</small></div><button class="inter" data-var="ETAPES_ECO" data-def="0" data-bascule="1"></button></div>
    <h3>Personnalités</h3>
    <label>Caractères<select data-var="PERSONNALITES" data-def="fixes">
      <option value="fixes">Fixes : chacun garde son caractère (recommandé)</option>
      <option value="libres">Libres : adaptés à chaque histoire</option></select></label>
    <p class="note">Jojo, Kévin et Lila sont les rôles d'écriture ; le dessin des personnages change à chaque vidéo.</p>
    <label>Jojo<div class="jeton"><textarea data-var="PERSO_JOJO" data-def="le pote radin et de mauvaise foi, qui ne lâche jamais rien et a toujours une excuse prête" data-texte="1" maxlength="300" rows="2"></textarea><button class="second" data-enr="PERSO_JOJO" style="flex:none;padding:10px 14px">OK</button></div></label>
    <label>Kévin<div class="jeton"><textarea data-var="PERSO_KEVIN" data-def="le naïf un peu mytho, roi des plans foireux, qui croit tout ce qu'on lui dit et s'enfonce à chaque réplique" data-texte="1" maxlength="300" rows="2"></textarea><button class="second" data-enr="PERSO_KEVIN" style="flex:none;padding:10px 14px">OK</button></div></label>
    <label>Lila<div class="jeton"><textarea data-var="PERSO_LILA" data-def="la lucide cash, qui s'énerve vite et balance tout haut les vérités que personne n'ose dire" data-texte="1" maxlength="300" rows="2"></textarea><button class="second" data-enr="PERSO_LILA" style="flex:none;padding:10px 14px">OK</button></div></label>
    <h3>Séries</h3>
    <label>Enchaînement des vidéos<select data-var="EPISODES" data-def="aleatoire">
      <option value="aleatoire">Une histoire différente à chaque fois</option>
      <option value="serie">En série : la suite d'une vidéo à l'autre</option></select></label>
    <label>Épisodes par série<select data-var="EPISODES_PAR_SERIE" data-def="5"><option value="3">3</option><option value="5">5 (recommandé)</option><option value="8">8</option><option value="10">10</option></select></label>
    <label>Format des épisodes<select id="serieFormat" class="perso"><option value="mini">⚡ Gags éclair</option><option value="libre">🎭 Sketchs longs</option></select></label>
    <button class="action perso" id="serieLot">🎬 Fabriquer toute la série d'un coup</button>
    <div id="suiviSerie" class="note"></div>
  </details>

  <details class="groupe"><summary>🛠️ Avancé</summary>
    <h3>Seuils de qualité</h3>
    <label>Note minimale pour publier tout seul<select data-var="SEUIL_PUBLICATION" data-def="80"><option value="90">90/100</option><option value="85">85/100</option><option value="80">80/100 (recommandé)</option><option value="75">75/100</option><option value="70">70/100</option></select></label>
    <label>Objectif d'écriture (réécrit jusqu'à cette note)<select data-var="SEUIL_QUALITE" data-def="90"><option value="95">95/100 (très rare)</option><option value="90">90/100 (recommandé)</option><option value="85">85/100</option><option value="80">80/100</option><option value="75">75/100</option></select></label>
    <label>Sujets essayés au plus<select data-var="SUJETS_MAX" data-def="3"><option value="2">2 (économique)</option><option value="3">3 (recommandé)</option><option value="4">4</option><option value="5">5 (le plus exigeant)</option></select></label>
    <label>Essais par créneau si la note manque<select data-var="ESSAIS_MAX" data-def="3"><option value="1">1 (pas de nouvel essai)</option><option value="2">2</option><option value="3">3 (recommandé)</option><option value="4">4</option></select></label>
    <h3>Budget</h3>
    <label>Plafond Claude par mois, en $ (vide = aucun)<div class="jeton"><input data-var="BUDGET_MOIS" data-def="" data-texte="1" maxlength="8" inputmode="decimal" placeholder="ex. 30"><button class="second" data-enr="BUDGET_MOIS" style="flex:none;padding:10px 14px">OK</button></div></label>
    <p class="note">Plafond atteint : plus de vidéos automatiques jusqu'au mois suivant.</p>
    <h3>Mode réaliste (Veo, coûteux)</h3>
    <p class="note">Vidéo filmée par une IA (Veo 3.1 via ElevenLabs) au lieu du dessin animé. Consomme beaucoup de crédits ElevenLabs.</p>
    <div class="auto"><div class="txt"><b>Vidéos automatiques en réaliste</b><small>Coupé : dessin animé.</small></div><button class="inter" data-var="REALISTE_AUTO" data-def="0" data-bascule="1"></button></div>
    <label>Qualité<select data-var="REALISTE_MODELE" data-def="veo-3.1-fast-generate-001"><option value="veo-3.1-fast-generate-001">Rapide (moins cher)</option><option value="veo-3.1-generate-001">Maximale (plus cher)</option></select></label>
    <label>Définition<select data-var="REALISTE_RESOLUTION" data-def="720p"><option value="720p">720p (recommandé)</option><option value="1080p">1080p</option></select></label>
    <div class="ligne2"><select id="realFormat" class="perso" style="margin:0;flex:1"><option value="mini">⚡ Court</option><option value="libre">🎭 Long</option></select><button class="second perso" id="realLancer" style="flex:1.4">🎬 Essayer en réaliste</button></div>
    <div id="suiviReal" class="note"></div>
    <h3>🎙️ Ma voix pour un personnage</h3>
    <p class="note">Parlez 10 à 18 secondes, près du micro, comme si vous jouiez le personnage. Les voix gratuites imiteront votre timbre et votre ton (et passeront en priorité pour ce personnage).</p>
    <div class="ligne2"><select id="vxRole" style="margin:0;flex:1"><option value="presentateur">Personnage 1 (homme)</option><option value="invite">Personnage 2 (homme)</option><option value="envoyee">Personnage féminin</option></select>
      <select id="vxEmo" style="margin:0;flex:1"><option value="base">Toutes les émotions</option><option value="rire">Quand il rit</option><option value="colere">En colère</option><option value="triste">Triste</option><option value="vif">Excité</option><option value="calme">Chuchoté</option></select></div>
    <div class="ligne2"><button class="action" id="vxRec" style="flex:1">⏺️ Enregistrer</button><button class="action" id="vxEnv" style="flex:1" disabled>📤 Envoyer</button></div>
    <audio id="vxEcoute" controls style="width:100%;display:none;margin-top:6px"></audio>
    <div id="suiviVx" class="note"></div>
    <h3>😅 Bêtisier de la semaine</h3>
    <p class="note">Chaque dimanche, les ratés relevés par le jury sont montés en une vidéo d'environ 15 s (jamais publiée toute seule).</p>
    <button class="action" id="betLancer">🎬 Le fabriquer maintenant</button>
    <div id="suiviBet" class="note"></div>
    <h3>Notifications</h3>
    <p class="note">Prévenu quand une vidéo est prête ou publiée. Sur iPhone : installez d'abord l'appli.</p>
    <button class="action" id="activerNotifs">🔔 Activer sur cet appareil</button>
    <button class="action" id="couperNotifs">🔕 Désactiver sur cet appareil</button>
    <button class="action" id="testNotif">Envoyer une notification de test</button>
    <div id="suiviNotif" class="note"></div>
    <section id="appairage" style="display:none"><h3>Connecter un autre appareil</h3>
      <p class="note">Scannez ce code avec l'autre appareil. <b>Ne le montrez à personne d'autre.</b></p>
      <button class="action" id="montrerQR">Afficher le code de connexion</button>
      <div id="qr" style="display:none;text-align:center"><div id="qrImg" style="background:#fff;display:inline-block;padding:12px;border-radius:12px;margin:8px 0"></div>
        <button class="action" id="copierLien">Copier le lien de connexion</button><button class="action" id="cacherQR">Masquer</button></div>
    </section>
    <h3>Application</h3>
    <button class="action" id="majsite">🔄 Mettre à jour l'application</button>
    <div id="suiviCfg" class="note"></div>
    <button class="second" id="oublier" style="width:100%;padding:12px">Déconnecter ce navigateur</button>
    <h3>Raccourcis</h3>
    <a class="lien" id="lienActions" target="_blank" rel="noopener">Activité du robot (GitHub)</a>
    <a class="lien" href="https://publish.buffer.com" target="_blank" rel="noopener">Buffer (file de publication)</a>
    <a class="lien" href="https://www.tiktok.com/tiktokstudio" target="_blank" rel="noopener">TikTok Studio</a>
  </details>
 </div>
</main>
<div id="barre"><div class="int">
  <div id="choix">Sélectionnez une vidéo pour la vérifier</div>
  <div id="cadreVideo"><video id="apercu" controls playsinline preload="metadata"></video>
    <button id="fermer" aria-label="Fermer la vidéo" title="Fermer">✕</button></div>
  <button id="publier" disabled>Publier sur TikTok</button>
  <div class="ligne2"><button class="second" id="voir" disabled>Aperçu</button><button class="second" id="copier" disabled>Copier la légende</button><button class="second" id="manuel" disabled>Partage manuel</button></div>
  <details id="plus"><summary>⋯ Plus d'actions sur cette vidéo</summary>
    <div class="ligne2"><button class="second" id="pouce" disabled>👍 J'aime</button><button class="second" id="bof" disabled>👎 Bof</button></div>
    <label>Ma note pour le jury<select id="noteAuteur"><option value="">—</option><option value="10">10/10</option><option value="9">9/10</option><option value="8">8/10</option><option value="7">7/10</option><option value="6">6/10</option><option value="5">5/10</option><option value="4">4/10</option><option value="3">3/10</option><option value="2">2/10</option><option value="1">1/10</option></select></label>
    <label>Ma remarque (le jury la retient pour les prochaines vidéos)<textarea id="remAuteur" rows="3" maxlength="600" placeholder="Ex. : la dame doit être plus grande, le père en marcel sur le canapé…"></textarea></label>
    <button class="second" id="remOk" disabled style="width:100%;margin-top:6px">🎬 Envoyer au jury</button>
    <label>Légende<textarea id="legEdit" rows="4" maxlength="2200"></textarea></label>
    <button class="second" id="legOk" disabled style="width:100%;margin-top:6px">✏️ Enregistrer la légende</button>
    <label>Programmer la publication (heure de Paris)<input type="datetime-local" id="quand"></label>
    <button class="second" id="programmer" disabled style="width:100%;margin-top:6px">🗓️ Programmer sur TikTok</button>
    <label>Refaire cette vidéo<select id="refaireQuoi"><option value="texte">Nouvelle version du sketch (même sujet)</option><option value="voix">Mêmes répliques, nouvelles voix</option><option value="decors">Mêmes répliques, nouveaux décors</option></select></label>
    <button class="second" id="refaire" disabled style="width:100%;margin-top:6px">🔁 Refaire (15 à 40 min)</button>
    <div style="display:flex;gap:6px;margin-top:6px"><button class="second" id="refaireVoix" disabled style="flex:1">🎙️ Juste la voix</button><button class="second" id="refaireDecor" disabled style="flex:1">🖼️ Juste le décor</button></div>
    <div id="quiBloc" style="display:none;margin-top:10px">
      <b>🗣️ Corriger qui parle</b>
      <p class="note">Chaque réplique avec son personnage : changez ceux qui sont faux, puis « Refaire ». Même son, mêmes décors : seul le personnage qui parle change.</p>
      <div id="quiListe"></div>
      <button class="second" id="quiOk" disabled style="width:100%;margin-top:6px">🔁 Refaire avec ces personnages</button>
    </div>
  </details>
  <button class="second" id="comparer" style="display:none;width:100%;margin-top:6px">📺 Comparer avec l'original</button>
  <div id="suivi"></div>
</div></div>
<div id="toast"></div>
<div id="cote" style="display:none"><div class="cote-int">
  <button id="coteFermer" aria-label="Fermer" title="Fermer">✕</button>
  <div class="cote-col"><b>Original</b><div id="coteOrig"></div></div>
  <div class="cote-col"><b>Notre version</b><video id="coteNous" controls playsinline></video></div>
</div></div>
<script>
var VARS={};
const DATA = __DATA__, CONF = __CONF__;
let OUTILS = __OUTILS__;
const API = "https://api.github.com/repos/" + CONF.depot;
const $ = s => document.querySelector(s);
let choisie = null, fichier = null, charge = null, armer = null;
function toast(t){const e=$("#toast");e.textContent=t;e.style.display="block";clearTimeout(e._t);e._t=setTimeout(()=>e.style.display="none",3200)}
function dateFr(d){try{return new Date(d+"T12:00:00").toLocaleDateString("fr-FR",{weekday:"long",day:"numeric",month:"long"})}catch(e){return d}}
function heureDe(v){const m=/_(\d{2})h(\d{2})_/.exec(v.fichier||"");return m?` à ${+m[1]} h ${m[2]}`:""}   // heure de fabrication (heure de Paris), lue dans le nom du fichier
function quand(v){const m=/(\d{4}-\d{2}-\d{2})_(\d{2})h(\d{2})/.exec(v.fichier||"");return m?m[1]+" "+m[2]+":"+m[3]:(v.date||"")}   // date + heure de fabrication
const recentsDabord=(a,b)=>quand(b[0]).localeCompare(quand(a[0]));    // du plus récent au plus ancien
function lireJeton(){try{return localStorage.getItem("jt_jeton")||""}catch(e){return window._jeton||""}}
function ecrireJeton(v){try{v?localStorage.setItem("jt_jeton",v):localStorage.removeItem("jt_jeton")}catch(e){window._jeton=v}}
async function gh(chemin, opts={}){
  const j=lireJeton(); if(!j) throw new Error("régie non connectée");
  const r=await fetch(API+chemin,{cache:"no-store",...opts,headers:{"Authorization":"Bearer "+j,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",...(opts.body?{"Content-Type":"application/json"}:{}),...(opts.headers||{})}});
  if(r.status===401) throw new Error("jeton refusé (expiré ou incorrect)");
  if(r.status===403) throw new Error("droits du jeton insuffisants");
  return r;
}
function majBandeau(){$("#bandeauCnx").style.display=lireJeton()?"none":""; $("#oublier").style.display=lireJeton()?"":"none"}
// ------------------------------------------------ interrupteur publication automatique (Réglages → Publication)
let auto = null;
function afficherAuto(){
  const b=$("#inter"); b.classList.toggle("on",auto===true); b.disabled=(auto===null);
  $("#autoTitre").textContent = auto===null ? "Publication automatique" : (auto ? "Publication automatique : ACTIVÉE" : "Publication automatique : COUPÉE");
  $("#autoAide").textContent = auto===null ? (lireJeton()?"Lecture du réglage…":"Connectez la régie pour utiliser ce réglage.")
    : (auto ? "Chaque vidéo part toute seule sur TikTok dès qu'elle est prête." : "Les vidéos attendent votre feu vert (onglet Vidéos).");
}
async function lireAuto(){
  if(!lireJeton()||!CONF.depot){auto=null;afficherAuto();return}
  try{const r=await gh("/actions/variables/PUBLICATION_AUTO");
    if(r.status===404){auto=false}else{const v=await r.json();auto=(String(v.value).trim()==="1")}
  }catch(e){auto=null;afficherAuto();$("#autoAide").textContent="Erreur : "+e.message;return}
  afficherAuto();
}
$("#inter").onclick=async()=>{
  const voulu=!auto; $("#inter").disabled=true;
  try{
    const corps=JSON.stringify({name:"PUBLICATION_AUTO",value:voulu?"1":"0"});
    let r=await gh("/actions/variables/PUBLICATION_AUTO",{method:"PATCH",body:corps});
    if(r.status===404) r=await gh("/actions/variables",{method:"POST",body:corps});
    if(!r.ok) throw new Error("GitHub a répondu "+r.status);
    auto=voulu; toast(voulu?"Publication automatique activée":"Publication automatique coupée : les vidéos attendront votre feu vert");
  }catch(e){toast("Impossible : "+e.message)}
  afficherAuto();
};
$("#oublier").onclick=()=>{ecrireJeton(""); auto=null; afficherAuto(); majBoutons(); majBandeau(); chargerReglages(); toast("Régie déconnectée")};
// ------------------------------------------------ voyants des outils payants (d'après la dernière vidéo de l'historique)
const RECHARGE={claude:"https://console.anthropic.com/settings/billing",mistral:"https://console.mistral.ai/usage",gemini:"https://aistudio.google.com/rate-limit",
  voix:"https://elevenlabs.io/app/subscription",decors:"https://modal.com/settings/usage"};
let CRED=null;                                                             // contrôle en direct (episodes/credits.json : bouton « Vérifier maintenant » et chaque vidéo)
const ETATS={ok:["vert","OK"],epuise:["rouge","quota ou crédit épuisé"],cle:["rouge","clé refusée"],erreur:["rouge","ne répond pas"],limite:["orange","limite par minute atteinte (compte à vérifier)"],absent:["gris","pas de clé"],secours:["rouge","crédit épuisé"]};
function voyantsDirect(){
  const c=CRED, e=(k,nom,quoi)=>{const x=ETATS[c[k]]||["gris","pas encore vérifié"]; return [k,x[0],`${nom} : ${x[1]}${quoi&&c[k]==="ok"?" — "+quoi:""}`]};
  const l=[e("claude","Claude","écriture et doublage"),e("mistral","Mistral (gratuit)","relais de Claude pour l'écriture"),e("gemini","Gemini (gratuit)","relais de Claude pour les images et le contrôle")];
  const v=c.elevenlabs; l.push(["voix",(ETATS[v]||["gris"])[0],"ElevenLabs : "+((ETATS[v]||[0,"pas encore vérifié"])[1])+(v==="epuise"?", le robot utilise les voix gratuites":"")]);
  const m=c.modal; l.push(["decors",(ETATS[m]||["gris"])[0],"Modal : "+((ETATS[m]||[0,"pas encore vérifié"])[1])+(m==="ok"?" (décors IA)":"")]);
  if(c.ia==="aucune") l.unshift(["claude","rouge","Aucune IA ne répond : le robot utilise les sketchs de secours"]);
  return l;
}
function voyants(){
  if(CRED&&CRED.date&&(!OUTILS||!OUTILS.date||new Date(CRED.date)>=new Date(OUTILS.date))) return voyantsDirect();
  const o=(OUTILS&&OUTILS.outils)||null, g=(t)=>["gris",t];
  const c=!o||!o.claude?g("Claude : pas encore d'information")
    :o.claude==="ok"?["vert","Claude : OK"]
    :o.claude==="secours"?["rouge","Claude : crédit épuisé, le robot utilise les sketchs de secours"]
    :o.claude==="absent"?["rouge","Claude : pas de clé, le robot utilise les sketchs de secours"]:g("Claude : pas encore d'information");
  const v=!o||!o.voix?g("ElevenLabs : pas encore d'information")
    :o.voix==="elevenlabs"?["vert","ElevenLabs : OK"]
    :(o.voix==="chatterbox"||o.voix==="piper")?["rouge","ElevenLabs : indisponible, le robot utilise les voix gratuites ("+(o.voix==="piper"?"Piper":"Chatterbox")+")"]
    :o.voix==="tiktok"?g("ElevenLabs : non utilisé (son de la vidéo TikTok)"):g("ElevenLabs : pas encore d'information");
  const d=!o||!o.decors?g("Modal : pas encore d'information")
    :o.decors==="ia"?["vert","Modal : OK (décors IA)"]
    :o.decors==="dessines"?["rouge","Modal : décors IA indisponibles ou coupés, le robot dessine les décors"]:g("Modal : pas encore d'information");
  if(o&&o.claude==="ok"&&o.eco) c[1]="Claude : OK (mode économique)";
  return [["claude",...c],["voix",...v],["decors",...d]];
}
function rendreOutils(){
  const l=voyants();
  $("#voyants").innerHTML=l.map(([k,coul,t])=>`<div class="voyant"><span class="point ${coul}"></span><span class="t">${t}</span><a href="${RECHARGE[k]}" target="_blank" rel="noopener">${k==="mistral"||k==="gemini"?"Quotas ↗":"Recharger ↗"}</a></div>`).join("");
  $("#outilsDate").textContent=CRED&&CRED.date?"Vérifié le "+new Date(CRED.date).toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"})+".":
    OUTILS&&OUTILS.outils&&OUTILS.date?"D'après la dernière vidéo ("+dateFr(OUTILS.date)+").":"Les voyants s'allument après la prochaine vidéo.";
  const rouges=l.filter(x=>x[1]==="rouge");
  $("#resumeOutils").textContent=rouges.length?"⚠️":"";
  $("#alerteCredit").innerHTML=rouges.length?`<div class="alerte">⚠️ ${rouges.map(x=>x[2].split(" :")[0]).join(", ")} : crédit à vérifier (⚙️ Réglages → Crédits et outils). Les vidéos sortent quand même avec les outils gratuits.</div>`:"";
}
$("#verifCredits").onclick=()=>{
  if(!lireJeton()){toast("Connectez d'abord la régie (une seule fois)");return}
  lancerFlux("credits.yml",$("#verifCredits"),"🔍 Test de chaque outil en direct (1 à 2 min)…",null,$("#suiviCredits"),
    async ok=>{ if(ok){await actualiserStats(); rendreOutils(); toast("Crédits vérifiés ✓")} });
};
// ------------------------------------------------ liste des vidéos
function badge(v){
  if(v.publie===true&&v.programmee&&new Date(v.programmee)>new Date()) return '<span class="badge att">🗓️ Programmée le '+new Date(v.programmee).toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"})+'</span>';
  if(v.publie===true) return '<span class="badge ok">✓ Publiée sur TikTok</span>'+(v.avis===1?' 👍':v.avis===-1?' 👎':'');
  if(v.publie===false) return '<span class="badge ko">⚠ Échec de publication</span>';
  return '<span class="badge att">⏸ En attente de validation</span>';
}
// ------------------------------------------------ onglet Statistiques (vues, dépenses, alertes)
const ALERTES = __ALERTES__;
let STATS_LIVE=__STATS__, DERNIERE_MAJ=0;
// actualisation automatique (statistiques et nouvelles vidéos) : au lancement, toutes les heures, et au retour sur l'appli après 5 min
// régie connectée : lecture directe par l'API GitHub (données fraîches) ; sinon fichiers publics (cache de quelques minutes)
async function lireEpisode(nom){
  if(lireJeton()){try{const r=await gh(`/contents/episodes/${nom}?ref=${CONF.branche}&t=${Date.now()}`,{headers:{"Accept":"application/vnd.github.raw+json"}});
    if(r.ok) return await r.json()}catch(e){}}
  const r=await fetch(`https://raw.githubusercontent.com/${CONF.depot}/${CONF.branche}/episodes/${nom}?t=${Date.now()}`,{cache:"no-store"});
  return r.ok?r.json():null;
}
async function actualiserStats(){
  if(!CONF.depot) return;
  try{
    const [h,st,cr]=await Promise.all([lireEpisode("historique.json").catch(()=>null),lireEpisode("stats.json").catch(()=>null),lireEpisode("credits.json").catch(()=>null)]);
    if(cr&&cr.date){CRED=cr; rendreOutils()}
    if(Array.isArray(h)){const par={}; h.forEach(e=>{if(e.fichier)par[e.fichier]=e});
      DATA.forEach(v=>{const e=par[v.fichier]; if(!e)return; ["vues","likes","commentaires","partages","publie","couts"].forEach(k=>{if(e[k]!==undefined)v[k]=e[k]})});
      ajouterNouvelles(h);
      const faites=h.filter(e=>e.fichier), der=faites[faites.length-1];
      if(der){OUTILS={outils:(der.outils&&typeof der.outils==="object")?der.outils:null,date:der.date||"",titre:der.titre||""}; rendreOutils()}}
    if(st&&st.compte){const vids=st.videos||[]; STATS_LIVE={compte:st.compte,maj:st.maj||"",videos:vids.length,
      vues:vids.reduce((a,x)=>a+(x.vues||0),0),liees:vids.filter(x=>x.fichier).length,abonnes:st.abonnes,abonnes_hist:st.abonnes_hist||[]}}
    DERNIERE_MAJ=Date.now();
    const o=document.body.dataset.onglet;
    if(o==="stats") rendreStats();
    else if(o==="accueil") rendreRecents();
    else if(o==="tiktok") rendreTk();
    majPointTk();
    if(o==="videos"){rendre(); if(choisie!==null) document.querySelectorAll("#liste .carte").forEach(c=>c.classList.toggle("choisie",+c.dataset.i===choisie))}
  }catch(e){}
}
// vidéo fabriquée mais pas encore dans cette version du site (mise en ligne en cours ou ratée) : elle apparaît quand même,
// lue directement depuis les Releases GitHub où le robot l'archive toujours ; supprimée : elle disparaît de la liste
function ajouterNouvelles(h){
  const connus=new Set(DATA.map(v=>v.fichier)), vivants=new Set(h.filter(e=>e.fichier).map(e=>e.fichier));
  const avant=DATA.length; if(choisie===null) for(let i=DATA.length-1;i>=0;i--) if(!vivants.has(DATA[i].fichier)) DATA.splice(i,1);
  const neuves=h.filter(e=>e.fichier&&!connus.has(e.fichier)).slice(-15).map(e=>({titre:e.titre||"",date:e.date||"",fichier:e.fichier,poster:"",
    src:`https://github.com/${CONF.depot}/releases/download/${e.tag||"emissions-"+e.fichier.slice(0,7)}/${e.fichier}`,
    origine:(e.filiere==="tiktok"||e.source_audio||String(e.theme||"").startsWith("Bande son")||String(e.theme||"").startsWith("TIKTOK::"))?"tiktok":(e.manuel||e.theme)?"texte":"auto",
    legende:e.legende||"",publie:e.publie,vues:e.vues,format:e.format||"",manuel:!!e.manuel,avis:e.avis||0,note:e.note,note_auteur:e.note_auteur,programmee:e.programmee,
    couts:e.couts||{},duree:e.duree,likes:e.likes,commentaires:e.commentaires,partages:e.partages}));
  if(!neuves.length&&DATA.length===avant) return;
  DATA.unshift(...neuves.reverse());
  if(choisie!==null) choisie+=neuves.length;                              // la vidéo ouverte garde sa place
}
const srcDe=v=>v.src||"videos/"+v.fichier;
setTimeout(actualiserStats,1500); setInterval(actualiserStats,3600*1000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&Date.now()-DERNIERE_MAJ>20*1000) actualiserStats()});   // à chaque retour dans l'appli
// nouveaux abonnés depuis une date : total actuel moins le dernier relevé d'avant cette date (ou le plus ancien connu)
function gainAbonnes(hist,depuis){
  if(!hist||!hist.length) return null; const n=hist[hist.length-1].n;
  const avant=hist.filter(x=>new Date(x.t)<=depuis); const ref=avant.length?avant[avant.length-1]:hist[0];
  return n-ref.n;
}
function rendreStats(){
  const S=STATS_LIVE, Z=$("#o-stats"), fr=n=>Number(n||0).toLocaleString("fr-FR");
  const H=S.abonnes_hist||[], minuit=new Date(); minuit.setHours(0,0,0,0);
  const gJour=gainAbonnes(H,minuit), g7=gainAbonnes(H,new Date(Date.now()-7*864e5)), sg=g=>g==null?"–":(g>0?"+":"")+fr(g);
  const pub=DATA.filter(v=>v.publie===true), vues=pub.reduce((a,v)=>a+(v.vues||0),0);
  const mois=new Date().toISOString().slice(0,7), duMois=DATA.filter(v=>(v.date||"").startsWith(mois));
  const usd=duMois.reduce((a,v)=>a+((v.couts||{}).claude_usd||0),0), car=duMois.reduce((a,v)=>a+((v.couts||{}).eleven_caracteres||0),0), gpu=duMois.reduce((a,v)=>a+((v.couts||{}).gpu_s||0),0);
  const top=[...pub].filter(v=>v.vues!=null).sort((a,b)=>b.vues-a.vues).slice(0,10), max=Math.max(1,...top.map(v=>v.vues));
  Z.innerHTML=`<section class="panneau"><h2>📊 La chaîne</h2><div class="chiffres">
    <div><b>${fr(vues)}</b>vues au total</div><div><b>${pub.length}</b>vidéos publiées</div>
    <div><b>${fr(pub.reduce((a,v)=>a+(v.likes||0),0))}</b>j'aime</div><div><b>${fr(pub.reduce((a,v)=>a+(v.commentaires||0),0))}</b>commentaires</div>
    <div><b>${S.abonnes!=null?fr(S.abonnes):"–"}</b>abonnés</div><div><b>${sg(gJour)}</b>nouveaux abonnés aujourd'hui</div>
    <div><b>${sg(g7)}</b>nouveaux abonnés sur 7 jours</div><div><b>${S.compte?"@"+S.compte:"–"}</b>compte suivi</div></div>
    <button class="action" id="majStats" style="margin-top:10px">🔄 Actualiser maintenant</button><p class="note" id="suiviMajStats"></p>
    <p class="note">${S.compte?"Compte @"+S.compte+(S.maj?", lu le "+new Date(S.maj).toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"}):""):"Compte TikTok pas encore réglé (⚙️ Réglages → Publication)."}</p></section>
    <section class="panneau"><h2>🏆 Vidéos les plus vues</h2><div class="barres">${top.length?top.map(v=>`<div><span style="flex:0 0 42%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${v.titre.replace(/</g,"&lt;")}</span><span class="b" style="width:${Math.round(50*v.vues/max)}%"></span>${fr(v.vues)}</div>`).join(""):'<p class="note">Les vues arrivent dans l’heure qui suit les premières publications.</p>'}</div></section>
    <section class="panneau"><h2>💶 Dépenses du mois</h2><div class="chiffres">
    <div><b>${usd.toFixed(2)} $</b>Claude (écriture)</div><div><b>${fr(car)}</b>crédits ElevenLabs (voix)</div>
    <div><b>${Math.round(gpu/60)} min</b>GPU Modal (décors)</div><div><b>${duMois.length?(usd/duMois.length).toFixed(2):"0.00"} $</b>Claude par vidéo</div></div>
    <p class="note">Compté par le robot, vidéo par vidéo.</p></section>
    <section class="panneau"><h2>🔔 Dernières alertes</h2>${ALERTES.length?[...ALERTES].reverse().slice(0,8).map(a=>`<div class="alerte ${/✅|🎬/.test(a.titre)?"ok":""}"><b>${a.titre.replace(/</g,"&lt;")}</b><br>${(a.texte||"").replace(/</g,"&lt;")}<br><small>${new Date(a.quand).toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"})}</small></div>`).join(""):'<p class="note">Aucune alerte.</p>'}</section>`;
  $("#majStats").onclick=()=>{
    if(!lireJeton()){$("#majStats").disabled=true; $("#suiviMajStats").textContent="Relecture des données publiées…"; actualiserStats().then(()=>toast("Données rechargées ✓ (connectez la régie pour relire TikTok tout de suite)")); return}
    lancerFlux("stats.yml",$("#majStats"),"📊 Lecture des vues et abonnés sur TikTok (1 à 3 min)…",null,$("#suiviMajStats"),
      async ok=>{ if(ok){await actualiserStats(); toast("Statistiques à jour ✓")} });
  };
}
// filtre de l'onglet Vidéos : toutes, courtes, longues, depuis un TikTok, depuis un texte
let FILTRE="tout";
const passe=(v,f)=>f==="essais"?!!v.essai:v.essai?false:f==="tiktok"?v.origine==="tiktok":(v.origine!=="tiktok"&&(f==="tout"||(f==="court"?v.format==="mini":f==="long"?v.format!=="mini":v.origine===f)));   // sons TikTok et essais : à part
const VIDE={essais:"Aucun essai en ce moment (les aperçus et essais s'effacent seuls au bout de 3 jours).",tiktok:"Aucune vidéo sur un son TikTok pour l'instant.",tout:"Aucune vidéo pour l'instant : touchez « Créer une vidéo » dans l'Accueil.",court:"Aucune vidéo courte pour l'instant.",long:"Aucune vidéo longue pour l'instant.",
  texte:"Aucune vidéo faite depuis votre texte pour l'instant."};
function carte(v,i,petite){
  const c=document.createElement("div");c.className="carte"+(petite?" petite":"");c.dataset.i=i;
  c.innerHTML=`<img loading="lazy" src="${v.poster?"videos/"+v.poster:"logo-192.png"}" alt=""><div class="infos"><div class="titre"></div><div class="date">${dateFr(v.date)}${heureDe(v)}${v.vues!=null?` · 👁 ${Number(v.vues).toLocaleString("fr-FR")} vues`:""}</div>${badge(v)}${v.voix_secours?'<div class="date" style="color:#c0392b">⚠ voix de secours (robotique)</div>':""}<div class="etat"></div></div>`+(petite?"":`<button class="croix" title="Supprimer cette vidéo" aria-label="Supprimer">✕</button>`);
  c.querySelector(".titre").textContent=v.titre; return c;
}
function rendre(){
  const L=$("#liste"); L.innerHTML="";
  const vis=DATA.map((v,i)=>[v,i]).filter(([v])=>passe(v,FILTRE)).sort(recentsDabord);
  if(!vis.length){L.innerHTML='<p class="vide">'+VIDE[FILTRE]+'</p>';return}
  vis.forEach(([v,i])=>{
    const c=carte(v,i,false); c.onclick=()=>choisir(i);
    c.querySelector(".croix").onclick=(ev)=>{ev.stopPropagation(); supprimer(i,c)}; L.appendChild(c);
  });
}
function rendreRecents(){
  const R=$("#recents"); R.innerHTML="";
  if(!DATA.length){R.innerHTML='<p class="note">Pas encore de vidéo.</p>';$("#toutVoir").style.display="none";return}
  DATA.map((v,i)=>[v,i]).filter(([v])=>v.origine!=="tiktok"&&!v.essai).sort(recentsDabord).slice(0,3).forEach(([v,i])=>{const c=carte(v,i,true); c.onclick=()=>{allerOnglet("videos","tout"); choisir(i);
    const x=document.querySelector(`#liste .carte[data-i="${i}"]`); if(x) x.scrollIntoView({block:"center"})}; R.appendChild(c)});
}
$("#toutVoir").onclick=()=>allerOnglet("videos","tout");
function lireVus(){try{return new Set(JSON.parse(localStorage.getItem("tk_vus")||"[]"))}catch(e){return new Set()}}
function majPointTk(){                                                     // nouvelle vidéo TikTok pas encore vue : point sur l'onglet + mot dans l'accueil
  const vus=lireVus(), neuves=DATA.filter(v=>v.origine==="tiktok"&&!v.essai&&!vus.has(v.fichier)&&(Date.now()-new Date(v.date).getTime())<4*86400000);
  const b=document.querySelector('.onglet[data-o="tiktok"]'); if(b) b.querySelector(".ic").textContent="🎵"+(neuves.length?"🔴":"");   // point rouge à côté de l'icône (le nom tient dans sa case)
  const z=$("#nouveauTk"); if(z){z.style.display=neuves.length?"":"none"; z.innerHTML=neuves.length?`🎵 <b>${neuves.length} nouvelle${neuves.length>1?"s":""} vidéo${neuves.length>1?"s":""} TikTok</b> prête${neuves.length>1?"s":""} : « ${neuves[0].titre.replace(/[<>&]/g,"")} » <button class="second" style="flex:none;padding:8px 12px" onclick="allerOnglet('tiktok')">Voir</button>`:""}
}
function marquerVusTk(){try{const vus=lireVus(); DATA.filter(v=>v.origine==="tiktok").forEach(v=>vus.add(v.fichier)); localStorage.setItem("tk_vus",JSON.stringify([...vus].slice(-300)))}catch(e){} majPointTk()}
function rendreTk(){                                                       // onglet TikTok : ses vidéos à lui
  const L=$("#listeTk"); L.innerHTML="";
  const vis=DATA.map((v,i)=>[v,i]).filter(([v])=>v.origine==="tiktok"&&!v.essai).sort(recentsDabord);
  if(!vis.length){L.innerHTML='<p class="vide">Aucune vidéo sur un son TikTok pour l\'instant.</p>';return}
  const file=filePubli();
  vis.forEach(([v,i])=>{const c=carte(v,i,false); c.onclick=()=>{allerOnglet("videos","tiktok"); choisir(i)};
    c.querySelector(".croix").onclick=(ev)=>{ev.stopPropagation(); supprimer(i,c)};   // ✕ : supprimer aussi depuis cet onglet
    if(v.publie!==true){const b=document.createElement("button"), k=file.indexOf(v.fichier); b.className="apub"+(k>=0?" on":"");
      b.textContent=k<0?"☐ À publier":v.publie===false?"⚠ Échec : sautée (republiez depuis la fiche)":`✅ À publier (n° ${attentePubli(file).indexOf(v.fichier)+1})`; b.onclick=(ev)=>{ev.stopPropagation(); basculerPubli(v.fichier,b)};
      c.querySelector(".infos").appendChild(b)}
    L.appendChild(c)});
  resumePubli();
}
// ------------------------------------------------ publication automatique : une vidéo cochée par jour (moteur/publication_auto.py)
const filePubli=()=>String((VARS&&VARS.PUBLI_FILE)||"").split(/\n+/).map(x=>x.trim()).filter(Boolean);
const attentePubli=f=>f.filter(n=>{const v=DATA.find(x=>x.fichier===n); return v&&v.publie==null});   // cochées, pas encore publiées (échec : sautée)
async function basculerPubli(nom,b){
  if(!lireJeton()){toast("Connectez d'abord la régie (onglet Réglages)");allerOnglet("config");return}
  b.disabled=true; let f=filePubli(); const on=f.includes(nom);
  f=on?f.filter(x=>x!==nom):[...f,nom];
  f=f.filter(n=>DATA.some(x=>x.fichier===n&&x.publie!==true));                // la liste ne garde que les vidéos à venir
  try{await ecrireVar("PUBLI_FILE",f.join("\n")||"-"); VARS.PUBLI_FILE=f.join("\n"); toast(on?"Retirée de la publication automatique":"Ajoutée à la publication automatique ✓"); rendreTk()}
  catch(e){toast("Impossible : "+e.message); b.disabled=false}
}
function resumePubli(){
  const z=$("#pubResume"); if(!z) return;
  if(!lireJeton()){z.textContent="Connectez la régie pour choisir les vidéos à publier.";return}
  const a=attentePubli(filePubli()), on=String((VARS&&VARS.PUBLI_AUTO)||"0")==="1", auto=String((VARS&&VARS.PUBLI_HEURE_AUTO)||"0")==="1", h=auto?(String(CONF.heure_stats??18).padStart(2,"0")+":00"):((VARS&&VARS.PUBLI_HEURE)||"18:00");
  if(!a.length){z.textContent=on?"Aucune vidéo cochée en attente : rien ne sera publié tant que vous n'en cochez pas.":"Aucune vidéo cochée.";return}
  const v=DATA.find(x=>x.fichier===a[0]), [hh,mm]=h.split(":").map(Number), d=new Date(); const jour=(d.getHours()*60+d.getMinutes()<hh*60+mm)?"aujourd'hui":"demain";
  z.textContent=on?`${a.length} vidéo${a.length>1?"s":""} en attente. Prochaine : « ${v?v.titre:a[0]} », ${jour} à ${h} (une par jour).`
                  :`${a.length} vidéo${a.length>1?"s":""} cochée${a.length>1?"s":""}. Activez la publication automatique pour lancer l'envoi quotidien.`;
}
$("#retourTk").onclick=()=>allerOnglet("tiktok");
const CONNUS=(CONF.profils_connus||[]).map(p=>"@"+p);
function majConnus(){                                                      // profils déjà connus : liste de départ, ou ajout à la liste de l'auteur
  const z=document.querySelector('[data-var="PROFILS_TIKTOK"]'); if(!z) return;
  if(!z.value.trim()&&CONNUS.length&&!(VARS&&VARS.PROFILS_TIKTOK)) z.value=CONNUS.join("\n");
  const deja=new Set(z.value.toLowerCase().split(/[\n,;]+/).map(x=>x.trim().replace(/^https?:\/\/(www\.)?tiktok\.com\//,"").replace(/[/?].*$/,"").replace(/^@?/,"@")));
  const manque=CONNUS.filter(p=>!deja.has(p.toLowerCase()));
  $("#tkConnus").style.display=manque.length?"":"none";
  $("#tkConnusNote").textContent=!(VARS&&VARS.PROFILS_TIKTOK)&&CONNUS.length?`${CONNUS.length} profils déjà connus du robot (ceux des sons déjà repris), utilisés tant que vous n'enregistrez pas votre liste. Modifiez si besoin puis touchez OK.`:"";
  return manque;
}
$("#tkConnus").onclick=()=>{const z=document.querySelector('[data-var="PROFILS_TIKTOK"]'), m=majConnus()||[]; if(!m.length) return;
  z.value=(z.value.trim()?z.value.trim()+"\n":"")+m.join("\n"); majConnus(); toast(m.length+" profil(s) ajouté(s) : touchez OK pour enregistrer")};
$("#tkCreer").onclick=()=>{
  if(!lireJeton()){toast("Connectez d'abord la régie (onglet Réglages)");allerOnglet("config");return}
  const u=$("#tkLien").value.trim();
  if(!/^https?:\/\/([a-z0-9-]+\.)*tiktok\.com\/\S+$/i.test(u)){toast("Collez un lien de vidéo TikTok (https://www.tiktok.com/… ou https://vm.tiktok.com/…)");return}
  lancerFlux("emission.yml",$("#tkCreer"),"🔗 Vidéo sur le son TikTok en fabrication (15 à 40 min). Elle apparaîtra dans cet onglet.",{theme:"TIKTOK::"+u,format:"mini"},$("#tkSuivi"));
};
$("#tkHasard").onclick=()=>{
  if(!lireJeton()){toast("Connectez d'abord la régie (onglet Réglages)");allerOnglet("config");return}
  lancerFlux("emission.yml",$("#tkHasard"),"🎲 Le robot choisit un son au hasard dans vos profils et fabrique la vidéo (20 à 45 min). Elle apparaîtra dans cet onglet.",{filiere:"tiktok"},$("#tkSuiviH"));
  setTimeout(()=>{$("#tkHasard").disabled=false},8000);                     // file d'attente : on peut en relancer une autre sans attendre
};
try{const n=+localStorage.getItem("tk_nb"); if(n>=1&&n<=10) $("#tkNb").value=n}catch(e){}
$("#tkNb").onchange=()=>{try{localStorage.setItem("tk_nb",$("#tkNb").value)}catch(e){}};
$("#tkSerie").onclick=()=>{                                                // plusieurs vidéos TikTok à la chaîne : chaque vidéo finie lance la suivante
  if(!lireJeton()){toast("Connectez d'abord la régie (onglet Réglages)");allerOnglet("config");return}
  const n=Math.max(1,Math.min(10,Math.round(+$("#tkNb").value||0))); $("#tkNb").value=n;
  if(!confirm(`Lancer ${n} vidéo${n>1?"s":""} TikTok à la chaîne ?\n\nElles seront fabriquées l'une après l'autre (environ 20 à 45 min chacune), chacune sur un son au hasard de vos profils.`)) return;
  lancerFlux("emission.yml",$("#tkSerie"),`🎲 ${n} vidéo${n>1?"s":""} à la chaîne : la 1re est en fabrication, chaque vidéo finie lance la suivante (barre « vidéo 1/${n} », « 2/${n} »…). Elles apparaîtront dans cet onglet.`,{filiere:"tiktok",chaine:"1/"+n},$("#tkSuiviS"));
  setTimeout(()=>{$("#tkSerie").disabled=false},8000);
};
async function supprimer(i,c){
  const v=DATA[i];
  if(!lireJeton()){toast("Connectez la régie (onglet Réglages) pour supprimer");return}
  if(!confirm(`Supprimer définitivement « ${v.titre} » (${dateFr(v.date)}${heureDe(v)}) ?\n\nLa vidéo sera effacée de l'application et des archives. Cette action est irréversible.`)) return;
  c.classList.add("supprimee"); c.querySelector(".etat").textContent="Suppression en cours…";
  try{
    const r=await gh("/actions/workflows/supprimer.yml/dispatches",{method:"POST",body:JSON.stringify({ref:CONF.branche,inputs:{fichier:v.fichier}})});
    if(r.status!==204) throw new Error("GitHub a répondu "+r.status);
    toast("Vidéo supprimée. L'application se met à jour dans une ou deux minutes.");
    c.querySelector(".etat").textContent="Supprimée";
    if(choisie===i) fermerVideo();
  }catch(e){c.classList.remove("supprimee"); c.querySelector(".etat").textContent=""; toast("Impossible : "+e.message)}
}
function majBoutons(){
  const p=$("#publier"); armer=null; p.classList.remove("confirmer");
  if(choisie===null){p.disabled=true;p.textContent="Publier sur TikTok";return}
  if(!lireJeton()){p.disabled=true;p.textContent="Connectez la régie pour publier";return}
  p.disabled=false; p.textContent = DATA[choisie].publie===true ? "Republier sur TikTok" : "Publier sur TikTok";
}
function ajusterBas(){setTimeout(()=>{document.querySelector("main").style.paddingBottom=($("#barre").offsetHeight+24)+"px"},50)}
function choisir(i){
  choisie=i; fichier=null; const v=DATA[i]; document.body.classList.add("lecture");
  ["#pouce","#bof","#legOk","#remOk","#programmer","#refaire","#refaireVoix","#refaireDecor"].forEach(s=>$(s).disabled=!lireJeton()); $("#legEdit").value=v.legende||""; $("#noteAuteur").value=v.note_auteur?String(v.note_auteur):"";
  $("#pouce").classList.toggle("actif",v.avis===1); $("#bof").classList.toggle("actif",v.avis===-1);
  document.querySelectorAll("#liste .carte").forEach(c=>c.classList.toggle("choisie",+c.dataset.i===i));
  $("#choix").textContent="Sélection : "+v.titre; ["#copier","#voir","#manuel"].forEach(s=>$(s).disabled=false);
  const a=$("#apercu"); a.src=srcDe(v); a.style.display="block"; $("#suivi").textContent=""; majBoutons(); ajusterBas();
  $("#comparer").style.display=v.source?"block":"none"; afficherQui(v);
}
// ------------------------------------------------ idée 5 : l'original et notre version côte à côte
$("#comparer").onclick=()=>{
  const v=DATA[choisie]; if(!v||!v.source)return;
  const id=(v.source.match(/\/video\/(\d+)/)||[])[1];
  if(!id){window.open(v.source,"_blank","noopener");return}            // lien court (vm.tiktok.com) : ouvert dans TikTok
  $("#coteOrig").innerHTML=`<iframe src="https://www.tiktok.com/embed/v2/${id}" allow="encrypted-media; fullscreen" allowfullscreen></iframe>`;
  $("#coteNous").src=srcDe(v); $("#cote").style.display="block"; $("#apercu").pause();
};
$("#coteFermer").onclick=()=>{$("#cote").style.display="none"; $("#coteOrig").innerHTML=""; $("#coteNous").pause()};
// ------------------------------------------------ idée 6 : corriger qui parle (réplique par réplique)
const PERSOS={presentateur:"Personnage 1",invite:"Personnage 2",envoyee:"Personnage 3",narrateur:"Voix off"};
function afficherQui(v){
  const b=$("#quiBloc"), l=$("#quiListe"); l.innerHTML="";
  if(!v.reps||!v.reps.length){b.style.display="none";return}
  b.style.display="block"; $("#quiOk").disabled=true;
  const presents=[...new Set(v.reps.map(r=>r[0]).filter(p=>PERSOS[p]))]; if(presents.length<2) presents.push(["presentateur","invite"].find(p=>!presents.includes(p)));
  v.reps.forEach(([p,t],k)=>{
    const d=document.createElement("div"); d.className="qui";
    const sel=document.createElement("select"); sel.dataset.k=k; sel.dataset.p=p;
    presents.forEach(x=>{const o=document.createElement("option"); o.value=x; o.textContent=PERSOS[x]; if(x===p)o.selected=true; sel.appendChild(o)});
    sel.onchange=()=>{d.classList.toggle("change",sel.value!==sel.dataset.p); $("#quiOk").disabled=!lireJeton()||!l.querySelector(".change")};
    const sp=document.createElement("span"); sp.textContent=t; d.append(sel,sp); l.appendChild(d);
  });
}
$("#quiOk").onclick=()=>{
  const v=DATA[choisie]; const ch=[...$("#quiListe").querySelectorAll("select")].filter(s=>s.value!==s.dataset.p).map(s=>s.dataset.k+"="+s.value);
  if(!ch.length)return;
  lancerFlux("emission.yml",$("#quiOk"),`🗣️ ${ch.length} réplique(s) rendue(s) au bon personnage : la nouvelle version apparaîtra à côté de l'ancienne.`,{refaire:v.fichier+"|qui|"+ch.join(";")},$("#suivi"));
};
// ------------------------------------------------ publication en un bouton (workflow publier.yml)
$("#publier").onclick=async()=>{
  if(choisie===null)return; const v=DATA[choisie], p=$("#publier");
  if(armer!==choisie){armer=choisie;p.classList.add("confirmer");p.textContent="Touchez encore pour confirmer";setTimeout(()=>{if(armer===choisie)majBoutons()},5000);return}
  armer=null;p.classList.remove("confirmer");p.disabled=true;p.textContent="Envoi de l'ordre…";
  const depart=new Date(Date.now()-5000);
  try{
    const r=await gh("/actions/workflows/publier.yml/dispatches",{method:"POST",body:JSON.stringify({ref:CONF.branche,inputs:{fichier:v.fichier,forcer:v.publie===true?"oui":"non"}})});
    if(r.status!==204) throw new Error("GitHub a répondu "+r.status);
    p.textContent="Publication en cours…"; suivre(depart, v);
  }catch(e){toast("Impossible : "+e.message); majBoutons()}
};
async function suivre(depart, v){
  const s=$("#suivi"); s.textContent="Le robot envoie la vidéo à TikTok (1 à 3 minutes)…";
  for(let k=0;k<60;k++){
    await new Promise(r=>setTimeout(r,6000));
    try{
      const r=await gh("/actions/workflows/publier.yml/runs?event=workflow_dispatch&per_page=5"); const d=await r.json();
      const run=(d.workflow_runs||[]).find(x=>new Date(x.created_at)>=depart); if(!run) continue;
      if(run.status!=="completed"){s.textContent="Le robot travaille… ("+(run.status==="queued"?"en file d'attente":"en cours")+")";continue}
      if(run.conclusion==="success"){s.innerHTML="✅ Vidéo envoyée à TikTok. Le site se met à jour dans une minute.";v.publie=true}
      else{s.innerHTML=`❌ Échec. <a style="color:var(--bleu)" href="${run.html_url}" target="_blank" rel="noopener">Voir le détail</a> — vous pouvez utiliser « Partage manuel ».`;v.publie=false}
      const b=document.querySelector(`#liste .carte[data-i="${DATA.indexOf(v)}"] .badge`); if(b) b.outerHTML=badge(v); majBoutons(); return;
    }catch(e){ if(k>50){s.textContent="Suivi interrompu (connexion) : l'état apparaîtra dans l'appli."; majBoutons(); return} }
  }
  s.textContent="Toujours en cours : regardez l'onglet Actions du dépôt."; majBoutons();
}
// ------------------------------------------------ secours : partage manuel
const peutPartager = !!(navigator.canShare && navigator.canShare({files:[new File([""],"t.mp4",{type:"video/mp4"})]}));
function fermerVideo(){
  const a=$("#apercu"); a.pause(); a.removeAttribute("src"); a.load(); a.style.display="none";
  choisie=null; fichier=null; document.querySelectorAll(".carte").forEach(c=>c.classList.remove("choisie")); document.body.classList.remove("lecture");
  $("#choix").textContent="Sélectionnez une vidéo pour la vérifier"; ["#copier","#voir","#manuel"].forEach(s=>$(s).disabled=true);
  $("#suivi").textContent=""; majBoutons(); ajusterBas();
}
$("#fermer").onclick=fermerVideo;
// ------------------------------------------------ actions sur la vidéo choisie
function action(a,valeur,msg){
  if(choisie===null)return; const v=DATA[choisie];
  lancerFlux("regie.yml",$("#legOk"),msg,{action:a,fichier:v.fichier,valeur:String(valeur)},$("#suivi"));
}
$("#pouce").onclick=()=>{const v=DATA[choisie];v.avis=v.avis===1?0:1;$("#pouce").classList.toggle("actif",v.avis===1);$("#bof").classList.remove("actif");action("avis",v.avis,"👍 Noté : le robot s'en servira comme exemple.")};
$("#bof").onclick=()=>{const v=DATA[choisie];v.avis=v.avis===-1?0:-1;$("#bof").classList.toggle("actif",v.avis===-1);$("#pouce").classList.remove("actif");action("avis",v.avis,"👎 Noté : le robot évitera ce genre de sketch.")};
$("#remOk").onclick=()=>{const n=$("#noteAuteur").value, t=$("#remAuteur").value.trim(); if(!n&&!t){toast("Mettez une note ou une remarque");return}
  action("remarque",(n||"")+"|"+t,"🎬 Merci ! Le jury s'en servira pour les prochaines vidéos."); $("#remAuteur").value=""};
$("#legOk").onclick=()=>{const t=$("#legEdit").value.trim(); if(!t){toast("Légende vide");return} DATA[choisie].legende=t; action("legende",t,"✏️ Légende enregistrée (le site se met à jour dans 2 à 3 min).")};
$("#programmer").onclick=()=>{
  const q=$("#quand").value; if(!q){toast("Choisissez la date et l'heure");return}
  if(new Date(q)<new Date(Date.now()+10*60000)){toast("Choisissez une heure dans au moins 10 minutes");return}
  const v=DATA[choisie];
  lancerFlux("publier.yml",$("#programmer"),"🗓️ Publication programmée le "+new Date(q).toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"})+" : Buffer s'en charge, même appli fermée.",{fichier:v.fichier,forcer:v.publie===true?"oui":"non",quand:q},$("#suivi"));
};
$("#refaire").onclick=()=>{const v=DATA[choisie], q=$("#refaireQuoi").value;
  lancerFlux("emission.yml",$("#refaire"),"🔁 Nouvelle version en fabrication. Elle apparaîtra à côté de l'ancienne (supprimez celle que vous ne gardez pas).",{refaire:v.fichier+"|"+q},$("#suivi"))};
[["#refaireVoix","voix","🎙️ Mêmes répliques et même image, nouvelles voix : la nouvelle version apparaîtra à côté de l'ancienne."],
 ["#refaireDecor","decors","🖼️ Mêmes répliques et mêmes voix, nouveaux décors : la nouvelle version apparaîtra à côté de l'ancienne."]].forEach(([s,q,m])=>{
  $(s).onclick=()=>{const v=DATA[choisie]; lancerFlux("emission.yml",$(s),m,{refaire:v.fichier+"|"+q},$("#suivi"))}});
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&choisie!==null)fermerVideo()});
$("#voir").onclick=()=>{const a=$("#apercu");a.style.display="block";a.play()};
$("#copier").onclick=async()=>{const t=DATA[choisie].legende||"";try{await navigator.clipboard.writeText(t);toast("Légende copiée")}catch(e){prompt("Copiez la légende :",t)}};
$("#manuel").onclick=async()=>{
  const v=DATA[choisie]; navigator.clipboard && navigator.clipboard.writeText(v.legende||"").catch(()=>{});
  if(!peutPartager){
    const a=document.createElement("a");a.href=srcDe(v);a.download=v.fichier;document.body.appendChild(a);a.click();a.remove();
    window.open("https://www.tiktok.com/tiktokstudio/upload","_blank");toast("Légende copiée · vidéo téléchargée");return;
  }
  const b=$("#manuel");
  if(!fichier){b.textContent="Préparation…";const jeton=charge={};
    try{const r=await fetch(srcDe(v));if(!r.ok)throw new Error(r.status);const blob=await r.blob();if(charge!==jeton)return;fichier=new File([blob],v.fichier,{type:"video/mp4"});
      b.textContent="Touchez pour partager";}catch(e){b.textContent="Partage manuel";if(v.src){window.open(v.src,"_blank");toast("Vidéo toute neuve : téléchargée depuis GitHub, partagez-la depuis vos fichiers")}else toast("Chargement impossible")}
    return;}
  try{await navigator.share({files:[fichier],title:v.titre});toast("Choisissez TikTok, collez la légende, activez « Contenu IA »")}
  catch(e){if(e.name!=="AbortError")toast("Partage impossible : "+e.message)}
  b.textContent="Partage manuel";
};
// ------------------------------------------------ connexion d'un autre appareil par QR code (la clé voyage dans le « # » du lien, jamais envoyé au serveur)
(function(){const m=location.hash.match(/^#cle=(.+)$/); if(!m) return;
  try{ecrireJeton(decodeURIComponent(m[1]));}catch(e){}
  history.replaceState(null,"",location.pathname+location.search); setTimeout(()=>toast("Régie connectée sur cet appareil ✓"),300);})();
function lienConnexion(){return location.origin+location.pathname+"#cle="+encodeURIComponent(lireJeton())}
$("#montrerQR").onclick=async()=>{
  if(typeof qrcode==="undefined") await new Promise(ok=>{const sc=document.createElement("script");
    sc.src="https://cdnjs.cloudflare.com/ajax/libs/qrcode-generator/1.4.4/qrcode.min.js";sc.onload=sc.onerror=ok;document.head.appendChild(sc)});
  if(typeof qrcode==="undefined"){toast("Générateur de code indisponible : utilisez « Copier le lien »");$("#qr").style.display="block";return}
  const q=qrcode(0,"M"); q.addData(lienConnexion()); q.make(); $("#qrImg").innerHTML=q.createSvgTag({cellSize:6,margin:2,scalable:true});
  $("#qrImg").querySelector("svg").style.width="240px"; $("#qr").style.display="block"; $("#montrerQR").style.display="none";
  clearTimeout(window._qrT); window._qrT=setTimeout(()=>$("#cacherQR").click(),120000);
};
$("#cacherQR").onclick=()=>{$("#qr").style.display="none";$("#qrImg").innerHTML="";$("#montrerQR").style.display=""};
$("#copierLien").onclick=async()=>{try{await navigator.clipboard.writeText(lienConnexion());toast("Lien copié : ouvrez-le sur l'autre appareil")}catch(e){prompt("Lien de connexion :",lienConnexion())}};
// ------------------------------------------------ onglets (Accueil, Vidéos, Statistiques, Réglages) et filtre des vidéos
// ------------------------------------------------ onglets affichés (Réglages) : variable ONGLETS_MASQUES, gardée aussi sur l'appareil
const MASQUABLES=["accueil","videos","stats"];
function appliquerOnglets(brut,local){
  try{if(!local&&Date.now()-(+localStorage.getItem("onglets_masques_t")||0)<5*60000) brut=localStorage.getItem("onglets_masques")}catch(e){}   // choix tout juste fait ici : prioritaire
  const m=new Set(String(brut||"").split(",").map(x=>x.trim()).filter(x=>MASQUABLES.includes(x)));
  try{localStorage.setItem("onglets_masques",[...m].join(",")); if(local) localStorage.setItem("onglets_masques_t",String(Date.now()))}catch(e){}
  document.querySelectorAll(".onglet").forEach(b=>b.style.display=m.has(b.dataset.o)?"none":"");
  document.querySelectorAll("[data-onglet-vu]").forEach(c=>c.checked=!m.has(c.dataset.ongletVu));
  const act=document.querySelector(".onglet.actif"); if(act&&m.has(act.dataset.o)) allerOnglet("tiktok");   // onglet caché : TikTok à la place
}
document.querySelectorAll("[data-onglet-vu]").forEach(c=>c.onchange=async()=>{
  const m=[...document.querySelectorAll("[data-onglet-vu]")].filter(x=>!x.checked).map(x=>x.dataset.ongletVu).join(",");
  appliquerOnglets(m,true);
  if(!lireJeton()){toast("Enregistré sur cet appareil (connectez la régie pour tous vos appareils)");return}
  try{await ecrireVar("ONGLETS_MASQUES",m||"-"); VARS.ONGLETS_MASQUES=m; toast("Onglets enregistrés ✓")}catch(e){toast("Impossible : "+e.message)}
});
function allerOnglet(o,f){
  document.querySelectorAll(".onglet").forEach(x=>x.classList.toggle("actif",x.dataset.o===o));
  if(f) choisirFiltre(f);
  ["accueil","videos","tiktok","stats","config"].forEach(k=>$("#o-"+k).style.display=k===o?"":"none");
  document.querySelectorAll(".onglet").forEach(x=>x.classList.toggle("actif",x.dataset.o===(o==="videos"&&FILTRE==="tiktok"?"tiktok":o)));
  $("#filtres").style.display=(o==="videos"&&FILTRE==="tiktok")?"none":""; $("#enteteTk").style.display=(o==="videos"&&FILTRE==="tiktok")?"":"none";
  document.body.dataset.onglet=o; $("#barre").style.display=o==="videos"?"":"none";
  if(o==="videos"){rendre(); if(choisie!==null) document.querySelectorAll("#liste .carte").forEach(c=>c.classList.toggle("choisie",+c.dataset.i===choisie))}
  if(o==="accueil") rendreRecents();
  if(o==="stats") rendreStats();
  if(o==="config"||o==="tiktok") chargerReglages();
  if(o==="tiktok"){rendreTk(); majConnus(); marquerVusTk()}
  window.scrollTo(0,0);
}
function choisirFiltre(f){
  FILTRE=f; document.querySelectorAll("#filtres .chip").forEach(x=>x.classList.toggle("on",x.dataset.f===f));
  if(choisie!==null&&!passe(DATA[choisie],FILTRE)) fermerVideo(); rendre();
}
document.querySelectorAll(".onglet").forEach(b=>b.onclick=()=>allerOnglet(b.dataset.o,b.dataset.o==="videos"?"tout":null));
document.querySelectorAll("#filtres .chip").forEach(b=>b.onclick=()=>choisirFiltre(b.dataset.f));
$("#allerCnx").onclick=()=>{allerOnglet("config"); setTimeout(()=>$("#jeton2").focus(),100)};
// ------------------------------------------------ réglages (variables du dépôt GitHub)
// ------------------------------------------------ série d'un seul jet
function lancerSerie(){
  const n=document.querySelector('[data-var="EPISODES_PAR_SERIE"]').value||"5", f=$("#serieFormat").value;
  lancerFlux("emission.yml",$("#serieLot"),`🎬 Série de ${n} ${f==="mini"?"gags éclair":"sketchs longs"} en fabrication : plan de la saison, puis les épisodes à la suite (environ ${f==="mini"?20*n:35*n} min au total).`,{format:f,serie:"1"},$("#suiviSerie"))}
$("#serieLot").onclick=()=>{if(!lireJeton()){toast("Connectez la régie pour lancer la série");return} lancerSerie()};
document.querySelector('[data-var="EPISODES"]').addEventListener("change",e=>{
  if(e.target.value==="serie"&&lireJeton()&&confirm("Fabriquer maintenant tous les épisodes de la série, d'un seul jet ?")) setTimeout(lancerSerie,600)});
// ------------------------------------------------ programme et planning personnalisés
const NOMS_F={mini:"⚡ Gag",libre:"🎭 Long"}; let SEQ=["mini","mini","mini","libre"], CREN=[], JOURS=new Set([1,2,3,4,5,6,7]);
function dessinerSeq(){const z=$("#seqChips"); z.innerHTML="";
  SEQ.forEach((f,i)=>{const b=document.createElement("button");b.className="chip perso";b.textContent=(i+1)+". "+NOMS_F[f]+" ✕";b.onclick=()=>{SEQ.splice(i,1);dessinerSeq()};z.appendChild(b)});
  if(!SEQ.length) z.innerHTML='<span class="note">Séquence vide : ajoutez au moins une vidéo.</span>'}
document.querySelectorAll("[data-ajout]").forEach(b=>b.onclick=()=>{if(SEQ.length<30){SEQ.push(b.dataset.ajout);dessinerSeq()}});
$("#selFormat").onchange=async()=>{const v=$("#selFormat").value; $("#seqBloc").style.display=v==="seq"?"":"none"; if(v==="seq"){dessinerSeq();return}
  try{await ecrireVar("FORMAT",v);toast("Réglage enregistré ✓")}catch(e){toast("Impossible : "+e.message)}};
$("#seqEnr").onclick=async()=>{if(!SEQ.length){toast("Ajoutez au moins une vidéo");return}
  try{await ecrireVar("FORMAT","seq:"+SEQ.join(","));toast("Séquence enregistrée ✓")}catch(e){toast("Impossible : "+e.message)}};
const TYPES_CRENEAU=["programme","mini","libre"];
function lireHoraires(brut){CREN=[];JOURS=new Set([1,2,3,4,5,6,7]); brut=String(brut||"17").toLowerCase();
  if(brut.includes("|jours=")){const [a,j]=brut.split("|jours=");brut=a;const s=new Set([...j].filter(c=>"1234567".includes(c)).map(Number));if(s.size)JOURS=s}
  brut.split(";").map(x=>x.trim()).filter(Boolean).forEach(m=>{let [h,f]=m.split("=");h=h.trim();f=(f||"programme").trim(); if(!TYPES_CRENEAU.includes(f)) f="programme";
    if(h==="auto"){CREN.push({h:"auto",f});return} let [hh,mm]=h.replace("h",":").split(":");hh=+hh;mm=+(mm||0);
    if(!isNaN(hh)&&hh>=0&&hh<24) CREN.push({h:String(hh).padStart(2,"0")+":"+String(mm).padStart(2,"0"),f})});
  if(!CREN.length) CREN=[{h:"17:00",f:"programme"}]}
function dessinerPlanning(){const z=$("#creneaux"); z.innerHTML="";
  CREN.forEach((c,i)=>{const l=document.createElement("div");l.className="creneau";
    const [hh,mm]=(c.h==="auto"?"17:00":c.h).split(":");
    const optH=[...Array(24).keys()].map(x=>`<option value="${String(x).padStart(2,"0")}">${x} h</option>`).join("");
    const optM=[...Array(12).keys()].map(x=>`<option value="${String(x*5).padStart(2,"0")}">${String(x*5).padStart(2,"0")}</option>`).join("");
    l.innerHTML=(c.h==="auto"?'<span class="auto-h">📊 Auto</span>':`<span class="heure"><select class="perso hh">${optH}</select><select class="perso mm">${optM}</select></span>`)+
      `<select class="perso"><option value="programme">Selon le programme</option><option value="mini">⚡ Gag éclair</option><option value="libre">🎭 Sketch long</option></select><button class="second perso" title="Retirer">✕</button>`;
    const sh=l.querySelector(".hh"), sm=l.querySelector(".mm");             // listes heure / minutes : faciles au doigt sur téléphone
    if(sh){sh.value=hh; sm.value=String(Math.round((+mm||0)/5)*5%60).padStart(2,"0"); const maj=()=>{c.h=sh.value+":"+sm.value}; sh.onchange=maj; sm.onchange=maj; maj()}
    const s=l.querySelector("select:not(.hh):not(.mm)"); s.value=c.f; s.onchange=()=>{c.f=s.value};
    l.querySelector("button").onclick=()=>{CREN.splice(i,1);dessinerPlanning()}; z.appendChild(l)});
  const j=$("#jours"); j.innerHTML="";
  ["L","M","M","J","V","S","D"].forEach((n,k)=>{const b=document.createElement("button");b.className="chip perso"+(JOURS.has(k+1)?" on":"");b.textContent=n;
    b.title=["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"][k];
    b.onclick=()=>{JOURS.has(k+1)?JOURS.delete(k+1):JOURS.add(k+1);b.classList.toggle("on")};j.appendChild(b)})}
$("#ajCreneau").onclick=()=>{if(CREN.length<12){CREN.push({h:"18:00",f:"programme"});dessinerPlanning()}};
$("#ajAuto").onclick=()=>{if(!CREN.some(c=>c.h==="auto")){CREN.push({h:"auto",f:"programme"});dessinerPlanning()}};
$("#planEnr").onclick=async()=>{
  if(!CREN.length){toast("Ajoutez au moins un créneau");return} if(!JOURS.size){toast("Cochez au moins un jour");return}
  const tri=[...CREN].sort((a,b)=>a.h==="auto"?1:b.h==="auto"?-1:a.h.localeCompare(b.h));
  let v=tri.map(c=>c.h+(c.f&&c.f!=="programme"?"="+c.f:"")).join(";"); if(JOURS.size<7) v+="|jours="+[...JOURS].sort().join("");
  try{await ecrireVar("HEURE",v);toast("Planning enregistré ✓ ("+tri.length+" créneau"+(tri.length>1?"x":"")+")")}catch(e){toast("Impossible : "+e.message)}};
function chargerPerso(v){const f=String(v.FORMAT||"cycle");
  if(f.startsWith("seq:")){SEQ=f.slice(4).split(",").filter(x=>NOMS_F[x]);$("#selFormat").value="seq";$("#seqBloc").style.display=""}
  else{$("#selFormat").value=["cycle","mini","libre"].includes(f)?f:"cycle";$("#seqBloc").style.display="none"}
  dessinerSeq(); lireHoraires(v.HEURE); dessinerPlanning()}
lireHoraires("17"); dessinerPlanning(); dessinerSeq();
$("#lienActions").href="https://github.com/"+CONF.depot+"/actions";
async function ecrireVar(nom,valeur){
  const corps=JSON.stringify({name:nom,value:String(valeur)});
  let r=await gh("/actions/variables/"+nom,{method:"PATCH",body:corps});
  if(r.status===404) r=await gh("/actions/variables",{method:"POST",body:corps});
  if(!r.ok) throw new Error("GitHub a répondu "+r.status);
}
const champs=()=>document.querySelectorAll("#o-config [data-var], #o-tiktok [data-var]");
function activer(on){champs().forEach(c=>c.disabled=!on);document.querySelectorAll("#o-config .action,[data-enr],#o-config .perso").forEach(b=>b.disabled=!on)}
$("#garder2").onclick=()=>{const v=$("#jeton2").value.trim(); if(!v)return; ecrireJeton(v); $("#jeton2").value=""; lireAuto(); majBoutons(); majBandeau(); chargerReglages(); verifierEnCours()};
async function chargerReglages(){
  $("#cfgConnexion").style.display=lireJeton()?"none":""; $("#appairage").style.display=lireJeton()?"":"none"; $("#oublier").style.display=lireJeton()?"":"none";
  if(!lireJeton()){activer(false);$("#cfgEtat").textContent="";return}
  $("#cfgEtat").textContent="Lecture des réglages…";
  try{
    const r=await gh("/actions/variables?per_page=100"); const d=await r.json(); const v={}; VARS=v;
    (d.variables||[]).forEach(x=>v[x.name]=x.value);
    champs().forEach(c=>{const val=(c.dataset.var in v)?v[c.dataset.var]:c.dataset.def;
      if(c.dataset.bascule) c.classList.toggle("on",String(val)!=="0"); else c.value=val;});
    chargerPerso(v); activer(true); majConnus(); $("#cfgEtat").textContent="Régie connectée ✓ — chaque changement est enregistré tout de suite.";
    appliquerOnglets(v.ONGLETS_MASQUES||""); if($("#o-tiktok").style.display!=="none") rendreTk();
    nettoyerAbos(v);
  }catch(e){$("#cfgEtat").textContent="Erreur : "+e.message+" — vérifiez la clé (droits Actions et Variables).";activer(false);
    if(/jeton refusé/.test(e.message)) $("#cfgConnexion").style.display=""}
}
champs().forEach(c=>{
  if(c.dataset.texte) return;
  const ev=c.dataset.bascule?"click":"change";
  c.addEventListener(ev,async()=>{
    const val=c.dataset.bascule?(c.classList.contains("on")?"0":"1"):c.value; c.disabled=true;
    try{await ecrireVar(c.dataset.var,val); VARS[c.dataset.var]=val; if(c.dataset.bascule) c.classList.toggle("on",val==="1"); toast("Réglage enregistré ✓"); resumePubli()}
    catch(e){toast("Impossible : "+e.message); chargerReglages()}
    c.disabled=false;
  });
});
document.querySelectorAll("[data-enr]").forEach(b=>b.onclick=async()=>{
  const c=document.querySelector(`[data-var="${b.dataset.enr}"]`); const val=c.value.trim(); if(!val)return;
  try{await ecrireVar(b.dataset.enr,val); VARS[b.dataset.enr]=val; toast("Enregistré ✓ (visible dès la prochaine vidéo)"); resumePubli()}catch(e){toast("Impossible : "+e.message)}
});
async function lancerFlux(fichier,bouton,texte,inputs,zone,fini){
  bouton.disabled=true; const s=zone||$("#suiviCfg"); const depart=new Date(Date.now()-5000);
  try{
    const r=await gh(`/actions/workflows/${fichier}/dispatches`,{method:"POST",body:JSON.stringify(inputs?{ref:CONF.branche,inputs}:{ref:CONF.branche})});
    if(r.status!==204) throw new Error("GitHub a répondu "+r.status);
    s.textContent="✓ Lancé. "+texte; let echecs=0;
    for(let k=0;k<200;k++){
      await new Promise(r=>setTimeout(r,15000));
      let d;                                                     // suivi : une coupure réseau passagère (appli en arrière-plan…) n'est pas une erreur
      try{d=await (await gh(`/actions/workflows/${fichier}/runs?event=workflow_dispatch&per_page=3`)).json(); echecs=0}
      catch(e){ if(++echecs>=4){s.textContent="✓ Lancé. Suivi interrompu (connexion) : le résultat apparaîtra dans l'appli quand ce sera fini.";break} continue }
      const run=(d.workflow_runs||[]).find(x=>new Date(x.created_at)>=depart); if(!run) continue;
      if(run.status!=="completed"){s.textContent=texte+" ("+(run.status==="queued"?"en file d'attente":"en cours")+")";continue}
      s.innerHTML=run.conclusion==="success"?(fini?"✅ Terminé.":"✅ Terminé. Rouvrez l'application dans une minute pour voir le résultat."):`❌ Échec. <a style="color:var(--bleu)" href="${run.html_url}" target="_blank" rel="noopener">Voir le détail</a>`;
      if(fini){try{await fini(run.conclusion==="success")}catch(e){}}
      break;
    }
  }catch(e){s.textContent="Impossible : "+(/failed to fetch|load failed|network/i.test(e.message)?"pas de connexion internet (réessayez)":e.message)}
  bouton.disabled=false;
}
// ------------------------------------------------ Accueil : « Créer une vidéo » (lien TikTok, mon texte ou idée automatique ; court ou long)
let SRC="texte", FMT="mini";
function majCreer(){
  document.querySelectorAll("[data-src]").forEach(b=>b.classList.toggle("on",b.dataset.src===SRC));
  document.querySelectorAll("[data-fmt]").forEach(b=>b.classList.toggle("on",b.dataset.fmt===FMT));
  $("#mTexteBloc").style.display=SRC==="texte"?"":"none"; $("#mAutoNote").style.display=SRC==="idee"?"":"none";
}
$("#creerBtn").onclick=()=>{const p=$("#creer"), ouvrir=p.style.display==="none"; p.style.display=ouvrir?"":"none";
  $("#creerBtn").textContent=ouvrir?"✕ Fermer":"➕ Créer une vidéo"; if(ouvrir) majCreer()};
document.querySelectorAll("[data-src]").forEach(b=>b.onclick=()=>{SRC=b.dataset.src; majCreer()});
document.querySelectorAll("[data-fmt]").forEach(b=>b.onclick=()=>{FMT=b.dataset.fmt; majCreer()});
$("#mMode").onchange=()=>{const s=$("#mMode").value==="script";
  $("#mAide").textContent=s?"Mon script (une réplique par ligne : « Jojo : … », « Kévin : … », « Lila : … »)":"Idée / thème de la vidéo";
  $("#mTexte").placeholder=s?"Jojo : Je vais résilier ma salle de sport.\nKévin : T'y es allé combien de fois ?\nJojo : Une. Pour m'inscrire.\nLila : Donc tu payes 30 € par mois pour un souvenir.":"Ex. : Jojo essaie de résilier son abonnement de salle de sport, mais le conseiller ne le laisse jamais partir.";
  $("#mStyleL").style.display=s?"none":""};
function lancerCreation(texte,inputs){
  $("#mSuivi").dataset.libre="0";
  if($("#mApercu")&&$("#mApercu").checked){inputs=Object.assign({},inputs,{apercu:"1"}); texte="👀 Aperçu rapide (10 s) en fabrication (environ 8 min). Il apparaîtra dans l'onglet Vidéos."}
  lancerFlux("emission.yml",$("#mCreer"),texte,inputs,$("#mSuivi"));
  $("#creer").style.display="none"; $("#creerBtn").textContent="➕ Créer une vidéo";
  $("#mSuivi").scrollIntoView({behavior:"smooth",block:"center"});
}
$("#mCreer").onclick=()=>{
  if(!lireJeton()){toast("Connectez d'abord la régie (onglet Réglages)");allerOnglet("config");return}
  const nomF=FMT==="mini"?"⚡ Gag éclair":"🎭 Sketch long";
  if(SRC==="idee"){
    lancerCreation(FMT==="mini"?"⚡ Le robot fabrique un gag éclair (15 à 30 min)…":"🎭 Le robot fabrique un sketch long (20 à 40 min)…",{format:FMT});
    return;
  }
  const t=$("#mTexte").value.trim(); if(t.length<8){toast("Tapez d'abord votre idée ou votre script");return}
  const script=$("#mMode").value==="script";
  if(script&&!/^\s*[^:\n]{1,25}:/m.test(t)){toast("Format du script : une réplique par ligne, « Jojo : … »");return}
  const theme=script?"SCRIPT::"+t:(t+($("#mStyle").value?"\n"+$("#mStyle").value:""));
  lancerCreation(nomF+" (votre texte) en fabrication (15 à 40 min). Il apparaîtra dans l'onglet Vidéos.",{format:FMT,theme});
};
// fabrication déjà en cours (lancée par le planning ou un autre appareil) : affichée dans l'Accueil
// ------------------------------------------------ barre de progression en temps réel (accueil et onglet TikTok)
// le robot publie son avancement toutes les 5 s (statut « progression-<run> » du commit) ; entre deux points, la barre et le
// compte à rebours avancent seuls, seconde par seconde
const SUIVI={runs:{},site:null,durees:{emission:25*60,site:5*60},maj:0,anonyme:0};
// sans la clé de la régie (autre appareil, PC) : lecture publique du dépôt, plus espacée (GitHub : 60 lectures/heure)
async function ghLire(chemin){
  if(lireJeton()) return gh(chemin);
  const r=await fetch(API+chemin,{cache:"no-store",headers:{"Accept":"application/vnd.github+json"}});
  if(r.status===403||r.status===429){const z=+r.headers.get("x-ratelimit-reset")||0; SUIVI.bloque=z?z*1000:Date.now()+15*60000; dessinerSuivi()}   // limite de GitHub sans clé
  if(!r.ok) throw new Error("lecture "+r.status); return r}
const sansCleBloque=()=>!lireJeton()&&(SUIVI.bloque||0)>Date.now();
const fmtReste=s=>s<=20?"quelques secondes":s<90?"≈ "+Math.round(s)+" s":"≈ "+Math.floor(s/60)+" min"+(s<600&&s%60>=10?" "+String(Math.round(s%60)).padStart(2,"0")+" s":"");
async function suiviLent(){                                                // toutes les 20 s : fabrications en cours, étape, durées habituelles
  if(!CONF.depot||document.hidden||sansCleBloque()) return;
  if(!lireJeton()){if(Date.now()-SUIVI.anonyme<110000) return; SUIVI.anonyme=Date.now()}   // sans clé : toutes les 2 min
  try{
    if(Date.now()-SUIVI.maj>600000){SUIVI.maj=Date.now();
      for(const [w,k] of [["emission.yml","emission"],["site.yml","site"]]){
        if(!lireJeton()) break;
        const d=await (await gh(`/actions/workflows/${w}/runs?status=success&per_page=15`)).json();
        const ds=(d.workflow_runs||[]).map(r=>(new Date(r.updated_at)-new Date(r.run_started_at||r.created_at))/1000).filter(x=>x>(k==="site"?60:300)).sort((a,b)=>a-b);
        if(ds.length) SUIVI.durees[k]=ds[Math.floor(ds.length/2)]}}
    const d=await (await ghLire("/actions/workflows/emission.yml/runs?per_page=15")).json(); const vus=new Set();
    for(const r of (d.workflow_runs||[])){
      const recent=r.status!=="completed"||(Date.now()-new Date(r.updated_at))<10*60000; if(!recent) continue;
      const s=SUIVI.runs[r.id]||(SUIVI.runs[r.id]={id:r.id,sha:r.head_sha,url:r.html_url,debut:new Date(r.run_started_at||r.created_at).getTime()});
      s.statut=r.status; s.conclusion=r.conclusion;
      if(!lireJeton()&&r.status==="completed"&&!s.vu) continue;           // sans clé : seulement les fabrications en cours
      try{const j=await (await ghLire(`/actions/runs/${r.id}/jobs`)).json(); const job=(j.jobs||[]).find(x=>x.name==="emission"), fj=(j.jobs||[]).find(x=>x.name==="file");
        s.attente=!job&&!!fj&&fj.status!=="completed";                     // file d'attente : attend que la vidéo d'avant soit finie
        s.fabrique=(!!job&&job.conclusion!=="skipped")||s.attente; if(job){s.etapeGh=((job.steps||[]).find(x=>x.status==="in_progress")||{}).name||""; s.jobStatut=job.status; s.debut=new Date(job.started_at||s.debut).getTime()}}catch(e){}
      if(s.fabrique) vus.add(String(r.id));
    }
    Object.keys(SUIVI.runs).forEach(k=>{if(!vus.has(k)) delete SUIVI.runs[k]});
    const sd=await (await ghLire("/actions/workflows/site.yml/runs?per_page=1")).json(); const r=(sd.workflow_runs||[])[0];
    SUIVI.site=r&&r.status!=="completed"?{debut:new Date(r.run_started_at||r.created_at).getTime(),url:r.html_url}:null;
  }catch(e){}
  dessinerSuivi();
}
async function suiviRapide(){                                              // toutes les 5 s : l'avancement publié par le robot
  if(document.hidden||sansCleBloque()||(!lireJeton()&&Date.now()-(SUIVI.anoRapide||0)<110000)) return;
  if(!lireJeton()) SUIVI.anoRapide=Date.now();
  for(const s of Object.values(SUIVI.runs)){
    if(s.statut==="completed"&&s.lu) continue;
    try{const d=await (await ghLire(`/commits/${s.sha}/status?per_page=100`)).json(); s.vu=true;
      let st=(d.statuses||[]).find(x=>x.context==="progression-"+s.id);
      if(!st){try{const c=await (await ghLire(`/commits/${s.sha}/check-runs?check_name=progression-${s.id}`)).json(); const cr=(c.check_runs||[])[0];   // voie de secours
        if(cr&&cr.output&&cr.output.title) st={description:cr.output.title,state:cr.status!=="completed"?"pending":(cr.conclusion==="success"?"success":"failure")}}catch(e){}}
      if(st){const [p,ty,txt,fin]=String(st.description||"").split("|"); const pct=+p||0;
        if(pct!==s.pct||txt!==s.texte){s.pct=pct; s.t_pct=Date.now()} s.type=ty==="tiktok"?"🎵 Son TikTok":ty==="sketch"?"🎭 Sketch":ty; s.texte=txt; s.fin=fin?(+fin)*1000:null; s.etat=st.state; if(s.statut==="completed") s.lu=true}
    }catch(e){}
  }
  dessinerSuivi();
}
function dessinerSuivi(){                                                  // chaque seconde : barre et compte à rebours qui avancent
  const zones=document.querySelectorAll(".progressions"); if(!zones.length) return;
  const now=Date.now(), lignes=[];
  for(const s of Object.values(SUIVI.runs).sort((a,b)=>a.debut-b.debut)){
    let pct, txt, reste, cls="";
    const finEst=s.fin||(s.debut+SUIVI.durees.emission*1000);
    if(s.statut==="completed"&&s.pct==null&&s.conclusion==="success") continue;   // rien fabriqué (planning : rien à faire)
    if(s.statut==="completed"){
      const ok=s.conclusion==="success"&&s.etat!=="failure"; cls=ok?"ok":"ko"; pct=ok?100:(s.pct||0);
      txt=ok?(s.texte||"Vidéo prête"):(s.etat==="failure"?(s.texte||"Pas de vidéo cette fois"):"Échec de la fabrication"); reste=null;
    }else if(s.attente||s.jobStatut==="queued"||s.statut==="queued"){pct=0; txt=s.texte&&/En file/.test(s.texte)?s.texte:"En file d'attente (une autre vidéo passe avant)"; reste=null}
    else if(s.pct!=null&&!/En file/.test(s.texte||"")){
      reste=Math.max(0,(finEst-now)/1000);
      const plafond=Math.min(99,s.pct+(s.texte&&s.texte.includes("Dessin")?6:4));   // avance doucement jusqu'au prochain point du robot
      const u=s.fin?Math.min(1,(now-s.t_pct)/Math.max(1000,(s.fin-s.t_pct))):Math.min(1,(now-s.t_pct)/60000);
      pct=s.pct+(plafond-s.pct)*u*(s.fin?(100-s.pct)/100:0.5); txt=s.texte;
    }else{const u=Math.min(1,(now-s.debut)/120000); pct=1+2*u; txt=s.etapeGh&&!/Fabriquer/.test(s.etapeGh)?"Préparation de la machine ("+s.etapeGh+")":"Préparation de la machine"; reste=Math.max(0,(finEst-now)/1000)}
    const debut=new Date(s.debut).toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"});
    lignes.push(`<div class="prog ${cls}"><div class="haut"><span>${(s.type||"🎬 Vidéo")} · lancée à ${debut}</span><span>${Math.floor(pct)} %</span></div>
      <div class="barre"><div class="plein" style="width:${pct.toFixed(1)}%"></div></div>
      <div class="bas"><span>${String(txt||"").replace(/[<>&]/g,"")}</span><span>${reste!=null?fmtReste(reste)+" restantes":(cls==="ko"?`<a style="color:var(--bleu)" href="${s.url}" target="_blank" rel="noopener">Détail</a>`:"")}</span></div></div>`);
  }
  if(SUIVI.site){const u=Math.min(0.97,(now-SUIVI.site.debut)/(SUIVI.durees.site*1000)), r=Math.max(0,SUIVI.durees.site-(now-SUIVI.site.debut)/1000);
    lignes.push(`<div class="prog"><div class="haut"><span>🌐 Mise en ligne sur le site</span><span>${Math.floor(u*100)} %</span></div><div class="barre"><div class="plein" style="width:${(u*100).toFixed(1)}%"></div></div><div class="bas"><span>La vidéo apparaîtra dans l'appli à la fin</span><span>${fmtReste(r)} restantes</span></div></div>`)}
  if(sansCleBloque()) lignes.unshift(`<p class="note">⏸️ Suivi en direct en pause : sans connexion, GitHub limite les lectures (reprise vers ${new Date(SUIVI.bloque).toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"})}). Connectez la régie (⚙️ Réglages) pour un suivi sans limite.</p>`);
  const html=lignes.length?lignes.join(""):'<p class="note">Aucune fabrication en cours.</p>';
  zones.forEach(z=>{if(z.innerHTML!==html) z.innerHTML=html});
  const m=$("#mSuivi"); if(m&&m.dataset.libre==="1") m.style.display=lignes.length?"none":"";
}
setInterval(suiviLent,20000); setInterval(suiviRapide,5000); setInterval(dessinerSuivi,1000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden){suiviLent().then(suiviRapide)}});
async function verifierEnCours(){
  suiviLent().then(suiviRapide);
  if(!lireJeton()||!CONF.depot) return;
  try{const d=await (await gh("/actions/workflows/emission.yml/runs?per_page=5")).json();
    const run=(d.workflow_runs||[]).find(x=>x.status!=="completed"); const z=$("#mSuivi");
    if(run&&z.dataset.libre==="1") z.innerHTML=`🎬 Une vidéo est en fabrication (lancée à ${new Date(run.created_at).toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"})}, ${run.status==="queued"?"en file d'attente":"en cours"}). <a style="color:var(--bleu)" href="${run.html_url}" target="_blank" rel="noopener">Détail</a>`;
  }catch(e){}
}
const b64u=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
const deB64u=s=>Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/")+"===".slice((s.length+3)%4)),c=>c.charCodeAt(0));
async function nettoyerAbos(v){                                            // appareils disparus (signalés par le robot) : retirés de la liste
  try{
    const morts=new Set(CONF.abos_morts||[]); if(!morts.size) return; let l=[]; try{l=JSON.parse(v.PUSH_ABONNEMENTS||"[]")}catch(_){return}
    const emp=async e=>Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(String(e))))).map(b=>b.toString(16).padStart(2,"0")).join("").slice(0,20);
    const garde=[]; for(const a of l){if(!morts.has(await emp(a.endpoint))) garde.push(a)}
    if(garde.length===l.length) return;
    await ecrireVar("PUSH_ABONNEMENTS",JSON.stringify(garde)); v.PUSH_ABONNEMENTS=JSON.stringify(garde);
    toast(garde.length?`🔔 ${l.length-garde.length} appareil(s) qui ne recevaient plus les alertes retiré(s)`:"🔔 Plus aucun appareil ne reçoit les alertes : réactivez les notifications (Réglages)");
  }catch(e){}
}
$("#activerNotifs").onclick=async()=>{
  const z=$("#suiviNotif");
  try{
    if(!lireJeton()) throw new Error("connectez d'abord la régie");
    if(!("serviceWorker" in navigator)||!("PushManager" in window)) throw new Error("cet appareil ne gère pas les notifications (sur iPhone : installez d'abord l'appli sur l'écran d'accueil)");
    if(await Notification.requestPermission()!=="granted") throw new Error("autorisation refusée : réactivez-la dans les réglages du navigateur");
    z.textContent="Activation…";
    if(!Object.keys(VARS).length){const r=await gh("/actions/variables?per_page=100"); (await r.json()).variables.forEach(x=>VARS[x.name]=x.value)}
    let pub=VARS.VAPID_PUBLIQUE;
    if(!pub||!VARS.VAPID_PRIVEE){                                   // clés du robot, créées une seule fois
      const k=await crypto.subtle.generateKey({name:"ECDSA",namedCurve:"P-256"},true,["sign","verify"]);
      pub=b64u(await crypto.subtle.exportKey("raw",k.publicKey)); const pr=b64u(await crypto.subtle.exportKey("pkcs8",k.privateKey));
      await ecrireVar("VAPID_PRIVEE",pr); await ecrireVar("VAPID_PUBLIQUE",pub); VARS.VAPID_PRIVEE=pr; VARS.VAPID_PUBLIQUE=pub;
    }
    const reg=await navigator.serviceWorker.ready; let ab=await reg.pushManager.getSubscription();
    if(ab&&b64u(ab.options.applicationServerKey)!==pub){await ab.unsubscribe(); ab=null}
    if(!ab) ab=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:deB64u(pub)});
    let l=[]; try{l=JSON.parse(VARS.PUSH_ABONNEMENTS||"[]")}catch(_){}
    l=l.filter(x=>x.endpoint!==ab.endpoint); l.push(ab.toJSON()); l=l.slice(-6);
    await ecrireVar("PUSH_ABONNEMENTS",JSON.stringify(l)); VARS.PUSH_ABONNEMENTS=JSON.stringify(l);
    z.textContent="✅ Notifications activées sur cet appareil ("+l.length+" appareil(s) au total). Touchez « Envoyer une notification de test »."
  }catch(e){z.textContent="Impossible : "+e.message}
};
$("#betLancer").onclick=()=>lancerFlux("betisier.yml",$("#betLancer"),"😅 Bêtisier en montage (2 à 5 min). Il apparaîtra dans la liste des vidéos.",{jours:"7"},$("#suiviBet"));
let VX={rec:null,morceaux:[],b64:"",fin:null};
$("#vxRec").onclick=async()=>{
  if(VX.rec&&VX.rec.state==="recording"){VX.rec.stop();return}
  try{
    const flux=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
    const type=["audio/webm;codecs=opus","audio/ogg;codecs=opus","audio/mp4"].find(x=>window.MediaRecorder&&MediaRecorder.isTypeSupported(x))||"";
    VX.rec=new MediaRecorder(flux,type?{mimeType:type,audioBitsPerSecond:16000}:{audioBitsPerSecond:16000}); VX.morceaux=[];
    VX.rec.ondataavailable=e=>VX.morceaux.push(e.data);
    VX.rec.onstop=()=>{flux.getTracks().forEach(x=>x.stop()); clearTimeout(VX.fin); $("#vxRec").textContent="⏺️ Recommencer";
      const b=new Blob(VX.morceaux,{type:VX.rec.mimeType}); $("#vxEcoute").src=URL.createObjectURL(b); $("#vxEcoute").style.display="block";
      const r=new FileReader(); r.onload=()=>{VX.b64=String(r.result).split(",")[1]||"";
        const ok=VX.b64.length>3000&&VX.b64.length<60000; $("#vxEnv").disabled=!ok||!lireJeton();
        $("#suiviVx").textContent=ok?"Réécoutez, puis envoyez.":(VX.b64.length>=60000?"Trop long : recommencez en 15 secondes environ.":"Trop court : parlez au moins 8 secondes.")};
      r.readAsDataURL(b)};
    VX.rec.start(); $("#vxRec").textContent="⏹️ Arrêter"; $("#suiviVx").textContent="🔴 Enregistrement… (arrêt automatique à 18 s)";
    VX.fin=setTimeout(()=>{if(VX.rec.state==="recording")VX.rec.stop()},18000);
  }catch(e){$("#suiviVx").textContent="Micro indisponible : autorisez le micro pour ce site ("+e.message+")."}
};
$("#vxEnv").onclick=()=>{if(!VX.b64)return;
  lancerFlux("voix_auteur.yml",$("#vxEnv"),"🎙️ Votre voix est en cours d'installation (1 à 2 min). Elle servira dès la prochaine vidéo.",{role:$("#vxRole").value,emotion:$("#vxEmo").value,audio:VX.b64},$("#suiviVx"))};
$("#couperNotifs").onclick=async()=>{                                     // plus aucune notification sur CET appareil
  const z=$("#suiviNotif");
  try{
    if(!lireJeton()) throw new Error("connectez d'abord la régie");
    z.textContent="Désactivation…"; let fin="";
    if("serviceWorker" in navigator){const reg=await Promise.race([navigator.serviceWorker.ready,new Promise(r=>setTimeout(()=>r(null),4000))]); const ab=reg&&reg.pushManager&&await reg.pushManager.getSubscription();
      if(ab){fin=ab.endpoint; await ab.unsubscribe()}}
    if(!Object.keys(VARS).length){const r=await gh("/actions/variables?per_page=100"); (await r.json()).variables.forEach(x=>VARS[x.name]=x.value)}
    let l=[]; try{l=JSON.parse(VARS.PUSH_ABONNEMENTS||"[]")}catch(_){}
    const reste=fin?l.filter(x=>x.endpoint!==fin):l;
    if(reste.length!==l.length){await ecrireVar("PUSH_ABONNEMENTS",JSON.stringify(reste)); VARS.PUSH_ABONNEMENTS=JSON.stringify(reste)}
    z.textContent=fin?`🔕 Notifications désactivées sur cet appareil (${reste.length} autre(s) appareil(s) les reçoivent encore). Touchez « Activer » pour les remettre.`
                     :"🔕 Cet appareil ne recevait pas de notifications.";
  }catch(e){z.textContent="Impossible : "+e.message}
};
$("#testNotif").onclick=()=>lancerFlux("notifier.yml",$("#testNotif"),"🔔 Envoi d'une notification de test (environ 30 s)…",{titre:"Petits.Dramas",texte:"Les notifications marchent 🎉"},$("#suiviNotif"));
$("#realLancer").onclick=()=>{if(!lireJeton()){toast("Connectez la régie");return} const f=$("#realFormat").value;
  if(confirm(f==="mini"?"Fabriquer un gag éclair réaliste ? Il consomme des crédits ElevenLabs (vidéo IA).":"Fabriquer un sketch long réaliste ? Une dizaine de plans de vidéo IA : c'est nettement plus de crédits ElevenLabs."))
  lancerFlux("emission.yml",$("#realLancer"),f==="mini"?"🎬 Gag réaliste en fabrication (20 à 40 min).":"🎬 Sketch long réaliste en fabrication (30 à 60 min).",{format:f,rendu:"realiste"},$("#suiviReal"))};
{const S=__STATS__, e=$("#statsEtat");
 e.textContent=!S.compte?"Enregistrez le compte (OK) : le robot lira les vues chaque matin."
  :"Dernière lecture de @"+S.compte+(S.maj?" le "+new Date(S.maj).toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"}):"")+" : "
   +(S.videos?S.videos+" vidéo(s), "+S.vues.toLocaleString("fr-FR")+" vues au total.":"aucune vidéo publiée pour l'instant.")}
$("#majsite").onclick=()=>lancerFlux("site.yml",$("#majsite"),"🔄 Mise à jour de l'application (2 à 3 min)…");
activer(false);
// ------------------------------------------------ application installable
if("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(()=>{});
let invite=null;
window.addEventListener("beforeinstallprompt",e=>{e.preventDefault();invite=e;$("#installer").style.display="inline-block"});
$("#installer").onclick=async()=>{if(!invite)return;invite.prompt();await invite.userChoice.catch(()=>{});invite=null;$("#installer").style.display="none"};
window.addEventListener("appinstalled",()=>{$("#installer").style.display="none";toast("Application installée ✓")});
rendre(); rendreRecents(); rendreOutils(); afficherAuto(); lireAuto(); majBoutons(); majBandeau(); verifierEnCours(); majPointTk(); $("#barre").style.display="none";
try{appliquerOnglets(localStorage.getItem("onglets_masques")||"")}catch(e){}
$("#tkColler").onclick=async()=>{                                          // dans TikTok : « Copier le lien », puis ce bouton
  try{
    const t=await navigator.clipboard.readText();
    const m=(t||"").match(/https?:\/\/([a-z0-9-]+\.)*tiktok\.com\/\S+/i);
    if(!m){toast("Aucun lien TikTok copié. Dans TikTok : Partager → Copier le lien, puis réessayez.");return}
    $("#tkLien").value=m[0]; $("#tkCreer").classList.add("pulse"); toast("Lien collé ✔ Touchez « Fabriquer sur ce son ».");
  }catch(e){toast("Le téléphone refuse l'accès au presse-papiers : appuyez longuement dans la case du lien puis « Coller ».")}
};
(function partageRecu(){                                                   // lien partagé depuis l'appli TikTok (Web Share Target)
  const q=new URLSearchParams(location.search); if(!q.get("partage")) return;
  const m=((q.get("lien")||"")+" "+(q.get("texte")||"")+" "+(q.get("titre")||"")).match(/https?:\/\/([a-z0-9-]+\.)*tiktok\.com\/\S+/i);
  history.replaceState(null,"",location.pathname);
  allerOnglet("tiktok");
  if(!m){toast("Le partage ne contenait pas de lien TikTok");return}
  $("#tkLien").value=m[0].replace(/[).,;]+$/,""); $("#tkLien").scrollIntoView({behavior:"smooth",block:"center"});
  $("#tkCreer").classList.add("pulse"); toast("Lien TikTok reçu ✓ Touchez « Fabriquer sur ce son »");
})();
if(lireJeton()) chargerReglages();                                        // onglets cachés et vidéos cochées : réglages de tous les appareils
if(!CONF.depot) $("#autoAide").textContent="Site de test : boutons du robot inactifs.";
</script></body></html>
"""

if __name__ == "__main__":
    construire()
