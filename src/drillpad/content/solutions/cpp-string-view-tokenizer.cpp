#include <charconv>

static bool is_space(char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v';
}

std::string_view trim(std::string_view s) {
    while (!s.empty() && is_space(s.front())) s.remove_prefix(1);
    while (!s.empty() && is_space(s.back())) s.remove_suffix(1);
    return s;
}

std::vector<std::string_view> split(std::string_view s, char delim) {
    std::vector<std::string_view> out;
    for (;;) {
        std::size_t pos = s.find(delim);
        if (pos == std::string_view::npos) { out.push_back(s); return out; }
        out.push_back(s.substr(0, pos));
        s.remove_prefix(pos + 1);
    }
}

std::vector<std::string_view> split_ws(std::string_view s) {
    std::vector<std::string_view> out;
    std::size_t i = 0;
    while (i < s.size()) {
        while (i < s.size() && is_space(s[i])) ++i;
        std::size_t start = i;
        while (i < s.size() && !is_space(s[i])) ++i;
        if (i > start) out.push_back(s.substr(start, i - start));
    }
    return out;
}

std::optional<std::int64_t> parse_int(std::string_view s) {
    if (s.empty()) return std::nullopt;
    std::int64_t v = 0;
    auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), v);
    if (ec != std::errc{} || ptr != s.data() + s.size()) return std::nullopt;   // overflow, junk or trailing chars
    return v;
}

std::optional<std::pair<std::string_view, std::string_view>> parse_kv(std::string_view line) {
    std::size_t eq = line.find('=');
    if (eq == std::string_view::npos) return std::nullopt;
    std::string_view key = trim(line.substr(0, eq));
    if (key.empty()) return std::nullopt;
    return std::make_pair(key, trim(line.substr(eq + 1)));
}
