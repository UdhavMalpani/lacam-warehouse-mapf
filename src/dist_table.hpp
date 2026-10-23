// Lazily evaluated BFS distance table, as in the official LaCAM code:
// get(i, v) = shortest-path distance from v to the goal of agent i. Each
// agent's backward BFS is resumed only as far as a query needs it.
#pragma once

#include <vector>

#include "graph.hpp"

class DistTable {
 public:
  DistTable(const Graph& G, const Config& goals);
  int get(int i, int v);
  const int V;  // also used as "infinity"

 private:
  const Graph& G;
  std::vector<std::vector<int>> table;     // [agent][vertex]
  std::vector<std::vector<int>> frontier;  // BFS queue of each agent
  std::vector<size_t> head;
};
