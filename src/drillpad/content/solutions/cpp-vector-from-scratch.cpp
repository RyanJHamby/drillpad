template <class T>
class Vec {
    T* data_ = nullptr;
    std::size_t size_ = 0, cap_ = 0;

    static T* alloc(std::size_t n) { return static_cast<T*>(::operator new(n * sizeof(T))); }
    static void dealloc(T* p) noexcept { ::operator delete(p); }
    void destroy_all() noexcept {
        for (std::size_t i = size_; i > 0; --i) data_[i - 1].~T();
        size_ = 0;
    }
    void swap(Vec& o) noexcept {
        std::swap(data_, o.data_); std::swap(size_, o.size_); std::swap(cap_, o.cap_);
    }
    // Move (or copy, if move may throw) the live elements into fresh storage of capacity n.
    void relocate(T* fresh, std::size_t n) {
        std::size_t done = 0;
        try {
            for (; done < size_; ++done) ::new (fresh + done) T(std::move_if_noexcept(data_[done]));
        } catch (...) {
            for (std::size_t i = done; i > 0; --i) fresh[i - 1].~T();
            throw;
        }
        std::size_t count = size_;
        destroy_all();
        dealloc(data_);
        data_ = fresh; cap_ = n; size_ = count;
    }

public:
    Vec() = default;
    Vec(const Vec& other) {
        if (other.size_ == 0) return;
        data_ = alloc(other.size_); cap_ = other.size_;
        try {
            for (; size_ < other.size_; ++size_) ::new (data_ + size_) T(other.data_[size_]);
        } catch (...) { destroy_all(); dealloc(data_); throw; }
    }
    Vec(Vec&& other) noexcept { swap(other); }
    Vec& operator=(const Vec& other) { Vec tmp(other); swap(tmp); return *this; }
    Vec& operator=(Vec&& other) noexcept { Vec tmp(std::move(other)); swap(tmp); return *this; }
    ~Vec() { destroy_all(); dealloc(data_); }

    template <class... Args>
    T& emplace_back(Args&&... args) {
        if (size_ == cap_) {
            std::size_t n = cap_ ? cap_ * 2 : 1;
            T* fresh = alloc(n);
            // Construct the new element first: args may alias an element of *this.
            try { ::new (fresh + size_) T(std::forward<Args>(args)...); } catch (...) { dealloc(fresh); throw; }
            try { relocate(fresh, n); } catch (...) { fresh[size_].~T(); dealloc(fresh); throw; }
            ++size_;
            return data_[size_ - 1];
        }
        ::new (data_ + size_) T(std::forward<Args>(args)...);
        ++size_;
        return data_[size_ - 1];
    }
    void push_back(const T& v) { emplace_back(v); }
    void push_back(T&& v) { emplace_back(std::move(v)); }
    void pop_back() { data_[--size_].~T(); }
    void clear() noexcept { destroy_all(); }
    void reserve(std::size_t n) {
        if (n <= cap_) return;
        T* fresh = alloc(n);
        try { relocate(fresh, n); } catch (...) { dealloc(fresh); throw; }
    }

    T& operator[](std::size_t i) { return data_[i]; }
    const T& operator[](std::size_t i) const { return data_[i]; }
    T& at(std::size_t i) { if (i >= size_) throw std::out_of_range("Vec::at"); return data_[i]; }
    const T& at(std::size_t i) const { if (i >= size_) throw std::out_of_range("Vec::at"); return data_[i]; }
    T& back() { return data_[size_ - 1]; }

    std::size_t size() const { return size_; }
    std::size_t capacity() const { return cap_; }
    bool empty() const { return size_ == 0; }
    T* data() { return data_; }
    T* begin() { return data_; }
    T* end() { return data_ + size_; }

};
