#!/usr/bin/env python3
import json, sys, ast, os
from pathlib import Path

# Where coverage.py wrote the JSON
COV_JSON = Path("coverage.json")

# Gates (overridable in env): MIN_COVERAGE and MIN_FILE_COVERAGE
OVERALL_MIN = float(os.getenv("MIN_COVERAGE", "60"))
PER_FILE_MIN = float(os.getenv("MIN_FILE_COVERAGE", "40"))

def main():
    if not COV_JSON.exists():
        print("ERROR: coverage.json not found. Run `coverage json` first.")
        sys.exit(2)

    data = json.loads(COV_JSON.read_text(encoding="utf-8"))
    files = data.get("files", {})

    total_executed = 0
    total_denominator = 0
    under_threshold = []

    print("\n=== Coverage Summary (file & function) ===")
    for abs_path, info in files.items():
        p = Path(abs_path)

        # Only report on your project code under scripts/
        if "scripts" not in p.parts:
            continue

        executed = set(info.get("executed_lines", []))
        missing  = set(info.get("missing_lines", []))
        denom    = executed | missing

        file_exec = len(executed)
        file_denom = len(denom)
        file_pct = 100.0 * file_exec / file_denom if file_denom else 100.0

        total_executed += file_exec
        total_denominator += file_denom

        print(f"\nFile: {abs_path} -> {file_pct:.1f}% ({file_exec}/{file_denom})")
        if file_pct < PER_FILE_MIN:
            under_threshold.append((abs_path, file_pct))

        # Function-level breakdown
        try:
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)

            funcs = []
            class V(ast.NodeVisitor):
                def visit_FunctionDef(self, n):
                    funcs.append((n.name, n.lineno, getattr(n, "end_lineno", n.lineno)))
                    self.generic_visit(n)
                def visit_AsyncFunctionDef(self, n):
                    funcs.append((n.name, n.lineno, getattr(n, "end_lineno", n.lineno)))
                    self.generic_visit(n)
            V().visit(tree)
            funcs.sort(key=lambda x: x[1])

            # Estimate end lines when end_lineno is missing
            spans = []
            for i, (nm, st, en) in enumerate(funcs):
                if en == st:
                    nxt = funcs[i+1][1] if i + 1 < len(funcs) else st + 1_000_000
                    en = nxt - 1
                spans.append((nm, st, en))

            for nm, st, en in spans:
                func_lines = set(range(st, en + 1))
                func_denom = func_lines & denom
                if not func_denom:
                    fpct = 100.0
                else:
                    fpct = 100.0 * len(func_lines & executed) / len(func_denom)
                print(f"  - {nm:28s} {fpct:5.1f}%")

        except Exception as e:
            print(f"  (function breakdown unavailable: {e})")

    overall = 100.0 * total_executed / total_denominator if total_denominator else 100.0
    print(f"\nOverall coverage: {overall:.1f}%")

    rc = 0
    if overall < OVERALL_MIN:
        print(f"ERROR: overall {overall:.1f}% < MIN {OVERALL_MIN}%")
        rc = 1
    if under_threshold:
        print("\nFiles under per-file threshold:")
        for name, pct in under_threshold:
            print(f"  - {name}: {pct:.1f}% (min {PER_FILE_MIN}%)")
        rc = 1

    sys.exit(rc)

if __name__ == "__main__":
    main()
