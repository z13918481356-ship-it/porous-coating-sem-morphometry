from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEPS = PROJECT / ".deps"
if DEPS.exists() and os.environ.get("SEM_USE_WORKSPACE_RUNTIME") != "1":
    sys.path.insert(0, str(DEPS))
sys.path.insert(0, str(PROJECT / "src"))

from morphometry.pipeline import run_pipeline


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=PROJECT / "data" / "raw" / "zenodo_16054027")
    parser.add_argument("--output-root", type=Path, default=PROJECT / "outputs")
    parser.add_argument("--calibration", type=Path, default=PROJECT / "configs" / "manual_calibration.csv")
    parser.add_argument("--seed", type=int, default=20260829)
    args = parser.parse_args()
    run_pipeline(args.data_root, args.output_root, args.calibration, args.seed)
