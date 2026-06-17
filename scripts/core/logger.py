import logging
import os
import sys
import tempfile
from datetime import datetime

__version__ = "1.0.0"

def setup_logging():
    """
    Configure le système de logging pour TGV.
    Crée un fichier de log 'tgv.YYYYMMDDHHMMSS.log' dans le dossier 'logs/'.
    Inspecte dynamiquement tous les modules importés dans le projet pour lister leurs versions s'ils en ont.
    """
    # Détection dynamique du mode DEBUG via la présence d'un fichier 'debug.txt'
    if getattr(sys, 'frozen', False):
        # Dossier de l'exécutable .exe une fois compilé
        app_dir = os.path.dirname(sys.executable)
    else:
        # Dossier de développement standard
        app_dir = os.getcwd()

    debug_trigger_file = os.path.join(app_dir, "debug.txt")
    if os.path.exists(debug_trigger_file):
        current_level = logging.DEBUG
        debug_activated_msg = "DEBUG MODE ACTIVATED (via debug.txt)"
    else:
        current_level = logging.INFO
        debug_activated_msg = "INFO MODE (Standard execution)"

    # 1. Génération du nom de fichier compact (Exemple : tgv.20260616102645.log)
    date_str = datetime.now().strftime("%Y%m%d%H%M%S")
    log_filename = f"tgv.{date_str}.log"
    log_dir = "logs"
    
    log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    handlers = []
    
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_filepath = os.path.join(log_dir, log_filename)
        file_handler = logging.FileHandler(log_filepath, mode='w', encoding='utf-8')
        handlers.append(file_handler)
        log_path_desc = os.path.abspath(log_filepath)
    except Exception:
        temp_log_dir = os.path.join(tempfile.gettempdir(), "tgv_logs")
        os.makedirs(temp_log_dir, exist_ok=True)
        log_filepath = os.path.join(temp_log_dir, log_filename)
        file_handler = logging.FileHandler(log_filepath, mode='w', encoding='utf-8')
        handlers.append(file_handler)
        log_path_desc = log_filepath

    if sys.stdout is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        handlers.append(console_handler)

    logging.basicConfig(
        level=current_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )

    logging.info("=========================================")
    logging.info(f"Starting TRGT Global Viewer (TGV) v{__version__}")
    logging.info(f"Python version: {sys.version.split()[0]}")
    logging.info(f"Platform: {sys.platform}")
    logging.info(f"Log file: {log_path_desc}")
    logging.info(f"Log level status: {debug_activated_msg}")
    logging.info("=========================================")
    
    # Liste exhaustive des modules importés
    project_imports = [
        "PySimpleGUI", "yaml", "sys", "os", "tempfile", "glob", "shutil", 
        "re", "traceback", "argparse", "base64", "json", "zipfile", "io", 
        "csv", "webbrowser", "datetime", "pathlib", "threading", "http.server", 
        "socketserver", "socket", "urllib.parse", "functools", "platform", 
        "getpass", "subprocess", "time"
    ]
    
    logging.info("Inventory of loaded modules and libraries:")
    for lib in sorted(project_imports):
        try:
            module = __import__(lib)
            version = getattr(module, "__version__", None)
            if not version:
                version = getattr(module, "version", None)
                
            if version:
                logging.info(f"  - {lib} (v{version})")
            else:
                logging.info(f"  - {lib}")
        except ImportError:
            logging.warning(f"  - {lib} (Not available)")
            
    logging.info("=========================================")