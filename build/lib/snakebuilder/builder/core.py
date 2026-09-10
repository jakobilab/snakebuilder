"""
Core builder logic for snakebuild.
Generates a Snakefile from a static config.yaml file.
"""

import yaml
from pathlib import Path
from snakebuilder.builder.snakefile_generator import generate_snakefile
import re
import os
import json

from pathlib import Path

FASTQ_PATTERN = re.compile(r"(.*?)(_R[12])\.fastq\.gz$")

def detect_samples_from_fastqs(search_dir: Path = Path("."), rename: bool = False):
    """Scan directory for paired FASTQ.gz files and return sample dict."""
    files = list(search_dir.glob("*.fastq.gz"))
    samples = {}

    for f in files:
        m = FASTQ_PATTERN.match(f.name)
        if not m:
            continue

        base, read = m.group(1), m.group(2)
        samples.setdefault(base, {})

        if read == "_R1":
            samples[base]["fastq1"] = str(f)
        elif read == "_R2":
            samples[base]["fastq2"] = str(f)

    # prune incomplete samples
    samples = {
        s: v for s, v in samples.items()
        if "fastq1" in v and "fastq2" in v
    }

    # -------------------------------
    # If rename is OFF → return as before
    # -------------------------------
    if not rename:
        return samples, {}

    # -------------------------------
    # RENAME MODE
    # -------------------------------
    print("\n🔄 Rename mode enabled. Showing detected FASTQ pairs:\n")

    new_samples = {}
    old_samples = {}

    for old_name, paths in samples.items():
        print(f"Found sample: {old_name}")
        print(f"  R1: {paths['fastq1']}")
        print(f"  R2: {paths['fastq2']}")

        new_name = input(f"📝 New name for sample '{old_name}' (or press Enter to keep original): ").strip()

        if not new_name:
            new_name = old_name  # no change

        # store old filenames
        old_samples[new_name] = {
            "fastq1": paths["fastq1"],
            "fastq2": paths["fastq2"]
        }

        # new symlink names
        new_r1 = f"{new_name}_R1.fastq.gz"
        new_r2 = f"{new_name}_R2.fastq.gz"

        # create symlinks
        Path(new_r1).unlink(missing_ok=True)
        Path(new_r2).unlink(missing_ok=True)

        Path(new_r1).symlink_to(Path(paths["fastq1"]).resolve())
        Path(new_r2).symlink_to(Path(paths["fastq2"]).resolve())

        new_samples[new_name] = {
            "fastq1": new_r1,
            "fastq2": new_r2,
        }

        print(f"➡️  Symlinked to: {new_r1}, {new_r2}\n")

    return new_samples, old_samples


# Legacy hardcoded defaults — kept as a fallback for hosts/species that
# aren't (yet) registered in the app's genome catalog below.
SPECIES_DB = {
    "hs": {
        "name": "homo_sapiens",
        "base": "/biodb/genomes/homo_sapiens/GRCh38_107",
        "fasta": "GRCh38_107.fa",
        "gtf": "GRCh38.107.chr_patch_hapl_scaff.gtf",
        "star": "star",
        "bowtie2": "bowtie2",
        "hisat2": "hisat2"
    },
    "mm": {
        "name": "mus_musculus",
        "base": "/biodb/genomes/mus_musculus/GRCm39_107",
        "fasta": "GRCm39_107.fa",
        "gtf": "GRCm39.107.gtf",
        "star": "star",
        "bowtie2": "bowtie2/GRCm39_107",
        "hisat2": "hisat2"
    },
    "dr": {
        "name": "danio_rerio",
        "base": "/biodb/genomes/danio_rerio/GRCz11_107",
        "fasta": "GRCz11_107.fa",
        "gtf": "GRCz11.107.gtf",
        "star": "star",
        "bowtie2": "bowtie2",
        "hisat2": "hisat2"
    },
    "gg": {
        "name": "gallus_gallus",
        "base": "/biodb/genomes/gallus_gallus/placeholder",
        "fasta": "genome.fa",
        "gtf": "annotation.gtf",
        "star": "star",
        "bowtie2": "bowtie2",
        "hisat2": "hisat2"
    },
    "rn": {
        "name": "rattus_norvegicus",
        "base": "/biodb/genomes/rattus_norvegicus/mRatBN7_2_110",
        "fasta": "mRatBN7_2_110.fa",
        "gtf": "mRatBN7.2.110.gtf",
        "star": "star",
        "bowtie2": "bowtie2",
        "hisat2": "hisat2"
    }
}

# Each entry under this root looks like:
#   <genomes_root>/<id>/genome.fa
#   <genomes_root>/<id>/annotation.gtf
#   <genomes_root>/<id>/metadata.json
#   <genomes_root>/<id>/index/{star_index, bowtie2_index, bwa_index.*, hisat2_index.*}
# Indices are pre-built and already carry their own *.done markers, so pointing
# star_index_path / bowtie2_index_path here means build_star_index /
# build_bowtie2_index just no-op (same as the existing bwa/hisat2 rules do).
GENOME_CATALOG_ROOT = Path(os.environ.get("CIRCTOOLS_GENOMES_DIR", "/app/data/genomes"))

# Species shorthand (as used by SPECIES_DB / --species) -> the string to match
# against a catalog entry's metadata.json ("name", "common_name", "taxon_id",
# or any of its "aliases").
SPECIES_CATALOG_QUERY = {
    "hs": "homo_sapiens",
    "mm": "mus_musculus",
    "dr": "danio_rerio",
    "gg": "gallus_gallus",
    "rn": "rattus_norvegicus",
}


def find_genome_in_catalog(query: str, catalog_root: Path = GENOME_CATALOG_ROOT) -> dict | None:
    """
    Look up a genome under the app's real genome catalog (metadata.json per
    directory) rather than the legacy hardcoded SPECIES_DB paths.

    Matches `query` (case-insensitive) against each entry's name, common_name,
    taxon_id, or aliases list. Returns resolved paths, or None if the catalog
    root doesn't exist or nothing matches (caller should fall back to SPECIES_DB).
    """
    if not catalog_root.exists():
        return None

    q = query.strip().lower()

    for genome_dir in sorted(p for p in catalog_root.iterdir() if p.is_dir()):
        meta_path = genome_dir / "metadata.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except Exception as e:
            print(f"⚠ Skipping {meta_path}: unreadable metadata.json ({e})")
            continue

        candidates = {
            str(meta.get("name", "")).lower(),
            str(meta.get("common_name", "")).lower(),
            str(meta.get("taxon_id", "")).lower(),
        }
        candidates |= {str(a).lower() for a in meta.get("aliases", [])}

        if q in candidates:
            index_dir = genome_dir / "index"
            return {
                "genome_id": genome_dir.name,
                "display_name": meta.get("display_name", meta.get("name", genome_dir.name)),
                "fasta": str(genome_dir / "genome.fa"),
                "gtf": str(genome_dir / "annotation.gtf"),
                "star_index_path": str(index_dir / "star_index"),
                "bowtie2_index_path": str(index_dir / "bowtie2_index"),
                "hisat2_index_path": str(index_dir / "hisat2_index"),
            }

    return None


def apply_species_defaults(config, species_key):
    # ensure input section exists
    config.setdefault("inputs", {})

    catalog_query = SPECIES_CATALOG_QUERY.get(species_key, species_key)
    catalog_hit = find_genome_in_catalog(catalog_query)

    if catalog_hit:
        print(
            f"🧬 Found '{species_key}' in genome catalog "
            f"(id={catalog_hit['genome_id']}, {catalog_hit['display_name']}). "
            f"Using pre-built indices from {GENOME_CATALOG_ROOT}."
        )
        fasta_path = Path(catalog_hit["fasta"])
        gtf_path = Path(catalog_hit["gtf"])
        config["inputs"].update({
            "fasta": catalog_hit["fasta"],
            "gtf": catalog_hit["gtf"],
            "star_index_path": catalog_hit["star_index_path"],
            "bowtie2_index_path": catalog_hit["bowtie2_index_path"],
            "hisat2_index_path": catalog_hit["hisat2_index_path"],
        })
    else:
        if species_key not in SPECIES_DB:
            raise ValueError(
                f"Species '{species_key}' not found in genome catalog "
                f"({GENOME_CATALOG_ROOT}) and no legacy default is registered for it."
            )
        print(
            f"⚠ Genome catalog lookup failed for '{species_key}' "
            f"(root={GENOME_CATALOG_ROOT}) — falling back to legacy /biodb path."
        )
        sp = SPECIES_DB[species_key]
        base = Path(sp["base"])
        fasta_path = base / sp["fasta"]
        gtf_path = base / sp["gtf"]
        config["inputs"].update({
            "fasta": str(fasta_path),
            "gtf": str(gtf_path),
            "star_index_path": str(base / sp["star"]),
            "bowtie2_index_path": str(base / sp["bowtie2"]),
            "hisat2_index_path": str(base / sp["hisat2"]),
        })

    # NOTE: no rrna_index_prefix key needed — remove_rrna aligns against the
    # same bowtie2_index_path index built by build_bowtie2_index (confirmed
    # against the real pipeline: params.index_prefix is derived directly as
    # f"{config['bowtie2_index_path']}/reference_index", not a separate config
    # value). There is no dedicated rRNA reference in the genome catalog.

    # default compute settings
    config.setdefault("memory", 16000)
    config.setdefault("threads", 8)
    config.setdefault("run_dir", "run_output")

    # auto-detect samples
    detected = detect_samples_from_fastqs(Path("."))
    if detected:
        config["samples"] = detected
    else:
        config.setdefault("samples", {
            "sample1": {
                "fastq1": "REPLACE_ME_sample1_R1.fastq.gz",
                "fastq2": "REPLACE_ME_sample1_R2.fastq.gz"
            }
        })

    # detect block
    config["detect"] = {
        "Nr1": 2,
        "Nr2": 2,
        "fasta": str(fasta_path),
        "gtf": str(gtf_path)
    }

    return config




DEFAULT_PLACEHOLDER_CONFIG = {
    "threads": 8,
    "memory": 16000,
    "run_dir": "run_output",

    # All placeholder paths — user *must* change these
    "inputs": {
        "fasta_gz": "REPLACE_ME_genome.fa.gz",
        "gtf_gz": "REPLACE_ME_annotation.gtf.gz",
        "fasta": "REPLACE_ME_genome.fa",
        "gtf": "REPLACE_ME_annotation.gtf",
        "bowtie2_index_path": "REPLACE_ME_bowtie2_index",
        "star_index_path": "REPLACE_ME_star_index",
    },

    "samples": {
        "sample1": {
            "fastq1": "REPLACE_ME_sample1_R1.fastq.gz",
            "fastq2": "REPLACE_ME_sample1_R2.fastq.gz",
        }
    },

    "detect": {
        "gtf": "REPLACE_ME_annotation.gtf",
        "fasta": "REPLACE_ME_genome.fa",
        "Nr1": 2,
        "Nr2": 2,
    }
}


def build_from_config(
    config_path,
    steps: list[str],
    outdir: Path,
    use_cloud: bool = False,
    species: str | None = None,
    rename: bool = False
) -> Path:

    """
    Build a Snakemake Snakefile from a YAML config and/or species auto-fill.
    """

    # --------------------------------------------------------
    # CLOUD MODE — config optional
    # --------------------------------------------------------
    if use_cloud:
        config = {}

    else:
        # --------------------------------------------------------
        # CASE A: CONFIG PROVIDED → LOAD AND DO NOTHING ELSE
        # --------------------------------------------------------
        if config_path is not None:
            cp = Path(config_path)

            if not cp.exists():
                raise FileNotFoundError(f"Provided config file not found: {config_path}")

            print(f"📄 Using provided config file: {config_path}")
            print("🔒 Skipping species defaults, auto-detection, and rename.")

            with open(cp) as f:
                config = yaml.safe_load(f)

            # Force rename OFF when user supplies config
            rename = False

        # --------------------------------------------------------
        # CASE B: NO CONFIG PROVIDED → USE SPECIES DEFAULTS
        # --------------------------------------------------------
        else:
            if species is None:
                print(
                    "⚠️ No species selected. "
                    "Generating placeholder config.yaml. "
                    "Replace placeholders with real paths."
                )
                config = DEFAULT_PLACEHOLDER_CONFIG

            else:
                print(f"🧬 Species '{species}' selected. Applying defaults...")
                config = apply_species_defaults({}, species)

            # --------------------------------------------------------
            # Auto-detect FASTQs and optional rename
            # --------------------------------------------------------
            print("\n🔍 Detecting FASTQ files...")

            detected_samples, old_names = detect_samples_from_fastqs(
                Path("."), rename=rename
            )

            if not detected_samples:
                print("❌ ERROR: No FASTQ pairs detected.")
                print("   Expected: SAMPLE_R1.fastq.gz and SAMPLE_R2.fastq.gz")
                raise SystemExit(1)

            print(f"✔ Found {len(detected_samples)} samples")

            config["samples"] = detected_samples

            if rename:
                config["old_samples"] = old_names
                print("✔ Added original sample names under 'old_samples'")

    # --------------------------------------------------------
    # Write Snakefile
    # --------------------------------------------------------
    outdir.mkdir(parents=True, exist_ok=True)

    snakefile_text = generate_snakefile(steps, use_cloud=use_cloud)
    snakefile_path = outdir / "Snakefile"
    snakefile_path.write_text(snakefile_text)

    # --------------------------------------------------------
    # Write config.yaml only when NOT cloud mode
    # --------------------------------------------------------
    if not use_cloud:
        if config_path is None:
            # Only write new config when we generated it
            out_config_path = outdir / "config.yaml"
            out_config_path.write_text(yaml.safe_dump(config, sort_keys=False))
            print(f"✔ config.yaml written: {out_config_path}")
        else:
            print("ℹ Using existing config — not writing new config.yaml")

    return snakefile_path