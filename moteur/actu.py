"""Récupère l'actualité dans des flux RSS de médias français et repère LE sujet qui fait les gros titres
(celui que le plus de médias différents traitent en ce moment)."""
import html, re, datetime, unicodedata, urllib.request
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
# flux « à la une » : servent à mesurer ce qui fait les gros titres
UNES = [
    "https://www.franceinfo.fr/titres.rss",
    "https://www.lemonde.fr/rss/une.xml",
    "https://www.lefigaro.fr/rss/figaro_actualites.xml",
    "https://www.20minutes.fr/feeds/rss-une.xml",
    "https://www.bfmtv.com/rss/news-24-7/",
    "https://www.lexpress.fr/arc/outboundfeeds/rss/alaune.xml",
    "https://www.liberation.fr/arc/outboundfeeds/rss-all/?outputType=xml",
]
# sujets dont on ne rit pas (drames, victimes)
DRAMES = re.compile(r"\b(mort|morts|morte|décès|décédé|tué|tués|tuée|meurtre|assassin|attentat|terroris|viol|victime|victimes|"
                    r"otage|massacre|bombard|guerre|israël|israel|gaza|hamas|palestin|hezbollah|ukrain|russie|iran|cisjordanie|blessé|blessés|noyé|incendie|crash|deuil|obsèques|pédo|agression|féminicide|suicide)", re.I)
# rubriques récurrentes (bourse, météo, jeux, horoscope…) : jamais un « sujet du jour »
RUBRIQUES = re.compile(r"(\d{2}/\d{2}|bourse|cac 40|marchés|valeurs|météo|horoscope|loto|euromillions|programme tv|résultats du|en direct|live|replay|podcast|quiz)", re.I)
VIDES = set("""le la les un une des du de d l au aux et ou en dans sur sous pour par avec sans ce cet cette ces son sa ses leur leurs qui que quoi
dont est sont a ont été être avoir fait faire plus moins très tout tous toute toutes après avant contre entre chez comme mais donc or ni car
il elle ils elles on nous vous je tu se s y ne pas n quand comment pourquoi selon face depuis vers lors ainsi aussi encore déjà va vont peut
doit veut dit annonce annoncé nouveau nouvelle nouveaux nouvelles premier première deux trois ans an jour jours semaine mois heure heures
france français française françaises français paris live direct vidéo video info infos actu actualité ce qu il faut savoir""".split())

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


def _mots(t):
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return {m for m in re.findall(r"[a-z0-9]{4,}", t) if m not in VIDES and not m.isdigit()}

def sujet_du_jour(heures=24, deja_vus=(), mots_recents=()):
    """Regroupe les titres par sujet (mots-clés communs) et renvoie le sujet traité par le plus de médias différents.
    Renvoie (titres du sujet, description) ou (None, raison)."""
    maintenant = datetime.datetime.now(datetime.timezone.utc); tous = []
    for url in FLUX + UNES:
        try: tous += [dict(i, flux=url) for i in lire_flux(url)]
        except Exception as e: print(f"  flux ignoré {url} : {e}", flush=True)
    items, vus = [], set()
    for it in tous:
        if it["date"] and (maintenant - it["date"]).total_seconds() > heures * 3600: continue
        cle = re.sub(r"\W+", "", it["titre"].lower())[:60]
        if cle in vus or it["lien"] in deja_vus or DRAMES.search(it["titre"] + " " + it["resume"][:200]) or RUBRIQUES.search(it["titre"]): continue
        vus.add(cle); it["mots"] = _mots(it["titre"] + " " + it["resume"][:160]); items.append(it)
    if len(items) < 3: return None, "pas assez de titres"
    # mots trop courants (présents dans plus de 6 % des titres) : ils ne caractérisent pas un sujet
    from collections import Counter
    freq = Counter(m for it in items for m in it["mots"]); lim = max(3, 0.06 * len(items))
    for it in items: it["cles"] = {m for m in it["mots"] if freq[m] <= lim}
    groupes = []                                                          # pour chaque titre : les titres qui partagent au moins 2 mots-clés distinctifs
    for it in items:
        membres = [x for x in items if len(x["cles"] & it["cles"]) >= 2]
        groupes.append({"items": membres, "mots": set(it["mots"]), "graine": it})
    recents = set(mots_recents)
    def score(g):
        sources = {i["source"] for i in g["items"]}
        frais = sum(1 for i in g["items"] if i["date"] and (maintenant - i["date"]).total_seconds() < 12 * 3600)
        deja = len(g["mots"] & recents) >= 4                                 # sujet déjà traité ces derniers jours
        return (len(sources) * 3 + len(g["items"]) + frais) * (0.3 if deja else 1)
    for g in groupes:                                                    # on veut un sujet de politique française : au moins un article des rubriques politique
        g["politique"] = any(i.get("flux") in FLUX for i in g["items"])
    groupes.sort(key=lambda g: (g["politique"], score(g)), reverse=True)
    g = groupes[0]; graine = g["graine"]
    sel = [graine] + [i for i in sorted(g["items"], key=lambda i: i["date"] or maintenant, reverse=True) if i is not graine][:7]
    nb = len({i["source"] for i in g["items"]})
    return sel, f"{len(g['items'])} articles, {nb} médias"
