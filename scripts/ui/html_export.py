import os
import tempfile
import webbrowser
import logging
import PySimpleGUI as sg
from pathlib import Path


def generate_html_table(headers, rows, sample_name):
    """Construit un tableau HTML complet, interactif et instantané (sans dépendances externes)."""
    logging.info(f"Generating export HTML table for patient '{sample_name}' with {len(rows)} selected rows.")

    # Pré-génération du tableau (avec ajout d'une colonne Actions à la fin)
    thead_html = (
        "<tr><th class='col-checkbox'></th>"
        + "".join(f"<th>{h}</th>" for h in headers)
        + "<th class='col-actions'>Actions</th>"
        + "</tr>"
    )

    tbody_rows = []
    for r in rows:
        row_html = "<tr>"
        row_html += "<td class='col-checkbox'><input type='checkbox' class='row-checkbox' checked></td>"
        row_html += "".join(f"<td>{r.get(h, '')}</td>" for h in headers)
        row_html += "<td class='col-actions'><button class='btn-swap' onclick='swapRowAlleles(this)' title='Inverser Allèle 1 / Allèle 2'>⇅</button></td>"
        row_html += "</tr>"
        tbody_rows.append(row_html)
    tbody_html = "".join(tbody_rows)

    # Document HTML avec polices système locales pour une rapidité maximale
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Résultats TRGT  {sample_name}</title>
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
    
    /* Utilisation de polices système locales très performantes */
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

  /* ── Header ── */
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
  .header-meta {{
    text-align: right;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--muted);
    line-height: 1.7;
  }}

  /* ── Layout ── */
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

  /* ── Tables ── */
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

  /* ── Checkboxes ── */
  .col-checkbox {{
    width: 45px;
    text-align: center;
    padding: 8px;
  }}
  .row-checkbox {{
    transform: scale(1.15);
    cursor: pointer;
    accent-color: var(--accent);
    vertical-align: middle;
  }}

  /* ── Actions (Swap button) ── */
  .col-actions {{
    width: 80px;
    text-align: center;
    padding: 8px;
  }}
  .btn-swap {{
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--accent2);
    border-radius: 4px;
    cursor: pointer;
    padding: 3px 8px;
    font-size: 12px;
    font-family: var(--font-sans);
    transition: all 0.15s;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    line-height: 1;
  }}
  .btn-swap:hover {{
    background: var(--accent-lt);
    border-color: var(--accent);
    color: var(--accent);
  }}

  /* ── Actions Container & Buttons ── */
  .btn-container {{
    margin-top: 20px;
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    justify-content: flex-start;
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
    transition: all 0.15s;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  
  .btn-primary {{
    background: var(--accent-lt);
    border: 1px solid #d9a0b4;
    color: var(--accent2);
  }}
  .btn-primary:hover {{
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }}
  .btn-primary.copied {{
    background: var(--success);
    border-color: var(--success);
    color: #fff;
  }}
  
  .btn-secondary {{
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-dim);
  }}
  .btn-secondary:hover {{
    background: var(--surface2);
    border-color: #d9a0b4;
    color: var(--accent2);
  }}

  /* ── Footer ── */
  .footer {{
    margin-top: 56px;
    padding: 18px 40px;
    border-top: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .footer-left {{
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .footer-dot {{
    width: 8px; height: 8px;
    border-radius: 50%;
    background: linear-gradient(135deg, #e8457a, #9e1f4f);
  }}
  .footer span {{
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--muted);
  }}

  @media print {{
    .btn-container, .col-actions, .btn-swap {{
      display: none !important;
    }}
    body {{
      margin: 0;
      background: white;
    }}
    .table-wrapper {{
      box-shadow: none;
      border: none;
    }}
    th, td {{
      padding: 8px;
      border: 1px solid var(--border);
    }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-brand">
    <div class="header-logo-mark"></div>
    <div class="header-titles">
      <h1>TRGT Global Viewer &mdash; Export Data</h1>
      <div class="subtitle">{sample_name}</div>
    </div>
  </div>
  <div class="header-meta">
  </div>
</div>

<main class="main">
  <section class="section">
    <div class="section-header">
      <div class="section-title">Résultats TRGT</div>
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
      <button class="btn btn-secondary" onclick="setAllCheckboxes(true)">Tout cocher</button>
      <button class="btn btn-secondary" onclick="setAllCheckboxes(false)">Tout décocher</button>
      <button id="btn-copy" class="btn btn-primary" onclick="copySelectedRows()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12" style="flex-shrink:0;">
          <rect x="9" y="9" width="13" height="13" rx="2"/>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
        <span>Copier la sélection</span>
      </button>
    </div>
  </section>
</main>

<footer class="footer">
  <div class="footer-left">
    <div class="footer-dot"></div>
    <span>PacBio TRGT · {sample_name}</span>
  </div>
</footer>

<script>
  function setAllCheckboxes(checked) {{
    const checkboxes = document.querySelectorAll('.row-checkbox');
    checkboxes.forEach(cb => cb.checked = checked);
  }}

  function swapRowAlleles(button) {{
    const row = button.closest('tr');
    if (!row) return;

    // Récupère l'ensemble des en-têtes du tableau pour mapper les colonnes séparées
    const headers = Array.from(document.querySelectorAll('table th')).map(th => th.innerText.trim());
    const cells = Array.from(row.querySelectorAll('td'));
    const pairs = [];

    // Détermine la correspondance d'en-tête opposée (ex: "Allele 1" -> "Allele 2")
    function getOppositeHeader(name) {{
      if (name.includes('Allele 1')) return name.replace('Allele 1', 'Allele 2');
      if (name.includes('Allele1')) return name.replace('Allele1', 'Allele2');
      if (name.includes('Allèle 1')) return name.replace('Allèle 1', 'Allèle 2');
      if (name.includes('Allèle1')) return name.replace('Allèle1', 'Allèle2');
      if (name.includes('A1')) return name.replace('A1', 'A2');
      if (name.includes('a1')) return name.replace('a1', 'a2');
      if (name.includes('1')) {{
        const lastIndex = name.lastIndexOf('1');
        return name.substring(0, lastIndex) + '2' + name.substring(lastIndex + 1);
      }}
      return null;
    }}

    // Recherche de toutes les paires de colonnes indépendantes à permuter
    for (let i = 0; i < headers.length; i++) {{
      const h1 = headers[i];
      if (!h1) continue;

      const target = getOppositeHeader(h1);
      if (target) {{
        const j = headers.findIndex(h => h === target);
        if (j !== -1 && j !== i) {{
          const alreadyAdded = pairs.some(p => p[0] === i || p[1] === i || p[0] === j || p[1] === j);
          if (!alreadyAdded) {{
            pairs.push([i, j]);
          }}
        }}
      }}
    }}

    // 1. Permuter les colonnes indépendantes si elles existent
    pairs.forEach(([i, j]) => {{
      if (cells[i] && cells[j]) {{
        const temp = cells[i].innerHTML;
        cells[i].innerHTML = cells[j].innerHTML;
        cells[j].innerHTML = temp;
      }}
    }});

    // 2. Traiter chaque cellule de données pour inverser le contenu séparé par "/"
    // On ignore l'index 0 (checkbox) et le dernier index (bouton d'action)
    for (let i = 1; i < cells.length - 1; i++) {{
      const cell = cells[i];

      // Évite de ré-inverser une colonne qui vient d'être permutée en tant que paire globale
      const isPairColumn = pairs.some(p => p[0] === i || p[1] === i);
      if (isPairColumn) continue;

      // Cas 1 : La cellule contient du texte brut simple
      if (cell.children.length === 0) {{
        const text = cell.textContent.trim();
        if (text.includes('/')) {{
          const parts = text.split('/');
          if (parts.length === 2) {{
            // Détection et conservation des espaces d'origine (ex: "12/15" ou "12 / 15")
            const hasLeftSpace = parts[0].endsWith(' ');
            const hasRightSpace = parts[1].startsWith(' ');
            const separator = (hasLeftSpace ? ' ' : '') + '/' + (hasRightSpace ? ' ' : '');
            
            cell.textContent = parts[1].trim() + separator + parts[0].trim();
          }}
        }}
      }} else {{
        // Cas 2 : La cellule contient des éléments enfants (badges HTML, spans, etc.)
        const nodes = Array.from(cell.childNodes);
        // On cherche le nœud de texte correspondant au séparateur "/"
        const slashIndex = nodes.findIndex(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim() === '/');
        
        if (slashIndex !== -1) {{
          const leftNodes = nodes.slice(0, slashIndex);
          const rightNodes = nodes.slice(slashIndex + 1);
          
          cell.innerHTML = '';
          // On ré-injecte l'allèle 2 à gauche, puis le séparateur, puis l'allèle 1 à droite
          rightNodes.forEach(n => cell.appendChild(n));
          cell.appendChild(nodes[slashIndex]);
          leftNodes.forEach(n => cell.appendChild(n));
        }}
      }}
    }}
  }}

  async function copySelectedRows() {{
    // Utilisation de .slice(1, -1) pour exclure la première colonne (checkbox) et la dernière colonne (Actions)
    const headers = Array.from(document.querySelectorAll('table th')).slice(1, -1).map(th => th.innerText);
    const rows = document.querySelectorAll('table tbody tr');
    let tsvContent = headers.join('\\t') + '\\n';
    let hasSelected = false;

    rows.forEach(row => {{
      const checkbox = row.querySelector('.row-checkbox');
      if (checkbox && checkbox.checked) {{
        hasSelected = true;
        const cells = Array.from(row.querySelectorAll('td')).slice(1, -1).map(td => td.innerText.trim());
        tsvContent += cells.join('\\t') + '\\n';
      }}
    }});

    if (!hasSelected) {{
      alert("Aucune ligne n'est sélectionnée pour la copie.");
      return;
    }}

    try {{
      await navigator.clipboard.writeText(tsvContent);
      
      const btn = document.getElementById('btn-copy');
      btn.classList.add('copied');
      const textSpan = btn.querySelector('span');
      const originalText = textSpan.innerText;
      
      textSpan.innerText = "Copié !";
      
      setTimeout(() => {{
        btn.classList.remove('copied');
        textSpan.innerText = originalText;
      }}, 2000);
    }} catch (err) {{
      alert("Erreur lors de la copie : " + err);
    }}
  }}
</script>

</body>
</html>
"""
    return html


def save_and_open_html(html_content):
    """Enregistre le HTML dans un fichier temporaire et l’ouvre de manière robuste sur tous les OS."""
    logging.info("Saving temporary HTML table export file...")
    try:
        tmp_path = os.path.join(tempfile.gettempdir(), "trgt_table.html")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logging.debug(f"Temporary export file successfully written at: {tmp_path}")

        # Path().as_uri() s'occupe de mettre le bon nombre de slashes selon l'OS (Windows vs Unix)
        uri = Path(tmp_path).as_uri()
        logging.info(f"Opening webbrowser for HTML table export at: {uri}")
        webbrowser.open(uri)
    except Exception as e:
        logging.error(f"Failed to generate or open temporary HTML table export: {e}", exc_info=True)
        sg.popup_error(f"Impossible de générer ou d'ouvrir le rapport d'exportation temporaire :\n{e}")