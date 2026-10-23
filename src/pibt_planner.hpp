// Standalone PIBT for one-shot MAPF ("PIBT without LaCAM").
//
// Repeats the same PIBT step used inside LaCAM, with the same dynamic
// priorities, until every agent is at its goal. There is no search on top, so
// the planner is incomplete: it can deadlock/livelock, in which case it fails
// at the step limit or the time limit.
#pragma once

#include <random>

#include "pibt.hpp"

class PIBTPlanner {
 public:
  PIBTPlanner(const Instance& ins, const Deadline& deadline, std::mt19937& MT, int max_steps,
              bool swap);
  Solution solve();  // empty if unsolved

  Solution trajectory;  // every configuration produced (kept even on failure)
  bool solved = false;
  bool hit_step_limit = false;

 private:
  const Instance& ins;
  const Deadline& deadline;
  std::mt19937& MT;
  const int max_steps;
  DistTable D;
  PIBT pibt;
};
