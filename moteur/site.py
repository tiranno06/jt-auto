"""Site de contrôle (GitHub Pages) : liste des émissions, de la plus récente à la plus ancienne, avec
- un interrupteur « Publication automatique » (variable PUBLICATION_AUTO du dépôt) pour vérifier les vidéos avant publication ;
- un bouton « Publier sur TikTok » qui lance le workflow publier.yml : la vidéo part toute seule via Buffer ;
- en secours, le partage manuel (menu de partage du téléphone vers l'application TikTok).
Les boutons du robot utilisent un jeton GitHub personnel, saisi une fois et gardé uniquement dans le navigateur.
Usage : python moteur/site.py  (dans le workflow, après la publication)"""
import html, json, os, shutil, subprocess

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE = os.path.join(RACINE, "site")
NB = int(os.environ.get("SITE_NB_VIDEOS", "15"))          # GitHub Pages : 1 Go max, ~25 Mo par vidéo

def recuperer(e, dest):
    """Copie la vidéo depuis sortie/ ou la télécharge depuis la Release du mois."""
    local = os.path.join(RACINE, "sortie", e["fichier"])
    if os.path.exists(local): shutil.copy(local, dest); return True
    r = subprocess.run(["gh", "release", "download", e["tag"], "-p", e["fichier"], "-D", os.path.dirname(dest), "--clobber"],
                       capture_output=True, text=True)
    if r.returncode: print(f"  vidéo introuvable {e['fichier']} : {r.stderr.strip()[:200]}")
    return os.path.exists(dest)

def affiche(video, image):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "4", "-i", video, "-frames:v", "1",
                    "-vf", "scale=360:-2", "-q:v", "4", image])

def construire():
    hist = json.load(open(os.path.join(RACINE, "episodes", "historique.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(RACINE, "episodes", "historique.json")) else []
    shutil.rmtree(SITE, ignore_errors=True); os.makedirs(os.path.join(SITE, "videos"))
    liste = []
    comptes = {}
    for e in reversed([h for h in hist if h.get("fichier")]):
        cat = "manuel" if e.get("manuel") else "court" if e.get("format") == "mini" else "long"
        if comptes.get(cat, 0) >= NB: continue                             # jusqu'à NB vidéos par onglet
        comptes[cat] = comptes.get(cat, 0) + 1
        dest = os.path.join(SITE, "videos", e["fichier"])
        if not recuperer(e, dest): continue
        poster = e["fichier"].replace(".mp4", ".jpg"); affiche(dest, os.path.join(SITE, "videos", poster))
        liste.append(dict(titre=e.get("titre", ""), date=e.get("date", ""), fichier=e["fichier"], poster=poster,
                          legende=e.get("legende", ""), publie=e.get("publie"), vues=e.get("vues"),
                          format=e.get("format", ""), manuel=bool(e.get("manuel")), avis=e.get("avis", 0), note=e.get("note"),
                          programmee=e.get("programmee"), couts=e.get("couts") or {}, duree=e.get("duree"),
                          likes=e.get("likes"), commentaires=e.get("commentaires"), partages=e.get("partages")))
    import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import marque
    nom = marque.NOM                                                       # nom de la chaîne (le JT garde son propre nom)
    conf = {"depot": os.environ.get("GITHUB_REPOSITORY", ""), "branche": os.environ.get("GITHUB_REF_NAME") or "main"}
    try: st = json.load(open(os.path.join(RACINE, "episodes", "stats.json"), encoding="utf-8"))
    except (OSError, ValueError): st = {}
    try: alertes = json.load(open(os.path.join(RACINE, "episodes", "alertes.json"), encoding="utf-8"))[-15:]
    except (OSError, ValueError): alertes = []
    resume = {"compte": st.get("compte", ""), "maj": st.get("maj", ""), "videos": len(st.get("videos", [])),
              "vues": sum(v.get("vues", 0) for v in st.get("videos", [])), "liees": sum(1 for v in st.get("videos", []) if v.get("fichier")),
              "abonnes": st.get("abonnes"), "abonnes_hist": (st.get("abonnes_hist") or [])[-24 * 8:]}
    page = (PAGE.replace("__NOM__", html.escape(nom)).replace("__CONF__", json.dumps(conf)).replace("__STATS__", json.dumps(resume, ensure_ascii=False))
            .replace("__ALERTES__", json.dumps(alertes, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__DATA__", json.dumps(liste, ensure_ascii=False).replace("</", "<\\/")))
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(page)
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
                 "icons": [{"src": f"logo-{t}.png", "sizes": f"{t}x{t}", "type": "image/png", "purpose": "any"} for t in (192, 512)] +
                          [{"src": f"logo-{t}-maskable.png", "sizes": f"{t}x{t}", "type": "image/png", "purpose": "maskable"} for t in (192, 512)]}
    json.dump(manifeste, open(os.path.join(SITE, "manifest.webmanifest"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(SITE, "sw.js"), "w").write(SW)

# Service worker : l'appli s'ouvre même hors connexion (dernière version de la page), sans jamais mettre en cache
# les vidéos (trop lourdes) ni les appels à GitHub.
SW = r"""const CACHE = "regie-v20";
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
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.endsWith(".mp4")) return;
  if (e.request.mode === "navigate" || u.pathname.endsWith("/") || u.pathname.endsWith(".html")) {
    // page : toujours la plus récente si le réseau répond en moins de 3 s, sinon la copie gardée (ouverture instantanée hors ligne)
    e.respondWith(new Promise(ok => {
      let fini = false; const copie = () => caches.match(e.request).then(r => r || caches.match("./"));
      const minuteur = setTimeout(() => copie().then(r => { if (r && !fini) { fini = true; ok(r); } }), 2500);
      fetch(e.request).then(r => { garder(e.request, r); if (!fini) { fini = true; clearTimeout(minuteur); ok(r); } })
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
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--texte);font-family:Poppins,system-ui,sans-serif}
header{padding:20px 16px 4px;text-align:center}
h1{margin:0;font-size:22px;color:var(--jaune);letter-spacing:.5px;text-shadow:0 2px 0 var(--rouge)}
.sous{color:var(--doux);font-size:13px;margin-top:4px}
main{max-width:560px;margin:0 auto;padding:8px 16px 260px}
.panneau{background:var(--carte);border:2px solid var(--ligne);border-radius:16px;padding:14px;margin:12px 0}
.auto{display:flex;align-items:center;gap:12px}
.auto .txt{flex:1;min-width:0}.auto b{display:block;font-size:15px}.auto small{color:var(--doux);font-size:12px;line-height:1.4;display:block}
.inter{position:relative;width:62px;height:34px;flex:none;border-radius:999px;background:#3a3d50;border:0;cursor:pointer;transition:background .2s}
.inter::after{content:"";position:absolute;top:4px;left:4px;width:26px;height:26px;border-radius:50%;background:#fff;transition:left .2s}
.inter.on{background:var(--vert)}.inter.on::after{left:32px}.inter:disabled{opacity:.45;cursor:wait}
details{margin-top:10px;font-size:13px;color:var(--doux)}summary{cursor:pointer;color:var(--bleu)}
.jeton{display:flex;gap:8px;margin-top:8px}
input,textarea{flex:1;min-width:0;font:inherit;font-size:14px;padding:10px;border-radius:10px;border:1px solid var(--ligne);background:#0e0f17;color:var(--texte)}
.carte{display:flex;gap:12px;background:var(--carte);border:2px solid var(--ligne);border-radius:16px;padding:10px;margin:10px 0;cursor:pointer;transition:border-color .15s,transform .1s}
.carte:active{transform:scale(.99)}.carte.choisie{border-color:var(--jaune)}
.carte{position:relative}.croix{position:absolute;top:8px;right:8px;width:34px;height:34px;border-radius:50%;border:none;background:rgba(0,0,0,.35);color:#fff;font-size:18px;line-height:34px;cursor:pointer;padding:0}
.croix:hover{background:#d33}.carte.supprimee{opacity:.35;pointer-events:none}
.carte img{width:84px;height:150px;object-fit:cover;border-radius:10px;flex:none;background:#000}
.infos{flex:1;min-width:0;display:flex;flex-direction:column;gap:6px}
.titre{font-weight:700;font-size:16px;line-height:1.25}.date{color:var(--doux);font-size:13px}
.badge{align-self:flex-start;font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px}
.ok{background:rgba(47,191,113,.15);color:var(--vert)}.ko{background:rgba(227,32,58,.15);color:#ff6b7d}.att{background:rgba(255,159,26,.15);color:var(--orange)}
.etat{font-size:12px;color:var(--doux)}
.vide{text-align:center;color:var(--doux);margin-top:60px}
#barre{position:fixed;left:0;right:0;bottom:0;background:rgba(14,15,23,.97);border-top:1px solid var(--ligne);padding:12px 16px calc(12px + env(safe-area-inset-bottom));backdrop-filter:blur(8px)}
.int{max-width:560px;margin:0 auto}
#choix{font-size:13px;color:var(--doux);margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
button{font:inherit;border:0;border-radius:14px;cursor:pointer}
#publier{width:100%;padding:15px;font-size:17px;font-weight:700;background:linear-gradient(90deg,#25f4ee,#fe2c55);color:#fff}
#publier:disabled{opacity:.4;cursor:not-allowed}
#publier.confirmer{background:var(--jaune);color:#111}
.ligne2{display:flex;gap:8px;margin-top:8px}
#plus{margin-top:8px;font-size:14px}#plus summary{cursor:pointer;color:var(--bleu);padding:6px 0}
#plus input{width:100%;margin-top:6px}
.alerte{background:#3a1d22;border:1px solid var(--rouge);border-radius:12px;padding:10px 12px;margin:0 0 12px;font-size:13px}
.alerte.ok{background:#16301f;border-color:var(--vert)}
.barres{display:flex;flex-direction:column;gap:6px}.barres div{display:flex;align-items:center;gap:8px;font-size:12px}
.barres span.b{height:12px;background:var(--jaune);border-radius:6px;min-width:2px}
.chiffres{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.chiffres div{background:var(--carte);border:1px solid var(--ligne);border-radius:12px;padding:10px}
.chiffres b{display:block;font-size:20px;color:var(--jaune)}
.second.actif{border-color:var(--jaune);color:var(--jaune)}
.second{flex:1;padding:11px 6px;font-size:13px;background:var(--carte);color:var(--texte);border:1px solid var(--ligne)}
.second:disabled{opacity:.4}
#suivi{font-size:13px;margin-top:8px;min-height:18px;color:var(--doux)}
#toast{position:fixed;top:16px;left:50%;transform:translateX(-50%);background:var(--jaune);color:#111;font-weight:700;padding:10px 16px;border-radius:12px;display:none;z-index:9;max-width:90vw;text-align:center}
.onglets{position:sticky;top:0;z-index:5;display:flex;gap:8px;max-width:560px;margin:0 auto;padding:8px 16px;background:var(--bg)}
.onglet{flex:1;padding:10px 4px;font-size:14px;white-space:nowrap;font-weight:700;background:var(--carte);color:var(--doux);border:1px solid var(--ligne)}
.onglet.actif{background:var(--jaune);color:#111;border-color:var(--jaune)}
h2{margin:0 0 10px;font-size:16px}
label{display:block;font-size:13px;color:var(--doux);margin:10px 0}
select{display:block;width:100%;margin-top:6px;font:inherit;font-size:15px;padding:10px;border-radius:10px;border:1px solid var(--ligne);background:#0e0f17;color:var(--texte)}
label .jeton{margin-top:6px}
.note{font-size:12px;color:var(--doux);line-height:1.45}
.action{display:block;width:100%;margin:8px 0;padding:13px;font-size:15px;font-weight:700;background:var(--carte);color:var(--texte);border:1px solid var(--ligne)}
.action:disabled{opacity:.45}
.lien{display:block;padding:11px 0;color:var(--bleu);text-decoration:none;border-bottom:1px solid var(--ligne);font-size:14px}.lien:last-child{border:0}
@media (min-width:900px){
  body[data-onglet="videos"] header, body[data-onglet="videos"] .onglets, body[data-onglet="videos"] main{margin-right:420px}
  header,.onglets{max-width:none}
  .onglets{max-width:560px;margin-left:auto;margin-right:auto}
  body[data-onglet="videos"] .onglets{margin-left:24px;margin-right:444px;max-width:none}
  main{max-width:1000px;padding:8px 24px 40px !important}
  body[data-onglet="videos"] main{max-width:none}
  #liste{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:0 14px}
  #o-config{display:grid;grid-template-columns:1fr 1fr;gap:0 16px;align-items:start}
  #o-config[style*="none"]{display:none !important}
  #o-config>.note,#cfgConnexion{grid-column:1/-1}
  #barre{left:auto;right:0;top:0;bottom:0;width:420px;border-top:0;border-left:1px solid var(--ligne);overflow:auto;padding:24px;display:flex;align-items:flex-start}
  #barre .int{width:100%}
  #barre video{max-height:62vh}
}
textarea{resize:vertical}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 10px}
.chip{padding:7px 11px;border-radius:999px;font-size:13px;background:var(--carte);color:var(--texte);border:1px solid var(--ligne)}
#jours .chip{width:40px;padding:8px 0;color:var(--doux)} #jours .chip.on{background:var(--jaune);color:#111;border-color:var(--jaune)}
.creneau{display:flex;gap:6px;align-items:center;margin:6px 0}
.creneau .heure{display:flex;gap:4px;flex:0 0 140px} .creneau .heure select{flex:1;padding:10px 4px;margin:0} .creneau select{flex:1;margin:0} .creneau .second{flex:0 0 42px;padding:9px 0}
.auto-h{flex:0 0 140px;font-weight:700;color:var(--jaune);text-align:center}
label>textarea{display:block;width:100%;margin-top:6px;box-sizing:border-box}
.onglet.reg{flex:0 0 42px;padding:10px 0}
@media (max-width:420px){.onglet{font-size:12.5px}.onglets{gap:6px;padding:8px 10px}}
#barre{z-index:10;max-height:88vh;overflow-y:auto}
video{width:100%;border-radius:12px;margin:0 0 8px;max-height:34vh;background:#000;display:none}
#cadreVideo{position:relative}
#fermer{display:none;position:absolute;top:8px;right:8px;width:40px;height:40px;padding:0;border-radius:50%;font-size:20px;font-weight:700;line-height:40px;background:rgba(0,0,0,.65);color:#fff;border:1px solid rgba(255,255,255,.35);z-index:2}
#apercu[style*="block"]+#fermer{display:block}
</style></head><body data-onglet="videos">
<header><h1><img src="logo-192.png" alt="" style="width:44px;height:44px;border-radius:12px;vertical-align:-10px;margin-right:10px">__NOM__</h1><div class="sous">Régie de la chaîne · vidéos de la plus récente à la plus ancienne</div>
<button id="installer" style="display:none;margin-top:10px;padding:9px 16px;font-size:14px;font-weight:700;background:var(--jaune);color:#111">📲 Installer l'application</button></header>
<nav class="onglets"><button class="onglet actif" data-o="videos" data-f="court">📱 Courtes</button><button class="onglet" data-o="videos" data-f="long">🎬 Longues</button><button class="onglet" data-o="videos" data-f="manuel">✍️ Manuel</button><button class="onglet reg" data-o="stats" aria-label="Statistiques" title="Statistiques">📊</button><button class="onglet reg" data-o="config" aria-label="Réglages" title="Réglages">⚙️</button></nav>
<main>
 <div id="o-videos">
  <section class="panneau">
    <div class="auto">
      <div class="txt"><b id="autoTitre">Publication automatique</b><small id="autoAide">Connectez la régie (ci-dessous) pour utiliser les boutons.</small></div>
      <button class="inter" id="inter" aria-label="Publication automatique" disabled></button>
    </div>
    <details id="reglages"><summary id="resume">Connecter la régie (une seule fois)</summary>
      <p>Collez votre jeton GitHub (voir LISEZMOI, étape « Régie »). Il reste uniquement dans ce navigateur.</p>
      <div class="jeton"><input id="jeton" type="password" placeholder="github_pat_…" autocomplete="off"><button class="second" id="garder" style="flex:none;padding:10px 14px">Enregistrer</button></div>
      <p><button class="second" id="oublier" style="padding:8px 12px">Déconnecter ce navigateur</button></p>
    </details>
  </section>
  <section class="panneau" id="manuel" style="display:none"><h2>✍️ Créer une vidéo à partir de mon texte</h2>
    <p class="note">À part du robot automatique : la vidéo n'entre pas dans le cycle et n'est jamais publiée toute seule. Elle apparaît ici quand elle est prête (15 à 40 min).</p>
    <label>Ce que je tape<select id="mMode">
      <option value="idee">💡 Une idée ou un thème : le robot écrit le sketch</option>
      <option value="script">📝 Mon script : les répliques sont jouées mot pour mot</option></select></label>
    <label><span id="mAide">Idée / thème de la vidéo</span><textarea id="mTexte" rows="6" maxlength="1800" placeholder="Ex. : Jojo essaie de résilier son abonnement de salle de sport, mais le conseiller ne le laisse jamais partir."></textarea></label>
    <label>Format<select id="mFormat"><option value="mini">⚡ Gag éclair (15-25 s)</option><option value="libre">🎭 Sketch long (+1 min)</option></select></label>
    <label>Rendu<select id="mRendu"><option value="">🎨 Dessin animé (Jojo, Kévin, Lila)</option><option value="realiste">🎬 Réaliste, filmé par l'IA (coûte des crédits ElevenLabs)</option></select></label>
    <label id="mStyleL">Ton<select id="mStyle"><option value="">Comme d'habitude (humour noir)</option><option value="Ton encore plus absurde et délirant.">Plus absurde</option><option value="Ton plus méchant et plus cash.">Plus méchant</option><option value="Ton plus tendre, humour bienveillant.">Plus tendre</option></select></label>
    <button class="action" id="mCreer">🎬 Créer la vidéo</button>
    <div id="mSuivi" class="note"></div>
  </section>
  <div id="liste"></div>
 </div>
 <div id="o-stats" style="display:none"></div>
 <div id="o-config" style="display:none">
  <section class="panneau" id="cfgConnexion"><h2>🔑 Connecter la régie</h2>
    <p class="note">Pour modifier les réglages depuis cet appareil (téléphone ou PC), collez une fois votre clé GitHub de régie. Elle reste uniquement dans ce navigateur.
    Pas encore de clé ? <a style="color:var(--bleu)" href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">Créer la clé</a> : dépôt <b>jt-auto</b> uniquement, droits <b>Actions</b> et <b>Variables</b> en « Read and write ».</p>
    <div class="jeton"><input id="jeton2" type="password" placeholder="github_pat_…" autocomplete="off"><button class="second" id="garder2" style="flex:none;padding:10px 14px">Connecter</button></div>
  </section>
  <p class="note" id="cfgEtat"></p>
  <section class="panneau"><h2>🎬 Programme</h2>
    <label>Type des vidéos automatiques<select id="selFormat" class="perso">
      <option value="cycle">⭐ Cycle croissance : 3 gags éclair puis 1 sketch long</option>
      <option value="seq">🧩 Ma séquence personnalisée (je compose l'ordre)</option>
      <option value="mini">⚡ Gags éclair uniquement</option>
      <option value="libre">🎭 Sketchs longs uniquement</option>
      <option value="actu">📰 JT d'actualité uniquement</option></select></label>
    <div id="seqBloc" style="display:none">
      <p class="note">Composez l'ordre des vidéos automatiques ; il se répète en boucle. Touchez une étiquette pour la retirer.</p>
      <div id="seqChips" class="chips"></div>
      <div class="ligne2"><button class="second perso" data-ajout="mini">+ ⚡ Gag</button><button class="second perso" data-ajout="libre">+ 🎭 Long</button><button class="second perso" data-ajout="actu">+ 📰 JT</button></div>
      <button class="action perso" id="seqEnr">Enregistrer la séquence</button>
    </div>
    <p class="note">Les vidéos de plus d'une minute sont les seules payées par TikTok (10 000 abonnés et 100 000 vues sur 30 jours) ; les courtes font monter les abonnés. Un créneau du planning peut aussi imposer son propre type.</p>
  </section>
  <section class="panneau"><h2>📅 Planning</h2>
    <label>Rythme<select data-var="FREQUENCE" data-def="1"><option value="1">Tous les jours cochés</option><option value="2">Un jour sur deux</option><option value="3">Un jour sur trois</option><option value="0">⏸ Pause (le robot ne produit plus)</option><option value="2x" hidden>Deux par jour (ancien réglage)</option></select></label>
    <p class="note" style="margin-bottom:4px">Jours de fabrication</p>
    <div id="jours" class="chips"></div>
    <p class="note" style="margin-bottom:4px">Créneaux (heure de Paris) et type de vidéo pour chacun</p>
    <div id="creneaux"></div>
    <div class="ligne2"><button class="second perso" id="ajCreneau">+ Ajouter un créneau</button><button class="second perso" id="ajAuto">+ Créneau 📊 automatique</button></div>
    <button class="action perso" id="planEnr">Enregistrer le planning</button>
    <p class="note">La vidéo est prête 20 à 40 minutes après l'heure du créneau (le robot se réveille toutes les 30 minutes et rattrape un créneau manqué). « 📊 automatique » : l'heure qui fait le plus de vues sur vos statistiques (17 h tant qu'il y a moins de 8 vidéos).</p>
  </section>
  <section class="panneau"><h2>✍️ Écriture</h2>
    <label>Note minimale pour fabriquer une vidéo<select data-var="QUALITE_MIN" data-def="85"><option value="90">90/100</option><option value="85">85/100 (recommandé)</option><option value="80">80/100</option><option value="75">75/100</option><option value="70">70/100</option><option value="0">Toujours fabriquer (pas de minimum)</option></select></label>
    <label>Sujets essayés au plus pour l'atteindre<select data-var="SUJETS_MAX" data-def="3"><option value="2">2 (économique)</option><option value="3">3 (recommandé)</option><option value="4">4</option><option value="5">5 (le plus exigeant)</option></select></label>
    <label>Essais par créneau si la note n'est pas atteinte<select data-var="ESSAIS_MAX" data-def="3"><option value="1">1 (pas de nouvel essai)</option><option value="2">2</option><option value="3">3 (recommandé)</option><option value="4">4</option></select></label>
    <p class="note">Si aucun sketch n'atteint la note minimale, le robot ne fabrique rien (voix et décors économisés), vous prévient, et réessaie au réveil suivant (toutes les 30 min environ) tant que le créneau a moins de 2 h et que la limite d'essais n'est pas atteinte. Chaque essai coûte environ 2 à 3 $ de Claude. Les vidéos que vous lancez vous-même (Manuel, Refaire, série d'un seul jet) sont toujours fabriquées.</p>
    <label>Note minimale pour la publication automatique<select data-var="SEUIL_PUBLICATION" data-def="80"><option value="90">90/100</option><option value="85">85/100</option><option value="80">80/100 (recommandé)</option><option value="75">75/100</option><option value="70">70/100</option></select></label>
    <label>Objectif d'écriture (le robot réécrit jusqu'à cette note)<select data-var="SEUIL_QUALITE" data-def="90"><option value="95">95/100 (très rare)</option><option value="90">90/100 (recommandé)</option><option value="85">85/100</option><option value="80">80/100</option><option value="75">75/100</option></select></label>
    <label>Auteur (modèle Claude)<select data-var="MODELE_CLAUDE" data-def="claude-opus-5-5"><option value="claude-opus-5-5">Opus (le plus drôle, recommandé)</option><option value="claude-sonnet-5-5">Sonnet (économique)</option></select></label>
    <div class="auto" style="margin-bottom:12px"><div class="txt"><b>Étapes simples en économique</b><small>Atelier de vannes, jury, idées et relecture sur un modèle moins cher (l'écriture et la critique restent sur l'auteur choisi). Coupé : tout sur l'auteur.</small></div><button class="inter" data-var="ETAPES_ECO" data-def="0" data-bascule="1"></button></div>
    <div class="auto" style="margin-bottom:12px"><div class="txt"><b>S'inspirer des tendances</b><small>Pour trouver les idées, le robot regarde les sujets qui buzzent en France cette semaine (recherche web, quelques centimes).</small></div><button class="inter" data-var="TENDANCES" data-def="1" data-bascule="1"></button></div>
    <label>Plafond de dépenses Claude par mois, en dollars (vide = pas de plafond)<div class="jeton"><input data-var="BUDGET_MOIS" data-def="" data-texte="1" maxlength="8" inputmode="decimal" placeholder="ex. 30"><button class="second" data-enr="BUDGET_MOIS" style="flex:none;padding:10px 14px">OK</button></div></label>
    <p class="note">Plafond atteint : les vidéos automatiques s'arrêtent jusqu'au mois suivant (les boutons restent utilisables).</p>
    <label>Nombre de retouches maximum<select data-var="MAX_REECRITURES" data-def="4"><option value="4">4 (recommandé)</option><option value="2">2 (économique)</option><option value="6">6 (le plus exigeant)</option></select></label>
  </section>
  <section class="panneau"><h2>👥 Personnages</h2>
    <label>Personnalités<select data-var="PERSONNALITES" data-def="fixes">
      <option value="fixes">Fixes : chacun garde son caractère d'une vidéo à l'autre (recommandé)</option>
      <option value="libres">Libres : caractère adapté à chaque histoire</option></select></label>
    <label>Jojo (bonnet orange)<div class="jeton"><textarea data-var="PERSO_JOJO" data-def="le pote radin et de mauvaise foi, qui ne lâche jamais rien et a toujours une excuse prête" data-texte="1" maxlength="300" rows="2"></textarea><button class="second" data-enr="PERSO_JOJO" style="flex:none;padding:10px 14px">OK</button></div></label>
    <label>Kévin (casquette)<div class="jeton"><textarea data-var="PERSO_KEVIN" data-def="le naïf un peu mytho, roi des plans foireux, qui croit tout ce qu'on lui dit et s'enfonce à chaque réplique" data-texte="1" maxlength="300" rows="2"></textarea><button class="second" data-enr="PERSO_KEVIN" style="flex:none;padding:10px 14px">OK</button></div></label>
    <label>Lila (nœud rose)<div class="jeton"><textarea data-var="PERSO_LILA" data-def="la lucide cash, qui s'énerve vite et balance tout haut les vérités que personne n'ose dire" data-texte="1" maxlength="300" rows="2"></textarea><button class="second" data-enr="PERSO_LILA" style="flex:none;padding:10px 14px">OK</button></div></label>
    <p class="note">Utilisé quand les personnalités sont « fixes ». Décrivez le caractère en une phrase ; chaque personnage garde aussi toujours la même voix.</p>
  </section>
  <section class="panneau"><h2>📺 Épisodes</h2>
    <label>Enchaînement des vidéos<select data-var="EPISODES" data-def="aleatoire">
      <option value="aleatoire">Aléatoires : une histoire différente à chaque vidéo</option>
      <option value="serie">En série : la suite de la même histoire d'une vidéo à l'autre (« Épisode 3 »)</option></select></label>
    <label>Épisodes par série<select data-var="EPISODES_PAR_SERIE" data-def="5"><option value="3">3</option><option value="5">5 (recommandé)</option><option value="8">8</option><option value="10">10</option></select></label>
    <p class="note">En série, le robot se souvient des épisodes précédents, fait des rappels, et démarre une nouvelle série quand la saison est finie.</p>
    <label>Format des épisodes<select id="serieFormat" class="perso"><option value="mini">⚡ Gags éclair</option><option value="libre">🎭 Sketchs longs (+1 min)</option></select></label>
    <button class="action perso" id="serieLot">🎬 Fabriquer toute la série maintenant</button>
    <div id="suiviSerie" class="note"></div>
    <p class="note">D'un seul jet : le robot écrit le plan de toute la saison, puis fabrique les épisodes à la suite (15 à 40 min chacun). Ils arrivent dans Courtes ou Longues, avec « Épisode 1, 2, 3… », et ne sont jamais publiés tout seuls : vous les publiez ou les programmez quand vous voulez.</p>
  </section>
  <section class="panneau"><h2>🧪 Contrôle qualité</h2>
    <div class="auto" style="margin-bottom:12px"><div class="txt"><b>Public test</b><small>Trois spectateurs virtuels découvrent le sketch sans contexte : ont-ils compris, ri, décroché ? Leurs critiques servent à améliorer le texte (un peu plus de crédit Claude).</small></div><button class="inter" data-var="PUBLIC_TEST" data-def="1" data-bascule="1"></button></div>
    <div class="auto" style="margin-bottom:12px"><div class="txt"><b>Contrôle de la vidéo finie</b><small>Une IA regarde des images de la vidéo (sous-titres, cadrage, décors, texte coupé) avant publication. En cas de défaut grave, pas de publication automatique.</small></div><button class="inter" data-var="CONTROLE_VIDEO" data-def="1" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Accroche choc en ouverture</b><small>La réplique la plus intrigante est rejouée dès la première seconde, avant le titre.</small></div><button class="inter" data-var="ACCROCHE" data-def="0" data-bascule="1"></button></div>
  </section>
  <section class="panneau"><h2>📤 Autres plateformes</h2>
    <p class="note">Mêmes vidéos publiées aussi ailleurs, en même temps que TikTok. À activer quand vous voulez : il suffit d'abord de connecter le compte dans Buffer (Connect channel).</p>
    <div class="auto" style="margin-bottom:12px"><div class="txt"><b>YouTube Shorts</b><small>YouTube rémunère aussi les Shorts (programme partenaire).</small></div><button class="inter" data-var="PUBLIER_YOUTUBE" data-def="0" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Instagram Reels</b><small>Compte Instagram professionnel requis par Instagram.</small></div><button class="inter" data-var="PUBLIER_INSTAGRAM" data-def="0" data-bascule="1"></button></div>
  </section>
  <section class="panneau"><h2>🔔 Notifications</h2>
    <p class="note">Une notification sur cet appareil quand une vidéo est prête, publiée, ou si quelque chose a échoué — même appli fermée. Sur iPhone : l'appli doit d'abord être installée sur l'écran d'accueil. À activer sur chaque appareil.</p>
    <button class="action" id="activerNotifs">🔔 Activer les notifications sur cet appareil</button>
    <button class="action" id="testNotif">Envoyer une notification de test</button>
    <div id="suiviNotif" class="note"></div>
  </section>
  <section class="panneau"><h2>📊 Statistiques TikTok</h2>
    <label>Compte TikTok de la chaîne<div class="jeton"><input data-var="TIKTOK_COMPTE" data-def="" data-texte="1" maxlength="40" placeholder="votre pseudo, sans @"><button class="second" data-enr="TIKTOK_COMPTE" style="flex:none;padding:10px 14px">OK</button></div></label>
    <p class="note">Chaque matin, le robot lit tout seul les vues, j'aime, commentaires et partages de vos vidéos (page publique du compte), apprend ce qui marche et s'en sert pour les sketchs, les hashtags et l'heure de publication.</p>
    <p class="note" id="statsEtat"></p>
    <button class="action" id="lancerStats">📊 Lire les statistiques maintenant</button>
    <div id="suiviStats" class="note"></div>
  </section>
  <section class="panneau"><h2>🎬 Mode réaliste (option)</h2>
    <p class="note">Au lieu du dessin animé, la vidéo est filmée par une IA vidéo (Veo 3.1 via ElevenLabs) : de vrais acteurs générés, avec leurs voix, découpés en plans de 4 à 8 s. Chaque seconde consomme des crédits ElevenLabs : regardez le coût dans votre application ElevenLabs après un premier essai.</p>
    <div class="auto" style="margin-bottom:12px"><div class="txt"><b>Vidéos automatiques en réaliste</b><small>Coupé : seules les vidéos lancées ci-dessous (ou depuis l'onglet Manuel) sont réalistes.</small></div><button class="inter" data-var="REALISTE_AUTO" data-def="0" data-bascule="1"></button></div>
    <label>Qualité<select data-var="REALISTE_MODELE" data-def="veo-3.1-fast-generate-001"><option value="veo-3.1-fast-generate-001">Rapide (Veo 3.1 Fast, moins cher)</option><option value="veo-3.1-generate-001">Maximale (Veo 3.1, plus cher)</option></select></label>
    <label>Définition<select data-var="REALISTE_RESOLUTION" data-def="720p"><option value="720p">720p (recommandé pour TikTok, moins cher)</option><option value="1080p">1080p</option></select></label>
    <button class="action perso" id="realMini">🎬 Fabriquer un gag éclair réaliste maintenant</button>
    <button class="action perso" id="realLibre">🎬 Fabriquer un sketch long réaliste maintenant</button>
    <div id="suiviReal" class="note"></div>
  </section>
  <section class="panneau"><h2>🎥 Vidéo animée</h2>
    <div class="auto" style="margin-bottom:12px"><div class="txt"><b>Voix ElevenLabs</b><small>Voix réalistes avec rires et coups de colère (abonnement ElevenLabs). Coupé : voix gratuites.</small></div><button class="inter" data-var="ELEVENLABS" data-def="1" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Décors générés par IA</b><small>Un décor du quotidien par scène, adapté à l'histoire (Stable Diffusion XL, crédits Modal). Coupé : fonds unis pastel.</small></div><button class="inter" data-var="DECORS" data-def="1" data-bascule="1"></button></div>
      <label>Voix des personnages<select data-var="VOIX_PERSOS" data-def="bibliotheque"><option value="bibliotheque">Voix de la bibliothèque ElevenLabs (actuelles)</option><option value="sur_mesure">🎙️ Voix sur mesure, créées pour Petits.Dramas</option></select></label>
    <p class="note">Les voix sur mesure sont uniques à la chaîne (Jojo, Kévin et Lila ne ressemblent à aucune autre vidéo TikTok). Elles s'appliquent dès la prochaine vidéo.</p>
    <label>Prononciation (mots mal lus par les voix)<div class="jeton"><textarea data-var="PRONONCIATION" data-def="" data-texte="1" maxlength="1500" rows="2" placeholder="Ex. : Kévin=Kévinne ; Lidl=Lidle ; OK=okay"></textarea><button class="second" data-enr="PRONONCIATION" style="flex:none;padding:10px 14px">OK</button></div></label>
    <p class="note">Une règle par « mot=comment il se dit », séparées par « ; ». Les sous-titres gardent l'orthographe normale. Déjà corrigés : POV, PDG, SMS, RER, SNCF, TikTok, wifi, €, %…</p>
  </section>
  <section class="panneau"><h2>📰 Mode JT (ancien format)</h2>
    <label>Durée du JT<select data-var="LONGUEUR" data-def="pro"><option value="pro">60-90 s (rémunérable)</option><option value="courte">Courte (30 s max)</option><option value="monetisable">Long +1 min</option></select></label>
    <label>Ton de l'humour<select data-var="TON" data-def="clash"><option value="clash">Clash, foutage de gueule direct (recommandé)</option><option value="farfelu">Farfelu et ironique</option><option value="piquant">Satire piquante</option><option value="absurde">Absurde total</option></select></label>
    <label>Nom de l'émission<div class="jeton"><input data-var="NOM_EMISSION" data-def="L'info en caoutchouc" data-texte="1" maxlength="30"><button class="second" data-enr="NOM_EMISSION" style="flex:none;padding:10px 14px">OK</button></div></label>
    <div class="auto" style="margin-bottom:12px"><div class="txt"><b>« Les infos de demain » le dimanche</b><small>Épisode spécial du JT : fausses brèves du futur.</small></div><button class="inter" data-var="INFOS_DEMAIN" data-def="1" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Plan gag généré par IA (JT)</b><small>Un plan « reconstitution » Wan 2.2 par JT.</small></div><button class="inter" data-var="PLAN_GAG" data-def="1" data-bascule="1"></button></div>
  </section>
  <section class="panneau"><h2>🚀 Actions</h2>
    <button class="action" id="lancerMini">⚡ Fabriquer un gag éclair maintenant</button>
    <button class="action" id="lancerLibre">🎭 Fabriquer un sketch long maintenant</button>
    <button class="action" id="lancer">📰 Fabriquer un JT d'actualité maintenant</button>
    <button class="action" id="majsite">🔄 Mettre à jour l'application</button>
    <div id="suiviCfg" class="note"></div>
  </section>
  <section class="panneau" id="appairage" style="display:none"><h2>📱 Connecter un autre appareil</h2>
    <p class="note">Scannez ce code avec l'appareil photo de l'autre appareil (téléphone ↔ PC) : la régie s'y connecte toute seule, sans rien recopier.
    La clé ne passe par aucun serveur. <b>Ne montrez ce code à personne d'autre.</b></p>
    <button class="action" id="montrerQR">Afficher le code de connexion</button>
    <div id="qr" style="display:none;text-align:center"><div id="qrImg" style="background:#fff;display:inline-block;padding:12px;border-radius:12px;margin:8px 0"></div>
      <button class="action" id="copierLien">Copier le lien de connexion</button><button class="action" id="cacherQR">Masquer</button></div>
  </section>
  <section class="panneau"><h2>🔗 Raccourcis</h2>
    <a class="lien" id="lienActions" target="_blank" rel="noopener">Activité du robot (GitHub)</a>
    <a class="lien" href="https://modal.com/settings/usage" target="_blank" rel="noopener">Crédits Modal (décors, contrôle des voix)</a>
    <a class="lien" href="https://elevenlabs.io/app/subscription" target="_blank" rel="noopener">Crédit ElevenLabs (voix)</a>
    <a class="lien" href="https://console.anthropic.com/settings/billing" target="_blank" rel="noopener">Crédit Claude (écriture)</a>
    <a class="lien" href="https://publish.buffer.com" target="_blank" rel="noopener">Buffer (file de publication)</a>
    <a class="lien" href="https://www.tiktok.com/tiktokstudio" target="_blank" rel="noopener">TikTok Studio (statistiques)</a>
  </section>
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
    <label>Légende<textarea id="legEdit" rows="4" maxlength="2200"></textarea></label>
    <button class="second" id="legOk" disabled style="width:100%;margin-top:6px">✏️ Enregistrer la légende</button>
    <label>Programmer la publication (heure de Paris)<input type="datetime-local" id="quand"></label>
    <button class="second" id="programmer" disabled style="width:100%;margin-top:6px">🗓️ Programmer sur TikTok</button>
    <label>Refaire cette vidéo<select id="refaireQuoi"><option value="texte">Nouvelle version du sketch (même sujet)</option><option value="voix">Mêmes répliques, nouvelles voix</option><option value="decors">Mêmes répliques, nouveaux décors</option></select></label>
    <button class="second" id="refaire" disabled style="width:100%;margin-top:6px">🔁 Refaire (15 à 40 min)</button>
  </details>
  <div id="suivi"></div>
</div></div>
<div id="toast"></div>
<script>
var VARS={};
const DATA = __DATA__, CONF = __CONF__;
const API = "https://api.github.com/repos/" + CONF.depot;
const $ = s => document.querySelector(s);
let choisie = null, fichier = null, charge = null, armer = null;
function toast(t){const e=$("#toast");e.textContent=t;e.style.display="block";clearTimeout(e._t);e._t=setTimeout(()=>e.style.display="none",3200)}
function dateFr(d){try{return new Date(d+"T12:00:00").toLocaleDateString("fr-FR",{weekday:"long",day:"numeric",month:"long"})}catch(e){return d}}
function heureDe(v){const m=/_(\d{2})h(\d{2})_/.exec(v.fichier||"");return m?` à ${+m[1]} h ${m[2]}`:""}   // heure de fabrication (heure de Paris), lue dans le nom du fichier
function lireJeton(){try{return localStorage.getItem("jt_jeton")||""}catch(e){return window._jeton||""}}
function ecrireJeton(v){try{v?localStorage.setItem("jt_jeton",v):localStorage.removeItem("jt_jeton")}catch(e){window._jeton=v}}
async function gh(chemin, opts={}){
  const j=lireJeton(); if(!j) throw new Error("régie non connectée");
  const r=await fetch(API+chemin,{...opts,headers:{"Authorization":"Bearer "+j,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",...(opts.body?{"Content-Type":"application/json"}:{}),...(opts.headers||{})}});
  if(r.status===401) throw new Error("jeton refusé (expiré ou incorrect)");
  if(r.status===403) throw new Error("droits du jeton insuffisants");
  return r;
}
// ------------------------------------------------ interrupteur publication automatique
let auto = null;
function afficherAuto(){
  const b=$("#inter"); b.classList.toggle("on",auto===true); b.disabled=(auto===null);
  $("#autoTitre").textContent = auto===null ? "Publication automatique" : (auto ? "Publication automatique : ACTIVÉE" : "Publication automatique : COUPÉE");
  $("#autoAide").textContent = auto===null ? (lireJeton()?"Lecture du réglage…":"Connectez la régie (ci-dessous) pour utiliser les boutons.")
    : (auto ? "Chaque vidéo part toute seule sur TikTok dès qu'elle est prête." : "Les nouvelles vidéos attendent ici : vérifiez-les, puis touchez « Publier sur TikTok ».");
}
async function lireAuto(){
  if(!lireJeton()||!CONF.depot){auto=null;afficherAuto();return}
  try{const r=await gh("/actions/variables/PUBLICATION_AUTO");
    if(r.status===404){auto=false}else{const v=await r.json();auto=(String(v.value).trim()==="1")}
    $("#resume").textContent="Régie connectée ✓";
  }catch(e){auto=null;$("#autoAide").textContent="Erreur : "+e.message}
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
$("#garder").onclick=()=>{const v=$("#jeton").value.trim(); if(!v)return; ecrireJeton(v); $("#jeton").value=""; $("#reglages").open=false; lireAuto(); majBoutons()};
$("#oublier").onclick=()=>{ecrireJeton(""); auto=null; $("#resume").textContent="Connecter la régie (une seule fois)"; afficherAuto(); majBoutons(); toast("Régie déconnectée")};
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
// actualisation automatique des statistiques : au lancement, puis toutes les heures (et au retour sur l'appli après plus d'une heure)
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
    const [h,st]=await Promise.all([lireEpisode("historique.json").catch(()=>null),lireEpisode("stats.json").catch(()=>null)]);
    if(Array.isArray(h)){const par={}; h.forEach(e=>{if(e.fichier)par[e.fichier]=e});
      DATA.forEach(v=>{const e=par[v.fichier]; if(!e)return; ["vues","likes","commentaires","partages","publie","couts"].forEach(k=>{if(e[k]!==undefined)v[k]=e[k]})})}
    if(st&&st.compte){const vids=st.videos||[]; STATS_LIVE={compte:st.compte,maj:st.maj||"",videos:vids.length,
      vues:vids.reduce((a,x)=>a+(x.vues||0),0),liees:vids.filter(x=>x.fichier).length,abonnes:st.abonnes,abonnes_hist:st.abonnes_hist||[]}}
    DERNIERE_MAJ=Date.now();
    if(document.body.dataset.onglet==="stats") rendreStats();
    else if(document.body.dataset.onglet==="videos"){rendre(); if(choisie!==null) document.querySelectorAll(".carte").forEach(c=>c.classList.toggle("choisie",+c.dataset.i===choisie))}
  }catch(e){}
}
setTimeout(actualiserStats,1500); setInterval(actualiserStats,3600*1000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&Date.now()-DERNIERE_MAJ>3600*1000) actualiserStats()});
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
    <p class="note">${S.compte?"Compte @"+S.compte+(S.maj?", lu le "+new Date(S.maj).toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"}):""):"Compte TikTok pas encore réglé (⚙️ → Statistiques TikTok)."}</p></section>
    <section class="panneau"><h2>🏆 Vidéos les plus vues</h2><div class="barres">${top.length?top.map(v=>`<div><span style="flex:0 0 42%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${v.titre.replace(/</g,"&lt;")}</span><span class="b" style="width:${Math.round(50*v.vues/max)}%"></span>${fr(v.vues)}</div>`).join(""):'<p class="note">Les vues arrivent dans l’heure qui suit les premières publications.</p>'}</div></section>
    <section class="panneau"><h2>💶 Dépenses du mois</h2><div class="chiffres">
    <div><b>${usd.toFixed(2)} $</b>Claude (écriture)</div><div><b>${fr(car)}</b>crédits ElevenLabs (voix)</div>
    <div><b>${Math.round(gpu/60)} min</b>GPU Modal (décors)</div><div><b>${duMois.length?(usd/duMois.length).toFixed(2):"0.00"} $</b>Claude par vidéo</div></div>
    <p class="note">Compté par le robot vidéo par vidéo (les vidéos fabriquées avant cette version n'ont pas de compte). Comparez avec vos tableaux de bord Anthropic, ElevenLabs et Modal.</p></section>
    <section class="panneau"><h2>🔔 Dernières alertes</h2>${ALERTES.length?[...ALERTES].reverse().slice(0,8).map(a=>`<div class="alerte ${/✅|🎬/.test(a.titre)?"ok":""}"><b>${a.titre.replace(/</g,"&lt;")}</b><br>${(a.texte||"").replace(/</g,"&lt;")}<br><small>${new Date(a.quand).toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"})}</small></div>`).join(""):'<p class="note">Aucune alerte.</p>'}</section>`;
  $("#majStats").onclick=()=>{
    if(!lireJeton()){$("#majStats").disabled=true; $("#suiviMajStats").textContent="Relecture des données publiées…"; actualiserStats().then(()=>toast("Données rechargées ✓ (connectez la régie pour relire TikTok tout de suite)")); return}
    lancerFlux("stats.yml",$("#majStats"),"📊 Lecture des vues et abonnés sur TikTok (1 à 3 min)…",null,$("#suiviMajStats"),
      async ok=>{ if(ok){await actualiserStats(); toast("Statistiques à jour ✓")} });
  };
}
let FILTRE="court";
const categorie=v=>v.manuel?"manuel":(v.format==="mini"?"court":"long");
function rendre(){
  const L=$("#liste"); L.innerHTML="";
  const vis=DATA.map((v,i)=>[v,i]).filter(([v])=>categorie(v)===FILTRE);
  if(!vis.length){L.innerHTML='<p class="vide">'+({court:"Aucune vidéo courte pour l'instant.",long:"Aucune vidéo longue pour l'instant.",manuel:"Aucune vidéo manuelle pour l'instant : tapez votre texte ci-dessus."})[FILTRE]+'</p>';return}
  vis.forEach(([v,i])=>{
    const c=document.createElement("div");c.className="carte";c.dataset.i=i;
    c.innerHTML=`<img loading="lazy" src="videos/${v.poster}" alt=""><div class="infos"><div class="titre"></div><div class="date">${dateFr(v.date)}${heureDe(v)}${v.vues!=null?` · 👁 ${Number(v.vues).toLocaleString("fr-FR")} vues`:""}</div>${badge(v)}<div class="etat"></div></div><button class="croix" title="Supprimer cette vidéo" aria-label="Supprimer">✕</button>`;
    c.querySelector(".titre").textContent=v.titre; c.onclick=()=>choisir(i);
    c.querySelector(".croix").onclick=(ev)=>{ev.stopPropagation(); supprimer(i,c)}; L.appendChild(c);
  });
}
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
    if(choisie===i){choisie=null; $("#apercu").style.display="none"; $("#choix").textContent=""; majBoutons()}
  }catch(e){c.classList.remove("supprimee"); c.querySelector(".etat").textContent=""; toast("Impossible : "+e.message)}
}
function majBoutons(){
  const p=$("#publier"); armer=null; p.classList.remove("confirmer");
  if(choisie===null){p.disabled=true;p.textContent="Publier sur TikTok";return}
  if(!lireJeton()){p.disabled=true;p.textContent="Connectez la régie pour publier";return}
  p.disabled=false; p.textContent = DATA[choisie].publie===true ? "Republier sur TikTok" : "Publier sur TikTok";
}
function choisir(i){
  choisie=i; fichier=null; const v=DATA[i];
  ["#pouce","#bof","#legOk","#programmer","#refaire"].forEach(s=>$(s).disabled=!lireJeton()); $("#legEdit").value=v.legende||"";
  $("#pouce").classList.toggle("actif",v.avis===1); $("#bof").classList.toggle("actif",v.avis===-1);
  document.querySelectorAll(".carte").forEach(c=>c.classList.toggle("choisie",+c.dataset.i===i));
  $("#choix").textContent="Sélection : "+v.titre; ["#copier","#voir","#manuel"].forEach(s=>$(s).disabled=false);
  const a=$("#apercu"); a.src="videos/"+v.fichier; a.style.display="block"; $("#suivi").textContent=""; majBoutons();
  setTimeout(()=>{document.querySelector("main").style.paddingBottom=($("#barre").offsetHeight+24)+"px"},50);
}
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
      document.querySelector(`.carte[data-i="${choisie}"] .badge`).outerHTML=badge(v); majBoutons(); return;
    }catch(e){ if(k>50){s.textContent="Suivi interrompu (connexion) : l'état apparaîtra dans l'appli."; majBoutons(); return} }
  }
  s.textContent="Toujours en cours : regardez l'onglet Actions du dépôt."; majBoutons();
}
// ------------------------------------------------ secours : partage manuel
const peutPartager = !!(navigator.canShare && navigator.canShare({files:[new File([""],"t.mp4",{type:"video/mp4"})]}));
function fermerVideo(){
  const a=$("#apercu"); a.pause(); a.removeAttribute("src"); a.load(); a.style.display="none";
  choisie=null; fichier=null; document.querySelectorAll(".carte").forEach(c=>c.classList.remove("choisie"));
  $("#choix").textContent="Sélectionnez une vidéo pour la vérifier"; ["#copier","#voir","#manuel"].forEach(s=>$(s).disabled=true);
  $("#suivi").textContent=""; majBoutons();
  setTimeout(()=>{document.querySelector("main").style.paddingBottom=($("#barre").offsetHeight+24)+"px"},50);
}
$("#fermer").onclick=fermerVideo;
// ------------------------------------------------ actions sur la vidéo choisie
function action(a,valeur,msg){
  if(choisie===null)return; const v=DATA[choisie];
  lancerFlux("regie.yml",$("#legOk"),msg,{action:a,fichier:v.fichier,valeur:String(valeur)},$("#suivi"));
}
$("#pouce").onclick=()=>{const v=DATA[choisie];v.avis=v.avis===1?0:1;$("#pouce").classList.toggle("actif",v.avis===1);$("#bof").classList.remove("actif");action("avis",v.avis,"👍 Noté : le robot s'en servira comme exemple.")};
$("#bof").onclick=()=>{const v=DATA[choisie];v.avis=v.avis===-1?0:-1;$("#bof").classList.toggle("actif",v.avis===-1);$("#pouce").classList.remove("actif");action("avis",v.avis,"👎 Noté : le robot évitera ce genre de sketch.")};
$("#legOk").onclick=()=>{const t=$("#legEdit").value.trim(); if(!t){toast("Légende vide");return} DATA[choisie].legende=t; action("legende",t,"✏️ Légende enregistrée (le site se met à jour dans 2 à 3 min).")};
$("#programmer").onclick=()=>{
  const q=$("#quand").value; if(!q){toast("Choisissez la date et l'heure");return}
  if(new Date(q)<new Date(Date.now()+10*60000)){toast("Choisissez une heure dans au moins 10 minutes");return}
  const v=DATA[choisie];
  lancerFlux("publier.yml",$("#programmer"),"🗓️ Publication programmée le "+new Date(q).toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"})+" : Buffer s'en charge, même appli fermée.",{fichier:v.fichier,forcer:v.publie===true?"oui":"non",quand:q},$("#suivi"));
};
$("#refaire").onclick=()=>{const v=DATA[choisie], q=$("#refaireQuoi").value;
  lancerFlux("emission.yml",$("#refaire"),"🔁 Nouvelle version en fabrication. Elle apparaîtra à côté de l'ancienne (supprimez celle que vous ne gardez pas).",{refaire:v.fichier+"|"+q},$("#suivi"))};
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&choisie!==null)fermerVideo()});
$("#voir").onclick=()=>{const a=$("#apercu");a.style.display="block";a.play()};
$("#copier").onclick=async()=>{const t=DATA[choisie].legende||"";try{await navigator.clipboard.writeText(t);toast("Légende copiée")}catch(e){prompt("Copiez la légende :",t)}};
$("#manuel").onclick=async()=>{
  const v=DATA[choisie]; navigator.clipboard && navigator.clipboard.writeText(v.legende||"").catch(()=>{});
  if(!peutPartager){
    const a=document.createElement("a");a.href="videos/"+v.fichier;a.download=v.fichier;document.body.appendChild(a);a.click();a.remove();
    window.open("https://www.tiktok.com/tiktokstudio/upload","_blank");toast("Légende copiée · vidéo téléchargée");return;
  }
  const b=$("#manuel");
  if(!fichier){b.textContent="Préparation…";const jeton=charge={};
    try{const r=await fetch("videos/"+v.fichier);const blob=await r.blob();if(charge!==jeton)return;fichier=new File([blob],v.fichier,{type:"video/mp4"});
      b.textContent="Touchez pour partager";}catch(e){b.textContent="Partage manuel";toast("Chargement impossible")}
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
// ------------------------------------------------ onglets
document.querySelectorAll(".onglet").forEach(b=>b.onclick=()=>{
  document.querySelectorAll(".onglet").forEach(x=>x.classList.toggle("actif",x===b));
  if(b.dataset.f){FILTRE=b.dataset.f; if(choisie!==null&&categorie(DATA[choisie])!==FILTRE) fermerVideo(); rendre();
    $("#manuel").style.display=FILTRE==="manuel"?"":"none"; document.querySelector("#o-videos .panneau:not(#manuel)").style.display=FILTRE==="manuel"?"none":""}
  $("#o-videos").style.display=b.dataset.o==="videos"?"":"none"; $("#o-config").style.display=b.dataset.o==="config"?"":"none";
  $("#o-stats").style.display=b.dataset.o==="stats"?"":"none"; if(b.dataset.o==="stats") rendreStats();
  $("#barre").style.display=b.dataset.o==="videos"?"":"none"; document.body.dataset.onglet=b.dataset.o; if(b.dataset.o==="config") chargerReglages();
});
// ------------------------------------------------ réglages (variables du dépôt GitHub)
// ------------------------------------------------ série d'un seul jet
function lancerSerie(){
  const n=document.querySelector('[data-var="EPISODES_PAR_SERIE"]').value||"5", f=$("#serieFormat").value;
  lancerFlux("emission.yml",$("#serieLot"),`🎬 Série de ${n} ${f==="mini"?"gags éclair":"sketchs longs"} en fabrication : plan de la saison, puis les épisodes à la suite (environ ${f==="mini"?20*n:35*n} min au total).`,{format:f,serie:"1"},$("#suiviSerie"))}
$("#serieLot").onclick=()=>{if(!lireJeton()){toast("Connectez la régie pour lancer la série");return} lancerSerie()};
document.querySelector('[data-var="EPISODES"]').addEventListener("change",e=>{
  if(e.target.value==="serie"&&lireJeton()&&confirm("Fabriquer maintenant tous les épisodes de la série, d'un seul jet ?")) setTimeout(lancerSerie,600)});
// ------------------------------------------------ programme et planning personnalisés
const NOMS_F={mini:"⚡ Gag",libre:"🎭 Long",actu:"📰 JT"}; let SEQ=["mini","mini","mini","libre"], CREN=[], JOURS=new Set([1,2,3,4,5,6,7]);
function dessinerSeq(){const z=$("#seqChips"); z.innerHTML="";
  SEQ.forEach((f,i)=>{const b=document.createElement("button");b.className="chip perso";b.textContent=(i+1)+". "+NOMS_F[f]+" ✕";b.onclick=()=>{SEQ.splice(i,1);dessinerSeq()};z.appendChild(b)});
  if(!SEQ.length) z.innerHTML='<span class="note">Séquence vide : ajoutez au moins une vidéo.</span>'}
document.querySelectorAll("[data-ajout]").forEach(b=>b.onclick=()=>{if(SEQ.length<30){SEQ.push(b.dataset.ajout);dessinerSeq()}});
$("#selFormat").onchange=async()=>{const v=$("#selFormat").value; $("#seqBloc").style.display=v==="seq"?"":"none"; if(v==="seq"){dessinerSeq();return}
  try{await ecrireVar("FORMAT",v);toast("Réglage enregistré ✓")}catch(e){toast("Impossible : "+e.message)}};
$("#seqEnr").onclick=async()=>{if(!SEQ.length){toast("Ajoutez au moins une vidéo");return}
  try{await ecrireVar("FORMAT","seq:"+SEQ.join(","));toast("Séquence enregistrée ✓")}catch(e){toast("Impossible : "+e.message)}};
function lireHoraires(brut){CREN=[];JOURS=new Set([1,2,3,4,5,6,7]); brut=String(brut||"17").toLowerCase();
  if(brut.includes("|jours=")){const [a,j]=brut.split("|jours=");brut=a;const s=new Set([...j].filter(c=>"1234567".includes(c)).map(Number));if(s.size)JOURS=s}
  brut.split(";").map(x=>x.trim()).filter(Boolean).forEach(m=>{let [h,f]=m.split("=");h=h.trim();f=(f||"programme").trim();
    if(h==="auto"){CREN.push({h:"auto",f});return} let [hh,mm]=h.replace("h",":").split(":");hh=+hh;mm=+(mm||0);
    if(!isNaN(hh)&&hh>=0&&hh<24) CREN.push({h:String(hh).padStart(2,"0")+":"+String(mm).padStart(2,"0"),f})});
  if(!CREN.length) CREN=[{h:"17:00",f:"programme"}]}
function dessinerPlanning(){const z=$("#creneaux"); z.innerHTML="";
  CREN.forEach((c,i)=>{const l=document.createElement("div");l.className="creneau";
    const [hh,mm]=(c.h==="auto"?"17:00":c.h).split(":");
    const optH=[...Array(24).keys()].map(x=>`<option value="${String(x).padStart(2,"0")}">${x} h</option>`).join("");
    const optM=[...Array(12).keys()].map(x=>`<option value="${String(x*5).padStart(2,"0")}">${String(x*5).padStart(2,"0")}</option>`).join("");
    l.innerHTML=(c.h==="auto"?'<span class="auto-h">📊 Auto</span>':`<span class="heure"><select class="perso hh">${optH}</select><select class="perso mm">${optM}</select></span>`)+
      `<select class="perso"><option value="programme">Selon le programme</option><option value="mini">⚡ Gag éclair</option><option value="libre">🎭 Sketch long</option><option value="actu">📰 JT</option></select><button class="second perso" title="Retirer">✕</button>`;
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
  else{$("#selFormat").value=["cycle","mini","libre","actu"].includes(f)?f:"cycle";$("#seqBloc").style.display="none"}
  dessinerSeq(); lireHoraires(v.HEURE); dessinerPlanning()}
lireHoraires("17"); dessinerPlanning(); dessinerSeq();
$("#lienActions").href="https://github.com/"+CONF.depot+"/actions";
async function ecrireVar(nom,valeur){
  const corps=JSON.stringify({name:nom,value:String(valeur)});
  let r=await gh("/actions/variables/"+nom,{method:"PATCH",body:corps});
  if(r.status===404) r=await gh("/actions/variables",{method:"POST",body:corps});
  if(!r.ok) throw new Error("GitHub a répondu "+r.status);
}
const champs=()=>document.querySelectorAll("#o-config [data-var]");
function activer(on){champs().forEach(c=>c.disabled=!on);document.querySelectorAll("#o-config .action,[data-enr],#o-config .perso").forEach(b=>b.disabled=!on)}
$("#garder2").onclick=()=>{const v=$("#jeton2").value.trim(); if(!v)return; ecrireJeton(v); $("#jeton2").value=""; lireAuto(); majBoutons(); chargerReglages()};
async function chargerReglages(){
  $("#cfgConnexion").style.display=lireJeton()?"none":""; $("#appairage").style.display=lireJeton()?"":"none";
  if(!lireJeton()){activer(false);$("#cfgEtat").textContent="";return}
  $("#cfgEtat").textContent="Lecture des réglages…";
  try{
    const r=await gh("/actions/variables?per_page=100"); const d=await r.json(); const v={}; VARS=v;
    (d.variables||[]).forEach(x=>v[x.name]=x.value);
    champs().forEach(c=>{const val=(c.dataset.var in v)?v[c.dataset.var]:c.dataset.def;
      if(c.dataset.bascule) c.classList.toggle("on",String(val)!=="0"); else c.value=val;});
    chargerPerso(v); activer(true); $("#cfgEtat").textContent="Régie connectée ✓ — chaque changement est enregistré immédiatement.";
  }catch(e){$("#cfgEtat").textContent="Erreur : "+e.message+" — vérifiez la clé (droits Actions et Variables).";activer(false);
    if(/jeton refusé/.test(e.message)) $("#cfgConnexion").style.display=""}
}
champs().forEach(c=>{
  if(c.dataset.texte) return;
  const ev=c.dataset.bascule?"click":"change";
  c.addEventListener(ev,async()=>{
    const val=c.dataset.bascule?(c.classList.contains("on")?"0":"1"):c.value; c.disabled=true;
    try{await ecrireVar(c.dataset.var,val); if(c.dataset.bascule) c.classList.toggle("on",val==="1"); toast("Réglage enregistré ✓")}
    catch(e){toast("Impossible : "+e.message); chargerReglages()}
    c.disabled=false;
  });
});
document.querySelectorAll("[data-enr]").forEach(b=>b.onclick=async()=>{
  const c=document.querySelector(`[data-var="${b.dataset.enr}"]`); const val=c.value.trim(); if(!val)return;
  try{await ecrireVar(b.dataset.enr,val);toast("Enregistré ✓ (visible dès la prochaine émission)")}catch(e){toast("Impossible : "+e.message)}
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
$("#lancer").onclick=()=>lancerFlux("emission.yml",$("#lancer"),"📰 Le robot fabrique un JT d'actualité (20 à 40 min)…",{format:"actu"});
$("#lancerMini").onclick=()=>lancerFlux("emission.yml",$("#lancerMini"),"⚡ Le robot fabrique un gag éclair (15 à 30 min)…",{format:"mini"});
$("#lancerLibre").onclick=()=>lancerFlux("emission.yml",$("#lancerLibre"),"🎭 Le robot fabrique un sketch long (20 à 40 min)…",{format:"libre"});
$("#mMode").onchange=()=>{const s=$("#mMode").value==="script";
  $("#mAide").textContent=s?"Mon script (une réplique par ligne : « Jojo : … », « Kévin : … », « Lila : … »)":"Idée / thème de la vidéo";
  $("#mTexte").placeholder=s?"Jojo : Je vais résilier ma salle de sport.\nKévin : T'y es allé combien de fois ?\nJojo : Une. Pour m'inscrire.\nLila : Donc tu payes 30 € par mois pour un souvenir.":"Ex. : Jojo essaie de résilier son abonnement de salle de sport, mais le conseiller ne le laisse jamais partir.";
  $("#mStyleL").style.display=s?"none":""};
$("#mCreer").onclick=()=>{
  if(!lireJeton()){toast("Connectez la régie (onglet Réglages) pour créer une vidéo");return}
  const t=$("#mTexte").value.trim(); if(t.length<8){toast("Tapez d'abord votre idée ou votre script");return}
  const script=$("#mMode").value==="script";
  if(script&&!/^\s*[^:\n]{1,25}:/m.test(t)){toast("Format du script : une réplique par ligne, « Jojo : … »");return}
  const theme=script?"SCRIPT::"+t:(t+($("#mStyle").value?"\n"+$("#mStyle").value:""));
  const f=$("#mFormat").value;
  const rendu=$("#mRendu").value; const inp={format:f,theme}; if(rendu) inp.rendu=rendu;
  lancerFlux("emission.yml",$("#mCreer"),(f==="mini"?"⚡ Gag éclair":"🎭 Sketch long")+(rendu?" réaliste":"")+" manuel en fabrication (15 à 40 min). Il apparaîtra dans cet onglet.",inp,$("#mSuivi"));
};
const b64u=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
const deB64u=s=>Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/")+"===".slice((s.length+3)%4)),c=>c.charCodeAt(0));
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
$("#testNotif").onclick=()=>lancerFlux("notifier.yml",$("#testNotif"),"🔔 Envoi d'une notification de test (environ 30 s)…",{titre:"Petits.Dramas",texte:"Les notifications marchent 🎉"},$("#suiviNotif"));
$("#realMini").onclick=()=>{if(!lireJeton()){toast("Connectez la régie");return} if(confirm("Fabriquer un gag éclair réaliste ? Il consomme des crédits ElevenLabs (vidéo IA)."))
  lancerFlux("emission.yml",$("#realMini"),"🎬 Gag réaliste en fabrication (20 à 40 min).",{format:"mini",rendu:"realiste"},$("#suiviReal"))};
$("#realLibre").onclick=()=>{if(!lireJeton()){toast("Connectez la régie");return} if(confirm("Fabriquer un sketch long réaliste ? Une dizaine de plans de vidéo IA : c'est nettement plus de crédits ElevenLabs."))
  lancerFlux("emission.yml",$("#realLibre"),"🎬 Sketch long réaliste en fabrication (30 à 60 min).",{format:"libre",rendu:"realiste"},$("#suiviReal"))};
$("#lancerStats").onclick=()=>{if(!lireJeton()){toast("Connectez la régie pour lancer la lecture");return}
  lancerFlux("stats.yml",$("#lancerStats"),"📊 Lecture des statistiques TikTok (1 à 3 min)…",null,$("#suiviStats"))};
{const S=__STATS__, e=$("#statsEtat");
 e.textContent=!S.compte?"Aucune lecture pour l'instant : enregistrez le compte (bouton OK) puis lancez la lecture."
  :"Dernière lecture de @"+S.compte+(S.maj?" le "+new Date(S.maj).toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"}):"")+" : "
   +(S.videos?S.videos+" vidéo(s), "+S.vues.toLocaleString("fr-FR")+" vues au total, "+S.liees+" reliée(s) aux vidéos du robot."
   :"aucune vidéo publiée pour l'instant (normal pour un compte neuf).")}
$("#majsite").onclick=()=>lancerFlux("site.yml",$("#majsite"),"🔄 Mise à jour de l'application (2 à 3 min)…");
activer(false);
// ------------------------------------------------ application installable
if("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(()=>{});
let invite=null;
window.addEventListener("beforeinstallprompt",e=>{e.preventDefault();invite=e;$("#installer").style.display="inline-block"});
$("#installer").onclick=async()=>{if(!invite)return;invite.prompt();await invite.userChoice.catch(()=>{});invite=null;$("#installer").style.display="none"};
window.addEventListener("appinstalled",()=>{$("#installer").style.display="none";toast("Application installée ✓")});
rendre(); afficherAuto(); lireAuto(); majBoutons();
if(!CONF.depot) $("#autoAide").textContent="Site de test : boutons du robot inactifs.";
</script></body></html>
"""

if __name__ == "__main__":
    construire()
