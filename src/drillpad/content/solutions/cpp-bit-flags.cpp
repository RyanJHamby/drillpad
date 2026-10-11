using u64 = std::uint64_t;

constexpr u64 set_bit(u64 x, unsigned i) { return i < 64 ? x | (u64{1} << i) : x; }
constexpr u64 clear_bit(u64 x, unsigned i) { return i < 64 ? x & ~(u64{1} << i) : x; }
constexpr u64 toggle_bit(u64 x, unsigned i) { return i < 64 ? x ^ (u64{1} << i) : x; }
constexpr bool test_bit(u64 x, unsigned i) { return i < 64 && ((x >> i) & 1u) != 0; }

constexpr int popcount(u64 x) {
    int n = 0;
    while (x) { x &= x - 1; ++n; }          // Kernighan: each step clears the lowest set bit
    return n;
}

constexpr u64 lowest_set_bit(u64 x) { return x & (~x + 1); }   // x & -x without signed negation
constexpr u64 clear_lowest_set_bit(u64 x) { return x & (x - 1); }

constexpr unsigned index_of_lowest_set_bit(u64 x) {
    if (x == 0) return 64;
    unsigned n = 0;
    if ((x & 0xFFFFFFFFull) == 0) { n += 32; x >>= 32; }
    if ((x & 0xFFFFull) == 0) { n += 16; x >>= 16; }
    if ((x & 0xFFull) == 0) { n += 8; x >>= 8; }
    if ((x & 0xFull) == 0) { n += 4; x >>= 4; }
    if ((x & 0x3ull) == 0) { n += 2; x >>= 2; }
    if ((x & 0x1ull) == 0) { n += 1; }
    return n;
}

constexpr bool is_power_of_two(u64 x) { return x != 0 && (x & (x - 1)) == 0; }

constexpr u64 rotl(u64 x, unsigned n) {
    n &= 63;                                 // n == 0 would make `x >> 64` undefined
    return n == 0 ? x : (x << n) | (x >> (64 - n));
}
constexpr u64 rotr(u64 x, unsigned n) {
    n &= 63;
    return n == 0 ? x : (x >> n) | (x << (64 - n));
}

template <class F>
void for_each_set_bit(u64 x, F f) {
    while (x) {
        f(index_of_lowest_set_bit(x));
        x = clear_lowest_set_bit(x);
    }
}
