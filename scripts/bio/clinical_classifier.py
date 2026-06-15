def clinical_group(data_group, clinical_group, repeat_mode, classification_mode, label_priority):
    """
    Classification clinique d'un SEUL groupe.
    Retourne uniquement le label clinique final.
    """

    # 1) repeat_count clinique selon le repeat_mode du groupe
    if repeat_mode == "sum_with_interruptions":
        repeat_count = data_group.total_main_count_with
    else:
        repeat_count = data_group.total_main_count_without

    label = None

    # 2) Mode structural → structure_rules d'abord
    if classification_mode == "structural" and clinical_group.structure_rules:
        has_interruptions = (data_group.i_count > 0)

        for rule in clinical_group.structure_rules:
            cond = rule["conditions"]

            rmin, rmax = cond["repeat_range"]
            interruptions_required = cond.get("interruptions", None)

            # Vérification du repeat_range
            if rmin is not None and repeat_count < rmin:
                continue
            if rmax is not None and repeat_count > rmax:
                continue

            # Vérification interruptions
            if interruptions_required is not None:
                if interruptions_required and not has_interruptions:
                    continue
                if not interruptions_required and has_interruptions:
                    continue

            # Première règle valide
            label = cond["classification"]
            break

    # 3) Fallback thresholds si aucune structure_rule n'a matché
    if label is None:
        for lbl, (min_v, max_v) in clinical_group.thresholds.items():
            if min_v is not None and repeat_count < min_v:
                continue
            if max_v is not None and repeat_count > max_v:
                continue
            label = lbl
            break

    # 4) Si rien ne matche → label de priorité la plus basse
    if label is None:
        label = min(label_priority, key=label_priority.get)

    return label
