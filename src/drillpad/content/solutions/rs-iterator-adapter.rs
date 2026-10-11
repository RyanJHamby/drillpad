struct Fibonacci {
    cur: Option<u64>,
    next: Option<u64>,
}

impl Fibonacci {
    fn new() -> Self {
        Fibonacci { cur: Some(0), next: Some(1) }
    }
}

impl Iterator for Fibonacci {
    type Item = u64;

    fn next(&mut self) -> Option<u64> {
        let c = self.cur?;
        let n = self.next;
        self.cur = n;
        self.next = n.and_then(|n| c.checked_add(n));
        Some(c)
    }
}

struct Stride<I> {
    iter: I,
    n: usize,
    first: bool,
}

impl<I: Iterator> Iterator for Stride<I> {
    type Item = I::Item;

    fn next(&mut self) -> Option<I::Item> {
        if self.n == 0 {
            return None;
        }
        if self.first {
            self.first = false;
            self.iter.next()
        } else {
            self.iter.nth(self.n - 1)
        }
    }
}

struct Pairwise<I: Iterator> {
    iter: I,
    prev: Option<I::Item>,
}

impl<I: Iterator> Iterator for Pairwise<I>
where
    I::Item: Clone,
{
    type Item = (I::Item, I::Item);

    fn next(&mut self) -> Option<Self::Item> {
        if self.prev.is_none() {
            self.prev = Some(self.iter.next()?);
        }
        let cur = self.iter.next()?;
        let prev = std::mem::replace(&mut self.prev, Some(cur.clone()))?;
        Some((prev, cur))
    }
}

trait IterExt: Iterator + Sized {
    fn stride(self, n: usize) -> Stride<Self> {
        Stride { iter: self, n, first: true }
    }

    fn pairwise(self) -> Pairwise<Self>
    where
        Self::Item: Clone,
    {
        Pairwise { iter: self, prev: None }
    }
}

impl<I: Iterator> IterExt for I {}
