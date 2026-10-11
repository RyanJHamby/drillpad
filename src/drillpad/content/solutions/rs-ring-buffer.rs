struct RingBuffer<T> {
    slots: Vec<Option<T>>,
    head: usize,
    len: usize,
}

impl<T> RingBuffer<T> {
    fn new(capacity: usize) -> Self {
        RingBuffer {
            slots: std::iter::repeat_with(|| None).take(capacity).collect(),
            head: 0,
            len: 0,
        }
    }

    fn push(&mut self, value: T) -> Result<(), T> {
        if self.is_full() {
            return Err(value);
        }
        let idx = (self.head + self.len) % self.slots.len();
        self.slots[idx] = Some(value);
        self.len += 1;
        Ok(())
    }

    fn push_overwrite(&mut self, value: T) -> Option<T> {
        if self.slots.is_empty() {
            return Some(value);
        }
        if !self.is_full() {
            self.push(value).ok();
            return None;
        }
        let old = self.slots[self.head].replace(value);
        self.head = (self.head + 1) % self.slots.len();
        old
    }

    fn pop(&mut self) -> Option<T> {
        if self.len == 0 {
            return None;
        }
        let v = self.slots[self.head].take();
        self.head = (self.head + 1) % self.slots.len();
        self.len -= 1;
        v
    }

    fn peek(&self) -> Option<&T> {
        if self.len == 0 {
            None
        } else {
            self.slots[self.head].as_ref()
        }
    }

    fn len(&self) -> usize {
        self.len
    }

    fn capacity(&self) -> usize {
        self.slots.len()
    }

    fn is_empty(&self) -> bool {
        self.len == 0
    }

    fn is_full(&self) -> bool {
        self.len == self.slots.len()
    }

    fn iter(&self) -> Box<dyn Iterator<Item = &T> + '_> {
        let cap = self.slots.len();
        Box::new((0..self.len).filter_map(move |k| self.slots[(self.head + k) % cap].as_ref()))
    }
}
