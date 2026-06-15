from scripts.models.trgt_group import TRGTGroupData

from scripts.core.sequence_utils import parse_motif_counts, parse_segmentation
from scripts.core.motif_utils import extract_group_motifs, compute_interruption_bp, compute_m

from scripts.bio.clinical_thresholds_loader import get_repeat_mode, get_motif_groups



def decompose_repetition_without_interruptions(repetitions, groups):
    """
    Version haut-niveau : retourne uniquement les résultats finaux TRGT.
    Pas de rep_string, pas de variables bas-niveau.
    """

    list_repetitions = parse_motif_counts(repetitions)

    # interruptions ignorées → liste vide
    extracted, others = extract_group_motifs(list_repetitions, [], groups)
    if not extracted:
        return None

    # ----------------------------------------------------------------------
    # MODE SINGLE : un seul motif → TRGT pur
    # ----------------------------------------------------------------------
    if len(extracted) == 1:
        motif, count = extracted[0]

        return TRGTGroupData(
            mode="simple",
            main_motif=motif,
            main_len=len(motif),

            total_main_count_without=count,
            total_main_count_with=None,

            short=[(motif, count)],
            long=[],
            others=others,

            m_without=0,
            m_with=None,
            i_count=0,
        )

    # Longueurs des motifs
    motif_lengths = {len(m) for m, _ in extracted}

    # ----------------------------------------------------------------------
    # MODE SIMPLE : tous les motifs ont la même longueur
    # ----------------------------------------------------------------------
    if len(motif_lengths) == 1:
        main_len = next(iter(motif_lengths))

        # Sélection correcte du motif principal
        candidates = [(m, c) for m, c in extracted]
        main_motif, _ = max(candidates, key=lambda x: x[1])

        total_main_count_without = sum(c for _, c in extracted)

        return TRGTGroupData(
            mode="simple",
            main_motif=main_motif,
            main_len=main_len,

            total_main_count_without=total_main_count_without,
            total_main_count_with=None,

            short=extracted,
            long=[],
            others=others,

            m_without=0,
            m_with=None,
            i_count=0,
        )

    # ----------------------------------------------------------------------
    # MODE COMPLEXE : motifs longs → calcul du m (sans interruptions)
    # ----------------------------------------------------------------------

    # Sélection correcte du motif principal
    min_len = min(len(m) for m, _ in extracted)
    candidates = [(m, c) for m, c in extracted if len(m) == min_len]
    main_motif, _ = max(candidates, key=lambda x: x[1])
    main_len = min_len

    short = []
    long = []

    for motif, count in extracted:
        if len(motif) == main_len:
            short.append((motif, count))
        else:
            long.append((motif, count))

    # Calcul des unités longues
    long_with_units = []
    units_long = 0
    bp_long = 0

    for motif, count in long:
        motif_len = len(motif)
        units = motif_len // main_len
        total_units = units * count

        long_with_units.append((motif, count, total_units))

        units_long += total_units
        bp_long += motif_len * count

    # m_without = motifs longs uniquement
    m_total = compute_m(bp_long, main_len)
    m_without = max(0, m_total - units_long)

    # total TRGT final
    total_main_count = sum(c for m2, c in short if m2 == main_motif)
    total_main_count_without = total_main_count + units_long + m_without

    return TRGTGroupData(
        mode="complex",
        main_motif=main_motif,
        main_len=main_len,

        total_main_count_without=total_main_count_without,
        total_main_count_with=None,

        short=short,
        long=long_with_units,
        others=others,

        m_without=m_without,
        m_with=None,
        i_count=0,
    )



def decompose_repetition_with_interruptions(repetitions, segmentation, groups):
    """
    Version haut-niveau : retourne uniquement les résultats finaux TRGT.
    """

    list_repetitions = parse_motif_counts(repetitions)
    list_segmentation = parse_segmentation(segmentation)

    extracted, others = extract_group_motifs(list_repetitions, [], groups)
    if not extracted:
        return None

    motif_lengths = {len(m) for m, _ in extracted}

    # ----------------------------------------------------------------------
    # MODE SIMPLE
    # ----------------------------------------------------------------------
    if len(motif_lengths) == 1:

        motif_len = next(iter(motif_lengths))

        # Sélection correcte du motif principal
        candidates = [(m, c) for m, c in extracted]
        main_motif, _ = max(candidates, key=lambda x: x[1])

        total_main_count_without = sum(c for _, c in extracted)

        # interruptions
        i_bp, i_count = compute_interruption_bp(list_segmentation, groups)
        m_with = compute_m(i_bp, motif_len)

        total_main_count_with = total_main_count_without + m_with

        return TRGTGroupData(
            mode="simple",
            main_motif=main_motif,
            main_len=motif_len,

            total_main_count_without=total_main_count_without,
            total_main_count_with=total_main_count_with,

            short=extracted,
            long=[],
            others=others,

            m_without=0,
            m_with=m_with,
            i_count=i_count,
        )

    # ----------------------------------------------------------------------
    # MODE COMPLEXE
    # ----------------------------------------------------------------------

    # Sélection correcte du motif principal
    min_len = min(len(m) for m, _ in extracted)
    candidates = [(m, c) for m, c in extracted if len(m) == min_len]
    main_motif, _ = max(candidates, key=lambda x: x[1])
    main_len = min_len

    short = []
    long = []

    for motif, count in extracted:
        if len(motif) == main_len:
            short.append((motif, count))
        else:
            long.append((motif, count))

    # Calcul des unités longues
    long_with_units = []
    units_long = 0
    bp_long = 0

    for motif, count in long:
        motif_len = len(motif)
        units = motif_len // main_len
        total_units = units * count

        long_with_units.append((motif, count, total_units))

        units_long += total_units
        bp_long += motif_len * count

    # m_without = motifs longs uniquement
    m_total_without = compute_m(bp_long, main_len)
    m_without = max(0, m_total_without - units_long)

    # interruptions
    i_bp, i_count = compute_interruption_bp(list_segmentation, groups)

    # m_with = motifs longs + interruptions
    m_total_with = compute_m(bp_long + i_bp, main_len)
    m_with = max(0, m_total_with - units_long)

    # total_main_count (motifs courts du motif principal)
    total_main_count = sum(c for m2, c in short if m2 == main_motif)

    total_main_count_without = total_main_count + units_long + m_without
    total_main_count_with = total_main_count + units_long + m_with

    return TRGTGroupData(
        mode="complex",
        main_motif=main_motif,
        main_len=main_len,

        total_main_count_without=total_main_count_without,
        total_main_count_with=total_main_count_with,

        short=short,
        long=long_with_units,
        others=others,

        m_without=m_without,
        m_with=m_with,
        i_count=i_count,
    )
