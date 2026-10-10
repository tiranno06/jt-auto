"""Notifications sur le téléphone (Web Push), même quand l'application est fermée — pistes 20 et 30.

L'appli (bouton « Activer les notifications ») crée une paire de clés VAPID, abonne le téléphone et range tout dans les
variables du dépôt : VAPID_PUBLIQUE, VAPID_PRIVEE (PKCS8 en base64url) et PUSH_ABONNEMENTS (liste JSON des appareils).
Le robot chiffre chaque message (RFC 8291, aes128gcm) et le signe (RFC 8292, JWT ES256) : aucune bibliothèque externe.
Chaque alerte est aussi gardée dans episodes/alertes.json (bandeau de la régie).
Usage : python moteur/alerte.py "Titre" "Texte" [lien]"""
import base64, datetime, json, os, struct, sys, time, urllib.parse, urllib.request
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hmac import HMAC

RACINE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
JOURNAL = os.path.join(RACINE, "episodes", "alertes.json")

def _b64d(s): s = str(s).strip(); return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
def _b64e(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def _hkdf(sel, cle, info, n):
    h = HMAC(sel, hashes.SHA256()); h.update(cle); prk = h.finalize()
    h = HMAC(prk, hashes.SHA256()); h.update(info + b"\x01"); return h.finalize()[:n]

def chiffrer(message, p256dh, auth):
    """Corps chiffré aes128gcm pour un abonnement (clé publique du navigateur + secret d'authentification)."""
    ua = _b64d(p256dh); secret = _b64d(auth)
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    partage = priv.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua))
    ikm = _hkdf(secret, partage, b"WebPush: info\x00" + ua + pub, 32)
    sel = os.urandom(16)
    cek = _hkdf(sel, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(sel, ikm, b"Content-Encoding: nonce\x00", 12)
    chiffre = AESGCM(cek).encrypt(nonce, message + b"\x02", None)
    return sel + struct.pack(">I", 4096) + bytes([len(pub)]) + pub + chiffre

def jeton_vapid(endpoint, prive_b64, sujet="https://tiranno06.github.io/jt-auto/"):
    cle = serialization.load_der_private_key(_b64d(prive_b64), None)
    u = urllib.parse.urlparse(endpoint)
    tete = _b64e(json.dumps({"typ": "JWT", "alg": "ES256"}).encode())
    corps = _b64e(json.dumps({"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": sujet}).encode())
    r, s = decode_dss_signature(cle.sign(f"{tete}.{corps}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"{tete}.{corps}.{_b64e(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"

def envoyer(abonnement, donnees, prive, publique):
    corps = chiffrer(json.dumps(donnees, ensure_ascii=False).encode(), abonnement["keys"]["p256dh"], abonnement["keys"]["auth"])
    req = urllib.request.Request(abonnement["endpoint"], data=corps, method="POST", headers={
        "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "TTL": "86400", "Urgency": "high",
        "Authorization": f"vapid t={jeton_vapid(abonnement['endpoint'], prive)}, k={publique}"})
    return urllib.request.urlopen(req, timeout=30).status

def noter(titre, texte, lien=""):
    try: j = json.load(open(JOURNAL, encoding="utf-8"))
    except (OSError, ValueError): j = []
    j.append({"quand": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"), "titre": titre, "texte": texte[:300], "lien": lien})
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    json.dump(j[-30:], open(JOURNAL, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def alerter(titre, texte, lien=""):
    """Envoie la notification à tous les appareils abonnés ; ne fait jamais échouer le robot."""
    noter(titre, texte, lien)
    prive, publique = os.environ.get("VAPID_PRIVEE", ""), os.environ.get("VAPID_PUBLIQUE", "")
    try: abos = json.loads(os.environ.get("PUSH_ABONNEMENTS") or "[]")
    except ValueError: abos = []
    if not (prive and publique and abos): print("Notification non envoyée : notifications pas encore activées dans l'appli."); return 0
    n = 0
    for a in abos:
        try: envoyer(a, {"titre": titre, "texte": texte, "lien": lien}, prive, publique); n += 1
        except Exception as e: print(f"Notification refusée par un appareil : {str(e)[:150]}")
    print(f"Notification envoyée à {n}/{len(abos)} appareil(s) : {titre}"); return n

if __name__ == "__main__":
    a = sys.argv[1:] + ["", "", ""]
    alerter(a[0] or "Petits.Dramas", a[1], a[2])
