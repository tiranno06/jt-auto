"""Machine d'aide du dessin partagé (workflow dessin.yml) : récupère le paquet de la fabrication, dessine SON morceau d'images
exactement comme la machine principale l'aurait fait, et le renvoie (release « dessins-temp »). En cas d'échec, elle le signale
tout de suite (fichier « .echec ») : la machine principale dessine alors le morceau elle-même."""
import os, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dessin_partage as DP


def main(nom, a, b):
    rel = DP.release(); tmp = tempfile.mkdtemp(); cle = f"{nom}_{a}_{b}"
    try:
        asset = next((x for x in DP.fichiers(rel) if x["name"] == f"{nom}_paquet.pkl.gz"), None)
        if asset is None: raise RuntimeError("paquet introuvable (fabrication déjà finie ?)")
        DP.telecharger(asset, f"{tmp}/paquet.pkl.gz")
        d = DP.ouvrir(f"{tmp}/paquet.pkl.gz")
        os.environ.update(d["env"]); os.environ["AIDE_DESSIN"] = "1"; os.environ["DESSIN_PARTAGE"] = "0"
        import cartoon
        t0 = time.time(); args = d["args"]
        for k, v in (args.get("module") or {}).items(): setattr(cartoon, k, v)   # réglages posés par la fabrication (ex. rendu simple)
        cartoon.rendre(args["sk"], f"{tmp}/{cle}.mp4", args["audios"], mots=args["mots"], decors=args["decors"], mini=args["mini"], plage=(a, b))
        print(f"Morceau {a}–{b} dessiné en {(time.time() - t0) / 60:.1f} min", flush=True)
        DP.envoyer(rel, f"{tmp}/{cle}.mp4", f"{cle}.mp4")
    except Exception as e:
        import traceback; traceback.print_exc()
        open(f"{tmp}/{cle}.echec", "w").write(str(e)[:500])
        try: DP.envoyer(rel, f"{tmp}/{cle}.echec", f"{cle}.echec")
        except Exception: pass
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
