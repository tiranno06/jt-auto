"""Catalogue des bruitages « tendance » des vidéos d'humour TikTok (recherche d'octobre 2026) et règles de placement.

Les sons à la mode sur TikTok sont souvent des extraits protégés (dessins animés, films, voix de mèmes) : on ne les copie pas.
On fabrique NOS PROPRES versions du même type de son, libres de droits :
- mode payant : ElevenLabs (Sound Effects) les fabrique UNE fois (workflow « Fabriquer les bruitages »), rangés dans sons_eleven/ ;
- mode gratuit (ou pas encore fabriqués) : synthèse sonore (moteur/sons_modernes.py).
Jamais de rires enregistrés (consigne de l'auteur).

Placement : sur la chute (vanne), un mot qui s'y prête (argent, photo, mot de passe, bug, raté…), une émotion (gêne, tristesse,
panique, choc) ou un blanc gênant ; un bruitage par réplique au plus, jamais deux fois le même d'affilée, dosé selon la durée.
En mode payant, Claude peut choisir lui-même (« studio » → "bruitages" : [{"replique": n, "son": nom}])."""
import re

# nom : (ce que c'est, en français ; consigne ElevenLabs en anglais ; durée en secondes)
CATALOGUE = {
    "vine_boom":     ("boom grave de révélation façon « vine boom » (le classique des chutes)",
                      "short deep punchy meme reveal boom, bass thump with a slight metallic ring, dramatic comedic emphasis, no music", 1.2),
    "dun_dun":       ("« dun dun duuun » : trois notes dramatiques façon téléréalité (révélation, choc)",
                      "dramatic comedic orchestral sting, three brass hits dun dun duuun, reality TV reveal, short", 2.2),
    "klaxon_clown":  ("klaxon de clown (moquerie, celui qui se ridiculise)",
                      "two quick honks of a clown bicycle horn, comedic, circus, dry", 1.0),
    "sifflet_chute": ("sifflet qui descend (échec, plan raté, quelqu'un qui « tombe de haut »)",
                      "cartoon slide whistle going down, comedic failure, short", 1.0),
    "boing":         ("boing de dessin animé (rebond, saut, idée absurde)",
                      "cartoon boing spring sound, jaw harp twang, bouncy, short", 0.8),
    "violon_triste": ("petit violon triste (fausse tristesse, apitoiement)",
                      "short melancholic solo violin phrase, mock sad comedic tiny violin, four slow descending notes", 2.6),
    "criquets":      ("criquets dans le silence (blanc gênant, vanne qui tombe à plat)",
                      "crickets chirping in an awkward silence, quiet night, comedic", 2.4),
    "os_craque":     ("craquement d'os (malaise, silence gênant)",
                      "short bone crack sound, comedic awkward moment, dry, close", 0.6),
    "scie_wobble":   ("scie musicale qui ondule (gêne, embarras)",
                      "cartoon saw wobble sound, wobbly embarrassed musical saw, short", 1.2),
    "dents":         ("claquement de dents (peur, panique)",
                      "cartoon teeth chattering from fear, fast rattling, short", 1.0),
    "bouilloire":    ("sifflement de bouilloire qui monte (stress, colère qui monte)",
                      "tea kettle whistle rising in pitch and volume, building anxiety, comedic, short", 1.6),
    "caisse":        ("« ka-ching » de caisse enregistreuse (argent, prix, facture)",
                      "cash register ka-ching, coins and bell, short and bright", 1.0),
    "flash":         ("déclencheur et flash d'appareil photo (photo, selfie, preuve)",
                      "camera shutter click with flash charge whine, short", 0.7),
    "clavier":       ("frappe rapide au clavier (ordinateur, mot de passe, message)",
                      "fast typing on a computer keyboard, a few seconds, close mic", 1.4),
    "glitch":        ("bug numérique (beug, réseau, appli qui plante)",
                      "short digital glitch stutter sound, data corruption, modern edit", 0.6),
    "bulle":         ("bulle qui éclate (petite vanne, détail ridicule)",
                      "single bubble pop, cute, crisp, short", 0.4),
}

# déclencheurs par mots (la réplique contient…) : (expression, bruitage, au moment du mot)
MOTS = [
    (r"\b(euros?|balles|argent|pay[ée]?r?|rembours\w*|prix|cher|ch[èe]re|fric|thunes?|salaire|facture|cr[ée]dit|banque)\b|€", "caisse"),
    (r"\b(photos?|selfies?|flash|film[ée]|story|preuves?)\b", "flash"),
    (r"\b(mot de passe|ordi\w*|clavier|mails?|tap[ée]r?|code|connexion|compte)\b", "clavier"),
    (r"\b(bug\w*|beug\w*|bloqu\w*|plant[ée]\w*|erreur|wifi|r[ée]seau|appli)\b", "glitch"),
    (r"\b(rat[ée]\w*|perdu|tomb\w*|[ée]chou\w*|foir[ée]\w*|vir[ée]\w*|recal[ée]\w*)\b", "sifflet_chute"),
    (r"\b(saut\w*|rebond\w*|danse\w*|boing)\b", "boing"),
]
# selon l'émotion de la réplique
EMOTIONS = {"gene": ("scie_wobble", "os_craque"), "triste": ("violon_triste",), "pleurs": ("violon_triste",),
            "panique": ("dents", "bouilloire"), "colere": ("bouilloire",), "choc": ("dun_dun", "vine_boom")}
CHUTES = ("vine_boom", "dun_dun", "klaxon_clown", "bulle", "sifflet_chute")      # vanne en cours de sketch (variée d'une vidéo à l'autre)
SILENCE = ("criquets", "os_craque")                                              # blanc gênant
GAIN = {"vine_boom": 0.75, "dun_dun": 0.6, "klaxon_clown": 0.55, "sifflet_chute": 0.5, "boing": 0.5, "violon_triste": 0.45,
        "criquets": 0.45, "os_craque": 0.6, "scie_wobble": 0.45, "dents": 0.45, "bouilloire": 0.35, "caisse": 0.55, "flash": 0.55,
        "clavier": 0.35, "glitch": 0.45, "bulle": 0.5}


def _instant(q, debut_mot):
    """Instant (s) du groupe de sous-titres qui contient le mot, sinon fin de la réplique."""
    texte = q.get("texte") or ""
    if debut_mot is not None and q.get("groupes"):
        n = len(texte[:debut_mot].split())
        compte = 0
        for g in q["groupes"]:
            compte += len(str(g[0]).split())
            if compte > n: return float(g[1])
    return float(q["fin"])


def densite_apprise():
    """Bruitages toutes les 10 s dans les vidéos TikTok déjà analysées (banque, pondérée par les vues), sinon None."""
    try:
        import banque_visuelle
        d = (banque_visuelle.tendances().get("audio") or {}).get("impacts_10s")
        return float(d) if d else None
    except Exception: return None


def choisir(ph, silences=(), graine=0, imposes=None, duree=None, densite=None):
    """Liste de (nom, instant, gain) pour la vidéo. ph : répliques minutées (texte, emo, chute, deb, fin, groupes).
    imposes : {indice de réplique: nom} choisis par Claude (mode payant)."""
    imposes = {int(k): v for k, v in (imposes or {}).items() if v in CATALOGUE}
    duree = duree or (max((q["fin"] for q in ph), default=0) + 1)
    par_10s = 3.1 if densite is None else min(4.0, max(1.5, densite))       # dosage : appris des vidéos TikTok envoyées (sinon ~1 / 3 s)
    plafond = max(2, int(duree * par_10s / 10))
    out, compte, dernier = [], {}, None

    def ajoute(nom, t, gain=None):
        nonlocal dernier
        if nom == dernier or compte.get(nom, 0) >= 2 or len(out) >= plafond: return False
        out.append((nom, max(0.0, t), GAIN.get(nom, 0.5) if gain is None else gain)); compte[nom] = compte.get(nom, 0) + 1; dernier = nom
        return True

    for j, q in enumerate(ph):
        if q.get("p") == "narrateur" and not q.get("chute"): continue
        h = (graine * 7 + j * 13) % 997
        if q["i"] in imposes:                                               # choix de Claude
            ajoute(imposes[q["i"]], q["fin"] + 0.05); continue
        if j == len(ph) - 1: continue                                        # chute finale : déjà son gros impact
        if q.get("chute"):
            ajoute(CHUTES[h % len(CHUTES)], q["fin"] + 0.08); continue
        fait = False
        for motif, nom in MOTS:
            m = re.search(motif, (q.get("texte") or "").lower())
            if m and h % 3:                                                  # pas systématique : 2 fois sur 3
                fait = ajoute(nom, _instant(q, m.start()) if nom in ("caisse", "flash", "glitch", "boing") else
                              (q["deb"] + 0.1 if nom == "clavier" else q["fin"] + 0.05))
                if fait: break
        if not fait and q.get("emo") in EMOTIONS and h % 2 == 0:
            choix = EMOTIONS[q["emo"]]; nom = choix[h % len(choix)]
            ajoute(nom, q["deb"] + 0.05 if nom in ("dents", "bouilloire") else q["fin"] + 0.05)
    for k, (a, b, *_r) in enumerate(silences):                               # blanc gênant
        if b - a >= 0.8: ajoute(SILENCE[(graine + k) % len(SILENCE)], a + 0.15)
    return out
