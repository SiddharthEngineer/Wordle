"""
Writes data/opening.csv: every word with its probability, E(|v|) and weighted E(|v|)
against the full list (the solver's answer with no rows). Too slow to compute per request,
so the web app loads this table instead. Rerun after changing the word list or the solver.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import solver  # noqa: E402

OUT = ROOT / "data/opening.csv"


def main():
    rows = solver.solve([])
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["word", "probability", "ev", "wev"])
        for r in rows:
            writer.writerow([r["word"], round(r["probability"], 6), round(r["ev"], 6), round(r["wev"], 6)])
    print(f"Wrote {len(rows)} rows to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
