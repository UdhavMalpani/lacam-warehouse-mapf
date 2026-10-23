#include "dist_table.hpp"

DistTable::DistTable(const Graph& G_, const Config& goals)
    : V(G_.size()), G(G_), table(goals.size()), frontier(goals.size()), head(goals.size(), 0)
{
  for (size_t i = 0; i < goals.size(); ++i) {
    table[i].assign(V, V);
    table[i][goals[i]] = 0;
    frontier[i].push_back(goals[i]);
  }
}

int DistTable::get(int i, int v)
{
  auto& T = table[i];
  if (T[v] < V) return T[v];

  // with unit edge costs the first label a vertex receives is final,
  // so we can stop as soon as v is labelled
  auto& Q = frontier[i];
  auto& h = head[i];
  while (T[v] >= V && h < Q.size()) {
    const int n = Q[h++];
    const int d_next = T[n] + 1;
    for (int k = 0; k < G.deg[n]; ++k) {
      const int m = G.nbr[n][k];
      if (T[m] <= d_next) continue;
      T[m] = d_next;
      Q.push_back(m);
    }
  }
  if (h >= Q.size()) {  // BFS finished: release the queue
    std::vector<int>().swap(Q);
    h = 0;
  }
  return T[v];
}
