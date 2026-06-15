import PySimpleGUI as sg
import os

def build_details_panel():
    return sg.Frame("Détails", [
        [
            sg.Multiline(
                "",
                key="-DETAILS-",
                disabled=True,
                expand_x=True,
                expand_y=True,
                font=("Consolas", 10) if os.name == "nt" else ("Courier New", 10)
            )
        ],
        [
            sg.Button("Séquence allèle 1", key="-SEQ1-", disabled=True),
            sg.Button("Séquence allèle 2", key="-SEQ2-", disabled=True),
        ],
        [
            # Le bouton est placé ici, PySimpleGUI le trouvera de manière globale
            sg.Button("Ouvrir IGV", key="-IGV-", disabled=True),
            sg.Text("Plots :", pad=((20, 5), 0)),
            sg.Combo([], key="-PLOT-LIST-", size=(30, 1), readonly=True),
            sg.Button("Ouvrir plot", key="-PLOT-OPEN-", disabled=True),
        ]
    ], expand_x=True, expand_y=True)


def update_details(window, dd):
    lines = []

    def add(label, value):
        if value not in (None, "", []):
            lines.append(f"{label:<22} {value}")

    # --- Informations générales ---
    lines.append("=== Informations générales ===")
    add("Locus :", dd.locus)
    add("Profondeur :", dd.depth)
    add("Taille (bp) :", dd.size)
    add("Méthylation :", dd.methylation)
    add("Purity :", dd.purity)
    add("Motifs TRGT :", dd.motifs)
    add("Génotype auto :", dd.gt_auto)
    add("Génotype final :", dd.genotype)

    add("Classification auto :", dd.classification_auto)
    add("Classification finale :", dd.classification)

    lines.append("")

    # --- Allèle 1 ---
    lines.append("=== Allèle 1 ===")
    add("Motifs cliniques :", dd.motifs_use1)
    add("Répétition :", dd.rep1)
    add("Segmentation :", dd.seg1)
    add("Interruptions :", dd.interruptions1)

    if dd.sequence1:
        add("Séquence :", "[cliquer bouton]")
        window["-SEQ1-"].update(disabled=False)
    else:
        window["-SEQ1-"].update(disabled=True)

    lines.append("")

    # --- Allèle 2 ---
    lines.append("=== Allèle 2 ===")
    add("Motifs cliniques :", dd.motifs_use2)
    add("Répétition :", dd.rep2)
    add("Segmentation :", dd.seg2)
    add("Interruptions :", dd.interruptions2)

    if dd.sequence2:
        add("Séquence :", "[cliquer bouton]")
        window["-SEQ2-"].update(disabled=False)
    else:
        window["-SEQ2-"].update(disabled=True)

    window["-DETAILS-"].update("\n".join(lines))