# TGV — TRGT Global Viewer

<details open>
  <summary><b>🇫🇷 Version Française (Cliquez pour replier)</b></summary>
  <br>

**TGV (TRGT Global Viewer)** est une application Python dotée d'une interface graphique simple, conçue au CHU de Nîmes pour faciliter l'analyse, le contrôle qualité et l'interprétation clinique des résultats de génotypage de répétitions en tandem issus de la technologie PacBio [3].

---

### 🧬 Contexte Clinique & Vision "Zéro Désarchivage"

* **Le défi diagnostique** : L'analyse des expansions de répétitions en tandem (comme dans le cas des ataxies) repose sur le séquençage HiFi de haute précision à longues lectures (séquenceur **PacBio Vega**). Si l'outil TRGT offre un profilage génomique puissant, les données brutes générées sont denses, éparpillées et complexes à manipuler.
* **La vision "Zéro désarchivage manuel" (Ergonomie)** : Au quotidien, manipuler et décompresser manuellement des dizaines d'archives ZIP volumineuses (fichiers BAM de plusieurs centaines de mégaoctets, graphiques d'allèles ou de méthylation) est une tâche lourde. **TGV résout ce problème en lisant et en traitant toutes les données directement à la volée en arrière-plan, sans aucune décompression manuelle préalable sur le disque dur de l'utilisateur.**

---

### 📋 Caractéristiques principales

* **Interface graphique (GUI) intuitive** : Permet de charger vos données, de filtrer vos patients ou vos locus d'intérêt (TRIDs), et de modifier les seuils cliniques ou les génotypes directement à l'écran.
* **Cochage automatique par panel** : Intègre un système de boutons configurables permettant de sélectionner automatiquement en un clic des listes de gènes d'intérêt (panels in silico) définies par l'utilisateur.
* **Visualisation d'alignements (igv.js)** : Extrait automatiquement les reads d'intérêt (`spanning_BAM` et `repeat_reads`) et ouvre une session IGV locale directement dans votre navigateur web pour inspecter les alignements.
* **Affichage de graphiques TRGT (SVG)** : Détecte et affiche les graphiques d'allèles et de méthylation (générés par l'outil de dessin de TRGT) directement depuis l'interface de détails, sans décompression manuelle préalable.
* **Rapport de contrôle qualité global (QC)** : Génère à la volée une vue d'ensemble de la qualité d'enrichissement du run (graphiques et couverture des cibles) sous forme de rapport HTML consultable immédiatement, sans créer de fichier permanent sur votre disque de travail.
* **Traçabilité par fichier de logs** : À chaque lancement d'analyse, un fichier de log structuré et horodaté à la seconde près est enregistré dans le dossier `logs/`. Il contient les versions utilisées, les fichiers d'entrée, les étapes du pipeline et les éventuels avertissements de fichiers manquants.
* **Zéro empreinte disque** : Tous les fichiers de visualisation et rapports d'enrichissement sont créés de manière temporaire. À la fermeture de TGV, l'application exécute un nettoyage automatique garanti (bloc `finally` de l'application) qui supprime tous ces fichiers temporaires de votre disque dur [3].
* **Léger et portable** : Développé sans bibliothèque lourde (pas de Pandas, NumPy ou Jinja2). Il peut être partagé sous forme d'un exécutable unique sous Windows (sans installation), ou lancé comme un simple script Python sous Linux/macOS.

---

### 🚀 Comment l'utiliser (Usage)

L'outil **TGV** s'adaptant à votre environnement de travail, il peut être lancé de deux manières différentes :

#### Option A : Sous Windows (Exécutable autonome)
Destiné aux cliniciens et biologistes sur poste de travail Windows.
1. Téléchargez l'exécutable autonome **`TGV.exe`** depuis l'onglet *Releases* de ce dépôt GitHub.
2. Double-cliquez sur l'exécutable pour lancer l'application. 
*Aucune installation de Python ou de bibliothèque n'est requise.*

#### Option B : Sous Linux / macOS (Ligne de commande)
Destiné aux bio-informaticiens ou pour une utilisation sur serveur de calcul.

1. Installez les deux dépendances requises :
   ```bash
   pip install PySimpleGUI-4-foss pyyaml
   ```
2. Lancez l'application :
   ```bash
   python main.py
   ```

---

### 📂 Spécifications des Entrées (Inputs)

Pour fonctionner de manière transparente et sans désarchivage préalable, **TGV** s'appuie sur une structure d'archives standardisée **au niveau du Run** (les fichiers d'échantillons individuels sont stockés à l'intérieur d'archives globales du run) :

#### 1. Fichiers généraux de l'analyse (Sélection manuelle sur l'IHM)
* **Archive de VCFs TRGT (`{ID_RUN}-trgt_vcfs.zip`)** : L'archive ZIP contenant l'ensemble des fichiers `.trgt.vcf` du run (un fichier VCF par échantillon).
* **Génome de référence (Optionnel)** : Le fichier de référence génomique au format `.fa` ou `.fasta` accompagné de son fichier d'index `.fai` (ex : `hg38.fa` et `hg38.fa.fai`).

#### 2. Archives globales de Run détectées automatiquement (Sister ZIPs)
TGV détecte automatiquement les archives associées présentes dans le même répertoire, sous réserve qu'elles partagent exactement le même préfixe de run (`{ID_RUN}-`) :
* **Alignements (BAM)** :
  * `{ID_RUN}-spanning_BAM.zip` : Contient les fichiers BAM/BAI de type *spanning* pour tous les patients du run.
  * `{ID_RUN}-repeat_reads.zip` : Contient les fichiers BAM/BAI de type *mapped* pour tous les patients du run.
* **Graphiques TRGT (SVG)** :
  * `{ID_RUN}-trgt_motifs_allele.zip` : Archives des profils de tailles des motifs d'allèles de tous les patients.
  * `{ID_RUN}-trgt_motifs_waterfall.zip` : Archives des profils de reads *waterfall* de tous les patients.
  * `{ID_RUN}-trgt_meth_allele.zip` : Archives de méthylation allèle-spécifique de tous les patients.
  * `{ID_RUN}-trgt_meth_waterfall.zip` : Archives de profils de reads *waterfall* de méthylation de tous les patients.

*Fonctionnement interne : Lors de la sélection d'un patient et d'un locus, TGV ouvre l'archive globale du run correspondante en mémoire, y recherche le fichier spécifique du patient (par exemple `nom_patient.sorted.spanning.bam`), l'extrait de manière temporaire pour l'analyse, puis nettoie le disque à la fermeture [3].*

#### 3. Données de Run QC (Niveau Plaque — Rapport global d'enrichissement)
Pour afficher le rapport d'enrichissement global de run, l'utilisateur fournit l'archive d'analyse **`{id}-QC.zip`** contenant [3] :
* Le rapport d'enrichissement : `target_enrichment_puretarget.report.json`
* Le résumé des échantillons : `sample_summary.csv`
* La couverture par cible : `target_cov_by_sample.csv`
* Les graphiques PNG correspondants (ex: `sample_coverage_boxplot-0.png`, `read_categories.png`). *Les miniatures de type `*_thumb.png` sont ignorées.* [3]

---

### ⚙️ Configuration & Personnalisation

TGV est hautement configurable pour s'adapter aux besoins spécifiques de votre laboratoire de diagnostic grâce à deux fichiers de configuration au format YAML situés dans le répertoire **`configs/`** :

* **`clinical_thresholds.yaml`** (`configs/`) : Fichier de référence clinique. Il définit, pour chaque maladie/locus (TRID), les plages de tailles de répétitions permettant de classer les allèles (Sain, Prémutation, Pathogène) ainsi que l'orientation du brin (Directe ou Reverse-Complement).
* **`buttons_panel.yaml`** (`configs/`) : Permet de personnaliser dynamiquement les boutons de l'interface graphique. Vous pouvez y définir des panels (ex: "Ataxies", "Myopathies") et lister les TRIDs associés pour les cocher automatiquement d'un seul clic à l'écran.

---

### 🛠️ Organisation des fichiers de logs

Les fichiers de logs techniques sont sauvegardés automatiquement à côté de l'exécutable dans le sous-dossier `logs/`. Ils sont nommés sous la forme :  
`TGV_run_ANNEEMOISJOUR_HEUREMINUTESECONDE.log` (ex: `TGV_run_20260612_145002.log`).

</details>

<br>

<details>
  <summary><b>🇬🇧 English Version (Click to expand)</b></summary>
  <br>

**TGV (TRGT Global Viewer)** is a Python-based graphical user interface (GUI) designed at the Nîmes University Hospital (CHU de Nîmes) to facilitate the analysis, quality control, and clinical interpretation of tandem repeat genotyping results generated by the **TRGT** tool (PacBio) [3].

---

### 🧬 Clinical Context & "Zero Extraction" Philosophy

* **The diagnostic challenge**: Interpreting expansions of tandem repeats (such as in spinocerebellar ataxias) relies on high-precision long-read HiFi sequencing (using the **PacBio Vega** sequencer). While TRGT provides powerful genomic profiling, the raw outputs are dense, scattered, and complex to manipulate.
* **The "Zero manual extraction" philosophy (Ergonomics)**: Handling, unarchiving, and organizing dozens of heavy ZIP archives on a daily basis (such as BAM files of several hundred megabytes, allele plots, or methylation graphs) is tedious. **TGV solves this by processing and reading all data on-the-fly in the background, without requiring any manual unarchiving on the user's hard drive.**

---

### 📋 Main Features

* **Intuitive Graphical User Interface (GUI)**: Easily load data, filter patients or loci of interest (TRIDs), and adjust clinical thresholds or genotypes directly on screen.
* **Automated Panel Selection**: Features a customizable button panel to automatically select pre-defined lists of genes of interest (in silico panels) in a single click.
* **Alignment Visualization (igv.js)**: Automatically extracts reads of interest (`spanning_BAM` and `repeat_reads`) and launches a local IGV session directly in your web browser. A minimal HTTP server supporting *Range Requests* runs in the background to smoothly stream large BAM files.
* **TRGT Graphics Display (SVG)**: Detects and renders allele and methylation graphs (generated by the TRGT plotting tool) directly from the details panel, with no manual extraction required.
* **Global Run Quality Control (QC)**: Generates a comprehensive view of the run's enrichment quality (plots and target coverage) as an HTML report on-the-fly, without creating permanent files on your workspace.
* **Traceability and Logging**: A structured, second-precision log file is saved in the `logs/` directory for each analysis run. It records software versions, input files, pipeline execution steps, and warnings about missing optional files.
* **Zero Disk Footprint**: All visualization and QC report files are created temporarily. Upon closing TGV, an automated cleanup routine (via the application's `finally` block) cleans up all these temporary files from your hard drive [3].
* **Lightweight and Portable**: Developed without heavy libraries (no Pandas, NumPy, or Jinja2). It can be shared as a single executable on Windows (no installation needed), or run as a simple Python script on Linux/macOS.

---

### 🚀 How to use (Usage)

The **TGV** tool adapting to your work environment, it can be launched in two different ways:

#### Option A: On Windows (Standalone executable)
Aimed at clinicians and biologists on Windows workstations.
1. Download the standalone executable **`TGV.exe`** from the *Releases* tab of this GitHub repository.
2. Double-click the executable to launch the application. 
*No Python installation or library setup is required.*

#### Option B: On Linux / macOS (Command-line usage)
Aimed at bioinformaticians or server environment usage.

1. Install the two required lightweight dependencies:
   ```bash
   pip install PySimpleGUI-4-foss pyyaml
   ```
2. Launch the application:
   ```bash
   python main.py
   ```

---

### 📂 Input Specifications

To operate transparently without prior manual extraction, **TGV** relies on a standardized, **Run-level archive structure** (individual sample files are stored inside global run-level ZIP archives):

#### 1. General Files (Manual selection on the GUI)
* **TRGT VCF Archive (`{ID_RUN}-trgt_vcfs.zip`)**: The primary ZIP archive containing all the `.trgt.vcf` files of the run (one VCF file per sample).
* **Reference Genome (Optional)**: The reference genome file in `.fa` or `.fasta` format accompanied by its `.fai` index file (e.g., `hg38.fa` and `hg38.fa.fai`).

#### 2. Automatically Detected Run Archives (Sister ZIPs)
TGV automatically detects associated run archives present in the same directory, provided they share the exact same run prefix (`{ID_RUN}-`):
* **Alignment Files (BAM)**:
  * `{ID_RUN}-spanning_BAM.zip`: Contains the *spanning* BAM/BAI files for all patients in the run.
  * `{ID_RUN}-repeat_reads.zip`: Contains the *mapped* BAM/BAI files for all patients in the run.
* **TRGT Graphics (SVG)**:
  * `{ID_RUN}-trgt_motifs_allele.zip`: Contains the motif allele size profiles for all patients in the run.
  * `{ID_RUN}-trgt_motifs_waterfall.zip`: Contains the motif waterfall plots for all patients in the run.
  * `{ID_RUN}-trgt_meth_allele.zip`: Contains the allele-specific methylation profiles for all patients in the run.
  * `{ID_RUN}-trgt_meth_waterfall.zip`: Contains the methylation waterfall plots for all patients in the run.

*Internal behavior: When a patient and a locus are selected, TGV opens the corresponding global run archive in-memory, searches for the patient's specific file (e.g., `patient_name.sorted.spanning.bam`), extracts it temporarily for the analysis, and cleans up the disk on exit [3].*

#### 3. Run QC Data (Plate-level — Global Enrichment Report)
To display the global run enrichment report, the user provides the **`{id}-QC.zip`** analysis archive containing [3]:
* The enrichment report: `target_enrichment_puretarget.report.json`
* The sample summary: `sample_summary.csv`
* The target coverage: `target_cov_by_sample.csv`
* The corresponding PNG plots (e.g., `sample_coverage_boxplot-0.png`, `read_categories.png`). *Thumbnail images (`*_thumb.png`) are automatically ignored.* [3]

---

### ⚙️ Configuration & Customization

TGV is highly configurable to meet your diagnostic laboratory's specific needs through two YAML configuration files located in the **`configs/`** directory:

* **`clinical_thresholds.yaml`** (`configs/`): Clinical reference file. It defines, for each disease/locus (TRID), the repeat size ranges to classify alleles (Benign, Permutation, Pathogenic) and the motif strand orientation (Forward or Reverse-Complement).
* **`buttons_panel.yaml`** (`configs/`): Allows customizing the GUI by dynamically creating selection buttons. You can define custom panels (e.g., "Ataxias", "Myopathies") and list the associated TRIDs to check them automatically in a single click on screen.

---

### 🛠️ Logs Directory Organization

Technical log files are automatically saved next to the executable in the `logs/` subdirectory. They are named as follows:  
`TGV_run_YYYYMMDD_HHMMSS.log` (e.g., `TGV_run_20260612_145002.log`).

</details>

<br>

<details>
  <summary><b>💻 Déploiement & Compilation / Deployment & Compilation (Developer)</b></summary>
  <br>

Le projet utilise un workflow sur GitHub Actions pour compiler l'exécutable Windows. Ce processus est configuré pour être déclenché uniquement de manière manuelle depuis l'onglet **Actions** de GitHub.

The project uses a GitHub Actions workflow to compile the Windows executable. This process is configured to be triggered only manually from the **Actions** tab on GitHub.

### Pour compiler manuellement sous Windows / To compile manually on Windows :
```bash
pip install pyinstaller PySimpleGUI-4-foss pyyaml
pyinstaller --onefile --windowed main.py --hidden-import yaml --add-data "scripts/bio/motifs_data.yaml;scripts/bio" --add-data "configs;configs" --add-data "assets;assets"
```
L'exécutable `main.exe` sera généré dans le répertoire `dist/`. / The standalone `main.exe` executable will be generated in the `dist/` directory.

</details>

<br>

<details>
  <summary><b>📝 Licence & Auteurs / License & Authors</b></summary>
  <br>

* **Auteur principal / Main Author** : Corentin Marco (CHU de Nîmes)
* **Licence / License** : Ce projet est sous licence libre **Creative Commons Attribution - Pas d'Utilisation Commerciale 4.0 International** (CC BY-NC 4.0).

Pour plus de détails, veuillez vous référer aux termes de la licence Creative Commons en ligne. / For more details, please refer to the Creative Commons license terms online.

</details>
