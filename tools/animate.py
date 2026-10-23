"""Animations of logged solutions (results/special/) as GIFs + a still frame strip.

  python tools/animate.py
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapf_utils as U  # noqa: E402
import make_figures as MF  # noqa: E402
from make_figures import (INK, INK2, MUTED, OBSTACLE, RES, SURFACE, COLOR, map_path,  # noqa: E402
                          fs, style, suptitle)

FIG = MF.FIG
DPI = 90

FREE = "#f3f2ee"
AT_GOAL = "#9ec5f4"  # light step of the blue ramp: agent already parked on its goal


def load(tag):
    f = RES / "special" / f"{tag}.txt"
    sol = np.array(U.parse_lacam_solution(f.read_text()))
    kv = dict(l.split("=", 1) for l in f.read_text().splitlines()[:40] if "=" in l)
    return sol, kv


def draw_panel(ax, map_name, title):
    w, h, free = U.load_map(map_path(map_name))
    ax.imshow(np.where(free, 1, 0), cmap=ListedColormap([OBSTACLE, FREE]), interpolation="nearest")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, fontsize=fs(10))
    moving = ax.scatter([], [], s=14, color=COLOR["LaCAM*"], linewidths=0, zorder=3)
    parked = ax.scatter([], [], s=14, color=AT_GOAL, linewidths=0, zorder=2)
    status = ax.text(0, -0.04, "", transform=ax.transAxes, ha="left", va="top", fontsize=fs(9),
                     color=INK2)
    return moving, parked, status


def update_panel(artists, sol, t, goals, label):
    moving, parked, status = artists
    tt = min(t, len(sol) - 1)
    pos = sol[tt]
    on_goal = (pos == goals).all(axis=1)
    moving.set_offsets(pos[~on_goal])
    parked.set_offsets(pos[on_goal] if on_goal.any() else np.empty((0, 2)))
    done = " · finished" if t >= len(sol) - 1 and on_goal.all() else ""
    status.set_text(f"{label}  t = {tt:>3}   on goal: {on_goal.sum()}/{len(pos)}{done}")


def side_by_side(map_name, n, left_tag, right_tag, out_name, frames=None, fps=12):
    left, _ = load(left_tag)
    right, _ = load(right_tag)
    _, goals = U.load_scen(next((RES.parent / "data").rglob(f"{map_name}-random-1.scen")), n)
    goals = np.array(goals)
    frames = frames or max(len(left), len(right))
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.6))
    a = draw_panel(axes[0], map_name, "PIBT alone")
    b = draw_panel(axes[1], map_name, "LaCAM* (PIBT + lazy-constraint search + swap)")
    suptitle(fig, f"{map_name} · {n} agents", "dark dot = moving / waiting · light dot = parked "
             "on its goal", y=1.02)

    def step(t):
        update_panel(a, left, t, goals, "PIBT")
        update_panel(b, right, t, goals, "LaCAM*")
        return []

    anim = FuncAnimation(fig, step, frames=frames, interval=1000 / fps)
    FIG.mkdir(exist_ok=True)
    anim.save(FIG / f"{out_name}.gif", writer=PillowWriter(fps=fps), dpi=DPI)
    # still strip for slides that cannot play GIFs
    plt.close(fig)
    ts = [0, len(right) // 3, 2 * len(right) // 3, len(right) - 1, frames - 1]
    fig, axes = plt.subplots(2, len(ts), figsize=(3.2 * len(ts), 3.4))
    for col, t in enumerate(ts):
        for row, (sol, lab) in enumerate([(left, "PIBT"), (right, "LaCAM*")]):
            arts = draw_panel(axes[row, col], map_name, f"{lab} · t = {min(t, len(sol) - 1)}")
            update_panel(arts, sol, t, goals, "")
    fig.subplots_adjust(hspace=0.45, wspace=0.05, top=0.82)
    suptitle(fig, f"{map_name} · {n} agents: PIBT stalls, LaCAM* finishes", y=0.97)
    fig.savefig(FIG / f"{out_name}_strip.png", bbox_inches="tight", dpi=180)
    plt.close(fig)
    print("wrote", FIG / f"{out_name}.gif")


def single(map_name, n, tag, out_name, fps=15):
    sol, _ = load(tag)
    _, goals = U.load_scen(next((RES.parent / "data").rglob(f"{map_name}-random-1.scen")), n)
    goals = np.array(goals)
    w, h, _ = U.load_map(map_path(map_name))
    fig, ax = plt.subplots(figsize=(10, 10 * h / w + 0.6))
    arts = draw_panel(ax, map_name, f"LaCAM* · {map_name} · {n} agents")
    anim = FuncAnimation(fig, lambda t: update_panel(arts, sol, t, goals, "") or [],
                         frames=len(sol), interval=1000 / fps)
    anim.save(FIG / f"{out_name}.gif", writer=PillowWriter(fps=fps), dpi=80)
    plt.close(fig)
    print("wrote", FIG / f"{out_name}.gif")


if __name__ == "__main__":
    if "--slides" in sys.argv:  # larger text and resolution for the slide deck
        MF.FONT_SCALE = 1.4
        FIG = MF.FIG / "slides"
        DPI = 150
    style()
    side_by_side("narrowaisle", 100, "solution_narrowaisle_N100_s1_pibt_partial",
                 "solution_narrowaisle_N100_s1_lacam_star_first", "anim_pibt_vs_lacam_narrowaisle",
                 frames=260)
    if "--slides" not in sys.argv:
        single("warehouse-10-20-10-2-1", 500,
               "solution_warehouse-10-20-10-2-1_N500_s1_lacam_star_first",
               "anim_lacam_warehouse_500")
