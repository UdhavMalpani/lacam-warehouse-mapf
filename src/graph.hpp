// 4-connected grid graph built from a MovingAI .map file.
#pragma once

#include <array>
#include <string>
#include <vector>

#include "common.hpp"

struct Graph {
  int width = 0;
  int height = 0;
  std::vector<int> cell_to_vertex;      // y * width + x  ->  vertex id (NO_VERTEX if blocked)
  std::vector<int> vertex_to_cell;      // vertex id      ->  y * width + x
  std::vector<std::array<int, 4>> nbr;  // neighbours of each vertex (first deg[v] entries valid)
  std::vector<int> deg;

  bool load(const std::string& map_file);
  int size() const { return (int)vertex_to_cell.size(); }
  int x(int v) const { return vertex_to_cell[v] % width; }
  int y(int v) const { return vertex_to_cell[v] / width; }
  int vertex_at(int x, int y) const;    // NO_VERTEX if outside the map or blocked
  bool adjacent(int u, int v) const;
};
