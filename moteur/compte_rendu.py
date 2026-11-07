"""Compte rendu de la vidéo corrigé tout de suite (demande de l'auteur du 7 novembre 2026 : « les problèmes signalés dans les comptes
rendus des vidéos doivent être réglés immédiatement pour que les scores augmentent »).

1. Pendant la fabrication (sons TikTok) : une fois la vidéo finie et contrôlée, les points restés « à vérifier » et les remarques du jury
   sont réécrits comme une remarque d'auteur (`texte`) et passent au même correcteur que « Dis ce qui ne va pas » (`remarque.appliquer` :
   qui parle, lieu, personnages, espèce, costume, jeu, réaction, bruitage…). Seuls les passages touchés sont redessinés ; la vidéo est
   contrôlée à nouveau et la version corrigée n'est gardée que si sa note de confiance (ou, à égalité, celle du jury) est meilleure.
   Deux tours au plus (COMPTE_RENDU_TOURS), jamais au-delà de la limite de temps ; COMPTE_RENDU=0 pour couper.
2. Vidéos déjà faites : bouton « 🛠️ Corriger d'après le compte rendu » (fiche d'une vidéo TikTok) et « Corriger les vidéos signalées »
   (onglet TikTok) -> refaire « fichier|compte_rendu » : même son, mêmes répliques, corrections du compte rendu ; la moins sûre des deux
   versions est ensuite retirée (jamais une vidéo publiée ou cochée « À publier »)."""
import os, re

GOUT = r"(pourrait|pourraient|serait|manque (un peu|de punch|d'impact)|plus dr[ôo]le|plus dynamique|plus expressi|plus vari)"


def actif(): return os.environ.get("COMPTE_RENDU", "1") != "0"


def tours():
    try: return max(0, min(3, int(os.environ.get("COMPTE_RENDU_TOURS") or 2)))
    except ValueError: return 2


def texte(points=None, jury=None, equipe=None):
    """Le compte rendu, écrit comme une remarque d'auteur (une ligne par problème concret, avec l'instant quand il est connu)."""
    lignes = []
    for p in points or []:
        q = str(p.get("quoi") or "").strip()
        if not q or re.search(r"saut d'image|clignotement|décalage", q, re.I): continue   # techniques : rien à corriger dans la mise en scène
        lignes.append((f"à {float(p['t']):.1f} s : " if p.get("t") is not None else "") + q)
    for k, v in (jury or {}).items():
        for r in (v or {}).get("remarques") or []:
            pb = str(r.get("probleme") or "").strip()
            if not pb or re.search(GOUT, pb, re.I): continue               # avis de goût : pas un problème à corriger
            lignes.append((f"à {float(r['moment']):.1f} s : " if isinstance(r.get("moment"), (int, float)) else "") + pb)
    for l in equipe or []:
        if not l.get("ok") and l.get("revoir"): lignes.append(f"{l.get('controle')} : {l.get('detail')}")
    vus, out = set(), []
    for l in lignes:
        c = re.sub(r"\W+", " ", l.lower())[:80]
        if c not in vus: vus.add(c); out.append(l)
    return "\n".join(f"- {l[:220]}" for l in out[:14])


def depuis_historique(h):
    """Compte rendu d'une vidéo déjà faite (ligne d'historique : points à vérifier et remarques du jury)."""
    pts = [p for p in (h or {}).get("a_verifier") or [] if isinstance(p, dict)]
    rem = {"jury": {"remarques": [{"probleme": r} for r in ((h or {}).get("jury") or {}).get("remarques") or [] if isinstance(r, str)]}}
    return texte(pts, rem)


def meilleure(c_avant, c_apres, n_avant=None, n_apres=None):
    """La version corrigée est-elle meilleure ? Confiance plus haute, ou égale avec une meilleure note du jury."""
    if c_apres is None or c_avant is None: return False
    if c_apres != c_avant: return c_apres > c_avant
    return n_apres is not None and n_avant is not None and n_apres > n_avant
