"""Registre des pannes (choix de l'auteur du 11 novembre 2026, idée 20).

À la fin de chaque fabrication (emission.yml), le journal est relu : chaque erreur ou repli (« … impossible », « … indisponible »,
« … en échec », Traceback, « Erreur ») est ramené à sa FORME (chiffres, liens, chemins et textes entre guillemets retirés) pour que la
même panne soit comptée une seule fois, quelle que soit la vidéo. episodes/pannes.json garde, pour chaque forme : le nombre de
fabrications touchées, la première et la dernière date, un exemple et l'étape. Le site (Réglages → « 🧯 Registre des pannes ») montre
celles qui reviennent le plus sur les 30 derniers jours : on corrige d'abord celles-là.
Deux fabrications qui finissent en même temps ne s'écrasent pas (fusion.FUSIONNES : nombres additionnés)."""
import datetime, json, os, re, sys

FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "pannes.json")
SIGNES = re.compile(r"(impossible|indisponible|en échec|échoué|echec|traceback|erreur|error|exception|refus[ée]|introuvable|plante|"
                    r"illisible|n'a pas pu|pas pu |timed? ?out|délai dépassé)", re.I)
BANAL = re.compile(r"(\b0 erreur|aucune erreur|sans erreur|✔|rien à enregistrer)", re.I)


def forme(ligne):
    """La même panne, quelle que soit la vidéo : sans chiffres, liens, chemins ni textes cités."""
    t = re.sub(r"https?://\S+", "<lien>", ligne)
    t = re.sub(r"(/[\w.\-]+){2,}", "<chemin>", t)
    t = re.sub(r"«[^»]*»|\"[^\"]*\"|'[^']{6,}'", "«…»", t)
    t = re.sub(r"\d+([.,]\d+)?", "N", t)
    t = re.sub(r"\s+", " ", t).strip(" -:·")
    return t[:140]


def lire_journal(texte):
    """[(forme, exemple, étape)] des pannes d'un journal de fabrication (une fois chacune)."""
    out, etape, vues = [], "", set()
    for l in str(texte or "").splitlines():
        l = l.strip()
        m = re.match(r"^\[équipe · ([^\]]+)\]", l)
        if m: etape = m.group(1)
        if not l or BANAL.search(l) or not SIGNES.search(l): continue
        if re.match(r'^(File ")|^\s*\^', l): continue                      # lignes de pile d'un Traceback : seul le message compte
        f = forme(l)
        if len(f) < 12 or f in vues: continue
        vues.add(f); out.append((f, l[:240], etape))
    return out


def ajouter(texte, quand=None, fichier=FICHIER):
    quand = quand or datetime.date.today().isoformat()
    try: R = json.load(open(fichier, encoding="utf-8"))
    except (OSError, ValueError): R = {}
    for f, ex, et in lire_journal(texte):
        e = R.setdefault(f, {"n": 0, "premiere": quand, "derniere": quand, "exemple": ex, "etape": et, "jours": {}})
        e["n"] += 1; e["derniere"] = quand; e["exemple"] = ex; e["etape"] = et or e.get("etape", "")
        e["jours"][quand] = e["jours"].get(quand, 0) + 1
        e["jours"] = dict(sorted(e["jours"].items())[-60:])
    limite = (datetime.date.fromisoformat(quand) - datetime.timedelta(days=90)).isoformat()
    R = {f: e for f, e in R.items() if e.get("derniere", "") >= limite}  # pannes disparues depuis 3 mois : oubliées
    os.makedirs(os.path.dirname(fichier), exist_ok=True)
    json.dump(R, open(fichier, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return R


def fusionner(eux, nous, base):
    """fusion.FUSIONNES : comptes des deux fabrications additionnés (distant + nous - départ commun)."""
    def lire(b):
        try: d = json.loads(b or b"{}"); return d if isinstance(d, dict) else {}
        except ValueError: return {}
    e, n, b = lire(eux), lire(nous), lire(base)
    out = dict(e)
    for f, v in n.items():
        if f not in out: out[f] = v; continue
        v0 = b.get(f, {}); o = dict(out[f])
        o["n"] = int(o.get("n", 0)) + int(v.get("n", 0)) - int(v0.get("n", 0))
        o["derniere"] = max(o.get("derniere", ""), v.get("derniere", ""))
        j = dict(o.get("jours") or {})
        for d, c in (v.get("jours") or {}).items(): j[d] = j.get(d, 0) + c - (v0.get("jours") or {}).get(d, 0)
        o["jours"] = j; out[f] = o
    return json.dumps(out, ensure_ascii=False, indent=1).encode()


if __name__ == "__main__":
    j = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(FICHIER), "journal.txt")
    try: R = ajouter(open(j, encoding="utf-8", errors="replace").read())
    except OSError: R = {}
    print(f"Registre des pannes : {len(R)} forme(s) de panne suivie(s)")
