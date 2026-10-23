"""Reproduction-fidelity check: our LaCAM / LaCAM* vs the official implementations.

Runs both on the same instances with the same seed (official: Kei18/lacam v1 and
Kei18/lacam2 with objective "none", i.e. first solution) and records solved / SoC /
makespan / runtime. Output: results/fidelity.csv

  python tools/validate_reimplementation.py
"""
import csv
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "build"
RAW_MAPS = ROOT / "data" / "raw" / "mapf-map"
RAW_SCENS = ROOT / "data" / "raw" / "mapf-scen-random" / "scen-random"
TIME_LIMIT = 10  # seconds (the official CLI takes an integer)

CASES = {  # map -> agent counts
    "warehouse-10-20-10-2-1": [100, 300], "warehouse-10-20-10-2-2": [100, 300],
    "warehouse-20-40-10-2-1": [100, 300], "warehouse-20-40-10-2-2": [100, 300],
    "sortation": [100, 300], "narrowaisle": [100, 300], "crossdock": [100, 300],
    "random-32-32-20": [50, 150], "room-64-64-8": [100, 300], "maze-32-32-4": [50, 150],
    "den520d": [100, 300], "Paris_1_256": [100, 300],
}
VARIANTS = [  # (label, official exe + extra args, our algorithm)
    ("LaCAM", ["lacam_official.exe"], "lacam"),
    ("LaCAM*", ["lacam2_official.exe", "-O", "0"], "lacam_star_first"),
]


def files(m, k):
    if (RAW_MAPS / f"{m}.map").exists():
        return RAW_MAPS / f"{m}.map", RAW_SCENS / f"{m}-random-{k}.scen"
    return ROOT / "data" / "maps" / f"{m}.map", ROOT / "data" / "scens" / f"{m}-random-{k}.scen"


def kv(path):
    d = {}
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                d[k] = v
    return d


def main():
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "r.txt"
        for m, ns in CASES.items():
            for n in ns:
                for k in (1, 2):
                    mp, sc = files(m, k)
                    for label, official, ours in VARIANTS:
                        out.unlink(missing_ok=True)
                        subprocess.run([str(B / official[0]), *official[1:], "-m", str(mp),
                                        "-i", str(sc), "-N", str(n), "-s", "0",
                                        "-t", str(TIME_LIMIT), "-o", str(out), "-l"],
                                       capture_output=True)
                        o = kv(out)
                        out.unlink(missing_ok=True)
                        subprocess.run([str(B / "mapf_lacam.exe"), "-m", str(mp), "-i", str(sc),
                                        "-N", str(n), "-a", ours, "-s", "0",
                                        "-t", str(TIME_LIMIT), "-o", str(out)],
                                       capture_output=True)
                        u = kv(out)
                        row = dict(variant=label, map=m, N=n, scen=k,
                                   official_solved=o.get("solved"), ours_solved=u.get("solved"),
                                   official_soc=o.get("soc"), ours_soc=u.get("soc"),
                                   official_makespan=o.get("makespan"),
                                   ours_makespan=u.get("makespan"),
                                   official_ms=o.get("comp_time"), ours_ms=u.get("comp_time_ms"))
                        rows.append(row)
                        print(row, flush=True)
    with open(ROOT / "results" / "fidelity.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
