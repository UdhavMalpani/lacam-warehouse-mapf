// Solution validation and the standard MAPF cost measures.
#pragma once

#include <string>

#include "instance.hpp"

// Checks starts/goals, that every move follows an edge or waits, and that there
// are no vertex or swap (edge) conflicts. `reason` describes the first error.
bool is_feasible(const Instance& ins, const Solution& sol, std::string* reason = nullptr);

int get_makespan(const Solution& sol);
long long get_sum_of_costs(const Instance& ins, const Solution& sol);  // arrival time of each agent, summed
long long get_sum_of_loss(const Instance& ins, const Solution& sol);   // actions other than waiting at the goal
long long get_soc_lower_bound(const Instance& ins);                    // sum of shortest-path distances
int get_makespan_lower_bound(const Instance& ins);

// single-source BFS distances on the grid (used for lower bounds)
std::vector<int> bfs_distances(const Graph& G, int source);
