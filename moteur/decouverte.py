"""Découverte de nouveaux créateurs (choix de l'auteur du 11 novembre 2026, idée 9).

Chaque semaine (workflow « Vitrine et nouveaux créateurs »), le robot relit les titres des vidéos récentes de vos profils et des
vidéos d'origine déjà reprises : les comptes qu'ils citent (« @… » : duos, collaborations, « allez voir @… ») sont souvent des
créateurs du même style. (La recherche par hashtag de TikTok est cassée dans yt-dlp et refusée par tikwm : on part donc de ces
mentions.) Chaque candidat est VÉRIFIÉ avant d'être proposé : le compte existe, il a au moins 8 vidéos de 8 à 150 s, il a publié
ces 30 derniers jours, et ses vidéos font des vues (médiane ≥ 5 000). Les 6 meilleurs sont rangés dans episodes/decouvertes.json ;
le site les montre (onglet TikTok, « 👥 Mes profils ») avec « ➕ Ajouter » et « 🚫 Jamais ». Jamais un profil déjà dans la liste,
dans la liste noire, ni notre chaîne. DECOUVERTE=0 pour couper."""
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
    return {"profil": pseudo, "vues_mediane": med, "videos": len(vs), "recentes_30j": len(recentes),
            "exemple": meilleure.get("url"), "titre": str(meilleure.get("titre") or "")[:90]}


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
    return out[:6]


if __name__ == "__main__":
    r = chercher()
    json.dump({"date": datetime.date.today().isoformat(), "profils": r}, open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Découverte : {len(r)} nouveau(x) créateur(s) proposé(s)")
