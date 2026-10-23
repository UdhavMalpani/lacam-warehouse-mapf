# Planner comparison: what we concluded and why LaCAM\* (PIBT + search) goes forward

This branch records the one-shot MAPF benchmark that decided which planner family we build on.
The next phase is a **lifelong** warehouse setting: goals keep arriving, agents dwell at goals for
an unknown time, and priorities change dynamically. Setup, raw data and figures are described in
[README.md](README.md). This page covers the reasoning.

## 1. Question

Our target is large warehouse fleets (hundreds to 1,000 robots) that must be replanned often.
We needed a planner that:

1. **almost never fails** at high density, including 1-wide aisles and dead-end aisles,
2. is **fast enough to replan every few timesteps** (tens of ms, not seconds),
3. produces plans of **acceptable** quality. Optimal quality is not required, because plans are
   thrown away and recomputed anyway.

## 2. How we tested it

* **Planners.** We used 7, from 3 algorithm families:
  * *Rule-based:* PIBT and PIBT + swap.
  * *Search over PIBT:* LaCAM and LaCAM\*. These are our C++ re-implementation, and all four of
    these planners share one PIBT routine, so differences between them isolate the search layer.
  * *Optimisation/search baselines:* EECBS (w = 1.2), MAPF-LNS2 and PBS, using the official code.
* **Fidelity check.** Our LaCAM / LaCAM\* gives byte-identical solutions to the official code on
  48/48 instances with the same seed. On the way we found and fixed undefined behaviour in the
  official LaCAM\* distance table. Details are in [README.md](README.md) and
  [third_party/PATCHES.md](third_party/PATCHES.md).
* **Instances.** There are 760 instances per planner: 7 warehouse layouts (the 4 MovingAI
  warehouses plus our *crossdock*, *sortation* and *narrowaisle* layouts) and 5 other domains, with up to
  1,000 agents.
* **Rules.** Each run gets a 30 s limit and a 1.2 GB memory cap. Every solution is checked by one
  independent validator, and all costs are recomputed by that validator. Runtime includes
  pre-processing.

## 3. Results

| Planner | Warehouse solved | Other solved | Median time (warehouse) | Median SoC / lower bound |
|---|---|---|---|---|
| **LaCAM\*** | **560/560 (100 %)** | **200/200** | **45 ms** | 1.48 |
| PIBT + swap | 528 (94 %) | 197 | 43 ms | 1.45 |
| MAPF-LNS2 | 481 (86 %) | 173 | 1.6 s | 1.22 |
| EECBS | 425 (76 %) | 110 | 2.3 s | 1.01 |
| LaCAM | 356 (64 %) | 180 | 69 ms | 1.37 |
| PIBT | 265 (47 %) | 146 | 51 ms | 1.32 |
| PBS | 289 (52 %) | 87 | 3.1 s | 1.00 |

At **1,000 agents** on warehouse maps the success rates are: LaCAM\* 100 %, PIBT + swap 84 %,
MAPF-LNS2 47 %, LaCAM 43 %, PIBT 43 %, EECBS 41 %, PBS 0 %.

Per-layout success at the hardest warehouses:

| Map | PIBT | PIBT + swap | LaCAM | **LaCAM\*** | LNS2 | EECBS | PBS |
|---|---|---|---|---|---|---|---|
| narrowaisle (dead ends) | 0 % | 62 % | 0 % | **100 %** | 52 % | 24 % | 11 % |
| warehouse-10-20-10-2-1 (1-wide) | 5 % | 98 % | 25 % | **100 %** | 76 % | 61 % | 36 % |
| sortation | 12 % | 100 % | 65 % | **100 %** | 88 % | 60 % | 39 % |

## 4. Conclusions

1. **LaCAM\* is the only planner that solved everything.** That includes every warehouse
   instance up to 1,000 agents, at a median of 45 ms.
2. **PIBT is the right primitive, but it is not enough on its own.** PIBT livelocks in narrow and
   dead-end aisles (0–12 % success there). Two different fixes are needed, and they cover
   different failures:
   * The *swap* technique fixes head-on conflicts in 1-wide aisles (5 % → 98 %).
   * LaCAM's *search* fixes livelock on random obstacles: it notices repeated configurations and
     backtracks.
   * Dead-end aisles need **both**: swap alone reaches 62 %, search alone 0 %, and together
     (LaCAM\*) 100 %.
3. **The search costs nothing when PIBT already works.** On instances that PIBT solves alone,
   LaCAM generates exactly one PIBT rollout (configurations ÷ (makespan + 1) = 1.00). The search
   only does extra work where PIBT would fail.
4. **Quality is the price.** Paired on instances both planners solved, LaCAM\*'s sum-of-costs is
   1.14× MAPF-LNS2, 1.31× EECBS and 1.26× PBS. But LaCAM\* is 35–84× faster. LaCAM\*'s anytime
   refinement is weak (1.7 % improvement in 60 s, and it hits the memory cap). MAPF-LNS improves
   by 11 %.
5. **Congestion depends on the layout.** With 1-wide lanes, 90–94 % of waits happen inside the
   lanes. In the dead-end layout, 83 % happen at junctions. That makes traffic-aware priorities
   and guidance the natural place to recover quality.

## 5. Why we carry PIBT/LaCAM\* into the lifelong setting

* **Replanning budget.** In lifelong operation the planner runs every few timesteps. Only the
  PIBT family fits a sub-100 ms budget at 1,000 agents. EECBS, PBS and LNS2 need seconds and still
  fail on 14–48 % of warehouse instances.
* **Robustness matters more than optimality.** A failed replan stops the fleet. A 1.3× costlier
  plan only lowers throughput a little, and the next replan corrects it anyway.
* **The extensions fit naturally.** Two features we need are hard to add to CBS-style search but
  easy here:
  * Agents dwelling at a goal become *temporary static obstacles*.
  * *Dynamic priorities* come from queue length and distance to goal. PIBT is a priority-inheritance
    scheme, so these are just a different priority function.
* **The weakness has a known remedy.** Quality and throughput can be improved with priority
  design and traffic guidance, as the League of Robot Runners winners did. We do not need to
  switch to slow optimal search for this.

Next step: lifelong LaCAM\* with task assignment, uncertain dwell times and dynamic priorities.
We will then benchmark it against the two strongest current lifelong MAPF systems on the same
simulator.
