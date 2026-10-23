"""Benchmark runner: parallel, resumable, with early stopping per (planner, map).

Every run is appended as one JSON line to the output file; re-running the same
command skips finished runs. For each (planner, map) the agent counts are
processed in increasing order, and once a planner solves none of the instances
at some agent count, larger counts on that map are skipped (recorded as
failures), which avoids burning hours on hopeless time-outs.

All solutions are validated: ours inside the C++ binary (independent checker in
metrics.cpp), the baselines by tools/mapf_utils.validate on their path files.

Examples
  python tools/run_experiments.py --suite smoke --workers 4
  python tools/run_experiments.py --suite main --workers 4
"""
import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
import psutil
from scipy.sparse.csgraph import shortest_path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapf_utils as U  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
RAW_MAPS = ROOT / "data" / "raw" / "mapf-map"
RAW_SCENS = ROOT / "data" / "raw" / "mapf-scen-random" / "scen-random"

MEM_LIMIT_MB = 1200  # per run: LaCAM stops itself, the baselines are killed by a watchdog
GRACE_S = 30         # wall-clock slack before a run that ignores its time limit is killed


def movingai(name, ns, category, scens):
    return dict(name=name, map=str(RAW_MAPS / f"{name}.map"),
                scen=str(RAW_SCENS / f"{name}-random-{{k}}.scen"),
                ns=ns, category=category, scens=scens)


def custom(name, ns, category, scens):
    return dict(name=name, map=str(ROOT / "data" / "maps" / f"{name}.map"),
                scen=str(ROOT / "data" / "scens" / f"{name}-random-{{k}}.scen"),
                ns=ns, category=category, scens=scens)


N_STD = [100, 200, 300, 400, 500, 600, 800, 1000]

MAIN_MAPS = [
    movingai("warehouse-10-20-10-2-1", N_STD, "warehouse", 10),
    movingai("warehouse-10-20-10-2-2", N_STD, "warehouse", 10),
    movingai("warehouse-20-40-10-2-1", N_STD, "warehouse", 10),
    movingai("warehouse-20-40-10-2-2", N_STD, "warehouse", 10),
    custom("sortation", N_STD, "warehouse", 10),
    custom("narrowaisle", N_STD, "warehouse", 10),
    custom("crossdock", N_STD, "warehouse", 10),
    movingai("random-32-32-20", [50, 100, 150, 200, 250, 300, 350, 400], "other", 5),
    movingai("room-64-64-8", N_STD, "other", 5),
    movingai("maze-32-32-4", [25, 50, 100, 150, 200, 250, 300, 350], "other", 5),
    movingai("den520d", N_STD, "other", 5),
    movingai("Paris_1_256", N_STD, "other", 5),
]

SUITES = {
    "smoke": dict(
        maps=[movingai("random-32-32-20", [50, 100], "other", 2),
              custom("narrowaisle", [100], "warehouse", 2)],
        planners=["PIBT", "PIBT+swap", "LaCAM", "LaCAM*", "EECBS", "LNS2", "PBS"],
        time_limit=10),
    "main": dict(
        maps=MAIN_MAPS,
        planners=["PIBT", "PIBT+swap", "LaCAM", "LaCAM*", "EECBS", "LNS2", "PBS"],
        time_limit=30),
    # solution quality over time: LaCAM*'s eventually-optimal refinement vs
    # MAPF-LNS's large-neighbourhood refinement (both started from their first solution)
    "anytime": dict(
        maps=[movingai("random-32-32-20", [50, 100, 200], "other", 3),
              movingai("room-64-64-8", [100, 300, 500], "other", 3),
              movingai("warehouse-10-20-10-2-1", [100, 300, 500], "warehouse", 3),
              custom("sortation", [100, 300, 500], "warehouse", 3),
              custom("narrowaisle", [100, 300, 500], "warehouse", 3)],
        planners=["LaCAM*-anytime", "LNS-anytime"],
        time_limit=60),
}

# planner name -> (kind, argument)
PLANNERS = {
    "PIBT": ("ours", "pibt"),
    "PIBT+swap": ("ours", "pibt_swap"),
    "LaCAM": ("ours", "lacam"),
    "LaCAM+swap": ("ours", "lacam_swap"),
    "LaCAM*": ("ours", "lacam_star_first"),
    "LaCAM*-anytime": ("ours", "lacam_star"),
    "EECBS": ("eecbs", 1.2),
    "LNS2": ("lns2", 0),
    "LNS-anytime": ("lns2", 10 ** 8),
    "PBS": ("pbs", None),
}


# ---------------------------------------------------------------------------
# process control

def run_cmd(cmd, cwd, timeout_s, mem_limit_mb=None):
    """Run cmd with a wall-clock timeout and an optional memory watchdog.
    Returns (wall_s, peak_mb, kill_reason)."""
    t0 = time.perf_counter()
    with open(Path(cwd) / "stdout.txt", "wb") as out:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=out, stderr=subprocess.STDOUT)
    try:
        ps = psutil.Process(proc.pid)
    except psutil.Error:
        ps = None
    peak, reason = 0.0, None
    while True:
        try:
            proc.wait(timeout=0.1)
            break
        except subprocess.TimeoutExpired:
            pass
        if ps is not None:
            try:
                mi = ps.memory_info()
                peak = max(peak, getattr(mi, "peak_pagefile", mi.rss) / 2 ** 20)
            except psutil.Error:
                pass
        if mem_limit_mb is not None and peak > mem_limit_mb:
            reason = "memout"
        elif time.perf_counter() - t0 > timeout_s:
            reason = "killed"
        if reason:
            proc.kill()
            proc.wait()
            break
    return time.perf_counter() - t0, peak, reason


def parse_kv(path):
    d = {}
    if not Path(path).exists():
        return d
    for line in Path(path).read_text().splitlines():
        if line.startswith("solution="):
            break
        if "=" in line:
            k, v = line.split("=", 1)
            d[k] = v
    return d


def last_csv_row(path):
    if not Path(path).exists():
        return None
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        return None
    return {h.strip(): v.strip() for h, v in zip(rows[0], rows[-1])}


_lb_cache, _lb_lock = {}, threading.Lock()


def shortest_distances(map_path, scen_path):
    """Per-agent shortest-path distance (4-connected) for all agents of a scen."""
    key = (map_path, scen_path)
    with _lb_lock:
        if key in _lb_cache:
            return _lb_cache[key]
    w, h, free = U.load_map(map_path)
    starts, goals = U.load_scen(scen_path, 10 ** 9)
    idx = np.arange(w * h).reshape(h, w)
    right = free[:, :-1] & free[:, 1:]
    down = free[:-1, :] & free[1:, :]
    from scipy.sparse import coo_matrix
    r = np.concatenate([idx[:, :-1][right], idx[:-1, :][down]])
    c = np.concatenate([idx[:, 1:][right], idx[1:, :][down]])
    G = coo_matrix((np.ones(len(r)), (r, c)), shape=(w * h, w * h)).tocsr()
    d = np.empty(len(starts), dtype=np.int64)
    for k0 in range(0, len(starts), 100):
        chunk = goals[k0:k0 + 100]
        D = shortest_path(G, directed=False, unweighted=True, indices=[y * w + x for x, y in chunk])
        for j, (sx, sy) in enumerate(starts[k0:k0 + 100]):
            d[k0 + j] = int(D[j, sy * w + sx])
    with _lb_lock:
        _lb_cache[key] = d
    return d


# ---------------------------------------------------------------------------
# planners

def run_ours(algo, task, tmp, tl):
    out = tmp / "out.txt"
    cmd = [str(BUILD / "mapf_lacam.exe"), "-m", task["map"], "-i", task["scen_file"],
           "-N", str(task["N"]), "-a", algo, "-t", str(tl), "-s", str(task["seed"]),
           "-o", str(out), "--mem-limit-mb", str(MEM_LIMIT_MB)]
    wall, peak, reason = run_cmd(cmd, tmp, tl + GRACE_S)
    kv = parse_kv(out)
    rec = dict(wall_ms=wall * 1000, peak_mb=peak, kill=reason)
    if not kv:
        rec.update(solved=False, valid=False, status=reason or "error")
        return rec
    solved = kv["solved"] == "1"
    valid = kv["valid"] == "1"
    mem = kv.get("mem_limit_hit") == "1"
    rec.update(
        solved=solved, valid=valid,
        runtime_ms=float(kv["time_first_ms"]) if solved else None,
        comp_time_ms=float(kv["comp_time_ms"]),
        soc=int(kv["soc"]) if solved else None,
        makespan=int(kv["makespan"]) if solved else None,
        sum_of_loss=int(kv["sum_of_loss"]) if solved else None,
        soc_lb=int(kv["soc_lb"]), makespan_lb=int(kv["makespan_lb"]),
        soc_first=int(kv["soc_first"]) if solved and kv["soc_first"] != "-1" else None,
        makespan_first=int(kv["makespan_first"]) if solved and kv["makespan_first"] != "-1" else None,
        hnodes=int(kv["hnodes"]), lnodes=int(kv["lnodes"]), loop_cnt=int(kv["loop_cnt"]),
        pibt_calls=int(kv["pibt_calls"]), pibt_fail=int(kv["pibt_fail"]),
        revisits=int(kv["revisits"]), restarts=int(kv["restarts"]), rewires=int(kv["rewires"]),
        max_open=int(kv["max_open"]), optimal=kv["optimal"] == "1", mem_limit_hit=mem,
        pibt_step_limit=kv.get("pibt_step_limit") == "1",
        anytime_log=kv.get("anytime_log", ""),
    )
    if solved and valid:
        rec["status"] = "solved"
    elif solved:
        rec["status"] = "invalid"
    else:
        rec["status"] = "memout" if mem else ("step_limit" if rec["pibt_step_limit"] else "timeout")
    return rec


def finish_baseline(task, tmp, rec, cost_key, solved_flag, runtime_s, pre_s, paths_file, tl):
    """Validate a baseline's path file and fill the common fields."""
    rec["runtime_ms"] = (runtime_s + pre_s) * 1000 if solved_flag else None
    rec["comp_time_ms"] = (runtime_s + pre_s) * 1000
    if not solved_flag:
        rec.update(solved=False, valid=False, status=rec.get("kill") or "timeout")
        return rec
    if rec["runtime_ms"] > tl * 1000:  # overshoot of the limit counts as a failure
        rec.update(solved=False, valid=False, status="timeout")
        return rec
    if not paths_file.exists():
        rec.update(solved=False, valid=False, status="no_paths")
        return rec
    starts, goals = U.load_scen(task["scen_file"], task["N"])
    paths = U.parse_cbs_style_paths(paths_file)
    if len(paths) != task["N"]:
        rec.update(solved=True, valid=False, status="invalid", invalid_reason="missing agents")
        return rec
    ok, msg, m = U.validate(task["map"], starts, goals, U.paths_to_array(paths, task["N"]))
    rec.update(solved=True, valid=ok, status="solved" if ok else "invalid")
    if not ok:
        rec["invalid_reason"] = msg
        return rec
    rec.update(soc=m["soc"], makespan=m["makespan"], sum_of_loss=m["sum_of_loss"],
               reported_cost=cost_key)
    return rec


def run_eecbs(w, task, tmp, tl):
    out, paths = tmp / "eecbs.csv", tmp / "paths.txt"
    cmd = [str(BUILD / "eecbs.exe"), "-m", task["map"], "-a", task["scen_file"], "-o", str(out),
           f"--outputPaths={paths}", "-k", str(task["N"]), "-t", str(tl),
           f"--suboptimality={w}", "-s", "0"]
    wall, peak, reason = run_cmd(cmd, tmp, tl + GRACE_S, MEM_LIMIT_MB)
    rec = dict(wall_ms=wall * 1000, peak_mb=peak, kill=reason)
    row = last_csv_row(out)
    if row is None or reason:
        rec.update(solved=False, valid=False, status=reason or "error")
        return rec
    cost = int(float(row["solution cost"]))
    rec.update(hl_expanded=int(row["#high-level expanded"]),
               hl_generated=int(row["#high-level generated"]),
               ll_expanded=int(row["#low-level expanded"]))
    return finish_baseline(task, tmp, rec, cost, cost >= 0, float(row["runtime"]),
                           float(row["preprocessing runtime"]), paths, tl)


def run_pbs(_, task, tmp, tl):
    out, paths = tmp / "pbs.csv", tmp / "paths.txt"
    cmd = [str(BUILD / "pbs.exe"), "-m", task["map"], "-a", task["scen_file"], "-o", str(out),
           f"--outputPaths={paths}", "-k", str(task["N"]), "-t", str(tl), "-s", "0"]
    wall, peak, reason = run_cmd(cmd, tmp, tl + GRACE_S, MEM_LIMIT_MB)
    rec = dict(wall_ms=wall * 1000, peak_mb=peak, kill=reason)
    row = last_csv_row(out)
    if row is None or reason:
        rec.update(solved=False, valid=False, status=reason or "error")
        return rec
    cost = int(float(row["solution cost"]))
    rec.update(hl_expanded=int(row["#high-level expanded"]),
               hl_generated=int(row["#high-level generated"]),
               ll_expanded=int(row["#low-level expanded"]))
    return finish_baseline(task, tmp, rec, cost, cost >= 0, float(row["runtime"]),
                           float(row["preprocessing runtime"]), paths, tl)


def run_lns2(max_iter, task, tmp, tl):
    prefix, paths = tmp / "lns", tmp / "paths.txt"
    stats = tmp / "iters-LNS.csv"  # LNS writes <stats prefix>-LNS.csv
    cmd = [str(BUILD / "lns.exe"), "-m", task["map"], "-a", task["scen_file"], "-o", str(prefix),
           f"--outputPaths={paths}", "-k", str(task["N"]), "-t", str(tl), "-s", "0",
           "--seed", str(task["seed"]), f"--maxIterations={max_iter}"]
    if max_iter > 0:
        cmd.append(f"--stats={tmp / 'iters'}")
    wall, peak, reason = run_cmd(cmd, tmp, tl + GRACE_S, MEM_LIMIT_MB)
    rec = dict(wall_ms=wall * 1000, peak_mb=peak, kill=reason)
    row = last_csv_row(Path(str(prefix) + "-LNS.csv"))
    if row is None or reason:
        rec.update(solved=False, valid=False, status=reason or "error")
        return rec
    init_cost = int(float(row["initial solution cost"]))
    solved = init_cost >= 0
    rec.update(iterations=int(float(row["iterations"])), initial_cost=init_cost)
    if max_iter > 0:
        # anytime run: time to the first solution is the initial-solution runtime
        t_init = float(row["runtime of initial solution"])
        rec = finish_baseline(task, tmp, rec, int(float(row["solution cost"])), solved, t_init,
                              float(row["preprocessing runtime"]), paths, tl)
        rec["comp_time_ms"] = (float(row["runtime"]) + float(row["preprocessing runtime"])) * 1000
        if stats.exists():
            # LNS logs every iteration (thousands per second): keep the header, every
            # strict improvement of the sum of costs, and the last iteration
            lines = stats.read_text().splitlines()
            keep, best = [lines[0]], float("inf")
            for line in lines[1:]:
                cols = line.split(",")
                if len(cols) >= 3 and cols[1] and float(cols[1]) < best:
                    best = float(cols[1])
                    keep.append(line)
            if len(lines) > 1 and keep[-1] != lines[-1]:
                keep.append(lines[-1])
            rec["iter_log"] = "\n".join(keep)
            rec["lns_iterations_logged"] = len(lines) - 1
        return rec
    return finish_baseline(task, tmp, rec, int(float(row["solution cost"])), solved,
                           float(row["runtime"]), float(row["preprocessing runtime"]), paths, tl)


RUNNERS = {"ours": run_ours, "eecbs": run_eecbs, "pbs": run_pbs, "lns2": run_lns2}


def execute(task, tl):
    kind, arg = PLANNERS[task["planner"]]
    tmp = Path(tempfile.mkdtemp(prefix="mapf_"))
    try:
        rec = RUNNERS[kind](arg, task, tmp, tl)
    except Exception as e:  # keep the runner alive, record the problem
        rec = dict(solved=False, valid=False, status="error", error=repr(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    d = shortest_distances(task["map"], task["scen_file"])[:task["N"]]
    rec.setdefault("soc_lb", int(d.sum()))
    rec.setdefault("makespan_lb", int(d.max()))
    rec["success"] = bool(rec.get("solved") and rec.get("valid"))
    base = {k: task[k] for k in ("planner", "map_name", "category", "N", "scen", "seed")}
    base["time_limit_s"] = tl
    return {**base, **rec}


# ---------------------------------------------------------------------------
# scheduling with early stopping

def task_id(t):
    return f'{t["planner"]}|{t["map_name"]}|{t["N"]}|{t["scen"]}'


class Scheduler:
    """Hands out tasks level by level (agent count) for every (planner, map) chain."""

    def __init__(self, chains, done, writer):
        self.cv = threading.Condition()
        self.ready = deque()
        self.chains = chains  # key -> list of levels (lists of tasks)
        self.state = {}
        self.done = done
        self.writer = writer
        self.running = 0
        for key in chains:
            self.state[key] = dict(level=-1, pending=0, succ=0)
            self._advance(key)

    def _advance(self, key):
        st, levels = self.state[key], self.chains[key]
        while True:
            st["level"] += 1
            if st["level"] >= len(levels):
                return
            level = levels[st["level"]]
            todo = [t for t in level if task_id(t) not in self.done]
            st["succ"] = sum(self.done[task_id(t)] for t in level if task_id(t) in self.done)
            st["pending"] = len(todo)
            if todo:
                self.ready.extend(todo)
                return
            if st["succ"] == 0:
                self._skip_rest(key)
                return

    def _skip_rest(self, key):
        st, levels = self.state[key], self.chains[key]
        for level in levels[st["level"] + 1:]:
            for t in level:
                if task_id(t) not in self.done:
                    self.writer({**{k: t[k] for k in ("planner", "map_name", "category", "N",
                                                      "scen", "seed")},
                                 "status": "skipped", "solved": False, "valid": False,
                                 "success": False})
                    self.done[task_id(t)] = False
        st["level"] = len(levels)

    def get(self):
        with self.cv:
            while not self.ready and self.running > 0:
                self.cv.wait()
            if not self.ready:
                return None
            self.running += 1
            return self.ready.popleft()

    def report(self, task, success):
        with self.cv:
            self.running -= 1
            key = (task["planner"], task["map_name"])
            st = self.state[key]
            self.done[task_id(task)] = success
            st["pending"] -= 1
            st["succ"] += int(success)
            if st["pending"] == 0:
                if st["succ"] == 0:
                    self._skip_rest(key)
                else:
                    self._advance(key)
            self.cv.notify_all()


def build_chains(suite, planners, maps_filter):
    chains = {}
    for m in suite["maps"]:
        if maps_filter and m["name"] not in maps_filter:
            continue
        for p in planners:
            levels = []
            for n in m["ns"]:
                level = []
                for k in range(1, m["scens"] + 1):
                    scen_file = m["scen"].format(k=k)
                    if not Path(scen_file).exists() or not Path(m["map"]).exists():
                        raise FileNotFoundError(scen_file)  # baselines would invent agents
                    level.append(dict(planner=p, map_name=m["name"], map=m["map"],
                                      category=m["category"], N=n, scen=k, seed=k,
                                      scen_file=scen_file))
                levels.append(level)
            chains[(p, m["name"])] = levels
    return chains


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="smoke", choices=sorted(SUITES))
    ap.add_argument("--planners", nargs="*")
    ap.add_argument("--maps", nargs="*")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--time-limit", type=float)
    ap.add_argument("--out")
    args = ap.parse_args()

    suite = SUITES[args.suite]
    planners = args.planners or suite["planners"]
    tl = args.time_limit or suite["time_limit"]
    out = Path(args.out or ROOT / "results" / f"{args.suite}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    done = {}
    if out.exists():
        for line in out.read_text().splitlines():
            r = json.loads(line)
            done[f'{r["planner"]}|{r["map_name"]}|{r["N"]}|{r["scen"]}'] = bool(r["success"])
    write_lock = threading.Lock()
    fout = open(out, "a")

    def writer(rec):
        with write_lock:
            fout.write(json.dumps(rec) + "\n")
            fout.flush()

    chains = build_chains(suite, planners, args.maps)
    total = sum(len(l) for levels in chains.values() for l in levels)
    sched = Scheduler(chains, done, writer)
    counter = dict(n=0)
    t_start = time.time()

    def worker():
        while True:
            task = sched.get()
            if task is None:
                return
            rec = execute(task, tl)
            writer(rec)
            with write_lock:
                counter["n"] += 1
                el = time.time() - t_start
                rt = rec.get("runtime_ms")
                print(f'[{counter["n"]:5d} | {el / 60:6.1f} min] {rec["planner"]:<10} '
                      f'{rec["map_name"]:<24} N={rec["N"]:<5} scen={rec["scen"]:<3} '
                      f'{rec["status"]:<9} {"" if rt is None else f"{rt:9.1f} ms"}', flush=True)
            sched.report(task, rec["success"])

    print(f"suite={args.suite} planners={planners} time_limit={tl}s tasks<={total} "
          f"already_done={len(done)} -> {out}", flush=True)
    threads = [threading.Thread(target=worker) for _ in range(args.workers)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    fout.close()
    print(f"finished in {(time.time() - t_start) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
