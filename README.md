# LaCAM for warehouse multi-agent path finding — re-implementation & benchmark

This project re-implements **LaCAM** (Okumura, AAAI-23) and **LaCAM\*** (Okumura, IJCAI-23):
search-based MAPF planners that use **PIBT** as a one-step configuration generator.
It then benchmarks them against standalone PIBT and three state-of-the-art planners from other
algorithm families, on 7 warehouse layouts and 5 other domains.

**Conclusions and the reasoning for building on LaCAM\*: [COMPARISON.md](COMPARISON.md).**

## What is in here

| Path | Content |
|---|---|
| `src/` | **Our C++17 implementation**: PIBT configuration generator (+ LaCAM\* swap technique), LaCAM / LaCAM\* search, standalone PIBT, independent solution checker |
| `tools/build_lacam.bat` | builds `build/mapf_lacam.exe` (MSVC 2019, x64) |
| `tools/build_baselines.bat` | builds the official EECBS, MAPF-LNS2 and PBS code (`third_party/`, patches documented in `third_party/PATCHES.md`) |
| `tools/build_official_lacam.bat` | builds the official LaCAM / LaCAM\* code, used only to validate our re-implementation |
| `tools/gen_warehouses.py` | generates the three custom warehouse layouts + scenarios (`data/maps`, `data/scens`) |
| `tools/run_experiments.py` | parallel, resumable benchmark runner with early stopping (`results/*.jsonl`) |
| `tools/special_runs.py` | progress traces and full solutions behind the explanatory figures |
| `tools/make_figures.py`, `tools/animate.py` | all figures (`figures/`) and summary tables (`results/tables/`) |
| `tools/mapf_utils.py` | map/scenario loading and the Python solution validator used for every baseline |
| `deck_source/` | HTML source of the presentation deck (`project/deck.json`, `project/slides/*.html`); the published copy is on claude.ai |

## Planners

| Name in figures | What it is | Code |
|---|---|---|
| **LaCAM\*** | LaCAM + PIBT swap technique + random restarts, first solution (IJCAI-23) | ours |
| **LaCAM** | original LaCAM, PIBT generator, lazy constraints, DFS (AAAI-23) | ours |
| **PIBT** | PIBT run step by step with no search on top ("PIBT without LaCAM") | ours |
| PIBT + swap | standalone PIBT with the swap technique (ablation) | ours |
| LaCAM\*-anytime | LaCAM\* kept running to refine its solution (eventually optimal) | ours |
| **EECBS** (w = 1.2) | bounded-suboptimal conflict-based search (Li et al., AAAI-21) | official |
| **MAPF-LNS2** | prioritised planning + large-neighbourhood collision repair (Li et al., AAAI-22) | official |
| **PBS** | priority-based search (Ma et al., AAAI-19) | official |
| LNS-anytime | MAPF-LNS anytime refinement started from LNS2 (Li et al., IJCAI-21) | official |

PIBT, LaCAM and LaCAM\* share one PIBT routine (`src/pibt.cpp`), so "PIBT vs LaCAM" isolates
exactly the contribution of LaCAM's search layer.

## Fidelity check against the official LaCAM code

With the same seed, our planners make the same random choices as the official ones and
return identical solutions:

| Instance | Official | Ours |
|---|---|---|
| random-32-32-20, 200 agents, LaCAM | SoC 8606, makespan 102, 10 ms | SoC 8606, makespan 102, 9 ms |
| warehouse-10-20-10-2-1, 500 agents, LaCAM\* (first) | SoC 80782, makespan 304, 59 ms | SoC 80782, makespan 304, 48 ms |
| warehouse-10-20-10-2-1, 300–500 agents, LaCAM | fails within 10 s (5/5) | fails within 10 s (5/5) |
| random-32-32-20, 100 agents, LaCAM\* anytime 10 s | 2814 → 2812, final SoC 3096 | 2814 → 2812, final SoC 3096 |

Systematic check (`tools/validate_reimplementation.py` → `results/fidelity.csv`): 48 instances (2 agent counts ×
2 scenarios × 12 maps), 10 s limit, seed 0, official code built with the same compiler and flags.

| | Same success / failure | Identical SoC and makespan | Runtime ours ÷ official (median) |
|---|---|---|---|
| LaCAM | 48 / 48 | 38 / 38 solved | 0.81 |
| LaCAM\* (first solution) | 48 / 48 | **48 / 48** | 0.87 |

The runtime ratio is 0.76–0.77 on the instances where the official run takes at least 10 ms (its timer has 1 ms
resolution).

Against the official LaCAM\* exactly as published, 2 of the 48 plans differ (narrowaisle 300 agents: 46,331 vs
46,750; maze-32-32-4 150 agents: 16,773 vs 15,950; kept in `results/fidelity_official_as_built.csv`). We traced this
to the official distance table (`dist_table.cpp` uses a reference to a queue element after `pop()`, which is
undefined behaviour): under MSVC it returns wrong distances for some agents, which is visible as a makespan lower
bound of 3,250 (the vertex count) in its output and makes the search start with the wrong agent order. The first
differing move of every such agent is an exact distance tie, so the plans are still valid, just tie-broken
differently. The original LaCAM (v1) copies the element and is not affected. After changing that one line
(documented in `third_party/PATCHES.md`) the official code reproduces ours on all 48 instances.

## Experimental protocol

* 30 s time limit per run; 4 runs in parallel on a Ryzen 7 7840HS laptop (Windows 11), MSVC 2019 `/O2` for every planner.
* Warehouse maps: 10 scenarios per agent count; other domains: 5. MovingAI "random" scenarios; custom maps use uniformly random start/goal pairs.
* Agent counts per map up to 1000. Once a planner solves **none** of the instances at some count, larger counts on that map are skipped and counted as failures (early stopping). Of the 5,320 planner-instance pairs
  (7 planners × 760), 4,500 were executed and 820 skipped this way.
* Runtime = the planner's own measurement including its heuristic/distance-table pre-processing, excluding file loading.
* PIBT is declared failed if not all agents are on their goals within 10,000 timesteps.
* Memory cap 1.2 GB per run (LaCAM stops itself; baselines are killed by a watchdog) — flagged `memout` in the data.
* Every solution is validated (vertex and swap conflicts, legal moves, start/goal) and all costs are recomputed by one validator; SoC = sum of arrival times, lower bound = sum of shortest-path distances.

## Results (main benchmark: 760 instances per planner, 30 s limit)

| Planner | Warehouse solved (/560) | Other solved (/200) | Median time, warehouse | Median SoC / LB, warehouse |
|---|---|---|---|---|
| **LaCAM\*** | **560 (100 %)** | **200 (100 %)** | **45 ms** | 1.48 |
| LaCAM | 356 (64 %) | 180 (90 %) | 69 ms | 1.37 |
| PIBT | 265 (47 %) | 146 (73 %) | 51 ms | 1.32 |
| PIBT + swap | 528 (94 %) | 197 (99 %) | 43 ms | 1.45 |
| EECBS (w = 1.2) | 425 (76 %) | 110 (55 %) | 2.3 s | 1.01 |
| MAPF-LNS2 | 481 (86 %) | 173 (87 %) | 1.6 s | 1.22 |
| PBS | 289 (52 %) | 87 (44 %) | 3.1 s | 1.00 |

Medians of time and quality are over each planner's own solved instances. Paired on instances both solved,
LaCAM\* is 35× / 44× / 84× faster than MAPF-LNS2 / EECBS / PBS (median) and its sum-of-costs is
1.14× / 1.31× / 1.26× theirs. At 1,000 agents on warehouse maps, success rates are LaCAM\* 100 %,
PIBT + swap 84 %, MAPF-LNS2 47 %, LaCAM 43 %, PIBT 43 %, EECBS 41 %, PBS 0 %.

What the data says about LaCAM itself:

* **Search is free when PIBT works.** On instances standalone PIBT solves, LaCAM generates exactly one PIBT rollout
  (configurations ÷ (makespan + 1) = 1.00, median). Where PIBT fails, the original LaCAM needs 11× more but still
  solves 125 such instances; it detects PIBT's livelock as revisited configurations (20–30 % of successors on warehouses).
* **Swap vs. search fix different failures.** 1-wide aisles/maze: swap (warehouse-10-20-10-2-1: PIBT 5 %, PIBT + swap 98 %,
  LaCAM 25 %). Random obstacles: search (PIBT + swap 92 %, LaCAM 100 %). Dead-end aisles: both (62 %, 0 %, LaCAM\* 100 %).
* **Anytime refinement is weak and memory-bound.** In 60 s LaCAM\* improves its first solution by 1.7 % (median); 33 of 45
  runs reach the 1.2 GB cap after ~19 s. MAPF-LNS improves 11.4 % but needs 0.5 s for its first solution vs 14 ms.
* **Congestion depends on layout.** With 1-wide lanes 90–94 % of waits happen inside the lanes; in the dead-end layout
  83 % happen at junction cells where aisles meet the corridors.

## Figures

`figures/` holds print versions (PNG + PDF); `figures/slides/` the same charts with larger text for slides.

| File | Shows |
|---|---|
| `fig00_maps` | the 12 benchmark maps |
| `fig01_success_rate` | success rate vs agents, per map |
| `fig02_runtime` | median time to solution vs agents, per map |
| `fig03_quality` | sum-of-costs ÷ lower bound vs agents, per map |
| `fig04_cactus` | instances solved vs time budget |
| `fig05_scalability` | % solved and largest reliable agent count, map × planner |
| `fig06_ablation` | PIBT / PIBT + swap / LaCAM / LaCAM\* per map |
| `fig07_pibt_livelock` | agents-on-goal traces: PIBT livelocks, LaCAM escapes |
| `fig08_search_effort` | LaCAM's search effort vs whether PIBT alone would succeed |
| `fig09_congestion` | where agents wait in LaCAM\* solutions |
| `fig10_tradeoff` | speed vs quality per planner |
| `fig11_paired_quality` | LaCAM\* cost relative to each planner on shared instances |
| `fig12_anytime`, `fig13_anytime_dumbbell` | LaCAM\* vs MAPF-LNS anytime refinement |
| `anim_pibt_vs_lacam_narrowaisle.gif` (+ `_strip.png`) | PIBT stalls, LaCAM\* finishes (100 agents, dead-end aisles) |
| `anim_lacam_warehouse_500.gif` | LaCAM\* with 500 agents on warehouse-10-20-10-2-1 |

Raw data: `results/main.jsonl`, `results/anytime.jsonl`, `results/fidelity.csv`; summaries in `results/tables/`.

## Reproduce

```bat
tools\fetch_third_party.bat
tools\build_lacam.bat
tools\build_baselines.bat
python tools\gen_warehouses.py --out data
python tools\run_experiments.py --suite main --workers 4
python tools\run_experiments.py --suite anytime --workers 4
python tools\special_runs.py
python tools\make_figures.py
python tools\animate.py
```

The MovingAI benchmark files go in `data/raw/` (download `mapf-map.zip` and `mapf-scen-random.zip` from <https://movingai.com/benchmarks/mapf/>).
