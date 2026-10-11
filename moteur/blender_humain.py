"""Script Blender (exécuté par le module bpy, Python 3.11) : personnages humains en VRAIE 3D, rendus image par image.

Appelé par rendu3d.py : python3.11 blender_humain.py travail.json
travail.json = {"sortie": dossier, "largeur", "hauteur", "echantillons", "roles": {role: {"fiche": …, "costume": …, "poses": [pose, …]}}}
Pour chaque rôle et chaque image : rend le personnage seul sur fond transparent (PNG), vu de face, caméra orthographique,
pieds à un endroit fixe de l'image (rendu3d.py le replace ensuite dans le décor, à la bonne taille).

Le personnage est construit en 3D d'après la même fiche que le dessin 2D (humain.py) : genre, âge, corpulence, taille, peau,
yeux, cheveux, barbe, lunettes, tenue (couleurs du haut, du bas, des chaussures). Formes lissées (subdivision), matières
(peau légèrement translucide, tissus mats, cheveux), éclairage à trois lumières, ombres douces (Cycles).
Il est animé par les mêmes poses que le dessin : bras (épaule, coude), mains, tête penchée, épaules, buste, bouche (visèmes,
ouverture), paupières, sourcils (hauteur, colère, tristesse), regard. Les poses identiques ne sont rendues qu'une fois."""
import json, math, os, shutil, sys

import bpy, bmesh
from mathutils import Vector

def _moitie_haute(o):
    """Ne garde que la moitié haute d'une sphère (paupière en forme de coque)."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.02], context="VERTS"); bm.to_mesh(o.data); bm.free()

def _mat(nom, couleur, rugosite=0.6, ssr=0.0, emission=None):
    m = bpy.data.materials.new(nom); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*[(c / 255) ** 2.2 for c in couleur], 1.0)
    b.inputs["Roughness"].default_value = rugosite
    if ssr and "Subsurface Weight" in b.inputs: b.inputs["Subsurface Weight"].default_value = ssr; b.inputs["Subsurface Radius"].default_value = (0.4, 0.2, 0.1)
    return m

def _lisse(o, niveaux=2):
    m = o.modifiers.new("lisse", "SUBSURF"); m.levels = niveaux; m.render_levels = niveaux
    bpy.context.view_layer.objects.active = o; bpy.ops.object.shade_smooth()

def _sphere(nom, loc, taille, mat, parent=None, lisse=True):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=28, radius=1, location=loc)
    o = bpy.context.object; o.name = nom; o.scale = taille; o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    if parent: _parent(o, parent)
    return o

def _cube(nom, loc, taille, mat, parent=None, niveaux=1):
    bpy.ops.mesh.primitive_cube_add(size=2, location=loc); o = bpy.context.object; o.name = nom; o.scale = taille; o.data.materials.append(mat)
    _lisse(o, niveaux)
    if parent: _parent(o, parent)
    return o

def _cylindre(nom, a, b, r1, r2, mat, parent=None, bouts=True):
    """Membre fuselé de a à b (cône tronqué arrondi)."""
    a, b = Vector(a), Vector(b); d = b - a
    bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=r1, radius2=r2, depth=d.length, location=(a + b) / 2)
    o = bpy.context.object; o.name = nom; o.data.materials.append(mat)
    o.rotation_mode = "QUATERNION"; o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d)
    bpy.context.view_layer.objects.active = o; bpy.ops.object.shade_smooth()     # pas de subdivision : la forme garde son épaisseur
    for p_ in ((a, b) if bouts else ()): _sphere(nom + "_bout", p_, (r1 if p_ == a else r2,) * 3, mat, parent)
    if parent: _parent(o, parent)
    return o

def _vide(nom, loc, parent=None):
    o = bpy.data.objects.new(nom, None); bpy.context.collection.objects.link(o); o.location = loc; bpy.context.view_layer.update()
    if parent: _parent(o, parent)
    bpy.context.view_layer.update(); o["z0"] = o.location.z; return o

def _parent(o, p):
    mw = o.matrix_world.copy(); o.parent = p; o.matrix_parent_inverse = p.matrix_world.inverted(); o.matrix_world = mw

def construire(fiche, costume):
    """Le personnage 3D (pieds en z=0, face à la caméra qui regarde vers +y). Renvoie les articulations à animer."""
    bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete()
    for b_ in (bpy.data.meshes, bpy.data.materials): [b_.remove(x) for x in list(b_)]
    T = 1.75 * fiche["taille"]; hh = T / 6.6; corp = fiche["corpulence"]; fem = fiche["genre"] == "f"
    peau = _mat("peau", fiche["peau"], 0.45, 0.15)
    c_haut = costume.get("c_haut") or (120, 140, 170)
    if costume.get("haut") == "blouse": c_haut = (244, 246, 250)
    haut = _mat("haut", c_haut, 0.85); bas = _mat("bas", costume.get("c_bas") or (60, 70, 90), 0.8)
    chauss = _mat("chaussures", costume.get("c_chaussures") or (50, 40, 35), 0.4)
    cheveux = _mat("cheveux", fiche["c_cheveux"], 0.55); blanc = _mat("blanc_oeil", (245, 243, 238), 0.2)
    iris = _mat("iris", fiche["iris"], 0.3); noir = _mat("pupille", (12, 10, 12), 0.2); bouche = _mat("bouche", (70, 28, 32), 0.5)
    levres = _mat("levres", tuple(int(a * 0.6 + b * 0.4) for a, b in zip(fiche["peau"], (190, 100, 100))), 0.4)
    racine = _vide("racine", (0, 0, 0))
    # jambes et chaussures
    l_ha = hh * (0.66 if not fem else 0.8) * (1 + 0.35 * corp) / 2.2
    jupe = costume.get("bas") == "jupe" or costume.get("haut") == "robe"
    for sg in (-1, 1):
        mat_j = peau if jupe else bas
        _cylindre(f"cuisse{sg}", (sg * l_ha, 0, hh * 3.25), (sg * l_ha * 1.02, 0, hh * 1.7), hh * (0.3 + 0.07 * corp), hh * 0.19, mat_j, racine)
        _cylindre(f"tibia{sg}", (sg * l_ha * 1.02, 0, hh * 1.7), (sg * l_ha * 1.04, 0, hh * 0.22), hh * 0.19, hh * 0.12, peau if (jupe or costume.get("bas") == "short") else bas, racine)
        _cube(f"pied{sg}", (sg * l_ha * 1.05, -hh * 0.14, hh * 0.1), (hh * 0.16, hh * 0.32, hh * 0.1), chauss, racine)
    # buste, hanches, cou
    l_ep = hh * (0.98 if not fem else 0.82) * (1 + 0.22 * corp) / 2.3
    bassin = _cube("bassin", (0, 0, hh * 3.4), (l_ha * 2.1, hh * 0.4, hh * 0.45), bas if not costume.get("haut") == "robe" else haut, racine)
    torse = _vide("torse", (0, 0, hh * 3.3), racine)
    _cube("buste", (0, 0, hh * 4.5), (l_ep * 1.35, hh * 0.45 * (1 + 0.3 * corp), hh * 1.05), haut, torse)
    _cube("taille", (0, 0, hh * 3.75), (l_ep * 1.1, hh * 0.42 * (1 + 0.3 * corp), hh * 0.45), haut, torse)
    for sg in (-1, 1): _sphere(f"epaule_rond{sg}", (sg * l_ep * 1.15, 0, hh * 5.15), (hh * 0.24, hh * 0.24, hh * 0.22), haut, torse)
    if jupe: _cylindre("jupe", (0, 0, hh * 3.6), (0, 0, hh * 2.0), l_ha * 2.0, l_ha * 2.7, bas if costume.get("bas") == "jupe" else haut, racine, bouts=False)
    if fem: [_sphere(f"poitrine{sg}", (sg * l_ep * 0.42, -hh * 0.25, hh * 4.75), (hh * 0.2, hh * 0.16, hh * 0.18), haut, torse) for sg in (-1, 1)]
    _cylindre("cou", (0, 0, hh * 5.3), (0, 0, hh * 5.9), hh * 0.17, hh * 0.15, peau, torse, bouts=False)
    # tête : crâne, mâchoire, nez, oreilles, yeux, paupières, sourcils, bouche, cheveux
    tete = _vide("tete", (0, 0, hh * 5.9), torse)
    zt = hh * 6.1
    _sphere("crane", (0, 0, zt), (hh * 0.4, hh * 0.44, hh * 0.52), peau, tete)
    _sphere("machoire", (0, -hh * 0.05, zt - hh * 0.2), (hh * (0.33 if fem else 0.37), hh * 0.36, hh * 0.32), peau, tete)
    _sphere("nez", (0, -hh * 0.43, zt - hh * 0.07), (hh * 0.045, hh * 0.06, hh * 0.1), peau, tete)
    for sg in (-1, 1): _sphere(f"oreille{sg}", (sg * hh * 0.4, 0, zt), (hh * 0.04, hh * 0.08, hh * 0.11), peau, tete)
    yeux, paupieres, sourcils, iris_o = [], [], [], []
    for sg in (-1, 1):
        oc = (sg * hh * 0.15, -hh * 0.37, zt + hh * 0.05)
        y = _sphere(f"oeil{sg}", oc, (hh * 0.065, hh * 0.05, hh * 0.05), blanc, tete); yeux.append(y)
        piv = _vide(f"regard{sg}", oc, tete)
        ir = _sphere(f"iris{sg}", (oc[0], oc[1] - hh * 0.042, oc[2]), (hh * 0.032, hh * 0.012, hh * 0.032), iris, piv)
        _sphere(f"pupille{sg}", (oc[0], oc[1] - hh * 0.05, oc[2]), (hh * 0.015, hh * 0.008, hh * 0.015), noir, piv); iris_o.append(piv)
        pp = _vide(f"paupiere_piv{sg}", oc, tete)
        pa = _sphere(f"paupiere{sg}", oc, (hh * 0.07, hh * 0.056, hh * 0.056), peau, pp)
        _moitie_haute(pa); paupieres.append(pp)
        sp = _vide(f"sourcil_piv{sg}", (sg * hh * 0.15, -hh * 0.4, zt + hh * 0.17), tete)
        _cube(f"sourcil{sg}", (sg * hh * 0.15, -hh * 0.41, zt + hh * 0.17), (hh * 0.09, hh * 0.015, hh * 0.018 * fiche["sourcils"]), cheveux, sp, 1); sourcils.append(sp)
    piv_b = _vide("bouche_piv", (0, -hh * 0.395, zt - hh * 0.27), tete)
    bo = _sphere("bouche", (0, -hh * 0.395, zt - hh * 0.27), (hh * 0.09, hh * 0.03, hh * 0.03), bouche, piv_b)
    _sphere("levre_h", (0, -hh * 0.405, zt - hh * 0.24), (hh * 0.095, hh * 0.025, hh * 0.016 * fiche["levres"]), levres, tete)
    lb = _sphere("levre_b", (0, -hh * 0.4, zt - hh * 0.3), (hh * 0.085, hh * 0.025, hh * 0.019 * fiche["levres"]), levres, piv_b)
    st = fiche["cheveux"]
    if st != "chauve":
        _sphere("cheveux", (0, hh * 0.07, zt + hh * 0.13), (hh * 0.425, hh * 0.46, hh * (0.47 if st not in ("rase",) else 0.44)), cheveux, tete)
        if st in ("long", "carre", "mi_long"):
            _cube("cheveux_longs", (0, hh * 0.15, zt - hh * (0.4 if st == "long" else 0.15)), (hh * 0.45, hh * 0.25, hh * (0.75 if st == "long" else 0.45)), cheveux, tete)
        if st == "queue": _cylindre("queue", (0, hh * 0.4, zt + hh * 0.15), (0, hh * 0.55, zt - hh * 0.7), hh * 0.1, hh * 0.05, cheveux, tete)
        if st == "chignon": _sphere("chignon", (0, hh * 0.25, zt + hh * 0.5), (hh * 0.18,) * 3, cheveux, tete)
        if st == "boucles":
            for k in range(14): a = k / 14 * 2 * math.pi; _sphere(f"boucle{k}", (hh * 0.42 * math.cos(a), hh * 0.15 + hh * 0.3 * math.sin(a) * 0.5, zt + hh * 0.2 + hh * 0.25 * math.sin(a)), (hh * 0.12,) * 3, cheveux, tete)
    if fiche.get("barbe") in ("courte", "trois_jours"):
        _sphere("barbe", (0, -hh * 0.02, zt - hh * 0.36), (hh * 0.37, hh * 0.33, hh * 0.2), cheveux if fiche["barbe"] == "courte" else _mat("barbe3j", tuple(int(a * 0.6 + b * 0.4) for a, b in zip(fiche["peau"], fiche["c_cheveux"])), 0.8), tete)
    if fiche.get("lunettes"):
        cadre = _mat("lunettes", (30, 28, 30), 0.3)
        for sg in (-1, 1):
            bpy.ops.mesh.primitive_torus_add(major_radius=hh * 0.1, minor_radius=hh * 0.012, location=(sg * hh * 0.15, -hh * 0.44, zt + hh * 0.05), rotation=(math.pi / 2, 0, 0))
            o = bpy.context.object; o.data.materials.append(cadre); _parent(o, tete)
    # bras et mains (pivots aux épaules et aux coudes)
    bras = {}
    for nom, sg in (("g", -1), ("d", 1)):
        ep = _vide(f"epaule_{nom}", (sg * l_ep * 1.1, 0, hh * 5.25), torse)
        L1, L2 = hh * 1.2, hh * 1.02
        manche = haut if costume.get("haut") not in ("debardeur",) else peau
        _cylindre(f"bras_{nom}", (sg * l_ep * 1.1, 0, hh * 5.25), (sg * l_ep * 1.1, 0, hh * 5.25 - L1), hh * (0.18 + 0.04 * corp), hh * 0.14, manche, ep)
        co = _vide(f"coude_{nom}", (sg * l_ep * 1.1, 0, hh * 5.25 - L1), ep)
        court = costume.get("haut") in ("tshirt", "polo", "debardeur")
        _cylindre(f"avantbras_{nom}", (sg * l_ep * 1.1, 0, hh * 5.25 - L1), (sg * l_ep * 1.1, 0, hh * 5.25 - L1 - L2), hh * 0.14, hh * 0.1, peau if court else manche, co)
        m_ = _sphere(f"main_{nom}", (sg * l_ep * 1.1, 0, hh * 5.25 - L1 - L2 - hh * 0.14), (hh * 0.11, hh * 0.07, hh * 0.16), peau, co)
        po = _sphere(f"pouce_{nom}", (sg * l_ep * 1.1 - sg * hh * 0.07, -hh * 0.03, hh * 5.25 - L1 - L2 - hh * 0.06), (hh * 0.03, hh * 0.03, hh * 0.06), peau, co)
        bras[nom] = (ep, co)
    # caméra orthographique de face, lumières
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera")); bpy.context.collection.objects.link(cam)
    cam.data.type = "ORTHO"; cam.data.ortho_scale = CADRE_H; cam.location = (0, -10, CADRE_H / 2 - PIEDS_BAS); cam.rotation_euler = (math.pi / 2, 0, 0)
    bpy.context.scene.camera = cam
    for nom, loc, e, taille in (("cle", (-3, -4, 4), 900, 3), ("douce", (4, -3, 2.5), 350, 4), ("contre", (0, 4, 4), 500, 2)):   # lumière principale, d'appoint, de contre
        l = bpy.data.lights.new(nom, "AREA"); l.energy = e; l.size = taille; o = bpy.data.objects.new(nom, l); bpy.context.collection.objects.link(o)
        o.location = loc; d = Vector((0, 0, T / 2)) - Vector(loc); o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    w = bpy.context.scene.world or bpy.data.worlds.new("monde"); bpy.context.scene.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.6, 0.6, 0.65, 1); w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    return dict(racine=racine, torse=torse, tete=tete, bras=bras, paupieres=paupieres, sourcils=sourcils, regard=iris_o, bouche=piv_b, hh=hh)

CADRE_H = 2.6                                                              # hauteur de l'image en mètres (bras levés compris)
PIEDS_BAS = 0.1                                                            # marge sous les pieds (mètres)

VISEMES = {"A": (1.0, 1.0), "E": (1.25, 0.45), "I": (1.15, 0.3), "O": (0.65, 0.85), "U": (0.5, 0.5), "M": (1.0, 0.0), "F": (1.0, 0.25)}

def poser(R, p):
    """Applique une pose 2D (mêmes clés que le dessin) aux articulations 3D."""
    for nom, cle in (("g", "bras_g"), ("d", "bras_d")):
        ep, co = R["bras"][nom]; a1, a2 = p.get(cle, (0, 0))
        ep.rotation_euler = (0, -math.radians(a1), 0); co.rotation_euler = (0, -math.radians(a2), 0)
        ep.location.z = ep["z0"] + float(p.get("epaules", 0.0)) * R["hh"] * 0.18
    R["tete"].rotation_euler = (math.radians(-6 * float(p.get("sourcils_h", 0.0))) * 0.3, -math.radians(p.get("tilt", 0.0) * 0.6), 0)
    R["torse"].rotation_euler = (0, -math.radians(4 * float(p.get("penche", 0.0))), 0)
    o = float(p.get("bouche", 0.0)); v = p.get("viseme"); f = p.get("forme", "neutre")
    lx, lz = VISEMES.get(v, (1.0, 1.0)) if v else (1.0, 1.0)
    ouv = 0.15 + 2.2 * o * lz if (v or o > 0.08 or f in ("cri", "o")) else 0.15
    if f == "cri": ouv = max(ouv, 2.4)
    larg = lx * (1.0 + 0.35 * float(p.get("coins", 0.0)) + (0.3 if f in ("sourire", "grand_sourire") else 0))
    R["bouche"].scale = (larg, 1, ouv)
    pa = 1.0 if p.get("yeux") == "fermes" else float(p.get("paupiere", 0.0))
    if p.get("yeux") in ("vides",): pa = max(pa, 0.5)
    if p.get("yeux") in ("heureux", "plisses"): pa = max(pa, 0.6)
    for pp in R["paupieres"]: pp.rotation_euler = (math.radians(-75 + 165 * pa), 0, 0)   # ouverte : coque relevée ; fermée : coque devant l'œil
    so = p.get("sourcils", "neutre"); hz = float(p.get("sourcils_h", 0.0))
    for k, sp in enumerate(R["sourcils"]):
        sg = -1 if k == 0 else 1
        ang = {"colere": 18, "triste": -15, "fronces": 10, "sceptique": (-12 if sg > 0 else 4)}.get(so, 0)
        sp.rotation_euler = (0, math.radians(ang * sg), 0); sp.location.z = sp["z0"] + R["hh"] * 0.04 * (hz + (0.8 if so == "hausses" else 0))
    gx, gy = p.get("regard", (0.0, 0.0))
    for rg in R["regard"]: rg.rotation_euler = (math.radians(gy * 15), 0, math.radians(-gx * 20))

def cle_pose(p):
    """Pose arrondie : deux poses presque identiques donnent la même image (rendue une seule fois)."""
    r = lambda v, k=1: round(float(v) / k) * k
    return json.dumps([r(p.get("bras_g", (0, 0))[0], 2), r(p.get("bras_g", (0, 0))[1], 2), r(p.get("bras_d", (0, 0))[0], 2), r(p.get("bras_d", (0, 0))[1], 2),
                       r(p.get("tilt", 0), 1), r(p.get("bouche", 0), 0.1), p.get("viseme"), p.get("forme"), p.get("yeux"), r(p.get("paupiere", 0), 0.25),
                       p.get("sourcils"), r(p.get("sourcils_h", 0), 0.2), r(p.get("epaules", 0), 0.2), r(p.get("penche", 0), 0.2),
                       [r(v, 0.2) for v in p.get("regard", (0, 0))], r(p.get("coins", 0), 0.25)])

def main(chemin):
    T = json.load(open(chemin)); sortie = T["sortie"]; os.makedirs(sortie, exist_ok=True)
    sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.device = "GPU" if T.get("gpu") else "CPU"
    sc.cycles.samples = int(T.get("echantillons", 12)); sc.cycles.use_denoising = True
    sc.render.film_transparent = True; sc.render.resolution_x = int(T["largeur"]); sc.render.resolution_y = int(T["hauteur"])
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    for role, J in T["roles"].items():
        R = construire(J["fiche"], J["costume"]); faites = {}
        for k, p in enumerate(J["poses"]):
            f = os.path.join(sortie, f"{role}_{k:05d}.png")
            if p is None: continue
            c = cle_pose(p)
            if c in faites: shutil.copyfile(faites[c], f); continue
            poser(R, p); bpy.context.view_layer.update()
            sc.render.filepath = f; bpy.ops.render.render(write_still=True); faites[c] = f
        print(f"3D : {role} : {len(J['poses'])} images, {len(faites)} rendues", flush=True)

if __name__ == "__main__":
    main(sys.argv[-1])
