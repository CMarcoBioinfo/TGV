"""
make_report.py  Unified and clean HTML report for PacBio TRGT & TGV QC

Command-line usage:
    python make_report.py <run_folder_or_zip_archive>
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
import logging
from datetime import datetime
from pathlib import Path

from scripts.ui.igv import start_local_server, cleanup_tmpdir_force, CURRENT_TMPDIR

try:
    import PySimpleGUI as sg
except ImportError:
    sg = None


class RunReader:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.is_zip = zipfile.is_zipfile(path)
        self.zip_file = None
        if self.is_zip:
            self.zip_file = zipfile.ZipFile(path, "r")

    def get_run_name(self) -> str:
        name = self.path.stem
        if name.endswith("-QC"):
            return name[:-3]
        return name

    def list_files_info(self) -> list[tuple[str, int]]:
        info = []
        if self.is_zip:
            for zinfo in self.zip_file.infolist():
                if not zinfo.is_dir() and not zinfo.filename.startswith("__MACOSX"):
                    info.append((zinfo.filename, zinfo.file_size))
        else:
            for p in self.path.glob("**/*"):
                if p.is_file():
                    relative_path = p.relative_to(self.path)
                    info.append((str(relative_path), p.stat().st_size))
        return sorted(info)

    def list_json_candidates(self) -> list[str]:
        if self.is_zip:
            candidates = [
                n for n in self.zip_file.namelist()
                if n.endswith(".json") and not n.startswith("__MACOSX") and "task-report" not in n
            ]
        else:
            candidates = [
                p.name for p in self.path.glob("*.json")
                if "task-report" not in p.name
            ]
        candidates.sort(key=lambda x: 0 if "target_enrichment_report.json" in x else 1)
        return candidates

    def find_member(self, filename: str) -> str | None:
        if not self.is_zip:
            return None
        names = self.zip_file.namelist()
        if filename in names:
            return filename
        for n in names:
            if n.endswith("/" + filename) or n.endswith("\\" + filename):
                return n
        return None

    def find_file_by_suffix(self, suffix: str) -> str | None:
        if self.is_zip:
            for n in self.zip_file.namelist():
                if n.endswith(suffix) and not n.startswith("__MACOSX"):
                    return n
        else:
            for p in self.path.glob(f"*{suffix}"):
                return p.name
        return None

    def file_exists(self, filename: str) -> bool:
        if self.is_zip:
            return self.find_member(filename) is not None or self.find_file_by_suffix(filename) is not None
        else:
            return (self.path / filename).exists() or len(list(self.path.glob(f"*{filename}"))) > 0

    def read_json(self, name: str) -> dict:
        if self.is_zip:
            member = self.find_member(name) or name
            with self.zip_file.open(member) as f:
                return json.load(f)
        else:
            file_path = self.path / name
            if not file_path.exists():
                matched = list(self.path.glob(f"*{name}"))
                if matched:
                    file_path = matched[0]
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

    def read_csv(self, filename: str) -> list[list[str]]:
        content = ""
        if self.is_zip:
            member = self.find_member(filename) or self.find_file_by_suffix(filename)
            if not member:
                return []
            with self.zip_file.open(member) as f:
                content = f.read().decode("utf-8-sig", errors="ignore")
        else:
            file_path = self.path / filename
            if not file_path.exists():
                matched = list(self.path.glob(f"*{filename}"))
                if matched:
                    file_path = matched[0]
                else:
                    return []
            with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                content = f.read()

        if not content.strip():
            return []

        delimiter = ','
        comma_count = content.count(',')
        semi_count = content.count(';')
        tab_count = content.count('\t')

        if semi_count > comma_count and semi_count > tab_count:
            delimiter = ';'
        elif tab_count > comma_count and tab_count > semi_count:
            delimiter = '\t'

        lines = []
        reader_obj = csv.reader(io.StringIO(content), delimiter=delimiter)
        for row in reader_obj:
            lines.append(row)
        return lines

    def read_png_base64(self, filename: str) -> str | None:
        """Helper générique de lecture b64."""
        if self.is_zip:
            member = self.find_member(filename) or self.find_file_by_suffix(filename)
            if not member:
                return None
            with self.zip_file.open(member) as f:
                return base64.b64encode(f.read()).decode("ascii")
        else:
            file_path = self.path / filename
            if not file_path.exists():
                matched = list(self.path.glob(f"*{filename}"))
                if matched:
                    file_path = matched[0]
                else:
                    return None
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")

    def close(self):
        if self.zip_file:
            self.zip_file.close()


def fmt_attribute_value(value) -> str:
    if isinstance(value, int):
        return f"{value:,}".replace(",", "\u202f")
    return str(value)


def fmt_dp_per_allele(fl: dict) -> str:
    """
    Formate la profondeur par allèle d'un locus flagué, ex: '40/2'.
    Fallback sur l'ancien champ 'dp' (profondeur totale) si un rapport
    généré par une version antérieure du pipeline ne contient pas encore
    'dp_per_allele' (rétro-compatibilité de lecture).
    """
    dp_per_allele = fl.get("dp_per_allele")
    if dp_per_allele:
        return "/".join(str(v) for v in dp_per_allele)
    if "dp" in fl:
        return str(fl["dp"])
    return "N/A"


def df_to_html_table(table_data: dict, table_id: str) -> str:
    if not table_data or not table_data.get("headers"):
        return ""
    headers = "".join(f"<th>{col}</th>" for col in table_data["headers"])
    rows = []
    for row in table_data.get("rows", []):
        cells = "".join(f"<td>{v}</td>" for v in row)
        rows.append(f"<tr>{cells}</tr>")

    return (
        f'<table id="{table_id}">\n'
        f'<thead><tr>{headers}</tr></thead>\n'
        f'<tbody>\n' + "\n".join(rows) + '\n</tbody>\n'
        f'</table>'
    )


def generate_report_html_string(input_path: Path) -> str:
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Specified path not found: {input_path}")

    reader = RunReader(input_path)
    run_name = reader.get_run_name()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    print("\n" + "="*60)
    print("      AUTOMATIC CONFIGURATION FILES DIAGNOSTIC")
    print("="*60)
    print(f"Analyzing source: {input_path.name}")
    print("-" * 60)

    available_files = reader.list_files_info()
    for filename, size in available_files:
        status_str = f"{size:,} bytes".replace(",", " ")
        if size == 0:
            status_str = "EMPTY (0 bytes) [!!! WARNING !!!]"
        print(f"  - {filename:<45} : {status_str}")
    print("-" * 60)

    json_candidates = reader.list_json_candidates()
    if not json_candidates:
        reader.close()
        raise FileNotFoundError(f"No valid JSON file found in {input_path.name}")

    json_filename = json_candidates[0]
    data = reader.read_json(json_filename)

    attributes = []
    for attr in data.get("attributes", []):
        fmt = fmt_attribute_value(attr["value"])
        attributes.append({"name": attr["name"], "value_fmt": fmt})

    raw_attrs = data.get("attributes", [])
    metrics_tsv = (
        run_name
        + "\t"
        + "\t".join(str(a["value"]) for a in raw_attrs)
        + "\n"
    )
    metrics_tsv_json = json.dumps(metrics_tsv)

    comment = data.get("_comment") or ""
    pbcommand_version = "?"
    if "version" in comment:
        parts = comment.split("version")
        if len(parts) > 1:
            pbcommand_version = parts[1].strip().split()[0] or "?"

    interp_data = {}
    interp_file = reader.find_file_by_suffix("qc_interpretation.json")
    if interp_file:
        raw_interp = reader.read_json(interp_file)
        for s in raw_interp.get("samples", []):
            interp_data[s["sample_id"]] = s

    # Chargement des tracés de distribution vectoriels (SVG)
    sample_boxplot_b64 = None
    locus_boxplot_b64 = None

    sample_boxplot_file = reader.find_file_by_suffix("reads_per_sample_boxplot.svg")
    if sample_boxplot_file:
        sample_boxplot_b64 = reader.read_png_base64(sample_boxplot_file)

    locus_boxplot_file = reader.find_file_by_suffix("reads_per_locus_boxplot.svg")
    if locus_boxplot_file:
        locus_boxplot_b64 = reader.read_png_base64(locus_boxplot_file)

    # Chargement du heatmap de statut qualité vectoriel (SVG)
    quality_status_b64 = None
    quality_status_file = reader.find_file_by_suffix("genotyping_quality_status.svg")
    if quality_status_file:
        quality_status_b64 = reader.read_png_base64(quality_status_file)

    sample_summary_html = None

    if reader.file_exists("sample_summary.csv"):
        raw_lines = reader.read_csv("sample_summary.csv")
        if raw_lines and len(raw_lines) > 0:
            unified_headers = [
                "Sample ID", "Reads", "Length (bp)", "Quality", "Mean Cov",
                "PASS Loci %", "Flagged Loci", "≥10x %", "≥20x %", "≥30x %",
                "<5x %", "On-Target %", "Dup %"
            ]
            unified_rows = []

            for row in raw_lines[1:]:
                if not row:
                    continue
                sid = row[0]

                pct_pass = '<span class="text-muted"></span>'
                flagged_str = '<span class="text-success">0</span>'

                if sid != "Sample Average" and sid in interp_data:
                    s = interp_data[sid]
                    vcf_qc = s.get("vcf_qc", {})
                    pct_pass = f"{vcf_qc.get('pct_pass_loci', 0.0):.1f}%"

                    flagged_list = vcf_qc.get("flagged_loci", [])
                    flagged_count = len(flagged_list)
                    if flagged_count > 0:
                        flagged_str = f'<strong>{flagged_count}</strong>'

                reads = row[1] if len(row) > 1 else "N/A"
                length = row[2] if len(row) > 2 else "N/A"
                quality = row[3] if len(row) > 3 else "N/A"
                cov = row[4] if len(row) > 4 else "N/A"
                p10 = row[5] if len(row) > 5 else "N/A"
                p20 = row[6] if len(row) > 6 else "N/A"
                p30 = row[7] if len(row) > 7 else "N/A"
                p5 = row[8] if len(row) > 8 else "N/A"
                ontarget = row[9] if len(row) > 9 else "N/A"
                dup = row[10] if len(row) > 10 else "N/A"

                unified_rows.append([
                    sid, reads, length, quality, cov, pct_pass, flagged_str,
                    p10, p20, p30, p5, ontarget, dup
                ])

            table_data = {"headers": unified_headers, "rows": unified_rows}
            sample_summary_html = df_to_html_table(table_data, "tbl-sample-summary")

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
                        new_row.append(val_str)  # Affiche directement la chaîne "VCF (BAM)"
                    else:
                        new_row.append("N/A")
                new_rows.append(new_row)
            table_data = {"headers": new_headers, "rows": new_rows}
            target_cov_html = df_to_html_table(table_data, "tbl-target-coverage")

    reader.close()
    print("Analysis finished successfully.")
    print("="*60 + "\n")

    # --- REORGANISATION DE L'ORDRE DES ONGLETS DE NAVIGATION ---
    nav_links = ['<a href="#run-metrics" class="active">Run Metrics</a>']
    if sample_boxplot_b64 or locus_boxplot_b64:
        nav_links.append('<a href="#qc-plots">Distribution Plots</a>')
    if quality_status_b64:
        nav_links.append('<a href="#locus-qc-coverage">Locus Coverage Quality</a>')
    if sample_summary_html:
        nav_links.append('<a href="#sample-summary">Sample Summary</a>')
    if target_cov_html:
        nav_links.append('<a href="#target-coverage">Target Coverage</a>')

    nav_links_html = "\n  ".join(nav_links)

    metrics_cards_list = []
    for attr in attributes:
        card = f"""      <div class="metric-card">
        <div class="metric-label">{attr['name']}</div>
        <div class="metric-value">{attr['value_fmt']}</div>
      </div>"""
        metrics_cards_list.append(card)
    metrics_cards_html = "\n".join(metrics_cards_list)

    sample_summary_section_html = ""
    if sample_summary_html:
        sample_summary_section_html = f"""  <!-- ── 4. Sample Summary Dashboard (Collapsible & Open by default) ── -->
  <section class="section" id="sample-summary">
    <details class="qc-details-collapse" open>
      <summary>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
          <path d="M6 9l6 6 6-6"/>
        </svg>
        Sample Summary Dashboard
      </summary>
      <div style="padding: 20px; background: var(--surface);">
        <div class="section-header" style="border-bottom:none; margin-bottom:12px;">
          <div class="section-title">Metrics & Genotyping Quality</div>
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
      </div>
    </details>
  </section>"""

    clinical_interpretation_section_html = ""
    if quality_status_b64:
        clinical_interpretation_section_html = f"""  <!-- ── 3. Locus Coverage Quality Matrix (Collapsible, Open by default) ── -->
  <section class="section" id="locus-qc-coverage">
    <details class="qc-details-collapse" open>
      <summary>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
          <path d="M6 9l6 6 6-6"/>
        </svg>
        Locus Coverage Quality Matrix
      </summary>
      <div style="padding: 20px; background: var(--surface);">
        <div class="plots-grid">
          <div class="plot-card">
            <div class="plot-title">Locus Coverage Quality Matrix (Interactive Viewport)</div>
            <div class="plot-viewport">
              <div class="plot-controls">
                <button class="btn-zoom-out" title="Zoom Out">-</button>
                <span class="zoom-pct">100%</span>
                <button class="btn-zoom-in" title="Zoom In">+</button>
                <button class="btn-zoom-reset" title="Reset View">↺</button>
              </div>
              <img src="data:image/svg+xml;base64,{quality_status_b64}" alt="Locus Coverage Quality Matrix">
            </div>
          </div>
        </div>
      </div>
    </details>
  </section>"""

    qc_plots_section_html = ""
    if sample_boxplot_b64 or locus_boxplot_b64:
        plots_list = []
        if sample_boxplot_b64:
            plots_list.append(f"""        <div class="plot-card">
          <div class="plot-title">Read Count Distribution Per Sample (Interactive Viewport)</div>
          <div class="plot-viewport">
            <div class="plot-controls">
              <button class="btn-zoom-out" title="Zoom Out">-</button>
              <span class="zoom-pct">100%</span>
              <button class="btn-zoom-in" title="Zoom In">+</button>
              <button class="btn-zoom-reset" title="Reset View">↺</button>
            </div>
            <img src="data:image/svg+xml;base64,{sample_boxplot_b64}" alt="Read Count Distribution Per Sample">
          </div>
        </div>""")
        if locus_boxplot_b64:
            plots_list.append(f"""        <div class="plot-card">
          <div class="plot-title">Read Count Distribution Per Locus (Interactive Viewport)</div>
          <div class="plot-viewport">
            <div class="plot-controls">
              <button class="btn-zoom-out" title="Zoom Out">-</button>
              <span class="zoom-pct">100%</span>
              <button class="btn-zoom-in" title="Zoom In">+</button>
              <button class="btn-zoom-reset" title="Reset View">↺</button>
            </div>
            <img src="data:image/svg+xml;base64,{locus_boxplot_b64}" alt="Read Count Distribution Per Locus">
          </div>
        </div>""")
        plots_joined = "\n".join(plots_list)
        qc_plots_section_html = f"""  <!-- ── 2. QC Distribution Plots (Collapsible & Open by default) ── -->
  <section class="section" id="qc-plots">
    <details class="qc-details-collapse" open>
      <summary>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
          <path d="M6 9l6 6 6-6"/>
        </svg>
        QC Distribution Plots
      </summary>
      <div style="padding: 20px; background: var(--surface);">
        <div class="plots-grid">
          {plots_joined}
        </div>
      </div>
    </details>
  </section>"""

    target_cov_section_html = ""
    if target_cov_html:
        target_cov_section_html = f"""  <!-- ── 5. Target Coverage Matrix (Collapsible & Open by default) ── -->
  <section class="section" id="target-coverage">
    <details class="qc-details-collapse" open>
      <summary>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
          <path d="M6 9l6 6 6-6"/>
        </svg>
        Global Target Coverage Matrix
      </summary>
      <div style="padding: 20px; background: var(--surface);">
        <div class="section-header" style="border-bottom:none; margin-bottom:12px;">
          <!-- Description du double format unifié explicite -->
          <div class="section-title">Coverage per Sample & Locus (Transposed Matrix - Format: VCF depth per allele (BAM physical coverage))</div>
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
      </div>
    </details>
  </section>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TGV QC Report &mdash; {run_name}</title>
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
  .header-meta {{
    text-align: right;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--muted);
    line-height: 1.7;
  }}

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

  .badge {{
    display: inline-block;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
    border-radius: 12px;
    text-transform: uppercase;
    font-family: var(--font-sans);
  }}
  .badge-pass {{ background: #e6f4ea; color: #137333; }}
  .badge-warn {{ background: #fef7e0; color: #b06000; }}
  .badge-fail {{ background: #fce8e6; color: #c5221f; }}
  .badge-flag {{
    background: #f1f3f4;
    color: #3c4043;
    text-transform: none;
    font-family: var(--font-mono);
    font-size: 10px;
    border: 1px solid var(--border);
    margin: 1px;
  }}
  .flagged-details {{
    font-size: 11px;
    color: var(--text-dim);
    font-family: var(--font-mono);
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
  
  /* --- BLOCAGE DE LA PREMIÈRE COLONNE (STICKY) --- */
  .table-wrapper table th:first-child,
  .table-wrapper table td:first-child {{
    position: sticky;
    left: 0;
    z-index: 5;
    box-shadow: 2px 0 5px rgba(0, 0, 0, 0.08);
  }}

  .table-wrapper table th:first-child {{
    background: var(--surface2) !important;
    z-index: 10;
  }}

  .table-wrapper table td:first-child {{
    background: var(--surface) !important;
  }}

  .table-wrapper table tbody tr:hover td:first-child {{
    background: var(--surface2) !important;
  }}

  .qc-details-collapse {{
    margin-top: 15px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    overflow: hidden;
  }}
  .qc-details-collapse summary {{
    padding: 12px 20px;
    font-weight: 600;
    font-size: 11.5px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    cursor: pointer;
    background: var(--surface2);
    color: var(--accent2);
    list-style: none;
    display: flex;
    align-items: center;
    gap: 8px;
    user-select: none;
  }}
  .qc-details-collapse summary::-webkit-details-marker {{
    display: none;
  }}
  .qc-details-collapse[open] summary {{
    border-bottom: 1px solid var(--border);
  }}
  .qc-details-collapse[open] summary svg {{
    transform: rotate(180deg);
  }}
  .qc-details-collapse summary svg {{
    transition: transform 0.2s;
  }}
  .qc-details-content {{
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }}
  .flagged-sample-block {{
    border-left: 3px solid var(--accent);
    padding-left: 14px;
  }}
  .flagged-sample-block h5 {{
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 6px;
  }}
  .flagged-sample-block ul {{
    list-style-type: none;
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-family: var(--font-mono);
    font-size: 11.5px;
  }}

  .plots-grid {{
    display: flex;
    flex-direction: column;
    gap: 24px;
    max-width: 1100px;
    margin: 0 auto;
  }}
  .plot-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
    width: 100%;
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

  /* --- SYSTEME ZOOM DYNAMIQUE & PAN VECTORIEL --- */
  .plot-viewport {{
    position: relative;
    width: 100%;
    height: 750px; /* Zone d'observation confortable ajustée pour la grande heatmap */
    background: #ffffff;
    overflow: hidden;
    border-top: 1px solid var(--border);
    user-select: none;
  }}
  .plot-viewport img {{
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    object-fit: contain;
    transform-origin: center center;
    cursor: grab;
    transition: transform 0.1s ease-out;
  }}
  .plot-viewport img:active {{
    cursor: grabbing;
  }}

  .plot-controls {{
    position: absolute;
    top: 12px;
    right: 12px;
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    z-index: 100;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }}
  .plot-controls button {{
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    font-weight: bold;
    width: 28px;
    height: 28px;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    transition: all 0.15s;
    user-select: none;
  }}
  .plot-controls button:hover {{
    background: var(--accent);
    color: #ffffff;
    border-color: var(--accent);
  }}
  .plot-controls .zoom-pct {{
    font-family: var(--font-mono);
    font-size: 11.5px;
    font-weight: 600;
    color: var(--text-dim);
    min-width: 48px;
    text-align: center;
    user-select: none;
  }}

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
    Generated on {generated_at}<br>
    {json_filename}<br>

    <button class="btn btn-primary" onclick="downloadSelf()" style="margin-top: 8px;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
      </svg>
      Save Report
    </button>
  </div>
</div>

<nav class="nav">
  {nav_links_html}
</nav>

<main class="main">

  <!-- 1. Run Metrics Summary (Ouvert par défaut) -->
  <section class="section" id="run-metrics">
    <details class="qc-details-collapse" open>
      <summary>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
          <path d="M6 9l6 6 6-6"/>
        </svg>
        Run Metrics Summary
      </summary>
      <div style="padding: 20px; background: var(--surface);">
        <div class="section-header" style="border-bottom:none; margin-bottom:12px;">
          <div class="section-title">Global Attributes</div>
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
      </div>
    </details>
  </section>

  <!-- 2. QC Distribution Plots (Ouvert par défaut) -->
  {qc_plots_section_html}

  <!-- 3. Locus QC Filter & Coverage Matrix (Ouvert par défaut, vectoriel & épuré) -->
  {clinical_interpretation_section_html}

  <!-- 4. Sample Summary Dashboard (Ouvert par défaut) -->
  {sample_summary_section_html}

  <!-- 5. Target Coverage Matrix (Ouvert par défaut) -->
  {target_cov_section_html}

</main>

<footer class="footer">
  <div class="footer-left">
    <div class="footer-dot"></div>
    <span>TRGT Global Viewer &mdash; Target Enrichment Report</span>
  </div>
  <span>{json_filename}</span>
</footer>

<script>
const METRICS_TSV = {metrics_tsv_json};

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

  // --- LOGIQUE PAN & ZOOM DYNAMIQUE MULTI-INSTANCE (PURS SVG VECTORIELS) ---
  document.querySelectorAll('.plot-viewport').forEach(viewport => {{
    const img = viewport.querySelector('img');
    const btnIn = viewport.querySelector('.btn-zoom-in');
    const btnOut = viewport.querySelector('.btn-zoom-out');
    const btnReset = viewport.querySelector('.btn-zoom-reset');
    const pctDisplay = viewport.querySelector('.zoom-pct');

    let scale = 1.0;
    let panX = 0;
    let panY = 0;
    let isDragging = false;
    let startX = 0;
    let startY = 0;

    function applyTransforms() {{
      img.style.transform = `translate(${{panX}}px, ${{panY}}px) scale(${{scale}})`;
      pctDisplay.textContent = `${{Math.round(scale * 100)}}%`;
    }}

    // Zoom In (+)
    btnIn.addEventListener('click', function(e) {{
      e.stopPropagation();
      scale = Math.min(scale + 0.2, 8.0); // Élargissement max 800%
      applyTransforms();
    }});

    // Zoom Out (-)
    btnOut.addEventListener('click', function(e) {{
      e.stopPropagation();
      scale = Math.max(scale - 0.2, 0.4); // Réduction min 40%
      applyTransforms();
    }});

    // Reset (↺)
    btnReset.addEventListener('click', function(e) {{
      e.stopPropagation();
      scale = 1.0;
      panX = 0;
      panY = 0;
      applyTransforms();
    }});

    // Molette de souris pour zoomer de manière fluide
    viewport.addEventListener('wheel', function(e) {{
      e.preventDefault();
      const zoomStep = 0.08;
      if (e.deltaY < 0) {{
        scale = Math.min(scale + zoomStep, 8.0);
      }} else {{
        scale = Math.max(scale - zoomStep, 0.4);
      }}
      applyTransforms();
    }}, {{ passive: false }});

    // Pan / Drag à la souris (Clic gauche)
    viewport.addEventListener('mousedown', function(e) {{
      if (e.button !== 0) return; // Uniquement clic gauche
      isDragging = true;
      startX = e.clientX - panX;
      startY = e.clientY - panY;
      img.style.transition = 'none'; // Désactiver les animations pendant le glissement
    }});

    window.addEventListener('mousemove', function(e) {{
      if (!isDragging) return;
      panX = e.clientX - startX;
      panY = e.clientY - startY;
      applyTransforms();
    }});

    window.addEventListener('mouseup', function() {{
      if (isDragging) {{
        isDragging = false;
        img.style.transition = 'transform 0.1s ease-out';
      }}
    }});

    // Annuler si la souris sort du cadre
    viewport.addEventListener('mouseleave', function() {{
      if (isDragging) {{
        isDragging = false;
        img.style.transition = 'transform 0.1s ease-out';
      }}
    }});
  }});

  // --- LOGIQUE BOUTONS COPIER TSV (EXISTANTS) ---
  function flash(btn) {{
    btn.classList.add('copied');
    const orig = btn.innerHTML;
    btn.innerHTML = orig.replace('Copy TSV', 'Copied!');
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
  }}, {{ threshold: 0.2 }});
  sections.forEach(s => observer.observe(s));

}});
</script>

</body>
</html>
"""
    return html


def open_report_on_the_fly(input_path: Path):
    global CURRENT_TMPDIR
    try:
        input_path = Path(input_path)
        html_content = generate_report_html_string(input_path)
        reader = RunReader(input_path)
        run_name = reader.get_run_name()
        reader.close()

        # 1. Nettoyage de toute instance précédente (serveur + dossier)
        cleanup_tmpdir_force()

        # 2. Création d'un dossier temporaire dédié
        CURRENT_TMPDIR = tempfile.mkdtemp(prefix="tgv_report_")
        
        # 3. Écriture du fichier dans ce dossier
        tmp_path = os.path.join(CURRENT_TMPDIR, "index.html")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 4. Lancement du serveur sur ce dossier
        port = start_local_server(CURRENT_TMPDIR)
        
        # 5. Ouverture via HTTP (contourne les blocages Linux)
        url = f"http://127.0.0.1:{port}/index.html"
        logging.info(f"Launching web browser at report URL: {url}")
        webbrowser.open(url)
        
    except Exception as e:
        logging.error(f"Failed to generate and open QC enrichment report: {e}", exc_info=True)
        if sg:
            sg.popup_error(f"Impossible d'ouvrir le rapport global :\n{e}")
        else:
            print(f"\n[ERREUR] Impossible d'ouvrir le rapport global :\n{e}\n", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Rapport HTML PacBio TRGT & TGV QC")
    parser.add_argument("input_path", type=Path, help="Dossier du run ou fichier ZIP contenant les QC")
    args = parser.parse_args()

    input_path = args.input_path.resolve()
    open_report_on_the_fly(input_path)


if __name__ == "__main__":
    main()