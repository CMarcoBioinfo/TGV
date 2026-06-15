import PySimpleGUI as sg

def build_results_table(rows, headers, col_widths):
    """
    Construit le tableau principal TRGT.
    Retourne : (widget_table, table_data)
    """

    table_data = [[r.get(h, "") for h in headers] for r in rows]

    table = sg.Table(
        values=table_data,
        headings=headers,
        auto_size_columns=False,
        col_widths=col_widths,
        justification="left",
        num_rows=max(1, min(20, len(table_data))),
        key="-TABLE-",
        enable_events=True,
        expand_x=True,
        expand_y=False
    )

    return table, table_data