// LaCAM: Lazy Constraints Addition search for MAPF (Okumura, AAAI-23) and
// LaCAM* (Okumura, IJCAI-23).
//
// High level: depth-first search over *configurations* (positions of all
// agents). Each high-level node owns a low-level search tree whose nodes are
// constraints "agent who[k] moves to where[k]", generated lazily in
// breadth-first order (one agent per depth, following the node's PIBT order).
// Every time a high-level node is on top of the stack, one constraint node is
// popped and PIBT generates a successor configuration that satisfies it.
// Because the low-level tree eventually enumerates every possible successor,
// the search is complete; because PIBT usually produces a good successor on
// the first try, it is also extremely fast.
//
// LaCAM* additions (enabled by LaCAMParams):
//   * swap      : PIBT with the swap technique,
//   * anytime   : costs g/h on configurations, rewiring of the search graph
//                 with Dijkstra-style updates and pruning by the incumbent,
//                 which makes the search eventually optimal,
//   * restart   : with a small probability, revisits jump back to the root.
#pragma once

#include <unordered_map>
#include <vector>

#include "pibt.hpp"

enum class Objective { NONE, MAKESPAN, SUM_OF_LOSS };

struct LaCAMParams {
  bool swap = false;
  bool anytime = false;
  Objective objective = Objective::NONE;
  float restart_rate = 0.0f;
  double mem_limit_mb = 4000.0;
};

struct AnytimeEntry {
  double time_ms;
  long long cost;  // value of the search objective (e.g. sum-of-loss)
  long long soc;   // sum-of-costs of the same solution
};

struct SearchStats {
  long long loop_cnt = 0;    // iterations of the main loop
  long long hnodes = 0;      // high-level nodes = distinct configurations generated
  long long lnodes = 0;      // low-level constraint nodes generated
  long long pibt_calls = 0;  // configuration-generator invocations
  long long pibt_fail = 0;   // ... that could not satisfy their constraints
  long long revisits = 0;    // generated configurations that were already explored
  long long restarts = 0;
  long long rewires = 0;     // g-value improvements propagated (LaCAM*)
  long long max_open = 0;
  double time_first_ms = -1;
  long long cost_first = -1;     // objective value (g) of the first solution
  long long soc_first = -1;      // sum-of-costs of the first solution
  int makespan_first = -1;
  bool optimal = false;      // LaCAM*: search space exhausted => optimal for the objective
  bool mem_limit_hit = false;
  std::vector<AnytimeEntry> anytime_log;  // one entry per incumbent improvement
};

// low-level node: a chain of constraints from the root of the constraint tree
struct LNode {
  std::vector<int> who;
  std::vector<int> where;
  LNode() = default;
  LNode(const LNode* parent, int i, int v) : who(parent->who), where(parent->where)
  {
    who.push_back(i);
    where.push_back(v);
  }
  int depth() const { return (int)who.size(); }
};

// high-level node: a configuration plus its lazily expanded constraint tree
struct HNode {
  const Config C;
  HNode* parent;
  std::vector<HNode*> neighbors;  // known successors (needed for LaCAM* rewiring)
  int g, h, f;
  std::vector<float> priorities;  // PIBT-style dynamic priorities
  std::vector<int> order;         // agents sorted by priority
  std::vector<LNode*> tree;       // FIFO queue of low-level nodes
  size_t tree_head = 0;

  HNode(const Config& C, HNode* parent, int g, int h, DistTable& D);
  ~HNode();
  bool tree_empty() const { return tree_head >= tree.size(); }
  LNode* tree_pop();
};

class LaCAM {
 public:
  LaCAM(const Instance& ins, const Deadline& deadline, std::mt19937& MT, const LaCAMParams& params);
  Solution solve();
  SearchStats stats;

 private:
  void record_first_solution(HNode* H_goal);
  Solution backtrack(HNode* H_goal) const;
  void expand_lowlevel_tree(HNode* H, const LNode* L);
  void rewrite(HNode* H_from, HNode* H_to, HNode* H_goal, std::vector<HNode*>& OPEN);
  int edge_cost(const Config& C1, const Config& C2) const;
  int h_value(const Config& C);

  const Instance& ins;
  const Deadline& deadline;
  std::mt19937& MT;
  const LaCAMParams params;
  const int N;
  DistTable D;
  PIBT pibt;
};
