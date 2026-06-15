import os
import sys
import yaml
from functools import lru_cache
from scripts.core.config_manager import get_safe_config_path

# ============================================================
# Chargement du YAML
# ============================================================

@lru_cache(maxsize=1)  # Évite de relire et re-parser le YAML sur le disque à chaque appel sans 'data'
def load_clinical_thresholds():
    """
    Charge le fichier clinical_thresholds.yaml.
    Cherche en priorité à côté de l'exécutable (externe), puis dans les sources (interne).
    Renvoie {} si le fichier est absent, vide ou illisible.
    """

    yaml_path = get_safe_config_path("clinical_thresholds.yaml")

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data is None:
                print(f"[WARN] clinical_thresholds.yaml est vide.")
                return {}
            print(f"[INFO] Fichier de seuils chargé depuis : {yaml_path}")
            return data

    except Exception as e:
        print(f"[WARN] Erreur lors du chargement de clinical_thresholds.yaml : {e}")
        return {}


# ============================================================
# Getter priority
# ============================================================

def get_locus_priority(thresholds_data=None):
    """
    Retourne la liste de priorité des labels
    """
    if thresholds_data is None:
        thresholds_data = load_clinical_thresholds()

    return thresholds_data.get("label_priority", {}) 

# ============================================================
# Getter principal : bloc complet d’un TRID
# ============================================================

def get_locus_config(trid, thresholds_data=None):
    """
    Retourne le bloc YAML complet correspondant au TRID demandé.
    Exemple :
        cfg = get_locus_config("SCA1_ATXN1")

    Cette fonction :
        - charge le YAML si nécessaire
        - vérifie que le TRID existe
        - renvoie la configuration brute du locus
    """
    if thresholds_data is None:
        thresholds_data = load_clinical_thresholds()

    if trid not in thresholds_data:
        raise KeyError(f"Locus '{trid}' introuvable dans clinical_thresholds.yaml")

    return thresholds_data[trid]


# ============================================================
# Getters spécialisés (1 par section du YAML)
# ============================================================

def get_classification_mode(trid, data=None):
    """
    Renvoie le mode de classification :
        - "simple"
        - "structural"
    """
    locus = get_locus_config(trid, data)
    return locus["classification_mode"]


def get_repeat_mode(trid, data=None):
    locus = get_locus_config(trid, data)
    return locus.get("repeat_mode", "sum_without_interruptions")


def get_genotype_display(trid, data=None):
    locus = get_locus_config(trid, data)
    return locus.get("genotype_display", "full_with_others")


def get_orientation(trid, data=None):
    """
    Renvoie l’orientation logique du locus :
        - "FW"
        - "RC"
    """
    locus = get_locus_config(trid, data)
    return locus["orientation"]


def get_motif_properties(trid, data=None):
    """
    Renvoie le bloc motif_properties :
        - pathogenic_motifs
        - pure_only
        - motif_groups
    """
    locus = get_locus_config(trid, data)
    return locus["motif_properties"]


def get_pure_only(trid, data=None):
    """
    Renvoie la valeur pure_only du locus (true/false).
    Contrôle uniquement l'affichage du génotype.
    """
    locus = get_locus_config(trid, data)
    return locus["motif_properties"].get("pure_only", False)


def get_pathogenic_motifs(trid, data=None):
    """
    Renvoie la liste des motifs pathogènes du locus.
    Exemple : ["CAG", "CAA"]
    """
    locus = get_locus_config(trid, data)
    return locus["motif_properties"].get("pathogenic_motifs", [])


def get_group_ids(trid, data=None):
    """
    Renvoie la liste des GROUP_ID définis pour ce locus.
    Exemple : ["CAG_CAA"], ["AAGGG", "AAAGG", "ACAGG", "AGGGC"]
    """
    locus = get_locus_config(trid, data)
    return list(locus["motif_properties"]["motif_groups"].keys())


def get_motif_groups(trid, data=None):
    """
    Renvoie le dictionnaire complet des motif_groups.
    Exemple :
        {"CAG_CAA": ["CAG", "CAA"]}
    """
    locus = get_locus_config(trid, data)
    return locus["motif_properties"]["motif_groups"]

def get_protective_motifs(trid, data=None):
    """
    Renvoie les motifs protecteurs (si définis).
    """
    locus = get_locus_config(trid, data)
    return locus["motif_properties"].get("protective_motifs", [])

    
def get_uncertain_motifs(trid, data=None):
    """
    Renvoie les motifs incertains (si définis).
    """
    locus = get_locus_config(trid, data)
    return locus["motif_properties"].get("uncertain_motifs", [])

# ============================================================
# Thresholds et Structure Rules (TOUS les groupes)
# ============================================================

def get_thresholds(trid, data=None):
    """
    Renvoie tous les thresholds du locus, pour tous les GROUP_ID.
    Exemple :
        {
            "CAG_CAA": {...},
            "GAA": {...},
            "AAGGG": {...}
        }

    Le moteur clinique choisira ensuite le groupe pertinent.
    """
    locus = get_locus_config(trid, data)
    return locus["thresholds"]


def get_structure_rules(trid, data=None):
    """
    Renvoie toutes les structure_rules du locus, pour tous les GROUP_ID.
    Exemple :
        {
            "CAG_CAA": [...],
            "GAA": [...],
            "AAGGG": [...]
        }

    Le moteur clinique appliquera ensuite les règles du groupe actif.
    """
    locus = get_locus_config(trid, data)
    return locus["structure_rules"]
