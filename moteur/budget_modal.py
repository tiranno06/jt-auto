"""Vrai compteur des dépenses Modal (choix de l'auteur du 6 novembre 2026, idée 48).

Le robot lit chez Modal ce qui a VRAIMENT été dépensé ce mois-ci (`modal billing summary --json` : coût mesuré, avant les crédits
offerts). Au-delà du plafond (BUDGET_MODAL, 30 $ par défaut) moins une marge de sécurité (2 $), Modal est coupé pour la fabrication :
décors dessinés au lieu des décors IA, voix et écoute gratuites (les replis habituels) ; la vidéo sort quand même, et une alerte
part sur le téléphone (une fois par jour). Le montant est aussi affiché sur le site (Réglages → Crédits et outils).
Modal ne répond pas (clé absente, offre sans relevé) : rien ne change, comme avant (le budget des décors DECORS_MOIS reste en place)."""
import datetime, json, os, subprocess, sys

MARGE = 2.0


def plafond():
    try: return float(os.environ.get("BUDGET_MODAL") or 30)
    except ValueError: return 30.0


def depense_mois(timeout=90):
    """Dépense Modal du mois en dollars (coût mesuré), ou None si Modal ne la donne pas."""
    if not (os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET")): return None
    try:
        exe = os.path.join(os.path.dirname(sys.executable), "modal")
        r = subprocess.run([exe if os.path.exists(exe) else "modal", "billing", "summary", "--json"], capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0: return None
        d = json.loads(r.stdout[r.stdout.find("{"):])
        return round(float(d.get("metered_cost") or 0), 2)
    except Exception: return None


def verifier(journal=print):
    """Au démarrage d'une fabrication : renvoie la dépense du mois (ou None) ; coupe Modal si le plafond est presque atteint."""
    d = depense_mois()
    if d is None: return None
    p = plafond()
    journal(f"Modal : {d:.2f} $ dépensés ce mois-ci (plafond {p:.0f} $)")
    if d >= p - MARGE:
        for k in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"): os.environ.pop(k, None)
        journal(f"⚠️ Modal coupé pour cette fabrication : {d:.2f} $ sur {p:.0f} $ (décors dessinés, voix et écoute gratuites)")
        try:
            jour = datetime.date.today().isoformat(); f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes", "alerte_modal.txt")
            if (open(f).read().strip() if os.path.exists(f) else "") != jour:
                open(f, "w").write(jour)
                __import__("alerte").alerter("Budget Modal presque atteint", f"{d:.2f} $ dépensés ce mois-ci sur {p:.0f} $ : le robot continue avec les "
                                             "outils gratuits (décors dessinés) jusqu'au mois prochain.")
        except Exception: pass
    return d
