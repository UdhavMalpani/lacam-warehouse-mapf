#include "graph.hpp"

#include <fstream>
#include <iostream>
#include <sstream>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#include <psapi.h>
#pragma comment(lib, "psapi.lib")
double current_memory_mb()
{
  PROCESS_MEMORY_COUNTERS pmc;
  if (GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof(pmc)))
    return (double)pmc.PagefileUsage / (1024.0 * 1024.0);
  return 0.0;
}
#else
double current_memory_mb() { return 0.0; }
#endif

// MovingAI convention: '.', 'G' and 'S' are passable, everything else ('@', 'T', 'O', 'W') is not.
static bool is_passable(char c) { return c == '.' || c == 'G' || c == 'S'; }

bool Graph::load(const std::string& map_file)
{
  std::ifstream f(map_file);
  if (!f) {
    std::cerr << "cannot open map file: " << map_file << std::endl;
    return false;
  }
  std::string line, key;
  while (std::getline(f, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    std::istringstream ss(line);
    ss >> key;
    if (key == "height") ss >> height;
    else if (key == "width") ss >> width;
    else if (key == "map") break;
  }
  if (width <= 0 || height <= 0) {
    std::cerr << "invalid map header: " << map_file << std::endl;
    return false;
  }

  cell_to_vertex.assign((size_t)width * height, NO_VERTEX);
  for (int y = 0; y < height; ++y) {
    if (!std::getline(f, line)) {
      std::cerr << "map file ended early: " << map_file << std::endl;
      return false;
    }
    if (!line.empty() && line.back() == '\r') line.pop_back();
    for (int x = 0; x < width && x < (int)line.size(); ++x) {
      if (!is_passable(line[x])) continue;
      cell_to_vertex[y * width + x] = (int)vertex_to_cell.size();
      vertex_to_cell.push_back(y * width + x);
    }
  }

  // neighbour order (left, right, down, up) only matters for tie-breaking,
  // and every planner randomises ties anyway
  static const int dx[4] = {-1, 1, 0, 0};
  static const int dy[4] = {0, 0, 1, -1};
  nbr.assign(size(), {NO_VERTEX, NO_VERTEX, NO_VERTEX, NO_VERTEX});
  deg.assign(size(), 0);
  for (int v = 0; v < size(); ++v) {
    for (int k = 0; k < 4; ++k) {
      const int u = vertex_at(x(v) + dx[k], y(v) + dy[k]);
      if (u != NO_VERTEX) nbr[v][deg[v]++] = u;
    }
  }
  return true;
}

int Graph::vertex_at(int x, int y) const
{
  if (x < 0 || x >= width || y < 0 || y >= height) return NO_VERTEX;
  return cell_to_vertex[y * width + x];
}

bool Graph::adjacent(int u, int v) const
{
  for (int k = 0; k < deg[u]; ++k)
    if (nbr[u][k] == v) return true;
  return false;
}
