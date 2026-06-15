class TRID:
    """
    Représente un locus TRGT global dans la run.
    """
    def __init__(self, trid):
        self.trid = trid

        # Position génomique
        self.chrom = None
        self.start = None
        self.end = None
        self.motifs = []
        self.motifs_rc = None

        # Config clinique (YAML)
        self.clinical = None

        # Samples pour ce TRID
        self.samples = {}

    def __repr__(self):
        return f"TRID({self.trid}, {len(self.samples)} samples)"