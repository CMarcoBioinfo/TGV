import re

PATHO_UI = "\u25CF"      # ● noir (compatible Table)
PATHO_HTML = "\U0001F534"  # 🔴 rouge (emoji)

def mark_pathogenic_motifs(motifs, pathogenic, ui=False):
    pathogenic = set(pathogenic or [])
    mark = PATHO_UI if ui else PATHO_HTML

    pathogenic_list = []
    normal_list = []

    for m in motifs:
        if m in pathogenic:
            pathogenic_list.append(f"{mark}{m}")
        else:
            normal_list.append(m)

    return ", ".join(pathogenic_list + normal_list)


def mark_pathogenic_genotype(genotype_str, pathogenic_motifs, ui=False):
    if not genotype_str:
        return genotype_str

    mark = PATHO_UI if ui else PATHO_HTML
    pathogenic = sorted(pathogenic_motifs or [], key=len, reverse=True)

    # On marque uniquement les motifs, pas les chiffres
    for motif in pathogenic:
        genotype_str = genotype_str.replace(motif, f"{mark}{motif}")

    return genotype_str


def mark_pathogenic_segments(seg_str, pathogenic_motifs, ui=False):
    if not seg_str:
        return seg_str

    mark = PATHO_UI if ui else PATHO_HTML
    pathogenic = set(pathogenic_motifs or [])

    parts = seg_str.split("_")
    marked_parts = []

    for part in parts:
        motif = part.split("(", 1)[0] if "(" in part else part
        if motif in pathogenic:
            marked_parts.append(f"{mark}{part}")
        else:
            marked_parts.append(part)

    return "_".join(marked_parts)


def mark_pathogenic_repetition(rep_str, pathogenic_motifs, ui=False):
    if not rep_str:
        return rep_str

    mark = PATHO_UI if ui else PATHO_HTML
    pathogenic = sorted(pathogenic_motifs or [], key=len, reverse=True)

    def mark_motif(motif):
        pattern = rf"(?<![A-Z]){motif}(?=[(_,+)]|$)"
        return re.sub(pattern, f"{mark}{motif}", rep_str)

    for motif in pathogenic:
        rep_str = mark_motif(motif)

    return rep_str
