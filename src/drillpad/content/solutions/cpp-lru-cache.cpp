template <class K, class V>
class LRUCache {
    using Item = std::pair<K, V>;
    using List = std::list<Item>;
    std::size_t cap_;
    List items_;   // front = most recently used
    std::unordered_map<K, typename List::iterator> index_;

public:
    explicit LRUCache(std::size_t capacity) : cap_(capacity) { index_.reserve(capacity); }

    V* get(const K& key) {
        auto it = index_.find(key);
        if (it == index_.end()) return nullptr;
        items_.splice(items_.begin(), items_, it->second);   // O(1), node (and its address) stays put
        return &it->second->second;
    }

    void put(const K& key, V value) {
        if (cap_ == 0) return;
        auto it = index_.find(key);
        if (it != index_.end()) {
            it->second->second = std::move(value);
            items_.splice(items_.begin(), items_, it->second);
            return;
        }
        if (items_.size() == cap_) {
            index_.erase(items_.back().first);
            items_.pop_back();
        }
        items_.emplace_front(key, std::move(value));
        index_[key] = items_.begin();
    }

    bool contains(const K& key) const { return index_.find(key) != index_.end(); }

    bool erase(const K& key) {
        auto it = index_.find(key);
        if (it == index_.end()) return false;
        items_.erase(it->second);
        index_.erase(it);
        return true;
    }

    std::size_t size() const { return items_.size(); }
    std::size_t capacity() const { return cap_; }
};
