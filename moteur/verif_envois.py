"""Vérification de CHAQUE envoi vers TikTok (demande de l'auteur du 25 novembre 2026 : « il n'a pas envoyé de vidéo à 7h30,
régler définitivement le problème, pour tous les envois »).

Avant, le robot notait « publiée » dès que Buffer acceptait la demande, sans jamais regarder ce qui se passait ensuite : les 24 et
25 novembre, Buffer a bien publié… sur un AUTRE compte TikTok (« buzz.insolite », branché sur Buffer la veille), et personne ne l'a vu.

Maintenant (workflow verif_envois.yml, toutes les 30 minutes, léger) : chaque envoi (numéro Buffer gardé dans l'historique,
"buffer_post") est relu chez Buffer une fois son heure passée :
  - parti sur @petitsdramas (lien TikTok de la vidéo) -> "envoi_verifie" = "ok", "lien_tiktok" ;
  - parti sur un autre compte, refusé par TikTok (erreur), ou toujours pas parti 2 heures après l'heure prévue -> la vidéo
    redevient « à publier » (publie = None, "erreur" lisible sur le site) et le téléphone est prévenu ;
  - rattrapage : si l'envoi raté était prévu il y a moins de 12 heures, la vidéo repart TOUT DE SUITE sur le bon compte (un
    rattrapage par passage) ; sinon elle reprend sa place au prochain créneau ;
  - une vidéo qui rate deux fois est mise de côté (publie = False, comme une publication échouée) : elle ne bloque pas les autres.
VERIF_ENVOIS=0 pour couper."""
import os, sys, json, datetime

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
HIST = os.path.join(ICI, "..", "episodes", "historique.json")
RETARD_H = 2           # heures après l'heure prévue au-delà desquelles un envoi « en attente » est un échec
RATTRAPAGE_H = 12      # un envoi raté prévu il y a moins de 12 h repart tout de suite

def _poignee(lien):
    lien = str(lien or "")
    return lien.split("@", 1)[1].split("/")[0].lower() if "@" in lien else ""

def _date(x):
    try: return datetime.datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError: return None

def juger(etat, voulu, maintenant):
    """("ok", lien) / ("attente", "") / ("rate", raison lisible) pour l'état d'un envoi lu chez Buffer."""
    statut = str(etat.get("status") or "").lower()
    lien = etat.get("externalLink") or ""
    canal = etat.get("channel") or {}
    noms = {str(canal.get(k) or "").lstrip("@").lower() for k in ("name", "displayName")} | {_poignee(canal.get("externalLink"))}
    noms.discard("")
    compte = _poignee(lien) or (sorted(noms)[0] if noms else "")
    from publier import meme_compte
    if compte and not meme_compte(compte, voulu) and not any(meme_compte(n, voulu) for n in noms):
        return "rate", f"partie sur le mauvais compte TikTok (@{compte}) au lieu de @{voulu}"
    err = etat.get("error")
    if err or statut in ("error", "failed"):
        msg = (err or {}).get("message") if isinstance(err, dict) else err
        return "rate", f"refusée par TikTok/Buffer : {str(msg or statut)[:200]}"
    if statut == "sent" or (etat.get("sentAt") and lien):
        return "ok", lien
    due = _date(etat.get("dueAt"))
    if due and maintenant - due > datetime.timedelta(hours=RETARD_H):
        return "rate", f"toujours pas partie {RETARD_H} h après l'heure prévue (statut Buffer : {statut or 'inconnu'})"
    return "attente", ""

def verifier(hist, lire_etat, voulu, maintenant):
    """Relit chaque envoi pas encore vérifié. Modifie l'historique. Renvoie (alertes, à_rattraper)."""
    alertes, rattraper = [], []
    for e in hist:
        post = e.get("buffer_post")
        if not post or e.get("envoi_verifie") or e.get("publie") is not True: continue
        try: etat = lire_etat(post) or {}
        except Exception as x:
            print(f"{e.get('fichier')} : envoi {post} illisible chez Buffer ({str(x)[:150]}) : revu au prochain passage"); continue
        verdict, info = juger(etat, voulu, maintenant)
        if verdict == "attente":
            print(f"{e.get('fichier')} : envoi {post} pas encore parti (prévu {etat.get('dueAt')})"); continue
        if verdict == "ok":
            e["envoi_verifie"] = "ok"; e["lien_tiktok"] = info
            print(f"{e.get('fichier')} : bien publiée sur @{voulu} ({info})"); continue
        e["echecs_envoi"] = int(e.get("echecs_envoi") or 0) + 1
        e["envoi_verifie"] = "rate"; e["erreur"] = info; e["envoi_rate"] = {"post": post, "raison": info, "lien": etat.get("externalLink") or ""}
        e.pop("buffer_post", None)
        due = _date(etat.get("dueAt")) or maintenant
        if e["echecs_envoi"] >= 2:
            e["publie"] = False
            alertes.append(("❌ Vidéo pas publiée (2e échec)", f"{e.get('fichier')} : {info}. Mise de côté : à publier à la main."))
        else:
            e["publie"] = None; e.pop("envoi_verifie", None)
            if maintenant - due <= datetime.timedelta(hours=RATTRAPAGE_H) and not rattraper:
                rattraper.append(e["fichier"])
                alertes.append(("⚠️ Envoi raté, rattrapé", f"{e.get('fichier')} : {info}. Elle repart tout de suite sur @{voulu}."))
            else:
                alertes.append(("⚠️ Envoi raté", f"{e.get('fichier')} : {info}. Elle repart au prochain créneau."))
        print(f"{e.get('fichier')} : {info}")
    return alertes, rattraper

def main():
    if str(os.environ.get("VERIF_ENVOIS") or "1").strip() == "0": print("Vérification des envois coupée (VERIF_ENVOIS=0)"); return
    cle = os.environ.get("BUFFER_API_KEY")
    if not cle: print("BUFFER_API_KEY absente : rien à vérifier"); return
    sys.path.insert(0, ICI)
    import publier
    hist = json.load(open(HIST, encoding="utf-8"))
    alertes, rattraper = verifier(hist, lambda i: publier.etat_post(cle, i), publier.compte_voulu(),
                                  datetime.datetime.now(datetime.timezone.utc))
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.makedirs(os.path.join(ICI, "..", "sortie"), exist_ok=True)
    json.dump({"alertes": alertes, "rattraper": rattraper}, open(os.path.join(ICI, "..", "sortie", "verif_envois.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a") as f: f.write(f"alertes={len(alertes)}\nrattraper={' '.join(rattraper)}\n")

def alerter():
    d = json.load(open(os.path.join(ICI, "..", "sortie", "verif_envois.json"), encoding="utf-8"))
    sys.path.insert(0, ICI)
    import alerte
    for titre, texte in d.get("alertes") or []:
        try: alerte.alerter(titre, texte)
        except Exception as x: print(f"alerte non envoyée : {str(x)[:150]}")

if __name__ == "__main__":
    if sys.argv[1:] == ["--alerter"]: alerter()
    else: main()
