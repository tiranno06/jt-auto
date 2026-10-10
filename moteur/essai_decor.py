"""Préchauffe le générateur de décors (télécharge Stable Diffusion XL sur Modal la première fois) et produit deux décors d'essai."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal
os.makedirs("essai_decor", exist_ok=True)
t0 = time.time()
try:
    f = modal.Cls.from_name("jt-decor", "Decor")().generer.spawn(["a narrow apartment building hallway, a closed front door with a peephole, a torn delivery notice on the floor", "a small cozy bar with wooden tables, beer taps and a chalkboard menu"], 7)
    pngs = f.get(timeout=1500)
    for k, p in enumerate(pngs):
        print(f"décor {k} : {len(p)} octets")
        if p: open(f"essai_decor/decor_{k}.png", "wb").write(p)
except Exception as e:
    print(f"ÉCHEC : {type(e).__name__} {str(e)[:500]}")
print(f"durée {time.time() - t0:.0f} s")
