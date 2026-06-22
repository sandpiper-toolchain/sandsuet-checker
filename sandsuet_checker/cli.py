import argparse
import os
import sys

from . import SandsuetChecker

# ANSI color codes — only applied when writing to a real terminal
_BLUE = "\033[34m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_RESET = "\033[0m"

_STATUS_COLORS = {
    "PASS": _BLUE,
    "WARN": _YELLOW,
    "FAIL": _RED,
    "SKIP": _RESET,
}


def _colorize(text, color, use_color):
    return f"{color}{text}{_RESET}" if use_color else text


def format_report(filepath, results, use_color=False):
    header = f"=== sandsuet Compliance Report: {os.path.basename(filepath)} ==="
    lines = [header, ""]

    for section, status, message in results:
        color = _STATUS_COLORS.get(status, _RESET)
        label = _colorize(f"[{status:4s}]", color, use_color)
        lines.append(f"  {label} {section}: {message}")
    lines.append("")

    counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
    for _, status, _ in results:
        counts[status] = counts.get(status, 0) + 1

    skip_note = f"  |  SKIP: {counts['SKIP']}" if counts["SKIP"] else ""
    verdict = "COMPLIANT" if counts["FAIL"] == 0 else "NON-COMPLIANT"
    verdict_color = _BLUE if counts["FAIL"] == 0 else _RED
    lines.append("--- Summary ---")
    lines.append(
        f"  {_colorize('PASS', _BLUE, use_color)}: {counts['PASS']}"
        f"  |  {_colorize('FAIL', _RED, use_color)}: {counts['FAIL']}"
        f"  |  {_colorize('WARN', _YELLOW, use_color)}: {counts['WARN']}{skip_note}"
    )
    lines.append(f"  Result: {_colorize(verdict, verdict_color, use_color)}")
    lines.append("=" * len(header))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="sandsuet v1.0.0 Compliance Checker for NetCDF4 files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", help="Path to the NetCDF4 file to validate.")
    parser.add_argument("-o", "--output", help="Save report to a text file.")
    parser.add_argument(
        "--georeferenced",
        action="store_true",
        help=(
            "Enable N-S-first horizontal dimension check. "
            "Use for datasets with real-world coordinate systems (e.g. UTM). "
            "Omit for model or laboratory grids with arbitrary spatial coords."
        ),
    )
    args = parser.parse_args()

    try:
        checker = SandsuetChecker.from_path(args.file, georeferenced=args.georeferenced)
        results = checker.run_all()
        report = format_report(args.file, results, use_color=sys.stdout.isatty())
        print(report)

        if args.output:
            with open(args.output, "w") as f:
                f.write(format_report(args.file, results, use_color=False))
            print(f"\nReport saved to {args.output}")

        fail_count = sum(1 for _, s, _ in results if s == "FAIL")
        sys.exit(1 if fail_count > 0 else 0)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
