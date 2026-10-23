// msvc_compat.h -- force-included (cl /FI) into every translation unit of the
// EECBS, MAPF-LNS2 and PBS builds made by tools/build_baselines.bat.
//
// Purpose: minimal Windows/MSVC portability shims for Jiaoyang Li's Linux/GCC
// MAPF solvers WITHOUT editing their algorithms.  See third_party/PATCHES.md.
//
//  (1) Standard headers that libstdc++ pulls in transitively but MSVC's STL
//      does not (the sources rely on that), plus <ciso646> because the code
//      uses the alternative tokens `and` / `or` / `not`, which MSVC only
//      accepts as macros from <iso646.h> unless /permissive- is used.
//      (1b) #undef of MSVC's predefined _MT macro (clashes with a parameter
//      name in MAPF-LNS2's PIBT module).
//
//  (2) Linux-identical pseudo-randomness.  On MSVC RAND_MAX is 32767, while on
//      glibc it is 2147483647.  MAPF-LNS2 uses `rand() % X` with X that can
//      exceed 32767 on large maps/instances (e.g. `rand() % intersections.size()`
//      in LNS::generateNeighborByIntersection, `rand() % (num_of_colliding_pairs*2)`
//      in InitLNS::generateNeighborByTarget, `rand() % total` in
//      InitLNS::generateNeighborRandomly) and `(double)rand() / RAND_MAX` in
//      BasicLNS::rouletteWheel.  We therefore replace rand()/srand()/RAND_MAX
//      with an exact re-implementation of glibc's random()/srandom()
//      (TYPE_3 additive feedback generator, the generator behind glibc rand()),
//      so the stream is bit-identical to Linux for the same seed (srand(0) is
//      treated as srand(1), as in glibc).  std::random_shuffle(first,last) is
//      replaced by libstdc++'s algorithm (j = rand() % (i+1)) drawing from the
//      same stream, as on Linux (MSVC's version draws from the CRT rand(),
//      which would no longer be seeded by the program's srand()).
//
// All standard headers are included BEFORE the macros are defined, so the
// macros never touch the standard library's own declarations.
#pragma once
#if defined(_MSC_VER)

// ---------------------------------------------------------------- (1) headers
#include <algorithm>
#include <array>
#include <cassert>
#include <cfloat>
#include <ciso646>
#include <climits>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <functional>
#include <iterator>
#include <limits>
#include <numeric>
#include <random>
#include <string>
#include <utility>

// ---------------------------------------------------- (1b) the _MT identifier
// MAPF-LNS2's PIBT module names constructor parameters `_MT` (e.g.
// `Graph(std::mt19937* _MT)`), but MSVC predefines the macro _MT=1 for the
// multithreaded CRT, so the declarations become `std::mt19937* 1`.  Neither the
// MSVC STL nor the UCRT headers test _MT; Boost only tests defined(_MT) in
// boost/config to set BOOST_HAS_THREADS, so include boost/config.hpp first
// (keeping Boost's configuration identical to the non-/FI program_options
// objects) and then drop the macro.
#include <boost/config.hpp>
#undef _MT

// ------------------------------------------------- (2) glibc-compatible rand()
namespace msvc_compat {

// Exact re-implementation of glibc random_r.c, TYPE_3 (degree 31, separation 3),
// which is what glibc's rand()/srand() use.  Output range [0, 2^31 - 1].
class GlibcRandom {
public:
    GlibcRandom() { seed(1u); }  // glibc's initial state == srandom(1)

    void seed(unsigned int s) {  // __srandom_r
        if (s == 0u) s = 1u;
        int32_t word = static_cast<int32_t>(s);
        state_[0] = word;
        for (int i = 1; i < kDeg; ++i) {
            // state[i] = (16807 * state[i-1]) % 2147483647 via Schrage's method
            const int64_t hi = word / 127773;
            const int64_t lo = word % 127773;
            word = static_cast<int32_t>(16807 * lo - 2836 * hi);
            if (word < 0) word += 2147483647;
            state_[i] = word;
        }
        f_ = kSep;
        r_ = 0;
        for (int i = 0; i < 10 * kDeg; ++i) (void)next();  // discard 310 outputs
    }

    int next() {  // __random_r
        const uint32_t val = static_cast<uint32_t>(state_[f_]) + static_cast<uint32_t>(state_[r_]);
        state_[f_] = static_cast<int32_t>(val);
        const int result = static_cast<int>(val >> 1);
        if (++f_ >= kDeg) {
            f_ = 0;
            ++r_;
        } else if (++r_ >= kDeg) {
            r_ = 0;
        }
        return result;
    }

private:
    static const int kDeg = 31;
    static const int kSep = 3;
    int32_t state_[kDeg];
    int f_, r_;
};

inline GlibcRandom& glibc_random() {  // one process-wide stream (inline => shared by all TUs)
    static GlibcRandom g;
    return g;
}

}  // namespace msvc_compat

inline int portable_rand() { return msvc_compat::glibc_random().next(); }
inline void portable_srand(unsigned int seed) { msvc_compat::glibc_random().seed(seed); }

// libstdc++'s std::random_shuffle (bits/stl_algo.h, branch used when RAND_MAX == INT_MAX)
template <class RandomIt>
inline void portable_random_shuffle(RandomIt first, RandomIt last) {
    if (first == last) return;
    for (RandomIt i = first + 1; i != last; ++i) {
        RandomIt j = first + (portable_rand() % ((i - first) + 1));
        if (i != j) std::iter_swap(i, j);
    }
}
template <class RandomIt, class RandomFunc>
inline void portable_random_shuffle(RandomIt first, RandomIt last, RandomFunc&& gen) {
    if (first == last) return;
    for (RandomIt i = first + 1; i != last; ++i) {
        RandomIt j = first + gen((i - first) + 1);
        if (i != j) std::iter_swap(i, j);
    }
}

// So that std::-qualified uses (std::rand(), std::random_shuffle(...)) resolve too.
namespace std {
using ::portable_rand;
using ::portable_srand;
using ::portable_random_shuffle;
}  // namespace std

#undef RAND_MAX
#define RAND_MAX 2147483647
#define rand portable_rand
#define srand portable_srand
#define random_shuffle portable_random_shuffle

#endif  // _MSC_VER
