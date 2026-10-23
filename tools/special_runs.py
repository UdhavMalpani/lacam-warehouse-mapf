"""Targeted runs behind the explanatory figures (not part of the timing benchmark).

  progress : agents-at-goal over time for PIBT vs LaCAM(*) on instances where PIBT
             livelocks (shows *why* the LaCAM search layer is needed)
  solutions: full LaCAM* / PIBT solutions for congestion heat-maps and animations

Outputs go to results/special/.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "build" / "mapf_lacam.exe"
OUT = ROOT / "results" / "special"
RAW_MAPS = ROOT / "data" / "raw" / "mapf-map"
RAW_SCENS = ROOT / "data" / "raw" / "mapf-scen-random" / "scen-random"


def paths(name):
    if (RAW_MAPS / f"{name}.map").exists():
        return RAW_MAPS / f"{name}.map", RAW_SCENS / f"{name}-random-{{k}}.scen"
    return ROOT / "data" / "maps" / f"{name}.map", ROOT / "data" / "scens" / f"{name}-random-{{k}}.scen"


def run(map_name, scen, n, algo, tag, extra=(), t=30, seed=None):
    m, s = paths(map_name)
    out = OUT / f"{tag}.txt"
    cmd = [str(EXE), "-m", str(m), "-i", str(s).format(k=scen), "-N", str(n), "-a", algo,
           "-t", str(t), "-s", str(scen if seed is None else seed), "-o", str(out), *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout.strip())
    return out


# (map, agents, scen) where PIBT is known to livelock in the benchmark probes
PROGRESS_CASES = [
    ("narrowaisle", 100, 1),
    ("warehouse-10-20-10-2-1", 300, 1),
    ("sortation", 500, 1),
    ("random-32-32-20", 200, 1),
]

SOLUTION_CASES = [
    ("warehouse-10-20-10-2-1", 500, 1, "lacam_star_first"),
    ("sortation", 500, 1, "lacam_star_first"),
    ("narrowaisle", 300, 1, "lacam_star_first"),
    ("crossdock", 800, 1, "lacam_star_first"),
    ("narrowaisle", 100, 1, "lacam_star_first"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="*", default=["progress", "solutions"])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    index = {}
    if "progress" in args.what:
        for m, n, k in PROGRESS_CASES:
            for algo in ("pibt", "pibt_swap", "lacam", "lacam_star_first"):
                tag = f"progress_{m}_N{n}_s{k}_{algo}"
                run(m, k, n, algo, tag, extra=("--log-progress",))
                index[tag] = dict(kind="progress", map=m, N=n, scen=k, algo=algo)
    if "solutions" in args.what:
        for m, n, k, algo in SOLUTION_CASES:
            tag = f"solution_{m}_N{n}_s{k}_{algo}"
            run(m, k, n, algo, tag, extra=("--log-solution",))
            index[tag] = dict(kind="solution", map=m, N=n, scen=k, algo=algo)
        # the PIBT trajectory on the livelocked narrow-aisle case, for a side-by-side animation
        tag = "solution_narrowaisle_N100_s1_pibt_partial"
        run("narrowaisle", 1, 100, "pibt", tag, extra=("--log-progress", "--log-solution", "--max-steps", "400"))
        index[tag] = dict(kind="progress", map="narrowaisle", N=100, scen=1, algo="pibt")
    idx_file = OUT / "index.json"
    old = json.loads(idx_file.read_text()) if idx_file.exists() else {}
    old.update(index)
    idx_file.write_text(json.dumps(old, indent=1))


if __name__ == "__main__":
    sys.exit(main())
