"""Dessins du JT (style cartoon simple) : plateau TV, duplex à l'Assemblée, 3 personnages fictifs (tête ronde, contour épais, air blasé)."""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops

W, H, S = 1080, 1920, 2
FB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'polices', 'Poppins-Bold.ttf')
NOIR = (28, 24, 26, 255)
TRAIT = (40, 36, 48, 255)

def P(*v): return [x * S for x in v]
def toile(): return Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
def fin(img): return np.array(img.resize((W, H), Image.LANCZOS))
def degrade(d, box, haut, bas):
    x0, y0, x1, y1 = box
    for y in range(int(y0), int(y1)):
        k = (y - y0) / max(1, (y1 - y0))
        d.line(P(x0, y, x1, y), fill=tuple(int(a * (1 - k) + b * k) for a, b in zip(haut, bas)) + (255,), width=S)

def lumiere(a, cx, cy, rx, ry, col, k):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    a[..., :3] = np.clip(a[..., :3] + np.exp(-(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2))[..., None] * np.array(col, np.float32) * k, 0, 255)

# ------------------------------------------------------------------ décors
def plateau(ecran="BUDGET 2027", teinte=(30, 60, 140)):
    img = toile(); d = ImageDraw.Draw(img)
    degrade(d, (0, 0, W, H), (18, 26, 60), (8, 10, 26))
    for k in range(7):                                                   # panneaux lumineux
        x = -40 + k * 170
        d.rounded_rectangle(P(x, 260, x + 130, 1150), 14 * S, fill=(40, 70, 160, 255), outline=(90, 140, 230, 255), width=3 * S)
    d.rounded_rectangle(P(150, 300, 930, 760), 22 * S, fill=(10, 16, 40, 255), outline=(230, 200, 80, 255), width=8 * S)   # grand écran
    from PIL import ImageFont
    t = 86
    while True:
        f = ImageFont.truetype(FB, t * S); w = d.textlength(ecran, font=f)
        if w < 700 * S or t < 40: break
        t -= 4; d.text(((W * S - w) / 2, 360 * S), ecran, font=f, fill=(240, 210, 80, 255))
    pts = [(260, 560), (380, 600), (480, 590), (590, 650), (700, 690), (820, 730)]
    d.line([v * S for p in pts for v in p], fill=(230, 70, 70, 255), width=12 * S, joint="curve")
    d.polygon(P(820, 730, 790, 700, 845, 705), fill=(230, 70, 70, 255))
    a = fin(img).astype(np.float32)
    lumiere(a, 540, 900, 520, 600, teinte, 0.9)
    return a.astype(np.uint8)

def bureau_plateau(couleur=(30, 40, 95)):
    img = toile(); d = ImageDraw.Draw(img)
    d.polygon(P(-30, 1300, W + 30, 1300, W + 120, H, -120, H), fill=couleur + (255,))
    d.rectangle(P(-30, 1282, W + 30, 1312), fill=(240, 205, 80, 255))
    d.rectangle(P(-30, 1312, W + 30, 1340), fill=(15, 20, 52, 255))
    for x in (120, 540, 960):
        d.ellipse(P(x - 70, 1390, x + 70, 1420), fill=(60, 80, 160, 255))
    return fin(img)

def assemblee():
    img = toile(); d = ImageDraw.Draw(img)
    degrade(d, (0, 0, W, 1250), (236, 222, 196), (214, 196, 166))
    for x in (60, 360, 720, 1020):                                         # colonnes
        d.rectangle(P(x - 55, 120, x + 55, 1250), fill=(244, 236, 220, 255), outline=TRAIT, width=5 * S)
        for k in range(-2, 3): d.line(P(x + k * 18, 160, x + k * 18, 1210), fill=(220, 208, 186, 255), width=4 * S)
        d.rectangle(P(x - 75, 100, x + 75, 140), fill=(236, 226, 206, 255), outline=TRAIT, width=5 * S)
        d.rectangle(P(x - 75, 1230, x + 75, 1270), fill=(236, 226, 206, 255), outline=TRAIT, width=5 * S)
    for x in (210, 870):                                                   # appliques dorées
        d.ellipse(P(x - 34, 420, x + 34, 488), fill=(255, 226, 140, 255), outline=(170, 130, 50, 255), width=5 * S)
    d.polygon(P(-40, 1270, W + 40, 1270, W + 200, H, -200, H), fill=(170, 40, 50, 255))                 # tapis rouge
    d.polygon(P(380, 1270, 700, 1270, 900, H, 180, H), fill=(190, 52, 60, 255))
    for k in range(6): d.line(P(-40, 1300 + k * 110, W + 40, 1300 + k * 110), fill=(150, 34, 44, 255), width=3 * S)
    a = fin(img).astype(np.float32)
    lumiere(a, 210, 450, 260, 260, (90, 70, 20), 0.6); lumiere(a, 870, 450, 260, 260, (90, 70, 20), 0.6)
    return a.astype(np.uint8)

# ------------------------------------------------------------------ têtes
def tete(c):
    CX, CY, R, PEAU = c["cx"], c["cy"], c["r"], c["peau"]
    img = toile(); d = ImageDraw.Draw(img)
    if c.get("cheveux_derriere"): c["cheveux_derriere"](d, c)
    for sd in (-1, 1):
        ex = CX + sd * R * 0.98
        d.ellipse(P(ex - 30, CY - 20, ex + 30, CY + 55), fill=PEAU + (255,), outline=NOIR, width=8 * S)
    d.ellipse(P(CX - R, CY - R, CX + R, CY + R), fill=PEAU + (255,), outline=NOIR, width=10 * S)
    om = toile(); ImageDraw.Draw(om).ellipse(P(CX - R + 40, CY - R + 50, CX + R + 20, CY + R + 10), fill=(200, 140, 110, 80))
    m = Image.new("L", om.size, 0); ImageDraw.Draw(m).ellipse(P(CX - R + 8, CY - R + 8, CX + R - 8, CY + R - 8), fill=255)
    m2 = Image.new("L", om.size, 0); ImageDraw.Draw(m2).ellipse(P(CX - R - 30, CY - R - 40, CX + R - 50, CY + R - 60), fill=255)
    om.putalpha(ImageChops.multiply(om.getchannel("A"), ImageChops.subtract(m, m2)))
    img.alpha_composite(om.filter(ImageFilter.GaussianBlur(6 * S))); d = ImageDraw.Draw(img)
    d.arc(P(CX - 22, CY + 0.15 * R, CX + 22, CY + 0.28 * R), 200, 340, fill=(190, 140, 110, 255), width=6 * S)
    bl = toile(); db = ImageDraw.Draw(bl)
    for sd in (-1, 1):
        db.ellipse(P(CX + sd * 0.58 * R - 46, CY + 0.25 * R, CX + sd * 0.58 * R + 46, CY + 0.40 * R), fill=(245, 120, 120, 90))
    img.alpha_composite(bl.filter(ImageFilter.GaussianBlur(5 * S))); d = ImageDraw.Draw(img)
    if c.get("cheveux"): c["cheveux"](d, c)
    if c.get("extra"): c["extra"](d, c)
    return img

def yeux(c, etat="ouvert", regard=0.0):
    CX, CY, R, PEAU = c["cx"], c["cy"], c["r"], c["peau"]
    img = toile(); d = ImageDraw.Draw(img); lid0 = c.get("paupiere", 6)
    for sd in (-1, 1):
        ex, ey = CX + sd * 0.37 * R, CY - 0.12 * R; ew = 0.18 * R
        if etat == "ferme":
            d.line(P(ex - ew, ey + 6, ex + ew, ey + 6), fill=NOIR, width=9 * S)
        else:
            h = 0.11 * R if etat != "grand" else 0.17 * R
            d.ellipse(P(ex - ew, ey - h, ex + ew, ey + h), fill=(255, 255, 255, 255), outline=NOIR, width=6 * S)
            px = ex + regard * ew * 0.45
            d.ellipse(P(px - 10, ey + 4, px + 10, ey + 24), fill=NOIR)
            lid = ey - (lid0 if etat != "grand" else h * 0.9)
            d.rectangle(P(ex - ew - 6, ey - h - 8, ex + ew + 6, lid), fill=PEAU + (255,))
            d.line(P(ex - ew - 4, lid, ex + ew + 4, lid), fill=NOIR, width=10 * S)
        sc = c.get("sourcil")
        if sc: d.line(P(ex - ew * 0.9, ey - 0.22 * R - sd * sc * 0, ex + ew * 0.9, ey - 0.22 * R + sd * sc), fill=NOIR, width=9 * S)
    if c.get("lunettes"):
        for sd in (-1, 1):
            ex, ey = CX + sd * 0.37 * R, CY - 0.12 * R
            d.rounded_rectangle(P(ex - 0.24 * R, ey - 0.16 * R, ex + 0.24 * R, ey + 0.16 * R), 18 * S, outline=NOIR, width=7 * S)
        d.line(P(CX - 0.13 * R, CY - 0.12 * R, CX + 0.13 * R, CY - 0.12 * R), fill=NOIR, width=7 * S)
    return img

def bouche(c, n, v=0):
    CX, CY, R = c["cx"], c["cy"], c["r"]
    img = toile(); d = ImageDraw.Draw(img); mx, my = CX + 6, CY + 0.55 * R
    if n == 0:
        k = c.get("sourire", 0)
        d.line(P(mx - 0.11 * R, my + k, mx, my, mx + 0.1 * R, my + k - 3), fill=NOIR, width=8 * S, joint="curve"); return img
    w = (0.13 * R + n * 6) * (0.7 if v else 1); h = 8 + n * 0.03 * R * (1.25 if v else 1)
    d.rounded_rectangle(P(mx - w, my - h * 0.4, mx + w, my + h), int(min(w, h) * 0.8) * S, fill=(80, 30, 36, 255), outline=NOIR, width=7 * S)
    if n >= 3: d.ellipse(P(mx - w * 0.5, my + h * 0.35, mx + w * 0.5, my + h * 0.95), fill=(220, 110, 110, 255))
    return img

def sprites(c):
    base = tete(c); out = {}
    CX, CY, R = c["cx"], c["cy"], c["r"]
    bx0, by0, bx1, by1 = int(CX - R - 90), int(CY - R - 120), int(CX + R + 90), int(CY + R + 60)
    for e, rgs in (("ouvert", (-1.0, 0.0, 1.0)), ("ferme", (0.0,)), ("grand", (0.0,))):
        for rg in rgs:
            t = base.copy(); t.alpha_composite(yeux(c, e, rg))
            for n in range(6):
                for v in ((0,) if n == 0 else (0, 1)):
                    x = t.copy(); x.alpha_composite(bouche(c, n, v))
                    out[(e, rg, n, v)] = np.array(x.resize((W, H), Image.LANCZOS))[by0:by1, bx0:bx1]
    return out, (bx0, by0)

# ------------------------------------------------------------------ coiffures et accessoires
def meches_grises(d, c):
    CX, CY, R = c["cx"], c["cy"], c["r"]; G = (205, 205, 212, 255)
    for sd in (-1, 1):                                                       # tempes grises
        d.ellipse(P(CX + sd * 0.93 * R - 0.16 * R, CY - 0.62 * R, CX + sd * 0.93 * R + 0.16 * R, CY + 0.02 * R), fill=G, outline=NOIR, width=7 * S)
    d.chord(P(CX - 1.0 * R, CY - 1.12 * R, CX + 1.0 * R, CY - 0.30 * R), 180, 360, fill=G, outline=NOIR, width=8 * S)
    d.pieslice(P(CX - 0.95 * R, CY - 0.95 * R, CX + 0.1 * R, CY - 0.25 * R), 180, 300, fill=G)     # raie sur le côté
    d.arc(P(CX - 0.95 * R, CY - 0.95 * R, CX + 0.1 * R, CY - 0.25 * R), 180, 300, fill=NOIR, width=7 * S)
    for k in range(3): d.arc(P(CX - 0.1 * R + k * 0.25 * R, CY - 1.0 * R, CX + 0.25 * R + k * 0.25 * R, CY - 0.6 * R), 200, 320, fill=(150, 150, 160, 255), width=5 * S)

def carre_brun_derriere(d, c):
    CX, CY, R = c["cx"], c["cy"], c["r"]
    d.rounded_rectangle(P(CX - 1.12 * R, CY - 1.08 * R, CX + 1.12 * R, CY + 0.62 * R), int(0.6 * R) * S, fill=(110, 70, 45, 255), outline=NOIR, width=8 * S)
def frange_brune(d, c):
    CX, CY, R = c["cx"], c["cy"], c["r"]
    d.chord(P(CX - 1.0 * R, CY - 1.06 * R, CX + 1.0 * R, CY - 0.18 * R), 180, 360, fill=(110, 70, 45, 255), outline=NOIR, width=8 * S)

def crane_sueur(d, c):
    CX, CY, R = c["cx"], c["cy"], c["r"]
    for sd in (-1, 1):
        d.ellipse(P(CX + sd * 0.95 * R - 0.12 * R, CY - 0.45 * R, CX + sd * 0.95 * R + 0.12 * R, CY - 0.05 * R), fill=(110, 100, 95, 255), outline=NOIR, width=6 * S)
    gx, gy = CX + 0.68 * R, CY - 0.55 * R
    d.polygon(P(gx, gy - 34, gx - 18, gy + 6, gx + 18, gy + 6), fill=(170, 215, 255, 255))
    d.ellipse(P(gx - 18, gy - 12, gx + 18, gy + 24), fill=(170, 215, 255, 255), outline=(80, 130, 190, 255), width=3 * S)

# ------------------------------------------------------------------ corps
def costume(c, veste, cravate=None, chemise=(245, 245, 245), larg=230):
    img = toile(); d = ImageDraw.Draw(img); CX, CY, R = c["cx"], c["cy"], c["r"]
    y0 = CY + R * 0.82
    d.rounded_rectangle(P(CX - larg, y0, CX + larg, H + 100), 140 * S, fill=veste + (255,), outline=NOIR, width=9 * S)
    d.polygon(P(CX - 70, y0 + 2, CX + 70, y0 + 2, CX, y0 + 170), fill=chemise + (255,), outline=NOIR, width=6 * S)
    if cravate:
        d.polygon(P(CX - 20, y0 + 20, CX + 20, y0 + 20, CX + 32, y0 + 200, CX, y0 + 240, CX - 32, y0 + 200), fill=cravate + (255,), outline=NOIR, width=5 * S)
    for sd in (-1, 1):
        d.line(P(CX + sd * 70, y0 + 2, CX + sd * 25, y0 + 260), fill=NOIR, width=7 * S)
    return fin(img)

def trench_micro(c):
    img = toile(); d = ImageDraw.Draw(img); CX, CY, R = c["cx"], c["cy"], c["r"]
    y0 = CY + R * 0.82; T = (196, 164, 112, 255)
    d.rounded_rectangle(P(CX - 300, y0, CX + 300, H + 100), 170 * S, fill=T, outline=NOIR, width=9 * S)
    d.polygon(P(CX - 70, y0, CX + 70, y0, CX, y0 + 150), fill=(250, 250, 250, 255), outline=NOIR, width=6 * S)
    for sd in (-1, 1):                                                        # revers du trench
        d.polygon(P(CX + sd * 70, y0, CX + sd * 170, y0 + 30, CX + sd * 110, y0 + 150, CX + sd * 20, y0 + 230), fill=(176, 144, 94, 255), outline=NOIR, width=6 * S)
    for k in range(2):
        for sd in (-1, 1): d.ellipse(P(CX + sd * 70 - 14, y0 + 300 + k * 110, CX + sd * 70 + 14, y0 + 328 + k * 110), fill=(90, 70, 40, 255))
    mx, my = CX + 250, y0 + 70                                              # micro « DIRECT »
    d.rounded_rectangle(P(mx - 22, my, mx + 22, my + 230), 10 * S, fill=(40, 40, 46, 255), outline=NOIR, width=5 * S)
    d.ellipse(P(mx - 48, my - 90, mx + 48, my + 6), fill=(70, 70, 80, 255), outline=NOIR, width=6 * S)
    d.rectangle(P(mx - 40, my + 10, mx + 40, my + 60), fill=(220, 40, 50, 255), outline=NOIR, width=4 * S)
    d.ellipse(P(mx - 52, my + 110, mx + 30, my + 200), fill=c["peau"] + (255,), outline=NOIR, width=6 * S)   # main
    return fin(img)

def moustache(d, c):
    CX, CY, R = c["cx"], c["cy"], c["r"]; B = (95, 60, 40, 255)
    d.chord(P(CX - 0.98 * R, CY - 1.1 * R, CX + 0.98 * R, CY - 0.25 * R), 180, 360, fill=B, outline=NOIR, width=8 * S)   # brushing
    d.pieslice(P(CX - 0.4 * R, CY - 1.25 * R, CX + 0.9 * R, CY - 0.45 * R), 190, 330, fill=B, outline=NOIR, width=7 * S)
    my = CY + 0.4 * R
    for sd in (-1, 1):
        d.chord(P(CX + (sd - 1) * 0.2 * R, my - 0.09 * R, CX + (sd + 1) * 0.2 * R, my + 0.13 * R), 180, 360, fill=B, outline=NOIR, width=6 * S)

# ------------------------------------------------------------------ casting fictif
def casting(sk=None):
    sk = sk or {}
    ecran = sk.get("ecran") or "L'ACTU"
    pres = dict(nom="Jean-Michel Plateau", role="Présentateur", couleur=(30, 90, 200), cx=540, cy=820, r=270,
                peau=(236, 180, 136), cheveux=meches_grises, paupiere=4, sourire=2)
    pres["corps"] = costume(pres, (26, 34, 80), cravate=(200, 30, 45), larg=250); pres["fond"] = plateau(ecran); pres["devant"] = bureau_plateau()
    env = dict(nom="Martine Couloir", role=f"Envoyée spéciale (fictive) · {sk.get('lieu_direct') or 'Assemblée'}", couleur=(200, 30, 45),
               cx=470, cy=860, r=245, peau=(250, 216, 184), cheveux_derriere=carre_brun_derriere, cheveux=frange_brune, paupiere=2, sourire=0, direct=True)
    env["corps"] = trench_micro(env); env["fond"] = assemblee(); env["devant"] = None
    look = sk.get("invite_look", "chauve")
    inv = dict(nom=sk.get("invite_nom") or "Hubert Rustine", role=sk.get("invite_role") or "Expert (fictif)", couleur=(110, 110, 125),
               cx=560, cy=830, r=255, peau=(240, 200, 168), paupiere=8, sourire=-6, sourcil=-10)
    if look == "moustache":
        inv.update(cheveux=moustache, peau=(232, 186, 150), paupiere=5, sourire=3, sourcil=8, couleur=(150, 70, 40))
        inv["corps"] = costume(inv, (90, 40, 30), cravate=(230, 190, 60), larg=245)
    else:
        inv.update(extra=crane_sueur, lunettes=True)
        inv["corps"] = costume(inv, (110, 112, 122), cravate=(70, 110, 170), larg=240)
    inv["fond"] = plateau(ecran, (40, 30, 90)); inv["devant"] = bureau_plateau((60, 50, 100))
    return {"presentateur": pres, "envoyee": env, "invite": inv}
