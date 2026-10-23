#include "instance.hpp"

#include <fstream>
#include <iostream>
#include <sstream>

bool Instance::load(const std::string& map_file, const std::string& scen_file, int N_)
{
  if (!G.load(map_file)) return false;

  std::ifstream f(scen_file);
  if (!f) {
    std::cerr << "cannot open scen file: " << scen_file << std::endl;
    return false;
  }
  std::string line;
  std::vector<char> used_start(G.size(), 0), used_goal(G.size(), 0);
  while ((int)starts.size() < N_ && std::getline(f, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty() || line.rfind("version", 0) == 0) continue;
    std::istringstream ss(line);
    int bucket, w, h, sx, sy, gx, gy;
    std::string map_name;
    if (!(ss >> bucket >> map_name >> w >> h >> sx >> sy >> gx >> gy)) continue;
    const int s = G.vertex_at(sx, sy);
    const int g = G.vertex_at(gx, gy);
    if (s == NO_VERTEX || g == NO_VERTEX) {
      std::cerr << "start/goal on a blocked cell: " << line << std::endl;
      return false;
    }
    if (used_start[s] || used_goal[g]) {
      std::cerr << "duplicated start/goal: " << line << std::endl;
      return false;
    }
    used_start[s] = used_goal[g] = 1;
    starts.push_back(s);
    goals.push_back(g);
  }
  N = (int)starts.size();
  if (N < N_) {
    std::cerr << "scen file has only " << N << " agents (requested " << N_ << ")" << std::endl;
    return false;
  }
  return true;
}
