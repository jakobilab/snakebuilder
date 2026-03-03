#!/usr/bin/env python3
"""
CLI entrypoint for snakebuild.

Usage examples:
    snakebuild --steps processing detect
    snakebuild --steps @steps.txt
    snakebuild --config config.yaml --steps processing detect
    snakebuild --cloud --steps detect circtest
"""
import argparse
from pathlib import Path
from snakebuilder.builder.core import build_from_config
import os
import yaml
from pathlib import Path


# -----------------------------------------------------------
# Step alias definitions (meta-steps)
# -----------------------------------------------------------
STEP_ALIASES = {
    "processing": [
        "check_inputs",
        "decompress_inputs",
        "build_star_index",
        "star_align",
        "star_align_mate2",
        "star_align_mate1",
        "prep_circtools_finalize",
        "prep_circtools_sample"
    ],
    # Add more aliases here if you like
    # "qc": ["fastp"],
    # "alignment": ["build_star_index", "star_align"],
}


def expand_steps_argument(steps_arg):
    """
    Expand @file syntax AND alias/meta-step syntax.

    Examples:
        ["detect", "circtest"]
        ["@steps.txt"]
        ["processing", "detect"]
        ["detect", "@more_steps.txt"]
    """

    expanded = []

    for entry in steps_arg:

        # -------------------------------------------------------
        # Case 1 — Step list from file via @filename
        # -------------------------------------------------------
        if entry.startswith("@"):
            file_path = Path(entry[1:])
            if not file_path.exists():
                raise FileNotFoundError(f"Steps file not found: {file_path}")

            file_steps = [
                line.strip()
                for line in file_path.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            expanded.extend(file_steps)
            continue

        # -------------------------------------------------------
        # Case 2 — Alias/meta-step expansion
        # -------------------------------------------------------
        if entry in STEP_ALIASES:
            expanded.extend(STEP_ALIASES[entry])
            continue

        # -------------------------------------------------------
        # Case 3 — Regular step name
        # -------------------------------------------------------
        expanded.append(entry)

    return expanded


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Snakemake Snakefile (auto-generates config.yaml if none is provided)."
    )

    parser.add_argument(
        "--config",
        required=False,
        help="Path to config.yaml (optional — a placeholder config is generated if omitted)"
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        required=True,
        help="Workflow steps, @file list, or alias (e.g., 'processing')"
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path.cwd(),
        help="Output directory for Snakefile"
    )
    parser.add_argument(
        "--cloud",
        action="store_true",
        help="Use cloud_rules.json instead of core_rules.json"
    )
    parser.add_argument(
        "--species",
        required = False,
        choices=["hs", "mm", "gg", "dr", "rn"],
        help = "Species choice for bowtie and star indexes (mm, hs, gg, dr, rn)",
    )
    parser.add_argument(
        "--rename",
        action="store_true",
        help="Interactively rename samples and create symlinks"
    )


    args = parser.parse_args()
    
    

    # -----------------------------------------------------------
    # Expand @file syntax AND alias/meta-step syntax
    # -----------------------------------------------------------
    args.steps = expand_steps_argument(args.steps)

    # -----------------------------------------------------------
    # CONFIG HANDLING
    # -----------------------------------------------------------
    config_path = Path(args.config) if args.config else None

    snakefile_path = build_from_config(
        config_path=config_path,
        steps=args.steps,
        outdir=args.outdir,
        use_cloud=args.cloud,
        species = args.species,
        rename  =args.rename
    )

    print(f"✅ Snakefile successfully written to: {snakefile_path}")


if __name__ == "__main__":
    main()
