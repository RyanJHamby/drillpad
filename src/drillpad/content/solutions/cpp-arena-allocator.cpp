class Arena {
    std::unique_ptr<std::byte[]> buf_;
    std::size_t cap_;
    std::size_t off_ = 0;

public:
    explicit Arena(std::size_t capacity_bytes) : buf_(new std::byte[capacity_bytes]), cap_(capacity_bytes) {}
    Arena(const Arena&) = delete;
    Arena& operator=(const Arena&) = delete;

    void* allocate(std::size_t size, std::size_t align = alignof(std::max_align_t)) {
        if (align == 0 || (align & (align - 1)) != 0) return nullptr;
        // Align the absolute address: the buffer base itself is only guaranteed max_align_t aligned.
        const auto base = reinterpret_cast<std::uintptr_t>(buf_.get());
        const std::uintptr_t cur = base + off_;
        const std::uintptr_t aligned = (cur + (align - 1)) & ~(static_cast<std::uintptr_t>(align) - 1);
        const std::size_t pad = static_cast<std::size_t>(aligned - cur);
        // Compare against remaining space instead of adding, so huge sizes cannot overflow.
        if (pad > cap_ - off_ || size > cap_ - off_ - pad) return nullptr;
        off_ += pad + size;                     // a failed request changes nothing
        return buf_.get() + (off_ - size);
    }
    template <class T, class... Args>
    T* create(Args&&... args) {
        void* p = allocate(sizeof(T), alignof(T));
        return p ? ::new (p) T(std::forward<Args>(args)...) : nullptr;
    }
    void reset() { off_ = 0; }
    std::size_t used() const { return off_; }
    std::size_t capacity() const { return cap_; }
};

template <class T>
class ObjectPool {
    union Slot {
        Slot* next;
        alignas(T) unsigned char storage[sizeof(T)];
        Slot() : next(nullptr) {}
    };
    std::vector<Slot> slots_;
    Slot* free_ = nullptr;
    std::size_t available_;

public:
    explicit ObjectPool(std::size_t capacity) : slots_(capacity), available_(capacity) {
        for (std::size_t i = capacity; i > 0; --i) {     // thread the free list so slot 0 is handed out first
            slots_[i - 1].next = free_;
            free_ = &slots_[i - 1];
        }
    }
    ObjectPool(const ObjectPool&) = delete;
    ObjectPool& operator=(const ObjectPool&) = delete;

    template <class... Args>
    T* acquire(Args&&... args) {
        if (!free_) return nullptr;
        Slot* s = free_;
        Slot* next = s->next;                    // read BEFORE constructing: the object overwrites these bytes
        T* obj;
        try {
            obj = ::new (static_cast<void*>(s->storage)) T(std::forward<Args>(args)...);
        } catch (...) { s->next = next; throw; }
        free_ = next;
        --available_;
        return obj;
    }
    void release(T* p) {
        p->~T();
        Slot* s = reinterpret_cast<Slot*>(p);    // storage is the union's address
        s->next = free_;
        free_ = s;
        ++available_;
    }
    std::size_t available() const { return available_; }
    std::size_t capacity() const { return slots_.size(); }
};
