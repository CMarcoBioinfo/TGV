import zipfile
from scripts.core.vcf_loader import list_vcfs

def extract_trid_static_info(zip_path, vcf_filename):
    """
    Extrait chrom, start, end, motifs pour chaque TRID
    depuis le premier VCF du ZIP.
    """

    info_map = {}

    with zipfile.ZipFile(zip_path, "r") as z:
        with z.open(vcf_filename) as f:
            for raw in f:
                line = raw.decode("utf-8").strip()
                if line.startswith("#"):
                    continue

                cols = line.split("\t")
                chrom = cols[0]
                pos = int(cols[1])
                info_str = cols[7]

                # Parse INFO
                info = {}
                for item in info_str.split(";"):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        info[k] = v

                trid = info.get("TRID")
                if not trid:
                    continue

                motifs = info.get("MOTIFS", "")
                motifs = motifs.split(",") if motifs else []

                end = int(info.get("END", pos))

                info_map[trid] = {
                    "chrom": chrom,
                    "start": pos,
                    "end": end,
                    "motifs": motifs
                }

    return info_map


def make_readable_name(trid):
    """
    Convertit un TRID du type PREFIX_GENE en 'PREFIX (GENE)'.
    Exemple :
      FRDA_FXN → FRDA (FXN)
      SCA1_ATXN1 → SCA1 (ATXN1)
      HD_HTT → HD (HTT)
    """
    if "_" not in trid:
        return trid

    prefix, gene = trid.split("_", 1)
    return f"{prefix} ({gene})"


def autodetect_trids(zip_path):
    """
    Détecte les TRIDs et extrait leurs métadonnées en une seule passe de lecture.
    Retourne :
      - liste des TRIDs
      - TRID_TO_GENE (TRID → gène)
      - DISEASES (nom lisible → TRID)
      - STATIC_INFO (chrom, start, end, motifs)
    """
    # 1. On liste les VCFs
    vcfs = list_vcfs(zip_path)
    if not vcfs:
        print("[ERROR] Aucun VCF trouvé dans le ZIP")
        return [], {}, {}, {}

    first_vcf = vcfs[0]
    print(f"[INFO] Lecture unique du VCF de référence : {first_vcf}")

    # 2. On extrait l'intégralité des informations en une seule passe de lecture
    static_info = extract_trid_static_info(zip_path, first_vcf)

    # 3. La liste des TRIDs correspond simplement aux clés triées du dictionnaire d'informations
    trids = sorted(static_info.keys())
    print(f"[INFO] {len(trids)} TRIDs détectés")

    trid_to_gene = {}
    diseases = {}

    for trid in trids:
        if "_" in trid:
            prefix, gene = trid.split("_", 1)
        else:
            prefix = gene = trid

        trid_to_gene[trid] = gene
        diseases[make_readable_name(trid)] = trid

    return trids, trid_to_gene, diseases, static_info
