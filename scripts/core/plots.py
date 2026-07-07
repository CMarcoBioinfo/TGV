import os
import zipfile
import io
import webbrowser
import tempfile
import threading
import time
from pathlib import Path
import http.server
import socketserver
import subprocess
import logging


def get_available_plots(zip_path, sample_name, trid):
    """
    Retourne une liste de tuples (inner_zip, svg_file)
    pour un TRID donné dans un ZIP imbriqué TRGT/TRVZ.
    """

    if not zip_path or not os.path.exists(zip_path):
        return []

    results = []

    try:
        with zipfile.ZipFile(zip_path, "r") as outer:
            # Exemple : S18_motifs_allele.trvz_alleles.zip
            for name in outer.namelist():
                if name.startswith(sample_name) and name.endswith(".trvz_alleles.zip"):
                    # ZIP interne trouvé
                    with outer.open(name) as inner_file:
                        inner_bytes = inner_file.read()
                        with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
                            target = f"{trid}.trvz.svg"
                            if target in inner.namelist():
                                results.append((name, target))

    except Exception as e:
        logging.warning(f"Failed to read plots from archive '{zip_path}': {e}")

    return results



def open_svg(zip_path, inner_zip, svg_file, sample_name):
    logging.info(f"Extracting SVG plot '{svg_file}' from nested archive: '{inner_zip}'")
    try:
        # --- Extraction du SVG ---
        with zipfile.ZipFile(zip_path, "r") as outer:
            with outer.open(inner_zip) as inner_file:
                inner_bytes = inner_file.read()
                with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
                    svg_bytes = inner.read(svg_file)

        # --- Dossier temporaire parent ---
        # On définit le dossier racine du serveur sur le parent (.tmp_plots)
        base_tmp_dir = os.path.join(tempfile.gettempdir(), ".tmp_plots")
        sample_dir = os.path.join(base_tmp_dir, sample_name)
        os.makedirs(sample_dir, exist_ok=True)

        svg_tmp_path = os.path.join(sample_dir, svg_file)
        logging.debug(f"Writing temporary SVG plot file to: {svg_tmp_path}")

        with open(svg_tmp_path, "wb") as f:
            f.write(svg_bytes)

        # --- Serveur HTTP local sur le dossier parent ---
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                # On sert à partir de base_tmp_dir pour que {sample_name} soit accessible dans l'URL
                super().__init__(*args, directory=base_tmp_dir, **kwargs)

        logging.info("Starting local HTTP server for SVG plot (dynamic port)...")
        httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)

        port = httpd.server_address[1]
        logging.info(f"SVG local HTTP server successfully started on port: {port}")

        threading.Thread(target=httpd.serve_forever, daemon=True).start()

        # --- Ouvrir dans le navigateur par défaut ---
        # Cette URL est maintenant valide car le serveur cherche dans base_tmp_dir/{sample_name}/{svg_file}
        url = f"http://127.0.0.1:{port}/{sample_name}/{svg_file}"
        logging.info(f"Launching web browser for SVG visualization at: {url}")

        webbrowser.open(f"{url}?t={time.time()}")

    except Exception as e:
        logging.error(f"Failed to extract or serve SVG plot '{svg_file}': {e}", exc_info=True)