# Testing Pyramid: Unit vs Integration vs E2E

## The Framework

```
         /\
        /  \  E2E (5-10% of tests)
       /----\
      /      \  Integration (20-30%)
     /--------\
    /          \  Unit (60-80%)
   /____________\
```

**Key insight:** Write many unit tests, fewer integration, minimal E2E

## Unit Tests (60-80% of your tests)

```cpp
// Test one function in isolation
TEST(OrderBook, MatchingLogic) {
  Order buy(Side::BUY, 100, 50);
  Order sell(Side::SELL, 100, 50);
  auto match = matching_engine.match(buy, sell);
  EXPECT_EQ(match.quantity, 100);
}

Cost: <1ms per test
Value: Fast feedback, catches logic bugs early
Use: Pure logic, algorithms, complex functions
```

## Integration Tests (20-30% of your tests)

```cpp
// Test components together (but not full system)
TEST(OrderBook, InsertAndMatchingFlow) {
  OrderBook book;
  book.insert(Order{...}); // Inserts into data structure
  book.insert(Order{...}); // Triggers matching
  
  auto fills = book.get_fills(); // Reads results
  EXPECT_EQ(fills.size(), 1);
}

Cost: 5-100ms per test (depends on I/O)
Value: Catches integration bugs, flow issues
Use: API interactions, data structure + logic, partial workflows
```

## E2E Tests (5-10% of your tests)

```cpp
// Full system end-to-end
TEST(OrderBook, EndToEnd) {
  Server server;
  Client client;
  
  client.send_order(Order{...});
  auto response = client.wait_for_response(100ms);
  EXPECT_EQ(response.status, Status::FILLED);
}

Cost: 100ms-1s per test (network, latency)
Value: Catches real-world issues
Use: Critical paths only (sign-up, payment, matching)
```

## Trading Interview: Test Coverage Tradeoff

```
Q: "Design tests for your order matching engine"

Weak answer:
  "100% code coverage with unit tests"
  (❌ Misses integration bugs, slow CI)

Strong answer:
  "Pyramid strategy:
   - 70% unit: matching logic, data structures
   - 20% integration: matching flow, order sequence
   - 10% E2E: full pipeline latency
   
   Why this split:
   - Unit tests: fast feedback (1s total)
   - Integration: catch ordering bugs
   - E2E: verify latency SLA
   
   E2E only for critical paths (matching engine,
   not admin tools).
   
   CI time: <2 min (unit fast, E2E on separate job)"
  (✅ Shows understanding of tradeoffs)
```

## Common Mistakes

```
❌ All E2E tests: CI takes 30 min, slow feedback
❌ No integration tests: unit tests pass, E2E fails
❌ Testing implementation details: brittle tests that break on refactor
✅ Test behavior, not implementation
✅ Use pyramid (many unit, few E2E)
✅ E2E only for critical paths
```

