template <class It, class T, class Comp = std::less<>>
It my_lower_bound(It first, It last, const T& value, Comp comp = Comp{}) {
    auto count = std::distance(first, last);          // O(1) for random access, O(n) once for others
    while (count > 0) {
        auto step = count / 2;
        It mid = first;
        std::advance(mid, step);
        if (comp(*mid, value)) {                      // *mid is still too small: answer is right of it
            first = ++mid;
            count -= step + 1;
        } else {
            count = step;
        }
    }
    return first;
}

template <class It, class T, class Comp = std::less<>>
It my_upper_bound(It first, It last, const T& value, Comp comp = Comp{}) {
    auto count = std::distance(first, last);
    while (count > 0) {
        auto step = count / 2;
        It mid = first;
        std::advance(mid, step);
        if (!comp(value, *mid)) {                     // *mid <= value: answer is right of it
            first = ++mid;
            count -= step + 1;
        } else {
            count = step;
        }
    }
    return first;
}

template <class It, class T, class Comp = std::less<>>
std::pair<It, It> my_equal_range(It first, It last, const T& value, Comp comp = Comp{}) {
    It lo = my_lower_bound(first, last, value, comp);
    return {lo, my_upper_bound(lo, last, value, comp)};
}
