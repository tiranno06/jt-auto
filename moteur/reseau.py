"""Appels réseau robustes : réessai automatique des coupures passagères (réseau, serveur saturé, erreur 5xx, 429)."""
import socket, time, urllib.error, urllib.request

PASSAGERES = (429, 500, 502, 503, 504, 520, 522, 524, 529)

def ouvrir(req, timeout=60, essais=4, pause=2.0):
    """urllib.request.urlopen(req).read() avec réessais (pauses 2, 4, 8 s). Les autres erreurs (crédit, clé…) remontent tout de suite."""
    for k in range(essais):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code not in PASSAGERES or k == essais - 1: raise
            print(f"  réseau : erreur {e.code} passagère, nouvel essai dans {pause * 2 ** k:.0f} s", flush=True)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            if k == essais - 1: raise
            print(f"  réseau : coupure ({str(e)[:80]}), nouvel essai dans {pause * 2 ** k:.0f} s", flush=True)
        time.sleep(pause * 2 ** k)

def _anthropic():
    import anthropic
    try: return anthropic.Anthropic(max_retries=5)
    except TypeError: return anthropic.Anthropic()                         # (client simulé des tests)


# ------------------------------------------------------------------ plusieurs IA, une seule porte d'entrée
# Claude d'abord (s'il a du crédit), sinon Mistral (humour en français) et Gemini (images), clés gratuites MISTRAL_API_KEY et
# GEMINI_API_KEY (secrets GitHub). Le reste du robot ne voit qu'un client « façon Claude » : reseau.claude().messages.create(...).
import json, os
from types import SimpleNamespace as _NS

FOURNISSEURS = {
    "mistral": dict(cle="MISTRAL_API_KEY", url="https://api.mistral.ai/v1/chat/completions",
                    texte=("ministral-14b-2512", "ministral-8b-latest"), images=("ministral-14b-2512", "ministral-8b-latest")),
    "gemini": dict(cle="GEMINI_API_KEY", url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                   texte=("gemini-flash-lite-latest", "gemini-2.5-flash-lite", "gemini-flash-latest"),
                   images=("gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest")),
}
HORS_SERVICE = set()                                                       # fournisseurs épuisés pendant cette fabrication
UTILISES = {}                                                              # nombre d'appels réussis par fournisseur (fiche de la vidéo)


def _libre(sch):
    """Gemini refuse les objets sans propriétés : on les demande en texte JSON (relu ensuite)."""
    if not isinstance(sch, dict): return sch
    if sch.get("type") == "object" and not sch.get("properties"): return {"type": "string", "description": "objet JSON écrit en texte"}
    out = {k: v for k, v in sch.items() if k not in ("additionalProperties",)}
    if "properties" in out: out["properties"] = {k: _libre(v) for k, v in out["properties"].items()}
    if "items" in out: out["items"] = _libre(out["items"])
    return out


def _relire(v, sch):
    """Remet en objets les champs « objet libre » renvoyés en texte JSON."""
    if not isinstance(sch, dict): return v
    if sch.get("type") == "object" and not sch.get("properties") and isinstance(v, str):
        try: return json.loads(v)
        except ValueError: return {}
    if isinstance(v, dict) and sch.get("properties"): return {k: _relire(x, sch["properties"].get(k, {})) for k, x in v.items()}
    if isinstance(v, list) and sch.get("items"): return [_relire(x, sch["items"]) for x in v]
    return v


def _messages_openai(kw, fourn):
    out = []
    sysm = kw.get("system")
    if sysm: out.append({"role": "system", "content": sysm if isinstance(sysm, str) else "\n".join(b.get("text", "") for b in sysm if isinstance(b, dict))})
    images = False
    for m in kw.get("messages") or []:
        c = m.get("content")
        if isinstance(c, str): out.append({"role": m["role"], "content": c}); continue
        parts = []
        for b in c or []:
            t = b.get("type") if isinstance(b, dict) else None
            if t == "text": parts.append({"type": "text", "text": b.get("text", "")})
            elif t == "image":
                src = b.get("source") or {}; url = f"data:{src.get('media_type', 'image/jpeg')};base64,{src.get('data', '')}"; images = True
                parts.append({"type": "image_url", "image_url": url if fourn == "mistral" else {"url": url}})
            elif t == "tool_result": parts.append({"type": "text", "text": str(b.get("content", ""))})
        if m["role"] == "assistant": out.append({"role": "assistant", "content": " ".join(p.get("text", "") for p in parts if p["type"] == "text") or "…"})
        else: out.append({"role": m["role"], "content": parts or "…"})
    return out, images


def _appel_openai(fourn, kw):
    F = FOURNISSEURS[fourn]; cle = os.environ.get(F["cle"], "")
    msgs, images = _messages_openai(kw, fourn)
    outils = [t for t in (kw.get("tools") or []) if isinstance(t, dict) and "input_schema" in t]   # la recherche web côté serveur est propre à Claude
    corps = {"messages": msgs, "max_tokens": min(int(kw.get("max_tokens") or 4000), 8000), "temperature": 0.8}
    if outils:
        corps["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", "")[:1000],
                                                           "parameters": _libre(t["input_schema"]) if fourn == "gemini" else t["input_schema"]}} for t in outils]
        tc = kw.get("tool_choice") or {}
        corps["tool_choice"] = ("any" if fourn == "mistral" else "required") if (tc.get("type") in ("tool", "any") or len(outils) == 1) else "auto"
    derniere = None
    modeles = F["images" if images else "texte"]
    for modele in modeles:
        corps["model"] = modele; d = None
        for essai in range(4):
            _attendre(fourn)
            req = urllib.request.Request(F["url"], data=json.dumps(corps).encode(), method="POST",
                                         headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/json"})
            try:
                d = json.loads(urllib.request.urlopen(req, timeout=240).read()); break
            except urllib.error.HTTPError as e:
                derniere = e; corps_err = e.read()[:300].decode("utf-8", "ignore"); bas = corps_err.lower()
                if e.code in (404, 400) and "model" in bas: d = "suivant"; break            # modèle inconnu : le suivant
                if e.code == 400 and outils and "tool" in bas and "tool_choice" in corps: corps.pop("tool_choice", None); continue
                if e.code == 429 and str(getattr(e, "headers", None) and e.headers.get("x-ratelimit-limit-req-minute")) == "0":
                    d = "suivant"; break                                                # modèle fermé à l'offre gratuite (0 / minute) : le suivant
                if e.code == 403 and "tier" in bas: d = "suivant"; break                  # modèle réservé aux offres payantes : le suivant
                if e.code == 429 and not any(m in bas for m in ("quota", "exhausted", "billing")):
                    if modele != modeles[-1]: d = "suivant"; break                     # limite à la minute : d'abord le modèle suivant
                    if essai < 2:                                                       # trop de demandes à la minute : on patiente
                        try: att = float(e.headers.get("Retry-After") or 0)
                        except (TypeError, ValueError, AttributeError): att = 0
                        time.sleep(min(30.0, att or 8.0 * (essai + 1))); continue
                    EN_PAUSE[fourn] = time.time() + 60                                  # limite du compte : une minute sans lui
                    raise RuntimeError(f"{fourn} limite 429 : {corps_err}")
                if e.code in (500, 502, 503, 504) and essai < 2: time.sleep(3.0 * (essai + 1)); continue   # serveur saturé un instant
                if e.code in (500, 502, 503, 504): d = "suivant"; break                  # toujours saturé : modèle suivant
                raise RuntimeError(f"{fourn} {e.code} : {corps_err}")
        if d == "suivant" or d is None: continue
        msg = (d.get("choices") or [{}])[0].get("message") or {}
        blocs = []
        if msg.get("content"):
            txt = msg["content"] if isinstance(msg["content"], str) else " ".join(x.get("text", "") for x in msg["content"] if isinstance(x, dict))
            if txt.strip(): blocs.append(_NS(type="text", text=txt))
        for tc_ in msg.get("tool_calls") or []:
            f = tc_.get("function") or {}; nom = f.get("name", "")
            try: args = json.loads(f.get("arguments") or "{}") if isinstance(f.get("arguments"), str) else (f.get("arguments") or {})
            except ValueError: args = {}
            sch = next((t["input_schema"] for t in outils if t["name"] == nom), {})
            blocs.append(_NS(type="tool_use", name=nom, input=_relire(args, sch), id=tc_.get("id", "")))
        u = d.get("usage") or {}
        UTILISES[fourn] = UTILISES.get(fourn, 0) + 1
        return _NS(content=blocs, stop_reason="max_tokens" if (d.get("choices") or [{}])[0].get("finish_reason") == "length" else "end_turn",
                   usage=_NS(input_tokens=u.get("prompt_tokens", 0), output_tokens=u.get("completion_tokens", 0), cache_read_input_tokens=0,
                             cache_creation_input_tokens=0, server_tool_use=None), model=f"{fourn}:{modele}", gratuit=True)
    raise RuntimeError(f"{fourn} : aucun modèle disponible ({derniere})")


_DERNIER = {}
EN_PAUSE = {}                                                               # fournisseur limité à la minute : sauté jusqu'à cette heure
PAUSE_MIN = {"mistral": 2.1, "gemini": 0.5}                                 # Mistral gratuit : ministral-14b = 30 demandes / minute


def _attendre(fourn):
    t = time.time() - _DERNIER.get(fourn, 0)
    if t < PAUSE_MIN.get(fourn, 0): time.sleep(PAUSE_MIN[fourn] - t)
    _DERNIER[fourn] = time.time()


def ordre_ia(images=False):
    """Ordre de passage : Claude (s'il a du crédit), puis Mistral et Gemini (Gemini d'abord pour regarder des images)."""
    o = [] if os.environ.get("CLAUDE_INDISPONIBLE") == "1" else ["claude"]
    autres = ["gemini", "mistral"] if images else ["mistral", "gemini"]
    o += [f for f in autres if os.environ.get(FOURNISSEURS[f]["cle"]) and f not in HORS_SERVICE]
    return [f for f in o if f not in HORS_SERVICE and EN_PAUSE.get(f, 0) <= time.time()] or [f for f in o if f not in HORS_SERVICE]


def ia_disponible():
    return bool(ordre_ia())


class _Messages:
    def __init__(self, raisonner=False, exclure=()):
        self._client = None; self.raisonner = raisonner; self.exclure = set(exclure or ()); self.dernier = None   # une seule connexion Claude par client

    def create(self, **kw):
        images = self.raisonner or any(isinstance(b, dict) and b.get("type") == "image" for m in kw.get("messages") or [] if isinstance(m.get("content"), list) for b in m["content"])
        erreurs = []
        for f in [f for f in ordre_ia(images) if f not in self.exclure]:
            try:
                if f == "claude":
                    if self._client is None: self._client = _anthropic()
                    r = self._client.messages.create(**kw); UTILISES["claude"] = UTILISES.get("claude", 0) + 1; self.dernier = f; return r
                kw2 = {k: v for k, v in kw.items() if k != "tools"}; kw2["tools"] = [t for t in (kw.get("tools") or []) if "input_schema" in t]
                if kw.get("tools") and not kw2["tools"]: raise RuntimeError("seulement un outil web (propre à Claude)")
                r = _appel_openai(f, kw2); self.dernier = f; return r
            except Exception as e:
                import secours
                txt = str(e).lower()
                if f == "claude" and not secours.claude_indisponible(e): raise         # erreur de Claude qui n'est pas un manque de crédit
                if any(m in txt for m in (" 401", " 403", "quota", "exhausted", "billing")): HORS_SERVICE.add(f)   # vraiment épuisé / refusé
                erreurs.append(f"{f} : {str(e)[:120]}")
                print(f"  IA {f} indisponible ({str(e)[:120]}) : on passe à la suivante", flush=True)
        raise RuntimeError("credit balance : aucune IA disponible (" + " | ".join(erreurs) + ")")


class _IA:
    def __init__(self, raisonner=False, exclure=()): self.messages = _Messages(raisonner, exclure)


def claude(raisonner=False, exclure=()):
    """Client « façon Claude » : Claude si possible, sinon Mistral puis Gemini (bascule automatique, quotas épuisés évités).
    raisonner=True : Gemini avant Mistral (comme pour les images), pour les tâches de logique (qui dit quoi dans un dialogue)."""
    return _IA(raisonner, exclure)   # exclure : fournisseurs à ne pas utiliser (2e avis indépendant d'une autre IA)


# ------------------------------------------------------------------ mode économique (réglage du site)
def mode_eco():
    """Réglage « Mode économique » : on garde les outils payants (Claude, ElevenLabs, décors IA) mais on dépense moins.
    Claude Sonnet au lieu d'Opus, petites étapes sur le modèle économique, 1 premier jet au lieu de 3, 2 réécritures et 2 sujets
    au plus, pas de public test ni de recherche des tendances, pas de nouvelles ambiances sonores ElevenLabs (celles déjà faites
    restent utilisées). À appeler avant d'importer ecrire. Renvoie True si le mode est actif."""
    import os
    if (os.environ.get("MODE_ECO") or "0") != "1": return False
    os.environ.update(MODELE_CLAUDE="claude-sonnet-5-5", ETAPES_ECO="1", VERSIONS="1", PUBLIC_TEST="0", TENDANCES="0", AMBIANCES_ELEVEN="0")
    for cle, plafond in (("MAX_REECRITURES", 2), ("SUJETS_MAX", 2)):
        try: v = int(os.environ.get(cle) or plafond)
        except ValueError: v = plafond
        os.environ[cle] = str(min(v, plafond))
    print("Mode économique : Claude Sonnet, 1 premier jet, 2 réécritures au plus, sans public test ni tendances.", flush=True)
    return True


# ------------------------------------------------------------------ crédits vérifiés au départ
def verifier_credits():
    """Vérifie au lancement si Claude et ElevenLabs répondent et ont du crédit (appel minuscule, coût négligeable).
    Pose CLAUDE_INDISPONIBLE=1 et/ou ELEVENLABS=0 dans l'environnement : le robot part directement sur les outils gratuits.
    Vérifie aussi Mistral et Gemini (remplaçants gratuits). Renvoie {"claude": "ok"|"secours"|"absent", "mistral"/"gemini":
    "ok"|"epuise"|"cle"|"limite"|"erreur"|"absent", "ia": "ok"|"aucune", "elevenlabs": "ok"|"epuise"|"absent"}."""
    import json, os
    etat = {}
    if not os.environ.get("ANTHROPIC_API_KEY"): etat["claude"] = "absent"
    else:
        try:
            _anthropic().messages.create(model="claude-haiku-5-5", max_tokens=1, messages=[{"role": "user", "content": "ok"}]); etat["claude"] = "ok"
        except Exception as e:
            import secours
            etat["claude"] = "secours" if secours.claude_indisponible(e) else "ok"   # erreur passagère : on tentera quand même
    if etat["claude"] != "ok": os.environ["CLAUDE_INDISPONIBLE"] = "1"
    for f, F in FOURNISSEURS.items():                                      # remplaçants gratuits : un appel minuscule chacun
        if not os.environ.get(F["cle"]): etat[f] = "absent"; continue
        try:
            _appel_openai(f, {"messages": [{"role": "user", "content": "Réponds juste : ok"}], "max_tokens": 5}); etat[f] = "ok"
        except Exception as e:
            t = str(e).lower(); etat[f] = ("epuise" if ("quota" in t or "exhausted" in t or "billing" in t) else "cle" if (" 401" in t or " 403" in t)
                                         else "limite" if "limite 429" in t else "erreur")
            if etat[f] in ("epuise", "cle"): HORS_SERVICE.add(f)                    # erreur passagère : on retentera pendant la fabrication
            print(f"  {f} : {str(e)[:160]}", flush=True)
    UTILISES.clear()
    etat["ia"] = "ok" if ia_disponible() else "aucune"
    cle = os.environ.get("ELEVENLABS_API_KEY")
    if not cle: etat["elevenlabs"] = "absent"
    else:
        try:
            d = json.loads(ouvrir(urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": cle}), timeout=30))
            reste = int(d.get("character_limit", 0)) - int(d.get("character_count", 0))
            etat["elevenlabs"] = "ok" if reste > 300 else "epuise"
            if etat["elevenlabs"] == "epuise": os.environ["ELEVENLABS"] = "0"
        except Exception as e:
            etat["elevenlabs"] = "ok"                                      # lecture du solde impossible : on tentera quand même
    print(f"Crédits au départ : Claude {etat['claude']}, Mistral {etat['mistral']}, Gemini {etat['gemini']}, ElevenLabs {etat['elevenlabs']}"
          f" — IA utilisée : {(ordre_ia() or ['aucune (sketchs de secours)'])[0]}", flush=True)
    return etat
