class TRGTGroupData:
    """
    Données TRGT finales pour un groupe clinique.
    Structure haut-niveau : uniquement les résultats utiles.
    """

    def __init__(
        self,
        mode,
        main_motif,
        main_len,
        total_main_count_without,
        total_main_count_with,
        short,
        long,
        others,
        m_without,
        m_with,
        i_count,
        clinical = None,
    ):
        self.mode = mode

        # Bloc 1
        self.main_motif = main_motif
        self.main_len = main_len
        self.total_main_count_without = total_main_count_without
        self.total_main_count_with = total_main_count_with

        # Bloc 2
        self.short = short
        self.long = long
        self.others = others

        # Bloc 3
        self.m_without = m_without
        self.m_with = m_with
        self.i_count = i_count

        #Bloc clinique  
        self.clinical = clinical

    # ------------------------------------------------------------------
    # Représentation complète (affichée dans print ET dans repr)
    # ------------------------------------------------------------------
    def __repr__(self):
        return self._pretty()

    def __str__(self):
        return self._pretty()

    def _pretty(self):
        return (
            "TRGTGroupData(\n"
            f"  mode={self.mode},\n"
            f"  clinical={self.clinical}\n"
            f"  main_motif={self.main_motif},\n"
            f"  main_len={self.main_len},\n"
            f"  total_main_count_without={self.total_main_count_without},\n"
            f"  total_main_count_with={self.total_main_count_with},\n"
            f"  m_without={self.m_without},\n"
            f"  m_with={self.m_with},\n"
            f"  i_count={self.i_count},\n"
            f"  short={self.short},\n"
            f"  long={self.long},\n"
            f"  others={self.others}\n"
            ")"
        )

