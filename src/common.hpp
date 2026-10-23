// Shared types and small utilities for the LaCAM / PIBT re-implementation.
#pragma once

#include <chrono>
#include <cstdint>
#include <random>
#include <string>
#include <vector>

constexpr int NO_VERTEX = -1;
constexpr int NO_AGENT = -1;

// A configuration assigns one vertex id to every agent; a solution is the
// sequence of configurations Q_0 (= starts), Q_1, ..., Q_T (= goals).
using Config = std::vector<int>;
using Solution = std::vector<Config>;

struct ConfigHasher {
  size_t operator()(const Config& C) const
  {
    uint64_t h = C.size();
    for (int v : C) h ^= (uint64_t)v + 0x9e3779b97f4a7c15ULL + (h << 6) + (h >> 2);
    return (size_t)h;
  }
};

// Wall-clock deadline; every planner checks it inside its main loop.
struct Deadline {
  using Clock = std::chrono::steady_clock;
  Clock::time_point t_start;
  double limit_ms;

  explicit Deadline(double limit_ms_) : t_start(Clock::now()), limit_ms(limit_ms_) {}
  double elapsed_ms() const
  {
    return std::chrono::duration<double, std::milli>(Clock::now() - t_start).count();
  }
  bool expired() const { return elapsed_ms() >= limit_ms; }
};

inline float rand01(std::mt19937& MT)
{
  return std::uniform_real_distribution<float>(0.0f, 1.0f)(MT);
}

// Resident memory of this process in MB (0 if unsupported on this platform).
double current_memory_mb();
