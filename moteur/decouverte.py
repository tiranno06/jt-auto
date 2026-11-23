"""Découverte de nouveaux créateurs (choix de l'auteur du 11 novembre 2026, idée 9).

Chaque semaine (workflow « Vitrine et nouveaux créateurs »), le robot relit les titres des vidéos récentes de vos profils et des
vidéos d'origine déjà reprises : les comptes qu'ils citent (« @… » : duos, collaborations, « allez voir @… ») sont souvent des
créateurs du même style. (La recherche par hashtag de TikTok est cassée dans yt-dlp et refusée par tikwm : on part donc de ces
mentions.) Chaque candidat est VÉRIFIÉ avant d'être proposé : le compte existe, il a au moins 8 vidéos de 8 à 150 s, il a publié
ces 30 derniers jours, et ses vidéos font des vues (médiane ≥ 5 000). Les 6 meilleurs sont rangés dans episodes/decouvertes.json ;
le site les montre (onglet TikTok, « 👥 Mes profils ») avec « ➕ Ajouter » et « 🚫 Jamais ». Jamais un profil déjà dans la liste,
dans la liste noire, ni notre chaîne. DECOUVERTE=0 pour couper. Depuis le 21 novembre : créateurs du reste de la francophonie
repérés (`pays`) et favorisés (`selection`)."""
import datetime, json, os, re, statistics, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "decouvertes.json")
VUES_MIN = 5000


def mentions(textes):
    """Comptes cités dans des textes : {pseudo: nombre de textes}."""
    c = {}
    for t in textes:
        for m in set(x.lower().rstrip(".") for x in re.findall(r"(?<![\w.])@([\w.\-]{3,30})", str(t or ""))):
            c[m] = c.get(m, 0) + 1
    return c


# Créateurs de TOUTE la francophonie (choix de l'auteur du 21 novembre 2026, idée 22 ; va avec le créneau francophonie) : repérés à
# leurs titres (drapeaux, villes, pays) ; jusqu'à 2 des 6 propositions leur sont réservées quand il y en a. FRANCOPHONIE_DECOUVERTE=0.
PAYS = [("Belgique", r"🇧🇪|\bbelgi|\bbruxelles\b|\bbxl\b|\bli[èe]ge\b|\bcharleroi\b"),
        ("Québec", r"🇨🇦|qu[ée]bec|\bmtl\b|montr[ée]al|\btabarn|\bpantoute\b"),
        ("Suisse", r"🇨🇭|\bsuisse\b|gen[èe]ve|lausanne"),
        ("Côte d'Ivoire", r"🇨🇮|c[ôo]te d.ivoire|ivoirien|abidjan"),
        ("Sénégal", r"🇸🇳|s[ée]n[ée]gal|dakar"),
        ("Cameroun", r"🇨🇲|cameroun|douala|yaound[ée]"),
        ("Maroc", r"🇲🇦|\bmaroc|casablanca|\brabat\b"),
        ("Algérie", r"🇩🇿|alg[ée]ri|\balger\b|\boran\b"),
        ("Tunisie", r"🇹🇳|tunisi|\btunis\b"),
        ("Congo", r"🇨🇩|🇨🇬|congo|kinshasa|brazzaville"),
        ("Haïti", r"🇭🇹|ha[ïi]ti"), ("Madagascar", r"🇲🇬|madagascar|malgache"),
        ("Afrique francophone", r"🇧🇫|🇲🇱|🇬🇦|🇧🇯|🇹🇬|🇬🇳|burkina|\bmali\b|gabon|b[ée]nin|\btogo\b|guin[ée]e|africain")]


def pays(titres):
    """Pays francophone hors France repéré dans les titres d'un créateur (2 titres au moins), ou None."""
    c = {}
    for t in titres:
        for nom, motif in PAYS:
            if re.search(motif, str(t or "").lower()): c[nom] = c.get(nom, 0) + 1
    return max(c, key=c.get) if c and max(c.values()) >= 2 else None


def verifier(pseudo, videos):
    """Fiche d'un candidat d'après ses vidéos récentes, ou None s'il ne convient pas."""
    import profils_tiktok as P
    vs = [v for v in videos if v.get("duree") is None or P.DUREE_MIN <= float(v["duree"]) <= P.DUREE_MAX]
    if len(vs) < 8: return None
    maintenant = time.time()
    recentes = [v for v in vs if v.get("date") and maintenant - float(v["date"]) < 30 * 86400]
    vues = [int(v["vues"]) for v in vs if v.get("vues") is not None]
    if not recentes or not vues: return None
    med = int(statistics.median(vues))
    if med < VUES_MIN: return None
    meilleure = max(vs, key=lambda v: int(v.get("vues") or 0))
    out = {"profil": pseudo, "vues_mediane": med, "videos": len(vs), "recentes_30j": len(recentes),
           "exemple": meilleure.get("url"), "titre": str(meilleure.get("titre") or "")[:90]}
    p_ = pays([v.get("titre") for v in vs])
    if p_: out["pays"] = p_
    return out


def chercher(journal=print, max_candidats=30):
    if os.environ.get("DECOUVERTE", "1") == "0": return []
    import profils_tiktok as P
    connus = {p.lower() for p in P.liste()} | {p.lower() for p in P.connus()} | P.interdits() | {x.lower() for x in P.NOTRE_CHAINE}
    connus.add((os.environ.get("TIKTOK_COMPTE") or "").strip().lstrip("@").lower())
    textes = []
    for p in P.liste()[:8]:
        textes += [v.get("titre") for v in P.videos(p, journal=lambda m: None)]
    try:
        hist = json.load(open(os.path.join(P.RACINE, "episodes", "historique.json"), encoding="utf-8"))
        textes += [h.get("titre_source") for h in hist if h.get("titre_source")]
    except (OSError, ValueError): pass
    c = {m: n for m, n in mentions(textes).items() if m not in connus}
    cand = sorted(c, key=lambda m: -c[m])[:max_candidats]
    journal(f"Découverte : {len(c)} compte(s) cité(s) par vos créateurs, {len(cand)} vérifié(s)")
    out = []
    for m in cand:
        f = verifier(m, P.videos(m, journal=lambda x: None))
        if f: f["cite"] = c[m]; out.append(f); journal(f"  ✅ @{m} : {f['videos']} vidéos, {f['vues_mediane']} vues (médiane)")
    out.sort(key=lambda f: -(f["vues_mediane"] * (1 + 0.3 * f["cite"])))
    return selection(out)


def selection(out, n=6, reserve=2):
    """Les n meilleurs, dont jusqu'à `reserve` places pour des créateurs francophones hors de France (idée 22)."""
    if os.environ.get("FRANCOPHONIE_DECOUVERTE", "1") == "0": return out[:n]
    franco = [f for f in out if f.get("pays")][:reserve]
    reste = [f for f in out if f not in franco][:n - len(franco)]
    return sorted(franco + reste, key=lambda f: out.index(f))


# Créateurs d'origine (choix de l'auteur du 23 novembre 2026, idée 5 : « et les rajouter dans la liste des profils suivis »). Nos créateurs
# suivis sont surtout des chaînes de dessin animé qui reprennent les voix de VRAIS créateurs (crédités « @… » dans leurs descriptions :
# @aguerin30, @jayzocc…). En prenant les sons à la source, on arrive avant les autres chaînes de dessin animé, sur des sons souvent bien
# plus vus. Gardé : cité au moins 2 fois, titres en français, 10 000 vues en médiane, 8 vidéos de 8 à 150 s, publié dans l'année
# (les noms affichés qui tombent sur un compte étranger sans rapport, « @julie », « @nbl », sont écartés). Résultat :
# episodes/createurs_origine.json ; profils_tiktok.liste() les ajoute aux profils suivis et le site les inscrit dans « Mes profils »
# (PROFILS_TIKTOK) à sa prochaine ouverture. ORIGINES=0 pour couper.
SEMENCE = ["aguerin30", "zequoiza", "jawedyoussef"]                       # cités dans la proposition choisie par l'auteur (23 novembre)
ORIGINES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "createurs_origine.json")
FR = re.compile(r"(?<![\w'])(je|tu|il|elle|on|nous|vous|le|la|les|un|une|des|du|de|et|est|c'est|t'es|pas|quand|mon|ma|mes|ton|ta|tes|ça|moi|toi|avec|pour|mais|ou|qui|que|quoi)(?![\w'])", re.I)


def francais(titres):
    t = [str(x or "").replace("’", "'") for x in titres if str(x or "").strip()]   # (titres courts, apostrophes typographiques : @aguerin30)
    return bool(t) and sum(1 for x in t if FR.search(x) or re.search(r"[éèêàçùû]|\b[jJ]'|\b[cC]'", x)) >= 0.4 * len(t)


def origine_ok(pseudo, videos, maintenant=None):
    import profils_tiktok as P
    maintenant = maintenant or time.time()
    vs = [v for v in videos if v.get("duree") is None or P.DUREE_MIN <= float(v["duree"]) <= P.DUREE_MAX]
    vues = [int(v["vues"]) for v in vs if v.get("vues") is not None]
    dates = [float(v["date"]) for v in vs if v.get("date")]
    if len(vs) < 8 or not vues or not francais([v.get("titre") for v in vs]): return None
    if dates and maintenant - max(dates) > 365 * 86400: return None
    med = int(statistics.median(vues))
    if med < 10000: return None
    return {"profil": pseudo, "vues_mediane": med, "videos": len(vs)}


def origines(journal=print, lister=None, max_candidats=20):
    if os.environ.get("ORIGINES", "1") == "0": return []
    import profils_tiktok as P, concurrence as C
    lister = lister or (lambda p: P.videos(p, journal=lambda m: None))
    suivis = [p for p in (P.liste(sans_origines=True) or [])]
    exclus = {p.lower() for p in suivis} | P.interdits() | {x.lower() for x in P.NOTRE_CHAINE}   # (pas connus() : un son déjà repris ne veut pas dire suivi)
    exclus.add((os.environ.get("TIKTOK_COMPTE") or "").strip().lstrip("@").lower())
    cite, par = {}, {}
    for p in suivis[:20]:
        for v in lister(p) or []:
            for m in C._mentions(v.get("titre")):
                if m not in exclus: cite[m] = cite.get(m, 0) + 1; par.setdefault(m, set()).add(p)
    cand = [m for m in sorted(cite, key=lambda m: -cite[m]) if cite[m] >= 2][:max_candidats]
    try:                                                                   # + les créateurs proposés dans « Nouveaux créateurs »
        for f in json.load(open(FICHIER, encoding="utf-8")).get("profils") or []:   # (cités chez nos créateurs, déjà vérifiés une fois)
            m = str(f.get("profil") or "").lower()
            if m and m not in exclus and m not in cand: cand.append(m); cite.setdefault(m, 1); par.setdefault(m, {"nouveaux créateurs"})
    except (OSError, ValueError): pass
    for m in SEMENCE:
        if m not in exclus and m not in cand: cand.append(m); cite.setdefault(m, 1); par.setdefault(m, {"proposition du 23 novembre"})
    out = []
    for m in cand:
        f = origine_ok(m, lister(m) or [])
        if f:
            f.update(cite=cite[m], par=sorted(par[m])[:5]); out.append(f)
            journal(f"  🎙️ créateur d'origine @{m} : cité {cite[m]} fois, {f['vues_mediane']} vues (médiane)")
    out.sort(key=lambda f: -(f["vues_mediane"] * (1 + 0.2 * f["cite"])))
    journal(f"Créateurs d'origine : {len(cand)} vérifié(s), {len(out)} gardé(s)")
    return out[:8]


if __name__ == "__main__" and "--origines" in sys.argv:
    try: ancien = json.load(open(ORIGINES, encoding="utf-8"))
    except (OSError, ValueError): ancien = {}
    if ancien.get("date") == datetime.date.today().isoformat() and "--forcer" not in sys.argv:
        print("Créateurs d'origine : déjà cherchés aujourd'hui"); sys.exit(0)
    r = origines()
    garde = {f["profil"]: f for f in (ancien.get("profils") or [])}            # jamais oublié une fois trouvé (le site l'a peut-être ajouté)
    for f in r: garde[f["profil"]] = f
    json.dump({"date": datetime.date.today().isoformat(), "profils": list(garde.values())[:20]}, open(ORIGINES, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    sys.exit(0)

if __name__ == "__main__":
    r = chercher()
    json.dump({"date": datetime.date.today().isoformat(), "profils": r}, open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Découverte : {len(r)} nouveau(x) créateur(s) proposé(s)")
