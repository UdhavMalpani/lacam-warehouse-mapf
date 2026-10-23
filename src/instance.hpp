// A MAPF instance: graph + start/goal vertex for each agent.
#pragma once

#include <string>
#include <vector>

#include "graph.hpp"

struct Instance {
  Graph G;
  Config starts;
  Config goals;
  int N = 0;

  // Reads the first N agents of a MovingAI .scen file (columns: bucket, map,
  // width, height, start_x, start_y, goal_x, goal_y, optimal_length).
  bool load(const std::string& map_file, const std::string& scen_file, int N);
};
