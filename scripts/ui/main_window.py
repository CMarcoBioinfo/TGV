import PySimpleGUI as sg
import os
import yaml
import re

from scripts.models.run import Run
from scripts.models.trid import TRID
from scripts.models.dto import AnalysisInput

from scripts.core.vcf_loader import list_vcfs
from scripts.core.vcf_parser import parse_vcf_for_sample
from scripts.core.utils import get_analysis_prefix
from scripts.core.sequence_utils import reverse_complement
from scripts.core.trid_detector import autodetect_trids
from scripts.core.config_manager import get_safe_config_path
from scripts.core.orchestrator import process_clinical, process_result, process_display

from scripts.bio.clinical_thresholds_loader import load_clinical_thresholds
from scripts.bio.clinical_config_builder import build_clinical_config

from scripts.ui.results_window import show_results_window
from scripts.ui.igv import is_online
from scripts.ui.make_report import open_report_on_the_fly

# ---------------------------------------------------------
# Chargement robuste du fichier buttons_panel.yaml
# ---------------------------------------------------------
def load_button_panels():
    # Appel de la fonction de chemin sécurisée
    path = get_safe_config_path("buttons_panel.yaml")

    if not os.path.exists(path):
        print("[INFO] Aucun fichier buttons_panel.yaml trouvé → aucun panel chargé.")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[WARN] Erreur lors du chargement de buttons_panel.yaml : {e}")
        return {}


# ---------------------------------------------------------
# Flow layout automatique
# ---------------------------------------------------------
def build_panel_rows(panel_names, window_width=600, button_padding=40):
    rows, row, current_width = [], [], 0

    for name in panel_names:
        estimated_width = len(name) * 8 + button_padding
        if current_width + estimated_width > window_width:
            rows.append(row)
            row, current_width = [], 0
        row.append(sg.Button(name, key=f"-PANEL-{name}-"))
        current_width += estimated_width

    if row:
        rows.append(row)

    return rows


# ---------------------------------------------------------
# Mise à jour TRIDs sélectionnés
# ---------------------------------------------------------
def update_trid_selected(window):
    selected = window.metadata.get("selected_trids", [])
    readable_map = window.metadata.get("readable_to_trid", {})
    trid_to_readable = {v: k for k, v in readable_map.items()}
    readable_list = [trid_to_readable[t] for t in selected]
    window["-TRID-SELECTED-"].update(values=readable_list)


# ---------------------------------------------------------
# Récupère les TRIDs ayant un bloc clinique
# ---------------------------------------------------------
def get_trids_with_clinical(window):
    run = window.metadata.get("run")
    if not run:
        return set()
    return {
        trid_id
        for trid_id, trid in run.trids.items()
        if getattr(trid, "clinical", None) is not None
    }


# ---------------------------------------------------------
# FENÊTRE PRINCIPALE
# ---------------------------------------------------------
def run_main_window():
    print("[INFO] Ouverture de la fenêtre principale")

    sg.theme("SystemDefault")
    # Ligne de titre stylisée à insérer au début de votre layout
    title_row = [
        # T - RGT
        sg.Push(),
        sg.Text("T", font=("Helvetica", 24, "bold"), text_color="#c8336a", pad=(0, 0)),
        sg.Text("RGT", font=("Helvetica", 14, "bold"), text_color="#5a4050", pad=((0, 15), 0)),
        
        # G - lobal
        sg.Text("G", font=("Helvetica", 24, "bold"), text_color="#c8336a", pad=(0, 0)),
        sg.Text("lobal", font=("Helvetica", 14, "bold"), text_color="#5a4050", pad=((0, 15), 0)),
        
        # V - iewer
        sg.Text("V", font=("Helvetica", 24, "bold"), text_color="#c8336a", pad=(0, 0)),
        sg.Text("iewer", font=("Helvetica", 14, "bold"), text_color="#5a4050", pad=(0, 0)),
        sg.Push(),
]

    layout = [
        title_row,
        [sg.Text("Sélection du fichier TRGT (trgt_vcfs.zip)")],
        [sg.Input(key="-ZIP-", enable_events=True), sg.FileBrowse("Parcourir")],
        [sg.Button("Rapport QC", key="-QC-REPORT-", disabled=True)],

        [sg.Text("Sélection du génome de référence (.fa / .fasta) [Optionnel]")],
        [sg.Input(key="-FASTA-", enable_events=True), sg.FileBrowse("Parcourir")],
        
        [sg.Text("Patient à analyser")],
        [sg.Input(key="-SEARCH-", enable_events=True, size=(40, 1))],
        [sg.Combo([], key="-SAMPLE-", size=(40, 1), readonly=True, enable_events=True)],

        [sg.Text("Recherche locus")],
        [sg.Input(key="-SEARCH-TRID-", enable_events=True, size=(40, 1))],
        [
            sg.Combo([], key="-TRID-COMBO-", size=(40, 1), readonly=True),
            sg.Button("Ajouter", key="-ADD-TRID-"),
        ],

        [sg.Frame(
            "Locus sélectionnés",
            [
                [sg.Listbox([], key="-TRID-SELECTED-", size=(40, 6),
                            select_mode=sg.SELECT_MODE_EXTENDED)],
                [sg.Button("Retirer", key="-DEL-TRID-", size=(12, 1))],
            ],
        )],

        [sg.Frame(
            "Actions sur les locus",
            [
                [sg.Button("Tout cocher", key="-SELECT-ALL-", size=(15, 1)),
                 sg.Button("Tout décocher", key="-UNSELECT-ALL-", size=(15, 1))]
            ],
        )],
    ]

    # Panels YAML
    panels = load_button_panels()
    if panels:
        panel_rows = build_panel_rows(list(panels.keys()))
        layout.append([sg.Frame("Panels", panel_rows)])

    layout.extend([
        [sg.Button("Lancer l'analyse")],
        [sg.Text("", key="-STATUS-", text_color="blue")],
        [sg.Text("by Corentin Marco", justification="right",
                 font=("Helvetica", 8), text_color="gray")],
    ])

    # Modification du titre officiel de la fenêtre
    window = sg.Window("TGV - TRGT Global Viewer", layout)

    window.metadata = {
        "all_samples": [],
        "all_trids": [],
        "readable_to_trid": {},
        "selected_trids": [],
        "button_panels": panels
    }

    # ---------------------------------------------------------
    # BOUCLE D'ÉVÉNEMENTS
    # ---------------------------------------------------------
    # Étape 1 : Tester la connexion une seule fois au démarrage de la fenêtre
    print("[IGV] Vérification de la connexion Internet...")
    online_status = is_online()
    print(f"[IGV] Statut Internet : {'En ligne' if online_status else 'Hors-ligne'}")

    fasta_path = None
    while True:
        event, values = window.read()
        if event == sg.WINDOW_CLOSED:
            break

        if event == "-FASTA-":
            fasta_path = values["-FASTA-"]
            if not fasta_path:
                continue

            # Vérifier extension
            fasta_path_lower = fasta_path.lower()
            if not (fasta_path_lower.endswith(".fasta") or fasta_path_lower.endswith(".fa")):
                sg.popup_error("Le fichier doit être au format .fasta ou .fa")
                continue

            # Vérifier existence du fichier FASTA
            if not os.path.isfile(fasta_path):
                sg.popup_error("Le fichier FASTA n'existe pas.")
                continue

            # Vérifier existence du fichier .fai
            fai_path = fasta_path + ".fai"
            if not os.path.isfile(fai_path):
                sg.popup_error(
                    f"Le fichier d'index FASTA (.fai) est manquant :\n{fai_path}\n\n"
                    "Génère-le avec :\n\nsamtools faidx fichier.fasta"
                )
                continue

        # ---------------------------------------------------------
        # Chargement ZIP
        # ---------------------------------------------------------
        if event == "-ZIP-":
            zip_path = values["-ZIP-"]
            if not zip_path:
                continue

            vcfs = list_vcfs(zip_path)
            if not vcfs:
                sg.popup_error("Ce ZIP ne contient aucun fichier .trgt.vcf.")
                continue

            run_name = get_analysis_prefix(zip_path)
            run = Run(name=run_name, vcf_zip=zip_path)

            # ---------------------------------------------------------
            # Détection ZIP associés
            # ---------------------------------------------------------

            zip_filename = os.path.basename(zip_path)

            # On retire uniquement le suffixe final
            # → "analysis-S18-30.04.2026-"
            prefix = re.sub(r"(?i)trgt_vcfs\.zip", "", zip_filename)

            # Répertoire contenant les fichiers
            base_dir = os.path.dirname(zip_path)

            # Construction explicite des chemins
            run.spanning_bam_zip      = os.path.join(base_dir, prefix + "spanning_BAM.zip")
            run.repeat_reads_zip      = os.path.join(base_dir, prefix + "repeat_reads.zip")
            run.motifs_allele_zip     = os.path.join(base_dir, prefix + "trgt_motifs_allele.zip")
            run.motifs_waterfall_zip  = os.path.join(base_dir, prefix + "trgt_motifs_waterfall.zip")
            run.meth_allele_zip       = os.path.join(base_dir, prefix + "trgt_meth_allele.zip")
            run.meth_waterfall_zip    = os.path.join(base_dir, prefix + "trgt_meth_waterfall.zip")
            run.qc_zip                = os.path.join(base_dir, prefix + "QC.zip")

            # Vérification d'existence
            if not os.path.exists(run.spanning_bam_zip):
                run.spanning_bam_zip = None

            # Vérification d'existence
            if not os.path.exists(run.repeat_reads_zip):
                run.repeat_reads_zip = None

            if not os.path.exists(run.motifs_allele_zip):
                run.motifs_allele_zip = None

            if not os.path.exists(run.motifs_waterfall_zip):
                run.motifs_waterfall_zip = None

            if not os.path.exists(run.meth_allele_zip):
                run.meth_allele_zip = None

            if not os.path.exists(run.meth_waterfall_zip):
                run.meth_waterfall_zip = None

            if run.qc_zip and os.path.exists(run.qc_zip):
                window["-QC-REPORT-"].update(disabled=False)
            else:
                run.qc_zip = None
                window["-QC-REPORT-"].update(disabled=True)

            # Construire la liste des noms de fichiers VCF
            display = [os.path.basename(v) for v in vcfs]

            # Mettre à jour la combo avec une LISTE
            window["-SAMPLE-"].update(values=display)

            # Stocker la liste complète
            window.metadata["all_samples"] = display

            # Détection TRIDs globaux
            trids, trid_to_gene, diseases, static_info = autodetect_trids(zip_path)

            thresholds_data = load_clinical_thresholds()
            label_priority = thresholds_data.get("label_priority", {})

            if not label_priority:
                sg.popup_error(
                    "Configuration clinique incomplète",
                    "La section 'label_priority' doit être définie dans clinical_thresholds.yaml."
                )
                return

            print("\n================= INIT TRID GLOBAL =================")

            # ---------------------------------------------------------
            # Création des TRIDs globaux + remplissage infos immuables + clinique
            # ---------------------------------------------------------
            for trid_id in trids:
                t = TRID(trid_id)

                # --- Infos TRGT immuables ---
                if trid_id in static_info:
                    info = static_info[trid_id]
                    t.chrom = info["chrom"]
                    t.start = info["start"]
                    t.end = info["end"]
                    t.motifs = info["motifs"]

                # --- Bloc YAML du TRID (sous-bloc) ---
                trid_yaml_block = thresholds_data.get(trid_id)
                print("YAML BLOCK FOR", trid_id, "=", trid_yaml_block)

                if trid_yaml_block:
                    t.clinical = build_clinical_config(trid_id, thresholds_data)

                    # --- Orientation RC : reverse-complement des motifs TRGT ---
                    if t.clinical.orientation.lower() == "rc":
                        t.motifs_rc = [reverse_complement(m) for m in t.motifs]

                run.trids[trid_id] = t

                # --- DEBUG ---
                print(f"\nTRID : {trid_id}")
                print(f"  chrom  = {t.chrom}")
                print(f"  start  = {t.start}")
                print(f"  end    = {t.end}")
                print(f"  motifs = {t.motifs}")
                if t.clinical:
                    print(f"  clinical.mode        = {t.clinical.classification_mode}")
                    print(f"  clinical.orientation = {t.clinical.orientation}")
                    print(f"  groups               = {list(t.clinical.groups.keys())}")
                else:
                    print("  clinical = None")


            print("\n================= END INIT TRID GLOBAL =================\n")

            # ---------------------------------------------------------
            # Stockage global
            # ---------------------------------------------------------
            window.metadata["run"] = run
            window.metadata["all_trids"] = trids
            window.metadata["readable_to_trid"] = diseases
            window.metadata["label_priority"] = label_priority

            window["-TRID-COMBO-"].update(values=sorted(diseases.keys()))

        # --------------------------------------------------------- 
        # Événement : Ouvrir le Rapport QC
        # ---------------------------------------------------------
        if event == "-QC-REPORT-":
            run = window.metadata.get("run")
            if run and run.qc_zip:
                open_report_on_the_fly(run.qc_zip)

        # ---------------------------------------------------------
        # Recherche patient
        # ---------------------------------------------------------
        
        if event == "-SEARCH-":
            query = values["-SEARCH-"].lower()
            all_samples = window.metadata.get("all_samples", [])

            # Filtrage
            filtered = [s for s in all_samples if query in s.lower()] if query else all_samples
            window["-SAMPLE-"].update(values=filtered)

            # Auto‑sélection si un seul résultat
            if len(filtered) == 1:
                sample = filtered[0]

                # Sélectionner SANS écraser la liste
                window["-SAMPLE-"].update(value=sample)

                # Déclencher le parsing
                window.write_event_value("-SAMPLE-", sample)

                # Effacer la recherche
                window["-SEARCH-"].update("")

                # Rétablir la liste complète
                window["-SAMPLE-"].update(values=all_samples, value=sample)


        # ---------------------------------------------------------
        # Sélection patient
        # ---------------------------------------------------------
        if event == "-SAMPLE-":
            sample_name = values.get("-SAMPLE-")
            if not sample_name:
                print("[WARN] Aucun sample sélectionné")
                continue

            run = window.metadata["run"]

            # Parser le VCF → retourne { trid_id : Sample }
            sample_trids = parse_vcf_for_sample(
                zip_path=run.vcf_zip,
                vcf_filename=sample_name,
                global_trids=run.trids,
            )

            # Attacher chaque Sample au TRID correspondant
            for trid_id, sample_obj in sample_trids.items():
                if trid_id in run.trids:
                    run.trids[trid_id].samples[sample_name] = sample_obj

            # Stockage UI
            window.metadata["current_trids"] = sample_trids

            # Mise à jour TRID lisibles
            readable_map = window.metadata["readable_to_trid"]
            readable_list = sorted(readable_map.keys())
            window["-TRID-COMBO-"].update(values=readable_list)

            # Debug
            print("\n================= DEBUG SAMPLE =================")
            print(f">>> SAMPLE: {sample_name}")

            for trid_id, sample_obj in sample_trids.items():
                print(f"\n  - {trid_id}")

                a1 = sample_obj.allele1
                a2 = sample_obj.allele2

                print("       allele1:")
                print(f"           size        = {a1.size}")
                print(f"           consensus   = {a1.sequence.sequence}")
                print(f"           mc          = {a1.sequence.repetitions}")
                print(f"           ms          = {a1.sequence.segmentation}")
                print(f"           interruptions = {a1.sequence.interruptions}")
                print(f"           seg_complete  = {a1.sequence.segmentation_complete}")


                print("       allele2:")
                print(f"           size        = {a2.size}")
                print(f"           consensus   = {a2.sequence.sequence}")
                print(f"           mc          = {a2.sequence.repetitions}")
                print(f"           ms          = {a2.sequence.segmentation}")
                print(f"           interruptions = {a2.sequence.interruptions}")
                print(f"           seg_complete  = {a2.sequence.segmentation_complete}")



        # ---------------------------------------------------------
        # Recherche TRID lisible
        # ---------------------------------------------------------
        if event == "-SEARCH-TRID-":
            query = values["-SEARCH-TRID-"].lower()
            readable_map = window.metadata.get("readable_to_trid", {})
            readable_list = sorted(readable_map.keys())

            filtered = [r for r in readable_list if query in r.lower()] if query else readable_list
            window["-TRID-COMBO-"].update(values=filtered)

            # Auto‑sélection si un seul TRID trouvé
            if len(filtered) == 1:
                readable = filtered[0]

                # Sélectionner SANS écraser la liste
                window["-TRID-COMBO-"].update(values=readable_list,value=readable)

                # Effacer la recherche
                window["-SEARCH-TRID-"].update("")

        # ---------------------------------------------------------
        # Ajouter TRID
        # ---------------------------------------------------------
        if event == "-ADD-TRID-":
            readable = values["-TRID-COMBO-"]
            if readable:
                trid = window.metadata["readable_to_trid"][readable]
                if trid not in window.metadata["selected_trids"]:
                    window.metadata["selected_trids"].append(trid)
                update_trid_selected(window)

            # Effacer la sélection dans la combo TRID
            window["-TRID-COMBO-"].update(value="")

            # Effacer aussi la recherche TRID
            window["-SEARCH-TRID-"].update("")


        # ---------------------------------------------------------
        # Tout cocher / décocher
        # ---------------------------------------------------------
        if event == "-SELECT-ALL-":
            readable_map = window.metadata["readable_to_trid"]
            all_trids = list(readable_map.values())

            # 1. TRIDs avec clinique
            trids_clinical = get_trids_with_clinical(window)
            first = [t for t in all_trids if t in trids_clinical]

            # 2. TRIDs sans clinique
            second = [t for t in all_trids if t not in trids_clinical]

            # Ordre final
            window.metadata["selected_trids"] = first + second

            update_trid_selected(window)


        if event == "-UNSELECT-ALL-":
            window.metadata["selected_trids"] = []
            update_trid_selected(window)

        # ---------------------------------------------------------
        # Retirer TRID
        # ---------------------------------------------------------
        if event == "-DEL-TRID-":
            readable_selected = values["-TRID-SELECTED-"] or []
            readable_map = window.metadata["readable_to_trid"]
            selected = window.metadata["selected_trids"]
            for readable in readable_selected:
                trid = readable_map[readable]
                if trid in selected:
                    selected.remove(trid)
            update_trid_selected(window)

        # ---------------------------------------------------------
        # Panels YAML
        # ---------------------------------------------------------
        if event.startswith("-PANEL-"):
            panel_name = event.replace("-PANEL-", "").replace("-", "")
            panels = window.metadata["button_panels"]
            if panel_name in panels:
                requested = panels[panel_name]
                detected = set(window.metadata["all_trids"])
                existing = [t for t in requested if t in detected]
                missing = [t for t in requested if t not in detected]

                window.metadata["selected_trids"] = existing
                update_trid_selected(window)

                if missing:
                    readable_map = window.metadata["readable_to_trid"]
                    missing_readable = []
                    for trid in missing:
                        readable = next((k for k, v in readable_map.items() if v == trid), trid)
                        missing_readable.append(readable)
                    sg.popup("Locus absents du VCF :\n" + "\n".join(missing_readable), keep_on_top=True)

        # ---------------------------------------------------------
        # Lancer l'analyse
        # ---------------------------------------------------------
        if event == "Lancer l'analyse":
            run = window.metadata.get("run")
            sample_name = values["-SAMPLE-"]
            selected_trids = window.metadata.get("selected_trids")

            if not run or not sample_name:
                window["-STATUS-"].update("Veuillez sélectionner un ZIP et un patient", text_color="red")
                continue

            if not selected_trids:
                window["-STATUS-"].update("Veuillez sélectionner au moins un locus", text_color="red")
                continue

            # TRIDs globaux sélectionnés
            trids_global = {
                trid_id: run.trids[trid_id]
                for trid_id in selected_trids
                if trid_id in run.trids
            }

            # Samples associés à ces TRIDs
            samples = {
                trid_id: run.trids[trid_id].samples.get(sample_name)
                for trid_id in selected_trids
                if trid_id in run.trids
            }
            print(fasta_path)
            analysis_input = AnalysisInput(
                sample_name=sample_name,
                trids=trids_global,
                samples=samples,
                ordered_trids=selected_trids,
                paths={
                    "vcf": run.vcf_zip,
                    "repeat_reads": run.repeat_reads_zip,
                    "spanning_bam": run.spanning_bam_zip,
                    "motifs_allele": run.motifs_allele_zip,
                    "motifs_waterfall": run.motifs_waterfall_zip,
                    "meth_allele": run.meth_allele_zip,
                    "meth_waterfall": run.meth_waterfall_zip,
                    "genome_fasta" : fasta_path
                },
                label_priority=window.metadata["label_priority"]
            )

            print("\n====================================")
            print("=== ANALYSIS INPUT STRUCTURE DUMP ===")
            print("====================================\n")

            print(f"Sample name : {analysis_input.sample_name}")
            print(f"TRIDs sélectionnés : {analysis_input.ordered_trids}")

            print("\n--- TRIDs GLOBAUX ---")
            for trid_id, trid in analysis_input.trids.items():
                print(f"\n>>> TRID : {trid_id}")
                print(f"  chrom  = {trid.chrom}")
                print(f"  start  = {trid.start}")
                print(f"  end    = {trid.end}")
                print(f"  motifs = {trid.motifs}")

                if trid.clinical:
                    print("  ClinicalConfig :")
                    print(f"    mode        = {trid.clinical.classification_mode}")
                    print(f"    orientation = {trid.clinical.orientation}")
                    print(f"    groups      = {list(trid.clinical.groups.keys())}")
                else:
                    print("  ClinicalConfig : None")

            print("\n--- SAMPLES ASSOCIÉS ---")
            for trid_id, sample in analysis_input.samples.items():
                print(f"\n>>> TRID : {trid_id}")

                if sample is None:
                    print("  Aucun sample TRGT pour ce TRID")
                    continue

                a1 = sample.allele1
                a2 = sample.allele2

                print("  Allele 1 :")
                print(f"    size        = {a1.size}")
                print(f"    range       = {a1.size_range}")
                print(f"    depth       = {a1.depth}")
                print(f"    purity      = {a1.purity}")
                print(f"    methylation = {a1.methylation}")
                print(f"    consensus   = {a1.sequence.sequence}")
                print(f"    MC          = {a1.sequence.repetitions}")
                print(f"    MS          = {a1.sequence.segmentation}")
                print(f"    MS_complete = {a1.sequence.segmentation_complete}")
                print(f"    interruptions = {a1.sequence.interruptions}")

                print("  Allele 2 :")
                print(f"    size        = {a2.size}")
                print(f"    range       = {a2.size_range}")
                print(f"    depth       = {a2.depth}")
                print(f"    purity      = {a2.purity}")
                print(f"    methylation = {a2.methylation}")
                print(f"    consensus   = {a2.sequence.sequence}")
                print(f"    MC          = {a2.sequence.repetitions}")
                print(f"    MS          = {a2.sequence.segmentation}")
                print(f"    MS_complete = {a2.sequence.segmentation_complete}")
                print(f"    interruptions = {a2.sequence.interruptions}")


            print("\n--- PATHS ---")
            for k, v in analysis_input.paths.items():
                print(f"{k:20s} : {v}")

            print("\n--- LABEL PRIORITY ---")
            print(analysis_input.label_priority)

            print("\n====================================")
            print("=== END OF STRUCTURE DUMP ===")
            print("====================================\n")

            process_clinical(analysis_input)
            process_result(analysis_input)

            results = []   # ← liste de Result

            for trid_id, sample in analysis_input.samples.items():
                if not sample or not sample.result:
                    continue

                clinical_cfg = analysis_input.trids[trid_id].clinical

                # Construit display_row / display_details / display_export / display_html
                process_display(sample.result, clinical_cfg)

                # On stocke l'objet Result complet
                results.append(sample.result)
                
            # Maintenant on appelle l'UI avec la liste de Result
            print(f"[INFO] Lancement de la fenêtre des résultats avec les chemins d'accès : {analysis_input.paths}")
            show_results_window(
                sample_name=sample_name.replace(".trgt.vcf", ""),
                results=results,
                label_priority=analysis_input.label_priority,
                paths=analysis_input.paths,
                online_status=online_status   
            )

    window.close()