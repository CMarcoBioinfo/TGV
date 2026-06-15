class Allele:
    """
    Représente un allèle TRGT + ses données dérivées.
    """
    def __init__(self, size, size_range, depth,
                 purity, methylation,
                 sequence):

        # Données TRGT brutes
        self.size = size
        self.size_range = size_range
        self.depth = depth
        self.purity = purity
        self.methylation = methylation

        # Séquence finale (déjà orientée FW ou RC)
        self.sequence = sequence

        # Résultats TRGT par groupe de motifs TRGT
        self.trgt_groups = {}   # group_id → TRGTGroupData

        # Analyse clinique (objet TRGT groupe winner)
        self.clinical_motifs = None
        self.clinical = None

    def __repr__(self):
        return (
            f"Allele(size={self.size}, "
            f"range={self.size_range}, "
            f"depth={self.depth}, "
            f"purity={self.purity}, "
            f"methylation={self.methylation})"
        )


class AlleleSequence:
    """
    Représente une séquence TRGT (FW ou RC) avec ses répétitions et sa segmentation.
    """
    def __init__(self, sequence, repetitions, segmentation):
        self.sequence = sequence
        self.repetitions = repetitions
        self.segmentation = segmentation

        self.segmentation_complete = None
        self.interruptions = None


    def __repr__(self):
        length = len(self.sequence) if self.sequence else 0
        return (
            f"AlleleSequence(len={length}, "
            f"MC={self.repetitions}, "
            f"MS={self.segmentation})"
            f"MS_complete={self.segmentation_complete})"
            f"interruptions={self.interruptions})"
        )
