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


# -----------------------------------------------------------
# Step alias definitions (meta-steps)
# -----------------------------------------------------------
STEP_ALIASES = {
    "processing": [
        "decompress_inputs",
        "fastp",
        "build_bowtie2_index",
        "remove_rrna",
        "build_star_index",
        "star_align",
        "prep_circtools",
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
        use_cloud=args.cloud
    )

    print(f"✅ Snakefile successfully written to: {snakefile_path}")


if __name__ == "__main__":
    main()
