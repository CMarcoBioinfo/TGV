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
        # On renomme m en motif pour éviter le conflit de nom avec la méthylation m
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

