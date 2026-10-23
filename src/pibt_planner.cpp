#include "pibt_planner.hpp"

#include <algorithm>
#include <numeric>

PIBTPlanner::PIBTPlanner(const Instance& ins_, const Deadline& deadline_, std::mt19937& MT_,
                         int max_steps_, bool swap)
    : ins(ins_),
      deadline(deadline_),
      MT(MT_),
      max_steps(max_steps_),
      D(ins_.G, ins_.goals),
      pibt(ins_, D, MT_, swap)
{
}

Solution PIBTPlanner::solve()
{
  const int N = ins.N;
  std::vector<float> priorities(N);
  for (int i = 0; i < N; ++i) priorities[i] = (float)D.get(i, ins.starts[i]) / N;
  std::vector<int> order(N);
  const std::vector<int> no_constraints;

  Config Q = ins.starts;
  trajectory.push_back(Q);
  while (true) {
    if (Q == ins.goals) {
      solved = true;
      break;
    }
    if ((int)trajectory.size() > max_steps) {
      hit_step_limit = true;
      break;
    }
    if (deadline.expired()) break;

    std::iota(order.begin(), order.end(), 0);
    std::sort(order.begin(), order.end(),
              [&](int i, int j) { return priorities[i] > priorities[j]; });
    // without constraints PIBT always returns a valid configuration
    pibt.generate(Q, order, no_constraints, no_constraints);
    Q = pibt.v_next;
    trajectory.push_back(Q);

    for (int i = 0; i < N; ++i) {
      if (Q[i] != ins.goals[i]) priorities[i] += 1;
      else priorities[i] -= (int)priorities[i];
    }
  }
  return solved ? trajectory : Solution();
}
