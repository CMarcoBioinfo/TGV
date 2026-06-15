def reverse_complement(seq):
    """
    Reverse-complement d'une séquence TRGT.
    """
    if not seq:
        return ""
    seq = seq.upper()
    complement = {
        "A": "T",
        "T": "A",
        "C": "G",
        "G": "C",
        "N": "N"
    }
    return "".join(complement.get(base, "N") for base in reversed(seq))


def rc_segmentation(seq, motifs_str):
    """
    Recalcule complètement la segmentation MS sur la séquence RC.
    Les index TRGT sont conservés car l'ordre des motifs ne change pas.
    """
    if not seq or not motifs_str:
        return ""

    motifs = motifs_str.split(",")

    # Tri par longueur décroissante pour matcher correctement
    motifs_sorted = sorted(
        [(m, motifs.index(m)) for m in motifs],
        key=lambda x: len(x[0]),
        reverse=True
    )

    ms = []
    i = 0
    n = len(seq)

    while i < n:
        matched = False

        for motif, trgt_idx in motifs_sorted:
            m = len(motif)

            if seq.startswith(motif, i):
                start = i
                i += m

                # Regroupe les répétitions consécutives du même motif
                while i < n and seq.startswith(motif, i):
                    i += m

                end = i
                ms.append((trgt_idx, start, end))
                matched = True
                break

        if not matched:
            i += 1

    if not ms:
        return ""

    return "_".join(f"{idx}({start}-{end})" for idx, start, end in ms)


def convert_mc(motifs, mc):
    """
    Convertit MC brut en MC lisible.
    MC NE CHANGE PAS en RC.
    """
    if not mc:
        return ""

    parts = mc.split("_")
    return "_".join(f"{motifs[i]}({count})" for i, count in enumerate(parts))


def convert_ms(motifs, ms):
    """
    Convertit MS brut en MS lisible.
    """
    if not ms:
        return ""

    blocks = ms.split("_")
    out = []

    for block in blocks:
        idx, coords = block.split("(")
        motif = motifs[int(idx)]
        coords = coords[:-1]  # remove ')'
        out.append(f"{motif}({coords})")

    return "_".join(out)


def parse_motif_counts(m: str):
    """
    Transforme 'CAG(2)_CAA(3)' en [('CAG', 2), ('CAA', 3)].
    """
    if not m:
        return []

    result = []
    parts = m.split("_")

    for part in parts:
        i = part.index("(")
        motif = part[:i]
        count = int(part[i+1:-1])  # enlève "(" et ")"
        result.append((motif, count))

    return result


def parse_segmentation(seg: str):
    """
    Transforme 'CAG(2-5)_T_CAG(6-9)_CAT' en liste (motif, start, end).
    """
    parts = seg.split("_")
    segments = []
    current_pos = None

    for part in parts:
        if "(" in part:
            motif, coords = part.split("(")
            coords = coords[:-1]  # enlever ")"
            start, end = map(int, coords.split("-"))
            segments.append((motif, start, end))
            current_pos = end
        else:
            motif = part
            motif_len = len(motif)
            start = current_pos
            end = current_pos + motif_len
            segments.append((motif, start, end))
            current_pos = end

    return segments


def format_interruptions(inter_list):
    """
    Transforme une liste d'interruptions ['TATAA', 'TAA', 'TATAA']
    en un string 'TATAA(2)_TAA(1)' trié par count décroissant.
    """
    if not inter_list:
        return ""

    # Compter les occurrences
    counts = {}
    for motif in inter_list:
        counts[motif] = counts.get(motif, 0) + 1

    # Trier par count décroissant
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    # Construire le string final
    parts = [f"{motif}({count})" for motif, count in sorted_items]

    return "_".join(parts)


def clean_and_sort_rep_string(rep_str):
    """
    Nettoie un string TRGT de répétitions :
    - enlève les motifs avec count = 0
    - trie par count décroissant
    - reconstruit un string 'motif(count)_motif(count)'
    """
    if not rep_str:
        return ""

    parts = rep_str.split("_")
    cleaned = []

    for p in parts:
        if "(" not in p or ")" not in p:
            continue

        motif = p.split("(")[0]
        count_str = p.split("(")[1].split(")")[0]

        # sécurité : ignorer les trucs non numériques
        try:
            count = int(count_str)
        except ValueError:
            continue

        if count > 0:
            cleaned.append((motif, count))

    # tri décroissant
    cleaned.sort(key=lambda x: x[1], reverse=True)

    # reconstruction
    return "_".join(f"{motif}({count})" for motif, count in cleaned)
