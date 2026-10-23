#include "lacam.hpp"

#include <algorithm>
#include <numeric>
#include <queue>

#include "metrics.hpp"

// ---------------------------------------------------------------------------
// high-level node

HNode::HNode(const Config& C_, HNode* parent_, int g_, int h_, DistTable& D)
    : C(C_), parent(parent_), g(g_), h(h_), f(g_ + h_), priorities(C_.size()), order(C_.size())
{
  tree.push_back(new LNode());  // root of the constraint tree: no constraint
  const size_t N = C.size();

  // priorities follow PIBT: they grow by one each step an agent is away from
  // its goal and drop back to their fractional part once it arrives
  if (parent == nullptr) {
    for (size_t i = 0; i < N; ++i) priorities[i] = (float)D.get((int)i, C[i]) / N;
  } else {
    for (size_t i = 0; i < N; ++i) {
      if (D.get((int)i, C[i]) != 0) priorities[i] = parent->priorities[i] + 1;
      else priorities[i] = parent->priorities[i] - (int)parent->priorities[i];
    }
  }
  std::iota(order.begin(), order.end(), 0);
  std::sort(order.begin(), order.end(), [&](int i, int j) { return priorities[i] > priorities[j]; });
}

HNode::~HNode()
{
  for (size_t k = tree_head; k < tree.size(); ++k) delete tree[k];
}

LNode* HNode::tree_pop()
{
  LNode* L = tree[tree_head++];
  if (tree_head == tree.size()) {  // queue drained: release its storage
    std::vector<LNode*>().swap(tree);
    tree_head = 0;
  }
  return L;
}

// ---------------------------------------------------------------------------
// planner

LaCAM::LaCAM(const Instance& ins_, const Deadline& deadline_, std::mt19937& MT_,
             const LaCAMParams& params_)
    : ins(ins_),
      deadline(deadline_),
      MT(MT_),
      params(params_),
      N(ins_.N),
      D(ins_.G, ins_.goals),
      pibt(ins_, D, MT_, params_.swap)
{
}

namespace {
// the explored table is keyed by the node's own configuration to avoid a second copy
struct ConfigPtrHash {
  size_t operator()(const Config* C) const { return ConfigHasher()(*C); }
};
struct ConfigPtrEq {
  bool operator()(const Config* a, const Config* b) const { return *a == *b; }
};
}  // namespace

Solution LaCAM::solve()
{
  std::vector<HNode*> OPEN;  // used as a stack (depth-first search)
  std::unordered_map<const Config*, HNode*, ConfigPtrHash, ConfigPtrEq> EXPLORED;
  EXPLORED.reserve(1 << 12);

  HNode* H_init = new HNode(ins.starts, nullptr, 0, h_value(ins.starts), D);
  OPEN.push_back(H_init);
  EXPLORED.emplace(&H_init->C, H_init);
  HNode* H_goal = nullptr;

  while (!OPEN.empty() && !deadline.expired()) {
    ++stats.loop_cnt;
    if ((stats.loop_cnt & 1023) == 0 && current_memory_mb() > params.mem_limit_mb) {
      stats.mem_limit_hit = true;
      break;
    }

    HNode* H = OPEN.back();  // do not pop: H stays until its constraint tree is exhausted

    if (!params.anytime) {
      // LaCAM (AAAI-23): return the first goal configuration found
      if (H->C == ins.goals) {
        H_goal = H;
        record_first_solution(H_goal);
        break;
      }
      if (H->tree_empty()) {
        OPEN.pop_back();
        continue;
      }
    } else {
      // LaCAM* (IJCAI-23): keep searching, pruning nodes that cannot improve the incumbent
      if (H->tree_empty()) {
        OPEN.pop_back();
        continue;
      }
      if (H_goal != nullptr && H->f >= H_goal->f) {
        OPEN.pop_back();
        continue;
      }
      if (H_goal == nullptr && H->C == ins.goals) {
        H_goal = H;
        record_first_solution(H_goal);
        stats.anytime_log.push_back({stats.time_first_ms, (long long)H->g, stats.soc_first});
        continue;
      }
    }

    // low-level step: take the next constraint and lazily create its children
    LNode* L = H->tree_pop();
    expand_lowlevel_tree(H, L);

    // high-level step: PIBT proposes a successor configuration respecting L
    ++stats.pibt_calls;
    const bool ok = pibt.generate(H->C, H->order, L->who, L->where);
    delete L;
    if (!ok) {
      ++stats.pibt_fail;
      continue;
    }

    auto it = EXPLORED.find(&pibt.v_next);
    if (it != EXPLORED.end()) {
      // known configuration: re-insert it (LaCAM) / rewire costs first (LaCAM*)
      ++stats.revisits;
      HNode* H_known = it->second;
      if (params.anytime) {
        rewrite(H, H_known, H_goal, OPEN);
        if (H_goal != nullptr && H_goal->g < stats.anytime_log.back().cost) {
          const Solution sol = backtrack(H_goal);
          stats.anytime_log.push_back(
              {deadline.elapsed_ms(), (long long)H_goal->g, get_sum_of_costs(ins, sol)});
        }
      }
      HNode* H_insert = H_known;
      if (params.restart_rate > 0.0f && rand01(MT) < params.restart_rate) {
        H_insert = H_init;
        ++stats.restarts;
      }
      if (H_goal == nullptr || H_insert->f < H_goal->f) OPEN.push_back(H_insert);
    } else {
      HNode* H_new = new HNode(pibt.v_next, H, H->g + edge_cost(H->C, pibt.v_next),
                               h_value(pibt.v_next), D);
      if (params.anytime) H->neighbors.push_back(H_new);
      EXPLORED.emplace(&H_new->C, H_new);
      if (H_goal == nullptr || H_new->f < H_goal->f) OPEN.push_back(H_new);
    }
    stats.max_open = std::max(stats.max_open, (long long)OPEN.size());
  }

  stats.hnodes = (long long)EXPLORED.size();
  stats.optimal = params.anytime && H_goal != nullptr && OPEN.empty();

  Solution solution = backtrack(H_goal);
  for (auto& kv : EXPLORED) delete kv.second;
  return solution;
}

Solution LaCAM::backtrack(HNode* H_goal) const
{
  Solution sol;
  for (HNode* H = H_goal; H != nullptr; H = H->parent) sol.push_back(H->C);
  std::reverse(sol.begin(), sol.end());
  return sol;
}

void LaCAM::record_first_solution(HNode* H_goal)
{
  stats.time_first_ms = deadline.elapsed_ms();
  stats.cost_first = H_goal->g;
  const Solution sol = backtrack(H_goal);
  stats.soc_first = get_sum_of_costs(ins, sol);
  stats.makespan_first = get_makespan(sol);
}

void LaCAM::expand_lowlevel_tree(HNode* H, const LNode* L)
{
  if (L->depth() >= N) return;
  const int i = H->order[L->depth()];
  const int v = H->C[i];
  const int K = ins.G.deg[v];
  std::array<int, 5> cand;
  for (int k = 0; k < K; ++k) cand[k] = ins.G.nbr[v][k];
  cand[K] = v;
  std::shuffle(cand.begin(), cand.begin() + K + 1, MT);
  for (int k = 0; k <= K; ++k) H->tree.push_back(new LNode(L, i, cand[k]));
  stats.lnodes += K + 1;
}

// Dijkstra-style propagation of improved g-values through the explored graph
void LaCAM::rewrite(HNode* H_from, HNode* H_to, HNode* H_goal, std::vector<HNode*>& OPEN)
{
  if (std::find(H_from->neighbors.begin(), H_from->neighbors.end(), H_to) ==
      H_from->neighbors.end())
    H_from->neighbors.push_back(H_to);

  std::queue<HNode*> Q;
  Q.push(H_from);
  while (!Q.empty()) {
    HNode* n_from = Q.front();
    Q.pop();
    for (HNode* n_to : n_from->neighbors) {
      const int g_val = n_from->g + edge_cost(n_from->C, n_to->C);
      if (g_val >= n_to->g) continue;
      n_to->g = g_val;
      n_to->f = n_to->g + n_to->h;
      n_to->parent = n_from;
      ++stats.rewires;
      Q.push(n_to);
      if (H_goal != nullptr && n_to->f < H_goal->f) OPEN.push_back(n_to);
    }
  }
}

int LaCAM::edge_cost(const Config& C1, const Config& C2) const
{
  if (params.objective == Objective::SUM_OF_LOSS) {
    int cost = 0;
    for (int i = 0; i < N; ++i)
      if (C1[i] != ins.goals[i] || C2[i] != ins.goals[i]) ++cost;
    return cost;
  }
  return 1;  // makespan (and depth when there is no objective)
}

int LaCAM::h_value(const Config& C)
{
  int cost = 0;
  if (params.objective == Objective::MAKESPAN) {
    for (int i = 0; i < N; ++i) cost = std::max(cost, D.get(i, C[i]));
  } else if (params.objective == Objective::SUM_OF_LOSS) {
    for (int i = 0; i < N; ++i) cost += D.get(i, C[i]);
  }
  return cost;
}
