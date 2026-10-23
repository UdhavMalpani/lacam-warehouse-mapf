// PIBT (Priority Inheritance with Backtracking, Okumura et al. IJCAI-19 / AIJ-22)
// used as a one-step *configuration generator*.
//
// Given the current configuration Q_from, an agent order (priorities) and an
// optional set of low-level constraints "agent who[k] must move to where[k]"
// (LaCAM's lazily generated constraints), it computes a collision-free next
// configuration Q_to, or reports failure when the constraints make that
// impossible. LaCAM calls it once per high-level step; the standalone PIBT
// planner calls it repeatedly without any search on top.
//
// The optional swap technique is the one introduced with LaCAM* (IJCAI-23):
// it lets two agents exchange positions inside narrow corridors, which vanilla
// PIBT cannot do.
#pragma once

#include <array>
#include <random>
#include <vector>

#include "dist_table.hpp"
#include "instance.hpp"

class PIBT {
 public:
  PIBT(const Instance& ins, DistTable& D, std::mt19937& MT, bool use_swap);

  // Returns true and fills `v_next` with a valid configuration, or false.
  bool generate(const Config& Q_from, const std::vector<int>& order,
                const std::vector<int>& who, const std::vector<int>& where);

  Config v_next;  // next location of every agent (result of generate)

 private:
  bool funcPIBT(int i);
  int swap_possible_and_required(int i);
  bool is_swap_required(int pusher, int puller, int v_pusher_origin, int v_puller_origin);
  bool is_swap_possible(int v_pusher_origin, int v_puller_origin);
  bool is_parked_dead_end(int u) const;

  const Instance& ins;
  const Graph& G;
  DistTable& D;
  std::mt19937& MT;
  const bool use_swap;
  const int N;

  Config v_now;                       // current location of every agent
  std::vector<int> occupied_now;      // vertex -> agent currently there
  std::vector<int> occupied_next;     // vertex -> agent that reserved it for the next step
  std::vector<float> tie_breakers;    // random tie-breaking per vertex
  std::vector<std::array<int, 5>> C_next;  // candidate next locations per agent
};
