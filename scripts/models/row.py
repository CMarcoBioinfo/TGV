class Row:
    """
    Représente une ligne finale (simple ou clinique) pour l'UI.
    """

    def __init__(
        self,
        locus,
        position,
        depth,
        size,
        motifs,
        genotype,
        classification,
        rep1,
        rep2,
        seg1,
        seg2,
    ):
        self.locus = locus
        self.position = position
        self.depth = depth
        self.size = size
        self.motifs = motifs
        self.genotype = genotype
        self.classification = classification
        self.rep1 = rep1
        self.rep2 = rep2
        self.seg1 = seg1
        self.seg2 = seg2

    def __repr__(self):
        return (
            f"Row("
            f"locus={self.locus!r}, "
            f"position={self.position!r}, "
            f"depth={self.depth}, "
            f"size={self.size!r}, "
            f"motifs={self.motifs!r}, "
            f"genotype={self.genotype!r}, "
            f"classification={self.classification!r}, "
            f"rep1={self.rep1!r}, "
            f"rep2={self.rep2!r}, "
            f"seg1={self.seg1!r}, "
            f"seg2={self.seg2!r}"
            f")"
        )


    def to_dict(self):
        return {
            "Locus": self.locus,
            "Position": self.position,
            "Profondeur (DP)": self.depth,
            "Taille (bp)": self.size,
            "Motifs": self.motifs,
            "Génotype": self.genotype,
            "Classification": self.classification,
            "Allèle 1 - Répétition": self.rep1,
            "Allèle 2 - Répétition": self.rep2,
            "Allèle 1 - Segmentation": self.seg1,
            "Allèle 2 - Segmentation": self.seg2,
        }
