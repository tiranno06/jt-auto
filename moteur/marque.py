"""Charte graphique de la chaîne « Petits.Dramas » : nom, couleurs, logo, signature de fin de vidéo, filigrane.

Le logo reprend le physique de nos personnages (marionnette.py) : la grosse tête ronde blanche de Jojo, bonnet orange,
en plein « petit drame » (grands yeux, larme, bouche en O) sur le fond jaune à rayons des cartons de transition.
Tout est dessiné par le code : aucune image externe, aucun droit à payer."""
import os
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

ICI = os.path.dirname(os.path.abspath(__file__))
NOM = "Petits.Dramas"
COMPTE = "@petits.dramas"
POLICE = os.path.join(ICI, "..", "polices", "Poppins-Bold.ttf")      # police unique de la chaîne
JAUNE, JAUNE_FONCE, ENCRE, BLANC, CORAIL = (255, 208, 40), (255, 190, 10), (20, 20, 24), (255, 255, 255), (240, 90, 80)

def _rayons(img, cx, cy, n=24, r=4000):
    d = ImageDraw.Draw(img); import math
    for k in range(n):
        a = k * 2 * math.pi / n
        d.polygon([(cx, cy), (cx + r * math.cos(a), cy + r * math.sin(a)), (cx + r * math.cos(a + math.pi / n * 0.55), cy + r * math.sin(a + math.pi / n * 0.55))], fill=JAUNE_FONCE)

def tete(taille, t=0.0, larme=0.35):
    """Tête de Jojo en « petit drame », sur fond transparent (RGBA, carré `taille`)."""
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
    """Icône carrée de l'appli / photo de profil : fond jaune à rayons + tête de Jojo."""
    S = 1024; img = Image.new("RGB", (S, S), JAUNE); _rayons(img, S / 2, S * 0.62)
    m = int(S * (marge + 0.11)); t = tete(S - 2 * m)
    img.paste(t, (m, m), t)
    if rond and not marge:
        masque = Image.new("L", (S, S), 0); ImageDraw.Draw(masque).rounded_rectangle((0, 0, S - 1, S - 1), int(S * 0.22), fill=255)
        fond = Image.new("RGB", (S, S), (14, 15, 23)); fond.paste(img, (0, 0), masque); img = fond
    return img.resize((taille, taille), Image.LANCZOS)

def _texte_contour(d, xy, txt, f, couleur=BLANC, contour=ENCRE, ep=10):
    d.text(xy, txt, font=f, fill=couleur, stroke_width=ep, stroke_fill=contour)

def signature(W, H, sous_titre="Abonne-toi pour la suite !"):
    """Carton de fin identique sur toutes les vidéos (charte) : rayons jaunes, tête de Jojo, nom de la chaîne, appel à s'abonner."""
    img = Image.new("RGB", (W, H), JAUNE); _rayons(img, W / 2, H * 0.4)
    t = tete(int(W * 0.62)); img.paste(t, (int(W * 0.19), int(H * 0.14)), t)
    d = ImageDraw.Draw(img); f = ImageFont.truetype(POLICE, 118); f2 = ImageFont.truetype(POLICE, 64)
    w = d.textlength(NOM, font=f); _texte_contour(d, ((W - w) / 2, H * 0.56), NOM, f, ep=13)
    if sous_titre:
        w2 = d.textlength(sous_titre, font=f2)
        d.rounded_rectangle(((W - w2) / 2 - 40, H * 0.69 - 18, (W + w2) / 2 + 40, H * 0.69 + 92), 50, fill=ENCRE)
        d.text(((W - w2) / 2, H * 0.69), sous_titre, font=f2, fill=JAUNE)
    return np.array(img)

def filigrane(hauteur=58):
    """Petit logo + nom en haut à gauche pendant la vidéo (RGBA float32, prêt pour jt.poser)."""
    f = ImageFont.truetype(POLICE, int(hauteur * 0.62)); d0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    w = int(d0.textlength(NOM, font=f)) + hauteur + 30
    img = Image.new("RGBA", (w, hauteur), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, hauteur - 1), hauteur // 2, fill=(255, 255, 255, 170))
    t = tete(hauteur - 6); img.paste(t, (4, 3), t)
    d.text((hauteur + 6, hauteur * 0.14), NOM, font=f, fill=(20, 20, 24, 230))
    return np.array(img).astype(np.float32)
