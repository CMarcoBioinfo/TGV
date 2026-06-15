import sys
import traceback
import os
import tempfile
import glob
from scripts.ui.main_window import run_main_window

import ctypes
import sys

def open_console():
    # Ouvre une console Windows
    ctypes.windll.kernel32.AllocConsole()
    # Redirige stdout et stderr vers la console
    sys.stdout = open("CONOUT$", "w")
    sys.stderr = open("CONOUT$", "w")

open_console()

def cleanup_temp_files():
    """
    Identifie et supprime les fichiers temporaires générés par l'application
    en ciblant leurs noms actuels dans le répertoire temp.
    """
    temp_dir = tempfile.gettempdir()
    
    # 1. Suppression du fichier d'export de tableau (trgt_table.html)
    table_path = os.path.join(temp_dir, "trgt_table.html")
    if os.path.exists(table_path):
        try:
            os.remove(table_path)
        except Exception:
            pass
            
    # 2. Suppression de tous les rapports de run (trgt_report_*.html)
    report_pattern = os.path.join(temp_dir, "trgt_report_*.html")
    for p in glob.glob(report_pattern):
        try:
            os.remove(p)
        except Exception:
            pass
            
    # 3. Arrêt du serveur et suppression du dossier IGV (via votre fonction existante)
    try:
        from scripts.ui.igv import cleanup_tmpdir_force
        cleanup_tmpdir_force()
    except Exception:
        pass


def main():
    try:
        run_main_window()
    except Exception as e:
        # En cas de crash avant ou pendant l'affichage de l'IHM,
        # on écrit l'erreur dans un fichier de log local.
        with open("crash_report.txt", "w", encoding="utf-8") as f:
            f.write("Une erreur critique est survenue au démarrage de l'application :\n\n")
            traceback.print_exc(file=f)
        sys.exit(1)
    finally:
        # Exécuté systématiquement à la fermeture pour nettoyer vos fichiers actuels
        cleanup_temp_files()


if __name__ == "__main__":
    main()
