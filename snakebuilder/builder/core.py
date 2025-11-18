"""
Core builder logic for snakebuild.
Generates a Snakefile from a static config.yaml file.
"""

import yaml
from pathlib import Path
from snakebuilder.builder.snakefile_generator import generate_snakefile


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



def build_from_config(config_path, steps: list[str], outdir: Path, use_cloud: bool = False) -> Path:
    """
    Build a Snakemake Snakefile from a static YAML config.

    Args:
        config_path: Path to config.yaml OR None when running in cloud mode
        steps: List of step names (matching rules in the registry)
        outdir: Directory to write Snakefile and (optionally) copy config
        use_cloud: If True, config.yaml is optional and ignored at build time

    Returns:
        Path to the written Snakefile
    """

    # --------------------------------------------------------
    # 🟢 CLOUD MODE — config optional, no file loading required
    # --------------------------------------------------------
    if use_cloud:
        # Cloud mode never requires a config
        config = {}
    else:
        # Core mode
        if config_path is None:
            # No config provided — generate placeholder
            print(
                "⚠️  No config provided. "
                "Generating placeholder config.yaml. "
                "Make sure to replace the placeholder paths with your actual files!"
            )
            config = DEFAULT_PLACEHOLDER_CONFIG
        else:
            config_path = Path(config_path)

            if not config_path.exists():
                print(
                    "⚠️  Config file not found. "
                    "Generating placeholder config.yaml instead. "
                    "Make sure to replace the placeholder paths with your actual files!"
                )
                config = DEFAULT_PLACEHOLDER_CONFIG
            else:
                # Valid config → load normally
                with open(config_path) as f:
                    config = yaml.safe_load(f)
    # --------------------------------------------------------
    # Create output directory & generate Snakefile
    # --------------------------------------------------------
    outdir.mkdir(parents=True, exist_ok=True)

    snakefile_text = generate_snakefile(steps, use_cloud=use_cloud)
    snakefile_path = outdir / "Snakefile"
    snakefile_path.write_text(snakefile_text)

    # --------------------------------------------------------
    # Copy config.yaml only in CORE mode
    # --------------------------------------------------------
    # --------------------------------------------------------
    # Copy config.yaml only in CORE mode
    # --------------------------------------------------------
    if not use_cloud:
        out_config_path = outdir / "config.yaml"

        # Only compare paths if user actually provided a config file
        if config_path is not None and config_path.resolve() != out_config_path.resolve():
            out_config_path.write_text(yaml.safe_dump(config))
        elif config_path is None:
            # We generated a placeholder config
            out_config_path.write_text(yaml.safe_dump(config))


    return snakefile_path
