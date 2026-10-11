template <class T, class D = std::default_delete<T>>
class UniquePtr {
    T* ptr_ = nullptr;
    [[no_unique_address]] D del_{};

public:
    constexpr UniquePtr() noexcept = default;
    constexpr UniquePtr(std::nullptr_t) noexcept {}
    explicit UniquePtr(T* p) noexcept : ptr_(p) {}
    UniquePtr(T* p, D d) noexcept : ptr_(p), del_(std::move(d)) {}

    UniquePtr(const UniquePtr&) = delete;
    UniquePtr& operator=(const UniquePtr&) = delete;

    UniquePtr(UniquePtr&& o) noexcept : ptr_(o.release()), del_(std::move(o.del_)) {}

    template <class U, class E>
        requires std::is_convertible_v<U*, T*> && std::is_convertible_v<E, D>
    UniquePtr(UniquePtr<U, E>&& o) noexcept : ptr_(o.release()), del_(std::move(o.get_deleter())) {}

    ~UniquePtr() { reset(); }

    UniquePtr& operator=(UniquePtr&& o) noexcept {
        if (this != &o) {
            reset(o.release());
            del_ = std::move(o.del_);
        }
        return *this;
    }
    UniquePtr& operator=(std::nullptr_t) noexcept { reset(); return *this; }

    T* get() const noexcept { return ptr_; }
    T* release() noexcept { return std::exchange(ptr_, nullptr); }
    void reset(T* p = nullptr) noexcept {
        T* old = std::exchange(ptr_, p);
        if (old) del_(old);
    }
    void swap(UniquePtr& o) noexcept { std::swap(ptr_, o.ptr_); std::swap(del_, o.del_); }

    T& operator*() const { return *ptr_; }
    T* operator->() const noexcept { return ptr_; }
    explicit operator bool() const noexcept { return ptr_ != nullptr; }
    D& get_deleter() noexcept { return del_; }
    const D& get_deleter() const noexcept { return del_; }
};

template <class T, class... Args>
UniquePtr<T> make_unique_ptr(Args&&... args) {
    return UniquePtr<T>(new T(std::forward<Args>(args)...));
}
