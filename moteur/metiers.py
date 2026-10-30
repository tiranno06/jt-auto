"""Métiers (demande de l'auteur, 30 octobre 2026) : quand on entend un métier dans le son TikTok (« je suis pompier », « docteur,
j'ai mal… », « t'es plombier ? »), le personnage qui l'exerce porte le costume de ce métier et tient son outil, d'après les planches
de référence de l'auteur (« Différents métiers », « Des métiers pour tous les rêves », « Styles et univers ») : nos propres dessins,
dans le style toon de la chaîne.

CATALOGUE : métier -> mots entendus, costume (moteur/toon.py et garde_robe.py), outil tenu en main (outil() ci-dessous).
qui_fait(sk) : {rôle: métier} d'après les répliques (« je suis… » = celui qui parle ; « tu es… », « docteur, … » = celui à qui il parle)."""
import math, re
import numpy as np, cv2

AA = cv2.LINE_AA
TRAIT = (25, 25, 30)

# ------------------------------------------------------------------ catalogue des métiers
# costume : clés du costume toon (haut, c_haut, bas, c_bas, chaussures, chapeau, c_chapeau, details…) ; outil : objet tenu en main
CATALOGUE = {
    "pompier": dict(mots=r"pompiers?|sapeurs?[- ]pompiers?|soldat du feu", outil="lance",
                    costume=dict(haut="veste_pompier", c_haut=(200, 70, 40), bas="pantalon", c_bas=(200, 70, 40), chaussures="bottes", c_chaussures=(30, 30, 32), chapeau="casque_pompier", c_chapeau=(205, 35, 35))),
    "policier": dict(mots=r"polici[eè]re?s?|flics?|keufs?|agent de police|lieutenant|commissaire|brigadier|monsieur l'agent", outil="talkie",
                     costume=dict(haut="uniforme", c_haut=(40, 55, 100), bas="pantalon", c_bas=(40, 55, 100), chaussures="ville", c_chaussures=(20, 20, 20), chapeau="casquette_officier", c_chapeau=(35, 50, 95), details=("badge",))),
    "medecin": dict(mots=r"m[ée]decins?|docteurs?|toubibs?|doc\b|g[ée]n[ée]raliste", outil="porte_bloc",
                    costume=dict(haut="blouse", c_haut=(250, 250, 250), c_dessous=(150, 190, 225), bas="pantalon", c_bas=(80, 95, 120), chaussures="ville", c_chaussures=(240, 240, 240), details=("stethoscope", "badge"))),
    "infirmier": dict(mots=r"infirmi[eè]re?s?|aide[- ]soignante?", outil="seringue",
                      costume=dict(haut="tunique_med", c_haut=(120, 180, 225), bas="pantalon", c_bas=(120, 180, 225), chaussures="baskets", c_chaussures=(250, 250, 250), chapeau="calot_infirmier")),
    "chirurgien": dict(mots=r"chirurgiens?|bloc op[ée]ratoire", outil=None,
                       costume=dict(haut="tunique_med", c_haut=(90, 170, 160), bas="pantalon", c_bas=(90, 170, 160), chaussures="baskets", c_chaussures=(250, 250, 250), chapeau="charlotte", c_chapeau=(90, 170, 160))),
    "dentiste": dict(mots=r"dentistes?", outil=None,
                     costume=dict(haut="blouse", c_haut=(250, 250, 250), c_dessous=(150, 190, 225), bas="pantalon", c_bas=(150, 190, 225), chaussures="baskets", c_chaussures=(250, 250, 250), chapeau="charlotte", c_chapeau=(150, 190, 225))),
    "veterinaire": dict(mots=r"v[ée]t[ée]rinaires?|v[ée]to\b", outil="porte_bloc",
                        costume=dict(haut="blouse", c_haut=(250, 250, 250), c_dessous=(110, 170, 120), bas="pantalon", c_bas=(70, 90, 110), chaussures="ville", details=("stethoscope",))),
    "enseignant": dict(mots=r"profs?|professeure?s?|ma[iî]tresse|instit(?:utrice|uteur)?|enseignante?s?|directeur d'[ée]cole|directrice", outil="livre",
                       costume=dict(haut="gilet", c_haut=(150, 110, 80), c_dessous=(240, 240, 235), bas="pantalon", c_bas=(110, 100, 90), chaussures="ville", c_chaussures=(80, 50, 30), details=("lunettes_vue",))),
    "cuisinier": dict(mots=r"chef cuisinier|cuisini[eè]re?s?|top chef|cuistots?", outil="poele",
                      costume=dict(haut="veste_chef", c_haut=(250, 250, 250), bas="pantalon", c_bas=(50, 50, 55), chaussures="ville", c_chaussures=(30, 30, 30), chapeau="toque")),
    "boulanger": dict(mots=r"boulang(?:er|[eè]re|erie)s?", outil="baguettes",
                      costume=dict(haut="tablier", c_haut=(250, 250, 250), c_tablier=(235, 215, 175), bas="pantalon", c_bas=(240, 240, 235), chaussures="ville", chapeau="calot")),
    "serveur": dict(mots=r"serveu(?:r|se)s?|gar[çc]on,|ma[iî]tre d'h[ôo]tel", outil="plateau",
                    costume=dict(haut="gilet", c_haut=(30, 30, 36), c_dessous=(250, 250, 250), bas="pantalon", c_bas=(30, 30, 36), chaussures="ville", c_chaussures=(20, 20, 20), details=("noeud_pap",))),
    "ingenieur": dict(mots=r"ing[ée]nieure?s?|architectes?|chef de chantier", outil="plans",
                      costume=dict(haut="chemise", c_haut=(170, 200, 230), bas="pantalon", c_bas=(60, 70, 90), chaussures="ville", chapeau="casque_chantier")),
    "ouvrier": dict(mots=r"ouvri[eè]re?s? du b[âa]timent|chantier|btp", outil="marteau",
                    costume=dict(haut="tshirt", c_haut=(240, 140, 40), bas="jean", c_bas=(70, 90, 120), chaussures="bottes", c_chaussures=(90, 60, 40), chapeau="casque_chantier")),
    "electricien": dict(mots=r"[ée]lectriciens?", outil="tournevis",
                        costume=dict(haut="salopette", c_haut=(80, 120, 170), c_salopette=(50, 70, 110), bas="pantalon", c_bas=(50, 70, 110), chaussures="bottes", c_chaussures=(60, 45, 35), chapeau="casque_chantier")),
    "plombier": dict(mots=r"plombiers?", outil="cle_molette",
                     costume=dict(haut="salopette", c_haut=(200, 60, 60), c_salopette=(50, 80, 160), bas="pantalon", c_bas=(50, 80, 160), chaussures="bottes", c_chaussures=(60, 45, 35), chapeau="casquette", c_chapeau=(50, 80, 160))),
    "mecanicien": dict(mots=r"m[ée]cano|m[ée]caniciens?|garagistes?", outil="cle_molette",
                       costume=dict(haut="combinaison", c_haut=(60, 90, 140), bas="pantalon", c_bas=(60, 90, 140), chaussures="bottes", c_chaussures=(40, 35, 30), c_ecusson=(230, 120, 40))),
    "agriculteur": dict(mots=r"agricult(?:eur|rice)s?|fermi[eè]re?s?|paysans?|[ée]leveurs?|la ferme", outil="fourche",
                        costume=dict(haut="salopette", c_haut=(200, 80, 70), c_salopette=(70, 120, 80), bas="pantalon", c_bas=(70, 120, 80), chaussures="bottes", c_chaussures=(60, 45, 35), chapeau="chapeau_paille")),
    "jardinier": dict(mots=r"jardini[eè]re?s?|paysagistes?", outil="arrosoir",
                      costume=dict(haut="salopette", c_haut=(240, 220, 170), c_salopette=(70, 130, 80), bas="pantalon", c_bas=(70, 130, 80), chaussures="bottes", c_chaussures=(60, 45, 35), chapeau="chapeau_paille")),
    "artiste": dict(mots=r"peintres?|artistes?|dessinat(?:eur|rice)", outil="palette",
                    costume=dict(haut="tablier", c_haut=(70, 110, 170), c_tablier=(240, 235, 220), taches_peinture=True, bas="pantalon", c_bas=(60, 60, 70), chaussures="ville", chapeau="beret", c_chapeau=(40, 60, 140))),
    "musicien": dict(mots=r"musiciens?|guitaristes?|rappeu(?:r|se)s?", outil="guitare",
                     costume=dict(haut="tshirt", c_haut=(60, 60, 70), bas="jean", c_bas=(50, 60, 90), chaussures="baskets", details=("chaine",))),
    "pilote": dict(mots=r"pilotes?|commandant de bord", outil=None,
                   costume=dict(haut="uniforme", c_haut=(30, 40, 75), bas="pantalon", c_bas=(30, 40, 75), chaussures="ville", c_chaussures=(20, 20, 20), chapeau="casquette_officier", c_chapeau=(30, 40, 75), details=("lunettes_soleil", "cravate"), c_cravate=(30, 30, 40))),
    "hotesse": dict(mots=r"h[ôo]tesses? de l'air|stewards?", outil=None,
                    costume=dict(haut="uniforme", c_haut=(40, 60, 110), bas="jupe", c_bas=(40, 60, 110), chaussures="ville", c_chaussures=(20, 20, 20), details=("echarpe",), c_echarpe=(200, 50, 60))),
    "scientifique": dict(mots=r"scientifiques?|chercheu(?:r|se)s?|chimistes?|labo(?:ratoire)?", outil="eprouvette",
                         costume=dict(haut="blouse", c_haut=(250, 250, 250), c_dessous=(120, 160, 120), bas="pantalon", c_bas=(70, 70, 80), chaussures="ville", details=("lunettes_vue",))),
    "informaticien": dict(mots=r"informaticiens?|d[ée]veloppeu(?:r|se)s?|codeu(?:r|se)s?|hackers?|geeks?|dev\b", outil="ordinateur",
                          costume=dict(haut="capuche", c_haut=(60, 60, 70), bas="jean", c_bas=(50, 60, 90), chaussures="baskets", details=("lunettes_vue", "ecouteurs"))),
    "avocat": dict(mots=r"avocate?s?|ma[iî]tre [A-Z]|notaires?", outil="valise",
                   costume=dict(haut="costume", c_haut=(30, 30, 38), bas="pantalon", c_bas=(30, 30, 38), chaussures="ville", c_chaussures=(15, 15, 15), details=("cravate",), c_cravate=(110, 30, 40))),
    "juge": dict(mots=r"juges?|tribunal|votre honneur|monsieur le juge|madame la juge", outil="marteau_juge",
                 costume=dict(haut="robe", c_haut=(25, 25, 30), bas="pantalon", c_bas=(25, 25, 30), chaussures="ville", details=("lunettes_vue",))),
    "astronaute": dict(mots=r"astronautes?|cosmonautes?|spationautes?|fus[ée]e", outil=None,
                       costume=dict(haut="combinaison", c_haut=(240, 242, 246), bas="pantalon", c_bas=(240, 242, 246), chaussures="bottes", c_chaussures=(200, 205, 215), chapeau="casque_astronaute")),
    "livreur": dict(mots=r"livreu(?:r|se)s?|uber ?eats|deliveroo|coursiers?|colis", outil="colis",
                    costume=dict(haut="polo", c_haut=(40, 170, 140), bas="jean", c_bas=(50, 60, 90), chaussures="baskets", chapeau="casquette", c_chapeau=(40, 170, 140), details=("sac_a_dos",), c_sac=(40, 170, 140))),
    "facteur": dict(mots=r"facteurs?|factrice|postiers?|la poste", outil="lettre",
                    costume=dict(haut="polo", c_haut=(250, 210, 50), bas="pantalon", c_bas=(40, 60, 120), chaussures="ville", chapeau="casquette", c_chapeau=(40, 60, 120))),
    "coiffeur": dict(mots=r"coiffeu(?:r|se)s?|barbiers?", outil="ciseaux",
                     costume=dict(haut="tablier", c_haut=(40, 40, 46), c_tablier=(25, 25, 30), bas="pantalon", c_bas=(30, 30, 36), chaussures="ville")),
    "caissier": dict(mots=r"caissi[eè]re?s?", outil=None,
                     costume=dict(haut="polo", c_haut=(210, 50, 50), bas="pantalon", c_bas=(50, 55, 70), chaussures="baskets", details=("badge",))),
    "vigile": dict(mots=r"vigiles?|agents? de s[ée]curit[ée]|videurs?", outil="talkie",
                   costume=dict(haut="polo", c_haut=(25, 25, 30), bas="pantalon", c_bas=(25, 25, 30), chaussures="ville", details=("badge", "ecouteurs"))),
    "karateka": dict(mots=r"karat[ée]|judo|judoka|ceinture noire|sensei", outil=None,
                     costume=dict(haut="kimono", c_haut=(250, 250, 250), bas="pantalon", c_bas=(250, 250, 250), chaussures="", c_ceinture=(25, 25, 28))),
    "sportif": dict(mots=r"coach sportif|entra[iî]neu(?:r|se)|basketteu(?:r|se)|sportifs?|athl[èe]tes?", outil=None,
                    costume=dict(haut="maillot", c_haut=(40, 90, 200), bas="short", c_bas=(250, 250, 250), chaussures="baskets")),
    "cowboy": dict(mots=r"cow-?boys?|sh[ée]rif|far ?west", outil=None,
                   costume=dict(haut="chemise", c_haut=(180, 70, 60), motif="carreaux", bas="jean", c_bas=(60, 80, 120), chaussures="bottes", c_chaussures=(110, 70, 40), chapeau="chapeau_cowboy", details=("ceinture",))),
    "sorcier": dict(mots=r"sorci[eè]re?s?", outil="baguette_magique",
                    costume=dict(haut="robe", c_haut=(80, 50, 150), bas="pantalon", c_bas=(60, 40, 110), chaussures="ville", chapeau="chapeau_sorcier", c_chapeau=(80, 50, 150))),
    "agent_secret": dict(mots=r"agent secret|espions?|james bond|mission secr[eè]te", outil=None,
                         costume=dict(haut="costume", c_haut=(20, 20, 24), bas="pantalon", c_bas=(20, 20, 24), chaussures="ville", c_chaussures=(10, 10, 10), details=("lunettes_soleil", "cravate", "ecouteurs"), c_cravate=(20, 20, 24))),
}

# 45 métiers de plus (liste gardée par l'auteur, créée avec le style croquis le 30 octobre 2026)
def _m(mots, haut, ch, bas="pantalon", cb=None, chapeau=None, cc=None, outil=None, details=(), **x):
    c = dict(haut=haut, c_haut=ch, bas=bas, c_bas=cb or ch, chaussures="ville")
    if chapeau: c["chapeau"] = chapeau
    if cc: c["c_chapeau"] = cc
    if details: c["details"] = tuple(details)
    c.update(x)
    return dict(mots=mots, outil=outil, costume=c)
CATALOGUE.update({
    "ambulancier": _m(r"ambulanci[eè]re?s?|secouristes?", "polo", (250, 250, 250), cb=(40, 60, 110), details=("bandes", "badge"), outil="porte_bloc"),
    "sage_femme": _m(r"sages?-femmes?|maïeuticien", "tunique_med", (230, 150, 190), outil="porte_bloc"),
    "kine": _m(r"kin[ée]s?\b|kin[ée]sith[ée]rapeutes?|ost[ée]opathes?", "polo", (250, 250, 250), cb=(60, 70, 90), details=("badge",)),
    "opticien": _m(r"opticien(?:ne)?s?", "blouse", (250, 250, 250), cb=(60, 70, 90), details=("lunettes_vue",)),
    "pharmacien": _m(r"pharmacien(?:ne)?s?", "blouse", (250, 250, 250), cb=(60, 120, 80), details=("badge", "lunettes_vue")),
    "psychologue": _m(r"psys?\b|psychologues?|psychiatres?|th[ée]rapeutes?", "gilet", (120, 100, 80), cb=(80, 70, 60), details=("lunettes_vue",), outil="porte_bloc"),
    "vendeur": _m(r"vendeu(?:r|se)s?", "polo", (60, 120, 200), cb=(50, 55, 70), details=("badge",)),
    "fleuriste": _m(r"fleuristes?", "tablier", (120, 170, 110), outil="fleur", c_tablier=(120, 170, 110)),
    "boucher": _m(r"bouch(?:er|[eè]re)s?|boucherie", "tablier", (250, 250, 250), cb=(70, 70, 80), c_tablier=(250, 250, 250), chapeau="calot"),
    "poissonnier": _m(r"poissonni(?:er|[eè]re)s?", "tablier", (90, 140, 200), c_tablier=(90, 140, 200), chapeau="bob", cc=(90, 140, 200)),
    "patissier": _m(r"p[âa]tissi(?:er|[eè]re)s?|p[âa]tisserie", "veste_chef", (250, 250, 250), cb=(240, 180, 200), chapeau="toque"),
    "barista": _m(r"baristas?|serveu(?:r|se) de caf[ée]", "tablier", (60, 50, 45), c_tablier=(60, 50, 45), outil="cafe", chapeau="casquette", cc=(60, 50, 45)),
    "livreur_pizza": _m(r"livreu(?:r|se)s? de pizzas?|pizza ?boy", "polo", (220, 50, 50), cb=(50, 55, 70), chapeau="casquette", cc=(220, 50, 50), outil="pizza"),
    "chauffeur_bus": _m(r"chauffeu(?:r|se)s? de bus|conducteu(?:r|se)s? de bus|machiniste", "chemise", (170, 200, 230), cb=(40, 50, 80), details=("cravate",), c_cravate=(40, 50, 80)),
    "chauffeur_vtc": _m(r"chauffeu(?:r|se)s?|vtc|uber\b|taxis?", "costume", (30, 30, 36), details=("cravate",), c_cravate=(30, 30, 36)),
    "conducteur_train": _m(r"conducteu(?:r|se)s? de trains?|cheminots?|aiguilleu(?:r|se)", "uniforme", (40, 60, 110), chapeau="casquette_officier", cc=(40, 60, 110)),
    "capitaine": _m(r"capitaines?|marins?|matelots?|bateau", "uniforme", (250, 250, 250), cb=(250, 250, 250), chapeau="casquette_officier", cc=(250, 250, 250), details=("boutons_or",)),
    "controleur": _m(r"contr[ôo]leu(?:r|se)s?|billets?,? s'il vous pla[iî]t", "uniforme", (40, 60, 110), chapeau="casquette_officier", cc=(40, 60, 110), outil="billet"),
    "militaire": _m(r"militaires?|soldats?|sergent|l'arm[ée]e|caporal", "uniforme", (90, 110, 70), chapeau="beret", cc=(80, 100, 60), motif="camouflage"),
    "gendarme": _m(r"gendarmes?|gendarmerie", "uniforme", (40, 55, 100), chapeau="casquette_officier", cc=(30, 40, 80), details=("badge",), outil="talkie"),
    "douanier": _m(r"douani(?:er|[eè]re)s?|douane", "uniforme", (50, 70, 90), chapeau="casquette_officier", cc=(50, 70, 90), details=("badge",)),
    "garde_du_corps": _m(r"gardes? du corps|bodyguards?", "costume", (20, 20, 24), details=("lunettes_soleil", "cravate", "ecouteurs"), c_cravate=(20, 20, 24)),
    "maitre_nageur": _m(r"ma[iî]tres?[- ]nageu(?:r|se)s?|surveillant de baignade", "debardeur", (220, 50, 50), bas="short", cb=(220, 50, 50), details=("sifflet",)),
    "journaliste": _m(r"journalistes?|reporters?|reportage", "chemise", (200, 210, 230), cb=(60, 70, 90), outil="micro"),
    "presentateur_tele": _m(r"pr[ée]sentat(?:eur|rice) t[ée]l[ée]|animat(?:eur|rice) t[ée]l[ée]|bonsoir et bienvenue", "costume", (60, 40, 100), details=("cravate",), c_cravate=(220, 180, 40), outil="micro"),
    "youtubeur": _m(r"youtubeu(?:r|se)s?|streameu(?:r|se)s?|influenceu(?:r|se)s?|twitch|abonnez-vous", "capuche", (240, 70, 70), bas="jean", cb=(50, 60, 90), details=("ecouteurs",), outil="telephone"),
    "chanteur": _m(r"chanteu(?:r|se)s?|star de la chanson", "veste_jean", (60, 90, 160), bas="jean", cb=(30, 30, 40), outil="micro", details=("chaine",)),
    "dj": _m(r"\bdj\b|disc[- ]jockey|platines", "tshirt", (30, 30, 36), bas="jean", cb=(30, 30, 40), chapeau="casque_audio"),
    "magicien": _m(r"magicien(?:ne)?s?|tour de magie|abracadabra", "costume", (30, 30, 40), chapeau="chapeau", cc=(25, 25, 30), details=("cape", "noeud_pap"), outil="baguette_magique"),
    "clown": _m(r"clowns?|cirque", "chemise", (250, 220, 60), cb=(60, 120, 220), motif="pois", details=("nez_rouge", "noeud_pap"), chapeau="chapeau", cc=(220, 60, 60)),
    "footballeur": _m(r"footballeu(?:r|se)s?|joueu(?:r|se) de foot|attaquant|gardien de but", "maillot", (30, 80, 200), bas="short", cb=(250, 250, 250)),
    "macon": _m(r"ma[çc]ons?|ma[çc]onnerie", "tshirt", (240, 140, 40), bas="jean", cb=(110, 100, 90), chapeau="casque_chantier", outil="marteau"),
    "menuisier": _m(r"menuisi(?:er|[eè]re)s?|charpenti(?:er|[eè]re)s?|[ée]b[ée]nistes?", "salopette", (200, 170, 130), c_salopette=(120, 90, 60), outil="marteau"),
    "peintre_batiment": _m(r"peintres? en b[âa]timent|repeindre le mur|rouleau de peinture", "salopette", (250, 250, 250), c_salopette=(250, 250, 250), taches_peinture=True, chapeau="casquette", cc=(250, 250, 250)),
    "agent_entretien": _m(r"femme de m[ée]nage|homme de m[ée]nage|agent d'entretien|concierge|balayeu(?:r|se)", "blouse", (110, 170, 200), cb=(60, 80, 110)),
    "baby_sitter": _m(r"baby-?sitt(?:er|eur|euse|ing)|nounou", "pull", (240, 170, 190), bas="jean", cb=(60, 80, 130)),
    "demenageur": _m(r"d[ée]m[ée]nageu(?:r|se)s?|d[ée]m[ée]nagement|cartons", "tshirt", (90, 90, 100), bas="jean", cb=(60, 70, 90), outil="colis"),
    "pirate": _m(r"pirates?|corsaires?|capitaine crochet|tr[ée]sor", "chemise", (250, 250, 250), cb=(40, 40, 50), motif="rayures", c_motif=(200, 40, 40), chapeau="tricorne", cc=(30, 30, 34), details=("cache_oeil",)),
    "chevalier": _m(r"chevaliers?|armure|[ée]p[ée]e|roi arthur", "tunique", (170, 175, 185), cb=(140, 145, 155), chapeau="casque_chevalier", cc=(170, 175, 185)),
    "super_heros": _m(r"super-?h[ée]ros|superman|batman|spider-?man|super-?pouvoirs?", "combinaison", (40, 80, 200), cb=(40, 80, 200), details=("cape", "logo")),
    "pere_noel": _m(r"p[èe]re no[ëe]l|ho ho ho|tra[iî]neau|lutins?", "doudoune", (210, 40, 40), cb=(210, 40, 40), chapeau="bonnet_noel", details=("ceinture",), barbe_blanche=True),
    "vampire": _m(r"vampires?|dracula", "costume", (25, 20, 30), details=("cape", "crocs"), teint=(232, 232, 240)),
    "zombie": _m(r"zombies?|mort-vivant|morts-vivants", "tshirt", (110, 110, 100), bas="jean", cb=(70, 80, 90), details=("dechire",), teint=(170, 205, 150)),
    "momie": _m(r"momies?|pharaon", "tunique", (230, 220, 190), cb=(230, 220, 190), details=("bandelettes",), teint=(236, 228, 200)),
    "extraterrestre": _m(r"extra-?terrestres?|aliens?|martiens?|ovni", "combinaison", (160, 170, 190), details=("antennes",), teint=(150, 220, 130)),
})

OUTILS = ("lance", "talkie", "porte_bloc", "poele", "baguettes", "plans", "marteau", "tournevis", "cle_molette", "fourche", "arrosoir", "palette",
          "guitare", "plateau", "eprouvette", "ordinateur", "colis", "ciseaux", "marteau_juge", "baguette_magique", "sac_main", "casque_moto")


# ------------------------------------------------------------------ qui exerce quel métier (d'après les répliques)
def _motif(m): return re.compile(r"(?<![\w'])(?:" + m + r")(?!\w)", re.I)


def qui_fait(sk):
    """{rôle: métier}. « je suis / moi c'est / en tant que <métier> » : celui qui parle ; « t'es / vous êtes <métier> ? », « docteur, … »,
    « bonjour docteur », « merci chef » : celui à qui il parle (l'autre personnage de l'échange). Un métier juste cité (« les pompiers
    arrivent », « mon père est plombier ») n'habille personne."""
    reps = [r for r in (sk.get("repliques") or []) if isinstance(r, dict)]
    roles = [r for r in dict.fromkeys(x.get("p") for x in reps) if r and r != "narrateur"]
    if not roles: return {}
    votes = {}
    def voter(role, metier, poids):
        if role in roles: votes.setdefault(role, {}).setdefault(metier, 0); votes[role][metier] += poids
    def autre(i):
        """L'autre personnage de l'échange : la réplique d'avant ou d'après qui n'est pas de lui."""
        moi = reps[i].get("p")
        for j in (i - 1, i + 1, i - 2, i + 2):
            if 0 <= j < len(reps) and reps[j].get("p") not in (moi, "narrateur", None): return reps[j]["p"]
        return next((r for r in roles if r != moi), None)
    for i, r in enumerate(reps):
        t = " " + str(r.get("t") or "").lower().replace("’", "'") + " "
        for nom, m in CATALOGUE.items():
            mm = m["mots"]
            if re.search(r"\b(je suis|j'suis|chuis|moi c'est|en tant que|je travaille comme|je bosse comme|mon m[ée]tier c'est|moi,? je suis)\s+(?:un |une |le |la |l')?(?:" + mm + r")(?!\w)", t, re.I):
                voter(r.get("p"), nom, 3)
            if re.search(r"\b(t'es|tu es|vous [êe]tes|t'[ée]tais|vous [ée]tiez|c'est toi le|c'est vous le|c'est vous la)\s+(?:un |une |le |la |l')?(?:" + mm + r")(?!\w)", t, re.I):
                voter(autre(i), nom, 3)
            if re.search(r"(?:^\s*|[.!?,]\s*|\b(?:bonjour|merci|pardon|excusez-moi|oui|non|allô|au revoir|salut)\s+)(?:monsieur le |madame la |monsieur l'|madame l')?(?:" + mm + r")\s*[,!?.]", t, re.I) \
               and nom in ("medecin", "policier", "juge", "enseignant", "serveur", "cuisinier", "pilote", "infirmier", "veterinaire", "dentiste", "avocat"):
                voter(autre(i), nom, 2)                                    # « Docteur, j'ai mal », « Merci chef ! » : on s'adresse à lui
    out = {}
    for role, v in votes.items():
        metier, pts = max(v.items(), key=lambda kv: kv[1])
        if pts >= 2 and metier not in out.values(): out[role] = metier
    return out


def costume(metier, base=None, genre=None):
    """Costume du métier (copie), posé sur le costume de base (coiffure, couleurs de peau… gardées)."""
    m = CATALOGUE.get(metier)
    if not m: return base
    c = dict(base or {}); c.update(dict(m["costume"]))
    if not m["costume"].get("details"): c.pop("details", None)
    if m.get("outil"): c["outil"] = m["outil"]
    c["metier"] = metier
    if genre == "f" and metier in ("hotesse",): c["bas"] = "jupe"
    return c


# ------------------------------------------------------------------ outils tenus en main (même calque RGBA que marionnette.objet)
def outil(nom, s=1.0):
    """Outil dessiné (calque RGBA, trait noir épais façon planches de l'auteur), tenu par la main (centre du calque = la main)."""
    if nom not in OUTILS: return None
    grands = {"lance": (200, 200), "fourche": (110, 300), "guitare": (150, 260), "plans": (170, 170), "baguettes": (170, 190), "baguette_magique": (90, 200)}
    W, H = grands.get(nom, (150, 170)); k = s * 1.3                       # outils bien visibles (plus grands que les petits objets)
    im = np.zeros((int(H * k), int(W * k), 4), np.uint8)
    P = lambda pts: np.array([[x * k, y * k] for x, y in pts], np.int32)
    def poly(pts, c, e=6):
        cv2.fillPoly(im, [P(pts)], tuple(c) + (255,), AA); cv2.polylines(im, [P(pts)], True, TRAIT + (255,), max(1, int(e * k)), AA)
    def cer(x, y, r, c, e=6):
        cv2.circle(im, (int(x * k), int(y * k)), int(r * k), tuple(c) + (255,), -1, AA)
        if e: cv2.circle(im, (int(x * k), int(y * k)), int(r * k), TRAIT + (255,), max(1, int(e * k)), AA)
    def ell(x, y, a, b, ang, c, e=6):
        cv2.ellipse(im, (int(x * k), int(y * k)), (int(a * k), int(b * k)), ang, 0, 360, tuple(c) + (255,), -1, AA)
        if e: cv2.ellipse(im, (int(x * k), int(y * k)), (int(a * k), int(b * k)), ang, 0, 360, TRAIT + (255,), max(1, int(e * k)), AA)
    def lig(a, b, c, e):
        cv2.line(im, (int(a[0] * k), int(a[1] * k)), (int(b[0] * k), int(b[1] * k)), tuple(c) + (255,), max(1, int(e * k)), AA)
    def tige(a, b, c, e):                                                  # bâton cerné de noir
        lig(a, b, TRAIT, e + 10); lig(a, b, c, e)
    if nom == "lance":                                                     # lance à incendie + tuyau, jet d'eau
        cv2.ellipse(im, (int(40 * k), int(160 * k)), (int(70 * k), int(40 * k)), 0, 180, 300, TRAIT + (255,), int(26 * k), AA)
        cv2.ellipse(im, (int(40 * k), int(160 * k)), (int(70 * k), int(40 * k)), 0, 180, 300, (200, 60, 50, 255), int(16 * k), AA)
        poly([(70, 95), (150, 70), (158, 88), (78, 116)], (60, 60, 66)); poly([(150, 66), (172, 60), (178, 92), (158, 92)], (215, 175, 70))
        for j in range(5): cer(188 - j * 2, 70 + j * 6, 6 - j * 0.6, (120, 190, 250), 0)
    elif nom == "talkie":
        poly([(48, 50), (100, 50), (100, 150), (48, 150)], (40, 40, 46)); lig((88, 50), (88, 12), TRAIT, 10)
        poly([(58, 62), (90, 62), (90, 88), (58, 88)], (140, 200, 150), 4)
        for j in range(3): lig((60, 104 + j * 12), (88, 104 + j * 12), (90, 90, 98), 4)
    elif nom == "porte_bloc":                                              # porte-bloc + feuille
        poly([(25, 25), (125, 25), (125, 160), (25, 160)], (160, 110, 60)); poly([(35, 40), (115, 40), (115, 150), (35, 150)], (250, 250, 248), 4)
        poly([(55, 15), (95, 15), (95, 35), (55, 35)], (190, 195, 205), 5)
        for j in range(5): lig((45, 62 + j * 18), (105 - (j % 2) * 20, 62 + j * 18), (130, 140, 170), 4)
    elif nom == "poele":
        lig((75, 150), (75, 95), TRAIT, 26); lig((75, 150), (75, 97), (60, 45, 35), 16)
        ell(75, 60, 62, 38, 0, (50, 50, 56)); ell(75, 56, 46, 26, 0, (90, 90, 98), 0)
        ell(62, 52, 16, 11, 0, (250, 250, 245), 3); cer(66, 52, 6, (250, 200, 50), 0)       # un œuf au plat
    elif nom == "baguettes":
        for j, (dx, ang) in enumerate(((0, -20), (28, -8), (54, 6))):
            ell(55 + dx, 95, 22, 88, ang, (220, 165, 85), 5)
            for q in range(4): lig((48 + dx + ang * 0.3, 40 + q * 32), (64 + dx + ang * 0.3, 50 + q * 32), (175, 115, 50), 4)
    elif nom == "plans":                                                   # plans roulés (architecte, ingénieur)
        poly([(20, 130), (130, 20), (155, 45), (45, 155)], (90, 140, 210)); ell(143, 32, 18, 12, -45, (190, 215, 245), 5)
        for j in range(3): lig((48 + j * 25, 120 - j * 25), (68 + j * 25, 140 - j * 25), (240, 245, 250), 3)
    elif nom == "marteau":
        tige((75, 160), (75, 50), (160, 110, 60), 14); poly([(35, 30), (115, 30), (115, 60), (35, 60)], (110, 115, 125))
    elif nom == "tournevis":
        tige((75, 20), (75, 90), (180, 185, 195), 7); poly([(58, 90), (92, 90), (95, 160), (55, 160)], (240, 200, 40))
    elif nom == "cle_molette":                                             # clé à molette (plombier, mécanicien)
        tige((75, 165), (75, 60), (200, 50, 50), 18)
        poly([(45, 70), (105, 70), (110, 40), (90, 15), (78, 40), (72, 40), (60, 15), (40, 40)], (150, 155, 165))
    elif nom == "fourche":
        tige((55, 295), (55, 80), (160, 110, 60), 12); poly([(20, 82), (90, 82), (90, 94), (20, 94)], (130, 135, 145), 5)
        for x_ in (25, 55, 85): tige((x_, 88), (x_, 15), (150, 155, 165), 5)
    elif nom == "arrosoir":
        poly([(35, 70), (110, 70), (115, 150), (30, 150)], (70, 150, 90)); lig((110, 120), (150, 70), TRAIT, 20); lig((110, 120), (150, 70), (70, 150, 90), 10)
        ell(150, 66, 12, 8, -40, (90, 170, 110), 5); cv2.ellipse(im, (int(72 * k), int(70 * k)), (int(34 * k), int(34 * k)), 0, 180, 360, TRAIT + (255,), int(10 * k), AA)
        for j in range(4): cer(160 + j * 4, 56 + j * 12, 4, (120, 190, 250), 0)
    elif nom == "palette":                                                 # palette de peintre + pinceau
        ell(70, 95, 62, 48, -15, (225, 195, 140)); ell(48, 110, 10, 9, 0, (238, 238, 238), 0)
        for (x_, y_, c) in ((40, 80, (220, 60, 60)), (70, 70, (250, 200, 50)), (100, 82, (60, 120, 220)), (102, 110, (80, 170, 90)), (78, 125, (200, 90, 200))): cer(x_, y_, 10, c, 4)
        tige((120, 20), (95, 140), (160, 110, 60), 6); ell(120, 18, 6, 12, -15, (60, 120, 220), 3)
    elif nom == "guitare":
        tige((75, 15), (75, 140), (150, 100, 55), 14); poly([(62, 8), (88, 8), (88, 30), (62, 30)], (80, 55, 35), 5)
        ell(75, 165, 52, 50, 0, (215, 140, 60)); ell(75, 215, 64, 46, 0, (215, 140, 60)); ell(75, 165, 46, 44, 0, (215, 140, 60), 0); cer(75, 180, 15, (60, 40, 30), 4)
        for j in range(3): lig((70 + j * 5, 20), (70 + j * 5, 230), (230, 230, 230), 1.5)
    elif nom == "plateau":                                                 # plateau de serveur avec cloche
        ell(75, 120, 70, 14, 0, (200, 205, 215)); cv2.ellipse(im, (int(75 * k), int(118 * k)), (int(52 * k), int(52 * k)), 0, 180, 360, TRAIT + (255,), -1, AA)
        cv2.ellipse(im, (int(75 * k), int(118 * k)), (int(46 * k), int(46 * k)), 0, 180, 360, (215, 220, 230, 255), -1, AA); cer(75, 64, 9, (215, 220, 230), 5)
        lig((48, 95), (60, 80), (250, 252, 255), 5)
    elif nom == "eprouvette":                                              # fiole de chimiste, liquide vert qui bulle
        poly([(62, 30), (88, 30), (88, 70), (125, 150), (25, 150), (62, 70)], (235, 245, 250)); poly([(45, 115), (105, 115), (125, 150), (25, 150)], (120, 210, 90), 0)
        cv2.polylines(im, [P([(62, 30), (88, 30), (88, 70), (125, 150), (25, 150), (62, 70)])], True, TRAIT + (255,), int(6 * k), AA)
        for j in range(3): cer(70 + j * 8, 22 - j * 10, 5 + j, (150, 230, 120), 3)
    elif nom == "ordinateur":                                              # ordinateur portable ouvert « </> »
        poly([(15, 30), (135, 30), (135, 110), (15, 110)], (60, 62, 70)); poly([(25, 40), (125, 40), (125, 100), (25, 100)], (40, 70, 110), 3)
        cv2.putText(im, "</>", (int(45 * k), int(80 * k)), cv2.FONT_HERSHEY_SIMPLEX, 0.9 * k, (120, 220, 250, 255), max(1, int(3 * k)), AA)
        poly([(5, 110), (145, 110), (135, 130), (15, 130)], (170, 175, 185))
    elif nom == "colis":                                                   # carton de livraison
        poly([(20, 55), (130, 55), (130, 150), (20, 150)], (200, 150, 90)); poly([(20, 55), (50, 30), (155, 30), (130, 55)], (220, 175, 115)); poly([(130, 55), (155, 30), (155, 125), (130, 150)], (175, 125, 70))
        lig((75, 55), (75, 150), (230, 210, 160), 10); lig((75, 55), (102, 30), (230, 210, 160), 10)
    elif nom == "ciseaux":
        for sg in (-1, 1): tige((75, 90), (75 + sg * 35, 15), (190, 195, 205), 7)
        cer(55, 125, 20, (220, 60, 60)); cer(95, 125, 20, (220, 60, 60)); cer(55, 125, 9, (0, 0, 0), 0); cer(95, 125, 9, (0, 0, 0), 0)
        im[..., 3][np.all(im[..., :3] == 0, axis=-1)] = 0
    elif nom == "marteau_juge":
        tige((40, 150), (95, 70), (130, 80, 45), 12); poly([(70, 30), (140, 70), (125, 95), (55, 55)], (140, 90, 50))
    elif nom == "baguette_magique":
        tige((45, 190), (45, 50), (30, 30, 35), 9); lig((45, 50), (45, 32), (250, 250, 250), 9)
        for j in range(6): a = j * math.pi / 3; lig((45, 30), (45 + 22 * math.cos(a), 30 + 22 * math.sin(a)), (250, 215, 70), 4)
    elif nom == "sac_main":                                                # sac à main (anse + rabat + fermoir doré)
        cv2.ellipse(im, (int(75 * k), int(70 * k)), (int(38 * k), int(40 * k)), 0, 180, 360, TRAIT + (255,), int(9 * k), AA)
        poly([(25, 70), (125, 70), (135, 150), (15, 150)], (180, 60, 90)); poly([(25, 70), (125, 70), (110, 105), (40, 105)], (150, 45, 75)); cer(75, 103, 7, (240, 200, 70), 3)
    elif nom == "casque_moto":                                             # casque de moto (visière teintée)
        cv2.ellipse(im, (int(75 * k), int(95 * k)), (int(62 * k), int(60 * k)), 0, 0, 360, (210, 50, 50, 255), -1, AA); cv2.ellipse(im, (int(75 * k), int(95 * k)), (int(62 * k), int(60 * k)), 0, 0, 360, TRAIT + (255,), int(6 * k), AA)
        poly([(40, 80), (130, 80), (130, 115), (45, 115)], (40, 50, 70)); lig((48, 88), (90, 88), (150, 170, 200), 5)
    return im
