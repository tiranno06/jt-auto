"""Orthographe et grammaire françaises par LanguageTool (LGPL ; choix de l'auteur du 11 novembre 2026, idée 15).
Service public gratuit api.languagetool.org (20 demandes / min : une seule demande par vidéo pour tous les sous-titres ; seul le
texte du dialogue est envoyé, rien d'autre). ORTHOGRAPHE=0 pour couper.
Règle d'or : les sous-titres restent ce qui est DIT. On n'accepte que les corrections qui ne s'entendent pas :
- accents (« a » -> « à », « ou » -> « où ») ;
- terminaisons muettes (« ils mange » -> « ils mangent », « des pomme » -> « des pommes ») : même début de mot, on AJOUTE des lettres ;
jamais un mot remplacé par un autre, jamais un mot ajouté ou retiré (« J'sais pas » reste « J'sais pas »), jamais un nom propre."""
import json, os, re, unicodedata, urllib.parse, urllib.request

URL = "https://api.languagetool.org/v2/check"


def _nu(t): return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def acceptable(avant, apres):
    """La correction ne change pas ce qu'on entend : mêmes mots, seuls des accents ou des lettres muettes AJOUTÉES en fin de mot."""
    a, b = avant.split(), apres.split()
    if len(a) != len(b) or avant == apres: return False
    for x, y in zip(a, b):
        if x == y: continue
        nx, ny = _nu(x), _nu(y)
        if nx == ny: continue                                              # accent seulement
        if x[:1].isupper(): return False                                   # nom propre (ou début de phrase : on ne touche pas)
        if not (ny.startswith(nx) and 1 <= len(ny) - len(nx) <= 3 and re.fullmatch(r"[a-z]+", ny[len(nx):])): return False
        if ny[len(nx):] not in ("s", "x", "e", "es", "nt", "ent", "t", "ée", "ées", "és", "é"): return False
    return True


def _demander(texte, delai=20):
    d = urllib.parse.urlencode({"text": texte, "language": "fr", "level": "default"}).encode()
    req = urllib.request.Request(URL, data=d, headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "jt-auto"})
    with urllib.request.urlopen(req, timeout=delai) as r: return json.loads(r.read().decode())


def corriger_lignes(lignes, demander=None):
    """(lignes corrigées, nombre de corrections). Une seule demande au service pour toutes les lignes."""
    if os.environ.get("ORTHOGRAPHE", "1") == "0" or not lignes: return list(lignes), 0
    texte = "\n\n".join(lignes)
    if len(texte) > 18000: return list(lignes), 0
    try: d = (demander or _demander)(texte)
    except Exception as e:
        print(f"  LanguageTool indisponible ({str(e)[:100]})", flush=True); return list(lignes), 0
    debuts, p = [], 0
    for l in lignes: debuts.append(p); p += len(l) + 2
    out, n = list(lignes), 0
    for m in sorted(d.get("matches") or [], key=lambda m: -int(m["offset"])):   # de la fin vers le début : les positions restent justes
        o, L = int(m["offset"]), int(m["length"])
        k = max(i for i, b in enumerate(debuts) if b <= o)
        o2 = o - debuts[k]
        if o2 + L > len(lignes[k]): continue
        avant = out[k][o2:o2 + L]
        if avant != lignes[k][o2:o2 + L]: continue                         # déjà touché par une autre correction
        cands = [r["value"] for r in (m.get("replacements") or [])[:5] if acceptable(avant, r["value"])]
        if not cands: continue
        apres = max(cands, key=lambda r: (len(r), -cands.index(r)))       # les lettres muettes AJOUTÉES (pluriels, accords) d'abord
        out[k] = out[k][:o2] + apres + out[k][o2 + L:]; n += 1
    if n: print(f"  LanguageTool : {n} faute(s) d'orthographe corrigée(s) (accents, accords muets)", flush=True)
    return out, n


def corriger_texte(t, demander=None):
    """Description TikTok : même règle ; les hashtags et les @comptes ne sont jamais touchés."""
    morceaux = re.split(r"((?:#|@)[\w.]+)", t or "")
    a_corriger = [i for i, x in enumerate(morceaux) if x and not re.match(r"[#@]", x)]
    lignes, _n = corriger_lignes([morceaux[i] for i in a_corriger], demander)
    for i, l in zip(a_corriger, lignes): morceaux[i] = l
    return "".join(morceaux)
