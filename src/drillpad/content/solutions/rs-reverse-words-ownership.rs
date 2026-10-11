fn reverse_words(s: &str) -> String {
    let words: Vec<&str> = s.split_whitespace().collect();
    words.iter().rev().copied().collect::<Vec<_>>().join(" ")
}

fn reverse_each_word(s: &str) -> String {
    s.split_whitespace()
        .map(|w| w.chars().rev().collect::<String>())
        .collect::<Vec<_>>()
        .join(" ")
}

fn first_word(s: &str) -> &str {
    s.split_whitespace().next().unwrap_or("")
}

fn longest_word(s: &str) -> &str {
    let mut best = "";
    let mut best_len = 0;
    for w in s.split_whitespace() {
        let n = w.chars().count();
        if n > best_len {
            best = w;
            best_len = n;
        }
    }
    best
}
