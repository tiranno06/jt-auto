const CACHE = "regie-v23";
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
