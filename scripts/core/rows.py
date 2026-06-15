from scripts.models.row import Row
from scripts.core.marking import mark_pathogenic_motifs, mark_pathogenic_segments, mark_pathogenic_repetition
from scripts.core.sequence_utils import reverse_complement
from scripts.core.clinical_compute import build_genotype_clinical, build_repetition_clinical

def build_row_simple(trid_id, trid, a1, a2, paths, sample_name):

    # Format Locus
    clinical_name, gene = trid_id.split("_", 1)
    locus_display = f"{clinical_name} ({gene})"

    # Position
    position = f"{trid.chrom}:{trid.start}-{trid.end}"

    # Motifs
    motifs_str = ", ".join(trid.motifs)

    row = Row(
        locus=locus_display,
        position=position,
        depth=a1.depth,
        size=f"{a1.size} / {a2.size}",
        motifs=motifs_str,
        genotype="",              # simple mode
        classification="",        # simple mode
        rep1=a1.sequence.repetitions,
        rep2=a2.sequence.repetitions,
        seg1=a1.sequence.segmentation,
        seg2=a2.sequence.segmentation,
    )

    # On stocke dans les allèles
    a1.row = row
    a2.row = row

    return row.to_dict()



def build_row_clinical(trid_id, trid, a1, a2, paths, sample_name, min_label):

    # Format Locus sécurisé
    if "_" in trid_id:
        clinical_name, gene = trid_id.split("_", 1)
        locus_display = f"{clinical_name} ({gene})"
    else:
        locus_display = trid_id

    # Position
    position = f"{trid.chrom}:{trid.start}-{trid.end}"

    clinical_cfg = trid.clinical

    # Motifs TRGT
    motifs = trid.motifs
    if clinical_cfg.orientation.lower() == "rc":
        motifs = [reverse_complement(m) for m in motifs]
    

    # Motifs pathogènes définis dans le YAML
    pathogenic = clinical_cfg.pathogenic_motifs 

    # Marquage
    motifs_str = mark_pathogenic_motifs(motifs, pathogenic, ui=True)
    seg1_str = mark_pathogenic_segments(a1.sequence.segmentation, pathogenic, ui=True)
    seg2_str = mark_pathogenic_segments(a2.sequence.segmentation, pathogenic, ui=True)

    # Paramètres d'affichage
    genotype_display = clinical_cfg.genotype_display
    pure_only = clinical_cfg.pure_only

    # Classification clinique brute
    class1 = a1.clinical.clinical 
    class2 = a2.clinical.clinical
    class_str = f"{class1} / {class2}"

    # Construction du génotype clinique
    genotype1 = build_genotype_clinical(
        clinical=a1.clinical,
        genotype_display=genotype_display,
        pure_only=pure_only,
        min_label=min_label
    )

    genotype2 = build_genotype_clinical(
        clinical=a2.clinical,
        genotype_display=genotype_display,
        pure_only=pure_only,
        min_label=min_label
    )

    rep1_raw = build_repetition_clinical(a1.clinical)
    rep2_raw = build_repetition_clinical(a2.clinical)

    rep1_str = mark_pathogenic_repetition(rep1_raw, pathogenic, ui=True)
    rep2_str = mark_pathogenic_repetition(rep2_raw, pathogenic, ui=True)


    genotype_str = f"{genotype1} / {genotype2}"

    # Construction de la ligne
    row = Row(
        locus=locus_display,
        position=position,
        depth=a1.depth,
        size=f"{a1.size} / {a2.size}",
        motifs=motifs_str,
        genotype=genotype_str,
        classification=class_str,
        rep1=rep1_str,
        rep2=rep2_str,
        seg1=seg1_str,
        seg2=seg2_str,
    )

    a1.row = row
    a2.row = row
    
    return row.to_dict()


def build_genotype_clinical(clinical, genotype_display, pure_only, min_label):

    # Sécurisation : si genotype_display est vide → fallback
    if not genotype_display:
        genotype_display = "pathogenic_only"

    # Nombre de répétitions du winner
    count_without = clinical.total_main_count_without
    count_with = clinical.total_main_count_with if clinical.total_main_count_with is not None else count_without
    count_repeats = count_with

    clinical_is_min = (clinical.clinical == min_label)

    # ============================================================
    # CAS 1 : pure_only (notation enrichie)
    # ============================================================
    # pure_only s'applique TOUJOURS, sauf si full_with_others choisit un best_other
    if pure_only and genotype_display != "full_with_others":
        return f"{count_without} ({count_with})"

    # ============================================================
    # CAS 2 : full_with_others
    # ============================================================
    if genotype_display == "full_with_others":

        # winner faible → comparaison avec others
        if clinical_is_min and clinical.others:
            best_other = max(clinical.others, key=lambda x: x[1])  # (motif, count)
            best_motif, best_count = best_other

            # Si best_other gagne → pure_only NE s'applique PAS
            if best_count > count_repeats:
                return f"{best_count} ({best_motif})"

        # Sinon winner reste le meilleur
        return f"{count_repeats} ({clinical.main_motif})"

    # ============================================================
    # CAS 3 : pathogenic_with_motif
    # ============================================================
    if genotype_display == "pathogenic_with_motif":
        if pure_only:
            return f"{count_without} ({count_with})"
        return f"{count_repeats} ({clinical.main_motif})"

    # ============================================================
    # CAS 4 : pathogenic_only
    # ============================================================
    if genotype_display == "pathogenic_only":
        if pure_only:
            return f"{count_without} ({count_with})"
        return str(count_repeats)

    # ============================================================
    # Fallback final
    # ============================================================
    return str(count_repeats)


def build_repetition_clinical(clinical):

    # Motif principal
    main = clinical.main_motif
    main_count = next((c for m, c in clinical.short if m == main), 0)

    # m = m_with si présent, sinon m_without
    m = clinical.m_with if clinical.m_with not in (None, 0) else clinical.m_without
    i = clinical.i_count

    # Nettoyage
    short = [(motif, count) for motif, count in clinical.short if count > 0]
    long = [(motif, count, units) for motif, count, units in clinical.long if count > 0]
    others = [(motif, count) for motif, count in clinical.others if count > 0]

    # Tri
    short.sort(key=lambda x: (len(x[0]), -x[1]))
    long.sort(key=lambda x: (len(x[0]), -x[1]))
    others.sort(key=lambda x: x[1], reverse=True)

    # CAS 4 : fallback
    if len(short) == 0 and len(long) == 0 and len(others) > 0:
        return "_".join(f"{motif}({count})" for motif, count in others)

    # CAS 1 : un seul motif court
    if len(short) == 1 and len(long) == 0:
        base = f"{main}({main_count}"

        if m > 0:
            base += f" + {m}m"
        if i > 0:
            base += f", {i}i"

        base += ")"

        if others:
            base += "_" + "_".join(f"{motif}({count})" for motif, count in others)

        return base

    # CAS 2 : plusieurs motifs courts
    if len(short) > 1 and len(long) == 0:
        names = "+".join(m for m, _ in short)
        counts = " + ".join(str(c) for _, c in short)

        if m > 0:
            counts += f" + {m}m"
        if i > 0:
            counts += f", {i}i"

        rep = f"{names}({counts})"

        if others:
            rep += "_" + "_".join(f"{motif}({count})" for motif, count in others)

        return rep

    # CAS 3 : motifs courts + motifs longs
    if len(long) > 0:
        base = f"{main}({main_count}"

        for motif_long, count_long, units in long:
            base += f" + {units} ({count_long}{motif_long})"

        if m > 0:
            base += f" + {m}m"
        if i > 0:
            base += f", {i}i"

        base += ")"

        if others:
            base += "_" + "_".join(f"{motif}({count})" for motif, count in others)

        return base

    return ""

