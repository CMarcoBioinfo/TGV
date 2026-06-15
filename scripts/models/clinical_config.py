class ClinicalConfig:
    """
    Paramètres cliniques d’un TRID (issus du YAML).
    """
    def __init__(self):
        self.enabled = False
        self.classification_mode = None
        self.repeat_mode = None
        self.genotype_display = None
        self.orientation = None

        self.pathogenic_motifs = []
        self.protective_motifs = []
        self.uncertain_motifs = []
        self.pure_only = None

        self.groups = {}



class ClinicalGroup:
    """
    Groupe clinique : motifs, thresholds, structure_rules.
    """
    def __init__(self, name):
        self.name = name
        self.motifs = []
        self.thresholds = {}
        self.structure_rules = []

    def __repr__(self):
        return (
            f"ClinicalGroup({self.name}, "
            f"motifs={self.motifs}, "
            f"thresholds={list(self.thresholds.keys())}, "
            f"rules={len(self.structure_rules)})"
        )
