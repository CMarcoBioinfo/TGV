import PySimpleGUI as sg
import os
import shutil
import tempfile
import logging

from scripts.core.config_manager import load_ui_settings, save_ui_settings
from scripts.core.plots import open_svg, get_available_plots
from scripts.ui.results_table import build_results_table
from scripts.ui.results_details import build_details_panel, update_details
from scripts.ui.html_export import generate_html_table, save_and_open_html
from scripts.ui.igv import open_igv, get_available_spanning_bam, get_available_bam


def can_open_igv(r, paths, sample_name, online_status):
    """
    Détermine si IGV peut être ouvert pour le locus sélectionné.
    Affiche des informations de débogage dans la console en cas de problème.
    """
    # 1. Vérification des BAMs (Au moins un BAM requis)
    span = get_available_spanning_bam(paths, sample_name)
    mapped = get_available_bam(paths, sample_name)
    
    logging.debug(f"IGV validation for locus: {r.chrom}:{r.start}-{r.end}")
    logging.debug(f"  - Spanning BAM found: {span is not None}")
    logging.debug(f"  - Mapped BAM found: {mapped is not None}")
    
    if not (span or mapped):
        logging.debug("Button disabled: No BAM alignment file found for this patient.")
        return False

    # 2. Vérification du génome
    fasta = paths.get("genome_fasta")
    has_local_fasta = False
    if fasta and os.path.isfile(fasta):
        if os.path.isfile(fasta + ".fai"):
            has_local_fasta = True
        else:
            logging.debug(f"  - Alert: Missing index file for local FASTA ({fasta}.fai)")
    else:
        logging.debug(f"  - Local FASTA not found at path: {fasta}")

    logging.debug(f"  - Valid local reference genome: {has_local_fasta}")
    logging.debug(f"  - Internet connection active: {online_status}")

    # Autorisé si on a le génome local OU si on est connecté à Internet (fallback hg38)
    decision = has_local_fasta or online_status
    logging.debug(f" Activation decision: {decision}")
    return decision


def build_classification_panel(sorted_labels):
    return sg.Frame("Classification", [
        [sg.Text("Locus :"), sg.Text("", key="-CL_LOCUS-")],
        [sg.Text("Génotype :"), sg.Text("", key="-CL_GENOTYPE-")],
        [sg.Text("Auto :"), sg.Text("", key="-CL_AUTO-")],
        [
            sg.Text("Appliquée :"),
            sg.Combo(sorted_labels, key="-CL_A1-", readonly=True, size=(12, 1)),
            sg.Combo(sorted_labels, key="-CL_A2-", readonly=True, size=(12, 1)),
        ],
        [
            sg.Button("Valider", key="-CL_VALIDATE-"),
            sg.Button("Réinitialiser auto", key="-CL_RESET-")
        ]
    ], relief=sg.RELIEF_SUNKEN, pad=(5, 5))


def build_genotype_panel():
    return sg.Frame("Génotype", [
        [sg.Text("Auto :"), sg.Text("", key="-GT_AUTO-")],
        [
            sg.Text("Appliqué :"),
            sg.Input("", key="-GT_A1-", size=(6,1)),
            sg.Input("", key="-GT_A2-", size=(6,1)),
        ],
        [
            sg.Button("Valider", key="-GT_VALIDATE-"),
            sg.Button("Réinitialiser auto", key="-GT_RESET-")
        ]
    ], relief=sg.RELIEF_SUNKEN, pad=(5,5))


def show_results_window(sample_name, results, label_priority, paths, online_status):
    sorted_labels = sorted(label_priority.keys(), key=lambda k: label_priority[k])
    sorted_labels = ["None"] + sorted_labels

    rows = []
    for r in results:
        dr = r.display_row
        dd = r.display_details

        classif_auto = f"{r.classification1_raw} / {r.classification2_raw}"

        # Si au moins une des deux classifications manuelles est renseignée (non None / non vide)
        if r.classification1_bio or r.classification2_bio:
            c1 = r.classification1_bio if r.classification1_bio else "None"
            c2 = r.classification2_bio if r.classification2_bio else "None"
            classif_display = f"{c1} / {c2}"
        else:
            classif_display = classif_auto

        dd.purity = f"{r.purity1} / {r.purity2}"
        dd.methylation = f"{r.methylation1} / {r.methylation2}"
        dr.classification = classif_display

        gt_auto = f"{r.genotype1_raw} / {r.genotype2_raw}"
        
        if r.genotype1_bio is not None or r.genotype2_bio is not None:
            g1 = r.genotype1_bio if r.genotype1_bio is not None else "None"
            g2 = r.genotype2_bio if r.genotype2_bio is not None else "None"
            gt_display = f"{g1} / {g2}"
        else:
            gt_display = gt_auto
            
        dr.genotype = gt_display
        dd.gt_auto = gt_auto
        dd.genotype = gt_display

        row = {
            "Locus": dr.locus,
            "Profondeur": dr.depth,
            "Taille (bp)": dr.size,
            "Motifs": dr.motifs,
            "Génotype": dr.genotype,
            
            "Classification": classif_display,
            "Allèle 1 - Répétition": dr.rep1,
            "Allèle 2 - Répétition": dr.rep2,
            "Allèle 1 - Segmentation": dr.seg1,
            "Allèle 2 - Segmentation": dr.seg2,

            "Result_obj": r,
            "Details_obj": dd,
            "Classification_auto": classif_auto,
            "Genotype_auto": gt_auto,

        }
        rows.append(row)

    headers = [
        "Locus",
        "Profondeur",
        "Taille (bp)",
        "Motifs",
        "Génotype",
        "Classification",
        "Allèle 1 - Répétition",
        "Allèle 2 - Répétition",
    ]

    col_widths = [10, 10, 12, 12, 14, 12, 18, 18]

    table, table_data = build_results_table(rows, headers, col_widths)
    details_panel = build_details_panel()
    classif_panel = build_classification_panel(sorted_labels)
    genotype_panel = build_genotype_panel()  

    layout = [
        [table],
        [ 
            classif_panel,
            genotype_panel, 
        ], 
        [details_panel],
        [
            sg.Button("Export Data", key="-EXPORT-DATA-"), 
            sg.Button("Fermer"),
        ]
    ]

    # --- 1. Charger la configuration utilisateur AVANT de créer la fenêtre ---
    ui_settings = load_ui_settings()
    results_settings = ui_settings.get("results_window", {})

    saved_w = results_settings.get("width")
    saved_h = results_settings.get("height")
    saved_x = results_settings.get("x")
    saved_y = results_settings.get("y")
    saved_cols = results_settings.get("column_widths")

    # Déterminer la position (coordonnées)
    if saved_x is not None and saved_y is not None:
        win_location = (saved_x, saved_y)
        logging.debug(f"Restored window position from configuration file: {win_location}")
    else:
        win_location = (50, 40)  # 50px de marge à gauche, 40px en haut pour éviter d'être collé
        logging.debug(f"No window position config found. Applying default location: {win_location}")

    # --- 2. Créer la fenêtre en passant directement le paramètre "location" ---
    window = sg.Window(
        f"Résultats pour {sample_name}",
        layout,
        resizable=True,
        finalize=True,
        no_titlebar=False,
        location=win_location
    )

    # --- 3. Bloquer l'action du bouton "X" système (MAINTENANT QUE LA FENÊTRE EXISTE) ---
    try:
        window.TKroot.protocol("WM_DELETE_WINDOW", lambda: None)
    except Exception as e:
        logging.warning(f"Could not disable system window close button: {e}")

    # --- 4. Appliquer la taille de la fenêtre après finalisation ---
    if saved_w and saved_h:
        window.set_size((saved_w, saved_h))
        logging.debug(f"Restored window size applied: {(saved_w, saved_h)}")
    else:
        screen_w, screen_h = sg.Window.get_screen_size()
        # On réduit à screen_w - 100 pour laisser une marge propre de 50px de chaque côté de l'écran
        window.set_size((screen_w - 100, screen_h - 120))
        logging.debug(f"No window size config found. Applying default dimensions: {(screen_w - 100, screen_h - 120)}")

    # --- 5. Appliquer les largeurs des colonnes ---
    if saved_cols:
        try:
            table_widget = window["-TABLE-"].Widget
            cols_keys = table_widget["columns"]
            for col_key, col_w_px in zip(cols_keys, saved_cols):
                table_widget.column(col_key, width=col_w_px)
        except Exception as e:
            logging.warning(f"Error during column widths restoration: {e}")

    # Étape 2 : Sélection automatique de la première ligne au démarrage
    if rows:
        window["-TABLE-"].update(select_rows=[0])
        # Injecte un événement artificiel de sélection de table dans la file d'attente
        window.write_event_value("-TABLE-", [0])

    plot_map = {}

    while True:
        ev, vals = window.read()
        if ev == sg.WINDOW_CLOSED:
            break

        if ev == "Fermer":
            # --- Enregistrement de la configuration utilisateur ---
            try:
                curr_size = window.size
                
                # Extraction ultra-précise des coordonnées Tkinter pour éviter la dérive
                import re
                geom = window.TKroot.geometry() # Retourne une chaîne du type "1200x800+100+150"
                logging.debug(f"Raw Tkinter window geometry detected at closing: {geom}")
                
                match = re.search(r'([+-]?\d+)([+-]\d+)$', geom)
                if match:
                    curr_x = int(match.group(1))
                    curr_y = int(match.group(2))
                    logging.debug(f"Coordinates matched via Regex: x={curr_x}, y={curr_y}")
                else:
                    curr_x, curr_y = window.current_location() # Fallback au cas où
                    logging.debug(f"Regex match failed. Falling back to current_location coordinates: x={curr_x}, y={curr_y}")
                
                table_widget = window["-TABLE-"].Widget
                col_widths_px = []
                for col_key in table_widget["columns"]:
                    col_widths_px.append(table_widget.column(col_key, "width"))
                
                ui_settings = load_ui_settings()
                ui_settings["results_window"] = {
                    "width": curr_size[0],
                    "height": curr_size[1],
                    "x": curr_x,
                    "y": curr_y,
                    "column_widths": col_widths_px
                }
                save_ui_settings(ui_settings)
                logging.debug("Successfully saved window size and position settings.")
            except Exception as e:
                logging.warning(f"Error saving UI geometry settings: {e}")

            # -----------------------------------------------------
            # Cleanup des SVG temporaires
            tmp_dir = os.path.join(tempfile.gettempdir(), ".tmp_plots", sample_name)
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

            window.close()
            return

        # -----------------------------
        # Sélection d'une ligne
        # -----------------------------
        if ev == "-TABLE-":
            # Gère aussi bien l'événement utilisateur que l'événement programmé de démarrage
            if isinstance(vals, dict) and "-TABLE-" in vals:
                selected_indices = vals["-TABLE-"]
            else:
                selected_indices = []

            if not selected_indices:
                continue

            idx = selected_indices[0]
            row = rows[idx]
            r = row["Result_obj"]
            dd = row["Details_obj"]

            window["-CL_LOCUS-"].update(row["Locus"])
            window["-CL_GENOTYPE-"].update(row["Génotype"])

            auto = row["Classification_auto"]
            applied = row["Classification"]

            window["-CL_AUTO-"].update(auto)

            if applied:
                parts = [x.strip() for x in applied.split("/")]
                if len(parts) == 2:
                    a1, a2 = parts
                else:
                    a1, a2 = applied, ""
            else:
                a1, a2 = "", ""

            window["-CL_A1-"].update(a1)
            window["-CL_A2-"].update(a2)

            window["-CL_A1-"].update(disabled=False)
            window["-CL_A2-"].update(disabled=False)
            window["-CL_VALIDATE-"].update(disabled=False)
            window["-CL_RESET-"].update(disabled=False)

            dd.classification_auto = row["Classification_auto"]
            dd.classification = row["Classification"]

            # Extraction des plots disponibles
            plot_entries = []
            plot_map.clear()

            if paths.get("motifs_allele"):
                for inner_zip, svg_file in get_available_plots(paths["motifs_allele"], sample_name, r.trid):
                    plot_entries.append("Motifs allele")
                    plot_map["Motifs allele"] = (inner_zip, svg_file)

            if paths.get("motifs_waterfall"):
                for inner_zip, svg_file in get_available_plots(paths["motifs_waterfall"], sample_name, r.trid):
                    plot_entries.append("Motifs waterfall")
                    plot_map["Motifs waterfall"] = (inner_zip, svg_file)

            if paths.get("meth_allele"):
                for inner_zip, svg_file in get_available_plots(paths["meth_allele"], sample_name, r.trid):
                    plot_entries.append("Meth allele")
                    plot_map["Meth allele"] = (inner_zip, svg_file)

            if paths.get("meth_waterfall"):
                for inner_zip, svg_file in get_available_plots(paths["meth_waterfall"], sample_name, r.trid):
                    plot_entries.append("Meth waterfall")
                    plot_map["Meth waterfall"] = (inner_zip, svg_file)

            window["-PLOT-LIST-"].update(values=plot_entries)
            window["-PLOT-OPEN-"].update(disabled=not bool(plot_entries))

            update_details(window, dd)

            gt_auto = row["Genotype_auto"]
            gt_applied = row["Génotype"]
            window["-GT_AUTO-"].update(gt_auto)

            g1, g2 = [x.strip() for x in gt_applied.split("/")] if gt_applied else ("", "")

            window["-GT_A1-"].update("" if g1 == "None" else g1)
            window["-GT_A2-"].update("" if g2 == "None" else g2)

            # Active les champs et les boutons du génotype
            window["-GT_A1-"].update(disabled=False)
            window["-GT_A2-"].update(disabled=False)
            window["-GT_VALIDATE-"].update(disabled=False)
            window["-GT_RESET-"].update(disabled=False)

            # Évaluation avec cache de statut Internet (très rapide)
            if can_open_igv(r, paths, sample_name, online_status):
                window["-IGV-"].update(disabled=False)
            else:
                window["-IGV-"].update(disabled=True)
        

        if ev == "-PLOT-OPEN-":
            label = vals["-PLOT-LIST-"]
            if not label:
                continue

            inner_zip, svg_file = plot_map[label]

            if label == "Motifs allele":
                zip_path = paths["motifs_allele"]
            elif label == "Motifs waterfall":
                zip_path = paths["motifs_waterfall"]
            elif label == "Meth allele":
                zip_path = paths["meth_allele"]
            elif label == "Meth waterfall":
                zip_path = paths["meth_waterfall"]
            else:
                zip_path = None

            if zip_path:
                open_svg(zip_path, inner_zip, svg_file, sample_name)

        if ev == "-CL_VALIDATE-":
            if not vals["-TABLE-"]:
                continue

            idx = vals["-TABLE-"][0]
            row = rows[idx]
            r = row["Result_obj"]

            new_a1 = vals["-CL_A1-"]
            new_a2 = vals["-CL_A2-"]

            r.classification1_bio = new_a1
            r.classification2_bio = new_a2

            new_final = f"{new_a1} / {new_a2}"
            logging.info(f"Audit Trail: Manual classification override for locus '{r.trid}' set to: {new_final}")

            r.display_row.classification = new_final
            row["Classification"] = new_final

            table_data[idx][5] = new_final
            window["-TABLE-"].update(values=table_data, select_rows=[idx])

            window["-CL_AUTO-"].update(row["Classification_auto"])
            window["-CL_A1-"].update(new_a1)
            window["-CL_A2-"].update(new_a2)

            dd = row["Details_obj"]
            dd.classification = new_final
            update_details(window, dd)

        if ev == "-CL_RESET-":
            if not vals["-TABLE-"]:
                continue

            idx = vals["-TABLE-"][0]
            row = rows[idx]
            r = row["Result_obj"]

            auto = row["Classification_auto"]
            a1, a2 = [x.strip() for x in auto.split("/")]

            r.classification1_bio = None
            r.classification2_bio = None

            row["Classification"] = auto
            logging.info(f"Audit Trail: Reset classification for locus '{r.trid}' to auto-detected default: {auto}")
            r.display_row.classification = auto

            table_data[idx][5] = auto
            window["-TABLE-"].update(values=table_data, select_rows=[idx])

            window["-CL_A1-"].update(a1)
            window["-CL_A2-"].update(a2)

            dd = row["Details_obj"]
            dd.classification = auto
            update_details(window, dd)

        if ev == "-SEQ1-":
            if not vals.get("-TABLE-"):
                continue
            idx = vals["-TABLE-"][0]
            dd = rows[idx]["Details_obj"]
            if dd.sequence1:
                layout = [
                    [sg.Multiline(dd.sequence1, size=(80, 25), key="-SEQPOP-", disabled=True)],
                    [sg.Button("Copier", key="-COPYSEQ1-"), sg.Button("Fermer")]
                ]
                win = sg.Window("Séquence allèle 1", layout, modal=True)
                while True:
                    ev2, _ = win.read()
                    if ev2 in (sg.WINDOW_CLOSED, "Fermer"):
                        break
                    if ev2 == "-COPYSEQ1-":
                        sg.clipboard_set(dd.sequence1)
                win.close()

        if ev == "-SEQ2-":
            if not vals.get("-TABLE-"):
                continue
            idx = vals["-TABLE-"][0]
            dd = rows[idx]["Details_obj"]
            if dd.sequence2:
                layout = [
                    [sg.Multiline(dd.sequence2, size=(80, 25), key="-SEQPOP-", disabled=True)],
                    [sg.Button("Copier", key="-COPYSEQ2-"), sg.Button("Fermer")]
                ]
                win = sg.Window("Séquence allèle 2", layout, modal=True)
                while True:
                    ev2, _ = win.read()
                    if ev2 in (sg.WINDOW_CLOSED, "Fermer"):
                        break
                    if ev2 == "-COPYSEQ2-":
                        sg.clipboard_set(dd.sequence2)
                win.close()

        if ev == "-EXPORT-DATA-":
            rows_export = []
            for r in rows:
                classif = r["Classification"]
                if not classif:
                    continue
                parts = [x.strip() for x in classif.split("/")]
                if len(parts) != 2:
                    continue
                a1, a2 = parts
                if a1 != "None" or a2 != "None":
                    rows_export.append(r)

            if not rows_export:
                sg.popup("Aucune ligne avec classification définie à exporter.")
                continue

            html = generate_html_table(
                ["Locus", "Profondeur", "Génotype", "Classification"],
                rows_export,
                sample_name
            )
            save_and_open_html(html)

        if ev == "-GT_VALIDATE-":
            if not vals["-TABLE-"]:
                continue

            idx = vals["-TABLE-"][0]
            row = rows[idx]
            r = row["Result_obj"]

            g1_val = vals["-GT_A1-"].strip()
            g2_val = vals["-GT_A2-"].strip()

            # Valeurs brutes automatiques d'origine pour comparaison
            raw1_str = str(r.genotype1_raw) if r.genotype1_raw is not None else ""
            raw2_str = str(r.genotype2_raw) if r.genotype2_raw is not None else ""

            # Validation de l'allèle 1 :
            # Valide si vide, "none", entier numérique, OU identique à sa valeur automatique d'origine
            g1_is_valid = (
                g1_val == "" or 
                g1_val.lower() == "none" or 
                g1_val.isdigit() or 
                g1_val == raw1_str
            )
            if not g1_is_valid:
                sg.popup("Le génotype 1 doit être un entier, vide, ou identique à sa valeur automatique.", keep_on_top=True)
                continue

            # Validation de l'allèle 2
            g2_is_valid = (
                g2_val == "" or 
                g2_val.lower() == "none" or 
                g2_val.isdigit() or 
                g2_val == raw2_str
            )
            if not g2_is_valid:
                sg.popup("Le génotype 2 doit être un entier, vide, ou identique à sa valeur automatique.", keep_on_top=True)
                continue

            # Conversion intelligente des valeurs biologiques :
            # - S'il est numérique, on convertit en int
            # - Si vide ou "none", on met à None (fallback ou vide)
            # - Sinon (ex: "10 (AGGGG)"), on conserve la chaîne de caractères
            if g1_val.isdigit():
                g1_bio = int(g1_val)
            elif g1_val == "" or g1_val.lower() == "none":
                g1_bio = None
            else:
                g1_bio = g1_val

            if g2_val.isdigit():
                g2_bio = int(g2_val)
            elif g2_val == "" or g2_val.lower() == "none":
                g2_bio = None
            else:
                g2_bio = g2_val

            r.genotype1_bio = g1_bio
            r.genotype2_bio = g2_bio
            logging.info(f"Audit Trail: Manual genotype override for locus '{r.trid}' set to: {g1_val} / {g2_val} (Auto-detected was: {raw1_str} / {raw2_str})")

            # Formatage pour l'affichage final
            display_g1 = str(g1_bio) if g1_bio is not None else "None"
            display_g2 = str(g2_bio) if g2_bio is not None else "None"
            new_gt = f"{display_g1} / {display_g2}"

            r.display_row.genotype = new_gt
            row["Génotype"] = new_gt

            table_data[idx][4] = new_gt
            window["-TABLE-"].update(values=table_data, select_rows=[idx])

            # Mise à jour des cases de saisie à l'écran
            window["-GT_A1-"].update("" if display_g1 == "None" else display_g1)
            window["-GT_A2-"].update("" if display_g2 == "None" else display_g2)

            dd = row["Details_obj"]
            dd.genotype1 = g1_bio
            dd.genotype2 = g2_bio
            dd.gt_auto = row["Genotype_auto"]
            dd.genotype = new_gt
            update_details(window, dd)

        if ev == "-GT_RESET-":
            if not vals["-TABLE-"]:
                continue

            idx = vals["-TABLE-"][0]
            row = rows[idx]
            r = row["Result_obj"]

            r.genotype1_bio = None
            r.genotype2_bio = None

            auto_gt = row["Genotype_auto"]
            row["Génotype"] = auto_gt
            r.display_row.genotype = auto_gt

            table_data[idx][4] = auto_gt
            window["-TABLE-"].update(values=table_data, select_rows=[idx])

            g1, g2 = [x.strip() for x in auto_gt.split("/")] if auto_gt else ("", "")
            window["-GT_A1-"].update("" if g1 == "None" else g1)
            window["-GT_A2-"].update("" if g2 == "None" else g2)

            dd = row["Details_obj"]
            dd.genotype1 = r.genotype1_raw
            dd.genotype2 = r.genotype2_raw
            dd.gt_auto = row["Genotype_auto"]
            dd.genotype = auto_gt
            update_details(window, dd)

        if ev == "-IGV-":
            if not vals.get("-TABLE-"):
                continue
            idx = vals["-TABLE-"][0]
            row = rows[idx]
            r = row["Result_obj"]

            span = get_available_spanning_bam(paths, sample_name)
            if span:
                spanning_zip_path, spanning_bam_file, spanning_bai_file = span
            else:
                spanning_zip_path = spanning_bam_file = spanning_bai_file = None

            mapped = get_available_bam(paths, sample_name)
            if mapped:
                mapped_zip_path, mapped_bam_file, mapped_bai_file = mapped
            else:
                mapped_zip_path = mapped_bam_file = mapped_bai_file = None

            open_igv(
                genome_fasta_path = paths.get("genome_fasta"),

                spanning_zip_path = spanning_zip_path,
                spanning_bam_file = spanning_bam_file,
                spanning_bai_file = spanning_bai_file,

                mapped_zip_path   = mapped_zip_path,
                mapped_bam_file   = mapped_bam_file,
                mapped_bai_file   = mapped_bai_file,

                chrom = r.chrom,
                start = r.start,
                end   = r.end,
                
                sample_name = sample_name,
                row = row 
            )