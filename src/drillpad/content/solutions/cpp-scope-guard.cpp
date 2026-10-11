template <class F>
class ScopeGuard {
    F f_;
    bool active_ = true;
public:
    explicit ScopeGuard(F f) : f_(std::move(f)) {}
    ScopeGuard(const ScopeGuard&) = delete;
    ScopeGuard& operator=(const ScopeGuard&) = delete;
    ScopeGuard(ScopeGuard&& o) noexcept(std::is_nothrow_move_constructible_v<F>)
        : f_(std::move(o.f_)), active_(std::exchange(o.active_, false)) {}
    ~ScopeGuard() {
        if (!active_) return;
        try { f_(); } catch (...) {}      // a destructor must not throw (it may run during unwinding)
    }
    void dismiss() noexcept { active_ = false; }
};

template <class F>
ScopeGuard<F> make_scope_guard(F f) { return ScopeGuard<F>(std::move(f)); }

void add_to_both(Sink& a, Sink& b, int v) {
    a.add(v);
    ScopeGuard rollback([&] { a.remove_last(); });
    b.add(v);                        // may throw: rollback undoes the add to a
    rollback.dismiss();              // everything succeeded: keep both
}
