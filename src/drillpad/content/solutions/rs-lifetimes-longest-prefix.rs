fn longest_common_prefix<'a>(words: &[&'a str]) -> &'a str {
    let first: &'a str = match words.first() {
        Some(w) => w,
        None => return "",
    };
    let mut end = first.len();
    for w in &words[1..] {
        let mut common = 0;
        let mut a = first.char_indices();
        let mut b = w.chars();
        while let (Some((i, ca)), Some(cb)) = (a.next(), b.next()) {
            if ca != cb {
                break;
            }
            common = i + ca.len_utf8();
        }
        end = end.min(common);
        if end == 0 {
            break;
        }
    }
    &first[..end]
}

fn split_at_delim<'a>(s: &'a str, delim: char) -> (&'a str, &'a str) {
    match s.find(delim) {
        Some(i) => (&s[..i], &s[i + delim.len_utf8()..]),
        None => (s, ""),
    }
}

fn is_punct(c: char) -> bool {
    "(),;+-*/=".contains(c)
}

struct Tokenizer<'a> {
    src: &'a str,
    pos: usize,
}

impl<'a> Tokenizer<'a> {
    fn new(src: &'a str) -> Tokenizer<'a> {
        Tokenizer { src, pos: 0 }
    }
}

impl<'a> Iterator for Tokenizer<'a> {
    type Item = &'a str;

    fn next(&mut self) -> Option<&'a str> {
        let src: &'a str = self.src;
        let rest = &src[self.pos..];
        let trimmed = rest.trim_start();
        self.pos += rest.len() - trimmed.len();
        let first = trimmed.chars().next()?;
        let end = if is_punct(first) {
            first.len_utf8()
        } else {
            trimmed
                .find(|c: char| c.is_whitespace() || is_punct(c))
                .unwrap_or(trimmed.len())
        };
        self.pos += end;
        Some(&trimmed[..end])
    }
}
