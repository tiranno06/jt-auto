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
    for e in reversed([h for h in hist if h.get("fichier")]):
        if len(liste) >= NB: break
        dest = os.path.join(SITE, "videos", e["fichier"])
        if not recuperer(e, dest): continue
        poster = e["fichier"].replace(".mp4", ".jpg"); affiche(dest, os.path.join(SITE, "videos", poster))
        liste.append(dict(titre=e.get("titre", ""), date=e.get("date", ""), fichier=e["fichier"], poster=poster,
                          legende=e.get("legende", ""), publie=e.get("publie")))
    nom = os.environ.get("NOM_EMISSION") or "L'info en caoutchouc"
    conf = {"depot": os.environ.get("GITHUB_REPOSITORY", ""), "branche": os.environ.get("GITHUB_REF_NAME") or "main"}
    page = (PAGE.replace("__NOM__", html.escape(nom)).replace("__CONF__", json.dumps(conf))
            .replace("__DATA__", json.dumps(liste, ensure_ascii=False).replace("</", "<\\/")))
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(page)
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    application(nom)
    print(f"Site : {len(liste)} vidéos")

# ------------------------------------------------------------------ application installable (PWA)
def icone(taille, marge=0.0):
    """Icône de l'appli : fond rouge JT, « JT » blanc et petit point « direct » jaune."""
    from PIL import Image, ImageDraw, ImageFont
    S = 4; T = taille * S; img = Image.new("RGB", (T, T), (227, 32, 58) if marge else (14, 15, 23)); d = ImageDraw.Draw(img)
    m = int(T * marge); r = int((T - 2 * m) * 0.22)
    d.rounded_rectangle((m, m, T - m, T - m), r, fill=(227, 32, 58))
    f = ImageFont.truetype(os.path.join(RACINE, "polices", "Poppins-Bold.ttf"), int((T - 2 * m) * 0.46))
    w = d.textlength("JT", font=f); d.text(((T - w) / 2, T * 0.5 - (T - 2 * m) * 0.36), "JT", font=f, fill=(255, 255, 255))
    c = int((T - 2 * m) * 0.075); cx, cy = T - m - int((T - 2 * m) * 0.2), m + int((T - 2 * m) * 0.2)
    d.ellipse((cx - c, cy - c, cx + c, cy + c), fill=(255, 214, 40))
    return img.resize((taille, taille), Image.LANCZOS)

def application(nom):
    for t in (192, 512):
        icone(t).save(os.path.join(SITE, f"icone-{t}.png"))
        icone(t, marge=0.1).save(os.path.join(SITE, f"icone-{t}-maskable.png"))
    icone(180).save(os.path.join(SITE, "apple-touch-icon.png"))
    manifeste = {"name": f"{nom} — régie", "short_name": "Régie JT", "lang": "fr", "start_url": "./", "scope": "./", "id": "./",
                 "display": "standalone", "orientation": "portrait", "background_color": "#0e0f17", "theme_color": "#0e0f17",
                 "description": "Vérifier et publier les émissions du robot sur TikTok.",
                 "icons": [{"src": f"icone-{t}.png", "sizes": f"{t}x{t}", "type": "image/png", "purpose": "any"} for t in (192, 512)] +
                          [{"src": f"icone-{t}-maskable.png", "sizes": f"{t}x{t}", "type": "image/png", "purpose": "maskable"} for t in (192, 512)]}
    json.dump(manifeste, open(os.path.join(SITE, "manifest.webmanifest"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(SITE, "sw.js"), "w").write(SW)

# Service worker : l'appli s'ouvre même hors connexion (dernière version de la page), sans jamais mettre en cache
# les vidéos (trop lourdes) ni les appels à GitHub.
SW = r"""const CACHE = "regie-v5";
const COQUILLE = ["./", "manifest.webmanifest", "icone-192.png", "icone-512.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(COQUILLE))); self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== CACHE).map(x => caches.delete(x))))); self.clients.claim(); });
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.endsWith(".mp4")) return;
  e.respondWith(fetch(e.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(CACHE).then(x => x.put(e.request, c)); } return r; })
    .catch(() => caches.match(e.request).then(r => r || caches.match("./"))));
});
"""

PAGE = r"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#0e0f17"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes">
<link rel="manifest" href="manifest.webmanifest"><link rel="icon" href="icone-192.png"><link rel="apple-touch-icon" href="apple-touch-icon.png">
<title>__NOM__ — régie</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;700&display=swap" rel="stylesheet">
<style>
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
input{flex:1;min-width:0;font:inherit;font-size:14px;padding:10px;border-radius:10px;border:1px solid var(--ligne);background:#0e0f17;color:var(--texte)}
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
.second{flex:1;padding:11px 6px;font-size:13px;background:var(--carte);color:var(--texte);border:1px solid var(--ligne)}
.second:disabled{opacity:.4}
#suivi{font-size:13px;margin-top:8px;min-height:18px;color:var(--doux)}
#toast{position:fixed;top:16px;left:50%;transform:translateX(-50%);background:var(--jaune);color:#111;font-weight:700;padding:10px 16px;border-radius:12px;display:none;z-index:9;max-width:90vw;text-align:center}
.onglets{position:sticky;top:0;z-index:5;display:flex;gap:8px;max-width:560px;margin:0 auto;padding:8px 16px;background:var(--bg)}
.onglet{flex:1;padding:10px;font-size:15px;font-weight:700;background:var(--carte);color:var(--doux);border:1px solid var(--ligne)}
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
video{width:100%;border-radius:12px;margin:0 0 8px;max-height:34vh;background:#000;display:none}
#cadreVideo{position:relative}
#fermer{display:none;position:absolute;top:8px;right:8px;width:40px;height:40px;padding:0;border-radius:50%;font-size:20px;font-weight:700;line-height:40px;background:rgba(0,0,0,.65);color:#fff;border:1px solid rgba(255,255,255,.35);z-index:2}
#apercu[style*="block"]+#fermer{display:block}
</style></head><body data-onglet="videos">
<header><h1>__NOM__</h1><div class="sous">Régie du robot · vidéos de la plus récente à la plus ancienne</div>
<button id="installer" style="display:none;margin-top:10px;padding:9px 16px;font-size:14px;font-weight:700;background:var(--jaune);color:#111">📲 Installer l'application</button></header>
<nav class="onglets"><button class="onglet actif" data-o="videos">🎬 Vidéos</button><button class="onglet" data-o="config">⚙️ Réglages</button></nav>
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
  <div id="liste"></div>
 </div>
 <div id="o-config" style="display:none">
  <section class="panneau" id="cfgConnexion"><h2>🔑 Connecter la régie</h2>
    <p class="note">Pour modifier les réglages depuis cet appareil (téléphone ou PC), collez une fois votre clé GitHub de régie. Elle reste uniquement dans ce navigateur.
    Pas encore de clé ? <a style="color:var(--bleu)" href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">Créer la clé</a> : dépôt <b>jt-auto</b> uniquement, droits <b>Actions</b> et <b>Variables</b> en « Read and write ».</p>
    <div class="jeton"><input id="jeton2" type="password" placeholder="github_pat_…" autocomplete="off"><button class="second" id="garder2" style="flex:none;padding:10px 14px">Connecter</button></div>
  </section>
  <p class="note" id="cfgEtat"></p>
  <section class="panneau"><h2>🎬 Programme</h2>
    <label>Type de vidéos (émissions automatiques)<select data-var="FORMAT" data-def="cycle">
      <option value="cycle">⭐ Cycle croissance : 3 gags éclair de 15 s puis 1 sketch long de +1 min (recommandé)</option>
      <option value="mini">⚡ Gags éclair uniquement (15 s)</option>
      <option value="libre">🎭 Sketchs longs uniquement (+1 min, rémunérables)</option>
      <option value="actu">📰 JT d'actualité (ancien format)</option></select></label>
    <p class="note">Le cycle enchaîne 3 vidéos courtes, qui font monter les abonnés, puis 1 vidéo de plus d'une minute, la seule durée payée par TikTok (programme « Creator Rewards » : 10 000 abonnés et 100 000 vues sur 30 jours). Avec deux émissions par jour, un cycle complet dure deux jours.</p>
  </section>
  <section class="panneau"><h2>📅 Planning</h2>
    <label>Rythme des émissions<select data-var="FREQUENCE" data-def="1"><option value="2x">Deux par jour (12 h + heure choisie, conseillé avec le cycle)</option><option value="1">Une par jour</option><option value="2">Un jour sur deux</option><option value="3">Un jour sur trois</option><option value="0">⏸ Pause (le robot ne produit plus)</option></select></label>
    <label>Heure de fabrication (heure de Paris)<select data-var="HEURE" data-def="17" id="selHeure"></select></label>
    <p class="note">La vidéo est prête environ 20 à 40 minutes après cette heure. 17 h (recommandé) = publiée pour le pic d'audience de 18 h à 21 h.</p>
  </section>
  <section class="panneau"><h2>✍️ Écriture</h2>
    <label>Exigence (note minimale pour publier automatiquement)<select data-var="SEUIL_QUALITE" data-def="90"><option value="95">95/100 (très rare)</option><option value="90">90/100 (recommandé)</option><option value="85">85/100</option><option value="80">80/100</option><option value="75">75/100</option></select></label>
    <label>Auteur (modèle Claude)<select data-var="MODELE_CLAUDE" data-def="claude-opus-5-5"><option value="claude-opus-5-5">Opus (le plus drôle, recommandé)</option><option value="claude-sonnet-5-5">Sonnet (économique)</option></select></label>
    <label>Nombre de retouches maximum<select data-var="MAX_REECRITURES" data-def="4"><option value="4">4 (recommandé)</option><option value="2">2 (économique)</option><option value="6">6 (le plus exigeant)</option></select></label>
  </section>
  <section class="panneau"><h2>🎥 Vidéo animée</h2>
    <div class="auto" style="margin-bottom:12px"><div class="txt"><b>Voix ElevenLabs</b><small>Voix réalistes avec rires et coups de colère (abonnement ElevenLabs). Coupé : voix gratuites.</small></div><button class="inter" data-var="ELEVENLABS" data-def="1" data-bascule="1"></button></div>
    <div class="auto"><div class="txt"><b>Décors générés par IA</b><small>Un décor du quotidien par scène, adapté à l'histoire (Stable Diffusion XL, crédits Modal). Coupé : fonds unis pastel.</small></div><button class="inter" data-var="DECORS" data-def="1" data-bascule="1"></button></div>
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
  <div id="suivi"></div>
</div></div>
<div id="toast"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcode-generator/1.4.4/qrcode.min.js"></script>
<script>
const DATA = __DATA__, CONF = __CONF__;
const API = "https://api.github.com/repos/" + CONF.depot;
const $ = s => document.querySelector(s);
let choisie = null, fichier = null, charge = null, armer = null;
function toast(t){const e=$("#toast");e.textContent=t;e.style.display="block";clearTimeout(e._t);e._t=setTimeout(()=>e.style.display="none",3200)}
function dateFr(d){try{return new Date(d+"T12:00:00").toLocaleDateString("fr-FR",{weekday:"long",day:"numeric",month:"long"})}catch(e){return d}}
function lireJeton(){try{return localStorage.getItem("jt_jeton")||""}catch(e){return window._jeton||""}}
function ecrireJeton(v){try{v?localStorage.setItem("jt_jeton",v):localStorage.removeItem("jt_jeton")}catch(e){window._jeton=v}}
async function gh(chemin, opts={}){
  const j=lireJeton(); if(!j) throw new Error("régie non connectée");
  const r=await fetch(API+chemin,{...opts,headers:{"Authorization":"Bearer "+j,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",...(opts.body?{"Content-Type":"application/json"}:{})}});
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
  if(v.publie===true) return '<span class="badge ok">✓ Publiée sur TikTok</span>';
  if(v.publie===false) return '<span class="badge ko">⚠ Échec de publication</span>';
  return '<span class="badge att">⏸ En attente de validation</span>';
}
function rendre(){
  const L=$("#liste");
  if(!DATA.length){L.innerHTML='<p class="vide">Aucune vidéo pour l\'instant.</p>';return}
  DATA.forEach((v,i)=>{
    const c=document.createElement("div");c.className="carte";c.dataset.i=i;
    c.innerHTML=`<img loading="lazy" src="videos/${v.poster}" alt=""><div class="infos"><div class="titre"></div><div class="date">${dateFr(v.date)}</div>${badge(v)}<div class="etat"></div></div><button class="croix" title="Supprimer cette vidéo" aria-label="Supprimer">✕</button>`;
    c.querySelector(".titre").textContent=v.titre; c.onclick=()=>choisir(i);
    c.querySelector(".croix").onclick=(ev)=>{ev.stopPropagation(); supprimer(i,c)}; L.appendChild(c);
  });
}
async function supprimer(i,c){
  const v=DATA[i];
  if(!lireJeton()){toast("Connectez la régie (onglet Réglages) pour supprimer");return}
  if(!confirm(`Supprimer définitivement « ${v.titre} » (${dateFr(v.date)}) ?\n\nLa vidéo sera effacée de l'application et des archives. Cette action est irréversible.`)) return;
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
    }catch(e){s.textContent="Suivi interrompu : "+e.message; majBoutons(); return}
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
$("#montrerQR").onclick=()=>{
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
  $("#o-videos").style.display=b.dataset.o==="videos"?"":"none"; $("#o-config").style.display=b.dataset.o==="config"?"":"none";
  $("#barre").style.display=b.dataset.o==="videos"?"":"none"; document.body.dataset.onglet=b.dataset.o; if(b.dataset.o==="config") chargerReglages();
});
// ------------------------------------------------ réglages (variables du dépôt GitHub)
for(let h=5;h<=22;h++){const o=document.createElement("option");o.value=h;o.textContent=h+" h";$("#selHeure").appendChild(o)}
$("#lienActions").href="https://github.com/"+CONF.depot+"/actions";
async function ecrireVar(nom,valeur){
  const corps=JSON.stringify({name:nom,value:String(valeur)});
  let r=await gh("/actions/variables/"+nom,{method:"PATCH",body:corps});
  if(r.status===404) r=await gh("/actions/variables",{method:"POST",body:corps});
  if(!r.ok) throw new Error("GitHub a répondu "+r.status);
}
const champs=()=>document.querySelectorAll("#o-config [data-var]");
function activer(on){champs().forEach(c=>c.disabled=!on);document.querySelectorAll("#o-config .action,[data-enr]").forEach(b=>b.disabled=!on)}
$("#garder2").onclick=()=>{const v=$("#jeton2").value.trim(); if(!v)return; ecrireJeton(v); $("#jeton2").value=""; lireAuto(); majBoutons(); chargerReglages()};
async function chargerReglages(){
  $("#cfgConnexion").style.display=lireJeton()?"none":""; $("#appairage").style.display=lireJeton()?"":"none";
  if(!lireJeton()){activer(false);$("#cfgEtat").textContent="";return}
  $("#cfgEtat").textContent="Lecture des réglages…";
  try{
    const r=await gh("/actions/variables?per_page=50"); const d=await r.json(); const v={};
    (d.variables||[]).forEach(x=>v[x.name]=x.value);
    champs().forEach(c=>{const val=(c.dataset.var in v)?v[c.dataset.var]:c.dataset.def;
      if(c.dataset.bascule) c.classList.toggle("on",String(val)!=="0"); else c.value=val;});
    activer(true); $("#cfgEtat").textContent="Régie connectée ✓ — chaque changement est enregistré immédiatement.";
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
async function lancerFlux(fichier,bouton,texte,inputs){
  bouton.disabled=true; const s=$("#suiviCfg"); const depart=new Date(Date.now()-5000);
  try{
    const r=await gh(`/actions/workflows/${fichier}/dispatches`,{method:"POST",body:JSON.stringify(inputs?{ref:CONF.branche,inputs}:{ref:CONF.branche})});
    if(r.status!==204) throw new Error("GitHub a répondu "+r.status);
    s.textContent=texte;
    for(let k=0;k<200;k++){
      await new Promise(r=>setTimeout(r,15000));
      const d=await (await gh(`/actions/workflows/${fichier}/runs?event=workflow_dispatch&per_page=3`)).json();
      const run=(d.workflow_runs||[]).find(x=>new Date(x.created_at)>=depart); if(!run) continue;
      if(run.status!=="completed"){s.textContent=texte+" ("+(run.status==="queued"?"en file d'attente":"en cours")+")";continue}
      s.innerHTML=run.conclusion==="success"?"✅ Terminé. Rouvrez l'application dans une minute pour voir le résultat.":`❌ Échec. <a style="color:var(--bleu)" href="${run.html_url}" target="_blank" rel="noopener">Voir le détail</a>`;
      break;
    }
  }catch(e){s.textContent="Impossible : "+e.message}
  bouton.disabled=false;
}
$("#lancer").onclick=()=>lancerFlux("emission.yml",$("#lancer"),"📰 Le robot fabrique un JT d'actualité (20 à 40 min)…",{format:"actu"});
$("#lancerMini").onclick=()=>lancerFlux("emission.yml",$("#lancerMini"),"⚡ Le robot fabrique un gag éclair (15 à 30 min)…",{format:"mini"});
$("#lancerLibre").onclick=()=>lancerFlux("emission.yml",$("#lancerLibre"),"🎭 Le robot fabrique un sketch long (20 à 40 min)…",{format:"libre"});
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
