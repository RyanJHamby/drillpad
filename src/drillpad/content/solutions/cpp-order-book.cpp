class OrderBook {
    struct Order { std::uint64_t id; std::int64_t qty; };
    using Queue = std::list<Order>;                       // FIFO within a price level
    std::map<std::int64_t, Queue, std::greater<>> bids_;  // begin() = best bid
    std::map<std::int64_t, Queue> asks_;                  // begin() = best ask
    struct Loc { Side side; std::int64_t price; Queue::iterator it; };
    std::unordered_map<std::uint64_t, Loc> index_;        // id -> where it rests, for O(1) cancel
    std::uint64_t next_id_ = 1;

    // Consume from the best levels of `book` while `ok(level_price)` holds and qty remains.
    template <class Book, class Pred>
    void sweep(Book& book, Pred ok, std::int64_t& qty, std::vector<Fill>& fills) {
        while (qty > 0 && !book.empty()) {
            auto lvl = book.begin();
            const std::int64_t price = lvl->first;
            if (!ok(price)) break;
            Queue& q = lvl->second;
            while (qty > 0 && !q.empty()) {
                Order& o = q.front();
                const std::int64_t take = std::min(qty, o.qty);
                fills.push_back({o.id, price, take});
                qty -= take;
                o.qty -= take;
                if (o.qty == 0) { index_.erase(o.id); q.pop_front(); }
            }
            if (q.empty()) book.erase(lvl);
        }
    }

    template <class Book>
    void rest(Book& book, Side side, std::uint64_t id, std::int64_t price, std::int64_t qty) {
        Queue& q = book[price];
        q.push_back({id, qty});
        index_[id] = {side, price, std::prev(q.end())};
    }

    template <class Book>
    std::vector<PriceLevel> depth_of(const Book& book) const {
        std::vector<PriceLevel> out;
        for (const auto& [price, q] : book) {
            std::int64_t total = 0;
            for (const Order& o : q) total += o.qty;
            out.push_back({price, total});
        }
        return out;
    }

public:
    LimitResult limit(Side side, std::int64_t price, std::int64_t qty) {
        if (price <= 0 || qty <= 0) throw std::invalid_argument("price and qty must be positive");
        LimitResult res{next_id_++, {}};
        if (side == Side::Buy) {
            sweep(asks_, [&](std::int64_t p) { return p <= price; }, qty, res.fills);
            if (qty > 0) rest(bids_, side, res.id, price, qty);
        } else {
            sweep(bids_, [&](std::int64_t p) { return p >= price; }, qty, res.fills);
            if (qty > 0) rest(asks_, side, res.id, price, qty);
        }
        return res;
    }

    std::vector<Fill> market(Side side, std::int64_t qty) {
        if (qty <= 0) throw std::invalid_argument("qty must be positive");
        std::vector<Fill> fills;
        auto any = [](std::int64_t) { return true; };
        if (side == Side::Buy) sweep(asks_, any, qty, fills);
        else sweep(bids_, any, qty, fills);
        return fills;
    }

    bool cancel(std::uint64_t id) {
        auto it = index_.find(id);
        if (it == index_.end()) return false;
        const Loc loc = it->second;
        index_.erase(it);
        auto erase_from = [&](auto& book) {
            auto lvl = book.find(loc.price);
            lvl->second.erase(loc.it);            // list erase by iterator is O(1)
            if (lvl->second.empty()) book.erase(lvl);
        };
        if (loc.side == Side::Buy) erase_from(bids_); else erase_from(asks_);
        return true;
    }

    std::optional<std::int64_t> best_bid() const {
        return bids_.empty() ? std::nullopt : std::optional<std::int64_t>(bids_.begin()->first);
    }
    std::optional<std::int64_t> best_ask() const {
        return asks_.empty() ? std::nullopt : std::optional<std::int64_t>(asks_.begin()->first);
    }
    std::vector<PriceLevel> depth(Side side) const {
        return side == Side::Buy ? depth_of(bids_) : depth_of(asks_);
    }
};
