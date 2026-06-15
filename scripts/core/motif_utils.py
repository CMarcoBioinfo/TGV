def extract_group_motifs(repetitions, interruptions, motif_group):
    """
    Sépare et trie les motifs appartenant au motif_group
    de ceux qui n'en font pas partie.
    """

    # Motifs du groupe
    group_reps = [(m, c) for m, c in repetitions if m in motif_group]
    group_inters = [(m, c) for m, c in interruptions if m in motif_group]

    # Motifs hors groupe
    other_reps = [(m, c) for m, c in repetitions if m not in motif_group]
    
    # Fusion + tri décroissant par count
    groups = sorted(group_reps + group_inters, key=lambda x: x[1], reverse=True)
    others = sorted(other_reps, key=lambda x: x[1], reverse=True)

    return groups, others


def compute_interruption_bp(segmentation, motif_group):
    """
    Calcule :
      - i_bp : taille totale des interruptions internes (en bp)
      - i_count : nombre d'interruptions internes
    Une interruption interne est un segment non-groupe situé
    entre le premier et le dernier segment du motif_group.
    """

    # Indices des segments appartenant au motif_group
    group_indices = [
        i for i, (motif, start, end) in enumerate(segmentation)
        if motif in motif_group
    ]
    if not group_indices:
        return 0, 0

    first_idx = group_indices[0]
    last_idx = group_indices[-1]

    interruption_bp = 0
    interruption_count = 0

    # Ne parcourir que la fenêtre interne
    for motif, start, end in segmentation[first_idx:last_idx+1]:
        if motif not in motif_group:
            interruption_bp += (end - start)
            interruption_count += 1

    return interruption_bp, interruption_count


def compute_m(interruption_bp, motif_len):
    """
    Calcule m = nombre de motifs compensés.
    """
    if motif_len <= 0:
        return 0
    return round(interruption_bp / motif_len)
