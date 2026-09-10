"""
Loads and formats Snakemake rule templates from JSON.
"""

import json
import textwrap
from pathlib import Path
import re

RULESET = "core"
_RULES_OVERRIDE_PATH: Path | None = None  # set via select_ruleset(rules_path=...)


# ----------------------------------------------------------
# Select active ruleset ("core" or "cloud")
# ----------------------------------------------------------
def select_ruleset(mode: str, rules_path: str | Path | None = None):
    global RULESET, _RULES_OVERRIDE_PATH
    if mode not in ("core", "cloud"):
        raise ValueError(f"Invalid ruleset: {mode}")
    RULESET = mode
    _RULES_OVERRIDE_PATH = Path(rules_path) if rules_path else None


# ----------------------------------------------------------
# Load rule definitions from the appropriate file
# ----------------------------------------------------------
def load_rules() -> dict:
    # Use override path if set (e.g. by HPC agent pointing to repo copy)
    if _RULES_OVERRIDE_PATH is not None:
        path = _RULES_OVERRIDE_PATH
    else:
        filename = "cloud_rules.json" if RULESET == "cloud" else "core_rules.json"
        path = Path(__file__).parent / filename

    if not path.exists():
        raise FileNotFoundError(f"Rule registry not found: {path}")

    with open(path) as f:
        return json.load(f)

# ----------------------------------------------------------
# Safely format rule values for Snakemake
# ----------------------------------------------------------
def _format_value(v: str) -> str:
    v = v.strip()

    # unwrap JSON quotes
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        inner = v[1:-1]
    else:
        inner = v

    # expressions that should NOT be quoted
    if (
        inner.startswith("lambda ") or
        inner.startswith("config") or
        inner.startswith("rules.") or
        inner.startswith("os.path") or
        inner.startswith("expand(") or
        inner.startswith("Path(") or
        inner.startswith("str(") or
        inner.startswith("touch(") or
        inner.startswith("wildcards.") or
        inner.startswith("PRIMER_CONFIG") or
        inner.startswith("DETECT_CONFIG") or
        inner.startswith("PADLOCK_CONFIG") or
        inner.startswith("CONSERVATION_CONFIG")
    ):
        return inner

    # handle join expressions like " ".join(...)
    if ".join(" in inner:
        return inner

    # foo.get(...)
    if re.match(r"[A-Za-z_][A-Za-z0-9_]*\s*\.\s*get\s*\(", inner):
        return inner

    # any other bare function call, e.g. _bowtie2_prefix(...), some_helper(...)
    if re.match(r"[A-Za-z_][A-Za-z0-9_]*\s*\(", inner):
        return inner

    # f-strings
    if inner.startswith("f'") or inner.startswith('f"'):
        return inner

    # literal → auto-quote
    return f'"{inner}"'





# ----------------------------------------------------------
# Escape AWK blocks safely
# ----------------------------------------------------------
def _escape_awk_braces(text: str) -> str:
    """
    Escape braces ONLY inside AWK single-quoted code: awk '...'.
    This avoids interfering with Snakemake placeholders {output}, {threads}.
    """

    def repl(match):
        awk = match.group(1)
        awk = awk.replace("{", "{{").replace("}", "}}")
        return f"awk '{awk}'"

    return re.sub(r"awk '([^']*)'", repl, text)



# ----------------------------------------------------------
# Render JSON → Snakemake rule block
# ----------------------------------------------------------
def get_rule(name: str) -> str:
    """
    Convert JSON rule → Snakemake rule block.
    Handles:
      - if <condition>: wrapping
      - indentation and layout
      - AWK escaping
      - params, input, output, resources
      - run/shell/python blocks
    """

    rules = load_rules()
    if name not in rules:
        raise KeyError(f"Rule '{name}' not found in registry.")

    rule = rules[name]
    lines = []

    # ----------------------------------------------------------
    # Optional condition wrapper
    # ----------------------------------------------------------
    condition = rule.get("condition")
    if condition:
        lines.append(condition)   # emit verbatim — colon and variable assignment already in the string
        lines.append("")

        base_indent = " " * 4
    else:
        base_indent = ""

    indent1 = base_indent + " " * 4
    indent2 = indent1 + " " * 4

    # ----------------------------------------------------------
    # Rule header
    # ----------------------------------------------------------
    lines.append(f"{base_indent}rule {rule['name']}:")

    # -------------------- input --------------------
    inputs = rule.get("input", {})
    if inputs:
        lines.append(f"{indent1}input:")
        for k, v in inputs.items():
            lines.append(f"{indent2}{k} = {_format_value(v)},")
        lines[-1] = lines[-1].rstrip(",")

    # -------------------- output --------------------
    outputs = rule.get("output", {})
    if outputs:
        lines.append(f"{indent1}output:")
        for k, v in outputs.items():
            lines.append(f"{indent2}{k} = {_format_value(v)},")
        lines[-1] = lines[-1].rstrip(",")

    # -------------------- params --------------------
    params = rule.get("params", {})
    if params:
        lines.append(f"{indent1}params:")
        for k, v in params.items():
            lines.append(f"{indent2}{k} = {_format_value(v)},")
        lines[-1] = lines[-1].rstrip(",")

    # -------------------- threads --------------------
    if "threads" in rule:
        lines.append(f"{indent1}threads: {rule['threads']}")

    # -------------------- resources --------------------
    resources = rule.get("resources", {})
    if resources:
        lines.append(f"{indent1}resources:")
        for k, v in resources.items():
            lines.append(f"{indent2}{k} = {v},")
        lines[-1] = lines[-1].rstrip(",")

    # ==========================================================
    # Action block (Python → run → shell)
    # ==========================================================
    python_code = rule.get("python")
    run_code = rule.get("run")
    shell_code = rule.get("shell")

    # python block
    if python_code:
        lines.append(f"{indent1}run:")
        for line in textwrap.dedent(python_code).rstrip().split("\n"):
            lines.append(f"{indent2}{line}")
        return "\n".join(lines)

    # python+shell hybrid (run:)
    if run_code:
        run_text = _escape_awk_braces(textwrap.dedent(run_code).rstrip())
        lines.append(f"{indent1}run:")
        for line in run_text.split("\n"):
            lines.append(f"{indent2}{line}")
        return "\n".join(lines)

    # pure shell
    if shell_code:
        shell_text = _escape_awk_braces(textwrap.dedent(shell_code).rstrip())
        lines.append(f"{indent1}shell:")
        lines.append(f'{indent2}"""{shell_text}"""')
        return "\n".join(lines)

    # no action block
    return "\n".join(lines)