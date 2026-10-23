#include "metrics.hpp"

#include <algorithm>

bool is_feasible(const Instance& ins, const Solution& sol, std::string* reason)
{
  auto fail = [&](const std::string& msg) {
    if (reason != nullptr) *reason = msg;
    return false;
  };
  if (sol.empty()) return fail("empty solution");
  if (sol.front() != ins.starts) return fail("first configuration differs from starts");
  if (sol.back() != ins.goals) return fail("last configuration differs from goals");

  const int N = ins.N;
  std::vector<int> occupied(ins.G.size(), NO_AGENT);  // vertex -> agent at time t-1
  std::vector<int> occupied_next(ins.G.size(), NO_AGENT);
  for (size_t t = 1; t < sol.size(); ++t) {
    const Config& P = sol[t - 1];
    const Config& Q = sol[t];
    if ((int)Q.size() != N) return fail("configuration of wrong size at t=" + std::to_string(t));
    for (int i = 0; i < N; ++i) {
      occupied[P[i]] = i;
      if (P[i] != Q[i] && !ins.G.adjacent(P[i], Q[i]))
        return fail("invalid move of agent " + std::to_string(i) + " at t=" + std::to_string(t));
    }
    for (int i = 0; i < N; ++i) {
      if (occupied_next[Q[i]] != NO_AGENT)
        return fail("vertex conflict between agents " + std::to_string(occupied_next[Q[i]]) +
                    " and " + std::to_string(i) + " at t=" + std::to_string(t));
      occupied_next[Q[i]] = i;
      const int j = occupied[Q[i]];  // agent that was at i's next vertex
      if (j != NO_AGENT && j != i && Q[j] == P[i])
        return fail("swap conflict between agents " + std::to_string(i) + " and " +
                    std::to_string(j) + " at t=" + std::to_string(t));
    }
    for (int i = 0; i < N; ++i) {
      occupied[P[i]] = NO_AGENT;
      occupied_next[Q[i]] = NO_AGENT;
    }
  }
  return true;
}

int get_makespan(const Solution& sol) { return sol.empty() ? 0 : (int)sol.size() - 1; }

long long get_sum_of_costs(const Instance& ins, const Solution& sol)
{
  if (sol.empty()) return 0;
  long long c = 0;
  for (int i = 0; i < ins.N; ++i) {
    int t = (int)sol.size();
    while (t > 0 && sol[t - 1][i] == ins.goals[i]) --t;
    c += t;
  }
  return c;
}

long long get_sum_of_loss(const Instance& ins, const Solution& sol)
{
  long long c = 0;
  for (size_t t = 1; t < sol.size(); ++t)
    for (int i = 0; i < ins.N; ++i)
      if (sol[t - 1][i] != ins.goals[i] || sol[t][i] != ins.goals[i]) ++c;
  return c;
}

std::vector<int> bfs_distances(const Graph& G, int source)
{
  std::vector<int> dist(G.size(), -1);
  std::vector<int> queue;
  queue.reserve(G.size());
  dist[source] = 0;
  queue.push_back(source);
  for (size_t h = 0; h < queue.size(); ++h) {
    const int v = queue[h];
    for (int k = 0; k < G.deg[v]; ++k) {
      const int u = G.nbr[v][k];
      if (dist[u] >= 0) continue;
      dist[u] = dist[v] + 1;
      queue.push_back(u);
    }
  }
  return dist;
}

long long get_soc_lower_bound(const Instance& ins)
{
  long long c = 0;
  for (int i = 0; i < ins.N; ++i) c += bfs_distances(ins.G, ins.goals[i])[ins.starts[i]];
  return c;
}

int get_makespan_lower_bound(const Instance& ins)
{
  int c = 0;
  for (int i = 0; i < ins.N; ++i)
    c = std::max(c, bfs_distances(ins.G, ins.goals[i])[ins.starts[i]]);
  return c;
}
