Heavy make_heavy(int v) {
    Heavy h(v);
    h.v += 0;
    return h;                       // NRVO: constructed directly in the caller's slot
}

std::vector<Heavy> make_batch(int n) {
    std::vector<Heavy> out;
    out.reserve(n);                 // no reallocation, so no relocation moves
    for (int i = 0; i < n; i++) out.emplace_back(i);   // construct in place
    return out;
}

void append_all(std::vector<Heavy>& dst, std::vector<Heavy> src) {
    dst.reserve(dst.size() + src.size());
    for (auto& h : src) dst.push_back(std::move(h));
}

class Holder {
    Heavy a_, b_;
public:
    Holder(Heavy a, Heavy b) : a_(std::move(a)), b_(std::move(b)) {}   // sink parameters
    const Heavy& first() const { return a_; }
    const Heavy& second() const { return b_; }
};

const Heavy& max_of(const Heavy& a, const Heavy& b) { return a.v >= b.v ? a : b; }

std::vector<Heavy> take_sorted(std::vector<Heavy> v) {
    std::sort(v.begin(), v.end(), [](const Heavy& x, const Heavy& y) { return x.v < y.v; });
    return v;
}

class Registry {
    std::vector<Heavy> items_;
public:
    void add(Heavy h) { items_.push_back(std::move(h)); }   // std::move on a const& silently copies
    std::size_t size() const { return items_.size(); }
    const Heavy& at(std::size_t i) const { return items_.at(i); }
};

Heavy choose(bool first, int x, int y) {
    Heavy a(x), b(y);
    if (first) return a;            // a conditional expression `c ? a : b` is not an id-expression: no implicit move
    return b;
}
