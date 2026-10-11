template <class K, class V, class Hash = std::hash<K>>
class HashMap {
    enum class State : std::uint8_t { Empty, Full, Tomb };
    struct Slot {
        State state = State::Empty;
        std::optional<std::pair<K, V>> kv;
    };
    std::vector<Slot> slots_;
    std::size_t size_ = 0;   // live entries
    std::size_t used_ = 0;   // live + tombstones: what the probe sequences actually pay for
    Hash hash_;

    static std::size_t round_up(std::size_t n) {
        std::size_t c = 8;
        while (c < n) c <<= 1;
        return c;
    }
    std::size_t home(const K& k) const {
        // Mix the hash: std::hash<int> is the identity and low-bit masking alone clusters badly.
        std::uint64_t h = static_cast<std::uint64_t>(hash_(k));
        h *= 0x9E3779B97F4A7C15ull;
        h ^= h >> 32;
        return static_cast<std::size_t>(h) & (slots_.size() - 1);
    }
    static constexpr std::size_t npos = static_cast<std::size_t>(-1);
    std::size_t find_index(const K& k) const {
        const std::size_t mask = slots_.size() - 1;
        for (std::size_t i = home(k);; i = (i + 1) & mask) {
            const Slot& s = slots_[i];
            if (s.state == State::Empty) return npos;               // chain ends only at a never-used slot
            if (s.state == State::Full && s.kv->first == k) return i;
        }
    }
    void rehash(std::size_t new_cap) {
        std::vector<Slot> old = std::move(slots_);
        slots_ = std::vector<Slot>(new_cap);   // assign(n, v) would need Slot to be copyable
        used_ = size_;
        const std::size_t mask = new_cap - 1;
        for (Slot& s : old) {
            if (s.state != State::Full) continue;
            std::size_t i = home(s.kv->first);
            while (slots_[i].state != State::Empty) i = (i + 1) & mask;
            slots_[i].state = State::Full;
            slots_[i].kv = std::move(s.kv);
        }
    }

public:
    explicit HashMap(std::size_t initial_buckets = 8) : slots_(round_up(initial_buckets)) {}

    bool insert_or_assign(const K& key, V value) {
        if (std::size_t i = find_index(key); i != npos) {
            slots_[i].kv->second = std::move(value);
            return false;
        }
        if ((used_ + 1) * 4 > slots_.size() * 3) {
            // Many tombstones, few live entries: rebuild at the same size to purge them, else double.
            rehash((size_ + 1) * 2 > slots_.size() ? slots_.size() * 2 : slots_.size());
        }
        const std::size_t mask = slots_.size() - 1;
        std::size_t i = home(key);
        while (slots_[i].state == State::Full) i = (i + 1) & mask;   // key is known absent: reuse first tombstone
        if (slots_[i].state == State::Empty) ++used_;
        slots_[i].state = State::Full;
        slots_[i].kv.emplace(key, std::move(value));
        ++size_;
        return true;
    }
    V* find(const K& key) {
        std::size_t i = find_index(key);
        return i == npos ? nullptr : &slots_[i].kv->second;
    }
    const V* find(const K& key) const {
        std::size_t i = find_index(key);
        return i == npos ? nullptr : &slots_[i].kv->second;
    }
    bool contains(const K& key) const { return find_index(key) != npos; }
    bool erase(const K& key) {
        std::size_t i = find_index(key);
        if (i == npos) return false;
        slots_[i].state = State::Tomb;       // cannot mark Empty: it would cut other keys' probe chains
        slots_[i].kv.reset();
        --size_;
        return true;
    }
    void clear() {
        for (Slot& s : slots_) { s.state = State::Empty; s.kv.reset(); }
        size_ = used_ = 0;
    }
    std::size_t size() const { return size_; }
    bool empty() const { return size_ == 0; }
    std::size_t bucket_count() const { return slots_.size(); }
};
