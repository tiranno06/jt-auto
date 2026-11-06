"""Calculs de dessin accélérés par Numba (choix de l'auteur du 6 novembre 2026, idée 4 : « dessin compilé »).

Les mélanges de couleur les plus coûteux (aquarelle et hachures du style croquis, collage des personnages super-échantillonnés,
ombre portée) sont faits en UNE passe compilée au lieu d'une dizaine de tableaux intermédiaires NumPy. Mêmes opérations, en float32,
dans le même ordre : EXACTEMENT les mêmes pixels (tests : TestDessinRapide). Les fonctions sont compilées à l'import (avant que les
processus de dessin ne soient lancés). Sans Numba, ou avec NUMBA=0 : chaque appelant garde son calcul NumPy d'avant (None ici)."""
import os
import numpy as np

LAVIS = HACHURES = COLLER = ASSOMBRIR = None


def _compiler():
    global LAVIS, HACHURES, COLLER, ASSOMBRIR
    if os.environ.get("NUMBA", "1") == "0": return
    try: import numba
    except Exception: return
    f32 = np.float32

    @numba.njit(cache=True, nogil=True)
    def lavis(zone, a, bb, coul, c2, bord):
        h, w = a.shape; un, z, mx, d = f32(1.0), f32(0.0), f32(255.0), f32(0.5)
        for i in range(h):
            for j in range(w):
                av = a[i, j]
                av = z if av < z else (un if av > un else av)
                bv = z
                if bord:
                    bv = bb[i, j] * d
                    bv = z if bv < z else (un if bv > un else bv)
                for c in range(3):
                    o = f32(zone[i, j, c]) * (un - av) + coul[c] * av
                    if bord: o = o * (un - bv) + c2[c] * bv
                    o = z if o < z else (mx if o > mx else o)
                    zone[i, j, c] = np.uint8(o)

    @numba.njit(cache=True, nogil=True)
    def hachures(zone, cal, coul):
        h, w = cal.shape; un, z, mx = f32(1.0), f32(0.0), f32(255.0)
        for i in range(h):
            for j in range(w):
                cv = cal[i, j]
                for c in range(3):
                    o = f32(zone[i, j, c]) * (un - cv) + coul[c] * cv
                    o = z if o < z else (mx if o > mx else o)
                    zone[i, j, c] = np.uint8(o)

    @numba.njit(cache=True, nogil=True)
    def coller(img, a_o, a_c, coul):
        """img = clip(img * (1 - 0,2 a_o) * (1 - a_c) + coul) : personnage (couleurs prémultipliées) collé sur le décor."""
        h, w = a_c.shape[0], a_c.shape[1]; un, z, mx, k = f32(1.0), f32(0.0), f32(255.0), f32(0.2)
        for i in range(h):
            for j in range(w):
                f1 = un - k * a_o[i, j, 0]; f2 = un - a_c[i, j, 0]
                for c in range(3):
                    o = (f32(img[i, j, c]) * f1) * f2 + coul[i, j, c]
                    o = z if o < z else (mx if o > mx else o)
                    img[i, j, c] = np.uint8(o)

    @numba.njit(cache=True, nogil=True)
    def assombrir(img, f):
        """img = img * (1 - f) (ombre portée sur le sol)."""
        h, w = f.shape[0], f.shape[1]; un = f32(1.0)
        for i in range(h):
            for j in range(w):
                g = un - f[i, j, 0]
                if g == un: continue
                for c in range(3): img[i, j, c] = np.uint8(f32(img[i, j, c]) * g)

    try:
        u8, z2, z3 = np.zeros((2, 2, 3), np.uint8), np.zeros((2, 2), f32), np.zeros(3, f32)
        lavis(u8, z2, z2, z3, z3, True); hachures(u8, z2, z3)
        coller(u8, np.zeros((2, 2, 1), f32), np.zeros((2, 2, 1), f32), np.zeros((2, 2, 3), f32)); assombrir(u8, np.zeros((2, 2, 1), f32))
    except Exception as e:
        print(f"Dessin compilé (Numba) indisponible ({str(e)[:100]}) : calcul NumPy habituel", flush=True); return
    LAVIS, HACHURES, COLLER, ASSOMBRIR = lavis, hachures, coller, assombrir


_compiler()
