# Windows / MSVC portability notes for the MAPF baselines

The baselines are Jiaoyang Li's official solvers, built on Windows 11 with MSVC 2019 (14.29), x64:

| Repo | Commit | Executable |
|---|---|---|
| `third_party/EECBS` | `06ec70585dc4ad73177580a4ef91138335fd4d24` (2024-07-24) | `build/eecbs.exe` |
| `third_party/MAPF-LNS2` | `1369823985a15944f9a339226d521f61605a6d17` (2024-05-09) | `build/lns.exe` |
| `third_party/PBS` | `d7b91fa5abdbb1376e8fc2cffa995a84eac811df` (2025-04-28) | `build/pbs.exe` |

**No source file inside the three repos was modified, and `git status` is clean in each.**
Every fix lives outside the repos in three places:

1. `tools/msvc_compat.h` is force-included (`cl /FI`) into every solver translation unit.
2. `tools/include_shim/eigen3/Eigen/Core` is an include-path shim (MAPF-LNS2 only).
3. `tools/build_baselines.bat` holds the build flags.

The algorithms are unchanged. The only intended behavioural effect is in section 3: `rand()` now
behaves exactly like glibc's.

Build: `tools\build_baselines.bat [eecbs] [lns] [pbs]` (default builds all three; a clean build takes about 20 s).

---

## 1. `tools/msvc_compat.h` (forced include, all three solvers)

| # | Problem on MSVC | Where | Fix in `msvc_compat.h` |
|---|---|---|---|
| 1a | Alternative tokens `and` / `or` / `not` are not keywords in MSVC's default (non-`/permissive-`) mode. You get `C2146: missing ')' before identifier 'and'`. | All three repos, e.g. EECBS `src/ConstraintTable.cpp:279`, PBS `src/PBS.cpp`, LNS2 `src/InitLNS.cpp` | `#include <ciso646>`, which defines them as macros on MSVC. |
| 1b | Missing standard includes that libstdc++ pulls in transitively: `std::to_string` (needs `<string>`) and `std::iota` (needs `<numeric>`). You get `C2039` / `C3861`. | LNS2 `src/PIBT/grid.cpp`, `mapf.cpp`, `pibt_agent.cpp`, `problem.cpp`, `task.cpp` (`to_string`); `src/PIBT/winpibt.cpp` (`iota`) | The header pre-includes `<string>` and `<numeric>`, plus `<algorithm> <array> <cassert> <cfloat> <climits> <cmath> <cstddef> <cstdint> <cstdio> <cstdlib> <cstring> <ctime> <functional> <iterator> <limits> <random> <utility>`. Only `<string>` and `<numeric>` were strictly needed (checked by compiling with a stripped header). The rest are included so that the RNG macros in section 3 are defined after all standard-library headers are processed. |
| 1c | PIBT names constructor parameters `_MT` (e.g. `Graph(std::mt19937* _MT)`). MSVC predefines the macro `_MT` (=1) for the multithreaded CRT, so the declaration becomes `std::mt19937* 1` and you get `C2143`. | LNS2 `inc/PIBT/{graph,grid,simplegrid,problem,mapf,pibt,pps,solver,winpibt}.h` and the matching `src/PIBT/*.cpp` (22 uses in 18 files) | `#include <boost/config.hpp>` then `#undef _MT`. No MSVC STL or UCRT header tests `_MT`. Boost tests only `defined(_MT)`, in `boost/config/detail/suffix.hpp` (to set `BOOST_HAS_THREADS`) and in auto_link (disabled). Including `boost/config.hpp` first keeps Boost's configuration identical to the program_options objects, which are compiled without `/FI`. |
| 1d | `RAND_MAX` is 32767 on MSVC (2147483647 on glibc), and `std::random_shuffle` is implemented differently. | See section 3 | glibc-identical `rand`/`srand`/`RAND_MAX` and libstdc++-identical `random_shuffle` |

Other hazards were checked and **not present**: POSIX headers (`unistd.h`, `sys/time.h`), `uint`/`ssize_t`/`ulong`,
`__builtin_*`, `__attribute__`, `M_PI`, VLAs, and `long`-width assumptions.

`/std:c++14` is required: MAPF-LNS2 calls `std::random_shuffle`, which was removed in C++17.

## 2. `tools/include_shim/eigen3/Eigen/Core` (MAPF-LNS2)

`inc/PIBT/solver.h` does `#include <eigen3/Eigen/Core>`. That path only exists with the Debian/Ubuntu layout
(`/usr/include/eigen3`). The Eigen 3.4 tarball (`deps/eigen-3.4.0`) has `Eigen/Core` at its root.
The shim is a one-line forwarder, `#include <Eigen/Core>`. Eigen is used only for `Eigen::MatrixXi dists` in the PIBT solver.

## 3. Randomness: the RAND_MAX finding and fix

### What uses `rand()`

**EECBS and PBS**

- The drivers call `srand((int)time(0))` before loading the instance and `srand(0)` after it.
- `rand() % 2` is used for tie-breaking: `SingleAgentSolver.h` open-list comparators and `Conflict.cpp`. EECBS also uses it in `CBS::addConstraints`, but only with `--disjointSplitting`, which is off by default.
- `rand() % map_size`, `% num_of_rows` and similar appear only in `Instance`'s random map and agent generator, which runs only when the map or scen file does not exist.
- **Not affected by RAND_MAX:** a 50/50 coin is unbiased either way.

**MAPF-LNS2** (`--seed`, default 0, passed to `srand(seed)` after loading)

These call sites **are affected**, because `X` can exceed 32767:

- `LNS::generateNeighborByIntersection`: `rand() % intersections.size()`. `intersections` holds every free cell with degree > 2. On large maps there are more than 32767: Berlin_1_256 has 46,113. With MSVC's `rand()`, about 29% of them (the highest linear indices, i.e. the bottom rows of the map) could never seed the Intersection destroy heuristic.
- `InitLNS::generateNeighborByTarget`: `rand() % (num_of_colliding_pairs * 2)`. `InitLNS::generateNeighborRandomly`: `rand() % (num_of_colliding_pairs * 2 + agents.size())`. When an initial plan has more than about 16k colliding pairs (thousands of agents), agent selection becomes biased towards low agent ids.
- `InitLNS::generateNeighborByCollisionGraph`: `all_vertices[rand() % all_vertices.size()]`. Affected only with more than 32767 colliding agents.
- `LNS::findRandomAgent`: `rand() % (sum_of_costs - sum_of_distances)` would be affected, but it is dead code (never called).

These call sites have smaller effects:

- `BasicLNS::rouletteWheel`: `(double)rand() / RAND_MAX`, used for ALNS destroy-heuristic selection. Resolution is 15-bit instead of 31-bit.
- `std::random_shuffle` is used for the PP agent order in `LNS::runPP` / `InitLNS::runPP` (initial solution and replans), for neighbourhood truncation, and in `generateNeighborByTarget`. MSVC's version uses its own algorithm (a URNG adaptor over `::rand()`) instead of libstdc++'s `rand() % (i+1)`. If only `srand` were redirected, it would also stop being seeded by `--seed`.
- Small moduli (path length, number of neighbours, makespan in `PathTable::get_agents`) are unaffected by RAND_MAX but draw from the same stream.

These do **not** use `rand()` and were left unchanged:

- PIBT/winPIBT/PPS (`std::mt19937` seeded with 0 or `random_device`, plus `std::shuffle` / `uniform_int_distribution`). These are only used with `--initAlgo=PIBT|winPIBT|PPS`.
- EECBS `CBS::shuffleAgents` / `generateRoot` (`random_device`). These only run with `--restart > 0` after a failed run.
- `Instance::randomWalk` (`default_random_engine`, random-instance generation only).

The distribution algorithms in `<random>` are implementation-defined, so these differ from a Linux build. They are not RAND_MAX-related.

### Fix

`msvc_compat.h` makes these changes:

- `portable_rand()` / `portable_srand(unsigned)` are an exact re-implementation of glibc's `random_r.c`, TYPE_3: an additive-feedback generator of degree 31 and separation 3, the generator behind glibc `rand()`. Seeding uses Schrage's method followed by 310 discarded outputs. `srand(0)` is treated as `srand(1)`, as in glibc. The output range is [0, 2^31 − 1].
- `RAND_MAX` is redefined to 2147483647.
- `portable_random_shuffle(first, last)` is libstdc++'s algorithm, `j = first + rand() % ((i - first) + 1)`, checked against `bits/stl_algo.h`. A 3-argument overload is also provided.
- The macros `rand`, `srand` and `random_shuffle` map to the portable versions. `using` declarations in namespace `std` make `std::rand()` and `std::random_shuffle(...)` resolve as well.
- All standard headers are included *before* the macros, so the STL's own declarations are untouched.

Verification:

- Standalone test compiled with the header at `/W4` with no warnings.
- Seed 1 (and seed 0) gives 1804289383, 846930886, 1681692777, 1714636915, 1957747793, … and seed 42 gives 71876166, 708592740, 1483128881, …. These are the glibc reference values.
- LNS2 runs are reproducible for a given `--seed`, as long as no time-based cut-off is hit (replans and InitLNS iterations are time-bounded). `--seed 0` and `--seed 1` give identical runs, as they do on Linux.

Consequence: the `rand()` and `random_shuffle` streams are bit-identical to a Linux/glibc build. Whole-run results can
still differ from Linux wherever other implementation-defined STL behaviour enters (for example, the order of equal
elements after `std::sort`, hash/unordered iteration order, or `<random>` distributions).

## 4. Build details (`tools/build_baselines.bat`)

- **Flags:** `/nologo /O2 /Ob2 /Oi /GL /DNDEBUG /EHsc /std:c++14 /MP /W1 /bigobj /DBOOST_ALL_NO_LIB /DNOMINMAX` and `/FI tools\msvc_compat.h`, linked with `/link /LTCG /STACK:268435456`. The default static CRT (`/MT`) means the executables depend only on `KERNEL32.dll`.
- **Boost:** there are no prebuilt Boost libs. `boost_1_83_0/libs/program_options/src/*.cpp` is compiled once into `build/obj_boost_po/` (no `/FI`) and linked into each executable. Boost auto-linking is disabled.
- **Object directories:** `build/obj_eecbs/`, `build/obj_lns/{,CBS,PIBT}/` and `build/obj_pbs/`.
- **Include paths:** each repo's `inc` dirs (LNS2: `inc inc/CBS inc/PIBT`), Boost, and for LNS2 also Eigen and the shim.
- **vcvars64:** `vcvars64.bat` is called only if `VCToolsInstallDir` is unset. The VS Installer dir is appended to `PATH` so vcvars can find `vswhere.exe`.
- **Remaining warnings:** only C4267 (size_t → int) inside STL template instantiations, e.g. EECBS `ConstraintTable.cpp:208` `emplace_back(size_t, int)` into a `list<pair<int,int>>`. This is the same implicit narrowing GCC performs, and it is harmless.

## 5. Output semantics (for the benchmark harness)

### (a) The `runtime` column

All values are in **seconds**.

| Solver | Timer starts | Includes | Excludes |
|---|---|---|---|
| EECBS | Start of `ECBS::solve()` | Root generation (low-level search for every agent) and the high-level search with its heuristics. With `--restart N`, it is the sum over all runs. | Instance loading, and the per-agent preprocessing in the `CBS` constructor (each `SIPP`/`SpaceTimeAStar` constructor runs a full-map BFS from its goal). That preprocessing is reported separately in the `preprocessing runtime` column. |
| PBS | Start of `PBS::solve()` | Root generation and the high-level search | Instance loading, and the constructor's per-agent BFS (`preprocessing runtime` column) |
| MAPF-LNS2 | Start of `LNS::run()` | The initial solution (PP; if PP fails, the InitLNS repair). With `--maxIterations=0` (the default) nothing else, so `runtime` equals `runtime of initial solution`, the time to the first feasible solution. With `maxIterations > 0`, the LNS improvement iterations are added. | Instance loading and the `LNS` constructor (per-agent SIPP plus BFS heuristic), reported in `preprocessing runtime` |

For MAPF-LNS2, `X-initLNS.csv`'s `runtime` covers only the InitLNS phase and excludes the failed PP attempt.

### (b) Failure values and detection

**EECBS**

- `solution cost` is the sum of costs on success.
- `-1` means timeout, or the high-level node limit was hit (screen prints `Timeout`).
- `-2` means the open/cleanup list was exhausted (`No solutions`). This should not occur for EECBS; unsolvable start/goal pairs `exit(-1)` during root generation instead, with no CSV row.
- `-3` is never assigned.

**PBS**

- `solution cost` is the sum of costs on success.
- `-1` means timeout or node limit (screen prints `Timeout`).
- `-2` means the PBS search was exhausted. PBS is incomplete, so this can happen on dense instances. Nothing is printed after the solver name in that case.
- If root generation fails ("No path exists for agent i"), `saveResults` dereferences a null root and crashes. This only happens for disconnected start/goal pairs.

**MAPF-LNS2**

On failure:

- stdout prints `Failed to find an initial solution in <t> seconds after <n> restarts`.
- `X-LNS.csv` gets a row with `initial solution cost = -1`, `solution cost = 0` and `group size = -1`. **Use `initial solution cost == -1` as the failure test.**
- If InitLNS ran, `X-initLNS.csv` has `num of collisions > 0`. Its `solution cost` there is the cost of an infeasible, colliding plan, so do not use it.

**All three solvers**

- The paths file is written **only on success**.
- The process exit code is 0 on both success and failure. It is `exit(-1)` only for input errors and invalid solutions.

**Harness gotchas**

- All three **append** a row to an existing CSV and write the header only when they create the file. Use one file per run, or read the last row.
- LNS2's `-o X` is a prefix: it writes `X-LNS.csv`, plus `X-initLNS.csv` when InitLNS runs.
- If the `-a` scen path does not exist and `k > 0`, the solvers *generate random agents and write them to that path*. Check that paths exist before launching.

### (c) How the time limit is checked

**EECBS and PBS use `clock()`**

- It is compared with `-t` in `terminate()` before each high-level node expansion.
- EECBS's WDG heuristic gets the remaining budget and checks it with whole-second integer division.
- Root generation and the low-level searches are not interrupted, so the limit can be overshot. Observed: 2.004 s and 2.001 s for `-t 2`.

**MAPF-LNS2 uses `std::chrono::high_resolution_clock`**

- This is wall time on both operating systems: `steady_clock`/QPC on MSVC, `system_clock` on libstdc++. Values are held in `duration<float>` seconds.
- The clock is checked between agents inside PP and once per InitLNS or LNS iteration. Each LNS replan is capped at `t/100`. Observed: 0.0595 s for `-t 0.05`.

**Windows `clock()` is wall time.** On Windows, `clock()` returns wall time since process start (`CLOCKS_PER_SEC` = 1000, so runtimes have 1 ms resolution). glibc's `clock()` returns process CPU time.

- For single-threaded, CPU-bound runs the two are nearly equal.
- On Windows, any time the process is descheduled counts towards EECBS/PBS runtime and their time limit. Examples are oversubscribing cores with parallel runs, or power-saving.
- Run at most one job per physical core, and time LaCAM with a wall clock as well.

### (d) Path file format

- There is one line per agent, ordered by id 0..k−1.
  - EECBS and PBS write `Agent <i>: (r,c)->(r,c)->...->` (a space after the colon and a trailing `->`).
  - LNS2 (`LNS::writePathsToFile`) writes `Agent <i>:(r,c)->(r,c)->...->` (no space after the colon).
- Entry `t` is the cell occupied at timestep `t`, and entry 0 is the start.
- Coordinates are **(row, col) = (y, x)**, with `row = loc / width` and `col = loc % width`. A MovingAI scen's `start_x start_y` becomes `(start_y, start_x)`.
- LaCAM writes (x, y), so swap the coordinates when comparing.
- Files are written in text mode, so lines end with CRLF on Windows.
- Any map character other than `.` counts as an obstacle. All benchmark maps contain only `.`, `@` and `T`, so the obstacle sets match LaCAM's.

### (e) Path cost convention

- Each path ends at the agent's **final** arrival at its goal. The agent may have passed through the goal earlier, and there are no trailing waits at the goal.
- After its path ends, the agent is assumed to stay at its goal forever. Target reasoning and goal-holding constraints guarantee that no later agent conflicts with it.
- The agent's cost is `len(path) − 1`, and `solution cost` = Σ(len − 1).
- This is the same as LaCAM's sum-of-costs: for each agent, the last timestep at which it is not yet at its goal, plus one.
- Verified with an independent validator on every smoke-test run. There were no vertex or swap conflicts, the path-derived SoC equalled the CSV `solution cost`, and the LaCAM-style recount matched.

---

## Official LaCAM / LaCAM\* (validation references only, not baselines)

`third_party/lacam` (AAAI-23) and `third_party/lacam2` (IJCAI-23) are built by `tools/build_official_lacam.bat`
only to check our re-implementation (`tools/validate_reimplementation.py`). Changes:

1. **`tools/uint_compat.h`** (forced include): `typedef unsigned int uint`, `<ciso646>` for the `or` token, and
   `#undef _MT` (MSVC predefines `_MT`, which clashes with the parameter name `_MT` in the planner).
2. **`main.cpp` of both repos**: the `Instance` is now built through a lambda instead of
   `cond ? Instance(a) : Instance(b)`. MSVC copies the result of `?:`, `Instance`/`Graph` own raw pointers and
   have no copy constructor, so the original crashed with a double free.
3. **`lacam2/src/dist_table.cpp`, a real bug fix**: the lazy BFS did
   `auto&& n = OPEN[i].front(); OPEN[i].pop();` and then used `n`, a reference to an already destroyed queue
   element (undefined behaviour). Changed to `auto n = ...` (by value). The element lives in a `std::deque`; MSVC's
   deque holds only 2 pointers per block, so the freed block is reused almost at once and some distances come
   out wrong (visible as an impossible makespan lower bound equal to the vertex count), whereas libstdc++'s
   64-pointer blocks make this far less likely to bite. `lacam` (v1) already copies by value and is not affected.

   Effect on the fidelity check (`results/fidelity_official_as_built.csv` vs `results/fidelity.csv`):
   with the original line, 2 of 48 LaCAM\* instances produce a different plan, because the wrong distances
   change the agents' initial priority order. All 23 first-step differences in one of them are exact
   distance ties broken differently. With the fix, our plans are identical to the official ones on 48 / 48.
