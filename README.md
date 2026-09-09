# snakebuild  
*A lightweight generator for Snakemake workflows*

`snakebuild` is a command-line tool that automatically generates a complete, ready-to-run **Snakemake workflow directory**.  
It supports both **local (core) workflows** and lightweight **cloud mode**, with automatic generation of configuration files and step lists.

---

# Features

- Generate a fully structured Snakemake `Snakefile`
- Automatically create `config.yaml` if none is provided  
  - Includes placeholder paths  
  - Warns user to update input files
- Supports **@file syntax** to load step lists:
  ```bash
  snakebuild --steps @steps.txt
  ```
- Supports cloud and core modes:
  - **Core mode** uses a config.yaml (auto-generated if needed)
  - **Cloud mode** does not require a config file
- Automatically creates the output directory
- Compatible with dynamic rule sets (core vs cloud rules)
- Clean CLI with clear error messages

---

#  Installation

```bash
pip install snakebuilder
```

Or from source:

```bash
git clone https://github.com/jakobilab/snakebuilder.git
cd snakebuilder
pip install -e .
```

---

# Usage

### Basic usage (auto-generates config.yaml):

```bash
snakebuild --steps processing detect --outdir ./myrun
```

This creates:

```
myrun/
    Snakefile
    config.yaml   (placeholder version)
```

---

## Using a config file

```bash
snakebuild --config config.yaml --steps processing detect --outdir run1
```

The config file is copied into the output directory, ensuring reproducibility.

---

## Using @file syntax for steps

Create a file:

`steps.txt`
```
# Preprocessing
 decompress_inputs 
 fastp 
 build_bowtie2_index 
 remove_rrna 
 build_star_index 
 star_align 
 prep_circtools 

 #run detection
 detect
```

Then run:

```bash
snakebuild --steps @steps.txt --outdir run_pipeline
```

You can mix syntax:

```bash
snakebuild --steps detect @extra_steps.txt circtest
```

---

# Cloud mode

Cloud mode ignores the local config and relies on cloud-based settings:

```bash
snakebuild --cloud --steps detect circtest
```

This is built for circtools.cloud wont work on CLI


---

# ⚠ Placeholder Config

If no config is provided, snakebuild generates a default `config.yaml` with clear placeholder values:

```
⚠  No config provided. Generating placeholder config.yaml.
   Make sure to replace the placeholder paths with your actual files!
```

This ensures the workflow remains self-contained while reminding the user to edit paths.

---

# Example: Full Pipeline

```bash
snakebuild     --steps @full_pipeline.txt     --outdir workflow_run --species mm
```

Where `full_pipeline.txt` contains:

```
check_inputs
fastp
build_bowtie2_index
remove_rrna
build_star_index
star_align
prep_circtools
detect
```

This will generate a circtools processing and detection pipeline for a given species using a generated config file that references genomes in BioDB.

```
snakemake --rerun-incomplete --snakefile ./Snakefile  --configfile ./config.yaml --cores 16 -p
```


This will generate a snakefile that cam be used to process genomic data and detect circular RNAs!

---
