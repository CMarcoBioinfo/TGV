class DisplayRow:
    def __init__(self):
        self.locus = None
        self.depth = None
        self.size = None
        self.motifs = None

        self.genotype = None
        self.classification = None
        self.rep1 = None
        self.rep2 = None
        self.seg1 = None
        self.seg2 = None

    def to_list(self):
        return [
            self.locus,
            self.depth,
            self.size,
            self.motifs,
            self.genotype,
            self.classification,
            self.rep1,
            self.rep2,
            self.seg1,
            self.seg2,
        ]


class DisplayDetails:
    def __init__(self):
        self.locus = None
        self.depth = None
        self.size = None
        self.motifs = None
        self.purity = None
        self.methylation = None

        self.classification = None
        
        self.sequence1 = None
        self.sequence2 = None
        self.interruptions1 = None
        self.interruptions2 = None
        self.motifs_use1 = None
        self.motifs_use2 = None
        self.seg1 = None
        self.seg2 = None
        self.rep1 = None
        self.rep2 = None


class DisplayExport:
    def __init__(self):
        self.locus = None
        self.depth1 = None
        self.depth2 = None
        self.motifs = None

        self.genotype = None
        self.classification = None

    def to_list(self):
        return [
            self.locus,
            self.depth,
            self.size,
            self.motifs,
            self.genotype,
            self.classification,
        ]


class DisplayHtml:
    def __init__(self):
        self.locus = None
        self.depth = None
        self.motifs = None
        self.genotype = None
        self.classification = None
