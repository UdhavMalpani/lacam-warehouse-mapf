// Command-line driver for the LaCAM / LaCAM* / PIBT re-implementation.
//
//   mapf_lacam.exe -m MAP -i SCEN -N AGENTS -a ALGO [-t SEC] [-s SEED] [-o OUT]
//                  [--log-solution] [--log-progress] [--max-steps K]
//                  [--restart-rate R] [--mem-limit-mb M] [-v]
//
// ALGO: lacam       LaCAM (AAAI-23): PIBT + lazy constraints, first solution
//       lacam_swap  LaCAM with the swap technique, first solution
//       lacam_star  LaCAM* (IJCAI-23): swap + anytime refinement (sum-of-loss)
//       lacam_star_first  LaCAM* returning its first solution (swap + restarts)//       pibt        standalone PIBT (no search)
//       pibt_swap   standalone PIBT with the swap technique
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>

#include "lacam.hpp"
#include "metrics.hpp"
#include "pibt_planner.hpp"

namespace {

struct Args {
  std::string map_file, scen_file, algo = "lacam", output;
  int N = 0;
  double time_limit_sec = 30.0;
  int seed = 0;
  int max_steps = 10000;
  float restart_rate = -1.0f;  // < 0: algorithm default
  double mem_limit_mb = 4000.0;
  bool log_solution = false;
  bool log_progress = false;
  bool verbose = false;
};

void usage()
{
  std::cerr << "usage: mapf_lacam -m MAP -i SCEN -N AGENTS -a {lacam,lacam_swap,lacam_star,pibt,"
               "pibt_swap} [-t SEC] [-s SEED] [-o OUT] [--log-solution] [--log-progress] "
               "[--max-steps K] [--restart-rate R] [--mem-limit-mb M] [-v]\n";
}

bool parse(int argc, char** argv, Args& a)
{
  for (int k = 1; k < argc; ++k) {
    const std::string s = argv[k];
    auto next = [&]() -> std::string {
      if (k + 1 >= argc) {
        std::cerr << "missing value for " << s << "\n";
        std::exit(2);
      }
      return argv[++k];
    };
    if (s == "-m") a.map_file = next();
    else if (s == "-i") a.scen_file = next();
    else if (s == "-N") a.N = std::stoi(next());
    else if (s == "-a") a.algo = next();
    else if (s == "-t") a.time_limit_sec = std::stod(next());
    else if (s == "-s") a.seed = std::stoi(next());
    else if (s == "-o") a.output = next();
    else if (s == "--max-steps") a.max_steps = std::stoi(next());
    else if (s == "--restart-rate") a.restart_rate = std::stof(next());
    else if (s == "--mem-limit-mb") a.mem_limit_mb = std::stod(next());
    else if (s == "--log-solution") a.log_solution = true;
    else if (s == "--log-progress") a.log_progress = true;
    else if (s == "-v") a.verbose = true;
    else {
      std::cerr << "unknown option " << s << "\n";
      return false;
    }
  }
  return !a.map_file.empty() && !a.scen_file.empty() && a.N > 0;
}

void write_config(std::ostream& os, const Graph& G, const Config& C)
{
  for (int v : C) os << "(" << G.x(v) << "," << G.y(v) << "),";
}

}  // namespace

int main(int argc, char** argv)
{
  Args args;
  if (!parse(argc, argv, args)) {
    usage();
    return 2;
  }
  const bool is_lacam = args.algo.rfind("lacam", 0) == 0;
  const bool is_pibt = args.algo == "pibt" || args.algo == "pibt_swap";
  if (!is_lacam && !is_pibt) {
    std::cerr << "unknown algorithm " << args.algo << "\n";
    return 2;
  }

  Instance ins;
  if (!ins.load(args.map_file, args.scen_file, args.N)) return 1;

  std::mt19937 MT(args.seed);
  Deadline deadline(args.time_limit_sec * 1000.0);  // includes building the distance table
  Solution solution;
  Solution trajectory;  // PIBT's partial trajectory when it fails
  SearchStats st;
  bool pibt_step_limit = false;

  if (is_lacam) {
    LaCAMParams p;
    if (args.algo == "lacam_swap") p.swap = true;
    if (args.algo == "lacam_star_first") {  // LaCAM* stopped at its first solution
      p.swap = true;
      p.restart_rate = 0.001f;
    }
    if (args.algo == "lacam_star") {
      p.swap = true;
      p.anytime = true;
      p.objective = Objective::SUM_OF_LOSS;
      p.restart_rate = 0.001f;
    }
    if (args.restart_rate >= 0.0f) p.restart_rate = args.restart_rate;
    p.mem_limit_mb = args.mem_limit_mb;
    LaCAM planner(ins, deadline, MT, p);
    solution = planner.solve();
    st = planner.stats;
  } else {
    PIBTPlanner planner(ins, deadline, MT, args.max_steps, args.algo == "pibt_swap");
    solution = planner.solve();
    st.loop_cnt = (long long)planner.trajectory.size() - 1;
    if (!solution.empty()) st.time_first_ms = deadline.elapsed_ms();
    pibt_step_limit = planner.hit_step_limit;
    if (solution.empty() && (args.log_progress || args.log_solution))
      trajectory = std::move(planner.trajectory);
  }
  const double comp_time_ms = deadline.elapsed_ms();

  // ---- evaluation (not timed) ----
  const bool solved = !solution.empty();
  std::string reason;
  const bool valid = solved && is_feasible(ins, solution, &reason);
  long long soc_lb = 0;
  int makespan_lb = 0;
  for (int i = 0; i < ins.N; ++i) {
    const int d = bfs_distances(ins.G, ins.goals[i])[ins.starts[i]];
    soc_lb += d;
    makespan_lb = std::max(makespan_lb, d);
  }

  std::ostringstream out;
  out << std::setprecision(10);
  out << "solver=" << args.algo << "\n";
  out << "map_file=" << args.map_file << "\n";
  out << "scen_file=" << args.scen_file << "\n";
  out << "agents=" << ins.N << "\n";
  out << "seed=" << args.seed << "\n";
  out << "time_limit_ms=" << args.time_limit_sec * 1000.0 << "\n";
  out << "solved=" << solved << "\n";
  out << "valid=" << valid << "\n";
  if (solved && !valid) out << "invalid_reason=" << reason << "\n";
  out << "comp_time_ms=" << comp_time_ms << "\n";
  out << "time_first_ms=" << st.time_first_ms << "\n";
  out << "soc=" << (solved ? get_sum_of_costs(ins, solution) : -1) << "\n";
  out << "soc_lb=" << soc_lb << "\n";
  out << "makespan=" << (solved ? get_makespan(solution) : -1) << "\n";
  out << "makespan_lb=" << makespan_lb << "\n";
  out << "sum_of_loss=" << (solved ? get_sum_of_loss(ins, solution) : -1) << "\n";
  out << "loop_cnt=" << st.loop_cnt << "\n";
  out << "hnodes=" << st.hnodes << "\n";
  out << "lnodes=" << st.lnodes << "\n";
  out << "pibt_calls=" << st.pibt_calls << "\n";
  out << "pibt_fail=" << st.pibt_fail << "\n";
  out << "revisits=" << st.revisits << "\n";
  out << "restarts=" << st.restarts << "\n";
  out << "rewires=" << st.rewires << "\n";
  out << "max_open=" << st.max_open << "\n";
  out << "cost_first=" << st.cost_first << "\n";
  out << "soc_first=" << st.soc_first << "\n";
  out << "makespan_first=" << st.makespan_first << "\n";
  out << "optimal=" << st.optimal << "\n";
  out << "mem_limit_hit=" << st.mem_limit_hit << "\n";
  out << "pibt_step_limit=" << pibt_step_limit << "\n";
  out << "anytime_log=";  // elapsed_ms:objective:sum_of_costs; per incumbent improvement
  for (auto& e : st.anytime_log) out << e.time_ms << ":" << e.cost << ":" << e.soc << ";";
  out << "\n";
  if (args.log_progress) {
    // number of agents standing on their goal at each timestep
    const Solution& traj = solved ? solution : trajectory;
    out << "progress=";
    for (const auto& C : traj) {
      int cnt = 0;
      for (int i = 0; i < ins.N; ++i) cnt += (C[i] == ins.goals[i]);
      out << cnt << ",";
    }
    out << "\n";
  }
  if (args.log_solution && (solved || !trajectory.empty())) {
    // an unsolved PIBT run logs its (partial) trajectory, marked as such
    const Solution& traj = solved ? solution : trajectory;
    out << "partial=" << !solved << "\n";
    out << "solution=\n";
    for (size_t t = 0; t < traj.size(); ++t) {
      out << t << ":";
      write_config(out, ins.G, traj[t]);
      out << "\n";
    }
  }

  if (!args.output.empty()) {
    std::ofstream f(args.output);
    f << out.str();
  }
  std::cout << args.algo << " N=" << ins.N << " solved=" << solved << " valid=" << valid
            << " time_ms=" << comp_time_ms;
  if (solved)
    std::cout << " soc=" << get_sum_of_costs(ins, solution) << " (lb " << soc_lb
              << ") makespan=" << get_makespan(solution) << " (lb " << makespan_lb << ")";
  std::cout << " hnodes=" << st.hnodes << std::endl;
  if (solved && !valid) std::cerr << "INVALID SOLUTION: " << reason << std::endl;
  return 0;
}
