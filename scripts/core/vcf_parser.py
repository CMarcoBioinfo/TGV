import zipfile

from scripts.models.trid import TRID
from scripts.models.sample import Sample
from scripts.models.allele import Allele, AlleleSequence

from scripts.core.sequence_utils import reverse_complement, rc_segmentation, convert_mc, convert_ms
from scripts.core.segmentation_interruptions import find_interruptions, extract_interruption_sequences, segmentation_complete


def parse_info(info_str):
    """Parse the INFO field of a VCF line."""
    info = {}
    for item in info_str.split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            info[key] = value
    return info


def split_two(value):
    """
    Sépare un champ 'x,y' en (x, y). 
    Convertit également les valeurs nulles VCF '.' en chaînes vides pour sécuriser le code.
    """
    if not value or value == ".":
        return "", ""
        
    parts = value.split(",")
    if len(parts) == 1:
        val = "" if parts[0] == "." else parts[0]
        return val, ""
        
    val1 = "" if parts[0] == "." else parts[0]
    val2 = "" if parts[1] == "." else parts[1]
    return val1, val2


def get_consensus_sequences(ref, alt, gt):
    """
    Retourne la séquence consensus des deux allèles selon GT.
    Supporte de manière robuste les cas d'haploïdie (mitochondrial, chromosome Y/X) 
    et les allèles non appelés (./. ou .).
    """    
    # Sécurité si le génotype global est absent
    if not gt or gt == ".":
        return "", ""

    # Détection dynamique du séparateur (VCF supporte '/' ou '|')
    separator = "/" if "/" in gt else "|" if "|" in gt else None
    
    if separator:
        parts = gt.split(separator)
        a1 = parts[0]
        a2 = parts[1] if len(parts) == 2 else "."
    else:
        # Cas haploïde (ex: "1") -> l'allèle 2 est considéré absent
        a1 = gt
        a2 = "."

    alt_list = [] if alt == "." else alt.split(",")

    def allele_seq(a):
        # Sécurité si l'allèle individuel est non-appelé ou vide
        if a in (None, "", "."):
            return ""
            
        try:
            idx = int(a)
        except ValueError:
            # Sécurité supplémentaire au cas où l'allèle contiendrait une valeur textuelle aberrante
            return ""

        # Allèle 0 = REF
        if idx == 0:
            seq = ref
        else:
            if not alt_list:
                seq = ref
            else:
                # Sécurité d'index si l'alternative déclarée dans le GT n'est pas présente dans ALT
                if idx - 1 < len(alt_list):
                    seq = alt_list[idx - 1]
                else:
                    seq = ref

        # TRGT : toujours une base de padding en tête → on l'enlève
        return seq[1:] if len(seq) > 1 else ""

    return allele_seq(a1), allele_seq(a2)


def parse_vcf_for_sample(zip_path, vcf_filename, global_trids):
    """
    global_trids : dict { trid_id: TRID } venant de run.trids
    Retourne : dict { trid_id: Sample }
    """
    samples = {}

    with zipfile.ZipFile(zip_path, "r") as z:
        with z.open(vcf_filename) as f:
            for raw in f:
                line = raw.decode("utf-8").strip()
                if line.startswith("#"):
                    continue

                cols = line.split("\t")
                chrom, pos, vid, ref, alt, qual, flt, info_str, fmt, sample_data = cols

                info = parse_info(info_str)
                trid_id = info.get("TRID")
                if not trid_id:
                    continue

                # On ne traite que les TRIDs connus globalement
                trid_global = global_trids.get(trid_id)
                if not trid_global:
                    continue

                # Création du Sample pour ce TRID
                if trid_id not in samples:
                    samples[trid_id] = Sample(name=vcf_filename)

                sample_obj = samples[trid_id]

                # -----------------------------
                # ORIENTATION CLINIQUE (FW / RC)
                # -----------------------------
                orientation = "fw"
                motifs = list(trid_global.motifs)  # copie

                if trid_global.clinical and trid_global.clinical.orientation:
                    if trid_global.clinical.orientation.lower() == "rc":
                        orientation = "rc"

                # -----------------------------
                # FORMAT → extraction TRGT
                # -----------------------------
                fmt_fields = fmt.split(":")
                sample_fields = sample_data.split(":")
                data = dict(zip(fmt_fields, sample_fields))

                gt = data.get("GT")
                cons1, cons2 = get_consensus_sequences(ref, alt, gt)

                al1, al2   = split_two(data.get("AL"))
                alr1, alr2 = split_two(data.get("ALLR"))
                sd1, sd2   = split_two(data.get("SD"))
                ap1, ap2   = split_two(data.get("AP"))
                am1, am2   = split_two(data.get("AM"))

                mc1_raw, mc2_raw = split_two(data.get("MC"))
                ms1_raw, ms2_raw = split_two(data.get("MS"))

                # -----------------------------
                # ORIENTATION RC → recalcul
                # -----------------------------
                if orientation == "rc":
                    motifs = [reverse_complement(m) for m in motifs]
                    cons1 = reverse_complement(cons1)
                    cons2 = reverse_complement(cons2)

                    motifs_str = ",".join(motifs)
                    ms1_raw = rc_segmentation(cons1, motifs_str)
                    ms2_raw = rc_segmentation(cons2, motifs_str)

                # -----------------------------
                # CONVERSION MC/MS
                # -----------------------------
                mc1 = convert_mc(motifs, mc1_raw)
                mc2 = convert_mc(motifs, mc2_raw)

                ms1 = convert_ms(motifs, ms1_raw)
                ms2 = convert_ms(motifs, ms2_raw)

                # -----------------------------
                # CONSTRUCTION DES ALLÈLES
                # -----------------------------
                allele1 = Allele(
                    size=al1,
                    size_range=alr1,
                    depth=sd1,
                    purity=ap1,
                    methylation=am1,
                    sequence=AlleleSequence(cons1, mc1, ms1)
                )

                interrupt_intervals_1 = find_interruptions(ms1)
                interrupt_seqs_1 = extract_interruption_sequences(cons1, interrupt_intervals_1)
                seg_complete_1 = segmentation_complete(ms1, interrupt_intervals_1, interrupt_seqs_1)

                allele1.sequence.interruptions = interrupt_seqs_1
                allele1.sequence.segmentation_complete = seg_complete_1

                allele2 = Allele(
                    size=al2,
                    size_range=alr2,
                    depth=sd2,
                    purity=ap2,
                    methylation=am2,
                    sequence=AlleleSequence(cons2, mc2, ms2)
                )

                interrupt_intervals_2 = find_interruptions(ms2)
                interrupt_seqs_2 = extract_interruption_sequences(cons2, interrupt_intervals_2)
                seg_complete_2 = segmentation_complete(ms2, interrupt_intervals_2, interrupt_seqs_2)

                allele2.sequence.interruptions = interrupt_seqs_2
                allele2.sequence.segmentation_complete = seg_complete_2

                sample_obj.allele1 = allele1
                sample_obj.allele2 = allele2

    return samples
