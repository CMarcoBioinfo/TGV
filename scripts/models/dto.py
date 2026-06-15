class AnalysisInput:
    """
    DTO : transporte les données nécessaires à l'analyse clinique.
    """
    def __init__(self, sample_name, trids, samples, ordered_trids, paths, label_priority):
        self.sample_name = sample_name

        # TRIDs globaux sélectionnés
        self.trids = trids              # { trid_id : TRID }

        # Samples TRGT associés à ces TRIDs
        self.samples = samples          # { trid_id : Sample }

        # Ordre d'affichage
        self.ordered_trids = ordered_trids

        # Chemins utiles (VCF, BAM, motifs, meth…)
        self.paths = paths

        # Priorité clinique (YAML)
        self.label_priority = label_priority

    def iter_items(self):
        """
        Itère sur les TRIDs sélectionnés.
        Retourne (trid_id, TRID_global, Sample).
        """
        for trid_id in self.ordered_trids:
            yield trid_id, self.trids[trid_id], self.samples[trid_id]