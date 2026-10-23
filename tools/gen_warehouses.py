"""Generate custom warehouse layouts and random scenarios in MovingAI format.

Three layouts complement the four MovingAI warehouse maps (which all have
looped 1- or 2-wide aisles between shelf blocks):

  sortation   robotic sortation floor: 2x2 chute blocks separated by 1-wide
              lanes (a lattice of narrow corridors with frequent junctions)
  narrowaisle very-narrow-aisle racking: 1-wide *dead-end* aisles branching off
              2-wide cross corridors (agents must back out of an aisle)
  crossdock   cross-dock / staging hall: open floor with sparse 2x3 pallet
              stacks and dock doors along the long walls

Usage:  python tools/gen_warehouses.py --out data
"""
import argparse
import random
from collections import deque
from pathlib import Path


def sortation(nbx=28, nby=18, block=2, lane=1, margin=3):
    period = block + lane
    w = 2 * margin + nbx * period - lane
    h = 2 * margin + nby * period - lane
    grid = [["." for _ in range(w)] for _ in range(h)]
    for by in range(nby):
        for bx in range(nbx):
            for dy in range(block):
                for dx in range(block):
                    grid[margin + by * period + dy][margin + bx * period + dx] = "@"
    return grid


def narrowaisle(n_aisles=40, depth=8, zones=3, corridor=2, shelf=2, side=3):
    # columns: [side corridor] (shelf, aisle)* shelf [side corridor]
    inner_w = n_aisles * (shelf + 1) + shelf
    w = 2 * side + inner_w
    zone_h = 2 * depth + 1  # aisles from above, separating wall, aisles from below
    h = corridor + zones * (zone_h + corridor)
    grid = [["." for _ in range(w)] for _ in range(h)]
    y = corridor
    for _ in range(zones):
        for dy in range(zone_h):
            for x in range(side, side + inner_w):
                col = x - side
                is_aisle = col % (shelf + 1) == shelf
                is_wall_row = dy == depth  # middle row: aisles are dead ends
                if not is_aisle or is_wall_row:
                    grid[y + dy][x] = "@"
        y += zone_h + corridor
    return grid


def crossdock(w=96, h=60, dock_band=6, pallet=(3, 2), gap=(5, 4), seed=7):
    rng = random.Random(seed)
    grid = [["." for _ in range(w)] for _ in range(h)]
    pw, ph = pallet
    gx, gy = gap
    row = 0
    y = dock_band
    while y + ph <= h - dock_band:
        x = 4 + (row % 2) * ((pw + gx) // 2)  # staggered rows
        while x + pw <= w - 4:
            if rng.random() < 0.85:  # leave a few gaps so the floor is not perfectly regular
                for dy in range(ph):
                    for dx in range(pw):
                        grid[y + dy][x + dx] = "@"
            x += pw + gx
        y += ph + gy
        row += 1
    return grid


LAYOUTS = {
    "sortation": sortation,
    "narrowaisle": narrowaisle,
    "crossdock": crossdock,
}


def largest_component(grid):
    h, w = len(grid), len(grid[0])
    seen = [[False] * w for _ in range(h)]
    best = []
    for sy in range(h):
        for sx in range(w):
            if grid[sy][sx] != "." or seen[sy][sx]:
                continue
            comp, q = [], deque([(sx, sy)])
            seen[sy][sx] = True
            while q:
                x, y = q.popleft()
                comp.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] == "." and not seen[ny][nx]:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            if len(comp) > len(best):
                best = comp
    return best


def write_map(grid, path):
    with open(path, "w", newline="\n") as f:
        f.write(f"type octile\nheight {len(grid)}\nwidth {len(grid[0])}\nmap\n")
        for row in grid:
            f.write("".join(row) + "\n")


def grid_graph(grid):
    """Sparse adjacency matrix of the free cells (index = y * w + x)."""
    import numpy as np
    from scipy.sparse import coo_matrix

    h, w = len(grid), len(grid[0])
    free = np.array([[c == "." for c in row] for row in grid])
    rows, cols = [], []
    idx = np.arange(h * w).reshape(h, w)
    right = free[:, :-1] & free[:, 1:]
    down = free[:-1, :] & free[1:, :]
    rows += list(idx[:, :-1][right]) + list(idx[:-1, :][down])
    cols += list(idx[:, 1:][right]) + list(idx[1:, :][down])
    data = np.ones(len(rows))
    return coo_matrix((data, (rows, cols)), shape=(h * w, h * w)).tocsr()


def write_scen(grid, map_name, path, n_agents, seed, graph):
    from scipy.sparse.csgraph import shortest_path

    rng = random.Random(seed)
    cells = largest_component(grid)
    starts = rng.sample(cells, n_agents)
    goals = rng.sample(cells, n_agents)
    h, w = len(grid), len(grid[0])
    dist = shortest_path(graph, directed=False, unweighted=True,
                         indices=[y * w + x for x, y in starts])
    with open(path, "w", newline="\n") as f:
        f.write("version 1\n")
        for k, ((sx, sy), (gx, gy)) in enumerate(zip(starts, goals)):
            d = int(dist[k, gy * w + gx])
            f.write(f"{d // 4}\t{map_name}\t{w}\t{h}\t{sx}\t{sy}\t{gx}\t{gy}\t{d}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--scens", type=int, default=25)
    ap.add_argument("--agents", type=int, default=1000)
    args = ap.parse_args()
    out = Path(args.out)
    (out / "maps").mkdir(parents=True, exist_ok=True)
    (out / "scens").mkdir(parents=True, exist_ok=True)
    for name, fn in LAYOUTS.items():
        grid = fn()
        # drop free cells that are not reachable from the main component
        comp = set(largest_component(grid))
        for y, row in enumerate(grid):
            for x, c in enumerate(row):
                if c == "." and (x, y) not in comp:
                    row[x] = "@"
        map_name = f"{name}.map"
        write_map(grid, out / "maps" / map_name)
        free = len(comp)
        print(f"{name}: {len(grid[0])}x{len(grid)}, free cells = {free}")
        graph = grid_graph(grid)
        for k in range(1, args.scens + 1):
            write_scen(grid, map_name, out / "scens" / f"{name}-random-{k}.scen",
                       min(args.agents, free // 2), seed=1000 * k + len(name), graph=graph)


if __name__ == "__main__":
    main()
