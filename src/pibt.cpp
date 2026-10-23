#include "pibt.hpp"

#include <algorithm>

PIBT::PIBT(const Instance& ins_, DistTable& D_, std::mt19937& MT_, bool use_swap_)
    : v_next(ins_.N, NO_VERTEX),
      ins(ins_),
      G(ins_.G),
      D(D_),
      MT(MT_),
      use_swap(use_swap_),
      N(ins_.N),
      v_now(ins_.N, NO_VERTEX),
      occupied_now(ins_.G.size(), NO_AGENT),
      occupied_next(ins_.G.size(), NO_AGENT),
      tie_breakers(ins_.G.size(), 0.0f),
      C_next(ins_.N)
{
}

bool PIBT::generate(const Config& Q_from, const std::vector<int>& order,
                    const std::vector<int>& who, const std::vector<int>& where)
{
  // reset the occupancy caches left over from the previous call
  for (int i = 0; i < N; ++i) {
    if (v_now[i] != NO_VERTEX && occupied_now[v_now[i]] == i) occupied_now[v_now[i]] = NO_AGENT;
    if (v_next[i] != NO_VERTEX) {
      occupied_next[v_next[i]] = NO_AGENT;
      v_next[i] = NO_VERTEX;
    }
    v_now[i] = Q_from[i];
    occupied_now[v_now[i]] = i;
  }

  // apply the low-level constraints first; reject them if they already collide
  for (size_t k = 0; k < who.size(); ++k) {
    const int i = who[k];
    const int l = where[k];
    if (occupied_next[l] != NO_AGENT) return false;  // vertex conflict
    const int l_pre = Q_from[i];
    if (occupied_next[l_pre] != NO_AGENT && occupied_now[l] != NO_AGENT &&
        occupied_next[l_pre] == occupied_now[l])
      return false;  // swap conflict
    v_next[i] = l;
    occupied_next[l] = i;
  }

  // the remaining agents are planned by PIBT in priority order
  for (int i : order) {
    if (v_next[i] == NO_VERTEX && !funcPIBT(i)) return false;
  }
  return true;
}

bool PIBT::funcPIBT(int i)
{
  const int v_i = v_now[i];
  const int K = G.deg[v_i];
  auto& C = C_next[i];

  // candidates: neighbours + stay, sorted by distance-to-goal with random tie-breaking
  for (int k = 0; k < K; ++k) {
    const int u = G.nbr[v_i][k];
    C[k] = u;
    tie_breakers[u] = rand01(MT);
  }
  C[K] = v_i;
  std::sort(C.begin(), C.begin() + K + 1, [&](int a, int b) {
    return D.get(i, a) + tie_breakers[a] < D.get(i, b) + tie_breakers[b];
  });

  int swap_agent = NO_AGENT;
  if (use_swap) {
    swap_agent = swap_possible_and_required(i);
    if (swap_agent != NO_AGENT) std::reverse(C.begin(), C.begin() + K + 1);
  }

  for (int k = 0; k <= K; ++k) {
    const int u = C[k];

    // vertex conflict
    if (occupied_next[u] != NO_AGENT) continue;

    // swap conflict with an agent that already decided to enter v_i
    const int j = occupied_now[u];
    if (j != NO_AGENT && v_next[j] == v_i) continue;

    // reserve u
    occupied_next[u] = i;
    v_next[i] = u;

    // priority inheritance: the occupant of u must move away (recursively)
    if (j != NO_AGENT && j != i && v_next[j] == NO_VERTEX && !funcPIBT(j)) continue;

    // swap technique: pull the swap partner into v_i
    if (k == 0 && swap_agent != NO_AGENT && v_next[swap_agent] == NO_VERTEX &&
        occupied_next[v_i] == NO_AGENT) {
      v_next[swap_agent] = v_i;
      occupied_next[v_i] = swap_agent;
    }
    return true;
  }

  // no valid move: stay (the caller then tries its next candidate)
  occupied_next[v_i] = i;
  v_next[i] = v_i;
  return false;
}

// ---------------------------------------------------------------------------
// swap technique (LaCAM*, IJCAI-23)

bool PIBT::is_parked_dead_end(int u) const
{
  // a dead-end vertex occupied by an agent that is already at its goal
  const int a = occupied_now[u];
  return G.deg[u] == 1 && a != NO_AGENT && ins.goals[a] == u;
}

int PIBT::swap_possible_and_required(int i)
{
  const auto& C = C_next[i];
  if (C[0] == v_now[i]) return NO_AGENT;  // agent i wants to stay: nothing to swap

  // usual swap situation: the agent occupying i's preferred vertex
  const int j = occupied_now[C[0]];
  if (j != NO_AGENT && v_next[j] == NO_VERTEX && is_swap_required(i, j, v_now[i], v_now[j]) &&
      is_swap_possible(v_now[j], v_now[i]))
    return j;

  // clear operation: a neighbour that should be pulled behind i
  for (int k = 0; k < G.deg[v_now[i]]; ++k) {
    const int u = G.nbr[v_now[i]][k];
    const int a = occupied_now[u];
    if (a == NO_AGENT || C[0] == v_now[a]) continue;
    if (is_swap_required(a, i, v_now[i], C[0]) && is_swap_possible(C[0], v_now[i])) return a;
  }
  return NO_AGENT;
}

// simulate pushing along a corridor: is a swap really needed?
bool PIBT::is_swap_required(int pusher, int puller, int v_pusher_origin, int v_puller_origin)
{
  int v_pusher = v_pusher_origin;
  int v_puller = v_puller_origin;
  int tmp = NO_VERTEX;
  while (D.get(pusher, v_puller) < D.get(pusher, v_pusher)) {
    int n = G.deg[v_puller];
    for (int k = 0; k < G.deg[v_puller]; ++k) {
      const int u = G.nbr[v_puller][k];
      if (u == v_pusher || is_parked_dead_end(u)) --n;
      else tmp = u;
    }
    if (n >= 2) return false;  // there is room to step aside
    if (n <= 0) break;
    v_pusher = v_puller;
    v_puller = tmp;
  }
  return (D.get(puller, v_pusher) < D.get(puller, v_puller)) &&
         (D.get(pusher, v_pusher) == 0 || D.get(pusher, v_puller) < D.get(pusher, v_pusher));
}

// simulate pulling: is there a branching vertex where the two agents can swap?
bool PIBT::is_swap_possible(int v_pusher_origin, int v_puller_origin)
{
  int v_pusher = v_pusher_origin;
  int v_puller = v_puller_origin;
  int tmp = NO_VERTEX;
  while (v_puller != v_pusher_origin) {
    int n = G.deg[v_puller];
    for (int k = 0; k < G.deg[v_puller]; ++k) {
      const int u = G.nbr[v_puller][k];
      if (u == v_pusher || is_parked_dead_end(u)) --n;
      else tmp = u;
    }
    if (n >= 2) return true;
    if (n <= 0) return false;
    v_pusher = v_puller;
    v_puller = tmp;
  }
  return false;
}
