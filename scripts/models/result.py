class Result:
    """
    Contient uniquement les données RAW nécessaires pour construire :
    - row (UI)
    - details
    - export

    Pas de pointeurs vers TRGT.
    Pas de décorations UI.
    Pas de séquences complètes.
    """

    def __init__(self):
        # Informations globales TRID
        self.trid = None
        self.clinical_name = None
        self.gene = None
        self.locus = None
        self.chrom = None
        self.start = None
        self.end = None
        self.position = None

        # Motifs
        self.motifs_raw = None
        self.motifs_used1 = None
        self.motifs_used2 = None

        # --- Allèle 1 ---
        self.depth1_raw = None
        self.size1_raw = None
        self.range_size1_raw = None
        self.purity1 = None
        self.methylation1 = None

        self.sequence1_raw = None
        self.rep1_raw = None
        self.rep1_clinical_raw = None
        self.seg1_raw = None
        self.inter1_raw = None

        self.genotype1_raw = None
        self.genotype1_bio = None
        self.classification1_raw = None
        self.classification1_bio = None

        # --- Allèle 2 ---
        self.depth2_raw = None
        self.size2_raw = None
        self.range_size2_raw = None
        self.purity2 = None
        self.methylation2 = None

        self.sequence2_raw = None
        self.rep2_raw = None
        self.rep2_clinical_raw = None
        self.seg2_raw = None
        self.inter2_raw = None

        self.genotype2_raw = None
        self.genotype2_bio = None
        self.classification2_raw = None
        self.classification2_bio = None

        # --- Objets dérivés ---
        self.display_row = None
        self.display_details = None
        self.display_export = None
        self.display_html = None
 
    def __repr__(self):
        return (
            "Result("
            f"trid={self.trid!r}, "
            f"locus={self.locus!r}, "
            f"position={self.position!r}, "
            f"motifs_raw={self.motifs_raw!r}, "
            f"motifs_used1={self.motifs_used1!r}, "
            f"motifs_used2={self.motifs_used2!r}, "

            # Allèle 1
            f"depth1={self.depth1_raw}, "
            f"size1={self.size1_raw}, "
            f"range1={self.range_size1_raw!r}, "
            f"purity1={self.purity1}, "
            f"methylation1={self.methylation1}, "
            f"rep1_raw={self.rep1_raw!r}, "
            f"rep1_clinical={self.rep1_clinical_raw!r}, "
            f"seg1={self.seg1_raw!r}, "
            f"inter1={self.inter1_raw!r}, "
            f"genotype1={self.genotype1_raw!r}, "
            f"classif1={self.classification1_raw!r}, "
            
            # Allèle 2
            f"depth2={self.depth2_raw}, "
            f"size2={self.size2_raw}, "
            f"range2={self.range_size2_raw!r}, "
            f"purity2={self.purity2}, "
            f"methylation2={self.methylation2}, "
            f"rep2_raw={self.rep2_raw!r}, "
            f"rep2_clinical={self.rep2_clinical_raw!r}, "
            f"seg2={self.seg2_raw!r}, "
            f"inter2={self.inter2_raw!r}, "
            f"genotype2={self.genotype2_raw!r}, "
            f"classif2={self.classification2_raw!r}"
            ")"
        )
