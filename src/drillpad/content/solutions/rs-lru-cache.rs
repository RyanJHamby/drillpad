use std::collections::HashMap;
use std::hash::Hash;

const NIL: usize = usize::MAX;

struct Entry<K, V> {
    key: K,
    val: V,
    prev: usize,
    next: usize,
}

struct LruCache<K, V> {
    map: HashMap<K, usize>,
    entries: Vec<Entry<K, V>>,
    capacity: usize,
    head: usize,
    tail: usize,
}

impl<K: Hash + Eq + Clone, V> LruCache<K, V> {
    fn new(capacity: usize) -> Self {
        LruCache {
            map: HashMap::with_capacity(capacity.min(1 << 16)),
            entries: Vec::new(),
            capacity,
            head: NIL,
            tail: NIL,
        }
    }

    fn detach(&mut self, i: usize) {
        let (prev, next) = (self.entries[i].prev, self.entries[i].next);
        if prev != NIL {
            self.entries[prev].next = next;
        } else {
            self.head = next;
        }
        if next != NIL {
            self.entries[next].prev = prev;
        } else {
            self.tail = prev;
        }
        self.entries[i].prev = NIL;
        self.entries[i].next = NIL;
    }

    fn attach_front(&mut self, i: usize) {
        self.entries[i].prev = NIL;
        self.entries[i].next = self.head;
        if self.head != NIL {
            let h = self.head;
            self.entries[h].prev = i;
        } else {
            self.tail = i;
        }
        self.head = i;
    }

    fn get(&mut self, key: &K) -> Option<&V> {
        let i = *self.map.get(key)?;
        self.detach(i);
        self.attach_front(i);
        Some(&self.entries[i].val)
    }

    fn peek(&self, key: &K) -> Option<&V> {
        self.map.get(key).map(|&i| &self.entries[i].val)
    }

    fn put(&mut self, key: K, value: V) -> Option<(K, V)> {
        if self.capacity == 0 {
            return Some((key, value));
        }
        if let Some(&i) = self.map.get(&key) {
            self.entries[i].val = value;
            self.detach(i);
            self.attach_front(i);
            return None;
        }
        let mut evicted = None;
        let i;
        if self.entries.len() < self.capacity {
            self.entries.push(Entry { key: key.clone(), val: value, prev: NIL, next: NIL });
            i = self.entries.len() - 1;
        } else {
            i = self.tail;
            self.detach(i);
            let old_key = std::mem::replace(&mut self.entries[i].key, key.clone());
            let old_val = std::mem::replace(&mut self.entries[i].val, value);
            self.map.remove(&old_key);
            evicted = Some((old_key, old_val));
        }
        self.map.insert(key, i);
        self.attach_front(i);
        evicted
    }

    fn contains(&self, key: &K) -> bool {
        self.map.contains_key(key)
    }

    fn len(&self) -> usize {
        self.map.len()
    }

    fn keys_mru_first(&self) -> Vec<K> {
        let mut out = Vec::with_capacity(self.map.len());
        let mut i = self.head;
        while i != NIL {
            out.push(self.entries[i].key.clone());
            i = self.entries[i].next;
        }
        out
    }
}
