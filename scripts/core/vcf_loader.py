import zipfile
import os

def list_vcfs(zip_path):
    """Retourne la liste des fichiers VCF dans un ZIP."""
    print(f"[INFO] Lecture du ZIP : {zip_path}")

    if not os.path.exists(zip_path):
        print(f"[ERROR] ZIP introuvable : {zip_path}")
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
                        
                print(f"[INFO] {len(vcfs)} VCF réels trouvés dans le ZIP")
                return vcfs
    except Exception as e:
        print(f"[ERROR] Impossible d'ouvrir le ZIP : {e}")
        return []
