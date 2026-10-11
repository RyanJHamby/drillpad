use std::collections::{BTreeMap, HashMap, VecDeque};

struct OrderBook {
    bids: BTreeMap<u64, VecDeque<(u64, u64)>>,
    asks: BTreeMap<u64, VecDeque<(u64, u64)>>,
    orders: HashMap<u64, (Side, u64)>,
    next_id: u64,
}

impl OrderBook {
    fn new() -> Self {
        OrderBook {
            bids: BTreeMap::new(),
            asks: BTreeMap::new(),
            orders: HashMap::new(),
            next_id: 1,
        }
    }

    /// Match `qty` of an incoming `side` order against the opposite book. Returns (remaining, fills).
    fn match_against(&mut self, side: Side, mut qty: u64, limit: Option<u64>) -> (u64, Vec<Fill>) {
        let mut fills = Vec::new();
        let book = match side {
            Side::Buy => &mut self.asks,
            Side::Sell => &mut self.bids,
        };
        while qty > 0 {
            let best = match side {
                Side::Buy => book.keys().next().copied(),
                Side::Sell => book.keys().next_back().copied(),
            };
            let price = match best {
                Some(p) => p,
                None => break,
            };
            if let Some(l) = limit {
                let crosses = match side {
                    Side::Buy => price <= l,
                    Side::Sell => price >= l,
                };
                if !crosses {
                    break;
                }
            }
            let queue = book.get_mut(&price).unwrap();
            while qty > 0 {
                let (id, rest) = match queue.front_mut() {
                    Some(front) => (front.0, front.1),
                    None => break,
                };
                let take = qty.min(rest);
                fills.push(Fill { order_id: id, price, qty: take });
                qty -= take;
                if take == rest {
                    queue.pop_front();
                    self.orders.remove(&id);
                } else {
                    queue.front_mut().unwrap().1 -= take;
                }
            }
            if queue.is_empty() {
                book.remove(&price);
            }
        }
        (qty, fills)
    }

    fn limit(&mut self, side: Side, price: u64, qty: u64) -> Result<(u64, Vec<Fill>), BookError> {
        if price == 0 {
            return Err(BookError::ZeroPrice);
        }
        if qty == 0 {
            return Err(BookError::ZeroQty);
        }
        let id = self.next_id;
        self.next_id += 1;
        let (rem, fills) = self.match_against(side, qty, Some(price));
        if rem > 0 {
            let book = match side {
                Side::Buy => &mut self.bids,
                Side::Sell => &mut self.asks,
            };
            book.entry(price).or_default().push_back((id, rem));
            self.orders.insert(id, (side, price));
        }
        Ok((id, fills))
    }

    fn market(&mut self, side: Side, qty: u64) -> Result<Vec<Fill>, BookError> {
        if qty == 0 {
            return Err(BookError::ZeroQty);
        }
        Ok(self.match_against(side, qty, None).1)
    }

    fn cancel(&mut self, order_id: u64) -> bool {
        let (side, price) = match self.orders.remove(&order_id) {
            Some(x) => x,
            None => return false,
        };
        let book = match side {
            Side::Buy => &mut self.bids,
            Side::Sell => &mut self.asks,
        };
        if let Some(queue) = book.get_mut(&price) {
            queue.retain(|&(id, _)| id != order_id);
            if queue.is_empty() {
                book.remove(&price);
            }
        }
        true
    }

    fn best_bid(&self) -> Option<u64> {
        self.bids.keys().next_back().copied()
    }

    fn best_ask(&self) -> Option<u64> {
        self.asks.keys().next().copied()
    }

    fn depth(&self, side: Side) -> Vec<(u64, u64)> {
        let level = |(p, q): (&u64, &VecDeque<(u64, u64)>)| (*p, q.iter().map(|o| o.1).sum::<u64>());
        match side {
            Side::Buy => self.bids.iter().rev().map(level).collect(),
            Side::Sell => self.asks.iter().map(level).collect(),
        }
    }
}
