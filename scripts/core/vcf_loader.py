import zipfile
import os
import logging

def list_vcfs(zip_path):
    """Retourne la liste des fichiers VCF dans un ZIP."""
    logging.info(f"Reading VCF archive ZIP: {zip_path}")

    if not os.path.exists(zip_path):
        logging.error(f"ZIP archive not found: {zip_path}")
        return []

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
                vcfs = []
                for f in z.namelist():
                    if (
                        f.lower().endswith((".vcf", ".vcf.gz")) 
                        and "__MACOSX" not in f 
                        and not os.path.basename(f).startswith("._")
                    ):
                        vcfs.append(f)
                        
                logging.info(f"Found {len(vcfs)} valid VCF files inside ZIP archive.")
                return vcfs
    except Exception as e:
        logging.error(f"Failed to open ZIP archive: {e}")
        return []
