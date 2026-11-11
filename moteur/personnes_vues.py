"""Qui est à l'image dans la vidéo d'origine, et qui bouge (choix de l'auteur du 11 novembre 2026, idées 11 et 12).

- Grounding DINO (IDEA Research, Apache 2.0, modèle « tiny » sur la machine) regarde une image toutes les 1,5 s et trouve, d'après des
  MOTS, les personnes (vraies ou dessinées) et les objets tenus (téléphone, verre, sac…) : une seule passe pour les deux.
  -> nombre de personnes vues ENSEMBLE à l'image (`nombre`) : il aide equipe.presents à ne pas dessiner un 3e personnage absent ;
  -> objets vus (`objets`), qui remplacent OWL-ViT dans objets_vus.py (repli : OWL-ViT).
- SAM 2 (Meta, Apache 2.0, modèle « tiny ») découpe précisément chaque personne trouvée, au début de chaque plan (coupes de
  TransNetV2) ; on mesure ensuite ce qui bouge DANS chaque silhouette (8 images/s), le mouvement du décor et de la caméra retiré.
  -> 4e témoin image pour « qui dit cette phrase » (`temoin`, même format que regard.temoin : 0 = la personne la plus à gauche).
Modèles de Hugging Face (fichiers safetensors, gardés dans le cache du workflow). ~2-3 min par vidéo sur la machine.
PERSONNES_VUES=0 pour tout couper (repli : OWL-ViT pour les objets, mouvements et visages pour le témoin)."""
import os
import numpy as np

DINO, SAM = "IDEA-Research/grounding-dino-tiny", "facebook/sam2.1-hiera-tiny"
PERSONNES = ("a person", "a cartoon character")
PAS, SEUIL_P, SEUIL_O = 1.5, 0.35, 0.3
_M, _MEMO = {}, {}


def actif(): return os.environ.get("PERSONNES_VUES", "1") != "0" and not _M.get("echec")


def _dino():
    if "dino" not in _M:
        from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
        _M["dino"] = (AutoProcessor.from_pretrained(DINO), AutoModelForZeroShotObjectDetection.from_pretrained(DINO).eval())
    return _M["dino"]


def _sam():
    if "sam" not in _M:
        from transformers import Sam2Model, Sam2Processor
        _M["sam"] = (Sam2Processor.from_pretrained(SAM), Sam2Model.from_pretrained(SAM).eval())
    return _M["sam"]


def _iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    i = max(0, x1 - x0) * max(0, y1 - y0)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.0


def sans_doublons(boites, seuil=0.5):
    """Boîtes [(score, [x0, y0, x1, y1])] : une seule par personne (une personne vue à la fois « person » et « cartoon character »)."""
    out = []
    for s, b in sorted(boites, key=lambda x: -x[0]):
        if all(_iou(b, o) < seuil for _, o in out): out.append((s, b))
    return out


def lire(video, duree_max=150):
    """[(instant, [boîte de personne…], [(objet, score)…])] une image toutes les PAS secondes ; [] si impossible. Gardé en mémoire."""
    if not actif() or not video or not os.path.exists(video): return []
    if video in _MEMO: return _MEMO[video]
    try:
        import cv2, torch, objets_vus
        from PIL import Image
        proc, mod = _dino()
        noms = list(objets_vus.CHERCHES)
        phrases = list(PERSONNES) + [objets_vus.CHERCHES[k] for k in noms]
        texte = ". ".join(phrases) + "."
        cap = cv2.VideoCapture(video)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        out, t = [], 0.5
        while t < min(duree_max, n / fps):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read()
            if not ok: break
            im = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
            with torch.no_grad():
                x = proc(images=im, text=texte, return_tensors="pt", size={"shortest_edge": 480, "longest_edge": 853})
                r = mod(**x)
                res = proc.post_process_grounded_object_detection(r, x["input_ids"], threshold=min(SEUIL_P, SEUIL_O), text_threshold=0.25,
                                                                  target_sizes=[im.size[::-1]])[0]
            labs = res.get("text_labels") or res.get("labels") or []
            pers, objs = [], []
            for s, l, b in zip(res["scores"].tolist(), labs, res["boxes"].tolist()):
                l = str(l).strip().lower()
                if any(p_ in l for p_ in ("person", "character")) and s >= SEUIL_P: pers.append((s, b))
                else:
                    k = next((k for k in noms if objets_vus.CHERCHES[k].lower().replace("a ", "", 1).replace("an ", "", 1) in l), None)
                    if k and s >= SEUIL_O: objs.append((k, round(float(s), 3)))
            out.append((round(t, 2), [b for _, b in sans_doublons(pers)], objs))
            t += PAS
        cap.release()
        _MEMO[video] = out
        print(f"  Grounding DINO : {len(out)} images regardées, jusqu'à {max((len(p) for _, p, _ in out), default=0)} personne(s) ensemble", flush=True)
        return out
    except Exception as e:
        print(f"  Grounding DINO indisponible ({str(e)[:120]})", flush=True); _M["echec"] = True
        return []


def nombre(video):
    """Personnes vues ENSEMBLE à l'image : le plus grand nombre vu sur 2 images au moins (une erreur isolée ne compte pas), ou None."""
    images = lire(video)
    if len(images) < 3: return None
    from collections import Counter
    c = Counter(len(p) for _, p, _ in images)
    bons = [k for k, v in c.items() if k >= 1 and v >= 2]
    return max(bons) if bons else None


def objets(video):
    """[(instant, objet, score)] au format de objets_vus.chercher, ou None si Grounding DINO n'a pas tourné."""
    images = lire(video)
    if not images: return None
    return [(t, o, s) for t, _, objs in images for o, s in objs]


def _plans(video, duree):
    try: c = __import__("plans_video").coupes(video) or []
    except Exception: c = []
    bornes = [0.0] + [float(x) for x in c if 0 < x < duree] + [duree]
    return list(zip(bornes[:-1], bornes[1:]))


def mouvements(video, duree_max=150, fps_m=8.0):
    """{plan: (début, fin, [instants], énergie [n_images, n_personnes])} : ce qui bouge dans chaque silhouette (SAM 2), personnes
    rangées de gauche à droite ; seulement les plans où 2 personnes ou plus sont vues ensemble."""
    images = lire(video)
    if not images: return {}
    import cv2, torch
    from PIL import Image
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; duree = min(duree_max, (cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / fps)
    out = {}
    try:
        sp, sm = _sam()
        for k, (a, b) in enumerate(_plans(video, duree)):
            dans = [(t, p) for t, p, _ in images if a <= t < b and len(p) >= 2]
            if not dans: continue
            t0, boites = max(dans, key=lambda x: len(x[1]))
            boites = sorted(boites, key=lambda bb: (bb[0] + bb[2]) / 2)[:4]
            cap.set(cv2.CAP_PROP_POS_MSEC, t0 * 1000); ok, f = cap.read()
            if not ok: continue
            im = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
            with torch.no_grad():
                xi = sp(images=im, input_boxes=[[list(map(float, bb)) for bb in boites]], return_tensors="pt")
                o = sm(**xi, multimask_output=False)
            M = sp.post_process_masks(o.pred_masks, xi["original_sizes"])[0][:, 0].numpy() > 0.5      # [personnes, H, W]
            if M.shape[0] < 2: continue
            petit = (160, int(160 * f.shape[0] / f.shape[1]))
            Mp = np.array([cv2.resize(m.astype(np.uint8), petit, interpolation=cv2.INTER_NEAREST) > 0 for m in M])
            fond = ~Mp.any(0)
            ts, E, prec = [], [], None
            t = a
            while t < b:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, g = cap.read()
                if not ok: break
                g = cv2.resize(cv2.cvtColor(g, cv2.COLOR_BGR2GRAY), petit).astype(np.float32)
                if prec is not None:
                    d = np.abs(g - prec); bruit = float(d[fond].mean()) if fond.any() else 0.0
                    E.append([max(0.0, float(d[m].mean()) - bruit) if m.any() else 0.0 for m in Mp]); ts.append(round(t, 3))
                prec = g; t += 1.0 / fps_m
            if len(E) >= 4: out[k] = (a, b, ts, np.array(E))
    finally: cap.release()
    return out


def temoin(video, mots, ph):
    """Témoin « qui dit cette phrase » : [(0 = personne la plus à gauche, 1…, ou None, certitude)] par phrase, ou None."""
    if not actif() or len(ph) < 3: return None
    try: mv = mouvements(video)
    except Exception as e:
        print(f"  SAM 2 indisponible ({str(e)[:120]})", flush=True); return None
    if not mv: return None
    out = []
    for p in ph:
        d, f = float(mots[p[0]]["s"]), float(mots[p[-1]]["e"])
        tot = None
        for a, b, ts, E in mv.values():
            sel = [i for i, t in enumerate(ts) if d <= t <= f]
            if sel:
                e = E[sel].mean(0)
                tot = e if tot is None or len(e) != len(tot) else tot + e
        if tot is None or len(tot) < 2 or tot.max() <= 0.3: out.append((None, 0.0)); continue
        o = np.argsort(-tot)
        w = float(min(1.0, (tot[o[0]] - tot[o[1]]) / (tot[o[0]] + 1e-6)))
        out.append((int(o[0]), w) if tot[o[0]] >= 1.3 * tot[o[1]] else (None, 0.0))
    lisibles = sum(1 for c, _ in out if c is not None)
    print(f"  SAM 2 : {lisibles}/{len(ph)} phrases où l'on voit qui bouge", flush=True)
    return out if lisibles >= 3 else None
