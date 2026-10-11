"""Mots-clés d'un sujet (pour reconnaître dans l'historique un sujet déjà traité). La recherche d'actualité (ancien mode JT) a été supprimée."""
import re, unicodedata

VIDES = set("""le la les un une des du de d l au aux et ou en dans sur sous pour par avec sans ce cet cette ces son sa ses leur leurs qui que quoi
dont est sont a ont été être avoir fait faire plus moins très tout tous toute toutes après avant contre entre chez comme mais donc or ni car
il elle ils elles on nous vous je tu se s y ne pas n quand comment pourquoi selon face depuis vers lors ainsi aussi encore déjà va vont peut
doit veut dit annonce annoncé nouveau nouvelle nouveaux nouvelles premier première deux trois ans an jour jours semaine mois heure heures
france français française françaises français paris live direct vidéo video info infos actu actualité ce qu il faut savoir
demande demandé demander demandent explique expliquer explications réagit réagir estime affirme assure déclare""".split())


def _mots(t):
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return {m for m in re.findall(r"[a-z0-9]{4,}", t) if m not in VIDES and not m.isdigit()}

ABREV = {"prof": "professeur", "profs": "professeur", "manif": "manifestation", "gouv": "gouvernement", "depute": "deputes",
         "presidentiel": "presidentielle", "senateur": "senat", "retraite": "retraites", "ministere": "ministre", "smic": "salaire"}

def _racine(m):
    m = ABREV.get(m, m)
    if len(m) > 5 and m[-1] in "sx": m = m[:-1]
    return ABREV.get(m, m)[:7]

def empreinte(texte):
    """Mots-clés normalisés d'un sujet (pluriels, abréviations) : sert à reconnaître un sujet déjà traité."""
    return {_racine(m) for m in _mots(texte)}

