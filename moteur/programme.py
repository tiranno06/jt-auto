"""Programme des émissions : quel type de vidéo fabriquer aujourd'hui."""
import datetime

def format_du_jour(demande, historique):
    """Type de vidéo de cette émission. « cycle » : 3 gags éclair puis 1 sketch long (+1 min, rémunérable), en boucle."""
    f = (demande or "cycle").strip().lower()
    if f == "alterne": return "libre" if datetime.date.today().toordinal() % 2 else "actu"
    if f == "cycle":
        courts = 0
        for h in reversed(historique):                                    # gags éclair depuis le dernier sketch long
            if h.get("manuel"): continue                                  # les vidéos manuelles ne comptent pas dans le cycle
            if h.get("format") == "libre": break
            if h.get("format") == "mini": courts += 1
        return "libre" if courts >= 3 else "mini"
    return f if f in ("actu", "libre", "mini") else "libre"
