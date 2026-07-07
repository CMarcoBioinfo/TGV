import os
import sys
import argparse
import shutil
import logging
import json5
import gzip
from datetime import datetime
import concurrent.futures
import subprocess
import zipfile
import glob

# Crée le dossier logs à la racine du script
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Crée un fichier de log horodaté
timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
log_file = os.path.join(LOG_DIR, f"tgv_input_builder.{timestamp}.log")


def setup_logging(log_file=None):
    log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[console_handler, file_handler]
    )


def log_file_only(message):
    logger = logging.getLogger()

    file_handler = None
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            file_handler = handler
            break

    if file_handler is None:
        logger.error("No FileHandler found in logger handlers.")
        return

    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn="",
        lno=0,
        msg=message,
        args=None,
        exc_info=None
    )

    file_handler.handle(record)


def check_fasta_index(fasta, samtools_exe="samtools"):
    fai = os.path.abspath(fasta) + ".fai"
    if not os.path.exists(fai):
        logging.error(f"FASTA index missing: {fai}")
        logging.error(f"Run: {samtools_exe} faidx {fasta}")
        sys.exit(1)


def check_file(file):
    if not os.path.exists(os.path.abspath(file)):
        logging.error(f"File not found: {file}")
        sys.exit(1)


def check_executable(exe, name):
    if os.path.exists(exe):
        return
    if shutil.which(exe) is None:
        logging.error(f"Executable not found: {exe}")
        logging.error(f"Ensure {name} is installed and available in PATH (or specify its path via the options).")
        sys.exit(1)


def check_indexed_file_exists(file_path, index_exts):
    """Vérifie si un fichier et au moins l'un de ses index associés existent et ne sont pas vides."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    for ext in index_exts:
        idx_path_1 = file_path + ext
        if os.path.exists(idx_path_1) and os.path.getsize(idx_path_1) > 0:
            return True
        if file_path.endswith(".bam") and ext == ".bai":
            idx_path_2 = file_path[:-4] + ".bai"
            if os.path.exists(idx_path_2) and os.path.getsize(idx_path_2) > 0:
                return True
    return False


def extract_repeat_ids(bed_path):
    """Parcourt le fichier BED et extrait de manière unique les IDs de la 4e colonne."""
    ids = []
    if not os.path.exists(bed_path):
        return ids
    with open(bed_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("track") or line.startswith("browser"):
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            col3 = parts[3]
            if "ID=" in col3:
                subparts = col3.split(";")
                found = False
                for sp in subparts:
                    if sp.startswith("ID="):
                        ids.append(sp.split("=")[1])
                        found = True
                        break
                if not found:
                    ids.append(col3)
            else:
                ids.append(col3)
    
    seen = set()
    unique_ids = []
    for r_id in ids:
        if r_id not in seen:
            seen.add(r_id)
            unique_ids.append(r_id)
    return unique_ids


def parse_list_samples(tsv_path, default_karyotype="XX"):
    """Lit le TSV (2 ou 3 colonnes) et associe à chaque patient son BAM et son caryotype."""
    samples = {}

    with open(tsv_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) < 2 or len(parts) > 3:
                logging.error(f"Invalid line in {tsv_path}: {line}")
                logging.error("Expected format: <sample_id> <tab> <bam_path> [<tab> <karyotype>]")
                continue

            sample_id = parts[0]
            bam_path = parts[1]
            
            karyotype = parts[2] if len(parts) == 3 else default_karyotype
            karyotype = karyotype.upper()
            if karyotype not in ["XX", "XY"]:
                if not os.path.exists(karyotype):
                    logging.warning(f"Invalid karyotype '{karyotype}' for sample '{sample_id}'. Defaulting to '{default_karyotype}'.")
                    karyotype = default_karyotype

            if not os.path.exists(bam_path):
                logging.warning(f"BAM not found for sample '{sample_id}': {bam_path}")
                logging.warning(f"Sample '{sample_id}' will be skipped.")
                continue

            samples[sample_id] = {
                "bam_path": bam_path,
                "karyotype": karyotype
            }

    logging.info(f"{len(samples)} valid samples loaded from {tsv_path}")
    return samples


# --- VALIDATEURS DE PARAMÈTRES TRGT ---

def validate_karyotype(val):
    normalized = val.upper()
    if normalized in ["XX", "XY"]:
        return True, normalized
    if os.path.exists(val):
        return True, val
    return False, "Must be 'XX', 'XY' or a valid path to a file."


def validate_preset(val):
    normalized = val.lower()
    if normalized in ["wgs", "targeted"]:
        return True, normalized
    return False, "Must be 'wgs' or 'targeted'."


def validate_color(val):
    normalized = val.lower()
    if normalized in ["always", "auto", "never"]:
        return True, normalized
    return False, "Must be 'always', 'auto' or 'never'."


def validate_genotyper(val):
    normalized = val.lower()
    if normalized in ["size", "cluster"]:
        return True, normalized
    return False, "Must be 'size' or 'cluster'."


def validate_int(val):
    try:
        ival = int(val)
        if ival >= 0:
            return True, ival
        return False, "Must be a non-negative integer."
    except ValueError:
        return False, "Must be a valid integer."


def validate_bool(val):
    normalized = str(val).lower().strip()
    if normalized in ["true", "yes", "y", "1"]:
        return True, True
    if normalized in ["false", "no", "n", "0"]:
        return True, False
    return False, "Must be a boolean (true/false or yes/no)."


def validate_plot_mode(val):
    normalized = str(val).lower().strip()
    if normalized in ["all", "meth", "allele", "waterfall", "motifs"]:
        return True, normalized
    return False, "Must be 'all', 'meth', 'allele', 'waterfall', or 'motifs'."


def validate_string(val):
    return True, str(val).strip()


# Association des paramètres de génotype à leurs validateurs
VALIDATORS = {
    "karyotype": validate_karyotype,
    "preset": validate_preset,
    "verbose": validate_int,
    "color": validate_color,
    "genotyper": validate_genotyper,
    "flank-len": validate_int,
    "max-depth": validate_int,
    "output-flank-len": validate_int,
}

PARAM_HELP = {
    "karyotype": "Possible values: 'XX', 'XY', or a valid path to a file.",
    "preset": "Possible values: 'wgs', 'targeted'.",
    "verbose": "Possible values:\n          0 = Standard mode (no -v)\n          1 = Verbose mode (-v)\n          2 = Very verbose mode (-vv)",
    "color": "Possible values: 'always', 'auto', 'never'.",
    "genotyper": "Possible values: 'size', 'cluster'.",
    "flank-len": "Possible values: Any positive integer (e.g., 250).",
    "max-depth": "Possible values: Any positive integer (e.g., 250).",
    "output-flank-len": "Possible values: Any positive integer (e.g., 50).",
}

# Association des paramètres de tracé à leurs validateurs
PLOT_VALIDATORS = {
    "plot_mode": validate_plot_mode,
    "verbose": validate_int,
    "squished": validate_bool,
    "font-family": validate_string,
    "color": validate_color,
    "flank-len": validate_int,
    "max-allele-reads": validate_int,
}

PLOT_PARAM_HELP = {
    "plot_mode": "Possible values: 'all', 'meth', 'allele', 'waterfall', 'motifs'.",
    "verbose": "Possible values:\n          0 = Standard mode (no -v)\n          1 = Verbose mode (-v)\n          2 = Very verbose mode (-vv)",
    "squished": "Possible values: 'true', 'false', 'yes', 'no'.",
    "font-family": "Possible values: Any font family name (e.g., 'Roboto Mono').",
    "color": "Possible values: 'always', 'auto', 'never'.",
    "flank-len": "Possible values: Any positive integer (e.g., 50).",
    "max-allele-reads": "Possible values: Any positive integer (e.g., 100).",
}


def ask_param_validated(key, current_val):
    """Saisie directe pour la génotypation. Conserve la valeur actuelle si vide, sinon valide l'entrée."""
    validator = VALIDATORS.get(key)
    if not validator:
        print(f"  {key} [{current_val}]: ", end="")
        new_val = input().strip()
        return new_val if new_val else current_val

    while True:
        print(f"  {key} [{current_val}]: ", end="")
        log_file_only(f"Prompt (genotype): {key} [{current_val}]")
        new_val = input().strip()
        log_file_only(f"User input (genotype): {new_val}")

        if not new_val:
            return current_val

        is_valid, validated_val = validator(new_val)
        if is_valid:
            log_file_only(f"Value accepted for {key}: {validated_val}")
            return validated_val

        print(f"  [ERROR] Invalid value: {validated_val}")
        print(f"  [HELP]  {PARAM_HELP.get(key, '')}\n")


def ask_plot_param_validated(key, current_val):
    """Saisie directe pour les tracés de graphiques. Conserve la valeur actuelle si vide, sinon valide l'entrée."""
    validator = PLOT_VALIDATORS.get(key)
    if not validator:
        print(f"  {key} [{current_val}]: ", end="")
        new_val = input().strip()
        return new_val if new_val else current_val

    while True:
        print(f"  {key} [{current_val}]: ", end="")
        log_file_only(f"Prompt (plot): {key} [{current_val}]")
        new_val = input().strip()
        log_file_only(f"User input (plot): {new_val}")

        if not new_val:
            return current_val

        is_valid, validated_val = validator(new_val)
        if is_valid:
            log_file_only(f"Value accepted for plot {key}: {validated_val}")
            return validated_val

        print(f"  [ERROR] Invalid value: {validated_val}")
        print(f"  [HELP]  {PLOT_PARAM_HELP.get(key, '')}\n")


def build_trgt_command(sample_id, bam_path, karyotype, threads_for_this_sample, args, trgt_params, output_root):
    sample_out = os.path.join(output_root, sample_id)
    os.makedirs(sample_out, exist_ok=True)

    output_prefix = os.path.join(sample_out, f"{sample_id}.trgt")

    cmd = [
        args.trgt,
        "genotype",
        "--genome", args.reference,
        "--reads", bam_path,
        "--repeats", args.bed,
        "--output-prefix", output_prefix,
        "--threads", str(threads_for_this_sample),
        "--karyotype", karyotype
    ]

    EXCLUDED_PARAMS = {"threads", "sample_name", "disable_bam_output", "karyotype"}

    for key, value in trgt_params.items():
        if key in EXCLUDED_PARAMS:
            continue
        if key == "verbose":
            if isinstance(value, int) and value > 0:
                cmd.append("-" + "v" * value)
            continue
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                cmd.append(f"--{key}")
            continue
        cmd.extend([f"--{key}", str(value)])

    log_file_only(f"TRGT command for {sample_id}: {' '.join(cmd)}")
    return cmd, sample_out


def run_plot_command(plot_cmd, sample_id, repeat_id, plot_type, show):
    """Exécute individuellement une commande de trgt plot et capture ses erreurs."""
    try:
        subprocess.run(plot_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except subprocess.CalledProcessError as e:
        log_file_only(
            f"Warning: Failed to generate {plot_type}/{show} plot for repeat ID '{repeat_id}' "
            f"(Sample: {sample_id}). Stderr: {e.stderr.strip()}"
        )


def get_plot_combinations(plot_mode="all"):
    """Filtre les tracés à réaliser à partir des combinaisons de base."""
    normalized = str(plot_mode).lower().strip()
    
    all_combos = [
        ("allele", "motifs"),
        ("allele", "meth"),
        ("waterfall", "motifs"),
        ("waterfall", "meth")
    ]
    
    if normalized == "all":
        return all_combos
    elif normalized == "meth":
        return [c for c in all_combos if c[1] == "meth"]
    elif normalized == "motifs":
        return [c for c in all_combos if c[1] == "motifs"]
    elif normalized == "allele":
        return [c for c in all_combos if c[0] == "allele"]
    elif normalized == "waterfall":
        return [c for c in all_combos if c[0] == "waterfall"]
    else:
        return all_combos


def create_sample_zip(directory, zip_path):
    """Crée une archive zip contenant tous les fichiers SVG du dossier donné (Fichiers textes -> ZIP_DEFLATED)."""
    svg_files = glob.glob(os.path.join(directory, "*.trvz.svg"))
    if not svg_files:
        return False
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in svg_files:
            zf.write(f, os.path.basename(f))
    return True


def create_global_aggregations(output_root, run_name, samples, skip_plots=False):
    """Crée les archives globales d'agrégation à la racine du dossier d'analyse (sans préfixe "analysis-")."""
    logging.info("Starting final global aggregations...")
    
    # 1. Agrégation des dossiers d'images compressés (SVGs benefit from ZIP_DEFLATED compression)
    if not skip_plots:
        categories = ["motifs_allele", "motifs_waterfall", "meth_allele", "meth_waterfall"]
        for cat in categories:
            zip_name = f"{run_name}-trgt_{cat}.zip"
            zip_path = os.path.join(output_root, zip_name)
            
            search_pattern = os.path.join(output_root, "*", f"*_{cat}.trvz_alleles.zip")
            sample_zips = glob.glob(search_pattern)
            
            if sample_zips:
                logging.info(f"Aggregating {len(sample_zips)} zip files into {zip_name}...")
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as main_zip:
                    for szip in sample_zips:
                        main_zip.write(szip, os.path.basename(szip))
            else:
                log_file_only(f"No sample-level zips found for category: {cat}")

    # 2. Agrégation globale des BAMs et BAIs triés (Déjà compressé -> ZIP_STORED pour vitesse maximale)
    bam_zip_name = f"{run_name}-spanning_BAM.zip"
    bam_zip_path = os.path.join(output_root, bam_zip_name)
    bams = glob.glob(os.path.join(output_root, "*", "*.trgt.spanning.sorted.bam"))
    bais = glob.glob(os.path.join(output_root, "*", "*.trgt.spanning.sorted.bam.bai"))
    alt_bais = glob.glob(os.path.join(output_root, "*", "*.trgt.spanning.sorted.bai"))
    all_bam_files = bams + bais + alt_bais
    
    if all_bam_files:
        logging.info(f"Aggregating {len(all_bam_files)} BAM/BAI files into {bam_zip_name} (Fast Copy mode)...")
        with zipfile.ZipFile(bam_zip_path, 'w', zipfile.ZIP_STORED) as bam_zip:
            for bfile in all_bam_files:
                bam_zip.write(bfile, os.path.basename(bfile))
    else:
        logging.warning("No spanning BAM/BAI files found for aggregation.")

    # 3. Agrégation globale des VCFs DECOMPRESSES (On lit le .gz et on l'écrit en .vcf brut à la volée dans le ZIP)
    vcf_zip_name = f"{run_name}-trgt_vcfs.zip"
    vcf_zip_path = os.path.join(output_root, vcf_zip_name)
    vcfs = glob.glob(os.path.join(output_root, "*", "*.trgt.sorted.vcf.gz"))
    
    if vcfs:
        logging.info(f"Decompressing and aggregating {len(vcfs)} VCF files into {vcf_zip_name}...")
        # On utilise ZIP_DEFLATED pour que l'archive finale soit compressée, mais les fichiers internes seront des .vcf décompressés
        with zipfile.ZipFile(vcf_zip_path, 'w', zipfile.ZIP_DEFLATED) as vcf_zip:
            for vgz_path in vcfs:
                base_name = os.path.basename(vgz_path)
                # On enlève le .gz pour avoir un fichier .vcf final
                vcf_name = base_name[:-3] if base_name.endswith(".gz") else base_name
                
                # Décompression à la volée vers l'archive ZIP sans surcharger la mémoire
                with gzip.open(vgz_path, 'rb') as f_in:
                    with vcf_zip.open(vcf_name, 'w') as f_out:
                        shutil.copyfileobj(f_in, f_out)
    else:
        logging.warning("No VCF files found for aggregation.")

    # 4. Agrégation globale des BAMs et BAIs d'entrée (Déjà compressé -> ZIP_STORED pour vitesse maximale)
    input_bam_zip_name = f"{run_name}-repeat_reads.zip"
    input_bam_zip_path = os.path.join(output_root, input_bam_zip_name)
    
    input_files_to_zip = []
    for sample_id, info in samples.items():
        bpath = info["bam_path"]
        if os.path.exists(bpath):
            input_files_to_zip.append(bpath)
            bai_1 = bpath + ".bai"
            bai_2 = bpath[:-4] + ".bai" if bpath.endswith(".bam") else None
            if os.path.exists(bai_1):
                input_files_to_zip.append(bai_1)
            elif bai_2 and os.path.exists(bai_2):
                input_files_to_zip.append(bai_2)

    if input_files_to_zip:
        logging.info(f"Aggregating {len(input_files_to_zip)} initial BAM/BAI files into {input_bam_zip_name} (Fast Copy mode)...")
        with zipfile.ZipFile(input_bam_zip_path, 'w', zipfile.ZIP_STORED) as ib_zip:
            for ffile in input_files_to_zip:
                ib_zip.write(ffile, os.path.basename(ffile))
    else:
        logging.warning("No initial BAM/BAI files found for repeat_reads aggregation.")


def run_trgt(sample_id, bam_path, karyotype, threads_for_this_sample, args, trgt_params, plot_params, output_root, repeat_ids):
    sample_out = os.path.join(output_root, sample_id)
    os.makedirs(sample_out, exist_ok=True)

    sorted_vcf = os.path.join(sample_out, f"{sample_id}.trgt.sorted.vcf.gz")
    sorted_bam = os.path.join(sample_out, f"{sample_id}.trgt.spanning.sorted.bam")

    # Établir la liste des fichiers ZIP de tracés attendus si les plots ne sont pas ignorés
    expected_zips = []
    if not args.skip_plots and repeat_ids:
        plot_mode = plot_params.get("plot_mode", "all")
        plot_combinations = get_plot_combinations(plot_mode)
        for ptype, show in plot_combinations:
            combo_key = f"{show}_{ptype}"
            zip_filename = f"{sample_id}_{combo_key}.trvz_alleles.zip"
            expected_zips.append(os.path.join(sample_out, zip_filename))

    # --- Étape de vérification pour reprise incrémentale (uniquement si les dossiers existent encore) ---
    vcf_ok = check_indexed_file_exists(sorted_vcf, [".tbi", ".csi"])
    bam_ok = check_indexed_file_exists(sorted_bam, [".bai"])
    plots_ok = all(os.path.exists(z) and os.path.getsize(z) > 0 for z in expected_zips)

    if vcf_ok and bam_ok and plots_ok:
        logging.info(f"Sample {sample_id} is already fully processed (VCF, BAM, and plots found). Skipping.")
        return sample_id

    logging.info(f"Starting sample: {sample_id} with {threads_for_this_sample} threads ({karyotype})")

    # --- VÉRIFICATION ET INDEXATION DU BAM D'ENTRÉE SI MANQUANT ---
    bai_path = bam_path + ".bai"
    alt_bai_path = bam_path[:-4] + ".bai" if bam_path.endswith(".bam") else None
    has_index = os.path.exists(bai_path) or (alt_bai_path and os.path.exists(alt_bai_path))
    
    if not has_index:
        logging.warning(f"Input BAM index (.bai) missing for sample {sample_id}. Indexing {bam_path} with {threads_for_this_sample} threads...")
        try:
            subprocess.run([args.samtools, "index", "-@", str(threads_for_this_sample), bam_path], check=True)
            logging.info(f"Successfully generated index for input BAM of sample {sample_id}.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to generate index for input BAM {bam_path} (exit code {e.returncode})")
            raise e

    # --- EXÉCUTION DE TRGT ---
    cmd, sample_out = build_trgt_command(sample_id, bam_path, karyotype, threads_for_this_sample, args, trgt_params, output_root)

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        logging.info(f"TRGT completed successfully for sample {sample_id}")
        
        if result.stderr:
            log_file_only(f"TRGT stderr output for {sample_id}:\n{result.stderr}")
                    
        raw_vcf = os.path.join(sample_out, f"{sample_id}.trgt.vcf.gz")
        raw_bam = os.path.join(sample_out, f"{sample_id}.trgt.spanning.bam")

        # --- Tri et indexation du VCF (bcftools) ---
        if os.path.exists(raw_vcf):
            logging.info(f"Sorting and indexing VCF for sample {sample_id}...")
            subprocess.run([
                args.bcftools, "sort", 
                "-Oz", "-o", sorted_vcf, raw_vcf
            ], check=True)
            subprocess.run([
                args.bcftools, "index", 
                "-t", sorted_vcf
            ], check=True)
            if not args.keep_temp:
                os.remove(raw_vcf)
        else:
            logging.error(f"Raw VCF missing for {sample_id}. Skipping VCF sorting.")

        # --- Tri et indexation du BAM (samtools multi-thread) ---
        if os.path.exists(raw_bam):
            logging.info(f"Sorting and indexing BAM for sample {sample_id} with {threads_for_this_sample} threads...")
            subprocess.run([
                args.samtools, "sort", 
                "-@", str(threads_for_this_sample), 
                "-o", sorted_bam, raw_bam
            ], check=True)
            subprocess.run([
                args.samtools, "index", 
                "-@", str(threads_for_this_sample), 
                sorted_bam
            ], check=True)
            if not args.keep_temp:
                os.remove(raw_bam)
        else:
            logging.error(f"Raw BAM missing for {sample_id}. Skipping BAM sorting.")

        # --- Génération parallélisée des graphiques TRGT (trgt plot) ---
        if not args.skip_plots and repeat_ids:
            plots_dir = os.path.join(sample_out, "plots")
            os.makedirs(plots_dir, exist_ok=True)
            logging.info(f"Generating TRGT plots in parallel for sample {sample_id} (using up to {threads_for_this_sample} threads)...")

            plot_mode = plot_params.get("plot_mode", "all")
            plot_combinations = get_plot_combinations(plot_mode)

            # Création des sous-dossiers temporaires spécifiques pour chaque catégorie de tracé
            combo_dirs = {}
            for ptype, show in plot_combinations:
                combo_key = f"{show}_{ptype}"
                combo_dir = os.path.join(sample_out, combo_key)
                os.makedirs(combo_dir, exist_ok=True)
                combo_dirs[combo_key] = combo_dir

            commands_to_run = []
            for repeat_id in repeat_ids:
                for ptype, show in plot_combinations:
                    combo_key = f"{show}_{ptype}"
                    combo_dir = combo_dirs[combo_key]

                    image_name = f"{repeat_id}.trvz.svg"
                    image_path = os.path.join(combo_dir, image_name)

                    plot_cmd = [
                        args.trgt, "plot",
                        "--genome", args.reference,
                        "--repeats", args.bed,
                        "--vcf", sorted_vcf,
                        "--spanning-reads", sorted_bam,
                        "--repeat-id", repeat_id,
                        "--plot-type", ptype,
                        "--show", show,
                        "--image", image_path
                    ]

                    verbose_val = plot_params.get("verbose", 0)
                    if isinstance(verbose_val, int) and verbose_val > 0:
                        plot_cmd.append("-" + "v" * verbose_val)

                    squished_val = plot_params.get("squished", False)
                    if isinstance(squished_val, str):
                        _, squished_val = validate_bool(squished_val)
                    if squished_val:
                        plot_cmd.append("--squished")
                    
                    if "font-family" in plot_params and plot_params["font-family"]:
                        plot_cmd.extend(["--font-family", str(plot_params["font-family"])])
                        
                    if "flank-len" in plot_params and plot_params["flank-len"] is not None:
                        plot_cmd.extend(["--flank-len", str(plot_params["flank-len"])])
                        
                    if "max-allele-reads" in plot_params and plot_params["max-allele-reads"] is not None:
                        plot_cmd.extend(["--max-allele-reads", str(plot_params["max-allele-reads"])])
                        
                    if "color" in plot_params and plot_params["color"]:
                        plot_cmd.extend(["--color", str(plot_params["color"])])

                    commands_to_run.append((plot_cmd, repeat_id, ptype, show))

            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, threads_for_this_sample)) as plot_executor:
                plot_futures = [
                    plot_executor.submit(run_plot_command, cmd, sample_id, rid, ptype, show)
                    for cmd, rid, ptype, show in commands_to_run
                ]
                concurrent.futures.wait(plot_futures)

            # --- ARCHIVAGE ET NETTOYAGE INDIVIDUEL ---
            for combo_key, combo_dir in combo_dirs.items():
                zip_filename = f"{sample_id}_{combo_key}.trvz_alleles.zip"
                zip_filepath = os.path.join(sample_out, zip_filename)
                
                logging.info(f"Zipping SVG files for category {combo_key} of sample {sample_id}...")
                zip_success = create_sample_zip(combo_dir, zip_filepath)
                
                if zip_success:
                    if not args.keep_temp:
                        try:
                            shutil.rmtree(combo_dir)
                            logging.info(f"Cleaned up raw SVGs directory: {combo_dir}")
                        except Exception as e:
                            logging.warning(f"Could not clean up directory {combo_dir}: {e}")
                else:
                    try:
                        shutil.rmtree(combo_dir)
                    except Exception:
                        pass
                    log_file_only(f"No SVG plots generated for category '{combo_key}' of sample {sample_id}. Zip skipped.")

            logging.info(f"Finished generating all plots for sample {sample_id}.")

    except subprocess.CalledProcessError as e:
        logging.error(f"TRGT or post-processing failed for sample {sample_id} (exit code {e.returncode})")
        logging.error(f"Error details:\n{e.stderr}")
        raise e
    except Exception as e:
        logging.error(f"Unexpected error running pipeline for {sample_id}: {e}")
        raise e

    return sample_id


def main():
    setup_logging(log_file)

    logging.info("========================================")
    logging.info("Starting TGV Inputs Builder v1.5.2 (Decompressed VCF ZIP Mode)")
    logging.info(f"Python version: {sys.version.split()[0]}")
    logging.info(f"Platform: {sys.platform}")
    logging.info(f"Log file: {os.path.abspath(log_file)}")
    logging.info("Log level status: INFO MODE (Standard execution)")

    parser = argparse.ArgumentParser(description="TGV Inputs Builder")

    parser.add_argument('--trgt', dest='trgt', default='trgt', help="Path to TRGT executable (default: trgt)")
    parser.add_argument('--samtools', dest='samtools', default='samtools', help="Path to samtools executable (default: samtools)")
    parser.add_argument('--bcftools', dest='bcftools', default='bcftools', help="Path to bcftools executable (default: bcftools)")
    parser.add_argument('--reference', '-r', dest='reference', required=True)
    parser.add_argument('--bed', '-b', dest='bed', required=True)
    parser.add_argument('--list_samples', '-l', dest='list_samples', required=True)
    parser.add_argument('--name', '-n', dest='run_name', required=True)
    parser.add_argument('--threads', '-t', dest='threads', default=1, type=int, help="Total available threads for the overall execution")
    parser.add_argument('--non-interactive', action='store_true', help='Disable interactive parameter modification')
    parser.add_argument('--keep-temp', action='store_true', help='Keep individual patient folders, raw unzipped SVGs, and unsorted BAMs/VCFs')
    parser.add_argument('--skip-plots', action='store_true', help='Skip generating tandem repeat visualization plots with trgt plot')

    args = parser.parse_args()

    logging.info("Checking input files and parameters...")

    check_executable(args.trgt, "TRGT")
    check_executable(args.samtools, "samtools")
    check_executable(args.bcftools, "bcftools")

    check_file(args.reference)
    check_file(args.bed)
    check_file(args.list_samples)
    check_fasta_index(args.reference, args.samtools)

    # 1. Chargement des configurations globales (Genotype et Plot) depuis JSON5
    params_file = os.path.join("configs", "trgt_params.json5")
    with open(params_file, "r") as f:
        config = json5.load(f)
        trgt_params = config.get("genotype", {})
        plot_params = config.get("plot", {})

    logging.info("TRGT parameters loaded from configs/trgt_params.json5.")

    if not args.non_interactive:
        # --- BLOC GÉNOTYPAGE ---
        print("\nCurrent TRGT genotype parameters:")
        for k, v in trgt_params.items():
            print(f"  {k}: {v}")
        
        print("\nDo you want to modify TRGT genotype parameters ? [y/N]: ", end="")
        log_file_only("Prompt: Do you want to modify TRGT genotype parameters ? [y/N]")
        custom_geno = input().strip().lower()
        log_file_only(f"User answer (genotype): {custom_geno}")

        if custom_geno == "y":
            print("\n--- Editing TRGT Genotype Parameters (Press Enter to keep current value) ---")
            for key, value in list(trgt_params.items()):
                trgt_params[key] = ask_param_validated(key, value)
            print()

        # --- BLOC GRAPHES (Optionnel) ---
        if not args.skip_plots:
            print("Current TRGT plot parameters:")
            for k, v in plot_params.items():
                print(f"  {k}: {v}")
            
            print("\nDo you want to modify TRGT plot parameters ? [y/N]: ", end="")
            log_file_only("Prompt: Do you want to modify TRGT plot parameters ? [y/N]")
            custom_plot = input().strip().lower()
            log_file_only(f"User answer (plot): {custom_plot}")

            if custom_plot == "y":
                print("\n--- Editing TRGT Plot Parameters (Press Enter to keep current value) ---")
                for key, value in list(plot_params.items()):
                    plot_params[key] = ask_plot_param_validated(key, value)
                print()
                
        print("\nNOTE:")
        print("  Any changes made here are temporary and apply only to this execution.")
        print("  To permanently change these values, edit configs/trgt_params.json5 directly.\n")
    else:
        print("\nNon-interactive mode enabled: using JSON5 parameters as-is.")
        logging.info("Non-interactive mode: JSON5 parameters used without modification.")

    # 2. Chargement de la liste des patients
    default_karyotype = trgt_params.get("karyotype", "XX")
    samples = parse_list_samples(args.list_samples, default_karyotype=default_karyotype)
    num_samples = len(samples)

    if num_samples == 0:
        logging.error("No valid samples to process. Exiting.")
        sys.exit(1)

    # 3. Extraction des Repeat IDs depuis le fichier BED
    repeat_ids = []
    if not args.skip_plots:
        repeat_ids = extract_repeat_ids(args.bed)
        num_repeats = len(repeat_ids)
        logging.info(f"Extracted {num_repeats} unique repeat IDs from BED file.")
        
        selected_mode = plot_params.get("plot_mode", "all")
        active_combos = get_plot_combinations(selected_mode)
        
        if num_repeats > 50:
            logging.warning(f"The BED file contains a high number of repeats ({num_repeats}).")
            logging.warning(f"Generating plots ('{selected_mode}' mode) will yield {num_repeats * len(active_combos)} files per sample.")
            logging.warning("This can take significant time and disk space.")
            logging.warning("Consider using '--skip-plots' if you want to bypass visualization.")

    logging.info("Preparing TRGT genotype execution for all samples...")

    output_root = os.path.join("output_" + args.run_name)
    os.makedirs(output_root, exist_ok=True)
    logging.info(f"Output directory created: {output_root}")

    # --- CALCUL INTELLIGENT DU PARALLÉLISME ---
    total_threads = max(1, args.threads)
    target_threads_per_job = 4
    
    max_parallel_jobs = max(1, min(num_samples, total_threads // target_threads_per_job))
    threads_per_job = max(1, total_threads // max_parallel_jobs)

    logging.info(f"Resource Scheduler Plan:")
    logging.info(f"  - Total thread budget: {total_threads}")
    logging.info(f"  - Parallel processes: {max_parallel_jobs}")
    logging.info(f"  - Threads per process: {threads_per_job}")
    logging.info(f"  - Combined thread load: {max_parallel_jobs * threads_per_job}")

    # --- SÉQUENCEUR PAR THREADPOOL ---
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel_jobs) as executor:
        futures = {
            executor.submit(
                run_trgt,
                sample_id,
                info["bam_path"],
                info["karyotype"],
                threads_per_job,
                args,
                trgt_params,
                plot_params,
                output_root,
                repeat_ids
            ): sample_id
            for sample_id, info in samples.items()
        }

        for future in concurrent.futures.as_completed(futures):
            sample_id = futures[future]
            try:
                finished_sample = future.result()
                logging.info(f"Finished processing sample: {finished_sample}")
            except Exception:
                logging.error(f"Execution failed for sample {sample_id}")

    # --- AGRÉGATION GLOBALE DES RÉSULTATS ---
    create_global_aggregations(output_root, args.run_name, samples, skip_plots=args.skip_plots)

    # --- NETTOYAGE DES DOSSIERS DE SAMPLES INDIVIDUELS ---
    # Si --keep-temp n'est PAS spécifié, on supprime proprement tous les dossiers de samples 
    # individuels pour ne garder QUE les fichiers .zip globaux comme seuls fichiers finaux.
    if not args.keep_temp:
        logging.info("Cleaning up individual sample directories to leave only global archives...")
        for sample_id in samples.keys():
            sample_dir = os.path.join(output_root, sample_id)
            if os.path.exists(sample_dir):
                try:
                    shutil.rmtree(sample_dir)
                    log_file_only(f"Removed individual sample directory: {sample_dir}")
                except Exception as e:
                    logging.warning(f"Could not remove directory {sample_dir}: {e}")
        logging.info("Individual sample directories cleanup completed successfully.")
    else:
        logging.info("Keeping individual sample directories (--keep-temp is active).")

    logging.info("TGV Inputs Builder completed successfully.")


if __name__ == "__main__":
    main()