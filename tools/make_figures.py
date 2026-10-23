"""Produce every figure and summary table from results/*.jsonl and results/special/.

  python tools/make_figures.py            # all figures that have data
  python tools/make_figures.py success    # just some of them

Figures are written to figures/ as PNG (slides) and PDF (print).
Colour follows the planner everywhere (fixed categorical slots from the dataviz
reference palette); every series also has its own marker so identity never
relies on colour alone.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapf_utils as U  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
FIG = ROOT / "figures"
RAW_MAPS = ROOT / "data" / "raw" / "mapf-map"

# ---------------------------------------------------------------- design tokens
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, OBSTACLE = "#e1e0d9", "#c3c2b7", "#3a3936"
GRAY = "#b5b3ab"  # de-emphasis

PLANNERS = ["LaCAM*", "LaCAM", "PIBT", "EECBS", "LNS2", "PBS", "PIBT+swap"]
MAIN = ["LaCAM*", "LaCAM", "PIBT", "EECBS", "LNS2", "PBS"]
COLOR = {"LaCAM*": "#2a78d6", "LaCAM": "#eb6834", "PIBT": "#1baf7a", "EECBS": "#eda100",
         "LNS2": "#e87ba4", "PBS": "#008300", "PIBT+swap": "#6250d6"}
MARKER = {"LaCAM*": "o", "LaCAM": "s", "PIBT": "^", "EECBS": "D", "LNS2": "v", "PBS": "P",
          "PIBT+swap": "X"}
LABEL = {"LaCAM*": "LaCAM*", "LaCAM": "LaCAM", "PIBT": "PIBT", "EECBS": "EECBS (w=1.2)",
         "LNS2": "MAPF-LNS2", "PBS": "PBS", "PIBT+swap": "PIBT + swap"}
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
       "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
SEQ_CMAP = LinearSegmentedColormap.from_list("seq_blue", SEQ)

# --slides renders the same figures with every font 1.4x larger (slide legibility)
FONT_SCALE = 1.0


def fs(size):
    return size * FONT_SCALE

MAP_ORDER = ["warehouse-10-20-10-2-1", "warehouse-10-20-10-2-2", "warehouse-20-40-10-2-1",
             "warehouse-20-40-10-2-2", "sortation", "narrowaisle", "crossdock",
             "random-32-32-20", "room-64-64-8", "maze-32-32-4", "den520d", "Paris_1_256"]
MAP_NOTE = {
    "warehouse-10-20-10-2-1": "MovingAI · 1-wide aisles",
    "warehouse-10-20-10-2-2": "MovingAI · 2-wide aisles",
    "warehouse-20-40-10-2-1": "MovingAI · large, 1-wide",
    "warehouse-20-40-10-2-2": "MovingAI · large, 2-wide",
    "sortation": "custom · sortation floor",
    "narrowaisle": "custom · dead-end aisles",
    "crossdock": "custom · open cross-dock",
    "random-32-32-20": "random obstacles",
    "room-64-64-8": "rooms + doors",
    "maze-32-32-4": "maze, 4-wide",
    "den520d": "game map",
    "Paris_1_256": "city map",
}
SHORT = {"warehouse-10-20-10-2-1": "wh-10-20-…-1", "warehouse-10-20-10-2-2": "wh-10-20-…-2",
         "warehouse-20-40-10-2-1": "wh-20-40-…-1", "warehouse-20-40-10-2-2": "wh-20-40-…-2"}


def map_path(name):
    p = RAW_MAPS / f"{name}.map"
    return p if p.exists() else ROOT / "data" / "maps" / f"{name}.map"


def style():
    plt.rcParams.update({
        "font.family": "Segoe UI", "font.size": fs(9),
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "figure.dpi": 110, "savefig.dpi": 220,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.labelcolor": INK2,
        "axes.titlecolor": INK, "axes.titlesize": fs(9.5), "axes.titleweight": "semibold",
        "axes.titlelocation": "left", "axes.titlepad": 6,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-",
        "axes.axisbelow": True,
        "xtick.color": INK2, "ytick.color": INK2, "xtick.major.size": 0, "ytick.major.size": 0,
        "xtick.minor.size": 0, "ytick.minor.size": 0, "xtick.major.pad": 4, "ytick.major.pad": 4,
        "legend.frameon": False, "legend.fontsize": fs(9), "text.color": INK,
        "lines.linewidth": 1.8, "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
        "lines.markersize": 5.5, "lines.markeredgewidth": 1.0,
    })


def save(fig, name):
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / f"{name}.png")


def suptitle(fig, title, subtitle=None, y=1.0):
    fig.text(0.0, y, title, ha="left", va="bottom", fontsize=fs(13), fontweight="semibold",
             color=INK, transform=fig.transFigure)
    if subtitle:
        fig.text(0.0, y - 0.005, subtitle, ha="left", va="top", fontsize=fs(9.5), color=INK2,
                 transform=fig.transFigure)


def planner_legend(fig, planners, y=0.985, ncol=None):
    handles = [Line2D([], [], color=COLOR[p], marker=MARKER[p], markeredgecolor=SURFACE,
                      lw=1.8, ms=6.5, label=LABEL[p]) for p in planners]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, y),
               ncol=ncol or len(planners), handlelength=2.2, columnspacing=1.6,
               labelcolor=INK)


def plot_series(ax, x, y, p, **kw):
    # LaCAM* (the subject) is drawn on top where series coincide (e.g. all at 100 %)
    z = 5 if p == "LaCAM*" else 3
    ax.plot(x, y, color=COLOR[p], marker=MARKER[p], markeredgecolor=SURFACE, zorder=z, **kw)


# ---------------------------------------------------------------- data

def load(name):
    f = RES / f"{name}.jsonl"
    if not f.exists():
        return None
    df = pd.DataFrame([json.loads(l) for l in f.read_text().splitlines() if l.strip()])
    df["success"] = df["success"].fillna(False).astype(bool)
    for col in ("soc", "soc_lb", "makespan", "makespan_lb", "runtime_ms"):
        if col not in df:
            df[col] = np.nan
    df["soc_ratio"] = df["soc"] / df["soc_lb"]
    df["makespan_ratio"] = df["makespan"] / df["makespan_lb"]
    return df


def aggregate(df):
    rows = []
    for (p, m, n), sub in df.groupby(["planner", "map_name", "N"]):
        succ = sub["success"].to_numpy()
        rt = np.where(succ, sub["runtime_ms"].to_numpy(dtype=float), np.inf)
        med = np.median(rt)  # failures count as +inf: defined only if >= 50 % solved
        solved = sub[sub["success"]]
        rows.append(dict(
            planner=p, map_name=m, N=n, category=sub["category"].iloc[0],
            n=len(sub), succ=succ.mean(),
            rt_median=med if np.isfinite(med) else np.nan,
            rt_q1=np.percentile(rt, 25) if np.isfinite(np.percentile(rt, 25)) else np.nan,
            rt_q3=np.percentile(rt, 75) if np.isfinite(np.percentile(rt, 75)) else np.nan,
            soc_ratio=solved["soc_ratio"].median() if succ.mean() >= 0.5 else np.nan,
            ms_ratio=solved["makespan_ratio"].median() if succ.mean() >= 0.5 else np.nan,
        ))
    return pd.DataFrame(rows)


def small_multiples(maps, ncols=4, w=3.15, h=2.35):
    nrows = int(np.ceil(len(maps) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(w * ncols, h * nrows), squeeze=False)
    axes = list(axes.flat)  # a list, so callers can iterate more than once
    for ax in axes[len(maps):]:
        ax.set_visible(False)
    return fig, axes


def map_title(ax, m, note=None):
    ax.set_title(m, fontsize=fs(9.5), pad=fs(15))
    ax.text(0.0, 1.025, MAP_NOTE.get(m, "") if note is None else note, transform=ax.transAxes,
            ha="left", va="bottom", fontsize=fs(8), color=MUTED)


# ---------------------------------------------------------------- figures

METRICS = {
    "success": ("fig01_success_rate", "Success rate within 30 s"),
    "runtime": ("fig02_runtime",
                "Median time to solution (failures count as time-outs; shown where ≥ 50 % solved)"),
    "quality": ("fig03_quality",
                "Solution quality: sum-of-costs ÷ lower bound (1.0 = no agent ever delayed)"),
}


def fig_metric(df, agg_df, kind, maps=None, suffix="", title_note=""):
    """Small multiples of one metric vs number of agents, one panel per map."""
    maps = maps or [m for m in MAP_ORDER if m in set(df["map_name"])]
    name, title = METRICS[kind]
    ncols = 4 if len(maps) > 6 else 3
    fig, axes = small_multiples(maps, ncols=ncols)
    for ax, m in zip(axes, maps):
        sub = agg_df[agg_df["map_name"] == m]
        for p in MAIN:
            s = sub[sub["planner"] == p].sort_values("N")
            if kind == "runtime":
                s = s.dropna(subset=["rt_median"])
                y = s["rt_median"] / 1000
            elif kind == "quality":
                s = s.dropna(subset=["soc_ratio"])
                y = s["soc_ratio"]
            else:
                y = 100 * s["succ"]
            if len(s):
                plot_series(ax, s["N"], y, p)
        if kind == "success":
            ax.set_ylim(-5, 105)
            ax.set_yticks([0, 50, 100])
            ax.set_yticklabels(["0%", "50%", "100%"])
        elif kind == "runtime":
            ax.set_yscale("log")
            ax.set_ylim(5e-4, 60)
            ax.set_yticks([1e-3, 1e-2, 1e-1, 1, 10])
            ax.set_yticklabels(["1 ms", "10 ms", "0.1 s", "1 s", "10 s"])
            ax.axhline(30, color=AXIS, lw=0.8)
        else:
            ax.axhline(1.0, color=AXIS, lw=0.8)
        map_title(ax, m)
    for k, ax in enumerate(axes):
        # x label on the lowest visible panel of every column
        if ax.get_visible() and (k + ncols >= len(maps)):
            ax.set_xlabel("number of agents")
    nrows = int(np.ceil(len(maps) / ncols))
    fig.subplots_adjust(hspace=0.8, wspace=0.3, top=1 - 0.42 / nrows)
    suptitle(fig, title + title_note, y=1.02)
    planner_legend(fig, MAIN, y=0.995)
    save(fig, name + suffix)


def fig_cactus(df):
    cats = [("warehouse", "Warehouse maps (7)"), ("other", "Other domains (5)")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
    for ax, (cat, title) in zip(axes, cats):
        sub = df[df["category"] == cat]
        total = len(sub.drop_duplicates(["map_name", "N", "scen"]))
        ends = []
        for p in MAIN:
            s = sub[(sub["planner"] == p) & sub["success"]]
            t = np.sort(s["runtime_ms"].to_numpy(dtype=float)) / 1000
            if len(t) == 0:
                continue
            t = np.maximum(t, 1e-3)
            xs = np.concatenate([[1e-3], t, [30]])
            ys = np.concatenate([[0], np.arange(1, len(t) + 1), [len(t)]])
            ax.step(xs, ys, where="post", color=COLOR[p], lw=1.8)
            ax.plot(30, len(t), marker=MARKER[p], color=COLOR[p], markeredgecolor=SURFACE,
                    ms=7, zorder=4, clip_on=False)
            ends.append((len(t), p))
        # direct labels at the right end; walk down from the top so they never overlap
        ends.sort(reverse=True)
        gap = total * 0.065
        prev = None
        for cnt, p in ends:
            y = cnt if prev is None else min(cnt, prev - gap)
            prev = y
            ax.annotate(f"{LABEL[p]}  {cnt}", xy=(30, cnt), xytext=(40, y), fontsize=fs(8.5),
                        color=INK, va="center", annotation_clip=False,
                        arrowprops=dict(arrowstyle="-", color=AXIS, lw=0.6,
                                        shrinkA=0, shrinkB=3))
        ax.axhline(total, color=AXIS, lw=0.8)
        ax.text(1.1e-3, total, f"{total} instances", va="bottom", fontsize=fs(8), color=MUTED)
        ax.set_xscale("log")
        ax.set_xlim(1e-3, 30)
        ax.set_xticks([1e-3, 1e-2, 1e-1, 1, 10, 30])
        ax.set_xticklabels(["1 ms", "10 ms", "0.1 s", "1 s", "10 s", "30 s"])
        ax.set_ylim(0, total * 1.08)
        ax.set_xlabel("time limit")
        ax.set_ylabel("instances solved")
        ax.set_title(title)
    fig.subplots_adjust(wspace=0.55, top=0.82)
    suptitle(fig, "Instances solved as a function of the time budget", y=0.98)
    save(fig, "fig04_cactus")


def heatmap(ax, mat, rows, cols, fmt, vmax=None, cmap=SEQ_CMAP, labels=None):
    """labels: optional matrix of cell texts (default: fmt(value))."""
    vmax = vmax if vmax is not None else np.nanmax(mat)
    ax.imshow(mat, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rows)
    ax.tick_params(axis="x", top=True, labeltop=True, bottom=False, labelbottom=False)
    # 2 px surface gaps between cells
    for i in range(len(rows) + 1):
        ax.axhline(i - 0.5, color=SURFACE, lw=2.2)
    for j in range(len(cols) + 1):
        ax.axvline(j - 0.5, color=SURFACE, lw=2.2)
    for i in range(len(rows)):
        for j in range(len(cols)):
            v = mat[i, j]
            if np.isnan(v):
                continue
            frac = v / vmax if vmax else 0
            ax.text(j, i, fmt(v) if labels is None else labels[i][j], ha="center",
                    va="center", fontsize=fs(8.5), color="white" if frac > 0.55 else INK)


def fig_scalability(df):
    maps = [m for m in MAP_ORDER if m in set(df["map_name"])]
    planners = [p for p in MAIN if p in set(df["planner"])]
    pct = np.full((len(maps), len(planners)), np.nan)
    maxn = np.full((len(maps), len(planners)), np.nan)
    for i, m in enumerate(maps):
        for j, p in enumerate(planners):
            s = df[(df["map_name"] == m) & (df["planner"] == p)]
            if len(s):
                pct[i, j] = 100 * s["success"].mean()
                ok = s.groupby("N")["success"].mean()
                ok = ok[ok >= 0.8]
                maxn[i, j] = ok.index.max() if len(ok) else 0
    rows = [f"{m}" for m in maps]
    tested = df.groupby("map_name")["N"].max()
    frac = np.array([[maxn[i, j] / tested[m] for j in range(len(planners))]
                     for i, m in enumerate(maps)])
    labels = [["–" if maxn[i, j] == 0 else
               f"{maxn[i, j]:.0f}" + ("+" if maxn[i, j] == tested[m] else "")
               for j in range(len(planners))] for i, m in enumerate(maps)]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.9))
    heatmap(axes[0], pct, rows, [LABEL[p] for p in planners], lambda v: f"{v:.0f}%", vmax=100)
    axes[0].set_title("Instances solved (all agent counts)", pad=40)
    heatmap(axes[1], frac, rows, [LABEL[p] for p in planners], None, vmax=1.0, labels=labels)
    axes[1].set_yticklabels([])
    axes[1].set_title("Largest agent count with ≥ 80 % success", pad=40)
    for ax in axes:
        plt.setp(ax.get_xticklabels(), rotation=30, ha="left", rotation_mode="anchor")
    fig.subplots_adjust(wspace=0.06, top=0.74)
    suptitle(fig, "Scalability summary · 30 s limit",
             "Right: shading relative to the largest count tested on that map (1000; "
             "random-32-32-20: 400; maze-32-32-4: 350). + = every tested count solved.",
             y=0.985)
    save(fig, "fig05_scalability")
    return pct, maxn, maps, planners


def fig_ablation(df):
    variants = ["PIBT", "PIBT+swap", "LaCAM", "LaCAM*"]
    maps = [m for m in MAP_ORDER if m in set(df["map_name"])]
    mat = np.full((len(maps), len(variants)), np.nan)
    for i, m in enumerate(maps):
        for j, p in enumerate(variants):
            s = df[(df["map_name"] == m) & (df["planner"] == p)]
            if len(s):
                mat[i, j] = 100 * s["success"].mean()
    cols = ["PIBT\n(no search, no swap)", "PIBT + swap\n(no search)", "LaCAM\n(search, no swap)",
            "LaCAM*\n(search + swap)"]
    fig, ax = plt.subplots(figsize=(7.4, 5.4))
    heatmap(ax, mat, maps, cols, lambda v: f"{v:.0f}%", vmax=100)
    ax.tick_params(axis="x", labelsize=fs(8.5))
    fig.subplots_adjust(top=0.84)
    suptitle(fig, "Which ingredient matters where?",
             "Instances solved within 30 s, all agent counts. Same PIBT code in every column.",
             y=0.985)
    save(fig, "fig06_ablation")


def fig_progress():
    idx_file = RES / "special" / "index.json"
    if not idx_file.exists():
        return
    idx = json.loads(idx_file.read_text())
    cases = [("narrowaisle", 100), ("warehouse-10-20-10-2-1", 300), ("sortation", 500),
             ("random-32-32-20", 200)]
    algos = [("lacam_star_first", "LaCAM*"), ("lacam", "LaCAM"), ("pibt", "PIBT"),
             ("pibt_swap", "PIBT+swap")]
    XMAX = 600
    slides = FONT_SCALE > 1
    if slides:
        fig, axes = plt.subplots(2, 2, figsize=(12, 7.4))
        axes = axes.flat
    else:
        fig, axes = plt.subplots(1, 4, figsize=(13.5, 3.5))
    for ax, (m, n) in zip(axes, cases):
        tmax = 0
        stuck = []
        for algo, p in algos:
            f = RES / "special" / f"progress_{m}_N{n}_s1_{algo}.txt"
            if not f.exists():
                continue
            kv = dict(l.split("=", 1) for l in f.read_text().splitlines() if "=" in l)
            prog = [int(x) for x in kv.get("progress", "").split(",") if x]
            if not prog:
                continue
            full_len, full_max = len(prog), max(prog)
            prog = np.array(prog[:XMAX + 1])
            ax.plot(np.arange(len(prog)), 100 * prog / n, color=COLOR[p], lw=1.6,
                    label=LABEL[p], zorder=3 if p.startswith("LaCAM") else 2)
            solved = kv["solved"] == "1"
            if solved:
                ax.plot(len(prog) - 1, 100 * prog[-1] / n, marker="o", color=COLOR[p],
                        markeredgecolor=SURFACE, ms=7, zorder=4)
            else:
                ax.plot(XMAX, 100 * prog[-1] / n, marker="x", color=COLOR[p], ms=7, mew=1.8,
                        zorder=4, clip_on=False)
                stuck.append(f"{LABEL[p]}: never above {full_max}/{n} on goal "
                             f"in {full_len - 1:,} steps")
            tmax = max(tmax, len(prog))
        for k, msg in enumerate(stuck):  # empty lower-right region of the panel
            ax.text(XMAX * 0.97, 42 - 11 * FONT_SCALE * k, msg, ha="right", va="bottom",
                    fontsize=fs(7.8), color=INK2)
        ax.set_xlim(0, XMAX)
        ax.set_ylim(0, 104)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax.set_xlabel("timestep")
        map_title(ax, m, note=f"{n} agents")
    for k, ax in enumerate(axes):
        if k % (2 if slides else 4) == 0:
            ax.set_ylabel("agents on their goal")
    if slides:
        fig.subplots_adjust(wspace=0.22, hspace=0.62, top=0.8)
    else:
        fig.subplots_adjust(wspace=0.3, top=0.62)
    suptitle(fig, "PIBT alone livelocks; LaCAM's search over configurations escapes",
             "Agents standing on their goal, first 600 timesteps. ● = all agents arrived · "
             "× = never finished (PIBT: 10,000-step cap; LaCAM v1: 30 s, no trace)", y=1.02)
    planner_legend(fig, ["LaCAM*", "LaCAM", "PIBT", "PIBT+swap"], y=0.93 if slides else 0.88)
    save(fig, "fig07_pibt_livelock")


def fig_search_effort(df):
    """How much search does LaCAM do beyond a single PIBT rollout?"""
    lac = df[df["planner"].isin(["LaCAM", "LaCAM*"]) & df["success"]].copy()
    if lac.empty:
        return
    lac["overhead"] = lac["hnodes"] / (lac["makespan"] + 1)
    pibt = df[df["planner"] == "PIBT"].set_index(["map_name", "N", "scen"])["status"]
    lac["pibt_outcome"] = [
        ("PIBT solved" if pibt.get((m, n, s)) == "solved" else "PIBT failed")
        if (m, n, s) in pibt.index else "PIBT not run"
        for m, n, s in zip(lac["map_name"], lac["N"], lac["scen"])]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.3), gridspec_kw=dict(width_ratios=[1, 1.1]))
    # (a) overhead distribution split by PIBT's outcome on the same instance
    ax = axes[0]
    groups = [("LaCAM*", "PIBT solved"), ("LaCAM*", "PIBT failed"), ("LaCAM", "PIBT solved"),
              ("LaCAM", "PIBT failed")]
    rng = np.random.default_rng(0)
    for k, (p, o) in enumerate(groups):
        v = lac[(lac["planner"] == p) & (lac["pibt_outcome"] == o)]["overhead"].to_numpy()
        if len(v) == 0:
            continue
        x = k + rng.uniform(-0.2, 0.2, len(v))
        ax.scatter(x, v, s=10, color=COLOR[p], alpha=0.45, linewidths=0, zorder=3)
        med = np.median(v)
        ax.plot([k - 0.3, k + 0.3], [med, med], color=INK, lw=1.8, zorder=4)
        ax.text(k, med * 1.45, f"{med:.2f}×" if med < 10 else f"{med:.0f}×", ha="center",
                va="bottom", fontsize=fs(8.5), color=INK, fontweight="semibold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.15", fc=SURFACE, ec="none", alpha=0.85))
    counts = [((lac["planner"] == p) & (lac["pibt_outcome"] == o)).sum() for p, o in groups]
    ax.set_yscale("log")
    ax.set_ylim(0.6, max(10, lac["overhead"].max() * 1.6))
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([f"{p}\n{o}\nn = {c}" for (p, o), c in zip(groups, counts)],
                       fontsize=fs(8))
    ax.set_xlim(-0.55, len(groups) - 0.45)
    ax.set_ylabel("configurations ÷ (makespan + 1)")
    ax.set_title("Search effort per solved instance", pad=fs(15))
    ax.text(0, 1.015, "1× = a single greedy PIBT rollout", transform=ax.transAxes,
            fontsize=fs(8), color=MUTED, va="bottom")
    # (b) PIBT-call failure / revisit rates vs N, LaCAM v1 vs LaCAM*
    ax = axes[1]
    allruns = df[df["planner"].isin(["LaCAM", "LaCAM*"]) & (df["status"] != "skipped")].copy()
    allruns["revisit_rate"] = allruns["revisits"] / allruns["pibt_calls"].clip(lower=1)
    for p in ["LaCAM*", "LaCAM"]:
        for cat, ls in [("warehouse", "-"), ("other", (0, (1, 0)))]:
            s = allruns[(allruns["planner"] == p) & (allruns["category"] == cat)]
            g = s.groupby("N")["revisit_rate"].mean() * 100
            if len(g):
                ax.plot(g.index, g.values, color=COLOR[p], marker=MARKER[p],
                        markeredgecolor=SURFACE, lw=1.8 if cat == "warehouse" else 1.0,
                        alpha=1 if cat == "warehouse" else 0.55,
                        label=f"{LABEL[p]} · {cat}")
    ax.set_ylabel("successors already explored (%)")
    ax.set_xlabel("number of agents")
    ax.set_title("Revisits = PIBT cycles LaCAM detects", pad=fs(15))
    ax.text(0, 1.015, "mean over all runs, incl. failed ones", transform=ax.transAxes,
            fontsize=fs(8), color=MUTED, va="bottom")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, fontsize=fs(8.5))
    fig.subplots_adjust(wspace=0.3, top=0.78, bottom=0.22)
    suptitle(fig, "LaCAM only pays for search when PIBT would get stuck", y=0.99)
    save(fig, "fig08_search_effort")


def fig_maps():
    maps = MAP_ORDER
    fig, axes = plt.subplots(3, 4, figsize=(13, 8.2))
    cmap = ListedColormap([OBSTACLE, "#f3f2ee"])
    for ax, m in zip(axes.flat, maps):
        w, h, free = U.load_map(map_path(m))
        ax.imshow(free, cmap=cmap, interpolation="nearest")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(m, fontsize=fs(9.5))
        ax.set_xlabel(f"{w}×{h} · {free.sum():,} free cells · {MAP_NOTE[m]}", fontsize=fs(8),
                      color=INK2)
    fig.subplots_adjust(hspace=0.3, wspace=0.12, top=0.95)
    suptitle(fig, "Benchmark maps: 7 warehouse layouts (first 7) and 5 other domains", y=0.985)
    save(fig, "fig00_maps")


def fig_congestion():
    cases = [("warehouse-10-20-10-2-1", 500), ("sortation", 500), ("narrowaisle", 300),
             ("crossdock", 800)]
    files = [(m, n, RES / "special" / f"solution_{m}_N{n}_s1_lacam_star_first.txt")
             for m, n in cases]
    files = [c for c in files if c[2].exists()]
    if not files:
        return
    fig, axes = plt.subplots(2, 2, figsize=(13, 6.6))
    axes = axes.flat
    for ax, (m, n, f) in zip(axes, files):
        w, h, free = U.load_map(map_path(m))
        sol = np.array(U.parse_lacam_solution(f.read_text()))  # (T+1, N, 2)
        stay = (sol[1:] == sol[:-1]).all(axis=2)  # agent did not move during step t
        goal = sol[-1]
        at_goal = (sol[1:] == goal[None]).all(axis=2)
        wait = stay & ~at_goal  # waiting somewhere that is not its goal
        counts = np.zeros((h, w))
        xs, ys = sol[1:][wait][:, 0], sol[1:][wait][:, 1]
        np.add.at(counts, (ys, xs), 1)
        img = np.ma.masked_where(~free | (counts == 0), np.log1p(counts))
        ax.imshow(np.where(free, 1, 0), cmap=ListedColormap([OBSTACLE, "#f3f2ee"]),
                  interpolation="nearest")
        im = ax.imshow(img, cmap=SEQ_CMAP, interpolation="nearest", vmin=0)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
        total = int(wait.sum())
        ax.set_title(f"{m} · {n} agents · LaCAM*", fontsize=fs(9.5))
        ax.set_xlabel(f"{total:,} wait actions in total; darkest cell: {int(counts.max())} waits",
                      fontsize=fs(8), color=INK2)
        cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
        ticks = [t for t in [1, 3, 10, 30, 100, 300] if np.log1p(t) <= np.log1p(counts.max())]
        cb.set_ticks(np.log1p(ticks))
        cb.set_ticklabels([str(t) for t in ticks])
        cb.outline.set_visible(False)
        cb.ax.tick_params(labelsize=fs(8), colors=INK2)
    fig.subplots_adjust(hspace=0.25, wspace=0.08, top=0.88)
    suptitle(fig, "Where do agents wait? Congestion heat-maps of LaCAM* solutions",
             "Wait actions (agent not yet at its goal) per cell, log scale; uncoloured = no waits",
             y=0.97)
    save(fig, "fig09_congestion")


def fig_tradeoff(df):
    """Speed vs quality on instances solved, one point per planner (LaCAM* emphasised)."""
    cats = [("warehouse", "Warehouse maps"), ("other", "Other domains")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
    for ax, (cat, title) in zip(axes, cats):
        sub = df[(df["category"] == cat) & df["success"]]
        for p in MAIN:
            s = sub[sub["planner"] == p]
            if s.empty:
                continue
            x = s["runtime_ms"].median() / 1000
            y = s["soc_ratio"].median()
            c = COLOR["LaCAM*"] if p == "LaCAM*" else GRAY
            ax.plot(x, y, marker=MARKER[p], color=c, markeredgecolor=SURFACE, ms=9, zorder=3)
            # EECBS and PBS land almost on top of each other: label one above, one below
            off, ha = {"EECBS": ((-6, 14), "right"), "PBS": ((6, -16), "left")}.get(
                p, ((8, 0), "left"))
            ax.annotate(f"{LABEL[p]} · {len(s)} solved", (x, y), xytext=off,
                        textcoords="offset points", fontsize=fs(8.5), va="center", ha=ha,
                        color=INK)
        ax.set_xscale("log")
        ax.set_xlim(1e-3, 60)
        ax.set_xticks([1e-3, 1e-2, 1e-1, 1, 10])
        ax.set_xticklabels(["1 ms", "10 ms", "0.1 s", "1 s", "10 s"])
        ax.set_ylim(0.95, None)
        ax.set_xlabel("median time to solution (solved instances)")
        ax.set_ylabel("median SoC ÷ lower bound")
        ax.set_title(title)
    fig.subplots_adjust(wspace=0.3, top=0.8)
    suptitle(fig, "Speed vs. quality: LaCAM* is orders of magnitude faster, at a quality cost",
             "Each planner summarised over the instances it solved (more solved = harder mix)",
             y=0.99)
    save(fig, "fig10_tradeoff")


def fig_paired_quality(df):
    """SoC of LaCAM* relative to each baseline on instances both solved (no selection bias)."""
    base = df[df["planner"] == "LaCAM*"].set_index(["map_name", "N", "scen"])
    fig, ax = plt.subplots(figsize=(8.6, 3.4))
    others = ["EECBS", "PBS", "LNS2", "LaCAM", "PIBT"]
    for k, p in enumerate(others):
        s = df[(df["planner"] == p) & df["success"]].set_index(["map_name", "N", "scen"])
        both = s.join(base[base["success"]][["soc"]], rsuffix="_lacam", how="inner")
        if both.empty:
            continue
        r = both["soc_lacam"] / both["soc"]
        q1, med, q3 = np.percentile(r, [25, 50, 75])
        lo, hi = np.percentile(r, [5, 95])
        ax.plot([lo, hi], [k, k], color=AXIS, lw=1.2, zorder=2)
        ax.plot([q1, q3], [k, k], color=COLOR[p], lw=7, solid_capstyle="butt", zorder=3)
        ax.plot(med, k, marker="o", color=INK, ms=5, zorder=4)
        ax.text(hi * 1.01, k, f"median {med:.2f}×  ·  n={len(r)}", va="center", fontsize=fs(8.5),
                color=INK2)
    ax.axvline(1.0, color=INK2, lw=0.9)
    ax.set_yticks(range(len(others)))
    ax.set_yticklabels([LABEL[p] for p in others])
    ax.invert_yaxis()
    ax.set_xlabel("SoC(LaCAM*) ÷ SoC(other planner) on the same instance  (> 1: LaCAM* is worse)")
    ax.grid(axis="y", visible=False)
    fig.subplots_adjust(top=0.78)
    suptitle(fig, "Head-to-head solution cost on commonly solved instances",
             "Bar = interquartile range, whisker = 5–95 %, dot = median", y=0.99)
    save(fig, "fig11_paired_quality")


def anytime_curves(df):
    """Incumbent SoC ÷ lower bound over time for every anytime run, on a common grid."""
    grid = np.logspace(-3, np.log10(60), 300)  # seconds
    curves = []
    for _, r in df.iterrows():
        pts = []  # (seconds, soc)
        if r["planner"] == "LaCAM*-anytime" and isinstance(r.get("anytime_log"), str):
            for e in r["anytime_log"].split(";"):
                if e.count(":") == 2:
                    t, _, soc = e.split(":")
                    pts.append((float(t) / 1000, float(soc)))
        elif r["planner"] == "LNS-anytime" and isinstance(r.get("iter_log"), str):
            rows = [l.split(",") for l in r["iter_log"].splitlines()[1:] if l.strip()]
            if rows and r.get("runtime_ms") == r.get("runtime_ms"):
                t0 = float(rows[0][2])
                for row in rows:  # shift so the first solution sits at its measured time
                    pts.append((r["runtime_ms"] / 1000 + float(row[2]) - t0, float(row[1])))
        if not pts:
            continue
        pts.sort()
        best, vals, k = np.inf, np.full(len(grid), np.nan), 0
        for i, t in enumerate(grid):
            while k < len(pts) and pts[k][0] <= t:
                best = min(best, pts[k][1])
                k += 1
            if np.isfinite(best):
                vals[i] = best / r["soc_lb"]
        curves.append(dict(planner=r["planner"], map_name=r["map_name"], N=r["N"],
                           scen=r["scen"], vals=vals, first=pts[0][1] / r["soc_lb"],
                           final=min(p[1] for p in pts) / r["soc_lb"],
                           t_first=pts[0][0], mem=r.get("mem_limit_hit") is True))
    return grid, curves


def fig_anytime():
    df = load("anytime")
    if df is None:
        return
    grid, curves = anytime_curves(df)
    cf = pd.DataFrame(curves)
    maps = [m for m in MAP_ORDER if m in set(cf["map_name"])]
    ns = {m: sorted(cf[cf["map_name"] == m]["N"].unique()) for m in maps}
    ncols = max(len(v) for v in ns.values())
    fig, axes = plt.subplots(len(maps), ncols, figsize=(3.6 * ncols, 2.25 * len(maps)),
                             squeeze=False)
    names = {"LaCAM*-anytime": ("LaCAM*", "LaCAM* (anytime)"),
             "LNS-anytime": ("LNS2", "MAPF-LNS (anytime)")}
    for i, m in enumerate(maps):
        for j in range(ncols):
            ax = axes[i, j]
            if j >= len(ns[m]):
                ax.set_visible(False)
                continue
            n = ns[m][j]
            for p, (ckey, lab) in names.items():
                runs = cf[(cf["map_name"] == m) & (cf["N"] == n) & (cf["planner"] == p)]
                if runs.empty:
                    continue
                mat = np.vstack(runs["vals"].to_numpy())
                med = np.where(np.isnan(mat).any(axis=0), np.nan, np.median(mat, axis=0))
                ax.plot(grid, med, color=COLOR[ckey], lw=1.8, drawstyle="steps-post")
                last = med[~np.isnan(med)]
                if len(last):
                    ax.plot(grid[-1], last[-1], marker=MARKER[ckey], color=COLOR[ckey],
                            markeredgecolor=SURFACE, ms=6.5, clip_on=False, zorder=4)
                    ax.annotate(f"{last[-1]:.2f}", (grid[-1], last[-1]), xytext=(7, 0),
                                textcoords="offset points", va="center", fontsize=fs(8),
                                color=INK, annotation_clip=False)
            ax.set_xscale("log")
            ax.set_xlim(1e-3, 60)
            ax.set_xticks([1e-3, 1e-2, 1e-1, 1, 10, 60])
            ax.set_xticklabels(["1 ms", "10 ms", "0.1 s", "1 s", "10 s", "60 s"], fontsize=fs(8))
            ax.axhline(1.0, color=AXIS, lw=0.8)
            ax.set_title(f"{m} · {n} agents", fontsize=fs(9))
            if j == 0:
                ax.set_ylabel("SoC ÷ lower bound")
    fig.subplots_adjust(hspace=0.6, wspace=0.38, top=0.88)
    suptitle(fig, "Anytime refinement: solution cost over time (median of 3 instances)",
             "Each curve starts at the planner's first solution; value at 60 s is labelled",
             y=0.985)
    handles = [Line2D([], [], color=COLOR[c], marker=MARKER[c], markeredgecolor=SURFACE, lw=1.8,
                      ms=6.5, label=lab) for c, lab in names.values()]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 0.95), ncol=2)
    save(fig, "fig12_anytime")
    fig_anytime_dumbbell(cf)
    summ = cf.groupby(["planner", "map_name", "N"]).agg(
        first=("first", "median"), final=("final", "median"), t_first_s=("t_first", "median"),
        mem_capped=("mem", "sum")).reset_index()
    (RES / "tables").mkdir(exist_ok=True)
    summ.round(3).to_csv(RES / "tables" / "anytime_summary.csv", index=False)
    print(summ.round(3).to_string())


def fig_anytime_dumbbell(cf):
    """First solution -> cost after 60 s, per case, for both anytime planners."""
    summ = cf.groupby(["planner", "map_name", "N"])[["first", "final"]].median().reset_index()
    cases = [(m, n) for m in MAP_ORDER for n in sorted(summ[summ["map_name"] == m]["N"].unique())]
    fig, ax = plt.subplots(figsize=(10.5, 0.36 * len(cases) + 1.0))
    rows = [("LaCAM*-anytime", "LaCAM*", -0.16), ("LNS-anytime", "LNS2", 0.16)]
    for i, (m, n) in enumerate(cases):
        for p, ckey, dy in rows:
            r = summ[(summ["planner"] == p) & (summ["map_name"] == m) & (summ["N"] == n)]
            if r.empty:
                continue
            a, b = r["first"].iloc[0], r["final"].iloc[0]
            ax.plot([a, b], [i + dy, i + dy], color=COLOR[ckey], lw=2.4, solid_capstyle="round")
            ax.plot(a, i + dy, marker="o", mfc=SURFACE, mec=COLOR[ckey], mew=1.8, ms=6.5, zorder=4)
            ax.plot(b, i + dy, marker=MARKER[ckey], color=COLOR[ckey], mec=SURFACE, ms=8, zorder=5)
        if i % 3 == 2 and i < len(cases) - 1:
            ax.axhline(i + 0.5, color=GRID, lw=1.0)
    ax.set_yticks(range(len(cases)))
    ax.set_yticklabels([f"{m} · {n}" for m, n in cases])
    ax.set_ylim(len(cases) - 0.5, -0.5)
    ax.grid(axis="y", visible=False)
    ax.axvline(1.0, color=INK2, lw=0.9)
    ax.set_xlabel("sum-of-costs ÷ lower bound (1.0 = no agent delayed)")
    handles = [Line2D([], [], color=COLOR["LaCAM*"], marker=MARKER["LaCAM*"], mec=SURFACE, lw=2.4,
                      ms=8, label="LaCAM* (anytime)"),
               Line2D([], [], color=COLOR["LNS2"], marker=MARKER["LNS2"], mec=SURFACE, lw=2.4,
                      ms=8, label="MAPF-LNS (anytime)"),
               Line2D([], [], color=INK2, marker="o", mfc=SURFACE, mec=INK2, mew=1.8, lw=0, ms=6.5,
                      label="first solution"),
               Line2D([], [], color=INK2, marker="o", mec=SURFACE, lw=0, ms=8,
                      label="after 60 s")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 0.955), ncol=4,
               columnspacing=1.4)
    fig.subplots_adjust(top=1 - 1.25 / (0.36 * len(cases) + 1.0))
    suptitle(fig, "From first solution to 60 s: LaCAM* barely moves, MAPF-LNS keeps improving",
             y=1.0)
    save(fig, "fig13_anytime_dumbbell")


def tables(df, agg_df):
    out = RES / "tables"
    out.mkdir(exist_ok=True)
    agg_df.sort_values(["category", "map_name", "planner", "N"]).to_csv(
        out / "per_map_planner_N.csv", index=False)
    summ = []
    for (p, m), s in df.groupby(["planner", "map_name"]):
        solved = s[s["success"]]
        summ.append(dict(planner=p, map=m, category=s["category"].iloc[0],
                         instances=len(s), solved=int(s["success"].sum()),
                         solved_pct=round(100 * s["success"].mean(), 1),
                         median_runtime_ms=round(solved["runtime_ms"].median(), 1)
                         if len(solved) else None,
                         median_soc_ratio=round(solved["soc_ratio"].median(), 3)
                         if len(solved) else None))
    pd.DataFrame(summ).to_csv(out / "summary_per_map.csv", index=False)
    print("wrote tables to", out)


def main():
    global FONT_SCALE, FIG
    if "--slides" in sys.argv:
        sys.argv.remove("--slides")
        FONT_SCALE = 1.4
        FIG = FIG / "slides"
    style()
    np.seterr(invalid="ignore")
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    want = set(sys.argv[1:])

    def on(name):
        return not want or name in want

    if on("maps"):
        fig_maps()
    if on("progress"):
        fig_progress()
    if on("congestion"):
        fig_congestion()
    if on("anytime"):
        fig_anytime()
    df = load("main")
    if df is not None:
        agg_df = aggregate(df)  # skipped (early-stopped) runs count as failures
        for kind in ("success", "runtime", "quality"):
            if not on(kind):
                continue
            if FONT_SCALE > 1:  # slides: warehouse and other domains as separate figures
                wh = [m for m in MAP_ORDER[:7] if m in set(df["map_name"])]
                ot = [m for m in MAP_ORDER[7:] if m in set(df["map_name"])]
                fig_metric(df, agg_df, kind, wh, "_warehouse", " · warehouse maps")
                fig_metric(df, agg_df, kind, ot, "_other", " · other domains")
            else:
                fig_metric(df, agg_df, kind)
        if on("cactus"):
            fig_cactus(df)
        if on("scalability"):
            fig_scalability(df)
        if on("ablation"):
            fig_ablation(df)
        if on("effort"):
            fig_search_effort(df)
        if on("tradeoff"):
            fig_tradeoff(df)
        if on("paired"):
            fig_paired_quality(df)
        if on("tables"):
            tables(df, agg_df)


if __name__ == "__main__":
    main()
