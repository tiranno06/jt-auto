"""Charte graphique de la chaîne « Petits.Dramas » : nom, couleurs, logo, signature de fin de vidéo, filigrane.

Logo (nouveau, 15 novembre 2026, demande de l'auteur : plus de Jojo) : deux personnages dans le style croquis des vidéos sur les
sons TikTok, en plein « petit drame » (elle en colère, lui choqué, une goutte de sueur), dans un médaillon rond sur papier, sur le
fond jaune à rayons de la chaîne. L'ancienne tête de Jojo (marionnette.py) reste dans `tete_jojo`, plus utilisée.
Tout est dessiné par le code : aucune image externe, aucun droit à payer."""
import os
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

ICI = os.path.dirname(os.path.abspath(__file__))
NOM = "Petits.Dramas"
COMPTE = "@petitsdramas"                                                   # adresse réelle de la chaîne (TikTok)
POLICE = os.path.join(ICI, "..", "polices", "Poppins-Bold.ttf")      # police unique de la chaîne
JAUNE, JAUNE_FONCE, ENCRE, BLANC, CORAIL = (255, 208, 40), (255, 190, 10), (20, 20, 24), (255, 255, 255), (240, 90, 80)

def _rayons(img, cx, cy, n=24, r=4000):
    d = ImageDraw.Draw(img); import math
    for k in range(n):
        a = k * 2 * math.pi / n
        d.polygon([(cx, cy), (cx + r * math.cos(a), cy + r * math.sin(a)), (cx + r * math.cos(a + math.pi / n * 0.55), cy + r * math.sin(a + math.pi / n * 0.55))], fill=JAUNE_FONCE)

_DUO = {}


def duo():
    """Les deux personnages du logo (style croquis), médaillon rond RGBA 1024 px, dessiné une fois puis gardé."""
    if "m" in _DUO: return _DUO["m"]
    import marionnette as M, humain as HU, croquis as C, perso_croquis as P
    img = C.papier(1100, 1100, graine=5)
    Ff = dict(HU.creer(7, genre="f", age=28, cheveux="queue"), silhouette="petit")
    Fh = dict(HU.creer(2, genre="h", age=28), silhouette="petit")
    pf = dict(M.pose_neutre(), x=330, y=1380, s=1.0, t=0.0, emo="colere", bouche=0.8, viseme="A",
              costume={"haut": "tshirt", "c_haut": (240, 90, 80)}, regard=(0.6, 0.0))
    ph = dict(M.pose_neutre(), x=770, y=1380, s=1.0, t=0.0, emo="choc", bouche=0.8, viseme="O",
              costume={"haut": "capuche", "c_haut": (60, 120, 220)}, effets=("sueur",), regard=(-0.6, 0.0))
    P.dessiner(img, Ff, HU._pose(Ff, pf)); P.dessiner(img, Fh, HU._pose(Fh, ph))
    x0, y0, c = 60, 270, 980                                                   # les deux têtes au centre du médaillon
    carre = Image.fromarray(np.ascontiguousarray(img[y0:y0 + c, x0:x0 + c])).resize((1024, 1024), Image.LANCZOS).convert("RGBA")
    S = 1024; ep = 34
    masque = Image.new("L", (S, S), 0); ImageDraw.Draw(masque).ellipse((ep, ep, S - 1 - ep, S - 1 - ep), fill=255)
    m = Image.new("RGBA", (S, S), (0, 0, 0, 0)); ImageDraw.Draw(m).ellipse((0, 0, S - 1, S - 1), fill=ENCRE + (255,))
    m.paste(carre, (0, 0), masque)
    _DUO["m"] = m
    return m


def tete(taille, t=0.0, larme=0.35):
    """Image du logo sur fond transparent (RGBA, carré `taille`) : le médaillon des deux personnages (voir `duo`)."""
    return duo().resize((taille, taille), Image.LANCZOS)


def tete_jojo(taille, t=0.0, larme=0.35):
    """ANCIEN logo (mis de côté le 15 novembre 2026) : tête de Jojo en « petit drame », sur fond transparent."""
    import marionnette as M
    S = 1024; img = np.full((1500, S, 3), 255, np.uint8); img[:] = (1, 2, 3)        # couleur clé pour la transparence
    p = M.pose_neutre(); p.update(x=S / 2, y=1420, s=2.05, yeux="grands", sourcils="triste", forme="o", bouche=0.0,
                                  regard=(0.0, -0.2), effets=(), t=t)
    s_ = 2.05; cx, cy = S / 2, 800; rx = ry = 150 * s_; ep = 8 * s_                 # tête seule (sans corps) : contour puis blanc
    M._ellipse(img, (cx, cy), (rx + ep, ry + ep), 0, M.TRAIT); M._ellipse(img, (cx, cy), (rx, ry), 0, M.BLANC)
    M._visage(img, (cx, cy), rx, ry, s_, p, M.PERSOS["bonnet"]); M._accessoire(img, (cx, cy), rx, ry, s_, p, M.PERSOS["bonnet"])
    M._ellipse(img, (cx + 106 * 2.05, cy + 70 * 2.05 + larme * 60), (19 * 2.05, 27 * 2.05), 0, M.TRAIT)   # grosse larme
    M._ellipse(img, (cx + 106 * 2.05, cy + 70 * 2.05 + larme * 60), (13 * 2.05, 20 * 2.05), 0, (90, 170, 245))
    a = (np.abs(img.astype(int) - (1, 2, 3)).sum(2) > 6).astype(np.uint8) * 255
    e = ep + 4
    ys = np.where(a.any(1))[0]; haut = int(ys[0]); bas = int(cy + ry + e + 4)                  # de la pointe du bonnet au menton
    cote = bas - haut; g = int(cx - cote / 2)
    carre = np.zeros((cote, cote, 4), np.uint8); x0, x1 = max(0, g), min(S, g + cote)
    carre[:, x0 - g:x1 - g, :3] = img[haut:bas, x0:x1]; carre[:, x0 - g:x1 - g, 3] = a[haut:bas, x0:x1]
    rgba = carre
    return Image.fromarray(rgba, "RGBA").resize((taille, taille), Image.LANCZOS)

def logo(taille, marge=0.0, rond=True):
    """Icône carrée de l'appli / photo de profil : fond jaune à rayons + médaillon des deux personnages."""
    S = 1024; img = Image.new("RGB", (S, S), JAUNE); _rayons(img, S / 2, S / 2)
    m = int(S * (marge + 0.09)); t = tete(S - 2 * m)
    img.paste(t, (m, m), t)
    if rond and not marge:
        masque = Image.new("L", (S, S), 0); ImageDraw.Draw(masque).rounded_rectangle((0, 0, S - 1, S - 1), int(S * 0.22), fill=255)
        fond = Image.new("RGB", (S, S), (14, 15, 23)); fond.paste(img, (0, 0), masque); img = fond
    return img.resize((taille, taille), Image.LANCZOS)

def _texte_contour(d, xy, txt, f, couleur=BLANC, contour=ENCRE, ep=10):
    d.text(xy, txt, font=f, fill=couleur, stroke_width=ep, stroke_fill=contour)

def signature(W, H, sous_titre="Abonne-toi pour la suite !"):
    """Carton de fin identique sur toutes les vidéos (charte) : rayons jaunes, médaillon du logo, nom de la chaîne, appel à s'abonner."""
    img = Image.new("RGB", (W, H), JAUNE); _rayons(img, W / 2, H * 0.4)
    t = tete(int(W * 0.62)); img.paste(t, (int(W * 0.19), int(H * 0.14)), t)
    d = ImageDraw.Draw(img); f = ImageFont.truetype(POLICE, 118); f2 = ImageFont.truetype(POLICE, 64)
    w = d.textlength(NOM, font=f); _texte_contour(d, ((W - w) / 2, H * 0.56), NOM, f, ep=13)
    if sous_titre:
        taille = 64
        while d.textlength(sous_titre, font=f2) > W - 140 and taille > 34:     # texte long (« Épisode 3 bientôt… ») : il rapetisse pour tenir
            taille -= 2; f2 = ImageFont.truetype(POLICE, taille)
        w2 = d.textlength(sous_titre, font=f2)
        d.rounded_rectangle(((W - w2) / 2 - 40, H * 0.69 - 18, (W + w2) / 2 + 40, H * 0.69 + 92), 50, fill=ENCRE)
        d.text(((W - w2) / 2, H * 0.69), sous_titre, font=f2, fill=JAUNE)
    return np.array(img)

def compte():
    """Nom du compte TikTok de la chaîne (réglage TIKTOK_COMPTE, sinon @petits.dramas) : on le retrouve si la vidéo est repartagée."""
    c = (os.environ.get("TIKTOK_COMPTE") or "").strip().lstrip("@")
    return "@" + c if c else COMPTE


def filigrane(hauteur=58):
    """Petit logo + nom du COMPTE en haut à gauche pendant la vidéo (RGBA float32, prêt pour jt.poser). Dessous, un petit bouton
    rouge « + Abonne-toi » façon TikTok (demande de l'auteur du 23 novembre 2026 ; texte : réglage ABONNE_HAUT, « 0 » pour l'enlever)."""
    f = ImageFont.truetype(POLICE, int(hauteur * 0.62)); d0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    NOM_ = compte()
    w = int(d0.textlength(NOM_, font=f)) + hauteur + 30
    abo = (os.environ.get("ABONNE_HAUT") or "+ Abonne-toi").strip()
    h2 = int(hauteur * 0.72) if abo != "0" else 0; f2 = ImageFont.truetype(POLICE, int(hauteur * 0.44))
    w2 = int(d0.textlength(abo, font=f2)) + int(hauteur * 0.7) if h2 else 0
    img = Image.new("RGBA", (max(w, w2), hauteur + (h2 + 8 if h2 else 0)), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, hauteur - 1), hauteur // 2, fill=(255, 255, 255, 170))
    t = tete(hauteur - 6); img.paste(t, (4, 3), t)
    d.text((hauteur + 6, hauteur * 0.14), NOM_, font=f, fill=(20, 20, 24, 230))
    if h2:                                                                 # bouton rouge TikTok sous le nom, aligné sur le texte du nom
        x0, y0 = int(hauteur * 0.55), hauteur + 8
        d.rounded_rectangle((x0, y0, x0 + w2 - 1, y0 + h2 - 1), h2 // 2, fill=(254, 44, 85, 235))
        d.text((x0 + w2 / 2, y0 + h2 / 2), abo, font=f2, fill=(255, 255, 255, 255), anchor="mm")
        img = img.crop((0, 0, max(w, x0 + w2), img.height))
    return np.array(img).astype(np.float32)
