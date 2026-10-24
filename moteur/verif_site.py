"""Contrôle après chaque mise en ligne du site (workflow site.yml) : la dernière vidéo fabriquée doit apparaître sur le site EN
LIGNE (page et fichier vidéo). Sinon : code de sortie 1 (le workflow refait la mise en ligne), puis alerte sur le téléphone.
Usage : python moteur/verif_site.py <adresse du site> [essais]"""
import sys, time, urllib.request, os

def verifier(url, fichier, essais=8, pause=30):
    url = url.rstrip("/") + "/"
    for k in range(essais):
        try:
            page = urllib.request.urlopen(urllib.request.Request(url + f"?v={time.time():.0f}", headers={"Cache-Control": "no-cache"}), timeout=30).read().decode("utf-8", "ignore")
            if fichier in page:
                r = urllib.request.urlopen(urllib.request.Request(url + "videos/" + fichier, method="HEAD"), timeout=30)
                if r.status == 200: print(f"Site en ligne à jour : {fichier} visible ✓"); return True
        except Exception as e: print(f"  essai {k + 1} : {str(e)[:120]}")
        time.sleep(pause)
    print(f"Le site en ligne ne montre pas encore {fichier}."); return False

if __name__ == "__main__":
    racine = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "derniere.txt")
    f = open(racine).read().strip() if os.path.exists(racine) else ""
    if not f: print("Aucune vidéo à vérifier."); sys.exit(0)
    sys.exit(0 if verifier(sys.argv[1], f, int(sys.argv[2]) if len(sys.argv) > 2 else 8) else 1)
