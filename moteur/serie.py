"""Code des sketchs (mis de côté depuis le 11 novembre 2026) rangé dans moteur/sketchs/serie.py (audit du 17 novembre 2026,
idée 23). Ce petit fichier garde l'ancien nom : « import serie » charge le vrai module, rien d'autre ne change."""
import importlib.util as _u, os as _os, sys as _sys
_s = _u.spec_from_file_location(__name__, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "sketchs", "serie.py"))
_m = _u.module_from_spec(_s); _sys.modules[__name__] = _m; _s.loader.exec_module(_m)
