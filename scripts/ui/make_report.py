#!/usr/bin/env python3
"""
make_report.py  Rapport HTML standalone pour sorties PacBio TRGT (pbcommand)

Usage en ligne de commande (Génère à la volée et ouvre dans le navigateur) :
    python make_report.py <dossier_run_ou_fichier_zip>

Usage en tant que module (pour votre outil TGV) :
    from make_report import generate_report_html_string, open_report_on_the_fly
"""
import os
import argparse
import base64
import json
import sys
import zipfile
import io
import csv
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# RunReader : Abstraction de lecture pour Dossier ET Archive ZIP (Sans Pandas)
# ---------------------------------------------------------------------------
class RunReader:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.is_zip = zipfile.is_zipfile(path)
        self.zip_file = None
        if self.is_zip:
            self.zip_file = zipfile.ZipFile(path, "r")
            
    def get_run_name(self) -> str:
        return self.path.stem

    def list_json_candidates(self) -> list[str]:
        """Liste les fichiers JSON en excluant le rapport de tâche interne de Cromwell."""
        if self.is_zip:
            return [
                n for n in self.zip_file.namelist() 
                if n.endswith(".json") and not n.startswith("__MACOSX") and "task-report" not in n
            ]
        else:
            return [
                p.name for p in self.path.glob("*.json") 
                if "task-report" not in p.name
            ]

    def find_member(self, filename: str) -> str | None:
        """Trouve le chemin exact d'un fichier dans le ZIP, même s'il est dans un sous-dossier."""
        if not self.is_zip:
            return None
        names = self.zip_file.namelist()
        if filename in names:
            return filename
        for n in names:
            if n.endswith("/" + filename) or n.endswith("\\" + filename):
                return n
        return None

    def file_exists(self, filename: str) -> bool:
        if self.is_zip:
            return self.find_member(filename) is not None
        else:
            return (self.path / filename).exists()

    def read_json(self, name: str) -> dict:
        if self.is_zip:
            member = self.find_member(name) or name
            with self.zip_file.open(member) as f:
                return json.load(f)
        else:
            with open(self.path / name) as f:
                return json.load(f)

    def read_csv(self, filename: str) -> list[list[str]]:
        """Lit un CSV et retourne une liste de lignes (listes de chaînes)."""
        if self.is_zip:
            member = self.find_member(filename)
            if not member:
                return []
            with self.zip_file.open(member) as f:
                content = f.read().decode("utf-8-sig", errors="ignore")
        else:
            file_path = self.path / filename
            if not file_path.exists():
                return []
            with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                content = f.read()
        
        lines = []
        reader_obj = csv.reader(io.StringIO(content))
        for row in reader_obj:
            lines.append(row)
        return lines

    def read_png_base64(self, filename: str) -> str | None:
        if self.is_zip:
            member = self.find_member(filename)
            if not member:
                return None
            with self.zip_file.open(member) as f:
                return base64.b64encode(f.read()).decode("ascii")
        else:
            file_path = self.path / filename
            if not file_path.exists():
                return None
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")

    def close(self):
        if self.zip_file:
            self.zip_file.close()


# ---------------------------------------------------------------------------
# Formatage & Tableaux HTML
# ---------------------------------------------------------------------------

def fmt_attribute_value(value) -> str:
    if isinstance(value, int):
        return f"{value:,}".replace(",", "\u202f")  # espace fine insécable
    return str(value)


def df_to_html_table(table_data: dict, table_id: str) -> str:
    """Génère un tableau HTML à partir d'un dictionnaire {"headers": [...], "rows": [[...]]}."""
    if not table_data:
        return ""
    headers = "".join(f"<th>{col}</th>" for col in table_data["headers"])
    rows = []
    for row in table_data["rows"]:
        cells = "".join(f"<td>{v}</td>" for v in row)
        rows.append(f"<tr>{cells}</tr>")
    
    return (
        f'<table id="{table_id}">\n'
        f'<thead><tr>{headers}</tr></thead>\n'
        f'<tbody>\n' + "\n".join(rows) + '\n</tbody>\n'
        f'</table>'
    )


# ---------------------------------------------------------------------------
# Fonction principale de génération du HTML (f-string pur, pas de dépendance)
# ---------------------------------------------------------------------------

def generate_report_html_string(input_path: Path) -> str:
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Le chemin spécifié est introuvable : {input_path}")
        
    reader = RunReader(input_path)
    run_name = reader.get_run_name()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # ── 1. Recherche du JSON ──
    json_candidates = reader.list_json_candidates()
    if not json_candidates:
        reader.close()
        raise FileNotFoundError(f"Aucun fichier JSON valide trouvé dans {input_path.name}")
        
    json_filename = json_candidates[0]
    data = reader.read_json(json_filename)

    # ── 2. Attributes (Metrics) ──
    attributes = []
    for attr in data.get("attributes", []):
        fmt = fmt_attribute_value(attr["value"])
        attributes.append({"name": attr["name"], "value_fmt": fmt})
    
    raw_attrs = data.get("attributes", [])
    metrics_tsv = (
        "\t".join(a["name"] for a in raw_attrs)
        + "\n"
        + "\t".join(str(a["value"]) for a in raw_attrs)
    )
    metrics_tsv_json = json.dumps(metrics_tsv)

    # ── 3. Version pbcommand ──
    comment = data.get("_comment", "")
    pbcommand_version = "?"
    if "version" in comment:
        parts = comment.split("version")
        if len(parts) > 1:
            pbcommand_version = parts[1].strip().split()[0] or "?"

    # ── 4. Plot groups (Chargement dynamique selon la présence des fichiers) ──
    EXCLUDED_PLOT_GROUPS = {"Read Categories"}
    plot_groups = []
    for group in data.get("plotGroups", []):
        if group["title"] in EXCLUDED_PLOT_GROUPS:
            continue
        plots = []
        for plot in group.get("plots", []):
            img_name = plot["image"]
            b64 = reader.read_png_base64(img_name)
            
            if b64:
                plots.append({
                    "title": plot.get("title"),
                    "caption": plot.get("caption"),
                    "image": img_name,
                    "b64": b64,
                })
                
        if plots:
            plot_groups.append({"title": group["title"], "plots": plots})

    # ── 5. Sample Summary (sans Pandas) ──
    sample_summary_html = None
    if reader.file_exists("sample_summary.csv"):
        raw_lines = reader.read_csv("sample_summary.csv")
        if raw_lines:
            headers = raw_lines[0]
            rows = []
            for row in raw_lines[1:]:
                if not row:
                    continue
                if row[0] == "Sample Average":
                    continue
                rows.append(row)
            
            table_data = {"headers": headers, "rows": rows}
            sample_summary_html = df_to_html_table(table_data, "tbl-sample-summary")

    # ── 6. Target Coverage (sans Pandas) ──
    target_cov_html = None
    if reader.file_exists("target_cov_by_sample.csv"):
        raw_lines = reader.read_csv("target_cov_by_sample.csv")
        if raw_lines and len(raw_lines) >= 2:
            targets = [row[0] for row in raw_lines[1:] if row]
            samples = raw_lines[0][1:]
            
            new_headers = ["Sample"] + targets
            new_rows = []
            for i, sample in enumerate(samples):
                new_row = [sample]
                for row in raw_lines[1:]:
                    if not row:
                        continue
                    if len(row) > (i + 1):
                        val_str = row[i + 1]
                        try:
                            val = int(round(float(val_str)))
                        except ValueError:
                            val = val_str
                        new_row.append(str(val))
                    else:
                        new_row.append("N/A")
                new_rows.append(new_row)
            
            table_data = {"headers": new_headers, "rows": new_rows}
            target_cov_html = df_to_html_table(table_data, "tbl-target-coverage")

    reader.close()

    # ── 7. Construction dynamique des blocs HTML (sans \\n visibles) ──
    
    # Navigation
    nav_links = ['<a href="#run-metrics" class="active">Run Metrics</a>']
    if plot_groups:
        nav_links.append('<a href="#plots">Plots</a>')
    if sample_summary_html:
        nav_links.append('<a href="#sample-summary">Sample Summary</a>')
    if target_cov_html:
        nav_links.append('<a href="#target-coverage">Target Coverage</a>')
    nav_links_html = "\n  ".join(nav_links)

    # Cartes de métriques
    metrics_cards_list = []
    for attr in attributes:
        card = f"""      <div class="metric-card">
        <div class="metric-label">{attr['name']}</div>
        <div class="metric-value">{attr['value_fmt']}</div>
      </div>"""
        metrics_cards_list.append(card)
    metrics_cards_html = "\n".join(metrics_cards_list)

    # Section des graphiques (Plots)
    plots_section_html = ""
    if plot_groups:
        plots_list = []
        for group in plot_groups:
            for plot in group["plots"]:
                title_suffix = f"  {plot['title']}" if plot.get("title") else ""
                img_tag = f'<img src="data:image/png;base64,{plot["b64"]}" alt="{plot.get("caption") or group["title"]}">'
                
                card = f"""        <div class="plot-card">
          <div class="plot-title">{group['title']}{title_suffix}</div>
          {img_tag}
        </div>"""
                plots_list.append(card)
        
        plots_joined = "\n".join(plots_list)
        plots_section_html = f"""  <!-- ── Plots ── -->
  <section class="section" id="plots">
    <div class="section-header">
      <div class="section-title">Plots</div>
    </div>
    <div class="plots-grid">
      {plots_joined}
    </div>
  </section>"""

    # Section Sample Summary
    sample_summary_section_html = ""
    if sample_summary_html:
        sample_summary_section_html = f"""  <!-- ── Sample Summary ── -->
  <section class="section" id="sample-summary">
    <div class="section-header">
      <div class="section-title">Sample Summary</div>
      <button class="btn btn-primary btn-copy" data-action="copy-table" data-table="tbl-sample-summary">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
          <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
        Copy TSV
      </button>
    </div>
    <div class="table-wrapper">
      {sample_summary_html}
    </div>
  </section>"""

    # Section Target Coverage
    target_cov_section_html = ""
    if target_cov_html:
        target_cov_section_html = f"""  <!-- ── Target Coverage ── -->
  <section class="section" id="target-coverage">
    <div class="section-header">
      <div class="section-title">Target Coverage by Sample</div>
      <button class="btn btn-primary btn-copy" data-action="copy-table" data-table="tbl-target-coverage">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
          <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
        Copy TSV
      </button>
    </div>
    <div class="table-wrapper">
      {target_cov_html}
    </div>
  </section>"""

    # --- Document f-string pur (Sans Jinja2 ni string.Template) ---
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TRGT Report  {run_name}</title>
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

  /* ── Nav ── */
  .nav {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 40px;
    display: flex;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }}
  .nav a {{
    display: block;
    padding: 10px 16px;
    font-size: 12px;
    font-weight: 500;
    color: var(--muted);
    text-decoration: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: color 0.15s, border-color 0.15s;
    letter-spacing: 0.4px;
    text-transform: uppercase;
  }}
  .nav a:hover {{ color: var(--text); }}
  .nav a.active {{ color: var(--accent); border-color: var(--accent); }}

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

  /* ── Metric cards ── */
  .metrics-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(185px, 1fr));
    gap: 12px;
  }}
  .metric-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px 20px;
    cursor: default;
    transition: box-shadow 0.15s, border-color 0.15s;
    position: relative;
    overflow: hidden;
  }}
  .metric-card::before {{
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: linear-gradient(180deg, #e8457a, #9e1f4f);
    border-radius: 6px 0 0 6px;
  }}
  .metric-card:hover {{
    border-color: #d9a0b4;
    box-shadow: 0 2px 8px rgba(200,51,106,0.10);
  }}
  .metric-label {{
    font-size: 10px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 6px;
  }}
  .metric-value {{
    font-family: var(--font-mono);
    font-size: 21px;
    font-weight: 500;
    color: var(--text);
    line-height: 1.2;
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
  tbody td:first-child {{
    color: var(--accent2);
    font-weight: 500;
    font-family: var(--font-sans);
    font-size: 12.5px;
  }}

  /* ── Plots ── */
  .plots-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(600px, 1fr));
    gap: 16px;
  }} 
  .plot-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }}
  .plot-title {{
    padding: 10px 16px;
    font-size: 11px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid var(--border);
    background: var(--surface2);
  }}
  .plot-card img {{ width: 100%; height: auto; display: block; }}
  .plot-missing {{
    padding: 40px;
    text-align: center;
    color: var(--muted);
    font-family: var(--font-mono);
    font-size: 12px;
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
</style>
</head>
<body>

<div class="header">
  <div class="header-brand">
    <div class="header-logo-mark"></div>
    <div class="header-titles">
      <h1>TRGT Global Viewer &mdash; Target Enrichment Report</h1>
      <div class="subtitle">{run_name}</div>
    </div>
  </div>
  <div class="header-meta">
    Généré le {generated_at}<br>
    {json_filename}<br>
    
    <!-- Bouton d'exportation en un clic (JS Local purement à la volée) -->
    <button class="btn btn-primary" onclick="downloadSelf()" style="margin-top: 8px;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
      </svg>
      Enregistrer le rapport
    </button>
  </div>
</div>

<nav class="nav">
  {nav_links_html}
</nav>

<main class="main">

  <!-- ── Run Metrics ── -->
  <section class="section" id="run-metrics">
    <div class="section-header">
      <div class="section-title">Run Metrics</div>
      <button class="btn btn-primary btn-copy" data-action="copy-metrics">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
          <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
        Copy TSV
      </button>
    </div>
    <div class="metrics-grid">
      {metrics_cards_html}
    </div>
  </section>

  {plots_section_html}

  {sample_summary_section_html}

  {target_cov_section_html}

</main>

<footer class="footer">
  <div class="footer-left">
    <div class="footer-dot"></div>
    <span>PacBio TRGT · pbcommand v{pbcommand_version}</span>
  </div>
  <span>{json_filename}</span>
</footer>

<script>
const METRICS_TSV = {metrics_tsv_json};

// Permet à l'utilisateur de sauvegarder localement son rapport généré à la volée
function downloadSelf() {{
  const htmlContent = "<!DOCTYPE html>\\n" + document.documentElement.outerHTML;
  const blob = new Blob([htmlContent], {{ type: 'text/html' }});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = "{run_name}_report.html";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}}

document.addEventListener('DOMContentLoaded', function() {{

  function flash(btn) {{
    btn.classList.add('copied');
    const orig = btn.innerHTML;
    btn.innerHTML = orig.replace('Copy TSV', 'Copié !');
    setTimeout(() => {{ btn.classList.remove('copied'); btn.innerHTML = orig; }}, 2000);
  }}

  function copyToClipboard(text) {{
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '-9999px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }}

  // Boutons copy
  document.querySelectorAll('.btn-copy').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      const action = btn.dataset.action;
      if (action === 'copy-metrics') {{
        copyToClipboard(METRICS_TSV);
        flash(btn);
      }} else if (action === 'copy-table') {{
        const table = document.getElementById(btn.dataset.table);
        if (!table) return;
        const tsv = Array.from(table.querySelectorAll('tr'))
          .map(row => Array.from(row.querySelectorAll('th, td')).map(c => c.textContent.trim()).join('\\t'))
          .join('\\n');
        copyToClipboard(tsv);
        flash(btn);
      }}
    }});
  }});

  // Nav active au scroll
  const sections = document.querySelectorAll('section[id]');
  const navLinks  = document.querySelectorAll('.nav a');
  const observer  = new IntersectionObserver(function(entries) {{
    entries.forEach(function(e) {{
      if (e.isIntersecting) {{
        navLinks.forEach(a => a.classList.remove('active'));
        const a = document.querySelector('.nav a[href="#' + e.target.id + '"]');
        if (a) a.classList.add('active');
      }}
    }});
  }}, {{ threshold: 0.3 }});
  sections.forEach(s => observer.observe(s));

}});
</script>

</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# Logique à la volée (Exactement comme votre save_and_open_html)
# ---------------------------------------------------------------------------

def open_report_on_the_fly(input_path: Path):
    """
    Génère le HTML à la volée, le stocke temporairement dans l'OS
    et l'ouvre dans le navigateur, sans polluer vos dossiers avec des fichiers.
    """
    try:
        input_path = Path(input_path)
        html_content = generate_report_html_string(input_path)
        reader = RunReader(input_path)
        run_name = reader.get_run_name()
        reader.close()
        
        # Exactement votre fonction de sauvegarde temporaire
        tmp_path = os.path.join(tempfile.gettempdir(), f"trgt_report_{run_name}.html")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        uri = Path(tmp_path).as_uri()
        webbrowser.open(uri)
    except Exception as e:
        import PySimpleGUI as sg
        sg.popup_error(f"Impossible d'ouvrir le rapport global :\n{e}")


# ---------------------------------------------------------------------------
# Main (Usage standard en console autonome)
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Rapport HTML PacBio TRGT")
    parser.add_argument("input_path", type=Path, help="Dossier du run ou fichier ZIP contenant les QC")
    args = parser.parse_args()

    input_path = args.input_path.resolve()
    
    # Génération et ouverture à la volée directe
    open_report_on_the_fly(input_path)


if __name__ == "__main__":
    main()