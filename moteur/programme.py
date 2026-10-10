"""Programme des émissions : quel type de vidéo fabriquer aujourd'hui."""
import datetime

def format_du_jour(demande, historique):
    """Type de vidéo de cette émission. « cycle » : 3 gags éclair puis 1 sketch long (+1 min, rémunérable), en boucle.
    « seq:mini,mini,libre,… » : séquence libre réglée dans la régie, rejouée en boucle sur les vidéos automatiques.
    Un créneau du planning peut imposer son propre type (« 18:30=libre »)."""
    import os
    f = (demande or "cycle").strip().lower()
    if os.environ.get("EVENEMENT") == "schedule":                          # le créneau du planning a son propre type : il l'emporte
        try:
            import planning
            _, _, du_creneau = planning.decision_complete()
            if du_creneau and du_creneau != "programme": return du_creneau
        except Exception: pass
    if f.startswith("seq:"):
        seq = [x.strip() for x in f[4:].split(",") if x.strip() in ("mini", "libre", "actu")]
        if seq:
            n = sum(1 for h in historique if h.get("auto") and not h.get("manuel"))   # position dans la séquence
            return seq[n % len(seq)]
        f = "cycle"
    if f == "alterne": return "libre" if datetime.date.today().toordinal() % 2 else "actu"
    if f == "cycle":
        courts = 0
        for h in reversed(historique):                                    # gags éclair depuis le dernier sketch long
            if h.get("manuel"): continue                                  # les vidéos manuelles ne comptent pas dans le cycle
            if h.get("format") == "libre": break
            if h.get("format") == "mini": courts += 1
        return "libre" if courts >= 3 else "mini"
    return f if f in ("actu", "libre", "mini") else "libre"
