import os
import sys
import json
import shutil
import getpass
import platform
import logging

# Extraction de l'utilisateur et de la machine physique (ex: ui_settings_pmartin_PC-MANIP.json)
username = getpass.getuser()
hostname = platform.node()
CONFIG_FILE_NAME = f"ui_settings_{username}_{hostname}.json"


def get_safe_config_path(filename, folder="configs"):
    """
    Résout le chemin d'un fichier de configuration :
    1. Si l'externe (modifiable) n'existe pas, on y copie le fichier interne par défaut.
    2. On retourne le chemin externe pour permettre les modifications utilisateur.
    """
    # Répertoire contenant l'exécutable (ou le script)
    if getattr(sys, 'frozen', False):
        # Lancé depuis l'exécutable PyInstaller (.exe)
        exe_dir = os.path.dirname(sys.executable)
        bundle_dir = sys._MEIPASS  # Dossier interne temporaire de l'EXE
    else:
        # Lancé depuis le script Python standard (main.py)
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        bundle_dir = exe_dir

    # Chemin externe (modifiable à côté du .exe)
    external_dir = os.path.join(exe_dir, folder)
    external_path = os.path.join(external_dir, filename)

    # Chemin interne (intégré dans l'EXE)
    internal_path = os.path.join(bundle_dir, folder, filename)

    # Si le fichier externe n'existe pas, on copie la version par défaut interne vers l'externe
    if not os.path.exists(external_path) and os.path.exists(internal_path):
        try:
            os.makedirs(external_dir, exist_ok=True)
            shutil.copy(internal_path, external_path)
            logging.info(f"Recreated default thresholds file at external path: '{external_path}'")
        except Exception as e:
            logging.warning(f"Could not copy default thresholds file to {external_path}: {e}")
            return internal_path

    # On utilise le fichier externe s'il existe (pour que l'utilisateur puisse le modifier)
    if os.path.exists(external_path):
        return external_path

    return internal_path


def get_user_config_dir():
    """Détermine le répertoire utilisateur local adapté à l'OS."""
    if os.name == 'nt':
        base_dir = os.environ.get('APPDATA')
        if not base_dir:
            base_dir = os.path.expanduser('~')
    else:
        base_dir = os.environ.get('XDG_CONFIG_HOME')
        if not base_dir:
            base_dir = os.path.expanduser('~/.config')
            
    config_dir = os.path.join(base_dir, "tgv_viewer")
    
    try:
        os.makedirs(config_dir, exist_ok=True)
    except Exception:
        config_dir = os.path.expanduser('~/.tgv_viewer')
        os.makedirs(config_dir, exist_ok=True)
        
    return config_dir


def get_config_path():
    return os.path.join(get_user_config_dir(), CONFIG_FILE_NAME)


def load_ui_settings():
    """Charge les paramètres d'affichage."""
    path = get_config_path()
    logging.debug(f"Reading user UI settings file: '{os.path.abspath(path)}'")
    if not os.path.exists(path):
        logging.debug("No user UI settings file found on disk.")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logging.debug(f"Successfully loaded user UI settings: {data}")
            return data
    except Exception as e:
        logging.warning(f"Could not read user UI settings file from {path}: {e}")
        return {}


def save_ui_settings(settings):
    """Sauvegarde les paramètres d'affichage."""
    path = get_config_path()
    logging.debug(f"Writing user UI settings to file: '{os.path.abspath(path)}'")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
            logging.debug("Successfully saved user UI settings to disk.")
    except Exception as e:
        logging.warning(f"Could not write user UI settings file to {path}: {e}")