import tempfile
import os
import webbrowser
import logging
from pathlib import Path

from scripts.ui.igv import start_local_server, cleanup_tmpdir_force, CURRENT_TMPDIR

try:
    from scripts.core.i18n import tr
except ImportError:
    try:
        from core.i18n import tr
    except ImportError:
        try:
            from i18n import tr
        except ImportError:
            def tr(text: str) -> str:
                return text

try:
    import PySimpleGUI as sg
except ImportError:
    sg = None


def is_low_coverage(r_dict):
    for key, val in r_dict.items():
        if key in ["Result_obj", "Details_obj"]:
            continue
        val_str = str(val)
        if "⚠️" in val_str or "\u26a0" in val_str:
            return True
    return False


def generate_html_table(headers, rows, sample_name, run_id=None):
    logging.info(f"Generating export HTML table for patient '{sample_name}' with {len(rows)} selected rows.")

    headers = list(headers)
    comments_label = tr("Commentaires")
    if comments_label not in headers:
        headers.append(comments_label)

    thead_html = (
        "<tr><th class='col-checkbox'></th>"
        + "".join(f"<th>{tr(h)}</th>" for h in headers)
        + f"<th class='col-actions'>{tr('Actions')}</th>"
        + "</tr>"
    )

    tbody_rows = []
    for r_dict in rows:
        row_html = "<tr>"
        row_html += "<td class='col-checkbox'><input type='checkbox' class='row-checkbox' checked></td>"
        
        r_obj = r_dict.get("Result_obj")
        is_low = is_low_coverage(r_dict)

        is_classif_modified = False
        if r_obj:
            if getattr(r_obj, "classification1_bio", None) or getattr(r_obj, "classification2_bio", None):
                is_classif_modified = True
        if r_dict.get("Classification") != r_dict.get("Classification_auto"):
            is_classif_modified = True

        is_genotype_modified = False
        if r_obj:
            if getattr(r_obj, "genotype1_bio", None) is not None or getattr(r_obj, "genotype2_bio", None) is not None:
                is_genotype_modified = True
        gt_current = r_dict.get("Génotype") or r_dict.get("Genotype", "")
        if gt_current != r_dict.get("Genotype_auto"):
            is_genotype_modified = True

        for h in headers:
            if h in ("Commentaires", comments_label):
                comment_val = tr("Couverture faible") if is_low else ""
                row_html += f"<td><span contenteditable='true' class='comment-input' data-placeholder=\"{tr('Ajouter un commentaire...')}\">{comment_val}</span></td>"
            else:
                val = r_dict.get(h, '')
                classes = []
                if h == "Classification" and is_classif_modified:
                    classes.append("modified-cell")
                elif h in ("Génotype", "Genotype") and is_genotype_modified:
                    classes.append("modified-cell")
                
                class_attr = f" class='{' '.join(classes)}'" if classes else ""
                row_html += f"<td{class_attr}>{tr(str(val))}</td>"

        swap_title = tr("Inverser Allèle 1 / Allèle 2")
        row_html += f'<td class="col-actions"><button type="button" class="btn-swap" onclick="swapRowAlleles(this)" title="{swap_title}">⇅</button></td>'
        row_html += "</tr>"
        tbody_rows.append(row_html)
    tbody_html = "".join(tbody_rows)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{tr("Résultats TGV")} - {sample_name}</title>
<style>
  :root {{
    --bg:        #f7f7f8;
    --surface:   #ffffff;
    --surface2:  #fdf4f7;
    --border:    #e8dde2;
    --accent:    #c8336a;
    --accent-lt: #fdf0f4;
    --accent2:   #9e1f4f;
    --muted:     #8a7480;
    --text:      #1a1015;
    --text-dim:  #5a4050;
    --success:   #2a7a4a;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --font-mono: SFMono-Regular, Consolas, "Liberation Mono", Menlo, Monaco, Courier, monospace;
  }}

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: 14px;
    line-height: 1.6;
    min-height: 100vh;
  }}

  .header {{
    background: var(--surface);
    border-bottom: 3px solid var(--accent);
    padding: 18px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
  }}
  .header-brand {{
    display: flex;
    align-items: center;
    gap: 16px;
  }}
  .header-logo-mark {{
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, #e8457a 0%, #9e1f4f 100%);
    flex-shrink: 0;
  }}
  .header-titles h1 {{
    font-size: 16px;
    font-weight: 600;
    color: var(--text);
    letter-spacing: -0.2px;
    line-height: 1.2;
  }}
  .header-titles .subtitle {{
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--muted);
    margin-top: 2px;
  }}

  .main {{ padding: 32px 40px; max-width: 1600px; margin: 0 auto; }}
  .section {{ margin-bottom: 44px; }}

  .section-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
  }}
  .section-title {{
    font-size: 13px;
    font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }}

  .table-wrapper {{
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
    white-space: nowrap;
  }}
  thead th {{
    background: var(--surface2);
    color: var(--text-dim);
    font-weight: 600;
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 9px 14px;
    text-align: left;
    border-bottom: 2px solid var(--border);
  }}
  tbody tr {{ border-bottom: 1px solid var(--border); }}
  tbody tr:last-child {{ border-bottom: none; }}
  tbody tr:hover {{ background: var(--surface2); }}
  tbody td {{
    padding: 8px 14px;
    color: var(--text);
    font-family: var(--font-mono);
    font-size: 12px;
  }}
  
  tbody td:nth-child(2) {{
    color: var(--accent2);
    font-weight: 500;
    font-family: var(--font-sans);
    font-size: 12.5px;
  }}

  td.modified-cell {{
    position: relative;
    background-color: var(--accent-lt) !important;
    border-bottom: 1.5px dashed var(--accent) !important;
  }}
  td.modified-cell::after {{
    content: " ✎";
    color: var(--accent);
    font-weight: bold;
    font-size: 11px;
    font-family: var(--font-sans);
    pointer-events: none;
  }}

  .comment-input {{
    display: block;
    width: 100%;
    min-width: 220px;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 4px 8px;
    font-family: var(--font-sans);
    font-size: 12px;
    background: var(--surface);
    outline: none;
  }}
  .comment-input:focus {{
    border-color: var(--accent);
    background: #fff;
  }}
  .comment-input:empty::before {{
    content: attr(data-placeholder);
    color: var(--muted);
    font-style: italic;
  }}

  .col-checkbox {{ width: 45px; text-align: center; padding: 8px; }}
  .row-checkbox {{ transform: scale(1.15); cursor: pointer; accent-color: var(--accent); }}
  .col-actions {{ width: 80px; text-align: center; padding: 8px; }}
  .btn-swap {{
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--accent2);
    border-radius: 4px;
    cursor: pointer;
    padding: 4px 10px;
    font-size: 13px;
    font-weight: bold;
    transition: all 0.15s;
  }}
  .btn-swap:hover {{
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
    transform: scale(1.08);
  }}

  .btn-container {{
    margin-top: 20px;
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }}
  
  .btn {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 11px;
    font-family: var(--font-mono);
    font-weight: 500;
    cursor: pointer;
    text-transform: uppercase;
  }}
  
  .btn-primary {{ background: var(--accent-lt); border: 1px solid #d9a0b4; color: var(--accent2); }}
  .btn-primary:hover {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
  .btn-primary.copied {{ background: var(--success); border-color: var(--success); color: #fff; }}
  .btn-secondary {{ background: var(--surface); border: 1px solid var(--border); color: var(--text-dim); }}
  .btn-secondary:hover {{ background: var(--surface2); color: var(--accent2); }}

  .footer {{
    margin-top: 56px;
    padding: 18px 40px;
    border-top: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .footer-dot {{
    width: 8px; height: 8px;
    border-radius: 50%;
    background: linear-gradient(135deg, #e8457a, #9e1f4f);
    display: inline-block;
    margin-right: 8px;
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-brand">
    <div class="header-logo-mark"></div>
    <div class="header-titles">
      <h1>TRGT Global Viewer &mdash; {tr("Export Data")}</h1>
      <div class="subtitle">{sample_name}</div>
    </div>
  </div>
</div>

<main class="main">
  <section class="section">
    <div class="section-header">
      <div class="section-title">{tr("Résultats TGV")}</div>
    </div>
    
    <div class="table-wrapper">
      <table>
        <thead>
          {thead_html}
        </thead>
        <tbody>
          {tbody_html}
        </tbody>
      </table>
    </div>

    <div class="btn-container">
      <button type="button" class="btn btn-secondary" onclick="setAllCheckboxes(true)">{tr("Tout cocher")}</button>
      <button type="button" class="btn btn-secondary" onclick="setAllCheckboxes(false)">{tr("Tout décocher")}</button>
      <button type="button" id="btn-copy" class="btn btn-primary" onclick="copySelectedRows()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
          <rect x="9" y="9" width="13" height="13" rx="2"/>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
        <span>{tr("Copier la sélection")}</span>
      </button>
    </div>
  </section>
</main>

<footer class="footer">
  <div><span class="footer-dot"></span><span>TRGT Global Viewer &bull; {sample_name}</span></div>
</footer>

<script>
  function setAllCheckboxes(checked) {{
    document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = checked);
  }}

  // Inverse les valeurs composées (ex: "40/2", "38 / 2", "40 (38/2)", "Sain / Pathogène")
  function swapCompositeValue(str) {{
    str = str.trim();
    if (!str || str.startsWith('http')) return str;

    // Format avec parenthèses : ex "40 (38/2)" ou "40 (38 / 2)"
    const matchParen = str.match(/^(.*?\\()([^/]+)\\/([^)]+)(\\).*)$/);
    if (matchParen) {{
      return matchParen[1] + matchParen[3].trim() + '/' + matchParen[2].trim() + matchParen[4];
    }}

    // Format avec espace "A / B"
    if (str.includes(' / ')) {{
      const parts = str.split(' / ');
      if (parts.length === 2) {{
        return parts[1].trim() + ' / ' + parts[0].trim();
      }}
    }}

    // Format direct avec slash "A/B" ou "40/2"
    if (str.includes('/')) {{
      const parts = str.split('/');
      if (parts.length === 2) {{
        return parts[1].trim() + '/' + parts[0].trim();
      }}
    }}

    return str;
  }}

  function swapRowAlleles(button) {{
    const row = button.closest('tr');
    if (!row) return;
    const table = row.closest('table');
    if (!table) return;

    const thElements = Array.from(table.querySelectorAll('thead th'));
    const headers = thElements.map(th => th.innerText.trim());
    const cells = Array.from(row.querySelectorAll('td'));
    const pairedIndices = new Set();

    // 1. Inversion des colonnes distinctes Allèle 1 <-> Allèle 2
    for (let i = 0; i < headers.length; i++) {{
      const h1 = headers[i];
      if (!h1) continue;
      const lower = h1.toLowerCase();
      let targetLower = null;

      if (lower.includes('allèle 1')) {{
        targetLower = lower.replace('allèle 1', 'allèle 2');
      }} else if (lower.includes('allele 1')) {{
        targetLower = lower.replace('allele 1', 'allele 2');
      }} else if (lower.includes('a1')) {{
        targetLower = lower.replace('a1', 'a2');
      }}

      if (targetLower) {{
        const j = headers.findIndex(h => h.toLowerCase() === targetLower);
        if (j !== -1 && j !== i && !pairedIndices.has(i) && !pairedIndices.has(j)) {{
          pairedIndices.add(i);
          pairedIndices.add(j);
          if (cells[i] && cells[j]) {{
            const tempHTML = cells[i].innerHTML;
            cells[i].innerHTML = cells[j].innerHTML;
            cells[j].innerHTML = tempHTML;

            const tempClass = cells[i].className;
            cells[i].className = cells[j].className;
            cells[j].className = tempClass;
          }}
        }}
      }}
    }}

    // 2. Inversion des colonnes combinées (Profondeur/Depth, Génotype, Classification, etc.)
    for (let k = 0; k < headers.length; k++) {{
      if (pairedIndices.has(k) || !cells[k]) continue;
      const hLow = headers[k].toLowerCase();

      // Ignorer les colonnes de sélection, d'actions, de commentaires et de Locus
      if (hLow === '' || hLow.includes('action') || hLow.includes('comment') || hLow.includes('locus')) {{
        continue;
      }}

      const currentHTML = cells[k].innerHTML.trim();
      const swappedHTML = swapCompositeValue(currentHTML);
      if (swappedHTML !== currentHTML) {{
        cells[k].innerHTML = swappedHTML;
      }}
    }}
  }}

  async function copySelectedRows() {{
    const runId = "{run_id}";
    const sampleName = "{sample_name}";
    const rows = document.querySelectorAll('table tbody tr');
    let tsvContent = '';
    let hasSelected = false;

    rows.forEach(row => {{
      const checkbox = row.querySelector('.row-checkbox');
      if (checkbox && checkbox.checked) {{
        hasSelected = true;
        const cells = Array.from(row.querySelectorAll('td')).slice(1, -1).map(td => {{
          const tempTd = td.cloneNode(true);
          tempTd.classList.remove('modified-cell');
          const commentInput = tempTd.querySelector('.comment-input');
          let textVal = commentInput ? commentInput.innerText : tempTd.innerText;
          textVal = textVal.replace(/[\\u26A0\\uFE0F]/g, '');
          return textVal.trim();
        }});
        const rowData = [runId, sampleName, ...cells];
        tsvContent += rowData.join('\\t') + '\\n';
      }}
    }});

    if (!hasSelected) {{
      alert("{tr("Aucune ligne n'est sélectionnée pour la copie.")}");
      return;
    }}

    try {{
      await navigator.clipboard.writeText(tsvContent);
      const btn = document.getElementById('btn-copy');
      btn.classList.add('copied');
      const textSpan = btn.querySelector('span');
      const originalText = textSpan.innerText;
      textSpan.innerText = "{tr("Copié !")}";
      setTimeout(() => {{
        btn.classList.remove('copied');
        textSpan.innerText = originalText;
      }}, 2000);
    }} catch (err) {{
      alert("{tr("Erreur lors de la copie : ")}" + err);
    }}
  }}
</script>
</body>
</html>
"""
    return html


def save_and_open_html(html_content):
    global CURRENT_TMPDIR, CURRENT_SERVER
    
    try:
        # 1. Nettoyage de l'ancienne session (port et dossier)
        cleanup_tmpdir_force() # Utilise votre fonction existante qui appelle stop_local_server()
        
        # 2. Création d'un dossier temporaire dédié pour ce rapport
        CURRENT_TMPDIR = tempfile.mkdtemp(prefix="tgv_report_")
        
        # 3. Écriture du fichier dans ce dossier
        tmp_path = os.path.join(CURRENT_TMPDIR, "index.html")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        # 4. Lancement du serveur sur ce dossier
        port = start_local_server(CURRENT_TMPDIR)
        
        # 5. Ouverture via le serveur (port local)
        url = f"http://127.0.0.1:{port}/index.html"
        logging.info(f"Ouverture du rapport via serveur local : {url}")
        webbrowser.open(url)
        
    except Exception as e:
        logging.error(f"Erreur lors de l'export HTML : {e}")
        if sg:
            sg.popup_error(f"{tr('Erreur')} :\n{e}")