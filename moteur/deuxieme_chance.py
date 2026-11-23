"""Deuxième chance (choix de l'auteur, 31 octobre 2026) : une vidéo sur un son TikTok dont la note de confiance est trop basse
(CONFIANCE_MIN, 40 par défaut) est refaite UNE fois, sur le même son, avec un autre tirage (mise en scène, casting, décors) ; à la
fin, on garde la plus sûre des deux et l'autre est supprimée (historique + archives). Jamais une vidéo déjà publiée ni une vidéo
cochée « À publier » : dans ce cas on garde les deux. DEUXIEME_CHANCE=0 pour couper.

Le lancement passe par l'entrée « theme » d'emission.yml : « TIKTOK::<lien>##2e:<fichier de la 1re version> »."""
import os

MARQUE = "##2e:"


def seuil():
    try: return float(os.environ.get("CONFIANCE_MIN") or 40)
    except ValueError: return 40.0


def separer(theme):
    """« TIKTOK::lien##2e:fichier » -> (« TIKTOK::lien », fichier) ; sinon (theme, "")."""
    if MARQUE not in (theme or ""): return theme, ""
    t, _, f = theme.partition(MARQUE)
    return t.strip(), f.strip()


def protegee(h, cochee_compte=True):
    """Publiée, ou cochée « À publier » (variable PUBLI_FILE) : on ne la supprime jamais. cochee_compte=False : seule une vidéo
    publiée est protégée (vidéo refaite : la nouvelle version reprend la case « À publier » de l'ancienne, publication_auto.remplacant)."""
    if not h: return True
    if h.get("publie") is True: return True
    if not cochee_compte: return False
    file_ = [x.strip() for x in str(os.environ.get("PUBLI_FILE") or "").splitlines() if x.strip()]
    return h.get("fichier") in file_


def remplacement(ancien, nouveau, mode):
    """Vidéo refaite (demande de l'auteur du 22 novembre 2026 : « remplacer la vidéo dans la liste pour éviter les doublons ») : renvoie
    le fichier à retirer ("" = les deux restent). L'ancienne version déjà PUBLIÉE sur TikTok reste (elle est en ligne). Sinon :
    corrections demandées par l'auteur (remarque, qui parle, personnages, décors…) -> la nouvelle remplace l'ancienne ; correction
    automatique du compte rendu -> la plus sûre des deux est gardée (note de confiance). Quand la nouvelle reste, elle porte
    "remplace" : elle reprend la place « À publier » de l'ancienne (publication_auto.remplacant, même calcul sur le site)."""
    if protegee(ancien, cochee_compte=False):
        print("Vidéo refaite : l'ancienne version est déjà publiée sur TikTok : les deux restent dans la liste", flush=True); return ""
    c1, c2 = ancien.get("confiance"), nouveau.get("confiance")
    if mode == "compte_rendu" and isinstance(c1, (int, float)) and isinstance(c2, (int, float)) and c2 < c1:
        print(f"Compte rendu : confiance {c1} → {c2} : la nouvelle version est moins sûre, elle est retirée (l'ancienne reste)", flush=True)
        return nouveau.get("fichier") or ""
    nouveau["remplace"] = ancien.get("fichier")
    print(f"Vidéo refaite : {nouveau.get('fichier')} remplace {ancien.get('fichier')} dans la liste" +
          (f" (confiance {c1} → {c2})" if c2 is not None else "") + " ; sa place « À publier » est gardée", flush=True)
    return ancien.get("fichier") or ""


def decider(historique, entree, url, premiere=""):
    """Après une vidéo TikTok (entree = sa ligne d'historique, déjà ajoutée). Renvoie :
    ("relancer", theme) : 1re version peu sûre -> une 2e chance est lancée ;
    ("supprimer", fichier) : 2e version finie -> la moins sûre des deux est retirée ;
    (None, "") : rien à faire."""
    if os.environ.get("DEUXIEME_CHANCE", "1") == "0" or not entree or entree.get("essai"): return None, ""
    c = entree.get("confiance")
    if premiere:                                                           # 2e version : on compare
        ancienne = next((h for h in historique if h.get("fichier") == premiere), None)
        entree["deuxieme_chance_de"] = premiere
        if ancienne is None: return None, ""                               # supprimée entre-temps par l'auteur : on garde la nouvelle
        c1 = ancienne.get("confiance") if isinstance(ancienne.get("confiance"), (int, float)) else 0
        c2 = c if isinstance(c, (int, float)) else 0
        if protegee(ancienne, cochee_compte=False):
            print(f"Deuxième chance : 1re version déjà publiée : les deux sont gardées ({c1} / {c2})", flush=True)
            return None, ""
        if c2 >= c1:
            print(f"Deuxième chance : la nouvelle version est plus sûre ({c1} → {c2}) : la 1re ({premiere}) est retirée (elle garde sa place « À publier »)", flush=True)
            entree["remplace"] = premiere
            return "supprimer", premiere
        print(f"Deuxième chance : la 1re version reste la plus sûre ({c1} contre {c2}) : la nouvelle est retirée", flush=True)
        return "supprimer", entree.get("fichier") or ""
    if not url or not isinstance(c, (int, float)) or c >= seuil(): return None, ""
    entree["deuxieme_chance"] = "en_cours"
    print(f"Deuxième chance : note de confiance {c} < {seuil():.0f} : la vidéo est refaite une fois sur le même son, la plus sûre sera gardée", flush=True)
    return "relancer", f"TIKTOK::{url}{MARQUE}{entree.get('fichier')}"


# ------------------------------------------------------------------ barrière de qualité (audit du 23 novembre 2026)
# Demande de l'auteur : « les vidéos auraient dû être réparées jusqu'à ce qu'il n'y ait plus d'erreurs, et ENSUITE postées sur le
# site ». Une vidéo tirée au hasard (chaîne, créneau, son au hasard) qui garde, après toutes les corrections automatiques, un défaut
# grave MESURÉ (réplique sur la mauvaise voix, l'image de l'original qui montre l'autre parler, bouches du mauvais personnage) est
# RECALÉE : rangée avec les essais (« 🧪 Essais » du site, effacée au bout de 3 jours, jamais proposée à la publication) et une
# nouvelle vidéo est lancée sur un AUTRE son (REMPLACANTES_MAX = 2 remplaçantes à la suite au plus). Un lien collé par l'auteur ou une
# vidéo refaite à sa demande n'est jamais recalée (il garde la main). BARRIERE=0 pour couper.
BLOQUANTS = ("attribution", "voix et dessin", "synchro", "bouches", "dialogue")


def remplacantes_max():
    try: return max(0, int(os.environ.get("REMPLACANTES_MAX") or 2))
    except ValueError: return 2


def barriere(entree):
    """Raisons de recaler la vidéo (liste de textes) ; [] = elle passe."""
    if os.environ.get("BARRIERE", "1") == "0" or not entree or entree.get("essai") or entree.get("manuel"): return []
    return [str(p.get("quoi") or "")[:140] for p in entree.get("a_verifier") or []
            if isinstance(p, dict) and p.get("grave", True) and str(p.get("poste") or "").split(" · ")[-1] in BLOQUANTS]


def recaler(entree, source, profondeur):
    """Range la vidéo avec les essais ; renvoie le texte de sortie/.remplacante (« n° de remplaçante » puis le son à éviter) ou ""."""
    raisons = barriere(entree)
    if not raisons: return ""
    entree["essai"] = True; entree["recalee"] = raisons[:6]
    print("Barrière de qualité : vidéo RECALÉE (rangée avec les essais, jamais sur la liste) : " + " ; ".join(raisons[:3]), flush=True)
    if profondeur >= remplacantes_max():
        print(f"Barrière de qualité : déjà {profondeur} remplaçante(s) à la suite : pas de nouvelle tentative", flush=True); return ""
    return f"{profondeur + 1}\n{source or ''}"
