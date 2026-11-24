"""Fiche de tournage d'un son TikTok (choix de l'auteur du 20 novembre 2026, idées 1 à 5, avec un triple contrôle).

Avant, chaque poste devinait de son côté (le décor d'après quelques mots, les habits d'après d'autres indices). Maintenant tout est
décidé UNE fois, d'après l'audio et la vidéo d'origine, et tous les postes (décor, costumes, jeu, objets, détails) suivent la même fiche :
- idée 1 : Gemini écoute ET regarde l'original en entier et écrit la fiche (lieu exact, heure, météo, saison, ambiance, niveau de vie,
  décor, détails de l'histoire, lumière ; pour chaque personnage : âge, allure, coiffure, tenue et son état, métier ; réplique par
  réplique : émotion, geste, objet, ce qu'il en fait, signe d'émotion ; réactions de celui qui écoute). Sans Gemini : une IA de texte
  sur le dialogue, sinon les règles seules ;
- idée 2 : les bruits de fond de l'original (CLAP : pluie, klaxons, vaisselle, télé, foule, oiseaux, vent, sirène…) et l'écho de la
  voix (petite pièce carrelée, grande salle) deviennent des éléments du décor ;
- idée 3 : le moment tiré des paroles (« il est 3 h du mat' », « il fait une chaleur », « je sors du boulot ») ;
- idée 4 : les objets cités (« ma voiture », « le frigo est vide », « ton gâteau ») vont dans le décor ou dans les mains ;
- idée 5 : le niveau de vie du lieu d'après le dialogue (appart d'étudiant en désordre, maison chic…).

TRIPLE CONTRÔLE avant de dessiner, avec correction automatique (demande de l'auteur) :
 1. les règles (cohérence interne et avec ce qui est DIT : nuit contre « il fait jour », maillot de bain au bureau, enfant barbu,
    homme / femme contre le vote des voix, objet cité absent, signe d'émotion contraire à l'émotion…) ;
 2. une 2e IA, d'un autre fournisseur, relit la fiche contre le dialogue et propose des corrections (champs autorisés seulement) ;
 3. ce que l'image de l'original a montré (analyse Gemini de la vidéo, personnes vues, lumière) : lieu, nombre de personnes, homme /
    femme vus ; puis les règles une dernière fois.
Chaque correction est notée dans le bulletin de l'équipe (poste « fiche de tournage »). FICHE=0 pour tout couper (ancien fonctionnement)."""
import base64, json, os, re, unicodedata


def journal(t): print(t, flush=True)


def actif(): return os.environ.get("FICHE", "1") != "0"


AMBIANCES = ("dispute", "romance", "peur", "joie", "tristesse", "gene", "calme", "suspense", "fete")
NIVEAUX = ("modeste", "moyen", "aise", "desordre", "luxe")
METEOS = ("", "pluie", "neige", "orage", "chaud", "froid", "vent")
TENUES = ("normale", "pyjama", "peignoir", "maillot_bain", "doudoune", "impermeable", "survetement", "gilet_jaune", "uniforme",
          "costume", "robe_soiree", "robe_mariee", "tablier")
ETATS = ("mouille", "sueur", "tache", "dechire", "maquillage_coule")
SIGNES = ("veine", "nuage", "coeurs", "etoiles", "goutte", "fumee_oreilles")
REACTIONS = ("choque", "yeux_au_ciel", "sourire_coin", "poings_serres", "rire", "gene", "sceptique", "mains_bouche")
ACTIONS = ("tenir", "telephone_oreille", "boire", "manger", "donner", "poche", "montrer", "pianoter")
ANIMATIONS = ("vapeur", "fumee", "pluie_vitre", "tele", "neige")
CHEVEUX = {"court": "court", "long": "long", "boucles": "boucles", "afro": "afro", "chauve": "chauve", "queue": "queue",
           "chignon": "chignon", "carre": "carre", "tresses": "tresses", "rase": "rase", "mi_long": "mi_long", "herisse": "herisse"}
COULEURS_CHEVEUX = {"noir": (35, 30, 32), "brun": (70, 48, 36), "chatain": (110, 78, 52), "blond": (220, 190, 120), "roux": (190, 90, 40),
                    "gris": (150, 150, 155), "blanc": (230, 230, 232)}
CORPULENCES = {"mince": 0.12, "moyen": 0.32, "fort": 0.7}
TAILLES = {"petit": 0.86, "moyen": 1.0, "grand": 1.1}
LIEUX_PUBLICS = ("bar", "restaurant", "magasin", "rue", "classe", "administration", "hall", "boulangerie", "gare", "aeroport", "metro",
                 "fast_food", "kebab", "cinema", "pharmacie", "banque", "poste", "hopital", "urgences", "cantine", "bibliotheque", "salle_sport",
                 "commissariat", "coiffeur", "garage", "parking", "stade", "arret_bus")
GENS = re.compile(r"\b(man|woman|men|women|person|people|boy|girl|child|kid|character|face|crowd|he|she)\b", re.I)


def _nu(t): return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn")


def _anglais(t):
    """Texte destiné à l'IA des décors : anglais, sans personne (sinon elle peint des gens dans le décor)."""
    t = re.sub(r"\s+", " ", str(t or "")).strip(" ,.")
    if not t or re.search(r"[àâçéèêëîïôûùœ]", t.lower()) or GENS.search(t): return ""
    return t[:160]


# ------------------------------------------------------------------ idées 3, 4, 5 : ce que disent les paroles (sans IA)
OBJETS_MOTS = [  # (motif, objet tenu (marionnette.OBJETS) ou "", détail du décor en anglais)
    (r"\bt[ée]l[ée]phone|\bportable\b|\bmon tel\b|\bje t'appelle|\bappelle[- ]moi\b|\bsnap\b|\btexto\b|\bun message\b", "telephone", ""),
    (r"\bun caf[ée]\b|\bmon caf[ée]\b|\bton caf[ée]\b|\bexpresso\b", "cafe", "coffee machine"),
    (r"\bun verre\b|\bboire un coup\b|\bune bi[èe]re\b|\bdu vin\b|\bun mojito\b", "verre", "glasses on a table"),
    (r"\bbouteille\b", "bouteille", ""),
    (r"\bpizzas?\b", "pizza", "pizza boxes"),
    (r"\bcroissants?\b", "croissant", "basket of croissants"),
    (r"\bmes cl[ée]s\b|\bles cl[ée]s\b|\btes cl[ée]s\b", "cles", "key hook by the door"),
    (r"\bvalises?\b|\bbagages?\b", "valise", "packed suitcases"),
    (r"\bparapluie\b", "parapluie", "umbrella stand"),
    (r"\bdes fleurs\b|\bun bouquet\b|\bune rose\b", "fleur", "vase of flowers"),
    (r"\bun cadeau\b|\bton cadeau\b|\bmon cadeau\b", "cadeau", "wrapped gifts"),
    (r"\bune lettre\b|\bcette lettre\b|\bcourrier\b", "lettre", "stack of mail"),
    (r"\bfactures?\b|\bloyer\b|\bimp[ôo]ts?\b", "facture", "pile of unpaid bills on the table"),
    (r"\bt[ée]l[ée]commande\b", "telecommande", "television"),
    (r"\bordi\b|\bordinateur\b|\bpc\b|\blaptop\b", "ordinateur", "laptop on a desk"),
    (r"\btablette\b|\bipad\b", "tablette", ""),
    (r"\bpo[êe]le\b|\bje cuisine\b", "poele", "stove with pans"),     # (« va te faire cuire » est une insulte, pas une poêle)
    (r"\bcolis\b|\bmon paquet\b|\bamazon\b", "colis", "cardboard parcel"),
    (r"\bmicro\b", "micro", ""),
    (r"\bguitare\b", "guitare", "guitar on a stand"),
    (r"\bun livre\b|\bmon livre\b|\bbouquin\b", "livre", "bookshelf full of books"),
    (r"\bsac [àa] main\b|\bmon sac\b|\bton sac\b", "sac_main", ""),
    (r"\bmoto\b|\bscooter\b", "casque_moto", ""),
    (r"\bbillets?\b|\bthunes?\b|\bde l'argent\b|\bfric\b", "billet", ""),
    (r"\bg[âa]teau\b|\banniversaire\b|\banniv\b", "", "birthday cake and balloons"),
    (r"\bfrigo\b|\br[ée]frig[ée]rateur\b", "", "open fridge"),
    (r"\bvaisselle\b|\bl'[ée]vier\b", "", "dirty dishes in the sink"),
    (r"\bmanette\b|\bconsole\b|\bjeux? vid[ée]o\b|\bplay\b|\bfortnite\b|\bfifa\b", "", "game console and controllers by the TV"),
    (r"\bla t[ée]l[ée]\b|\bt[ée]l[ée]vision\b|\bnetflix\b|\bune s[ée]rie\b", "", "television"),
    (r"\bcartons?\b|\bd[ée]m[ée]nag", "", "moving boxes"),
    (r"\bsapin\b|\bno[ëe]l\b", "", "christmas tree with lights"),
    (r"\bdevoirs?\b|\bcahier\b|\bexamen\b|\br[ée]viser\b|\bbac\b", "", "school books and notebooks on a desk"),
    (r"\bcanap[ée]\b", "", "sofa"),
    (r"\blinge\b|\blessive\b|\bmachine [àa] laver\b", "", "laundry basket"),
    (r"\bmon chien\b|\bton chien\b|\ble chien\b", "", "dog bed and toys"),
    (r"\bmon chat\b|\bton chat\b|\ble chat\b", "", "cat tree"),
    (r"\bvoiture\b|\bbagnole\b|\bcaisse\b", "", ""),
]
OCCASIONS = [(r"\banniversaire|\banniv\b|\bjoyeux anniv", "anniversaire"), (r"\bno[ëe]l\b|\bsapin\b|p[èe]re no[ëe]l", "noel"),
             (r"\bmariage\b|\bmari[ée]e?s?\b", "mariage"), (r"\bhalloween\b", "halloween"), (r"\bnouvel an\b|\br[ée]veillon\b", "nouvel_an"),
             (r"\bje pars\b|\bon part\b|\bd[ée]m[ée]nag|\bvalise", "depart"), (r"\bentretien d'embauche\b|\bentretien\b", "entretien"),
             (r"\brentr[ée]e\b|\bexamen\b|\bbac\b|\bpartiel", "ecole"), (r"\bpremier rendez-vous\b|\bun date\b|\bun rencard\b", "rendez_vous"),
             (r"\bsoir[ée]e\b|\bf[êe]te\b", "fete")]


def indices_texte(reps):
    """Ce que les paroles disent du moment, de la météo, de l'occasion, du niveau de vie et des objets (idées 3, 4, 5)."""
    t = " ".join(str(r.get("t") or "") for r in reps).lower()
    out = {"moment": None, "meteo": "", "occasion": None, "niveau": None, "objets": [], "details": [], "explicite": set()}
    m = re.search(r"\b(\d{1,2}) ?h(?:eures?)?(?:\d\d)?\b(?: du mat)?", t)
    if m and ("du mat" in t[m.start():m.end() + 8] or re.search(r"\bdu matin\b|\bde la nuit\b", t[m.start():m.end() + 14])):
        h = int(m.group(1)); out["moment"] = "nuit" if h < 6 else "matin"
    elif re.search(r"\bminuit\b|\bil est tard\b|\bcette nuit\b|\ben pleine nuit\b|\bje vais (me coucher|dormir)\b|\bt'es pas couch|\binsomnie\b", t): out["moment"] = "nuit"
    # (audit du 20 novembre : « je dors plus » ou « la nuit » dans une dispute de bureau avaient mis la scène en pleine nuit)
    elif re.search(r"\bce soir\b|\bd[îi]ner\b|\bap[ée]ro\b|\bje sors du (boulot|taf|travail)\b|\bje rentre du (boulot|taf)\b", t): out["moment"] = "soir"
    elif re.search(r"\bce matin\b|\bpetit[- ]d[ée]j|\bdebout\b.*\bl'[ée]cole\b|\bt'es en retard pour l'[ée]cole\b|\bc'est l'heure de se lever\b", t): out["moment"] = "matin"
    elif re.search(r"\bce midi\b|\bd[ée]jeuner\b|\bil fait jour\b|\bcet apr[èe]s-midi\b", t): out["moment"] = "jour"
    if out["moment"]: out["explicite"].add("moment")
    for motif, met in ((r"\bil pleut\b|\bsous la pluie\b|\bla pluie\b|\btremp[ée]\b|\bparapluie\b", "pluie"), (r"\bil neige\b|\bla neige\b", "neige"),
                       (r"\borage\b|\btonnerre\b", "orage"), (r"\bil fait (trop |tellement |super )?chaud\b|\bcanicule\b|\bcr[èe]ve de chaud\b|\bquelle chaleur\b", "chaud"),
                       (r"\bil fait (trop |tellement |super )?froid\b|\b[çc]a caille\b|\bje me g[èe]le\b|\bje gèle\b", "froid"), (r"\bquel vent\b|\bil y a du vent\b", "vent")):
        if re.search(motif, t): out["meteo"] = met; out["explicite"].add("meteo"); break
    for motif, occ in OCCASIONS:
        if re.search(motif, t): out["occasion"] = occ; break
    if re.search(r"\bc'est le bordel\b|\brange ta chambre\b|\ben d[ée]sordre\b|\bc'est crade\b|\bc'est sale\b|\bun chantier\b", t): out["niveau"] = "desordre"
    elif re.search(r"\bloyer\b|\bfin du mois\b|\bfauch[ée]\b|\bpas de thunes?\b|\bj'ai plus d'argent\b|\bsmic\b|\bcoloc\b|\b[ée]tudiant\b", t): out["niveau"] = "modeste"
    elif re.search(r"\bvilla\b|\bmajordome\b|\bmon chauffeur\b|\bjacuzzi\b|\byacht\b|\bmillionnaire\b|\bluxe\b", t): out["niveau"] = "luxe"
    for i, r in enumerate(reps):
        tr = str(r.get("t") or "").lower()
        for motif, obj, det in OBJETS_MOTS:
            mm = re.search(motif, tr)
            if not mm: continue
            if obj: out["objets"].append({"n": i, "objet": obj, "mot": mm.group(0).strip()})
            if det and det not in out["details"]: out["details"].append(det)
    return out


# ------------------------------------------------------------------ idée 2 : bruits de fond et écho
SONS_DECOR = {"rain": ("pluie", "rain on the windows"), "thunder": ("orage", "dark stormy window"), "siren": (None, "police lights far away"),
              "horn": (None, "busy street outside"), "traffic": (None, "busy street outside the window"), "dishes": (None, "kitchen counter with plates"),
              "tv": (None, "television switched on"), "crowd": (None, "crowded place"), "birds": (None, "trees and birds outside"),
              "wind": ("vent", "trees bending in the wind"), "water": (None, "running tap"), "keyboard": (None, "computer desk"),
              "dog": (None, "dog bed and toys"), "cat": (None, "cat tree"), "applause": (None, "stage lights"), "baby": (None, "baby toys and a crib")}


def indices_son(evenements, duree=None):
    """Bruits de l'original (événements CLAP / ElevenLabs : (début, fin, nom)) -> météo et détails du décor. Un bruit compte s'il dure
    au moins 2 s en tout (un seul instant isolé peut être une erreur de l'écoute)."""
    tot = {}
    for e in evenements or []:
        try: a, b, n = float(e[0]), float(e[1]), str(e[2]).lower()
        except (TypeError, ValueError, IndexError): continue
        tot[n] = tot.get(n, 0.0) + max(0.0, b - a)
    out = {"meteo": "", "details": [], "animations": [], "entendus": sorted(k for k, v in tot.items() if v >= 2.0)}
    for n in out["entendus"]:
        met, det = SONS_DECOR.get(n, (None, None))
        if met and not out["meteo"]: out["meteo"] = met
        if det and det not in out["details"]: out["details"].append(det)
        if n == "tv": out["animations"].append("tele")
    return out


def echo(sig, sr, mots):
    """Écho de la voix (idée 2) : énergie qui traîne juste après la fin des mots par rapport au mot lui-même. Très résonnant ->
    « carrelage » (salle de bain, couloir, hall) ; très mat -> None. Mesure prudente : un seul indice parmi d'autres."""
    try:
        import numpy as np
        x = np.asarray(sig, np.float32)
        if x is None or len(x) < sr: return None
        r = []
        for m in mots or []:
            e = int(float(m["e"]) * sr); s = int(float(m["s"]) * sr)
            if e - s < int(0.08 * sr) or e + int(0.18 * sr) >= len(x): continue
            dedans = float(np.sqrt(np.mean(x[s:e] ** 2)) + 1e-6); apres = float(np.sqrt(np.mean(x[e + int(0.04 * sr):e + int(0.16 * sr)] ** 2)))
            r.append(apres / dedans)
        if len(r) < 8: return None
        v = float(np.median(r))
        return "carrelage" if v > 0.42 else None
    except Exception: return None


# ------------------------------------------------------------------ idée 1 : la fiche écrite par Gemini (vidéo + son), sinon une IA de texte
def _consigne(sk, lieux):
    import studio
    lignes = "\n".join(f"{i}. [{r.get('p')}] {str(r.get('t') or '')[:180]}" for i, r in enumerate(sk.get("repliques") or []))
    roles = sorted({r.get("p") for r in sk.get("repliques") or [] if r.get("p") and r.get("p") != "narrateur"})
    import marionnette as M, metiers
    return f"""Tu prépares le TOURNAGE d'un petit dessin animé qui reprend EXACTEMENT ce son TikTok (mêmes voix, mêmes répliques).
Personnages (identifiants à garder) : {", ".join(roles)} ; "narrateur" = voix sans personnage.
Répliques numérotées :
{lignes}

Construis tout l'univers visuel en parfaite cohérence avec l'audio (paroles, intonations, bruits, ambiance) et avec l'image de la
vidéo d'origine si tu la vois. Réponds UNIQUEMENT en JSON :
{{"lieu": un mot parmi {", ".join(lieux)},
 "lieu_precis": "décor exact EN ANGLAIS, 8 à 15 mots, sans personne (ex. small messy student bedroom with posters)",
 "interieur": true/false, "moment": "matin|jour|soir|nuit", "meteo": "|pluie|neige|orage|chaud|froid|vent",
 "occasion": "anniversaire, noel, depart… ou vide", "ambiance": un mot parmi {", ".join(AMBIANCES)},
 "niveau": un mot parmi {", ".join(NIVEAUX)},
 "details": ["3 à 5 accessoires de l'HISTOIRE EN ANGLAIS, 2 à 5 mots chacun, sans personne (ex. pile of unpaid bills)"],
 "lumiere": "lumière EN ANGLAIS, 3 à 6 mots (ex. cold harsh neon light)",
 "panneaux": ["textes courts EN FRANÇAIS lisibles dans le décor (enseigne, menu, tableau), 0 à 2, seulement si le lieu en a"],
 "ecran_tel": "ce qu'affiche le téléphone s'il sert (ex. Maman, Nouveau message), sinon vide",
 "animations": [parmi {", ".join(ANIMATIONS)}],
 "personnages": {{"<identifiant>": {{"genre": "h|f", "age": nombre, "corpulence": "mince|moyen|fort", "taille": "petit|moyen|grand",
     "cheveux": un mot parmi {", ".join(CHEVEUX)}, "c_cheveux": un mot parmi {", ".join(COULEURS_CHEVEUX)}, "barbe": "aucune|trois_jours|moustache",
     "lunettes": true/false, "tenue": un mot parmi {", ".join(TENUES)}, "haut": un mot parmi {", ".join(M.HAUTS)}, "c_haut": "couleur en français",
     "etat_tenue": [parmi {", ".join(ETATS)}], "metier": "métier ou vide"}}}},
 "repliques": [{{"n": numéro, "emotion": un mot parmi {", ".join(studio.EMOTIONS_JEU)}, "intensite": 1 à 3,
     "geste": un mot parmi {", ".join(studio.GESTES)} ou vide, "cible": "autre|objet|", "objet": un mot parmi {", ".join(M.OBJETS)} ou vide,
     "action": un mot parmi {", ".join(ACTIONS)} ou vide, "signe": un mot parmi {", ".join(SIGNES)} ou vide}}],
 "reactions": [{{"n": numéro de la réplique, "qui": identifiant de celui qui ÉCOUTE, "mot": "le mot de la réplique qui le fait réagir",
     "reaction": un mot parmi {", ".join(REACTIONS)}}}]}}
Règles : rien d'inventé contre le dialogue (s'il dit « il fait jour », pas de nuit ; un objet cité doit apparaître) ; une personne dont on
parle mais qu'on ne voit pas n'est pas un personnage ; un enfant n'a jamais de barbe ; signe : veine = colère, coeurs = amour, nuage =
déprime, etoiles = choc ou émerveillement, goutte = gêne ou stress, fumee_oreilles = rage ; "metier" seulement s'il est dit ou vu."""


def _gemini_video(chemin, texte):
    """Fiche écrite par Gemini en regardant et en écoutant la vidéo d'origine en entier (API native, vidéo réduite 360p)."""
    cle = os.environ.get("GEMINI_API_KEY")
    if not cle or not chemin or not os.path.exists(chemin): return None
    import reseau, video_ia
    if "gemini" in reseau.HORS_SERVICE: return None
    v = video_ia._petite(chemin)
    if not v: return None
    corps = {"contents": [{"parts": [{"inline_data": {"mime_type": "video/mp4", "data": base64.b64encode(open(v, "rb").read()).decode()}}, {"text": texte}]}],
             "generationConfig": {"temperature": 0.3, "response_mime_type": "application/json"}}
    return video_ia.generer(corps, timeout=240, valide=lambda r: bool(r.get("lieu")), journal=journal, quoi="fiche de tournage")


def _ia_texte(texte, exclure=()):
    """Même fiche par une IA de texte (dialogue seul), en repli."""
    import ecrire, reseau
    if not reseau.ia_disponible(): return None
    try:
        cl = reseau.claude(exclure=exclure)
        props = {k: {"type": "string"} for k in ("lieu", "lieu_precis", "moment", "meteo", "occasion", "ambiance", "niveau", "lumiere", "ecran_tel")}
        props.update(interieur={"type": "boolean"}, details={"type": "array", "items": {"type": "string"}}, panneaux={"type": "array", "items": {"type": "string"}},
                     animations={"type": "array", "items": {"type": "string"}}, personnages={"type": "object"},
                     repliques={"type": "array", "items": {"type": "object"}}, reactions={"type": "array", "items": {"type": "object"}})
        r = ecrire._appel(cl, None, [{"role": "user", "content": texte}],
                          {"name": "fiche", "description": "La fiche de tournage.", "input_schema": {"type": "object", "properties": props, "required": ["lieu"]}},
                          max_tokens=4000)
        return r if isinstance(r, dict) and r else None
    except Exception as e:
        journal(f"  fiche de tournage par l'IA de texte impossible ({str(e)[:100]})"); return None


# ------------------------------------------------------------------ remise en forme (valeurs autorisées seulement)
def nettoyer(f, sk):
    """Fiche brute (IA) -> fiche propre : chaque valeur vérifiée contre les listes autorisées, le reste retiré."""
    import decor_dessin as DD, studio, marionnette as M, metiers
    f = f if isinstance(f, dict) else {}
    roles = sorted({r.get("p") for r in sk.get("repliques") or [] if r.get("p") and r.get("p") != "narrateur"})
    n_rep = len(sk.get("repliques") or [])
    def mot(v, autorises, defaut=""):
        v = _nu(v).strip().replace(" ", "_").replace("-", "_")
        return v if v in autorises else defaut
    out = {"lieu": mot(f.get("lieu"), DD.LIEUX), "lieu_precis": _anglais(f.get("lieu_precis")), "interieur": bool(f.get("interieur", True)),
           "moment": mot(f.get("moment"), studio.MOMENTS), "meteo": mot(f.get("meteo"), METEOS), "occasion": _nu(f.get("occasion"))[:30],
           "ambiance": mot(f.get("ambiance"), AMBIANCES), "niveau": mot(f.get("niveau"), NIVEAUX),
           "details": [d for d in (_anglais(x) for x in (f.get("details") or [])[:6] if isinstance(x, str)) if d][:5],
           "lumiere": _anglais(f.get("lumiere"))[:60],
           "panneaux": [t for t in (texte_panneau(p) for p in (f.get("panneaux") or [])[:3] if isinstance(p, str)) if t][:2],
           "ecran_tel": str(f.get("ecran_tel") or "").strip()[:20],
           "animations": [a for a in (mot(x, ANIMATIONS) for x in (f.get("animations") or [])) if a],
           "personnages": {}, "repliques": {}, "reactions": [], "source": f.get("source") or "ia"}
    P = f.get("personnages") if isinstance(f.get("personnages"), dict) else {}
    for r in roles:
        d = P.get(r) if isinstance(P.get(r), dict) else {}
        p = {}
        if mot(d.get("genre"), ("h", "f")): p["genre"] = mot(d.get("genre"), ("h", "f"))
        try:
            a = int(float(d.get("age")))
            if 3 <= a <= 95: p["age"] = a
        except (TypeError, ValueError): pass
        for k, tab in (("corpulence", CORPULENCES), ("taille", TAILLES), ("cheveux", CHEVEUX), ("c_cheveux", COULEURS_CHEVEUX)):
            v = mot(d.get(k), tab)
            if v: p[k] = v
        b = mot(d.get("barbe"), ("aucune", "trois_jours", "moustache"))
        if b: p["barbe"] = b
        if isinstance(d.get("lunettes"), bool): p["lunettes"] = d["lunettes"]
        t = mot(d.get("tenue"), TENUES)
        if t: p["tenue"] = t
        h = mot(d.get("haut"), M.HAUTS)
        if h: p["haut"] = h
        c = _nu(d.get("c_haut")).strip()
        if c in studio.NOMS_COULEURS: p["c_haut"] = c
        p["etat_tenue"] = [e for e in (mot(x, ETATS) for x in (d.get("etat_tenue") or [])) if e]
        me = mot(d.get("metier"), metiers.CATALOGUE)
        if me: p["metier"] = me
        out["personnages"][r] = p
    for x in f.get("repliques") or []:
        if not isinstance(x, dict): continue
        try: n = int(x.get("n"))
        except (TypeError, ValueError): continue
        if not 0 <= n < n_rep: continue
        q = {}
        e = mot(x.get("emotion"), studio.EMOTIONS_JEU)
        if e: q["emotion"] = e
        try: q["intensite"] = int(min(3, max(1, int(float(x.get("intensite"))))))
        except (TypeError, ValueError): pass
        for k, tab in (("geste", tuple(studio.GESTES)), ("objet", M.OBJETS), ("action", ACTIONS), ("signe", SIGNES), ("cible", ("autre", "objet"))):
            v = mot(x.get(k), tab)
            if v: q[k] = v
        out["repliques"][n] = q
    for x in f.get("reactions") or []:
        if not isinstance(x, dict): continue
        try: n = int(x.get("n"))
        except (TypeError, ValueError): continue
        rc = mot(x.get("reaction"), REACTIONS); qui = str(x.get("qui") or "")
        if 0 <= n < n_rep and rc and qui in roles: out["reactions"].append({"n": n, "qui": qui, "mot": str(x.get("mot") or "")[:30], "reaction": rc})
    return out


def texte_panneau(p):
    """Le TEXTE écrit sur un panneau, pas sa description (audit du 20 novembre : « Affiche 'Travail & Joie' au mur » était écrit tel
    quel dans le décor) : le passage entre guillemets s'il y en a ; une description sans guillemets est refusée."""
    p = str(p or "").strip()
    m = re.search(r"[«\"'“‘]\s*([^«»\"“”‘’]{2,28}?)\s*[»\"'”’]", p)
    if m: p = m.group(1).strip()
    elif re.match(r"^(affiche|panneau|enseigne|tableau|inscription|menu)\s*:\s*(.+)$", p, re.I):   # « Affiche: Happy Hour éternel »
        p = re.match(r"^\w+\s*:\s*(.+)$", p).group(1).strip()
    elif re.search(r"\b(affiche|panneau|enseigne|tableau|écrit|inscription|au mur|sur la porte|menu de|logo)\b", p, re.I): return ""
    return p if 2 <= len(p) <= 28 else ""


# ------------------------------------------------------------------ contrôle 1 : les règles
PEAU_NUE = ("maillot_bain",)


def controle_regles(F, sk, ind):
    """Cohérence de la fiche avec ce qui est dit et avec elle-même. Corrige en place ; renvoie la liste des corrections."""
    import studio
    cor = []
    def fixe(ou, avant, apres, pourquoi):
        cor.append(f"{ou} : {avant or '—'} -> {apres or '—'} ({pourquoi})")
    reps = sk.get("repliques") or []
    t = " ".join(str(r.get("t") or "") for r in reps).lower()
    if ind.get("moment") and F.get("moment") != ind["moment"]:
        fixe("moment", F.get("moment"), ind["moment"], "dit dans le dialogue"); F["moment"] = ind["moment"]
    if not F.get("moment"): F["moment"] = ind.get("moment") or "jour"
    if ind.get("meteo") and F.get("meteo") != ind["meteo"] and "meteo" in ind.get("explicite", set()):
        fixe("météo", F.get("meteo"), ind["meteo"], "dit dans le dialogue"); F["meteo"] = ind["meteo"]
    if F.get("meteo") in ("pluie", "neige", "orage") and not (ind.get("meteo") or ind.get("meteo_son")) and F.get("source") != "video":
        fixe("météo", F["meteo"], "", "ni dit, ni entendu, ni vu"); F["meteo"] = ""
    if not F.get("lieu"):
        import decor_dessin as DD
        F["lieu"] = DD.lieu_de(t, "") or "salon"; fixe("lieu", "", F["lieu"], "d'après les paroles")
    if not F.get("niveau") and ind.get("niveau"): F["niveau"] = ind["niveau"]
    if not F.get("occasion") and ind.get("occasion"): F["occasion"] = ind["occasion"]
    if F.get("meteo") in ("pluie", "neige", "orage") and F.get("interieur", True) and "pluie_vitre" not in F["animations"] and F["meteo"] != "neige":
        F["animations"].append("pluie_vitre")
    if F.get("meteo") == "neige" and not F.get("interieur", True) and "neige" not in F["animations"]: F["animations"].append("neige")
    for d in ind.get("details") or []:                                     # objets / éléments cités : présents dans le décor
        if d not in F["details"] and len(F["details"]) < 6: F["details"].append(d); fixe("décor", "", d, "cité dans le dialogue ou entendu")
    for r, p in F["personnages"].items():
        g_vote = studio.genre_voix(sk, r, (sk.get("studio") or {}).get("personnages", {}).get(r) if isinstance((sk.get("studio") or {}).get("personnages"), dict) else {})
        if g_vote and p.get("genre") and p["genre"] != g_vote and sk.get("_voix_timbre"):
            fixe(f"{r} genre", p["genre"], g_vote, "vote des voix"); p["genre"] = g_vote
        if p.get("age", 30) < 16 and p.get("barbe") not in (None, "aucune"): fixe(f"{r} barbe", p["barbe"], "aucune", "enfant"); p["barbe"] = "aucune"
        if p.get("genre") == "f" and p.get("barbe") not in (None, "aucune"): fixe(f"{r} barbe", p["barbe"], "aucune", "femme"); p["barbe"] = "aucune"
        ten = p.get("tenue")
        if ten == "maillot_bain" and F["lieu"] not in ("plage", "piscine", "salle_de_bain", "camping") and not re.search(r"maillot|plage|piscine|bronz|nager", t):
            fixe(f"{r} tenue", ten, "normale", f"maillot de bain hors plage ({F['lieu']})"); p["tenue"] = "normale"
        if ten == "doudoune" and F.get("meteo") == "chaud": fixe(f"{r} tenue", ten, "normale", "il fait chaud"); p["tenue"] = "normale"
        if ten == "pyjama" and F["lieu"] not in ("chambre", "salon", "cuisine", "salle_de_bain", "hopital") and not re.search(r"pyjama", t):
            fixe(f"{r} tenue", ten, "normale", f"pyjama hors de la maison ({F['lieu']})"); p["tenue"] = "normale"
        if ten == "robe_mariee" and p.get("genre") == "h": fixe(f"{r} tenue", ten, "costume", "homme"); p["tenue"] = "costume"
        if ten in ("robe_soiree",) and p.get("genre") == "h": fixe(f"{r} tenue", ten, "costume", "homme"); p["tenue"] = "costume"
        lignes = " ".join(str(x.get("t") or "") for x in reps if x.get("p") == r).lower()
        emos = {(F["repliques"].get(i) or {}).get("emotion") for i, x in enumerate(reps) if x.get("p") == r}
        garde = []
        for e in p.get("etat_tenue") or []:
            ok = {"mouille": F.get("meteo") in ("pluie", "orage") and not F.get("interieur", True) or F["lieu"] in ("piscine", "plage") or bool(re.search(r"tremp|mouill|douche|pluie|flotte", t)),
                  "sueur": bool(re.search(r"chaud|sport|courir|cour[su]|transpir|sueur|stress|flipp", t)) or F.get("meteo") == "chaud" or bool(emos & {"panique"}),
                  "tache": bool(re.search(r"tach|renvers|sale|crade|sauce|ketchup|café", t)),
                  "dechire": bool(re.search(r"d[ée]chir|bagarre|tomb[ée]|troué", t)),
                  "maquillage_coule": bool(emos & {"pleurs"}) or bool(re.search(r"pleur|larmes", lignes))}.get(e, False)
            if ok: garde.append(e)
            else: fixe(f"{r} état de la tenue", e, "", "rien ne le justifie dans le son")
        p["etat_tenue"] = garde
    for n, q in F["repliques"].items():
        e = q.get("emotion") or ""
        s = q.get("signe")
        if s:
            ok = {"veine": e in ("colere", "cri"), "fumee_oreilles": e in ("colere", "cri"), "coeurs": e in ("amour", "joie") or F.get("ambiance") == "romance",
                  "nuage": e in ("soupir", "blase", "pleurs", "fatigue", "colere"), "etoiles": e in ("choc", "idee", "joie", "rire", "amour"),
                  "goutte": e in ("gene", "panique", "choc", "reflechit")}.get(s, False)
            if not ok: fixe(f"réplique {n} signe", s, "", f"pas cohérent avec l'émotion « {e or 'neutre'} »"); q.pop("signe")
        if q.get("objet") == "telephone" and n < len(reps) and not re.search(r"t[ée]l[ée]phone|portable|appel|allô|allo|message|snap|photo|texto|\btel\b",
                                                                              str(reps[n].get("t") or "").lower()) and not re.search(r"appel|allô|allo", t):
            fixe(f"réplique {n} objet", "telephone", "", "on ne parle pas de téléphone"); q.pop("objet"); q.pop("action", None)
        if q.get("action") == "telephone_oreille" and q.get("objet") not in (None, "telephone"): q["action"] = "tenir"
    retires = set(F.get("_retires") or [])                                 # objets retirés par la 2e IA : jamais remis par les règles
    for o in ind.get("objets") or []:                                      # objet cité : dans les mains de celui qui en parle
        if o["n"] in retires: continue
        q = F["repliques"].setdefault(o["n"], {})
        if not q.get("objet") and not (o["objet"] == "telephone" and not re.search(r"t[ée]l[ée]phone|portable|appel|allô|allo|message|snap|texto",
                                                                                     str(reps[o["n"]].get("t") or "").lower())):
            q["objet"] = o["objet"]; q.setdefault("action", "telephone_oreille" if o["objet"] == "telephone" and re.search(r"allô|allo|je t'appelle|appel", t) else "tenir")
            q["mot_objet"] = o["mot"]; fixe(f"réplique {o['n']} objet", "", o["objet"], f"« {o['mot']} » est dit")
    if F.get("ecran_tel") and not any(q.get("objet") == "telephone" for q in F["repliques"].values()):
        F["ecran_tel"] = ""
    if F.get("panneaux") and F["lieu"] not in LIEUX_PUBLICS: fixe("panneaux", ", ".join(F["panneaux"]), "", f"pas d'enseigne dans « {F['lieu']} »"); F["panneaux"] = []
    roles = set(F["personnages"])
    F["reactions"] = [x for x in F["reactions"] if x["qui"] in roles and x["n"] < len(reps) and reps[x["n"]].get("p") != x["qui"]]
    for x in F["reactions"]:
        if x.get("mot") and _nu(x["mot"]) not in _nu(reps[x["n"]].get("t")): x["mot"] = ""
    return cor


# ------------------------------------------------------------------ contrôle 2 : une 2e IA relit la fiche contre le dialogue
CHAMPS_AUTORISES = re.compile(r"^(lieu|moment|meteo|ambiance|niveau|occasion|interieur|personnages\.\w+\.(genre|age|tenue|barbe|etat_tenue|metier|lunettes)|"
                              r"repliques\.\d+\.(emotion|intensite|geste|objet|action|signe))$")


def controle_ia(F, sk, exclure=()):
    """Une IA d'un autre fournisseur relit la fiche contre le dialogue : [{champ, valeur, raison}] appliquées si autorisées."""
    import ecrire, reseau
    if not reseau.ia_disponible() or os.environ.get("FICHE_2E_AVIS", "1") == "0": return []
    lignes = "\n".join(f"{i}. [{r.get('p')}] {str(r.get('t') or '')[:160]}" for i, r in enumerate(sk.get("repliques") or []))
    resume = json.dumps({k: F[k] for k in ("lieu", "lieu_precis", "moment", "meteo", "ambiance", "niveau", "occasion", "personnages", "repliques")},
                        ensure_ascii=False, default=str)[:7000]
    txt = (f"Voici le dialogue d'un son TikTok :\n{lignes}\n\nEt la fiche de tournage préparée pour le dessiner :\n{resume}\n\n"
           "Relis la fiche contre le dialogue. Liste UNIQUEMENT les incohérences sûres (un lieu, une heure, une météo, une tenue, un âge, "
           "un genre, un objet, une émotion qui contredit ce qui est dit). Pour chacune : \"champ\" (chemin, ex. moment, "
           "personnages.invite.tenue, repliques.3.emotion), \"valeur\" (la bonne valeur, mêmes mots que la fiche) et \"raison\". "
           "Liste vide si tout est cohérent.")
    outil = {"name": "corrections", "description": "Les corrections sûres de la fiche.",
             "input_schema": ecrire._schema({"corrections": {"type": "array", "items": ecrire._schema(
                 {"champ": {"type": "string"}, "valeur": {}, "raison": {"type": "string"}}, ["champ", "valeur"])}}, ["corrections"])}
    try: r = ecrire._appel(reseau.claude(raisonner=True, exclure=exclure), None, [{"role": "user", "content": txt}], outil, max_tokens=2500)
    except Exception as e:
        journal(f"  fiche de tournage : 2e avis impossible ({str(e)[:100]})"); return None
    out = []
    for c in ecrire._liste(r.get("corrections")):
        try:
            ch = str(c.get("champ") or "").strip()
            if CHAMPS_AUTORISES.match(ch): out.append({"champ": ch, "valeur": c.get("valeur"), "raison": str(c.get("raison") or "")[:120]})
        except AttributeError: pass
    return out


def appliquer_corrections(F, sk, corrections):
    """Applique les corrections de la 2e IA en repassant par la remise en forme (une valeur interdite est ignorée)."""
    faites = []
    for c in corrections or []:
        if c.get("champ") in ("lieu", "lieu_precis") and F.get("_lieu_dit"): continue   # lieu écrit sur la vidéo : jamais changé
        brut = json.loads(json.dumps(F, default=list))
        brut["personnages"] = {r: dict(p) for r, p in F["personnages"].items()}
        brut["repliques"] = [dict(q, n=n) for n, q in F["repliques"].items()]
        parties = c["champ"].split(".")
        if parties[0] == "personnages":
            brut["personnages"].setdefault(parties[1], {})[parties[2]] = c["valeur"]
        elif parties[0] == "repliques":
            n = int(parties[1]); q = next((x for x in brut["repliques"] if x["n"] == n), None)
            if q is None: q = {"n": n}; brut["repliques"].append(q)
            q[parties[2]] = c["valeur"]
        else: brut[parties[0]] = c["valeur"]
        G = nettoyer(brut, sk)
        avant = _lire(F, parties); apres = _lire(G, parties)
        if apres in (None, "", []) and c["valeur"] not in (None, "", [], False): continue   # valeur refusée par la remise en forme
        if avant != apres:
            prives = {k: v for k, v in F.items() if k.startswith("_")}
            if parties[0] == "repliques" and parties[2] == "objet" and apres in (None, ""):
                prives["_retires"] = sorted(set(prives.get("_retires") or []) | {int(parties[1])})
            G["source"] = F.get("source"); F.clear(); F.update(G); F.update(prives); faites.append(f"{c['champ']} : {avant} -> {apres} ({c['raison']})")
    return faites


def _lire(F, parties):
    try:
        if parties[0] == "personnages": return F["personnages"].get(parties[1], {}).get(parties[2])
        if parties[0] == "repliques": return F["repliques"].get(int(parties[1]), {}).get(parties[2])
        return F.get(parties[0])
    except (KeyError, ValueError, AttributeError): return None


# ------------------------------------------------------------------ contrôle 3 : ce que l'image de l'original a montré
def controle_image(F, sk):
    """Fiche comparée à ce qui a été VU dans l'original (analyse Gemini de la vidéo, personnes vues, lumière de l'image)."""
    cor = []
    V = ((sk.get("doublage") or {}).get("visuel")) or {}
    import decor_dessin as DD
    l_vu = ((sk.get("doublage") or {}).get("lieu_ia") or None)            # ce que Gemini a vu dans CET original (pas le dernier son écouté)
    l_vu = l_vu if l_vu in DD.LIEUX else None
    if l_vu and F.get("lieu") != l_vu and F.get("source") != "video" and not F.get("_lieu_dit"):
        cor.append(f"lieu : {F.get('lieu')} -> {l_vu} (vu dans la vidéo d'origine)"); F["lieu"] = l_vu
    if V.get("moment") in ("matin", "jour", "soir", "nuit") and F.get("source") != "video" and F.get("moment") != V["moment"] and not F.get("_moment_dit"):
        cor.append(f"moment : {F.get('moment')} -> {V['moment']} (lumière de la vidéo d'origine)"); F["moment"] = V["moment"]
    S = sk.get("studio") if isinstance(sk.get("studio"), dict) else {}
    P = S.get("personnages") if isinstance(S.get("personnages"), dict) else {}
    import studio as _ST
    acteur = _ST.un_acteur(sk)
    for r, p in F["personnages"].items():
        g_vu = str((P.get(r) or {}).get("genre_vu") or "").lower()[:1]
        g_txt, force = _ST.genre_texte(sk, r)
        if g_txt and p.get("genre") == g_txt and (acteur or force >= 4): continue   # rôle joué par un acteur de l'autre sexe
        if g_vu in ("h", "f") and p.get("genre") and p["genre"] != g_vu:   # (audit du 23 nov. : « les meufs… » repassées en garçons)
            cor.append(f"{r} genre : {p['genre']} -> {g_vu} (vu dans la vidéo d'origine)"); p["genre"] = g_vu
    return cor


# ------------------------------------------------------------------ la fiche complète
def faire(sk, video="", sig=None, sr=22050, mots=None, B=None):
    """Fiche de tournage contrôlée trois fois (sk["_fiche"]). B : bulletin de l'équipe (equipe.Bulletin) ou None."""
    if not actif() or not sk.get("repliques"): return None
    import decor_dessin as DD
    reps = sk["repliques"]
    ind = indices_texte(reps)
    son = indices_son((sk.get("doublage") or {}).get("evenements") or [], None)
    if son["meteo"]: ind["meteo_son"] = son["meteo"]; ind["meteo"] = ind.get("meteo") or son["meteo"]
    ind["details"] = list(dict.fromkeys((ind.get("details") or []) + son["details"]))
    ec = echo(sig, sr, mots) if sig is not None else None
    if ec == "carrelage": ind["details"].append("tiled walls")
    texte = _consigne(sk, DD.LIEUX)
    brut = _gemini_video(video, texte)
    source = "video" if brut else None
    if brut is None:
        brut = _ia_texte(texte); source = "ia" if brut else "regles"
    brut = dict(brut or {}); brut["source"] = source
    F = nettoyer(brut, sk)
    F["animations"] = list(dict.fromkeys(F["animations"] + son["animations"]))
    F["_moment_dit"] = "moment" in ind.get("explicite", set())
    if source != "video" and F.get("lieu") and F.get("lieu") != "salon":
        # Lieu proposé par une IA qui n'a PAS regardé l'original (audit du 24 novembre : « l'été est passé » mis dans un aéroport,
        # le créateur est chez lui) : gardé seulement si les paroles ou le titre en parlent ; sinon le lieu des mots, ou le salon.
        d_ = sk.get("doublage") if isinstance(sk.get("doublage"), dict) else {}
        txt_ = " ".join(str(r.get("t") or "") for r in reps) + " " + str(d_.get("legende_ecran") or "") + " " + str(d_.get("titre") or "")
        sc_, _r = DD.scores_lieux(txt_.lower())
        if not sc_.get(F["lieu"]):
            nouveau = DD.lieu_de(txt_.lower(), None) or "salon"
            journal(f"  fiche de tournage : lieu {F['lieu']} imaginé par l'IA (rien ne le dit) -> {nouveau}")
            F["lieu"] = nouveau; F.pop("lieu_precis", None)
    if source != "video" and F.get("panneaux"):                           # panneaux d'une IA qui n'a pas vu l'original : seulement si le
        dial_ = " ".join(str(r.get("t") or "") for r in reps).lower()    # dialogue en parle (« DEPARTURES - GATE A15 » inventé, 24 nov.)
        F["panneaux"] = [p_ for p_ in F["panneaux"] if any(w in dial_ for w in re.findall(r"[^\W\d_]{4,}", str(p_).lower()))]
    l_ecrit = lieu_ecrit(sk)
    if l_ecrit and l_ecrit in DD.LIEUX:
        if F.get("lieu") != l_ecrit: journal(f"  fiche de tournage : lieu {F.get('lieu')} -> {l_ecrit} (écrit sur la vidéo d'origine)")
        F["lieu"] = l_ecrit; F["_lieu_dit"] = True
    journal(f"  fiche de tournage écrite ({ {'video': 'Gemini a regardé et écouté l original', 'ia': 'IA de texte sur le dialogue', 'regles': 'règles seules'}[source] }) : "
            f"{F['lieu']} ({F['lieu_precis'][:50]}), {F['moment']}, {F['meteo'] or 'temps normal'}, ambiance {F['ambiance'] or '?'}, niveau {F['niveau'] or '?'}"
            + (f", bruits entendus : {', '.join(son['entendus'])}" if son["entendus"] else ""))
    def note(controle, cor, ok=True):
        if B is not None: B.note("fiche de tournage", controle, ok, ("; ".join(cor)[:190] + " (corrigé)") if cor else "")
        for c in cor[:12]: journal(f"    correction : {c}")
    c1 = controle_regles(F, sk, ind)
    note("contrôle 1 : règles (cohérence avec ce qui est dit)", c1)
    c2 = controle_ia(F, sk, exclure=("gemini",) if source == "video" else ())
    if c2 is None: note("contrôle 2 : 2e IA (autre fournisseur)", ["IA indisponible"], ok=True)
    else:
        faites = appliquer_corrections(F, sk, c2)
        note("contrôle 2 : 2e IA (autre fournisseur)", faites)
    c3 = controle_image(F, sk)
    c3 += controle_regles(F, sk, ind)                                      # dernière passe des règles après les deux autres contrôles
    note("contrôle 3 : image de l'original, puis règles", c3)
    F.pop("_moment_dit", None)
    F["controles"] = len(c1) + len(c2 or []) + len(c3)
    sk["_fiche"] = F
    return F


# ------------------------------------------------------------------ la fiche appliquée au studio (studio.bible, cartoon)
TENUE_STUDIO = {"pyjama": ("pyjama", (150, 180, 230), "pantalon", (150, 180, 230), "pyjama", ()),
                "peignoir": ("robe", (250, 250, 250), "pantalon", (250, 250, 250), "peignoir", ("ceinture",)),
                "maillot_bain": ("debardeur", (240, 90, 120), "short", (60, 140, 220), "maillot_bain", ()),
                "doudoune": ("doudoune", (220, 60, 60), "pantalon", (40, 50, 70), "doudoune", ("echarpe", "gants")),
                "impermeable": ("blouson", (250, 210, 50), "pantalon", (60, 70, 90), "impermeable", ()),
                "survetement": ("survetement", (60, 80, 160), "pantalon", (60, 80, 160), "survetement", ("bandes",)),
                "gilet_jaune": ("tshirt", (250, 220, 40), "jean", (60, 70, 90), "gilet_jaune", ("bandes",)),
                "uniforme": ("polo", (250, 250, 250), "pantalon", (40, 50, 90), "uniforme", ("cravate",)),
                "costume": ("costume", (30, 30, 36), "pantalon", (30, 30, 36), "costume", ("cravate",)),
                "robe_soiree": ("robe", (170, 30, 70), "pantalon", (170, 30, 70), "robe_soiree", ()),
                "robe_mariee": ("robe", (252, 252, 250), "pantalon", (252, 252, 250), "robe_mariee", ()),
                "tablier": ("tablier", (240, 240, 240), "pantalon", (60, 70, 90), "", ())}
LUMIERE_AMBIANCE = {"dispute": "cold contrasted light", "romance": "warm soft golden light", "peur": "dim moody shadows",
                    "joie": "bright cheerful light", "tristesse": "pale grey light", "gene": "flat neutral light", "suspense": "low dramatic light",
                    "fete": "colorful party lights", "calme": "soft natural light"}
NIVEAU_EN = {"modeste": "small modest", "desordre": "very messy cluttered", "aise": "comfortable well furnished", "luxe": "luxurious elegant",
             "moyen": ""}


def _lieu_en(lieu):
    """Description anglaise de base d'un lieu du catalogue (studio.DECOR_EN, semi_realiste.LIEUX_EN) ou ""."""
    if not lieu: return ""
    try:
        import studio, semi_realiste
        return str((getattr(studio, "DECOR_EN", {}) or {}).get(lieu) or semi_realiste.LIEUX_EN.get(lieu) or "")
    except Exception: return ""


def lieu_ecrit(sk):
    """Lieu ÉCRIT par le créateur sur la vidéo ou dans son titre (« Pov: t'es au bureau et GTA 6 sort demain ») : il passe avant ce
    que les IA devinent (audit du 23 novembre 2026 : bureau dessiné en chambre). None si rien de net."""
    d = sk.get("doublage") if isinstance(sk.get("doublage"), dict) else {}
    t = f"{d.get('legende_ecran') or ''} {d.get('titre') or ''}"
    if not t.strip(): return None
    import decor_dessin as DD
    scores, regles = DD.scores_lieux(t)
    bons = sorted((r[0] for r in regles if scores[r[0]]), key=lambda l: -scores[l])
    if not bons or (len(bons) > 1 and scores[bons[0]] == scores[bons[1]]): return None
    return bons[0]


def decor_compose(F, lieu_en=""):
    """Description anglaise du décor pour l'IA des peintures (idées 5 et 6) : lieu exact, niveau de vie, 3 détails de l'histoire, lumière."""
    import decor_dessin as DD
    lieu = F.get("lieu")
    def _autre_lieu(txt):                                                  # le texte décrit-il un AUTRE lieu que celui de la fiche ?
        l_ = DD.lieu_de(str(txt or ""), None)
        return bool(lieu and l_ and l_ != lieu)
    # (audit du 23 novembre : fiche « bureau » mais lieu exact « small cluttered bedroom with a messy bed » : une chambre a été peinte)
    precis = F.get("lieu_precis") if not _autre_lieu(F.get("lieu_precis")) else ""
    base = precis or lieu_en or _lieu_en(lieu) or (lieu or "living room").replace("_", " ")
    niv = NIVEAU_EN.get(F.get("niveau") or "", "")
    if niv and not any(w in base.lower() for w in niv.split()): base = f"{niv} {base}"
    dets = [d for d in F.get("details") or [] if d.lower() not in base.lower() and not _autre_lieu(d)
            and not (lieu not in ("chambre", "hopital") and re.search(r"\b(bed|pillow|nightstand|duvet)\b", str(d).lower()))][:3]
    return base + (" with " + ", ".join(dets) if dets else "")


def lumiere(F):
    """Lumière d'après l'ambiance (idée 7), accordée au moment : jamais de nuit si on dit qu'il fait jour."""
    l_ = F.get("lumiere") or LUMIERE_AMBIANCE.get(F.get("ambiance") or "", "")
    if F.get("moment") in ("matin", "jour") and re.search(r"\b(night|dark|moon)\b", l_.lower()): l_ = LUMIERE_AMBIANCE.get(F.get("ambiance") or "", "soft natural light")
    if F.get("meteo") in ("pluie", "orage") and "rain" not in l_.lower(): l_ = (l_ + ", rainy weather outside").strip(", ")
    return l_


def appliquer(sk, F=None):
    """Fiche -> sk["studio"] (ce que studio.bible et cartoon lisent) et découpage (décor). Ce que l'auteur a choisi (🎭 Changer les
    personnages, « Dis ce qui ne va pas ») reste prioritaire : il passe après, dans studio.bible et remarque.py."""
    F = F or sk.get("_fiche")
    if not isinstance(F, dict) or not actif(): return 0
    S = sk["studio"] if isinstance(sk.get("studio"), dict) else {}
    sk["studio"] = S
    vu = F.get("source") == "video"                                         # Gemini a vu et entendu : il passe devant l'IA de mise en scène
    S["moment"] = F.get("moment") or S.get("moment")
    dec = sk.get("decoupage") or []
    if F.get("lieu") and not S.get("lieux_separes"):
        if vu or not S.get("lieux"): S["lieux"] = [F["lieu"]] * max(1, len(dec))
    P = S.setdefault("personnages", {}) if isinstance(S.get("personnages", {}), dict) else {}
    for r, p in F["personnages"].items():
        d = P.setdefault(r, {})
        def mettre(k, v):
            if v is not None and (vu or k not in d): d[k] = v
        if p.get("genre"): d.setdefault("genre", {"h": "homme", "f": "femme"}[p["genre"]])
        mettre("age", p.get("age")); mettre("corpulence", CORPULENCES.get(p.get("corpulence") or ""))
        mettre("taille", TAILLES.get(p.get("taille") or ""))
        if p.get("cheveux") and not ((p.get("genre") or d.get("genre_vu") or "")[:1] == "h" and p["cheveux"] in ("long", "carre", "chignon", "queue", "tresses", "mi_long")) \
                and not ((p.get("genre") or "")[:1] == "f" and p["cheveux"] in ("chauve", "rase", "herisse")):
            mettre("cheveux", CHEVEUX[p["cheveux"]])                       # (jamais une coupe de fille sur un homme : audit du 20 novembre)
        if p.get("barbe"): mettre("barbe", p["barbe"])                     # « aucune » : hors des barbes connues, le casting n'en met pas
    tenues = S.setdefault("tenues_fiche", {})
    for r, p in F["personnages"].items():
        x = {k: p[k] for k in ("tenue", "haut", "c_haut", "c_cheveux", "lunettes") if p.get(k) not in (None, "")}
        x["etats"] = list(p.get("etat_tenue") or [])
        tenues[r] = x
        if p.get("metier"):
            if not isinstance(S.get("metiers"), dict): S["metiers"] = {}
            S["metiers"].setdefault(r, p["metier"])
    jeu = [x for x in (S.get("jeu") or []) if isinstance(x, dict)] if isinstance(S.get("jeu"), list) else []
    deja = set()
    for x in jeu:
        try: deja.add(int(x.get("replique")))
        except (TypeError, ValueError): pass
    reps = sk.get("repliques") or []
    for n, q in F["repliques"].items():
        if n >= len(reps): continue
        if q.get("emotion") and n not in deja: jeu.append({"replique": n, "emotion": q["emotion"], "intensite": q.get("intensite", 2), "geste": q.get("geste", "")})
        r = reps[n]
        if q.get("objet") and not r.get("objet"): r["objet"] = q["objet"]
        for k in ("action", "signe", "cible", "mot_objet"):
            if q.get(k): r["_" + k] = q[k]
        if q.get("geste") and not r.get("_geste"): r["_geste"] = q["geste"]
    S["jeu"] = jeu
    S["reactions"] = F.get("reactions") or []
    amb = set(a for a in (S.get("ambiances") or []) if isinstance(a, str))
    if F.get("meteo") in ("pluie", "orage", "neige"): amb.add(F["meteo"] if F["meteo"] != "orage" else "orage")
    if F.get("meteo") == "orage": amb.add("pluie")
    S["ambiances"] = sorted(amb)
    S["animations"] = list(F.get("animations") or [])
    S["panneaux"] = list(F.get("panneaux") or [])
    S["ecran_tel"] = F.get("ecran_tel") or ""
    S["lumiere_ambiance"] = lumiere(F)
    S["interieur"] = bool(F.get("interieur", True))
    if not S.get("lieux_separes") and not sk.get("_separes"):              # idée 6 : le décor raconte l'histoire
        compo = decor_compose(F)
        for sc in dec:
            if compo: sc["decor"] = compo
    S["decor_fiche"] = {k: F.get(k) for k in ("lieu", "lieu_precis", "details", "niveau", "ambiance", "occasion", "meteo", "moment", "interieur")}
    return 1


def resume(F):
    """Résumé court de la fiche (choix du décor par Gemini, contrôle final)."""
    if not isinstance(F, dict): return ""
    pers = "; ".join(f"{r} : {p.get('genre', '?')}, {p.get('age', '?')} ans, tenue {p.get('tenue', 'normale')}" + (f" ({', '.join(p['etat_tenue'])})" if p.get("etat_tenue") else "")
                     for r, p in (F.get("personnages") or {}).items())
    objs = ", ".join(sorted({q["objet"] for q in (F.get("repliques") or {}).values() if q.get("objet")}))
    return (f"Lieu : {F.get('lieu')} ({F.get('lieu_precis')}) ; moment : {F.get('moment')} ; météo : {F.get('meteo') or 'normale'} ; "
            f"ambiance : {F.get('ambiance')} ; détails : {', '.join(F.get('details') or [])} ; personnages : {pers} ; objets : {objs or 'aucun'}")


# ------------------------------------------------------------------ idées 9 et 11 : Gemini juge les décors peints
def _gemini_images(images, texte, timeout=120):
    """Question à Gemini avec des images (tableaux RGB) ; réponse JSON (dict) ou None."""
    cle = os.environ.get("GEMINI_API_KEY")
    if not cle or os.environ.get("DECOR_GEMINI", "1") == "0": return None
    import cv2, reseau, video_ia
    if "gemini" in reseau.HORS_SERVICE: return None
    parts = []
    for im in images:
        ok, jpg = cv2.imencode(".jpg", cv2.cvtColor(cv2.resize(im, (432, 768), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 82])
        if ok: parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpg.tobytes()).decode()}})
    parts.append({"text": texte})
    corps = {"contents": [{"parts": parts}], "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"}}
    return video_ia.generer(corps, timeout=timeout, tours=2, quoi="images")


def _boite(b, W=1080, H=1920):
    """[y0, x0, y1, x1] sur 0-1000 (format de Gemini) -> [x0, y0, x1, y1] en pixels, ou None."""
    try:
        y0, x0, y1, x1 = [float(v) for v in b][:4]
        if not (0 <= x0 < x1 <= 1000 and 0 <= y0 < y1 <= 1000) or (x1 - x0) * (y1 - y0) < 400: return None
        return [int(x0 * W / 1000), int(y0 * H / 1000), int(x1 * W / 1000), int(y1 * H / 1000)]
    except (TypeError, ValueError): return None


def choisir_decor(images, F):
    """Idée 9 : parmi les tirages déjà bien cadrés, celui qui colle le mieux à la fiche ; un tirage avec du texte absurde ou une
    personne peinte est refusé. Renvoie (indice ou None, zones du décor choisi : fenêtre et télé, pour la pluie et la lueur)."""
    if not images: return None, {}
    txt = (f"Voici {len(images)} décors peints (numérotés à partir de 0) pour cette scène : {resume(F)}.\n"
           "Choisis celui qui colle le mieux à l'histoire et à l'ambiance. Refuse un décor qui contient une personne, un visage ou du "
           "texte illisible. Donne aussi, dans le décor choisi, la boîte de la fenêtre, de la télévision et d'un panneau / tableau / "
           "enseigne VIDE où l'on pourrait écrire, s'il y en a, au format [y0, x0, y1, x1] sur 0-1000. JSON : {\"choix\": n ou -1 si "
           "aucun ne va, \"refuses\": [n…], \"fenetre\": [..] ou [], \"tele\": [..] ou [], \"panneau\": [..] ou []}")
    r = _gemini_images(images, txt)
    if not isinstance(r, dict): return None, {}
    try: ch = int(r.get("choix"))
    except (TypeError, ValueError): ch = None
    if ch is not None and not 0 <= ch < len(images): ch = None
    zo = {k: _boite(r.get(k)) for k in ("fenetre", "tele", "panneau")}
    return ch, {k: v for k, v in zo.items() if v}


def decor_convient(image, F):
    """Idée 11 : un décor de la banque n'est repris que s'il colle à la fiche (True / False ; None si Gemini ne répond pas)."""
    r = _gemini_images([image], f"Ce décor convient-il à cette scène : {resume(F)} ? Il doit montrer le bon lieu, le bon moment de la journée "
                                "et l'ambiance ; les détails manquants sont permis. JSON : {\"convient\": true/false, \"raison\": \"...\"}", timeout=60)
    if isinstance(r, dict) and isinstance(r.get("convient"), bool): return r["convient"]
    return None


# ------------------------------------------------------------------ idée 25 : la vidéo FINIE est-elle fidèle à l'audio ?
def fidelite(video, sk, R=None):
    """Gemini regarde ET écoute notre vidéo finie et la compare à la fiche et au dialogue : ce qui ne colle pas (objet cité absent,
    tenue hors sujet, expression contraire à la voix, décor de jour pour une scène de nuit…). Renvoie [{t, probleme, champ, valeur}]
    (champ / valeur : correction automatique de la fiche quand c'est possible), ou None si Gemini n'a pas pu regarder. FIDELITE=0."""
    if os.environ.get("FIDELITE", "1") == "0" or not actif() or not video or not os.path.exists(video): return None
    F = sk.get("_fiche")
    if not isinstance(F, dict): return None
    lignes = "\n".join(f"{i}. [{r.get('p')}] {str(r.get('t') or '')[:140]}" for i, r in enumerate(sk.get("repliques") or []))
    txt = (f"Voici NOTRE petit dessin animé (style croquis voulu : grosses têtes, personnages simples, animaux qui parlent voulus) fait "
           f"sur un son TikTok. Dialogue :\n{lignes}\n\nFiche de tournage prévue : {resume(F)}\n\n"
           "Regarde ET écoute la vidéo. Liste UNIQUEMENT ce qui contredit vraiment l'audio ou la fiche : un objet dont on parle et qu'on "
           "ne voit pas, une tenue hors sujet, une expression contraire au ton de la voix, un lieu ou un moment de la journée faux, "
           "la météo. PAS de remarque sur les sous-titres, le style du dessin, les plans ou la caméra. Pour chaque problème : \"t\" "
           "(secondes), \"probleme\" (en français, court), et si possible la correction de la fiche : \"champ\" (lieu, moment, "
           "meteo, personnages.<identifiant>.tenue, repliques.<n>.objet, repliques.<n>.emotion…) et \"valeur\". "
           "JSON : {\"problemes\": [...]} (liste vide si tout colle).")
    brut = _gemini_brut(video, txt)
    if not isinstance(brut, dict): return None
    out = []
    for x in brut.get("problemes") or []:
        if not isinstance(x, dict) or not str(x.get("probleme") or "").strip(): continue
        pb = str(x["probleme"]).strip()[:170]
        if re.search(r"sous-titre|caméra|plan |style|croquis|dessin simple", pb, re.I): continue
        ch = str(x.get("champ") or "").strip()
        try: t = float(x.get("t"))
        except (TypeError, ValueError): t = None
        out.append({"t": t, "probleme": pb, "champ": ch if CHAMPS_AUTORISES.match(ch) else "", "valeur": x.get("valeur")})
    return out[:8]


def _gemini_brut(video, texte):
    """Comme _gemini_video, mais la réponse peut ne pas avoir de « lieu » (contrôle final)."""
    cle = os.environ.get("GEMINI_API_KEY")
    if not cle: return None
    import reseau, video_ia
    if "gemini" in reseau.HORS_SERVICE: return None
    v = video_ia._petite(video)
    if not v: return None
    corps = {"contents": [{"parts": [{"inline_data": {"mime_type": "video/mp4", "data": base64.b64encode(open(v, "rb").read()).decode()}}, {"text": texte}]}],
             "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"}}
    return video_ia.generer(corps, timeout=120, tours=3, max_modeles=2, quoi="contrôle « fidélité »")   # (2 modèles, 3 tours patients)


DECOR_CHAMPS = re.compile(r"^(lieu|moment|meteo|ambiance|niveau|occasion|interieur)$")


def corriger_depuis_points(sk, points):
    """Compte rendu (principal.corriger_compte_rendu) : les corrections de la fiche portées par les points « fidélité à l'audio »
    sont appliquées à la fiche puis au studio ; un changement de lieu / moment / météo fait repeindre le décor. Renvoie ce qui a été fait."""
    F = sk.get("_fiche")
    if not isinstance(F, dict): return []
    cor = [c for p in points or [] for c in (p.get("correction") or []) if isinstance(c, dict) and CHAMPS_AUTORISES.match(str(c.get("champ") or ""))]
    ind = indices_texte(sk.get("repliques") or [])
    son = indices_son((sk.get("doublage") or {}).get("evenements") or [])
    if not (ind.get("meteo") or son.get("meteo")):                         # la météo ne vient que du son ou des paroles (audit du 20 novembre :
        cor = [c for c in cor if c.get("champ") != "meteo" or not c.get("valeur")]   # Gemini voyait « de la pluie » dans notre peinture)
    # Homme / femme : jamais changé par ce contrôle (audit du 23 novembre : « dessiné en femme alors que la fiche dit homme » faisait
    # passer la FICHE en femme, puis le tour suivant « barbu alors que la fiche dit femme » la repassait en homme : la vidéo empirait).
    # Le genre se décide par la voix, les mots et ce qui a été vu dans l'original (studio.genre_voix), pas par notre dessin.
    cor = [c for c in cor if not str(c.get("champ") or "").endswith(".genre")]
    if not cor: return []
    faites = appliquer_corrections(F, sk, [dict(c, raison=c.get("raison") or "contrôle final : pas fidèle à l'audio") for c in cor])
    if not faites: return []
    controle_regles(F, sk, ind)                                            # la correction ne doit pas casser la cohérence
    appliquer(sk, F)
    if any(DECOR_CHAMPS.match(f.split(" :")[0]) for f in faites):
        sk["_decors_a_refaire"] = sorted(set(sk.get("_decors_a_refaire") or []) | set(range(len(sk.get("decoupage") or []))))
    return ["fiche de tournage : " + f for f in faites]
