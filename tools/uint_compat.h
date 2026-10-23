// Forced-include header for compiling Linux-oriented research code with MSVC.
#pragma once
// glibc exposes `uint` through <sys/types.h>, MSVC does not.
typedef unsigned int uint;

// MSVC predefines the macro _MT (multithreaded CRT), which clashes with the
// parameter name `_MT` used by the official LaCAM code. Pull in the standard
// headers first (they are include-guarded), then drop the macro.
#include <ciso646>  // alternative tokens such as `or` / `and` / `not`
#include <algorithm>
#include <array>
#include <chrono>
#include <climits>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <queue>
#include <random>
#include <regex>
#include <set>
#include <stack>
#include <string>
#include <unordered_map>
#include <vector>
#undef _MT
