class Run:
    """
    Représente une run TRGT complète.
    """
    def __init__(self, name, vcf_zip):
        self.name = name

        # ZIP principaux
        self.vcf_zip = vcf_zip
        self.repeat_reads_zip = None
        self.spanning_bam_zip = None
        self.motifs_allele_zip = None
        self.motifs_waterfall_zip = None
        self.meth_allele_zip = None
        self.meth_waterfall_zip = None
        self.qc_zip = None

        # Samples
        self.trids = {}

    def __repr__(self):
        return f"<Run {self.name} | {len(self.trids)} TRIDs>"
