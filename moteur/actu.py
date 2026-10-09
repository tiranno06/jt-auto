"""Récupère les titres politiques récents dans des flux RSS de médias français."""
import html, re, datetime, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FLUX = [
    "https://www.franceinfo.fr/politique.rss",
    "https://www.lemonde.fr/politique/rss_full.xml",
    "https://www.lefigaro.fr/rss/figaro_politique.xml",
    "https://www.20minutes.fr/feeds/rss-politique.xml",
    "https://www.lexpress.fr/arc/outboundfeeds/rss/politique.xml",
    "https://www.bfmtv.com/rss/politique/",
]

def _texte(x):
    x = html.unescape(re.sub(r"<[^>]+>", " ", x or ""))
    return re.sub(r"\s+", " ", x).strip()

def _date(s):
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        except Exception: return None
    return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)

def lire_flux(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (robot-jt-satirique)"})
    data = urllib.request.urlopen(req, timeout=timeout).read()
    root = ET.fromstring(data); items = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"): continue
        get = lambda n: next((c for c in it if c.tag.split("}")[-1] == n), None)
        titre = _texte(getattr(get("title"), "text", ""))
        desc = _texte(getattr(get("description"), "text", "") or getattr(get("summary"), "text", ""))
        lien_el = get("link"); lien = (lien_el.text or lien_el.get("href", "")) if lien_el is not None else ""
        d = _date(getattr(get("pubDate"), "text", None) or getattr(get("published"), "text", None) or getattr(get("updated"), "text", None))
        if titre: items.append(dict(titre=titre, resume=desc[:400], lien=(lien or "").strip(), date=d, source=url.split("/")[2]))
    return items

def titres_recents(heures=36, deja_vus=(), maxi=30):
    maintenant = datetime.datetime.now(datetime.timezone.utc); tous = []
    for url in FLUX:
        try:
            tous += lire_flux(url)
        except Exception as e:
            print(f"  flux ignoré {url} : {e}", flush=True)
    recents, vus = [], set()
    for it in sorted(tous, key=lambda i: i["date"] or maintenant, reverse=True):
        if it["date"] and (maintenant - it["date"]).total_seconds() > heures * 3600: continue
        cle = re.sub(r"\W+", "", it["titre"].lower())[:60]
        if cle in vus or it["lien"] in deja_vus: continue
        vus.add(cle); recents.append(it)
    return recents[:maxi]
