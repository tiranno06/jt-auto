"""Banque visuelle et sonore du studio : tout ce qui a été vu ET entendu dans les vidéos TikTok envoyées, vidéo après vidéo (episodes/banque_visuelle.json).

Pour chaque vidéo d'origine : les mesures de l'image (analyse_video : montage, cadrages, caméra, personnes, couleurs d'habits et de
cheveux, palette, lumière, agitation, sourires), le son (analyse_audio : voix, débit, blancs, musique, bruitages, événements,
émotions de jeu), ce que Claude y a reconnu quand il était disponible (lieu, objets, tenues, coiffures,
gestes, plans), ce que notre studio en a fait (bible) et le fichier de notre vidéo. Les vues TikTok de notre vidéo (stats.json) sont
relues à chaque fois : plus une vidéo a marché, plus son style pèse dans les tendances.

Le système s'améliore ainsi au fil des vidéos, sans entraînement ni IA : quand une vidéo n'apporte pas d'image exploitable, le studio
reprend le rythme et les cadrages moyens de la banque (pondérés par les vues), et Claude reçoit un résumé de la banque (ce qui revient
souvent, ce qui a fait des vues) quand il met en scène une nouvelle vidéo."""
import datetime, json, math, os
from collections import Counter

ICI = os.path.dirname(os.path.abspath(__file__))
FICHIER = os.path.join(ICI, "..", "episodes", "banque_visuelle.json")
STATS = os.path.join(ICI, "..", "episodes", "stats.json")

def lire():
    try:
        with open(FICHIER, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return []

def _vues():
    try:
        with open(STATS, encoding="utf-8") as f: return {v.get("fichier"): int(v.get("vues") or 0) for v in json.load(f).get("videos", []) if v.get("fichier")}
    except (OSError, ValueError, AttributeError): return {}

def rythme(V):
    """Ce qu'on garde du montage d'une vidéo pour notre storyboard."""
    p = V.get("plans") or {}
    return dict(serre=round(p.get("tres_serre", 0) + p.get("serre", 0), 3), large=round(p.get("large", 0), 3), tres_serre=p.get("tres_serre", 0),
                camera=V.get("camera") or {}, energie=V.get("energie", 0.3), sourires=V.get("sourires", 0.0), duree_plan=V.get("duree_plan", 2.0))

def ajouter(doublage, studio_claude=None, realisation=None, fichier=None):
    """Range une vidéo analysée dans la banque (une seule entrée par vidéo d'origine : la plus récente)."""
    V = (doublage or {}).get("visuel") or {}; A = (doublage or {}).get("audio") or {}
    if not V and not A and not studio_claude: return
    S = studio_claude if isinstance(studio_claude, dict) else {}
    entree = dict(date=datetime.date.today().isoformat(), source=(doublage or {}).get("source"), auteur=(doublage or {}).get("auteur"),
                  visuel=V, audio=A, claude={k: S[k] for k in ("lieux", "moment", "costumes", "objets", "gags", "ambiances", "plans") if k in S},
                  realisation=realisation or {}, video=fichier)
    b = [e for e in lire() if not entree["source"] or e.get("source") != entree["source"]] + [entree]
    try:
        os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
        with open(FICHIER, "w", encoding="utf-8") as f: json.dump(b[-300:], f, ensure_ascii=False, indent=1)
    except OSError: pass

def tendances():
    """Moyennes de la banque pondérées par les vues de nos vidéos : rythme (cadrages, caméra, agitation) et ce qui revient souvent."""
    b = lire(); vues = _vues()
    if not b: return {}
    tot, acc, cam = 0.0, Counter(), Counter(); lieux, objets, hauts, coiffures, gestes = Counter(), Counter(), Counter(), Counter(), Counter()
    meilleurs = []; son, tot_s, evts, emos = Counter(), 0.0, Counter(), Counter()
    for e in b:
        v = vues.get(e.get("video"), 0); w = 1.0 + math.log1p(v) / 3                  # 0 vue : poids 1 ; 1 000 vues : poids ≈ 3,3
        if v: meilleurs.append((v, e))
        V = e.get("visuel") or {}
        if V.get("plans"):
            r = rythme(V); tot += w
            for k in ("serre", "large", "tres_serre", "energie", "sourires", "duree_plan"): acc[k] += w * float(r.get(k) or 0)
            for k, x in (r.get("camera") or {}).items(): cam[k] += w * float(x)
        A = e.get("audio") or {}
        if A.get("duree"):
            tot_s += w
            for k in ("debit", "blanc_moyen", "dynamique_db", "impacts_10s"): son[k] += w * float(A.get(k) or 0)
            son["musique"] += w * float(A.get("musique") or 0) ; son["sur_vanne"] += w * (A.get("sur_vanne", 0) / max(1, A.get("impacts", 0)))
            for k, x in (A.get("evenements") or {}).items(): evts[k] += w * x
            for k, x in (A.get("emotions") or {}).items(): emos[k] += w * x
        C = e.get("claude") or {}; R_ = e.get("realisation") or {}
        for l in (C.get("lieux") or R_.get("lieux") or []): lieux[l] += w
        for o in C.get("objets") or []:
            if isinstance(o, dict) and o.get("objet"): objets[o["objet"]] += w
        for c in (C.get("costumes") or {}).values():
            if isinstance(c, dict):
                if c.get("haut"): hauts[c["haut"]] += w
                if c.get("cheveux"): coiffures[c["cheveux"]] += w
        for x in C.get("plans") or []:
            if isinstance(x, dict) and x.get("geste"): gestes[x["geste"]] += w
    out = dict(n=len(b), lieux=[k for k, _ in lieux.most_common(5)], objets=[k for k, _ in objets.most_common(8)], hauts=[k for k, _ in hauts.most_common(6)],
               coiffures=[k for k, _ in coiffures.most_common(4)], gestes=[k for k, _ in gestes.most_common(6)],
               meilleures=[(v, (e.get("realisation") or {}).get("lieux"), e.get("source")) for v, e in sorted(meilleurs, key=lambda x: -x[0])[:3]])
    if tot_s:
        out["audio"] = {k: round(son[k] / tot_s, 2) for k in ("debit", "blanc_moyen", "dynamique_db", "impacts_10s", "musique", "sur_vanne")}
        out["audio"].update(n=int(sum(1 for e in b if (e.get("audio") or {}).get("duree"))), evenements=[k for k, _ in evts.most_common(5)],
                            emotions=[k for k, _ in emos.most_common(6)])
    if tot:
        out["rythme"] = {k: round(acc[k] / tot, 3) for k in ("serre", "large", "tres_serre", "energie", "sourires", "duree_plan")}
        out["rythme"]["camera"] = {k: round(x / tot, 3) for k, x in cam.items()}
    return out

def consigne():
    """Résumé de la banque pour Claude (vide tant qu'elle est vide)."""
    t = tendances()
    if not t: return ""
    r = t.get("rythme") or {}
    morceaux = [f"BANQUE VISUELLE ET SONORE ({t['n']} vidéo(s) déjà analysée(s), pondérée par les vues de nos vidéos) :"]
    if r: morceaux.append(f"cadrages serrés {int(100 * r['serre'])} %, larges {int(100 * r['large'])} %, un plan toutes les {r['duree_plan']:.1f} s, agitation {r['energie']:.2f}")
    for nom, cle in (("lieux fréquents", "lieux"), ("objets fréquents", "objets"), ("tenues fréquentes", "hauts"), ("coiffures", "coiffures"), ("gestes", "gestes")):
        if t.get(cle): morceaux.append(f"{nom} : {', '.join(t[cle])}")
    if t.get("meilleures"): morceaux.append("ce qui a fait le plus de vues : " + "; ".join(f"{v} vues ({', '.join(l or [])})" for v, l, _ in t["meilleures"]))
    a = t.get("audio") or {}
    if a: morceaux.append(f"son ({a['n']} vidéo(s)) : {a['debit']} mots/s, blancs de {a['blanc_moyen']} s, {a['impacts_10s']} bruitage(s) toutes les 10 s "
                          f"(dont {int(100 * a['sur_vanne'])} % sur une vanne), musique de fond {int(100 * a['musique'])} % du volume"
                          + (f", événements : {', '.join(a['evenements'])}" if a.get("evenements") else "")
                          + (f", émotions de jeu : {', '.join(a['emotions'])}" if a.get("emotions") else ""))
    morceaux.append("Inspire-t'en sans copier : la vidéo du jour passe d'abord.")
    return "\n".join(morceaux)
