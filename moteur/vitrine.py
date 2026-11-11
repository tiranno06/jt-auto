"""Vitrine du profil TikTok (choix de l'auteur du 11 novembre 2026, idée 15).

Chaque semaine (workflow « Vitrine et nouveaux créateurs »), le robot prépare de quoi soigner la page de la chaîne, que l'auteur
applique à la main dans l'appli TikTok (TikTok ne permet pas de le faire à sa place) :
- 3 propositions de BIO (80 caractères au plus, la limite de TikTok), écrites par l'IA gratuite d'après ce qui marche (recette du
  succès, thèmes des vidéos les plus vues) ; sans IA : 3 bios toutes prêtes ;
- les 3 vidéos à ÉPINGLER : les plus vues de la chaîne, de 3 histoires différentes (jamais deux du même créateur d'origine) ;
- la PHOTO de profil : le logo de la chaîne (logo-512.png du site), à télécharger.
Résultat : episodes/vitrine.json, montré sur le site (onglet TikTok, « 🏪 Vitrine du profil », boutons « 📋 Copier »)."""
import datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FICHIER = os.path.join(RACINE, "episodes", "vitrine.json")
BIOS_SECOURS = ["Des petits drames du quotidien en dessin animé 😂 Une histoire par jour !",
                "Vos galères préférées, en dessin 🎭 Nouvelle histoire chaque jour 👇",
                "Famille, couple, potes : les petits drames de la vie en croquis 😅🔔"]


def _lire(nom, defaut):
    try: return json.load(open(os.path.join(RACINE, "episodes", nom), encoding="utf-8"))
    except (OSError, ValueError): return defaut


def epingles(historique, n=3):
    """Les vidéos à épingler : les plus vues, publiées, de créateurs d'origine différents."""
    import publication_auto as PA
    pub = sorted([h for h in historique if h.get("publie") is True and h.get("vues") is not None and not h.get("essai")],
                 key=lambda h: -int(h.get("vues") or 0))
    out, profils = [], set()
    for h in pub:
        p = PA.profil(h)
        if p and p in profils: continue
        profils.add(p); out.append({"fichier": h["fichier"], "titre": str(h.get("titre") or "")[:80], "vues": int(h["vues"]),
                                    "url": h.get("url_tiktok") or ""})
        if len(out) >= n: break
    return out


def bios(historique, recette):
    """3 bios (80 caractères au plus) : l'IA gratuite d'abord, sinon les bios toutes prêtes."""
    top = [str(h.get("titre") or "") for h in sorted([h for h in historique if h.get("vues")], key=lambda h: -int(h["vues"]))[:8]]
    forts = ", ".join(f"{x['critere']} {x['valeur']}" for x in (recette.get("plus") or [])[:4])
    try:
        import reseau, ecrire
        if not reseau.ia_disponible(): raise RuntimeError("aucune IA")
        outil = {"name": "bios", "description": "Bios TikTok.", "input_schema": ecrire._schema({"bios": {"type": "array", "items": {"type": "string"}}}, ["bios"])}
        txt = ("Propose 3 bios TikTok en français pour la chaîne « Petits.Dramas » : des petits drames du quotidien joués en dessin animé "
               "(style croquis) sur les sons de TikTok. 80 caractères AU MAXIMUM chacune (emojis compris), drôles, qui donnent envie de "
               f"s'abonner, sans lien ni hashtag. Vidéos qui marchent le mieux : {' | '.join(top)[:600]}. Ce qui plaît : {forts or '—'}.")
        r = ecrire._appel(reseau.claude(), None, [{"role": "user", "content": txt}], outil, max_tokens=600)
        b = [re.sub(r"\s+", " ", str(x)).strip().strip('"') for x in ecrire._liste(r.get("bios"))]
        b = [x for x in b if 10 <= len(x) <= 80 and "http" not in x and "#" not in x][:3]
        if len(b) == 3: return b
    except Exception as e: print(f"Vitrine : bios de l'IA impossibles ({str(e)[:100]}) : bios toutes prêtes", flush=True)
    return BIOS_SECOURS


def preparer():
    h = _lire("historique.json", []); r = _lire("recette.json", {})
    v = {"date": datetime.date.today().isoformat(), "bios": bios(h, r), "epingles": epingles(h), "photo": "logo-512.png"}
    json.dump(v, open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return v


if __name__ == "__main__":
    v = preparer()
    print(f"Vitrine : {len(v['bios'])} bio(s), {len(v['epingles'])} vidéo(s) à épingler")
