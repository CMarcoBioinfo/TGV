from scripts.models.clinical_config import ClinicalConfig, ClinicalGroup

from scripts.bio.clinical_thresholds_loader import get_locus_config

def build_clinical_config(trid, thresholds_data=None):
    cc = ClinicalConfig()

    # 1) Charger le bloc YAML (ou désactiver si absent)
    try:
        cfg_yaml = get_locus_config(trid, thresholds_data)
        cc.enabled = True
    except KeyError:
        cc.enabled = False
        return cc

    # 2) Champs simples
    cc.classification_mode = cfg_yaml.get("classification_mode")
    cc.repeat_mode = cfg_yaml.get("repeat_mode")
    cc.genotype_display = cfg_yaml.get("genotype_display")
    cc.orientation = cfg_yaml.get("orientation")

    # 3) Motifs
    motif_props = cfg_yaml.get("motif_properties", {})

    cc.pathogenic_motifs = list(motif_props.get("pathogenic_motifs", []))
    cc.protective_motifs = list(motif_props.get("protective_motifs", []))
    cc.uncertain_motifs = list(motif_props.get("uncertain_motifs", []))
    cc.pure_only = motif_props.get("pure_only", False)

    motif_groups = motif_props.get("motif_groups", {})

    # 4) Thresholds
    thresholds = cfg_yaml.get("thresholds", {})

    # 5) Structure rules  normalisation
    raw_rules = cfg_yaml.get("structure_rules", {})

    if isinstance(raw_rules, dict):
        structure_rules = raw_rules
    else:
        # [] ou None → aucun groupe
        structure_rules = {}

# 6) Construire les groupes cliniques
    for group_name, motifs in motif_groups.items():
        g = ClinicalGroup(group_name)

        # Si motifs est None (déclaré vide), on replie sur une liste vide
        g.motifs = list(motifs or [])
        
        # Si thresholds.get() renvoie None, 'or {}' garantit d'avoir un dictionnaire vide
        raw_thresh = thresholds.get(group_name) or {}
        g.thresholds = dict(raw_thresh)
        
        # Si structure_rules.get() renvoie None, 'or []' garantit d'avoir une liste vide
        raw_rules = structure_rules.get(group_name) or []
        g.structure_rules = list(raw_rules)

        cc.groups[group_name] = g

    return cc

