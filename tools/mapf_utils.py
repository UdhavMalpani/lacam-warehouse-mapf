"""Shared helpers: MovingAI map/scen loading, path-file parsing and an
independent solution validator used for *every* planner's output, so that all
reported costs are computed in exactly the same way."""
import re
from functools import lru_cache
from pathlib import Path

import numpy as np


@lru_cache(maxsize=None)
def load_map(path):
    """Returns (width, height, free mask as (H, W) bool array)."""
    lines = Path(path).read_text().splitlines()
    h = w = 0
    k = 0
    while k < len(lines):
        tok = lines[k].split()
        k += 1
        if not tok:
            continue
        if tok[0] == "height":
            h = int(tok[1])
        elif tok[0] == "width":
            w = int(tok[1])
        elif tok[0] == "map":
            break
    rows = lines[k:k + h]
    free = np.array([[c in ".GS" for c in row[:w].ljust(w, "@")] for row in rows], dtype=bool)
    return w, h, free


def load_scen(path, n):
    """First n (start, goal) pairs as (x, y) tuples."""
    starts, goals = [], []
    for line in Path(path).read_text().splitlines():
        tok = line.split()
        if len(tok) < 8 or tok[0] == "version":
            continue
        starts.append((int(tok[4]), int(tok[5])))
        goals.append((int(tok[6]), int(tok[7])))
        if len(starts) == n:
            break
    return starts, goals


_RC = re.compile(r"\((\d+),(\d+)\)")


def parse_cbs_style_paths(path):
    """EECBS / PBS / MAPF-LNS2 path files: 'Agent i: (row,col)->(row,col)->...'.
    Returns {agent: [(x, y), ...]}."""
    paths = {}
    for line in Path(path).read_text().splitlines():
        if not line.startswith("Agent"):
            continue
        head, _, body = line.partition(":")
        i = int(head.split()[1])
        paths[i] = [(int(c), int(r)) for r, c in _RC.findall(body)]
    return paths


def parse_lacam_solution(text):
    """Our / official LaCAM output: 't:(x,y),(x,y),...' lines after 'solution='.
    Returns a (T+1, N) list of configurations of (x, y)."""
    sol = []
    started = False
    for line in text.splitlines():
        if line.startswith("solution="):
            started = True
            continue
        if started and ":" in line:
            _, _, body = line.partition(":")
            sol.append([(int(x), int(y)) for x, y in _RC.findall(body)])
    return sol


def paths_to_array(paths, n):
    """Per-agent paths (agents stay at their goal after the path ends) -> (T+1, N) array of (x, y)."""
    T = max(len(paths[i]) for i in range(n))
    arr = np.empty((T, n, 2), dtype=np.int32)
    for i in range(n):
        p = np.asarray(paths[i], dtype=np.int32)
        arr[:len(p), i] = p
        arr[len(p):, i] = p[-1]
    return arr


def validate(map_path, starts, goals, sol):
    """sol: (T+1, N, 2) array of (x, y). Returns (ok, message, metrics)."""
    w, h, free = load_map(map_path)
    sol = np.asarray(sol, dtype=np.int64)
    n = sol.shape[1]
    st = np.asarray(starts, dtype=np.int64)
    gl = np.asarray(goals, dtype=np.int64)
    if sol.shape[1] != len(starts):
        return False, "wrong number of agents", {}
    if not np.array_equal(sol[0], st):
        return False, "first configuration differs from starts", {}
    if not np.array_equal(sol[-1], gl):
        return False, "last configuration differs from goals", {}
    xs, ys = sol[..., 0], sol[..., 1]
    if xs.min() < 0 or ys.min() < 0 or xs.max() >= w or ys.max() >= h:
        return False, "position outside the map", {}
    if not free[ys, xs].all():
        return False, "agent on an obstacle", {}
    idx = ys * w + xs  # (T+1, N) cell ids
    step = np.abs(np.diff(xs, axis=0)) + np.abs(np.diff(ys, axis=0))
    if (step > 1).any():
        t, i = np.argwhere(step > 1)[0]
        return False, f"invalid move of agent {i} at t={t + 1}", {}
    for t in range(1, idx.shape[0]):
        cur = idx[t]
        if np.unique(cur).size != n:
            return False, f"vertex conflict at t={t}", {}
        prev = idx[t - 1]
        moving = prev != cur
        if moving.any():
            fwd = prev[moving] * (w * h) + cur[moving]
            bwd = cur[moving] * (w * h) + prev[moving]
            if np.intersect1d(fwd, bwd).size:
                return False, f"swap conflict at t={t}", {}
    # costs
    at_goal = idx == (gl[:, 1] * w + gl[:, 0])[None, :]
    T = idx.shape[0] - 1
    # cost of an agent = arrival time = (last timestep it was NOT at its goal) + 1
    not_goal = ~at_goal
    arrival = np.where(not_goal.any(axis=0), (T + 1) - np.argmax(not_goal[::-1], axis=0), 0)
    soc = int(arrival.sum())
    makespan = int(arrival.max()) if n else 0
    loss = int(((~at_goal[:-1]) | (~at_goal[1:])).sum())
    return True, "ok", {"soc": soc, "makespan": makespan, "sum_of_loss": loss}
