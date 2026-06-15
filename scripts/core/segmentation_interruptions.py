def find_interruptions(ms):
    """
    Retourne les intervalles des interruptions sous forme [(start, end), ...]
    """
    if not ms:
        return []

    parts = ms.split("_")
    intervals = []

    # Extraction des intervalles de chaque segment
    for p in parts:
        inside = p.split("(")[1].split(")")[0]  # "0-30"
        start, end = inside.split("-")
        intervals.append((int(start), int(end)))

    interruptions = []

    # Comparer chaque intervalle avec le suivant
    for (s1, e1), (s2, e2) in zip(intervals, intervals[1:]):
        if e1 != s2:
            interruptions.append((e1 , s2))

    return interruptions


def extract_interruption_sequences(consensus, interruptions):
    """
    Extrait les séquences d'interruptions à partir de CONS1/CONS2 et des intervalles.
    """
    seqs = []
    for start, end in interruptions:
        seqs.append(consensus[start:end])
    return seqs

def segmentation_complete(segmentation_trgt, interruption_inter, seqs):
    """
    Construit la segmentation complete : segmentation trgt + interruptions
    """
    if not segmentation_trgt:
        return ""

    motifs = segmentation_trgt.split("_")
    result = []

    for m in motifs:
        result.append(m)

        inside = m.split("(")[1].split(")")[0]
        start_str, end_str = inside.split("-")
        end = int(end_str)
        

        for i, (s_int, e_int) in enumerate(interruption_inter):
            if s_int == end :
                result.append(seqs[i])

    return "_".join(result)
