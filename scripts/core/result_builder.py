from scripts.core.clinical_compute import build_genotype_clinical, build_repetition_clinical
from scripts.core.sequence_utils import format_interruptions, clean_and_sort_rep_string

def fill_raw_base(result, trid_id, trid, a1, a2):
    """
    Remplit les champs RAW de Result à partir des données TRGT.
    Pas de décoration.
    Pas de logique clinique.
    Pas de pointeurs vers TRGT.
    """

    # --- Informations globales ---
    result.trid = trid_id

    clinical_name, gene = trid_id.split("_", 1)
    result.clinical_name = clinical_name
    result.gene = gene
    result.locus = f"{clinical_name} ({gene})"

    result.chrom = trid.chrom
    result.start = trid.start
    result.end = trid.end
    result.position = f"{trid.chrom}:{trid.start}-{trid.end}"

    # Motifs bruts TRGT
    result.motifs_raw = trid.motifs_rc if trid.motifs_rc else trid.motifs

    # ---------------------------------------------------------
    # --- Allèle 1 ---
    # ---------------------------------------------------------
    result.depth1_raw = a1.depth
    result.size1_raw = a1.size
    result.range_size1_raw = a1.size_range
    result.purity1 = a1.purity
    result.methylation1 = a1.methylation

    result.sequence1_raw = a1.sequence.sequence

    # Nettoyage robuste rep1_raw
    result.rep1_raw = clean_and_sort_rep_string(a1.sequence.repetitions)

    # segmentation_complete → segmentation (ta classe Result)
    result.seg1_raw = a1.sequence.segmentation_complete
    result.inter1_raw = format_interruptions(a1.sequence.interruptions)

    result.classification1_raw = a1.clinical.clinical if a1.clinical else None

    # ---------------------------------------------------------
    # --- Allèle 2 ---
    # ---------------------------------------------------------
    result.depth2_raw = a2.depth
    result.size2_raw = a2.size
    result.range_size2_raw = a2.size_range
    result.purity2 = a2.purity
    result.methylation2 = a2.methylation

    result.sequence2_raw = a2.sequence.sequence

    # Nettoyage robuste rep2_raw
    result.rep2_raw = clean_and_sort_rep_string(a2.sequence.repetitions)

    result.seg2_raw = a2.sequence.segmentation_complete
    result.inter2_raw = format_interruptions(a2.sequence.interruptions)

    result.classification2_raw = a2.clinical.clinical if a2.clinical else None



def fill_clinical_base(result, trid, a1, a2, min_label):
    """
    Remplit uniquement les champs cliniques calculés :
    - genotypeX_raw
    - repX_clinical_raw

    Pas de décoration UI.
    Pas de marquage.
    Pas de Row.
    Pas de classification (déjà dans fill_raw_base).
    """

    clinical_cfg = trid.clinical
    genotype_display = clinical_cfg.genotype_display
    pure_only = clinical_cfg.pure_only

    # --- Allèle 1 ---
    if a1.clinical:
        result.genotype1_raw = build_genotype_clinical(
            clinical=a1.clinical,
            genotype_display=genotype_display,
            pure_only=pure_only,
            min_label=min_label
        )
        result.rep1_clinical_raw = build_repetition_clinical(a1.clinical)

    # --- Allèle 2 ---
    if a2.clinical:
        result.genotype2_raw = build_genotype_clinical(
            clinical=a2.clinical,
            genotype_display=genotype_display,
            pure_only=pure_only,
            min_label=min_label
        )
        result.rep2_clinical_raw = build_repetition_clinical(a2.clinical)
