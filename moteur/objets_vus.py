"""Objets de la vidéo d'origine repérés automatiquement (choix de l'auteur du 11 novembre 2026, idée 4).

OWL-ViT (Google, Apache 2.0, gratuit, sur la machine) cherche dans l'original, une image toutes les 1,5 s, les objets que nos
personnages savent tenir (téléphone, verre, tasse, livre, ordinateur, sac, valise, parapluie, fleurs, cadeau, pizza, micro, guitare…).
Marche aussi sur les dessins animés (la plupart des sons repris en sont). Un objet vu sur au moins 2 images est donné au personnage
qui parle à ce moment-là (réplique sans objet seulement : ce que l'IA ou le texte a choisi n'est jamais remplacé). Pas d'objets du
décor (ordinateur de bureau, meubles) : l'essai du 11 novembre donnait un écran posé sur un bureau à tenir en main.
Sans l'IA de mise en scène, ou quand elle oublie un objet, la vidéo le montre quand même. OBJETS_VUS=0 pour couper."""
import os

MODELE = "google/owlvit-base-patch32"
SEUIL = 0.2
PAS = 1.5
CHERCHES = {"telephone": "a smartphone", "verre": "a drinking glass", "cafe": "a coffee mug", "bouteille": "a bottle", "livre": "a book",
            "tablette": "a tablet computer", "cles": "a bunch of keys", "portefeuille": "a wallet",
            "billet": "banknotes", "sac_main": "a handbag", "valise": "a suitcase", "parapluie": "an umbrella", "fleur": "a bouquet of flowers",
            "cadeau": "a gift box with a ribbon", "pizza": "a pizza", "croissant": "a croissant", "micro": "a microphone", "guitare": "a guitar",
            "telecommande": "a tv remote control", "stylo": "a pen", "journal": "a newspaper", "lettre": "an envelope", "colis": "a cardboard box",
            "casque_moto": "a motorcycle helmet", "poele": "a frying pan", "ciseaux": "scissors", "marteau": "a hammer", "haltere": "a dumbbell"}
_M = {}


def actif(): return os.environ.get("OBJETS_VUS", "1") != "0"


def _modele():
    if "m" not in _M:
        from transformers import OwlViTProcessor, OwlViTForObjectDetection
        _M["p"] = OwlViTProcessor.from_pretrained(MODELE); _M["m"] = OwlViTForObjectDetection.from_pretrained(MODELE).eval()
    return _M["p"], _M["m"]


def chercher(video, duree_max=150):
    """[(instant, objet, score)] vus dans la vidéo (une image toutes les PAS secondes)."""
    import cv2, torch
    from PIL import Image
    cap = cv2.VideoCapture(video)
    if not cap.isOpened(): return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    proc, mod = _modele(); noms = list(CHERCHES); textes = [[CHERCHES[k] for k in noms]]
    out, t = [], 0.5
    try:
        while t < min(duree_max, n / fps):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read()
            if not ok: break
            im = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
            with torch.no_grad():
                x = proc(text=textes, images=im, return_tensors="pt"); r = mod(**x)
                pp = getattr(proc, "post_process_grounded_object_detection", None) or proc.post_process_object_detection   # (selon la version)
                res = pp(r, threshold=SEUIL, target_sizes=torch.tensor([im.size[::-1]]))[0]
            for s, l in zip(res["scores"].tolist(), res["labels"].tolist()):
                out.append((round(t, 2), noms[l], round(float(s), 3)))
            t += PAS
    finally: cap.release()
    return out


def attribuer(reps, vus, journal=print):
    """Donne chaque objet vu (sur 2 images au moins) au personnage qui parle à ce moment, si sa réplique n'a pas déjà d'objet."""
    from collections import Counter
    sur = Counter(o for _, o, _ in vus)
    faits = []
    for t, o, s in sorted(vus, key=lambda x: -x[2]):
        if sur[o] < 2: continue
        k = next((k for k, r in enumerate(reps) if float(r.get("_deb", 0)) - 0.4 <= t <= float(r.get("_fin", 0)) + 0.4
                  and r.get("p") not in (None, "narrateur")), None)
        if k is None or reps[k].get("objet"): continue
        reps[k]["objet"] = o; faits.append(f"réplique {k + 1} : {o}")
    if faits: journal("  objets vus dans l'original : " + ", ".join(faits[:8]))
    return faits


def appliquer(video, reps, journal=print):
    if not actif() or not video or not os.path.exists(video): return []
    try: vus = chercher(video)
    except Exception as e:
        journal(f"  objets de l'original non cherchés ({str(e)[:120]})"); return []
    return attribuer(reps, vus, journal)
