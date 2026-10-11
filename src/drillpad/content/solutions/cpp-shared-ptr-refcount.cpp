struct SpControl {
    std::atomic<long> strong{1};
    virtual ~SpControl() = default;
    virtual void dispose() noexcept = 0;     // destroy the managed object
};

// Captures the object's REAL type at construction, so base-class views delete correctly.
template <class U>
struct SpControlImpl final : SpControl {
    U* obj;
    explicit SpControlImpl(U* p) : obj(p) {}
    void dispose() noexcept override { delete obj; }
};

template <class T>
class SharedPtr {
    T* ptr_ = nullptr;
    SpControl* ctl_ = nullptr;
    template <class U> friend class SharedPtr;

    void acquire() const noexcept {
        if (ctl_) ctl_->strong.fetch_add(1, std::memory_order_relaxed);    // no ordering needed to bump
    }
    void drop() noexcept {
        if (ctl_ && ctl_->strong.fetch_sub(1, std::memory_order_acq_rel) == 1) {
            ctl_->dispose();                 // acq_rel: all other owners' writes happen-before the delete
            delete ctl_;
        }
        ptr_ = nullptr; ctl_ = nullptr;
    }

public:
    SharedPtr() noexcept = default;
    SharedPtr(std::nullptr_t) noexcept {}
    template <class U>
        requires std::is_convertible_v<U*, T*>
    explicit SharedPtr(U* p) : ptr_(p) {
        if (!p) return;
        try { ctl_ = new SpControlImpl<U>(p); } catch (...) { delete p; throw; }
    }
    SharedPtr(const SharedPtr& o) noexcept : ptr_(o.ptr_), ctl_(o.ctl_) { acquire(); }
    SharedPtr(SharedPtr&& o) noexcept : ptr_(std::exchange(o.ptr_, nullptr)), ctl_(std::exchange(o.ctl_, nullptr)) {}
    template <class U>
        requires std::is_convertible_v<U*, T*>
    SharedPtr(const SharedPtr<U>& o) noexcept : ptr_(o.ptr_), ctl_(o.ctl_) { acquire(); }
    template <class U>
        requires std::is_convertible_v<U*, T*>
    SharedPtr(SharedPtr<U>&& o) noexcept : ptr_(std::exchange(o.ptr_, nullptr)), ctl_(std::exchange(o.ctl_, nullptr)) {}

    SharedPtr& operator=(const SharedPtr& o) noexcept { SharedPtr(o).swap(*this); return *this; }
    SharedPtr& operator=(SharedPtr&& o) noexcept { SharedPtr(std::move(o)).swap(*this); return *this; }
    ~SharedPtr() { drop(); }

    T* get() const noexcept { return ptr_; }
    T& operator*() const { return *ptr_; }
    T* operator->() const noexcept { return ptr_; }
    explicit operator bool() const noexcept { return ptr_ != nullptr; }
    long use_count() const noexcept { return ctl_ ? ctl_->strong.load(std::memory_order_relaxed) : 0; }
    void reset() noexcept { SharedPtr().swap(*this); }
    template <class U>
    void reset(U* p) { SharedPtr(p).swap(*this); }
    void swap(SharedPtr& o) noexcept { std::swap(ptr_, o.ptr_); std::swap(ctl_, o.ctl_); }
};
