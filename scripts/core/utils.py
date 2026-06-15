import os

def get_analysis_prefix(zip_path):
    """
    Retourne un identifiant de run basé sur le nom du ZIP.
    Ex : /path/to/RUN_2025_05_21.zip → RUN_2025_05_21
    """
    base = os.path.basename(zip_path)
    prefix = base.replace(".zip", "")
    return prefix