# Memory Layout and Virtual Memory: Pages, Faults, and TLB

## Overview

1. Process memory layout (stack, heap, code, data)
2. Virtual memory (paging, TLB, page faults)
3. Page fault cost (100+ microseconds!)
4. Memory-mapped I/O (mmap)

---

## Process Memory Layout

```
High address
  ┌─────────────────────────────┐
  │ Kernel (1GB)                │  Not accessible from user code
  └─────────────────────────────┘
  
  ┌─────────────────────────────┐
  │ Stack (grows down)          │  Local variables, function calls
  │ Stack pointer →             │  ~8MB default
  └─────────────────────────────┘
  
  ┌─────────────────────────────┐
  │ [unused space]              │  Heap can grow up, stack grows down
  └─────────────────────────────┘
  
  ┌─────────────────────────────┐
  │ Heap (grows up)             │  malloc/new allocations
  │ Heap pointer →              │  Unlimited (swap space)
  └─────────────────────────────┘
  
  ┌─────────────────────────────┐
  │ BSS (uninitialized data)    │  Global arrays, static memory
  │ Data (initialized globals)  │
  │ Code (.text)                │
  └─────────────────────────────┘
Low address
```

**Key sizes:**
- Stack: ~8MB (fixed, growing down)
- Heap: unlimited (growing up)
- Code: varies (50KB - 100MB typical)

---

## Virtual Memory and Paging

OS provides each process illusion of infinite memory. Actual mapping:

```
Virtual address (what program sees):
  0x7fffffff123  (32-bit: 4GB address space per process)
  0x12345678     (64-bit: 256TB address space per process)

Physical address (actual RAM):
  0xabcd1234     (8GB physical RAM)

Translation: MMU (Memory Management Unit) translates virtual → physical
  Uses page tables (kept in RAM)
  Fast lookup: TLB (Translation Lookaside Buffer, on CPU)
```

**Pages:**
```
4KB page (typical):
  Virtual address 0x12345000 → maps to physical address 0xabcd0000
  Virtual address 0x12345001 → same page (0xabcd0001)

64-bit virtual address breakdown:
  Bits 0-11: offset within page (4KB = 2^12)
  Bits 12-63: page number

Example:
  Virtual 0x123456789abc
  Offset: 0xabc (page-internal offset)
  Page #: 0x123456789 (virtual page number)
```

---

## TLB and Page Faults

**TLB (Translation Lookaside Buffer):**
```
Fast cache of recent virtual→physical translations
  ~128-256 entries
  L1 TLB: 1-4 cycle lookup (fast)
  L2 TLB: 10-20 cycle lookup (slower)
  Miss: walk page tables (100+ cycles)

TLB hit: virtual → physical in 1-2 cycles (~1 nanosecond)
TLB miss: walk page table, 100+ cycles (~30-50 nanoseconds)
```

**Page Fault:**
```
Virtual address not mapped (page not in RAM):

1. MMU: "Address not in TLB, check page table"
2. Page table: "This page is on disk"
3. OS: Generate page fault interrupt
4. OS handler:
   - Find a free page in RAM (or evict old page)
   - Read page from disk (5-10 milliseconds!)
   - Update page table
   - Resume instruction
   
Total cost: 5-10 milliseconds (10 million CPU cycles!)
```

**Minor vs major faults:**
```
Minor fault: Page in memory, just not in TLB
  Cost: ~1 microsecond (reload TLB)
  
Major fault: Page on disk, must read
  Cost: 5-10 milliseconds
  
Example: First access to large array
  Array allocated but not yet accessed
  Major fault: 5ms to load first page
  Subsequent accesses: minor fault (TLB miss = 50ns)
```

---

## Page Fault Spike in Latency Systems

```
Order book latency normally: 0.2 microseconds per order

Scenario: Process allocated large memory (2GB array)
  At startup: allocated but not accessed (lazy allocation)
  
Order arrives, touches previously unmapped memory:
  Page fault! OS reads 4KB from disk
  5 milliseconds to load page
  
Latency spike: 0.2µs → 5000µs (25,000x worse!)

Prevention:
  1. Touch all memory at startup (mlockall on Linux)
  2. Use huge pages (2MB instead of 4KB, fewer faults)
  3. Avoid dynamic allocation in hot path
```

---

## Memory-Mapped I/O (mmap)

mmap maps files directly to memory:

```
Traditional I/O:
  read(fd, buffer, 1MB)   → System call, copy from kernel to user space
  Cost: 1 context switch (10-100µs) + data copy

Memory-mapped:
  void *ptr = mmap(NULL, 1MB, PROT_READ, MAP_SHARED, fd, 0);
  *ptr  → Direct memory access (no copy)
  Cost: ~1 page fault on first access (5ms once)
```

**When mmap wins:**

```
Sequential read (1GB file):
  Traditional: 1000 × read(1MB) = 1000 system calls = milliseconds overhead
  mmap: 1 mmap call, then sequential access, TLB hits after first page
  
Random access (sparse):
  Traditional: fast, each read is small
  mmap: page faults for each random region (bad)
```

---

## Practical: Order Book with mmap

```cpp
// Bad: Allocates 100MB, first access causes page fault spike
std::vector<Order> orders(1000000);

// Better: mmap, no page fault (already paged)
int fd = open("order_log.bin", O_RDONLY);
void *ptr = mmap(NULL, 100MB, PROT_READ, MAP_SHARED, fd, 0);

// Best: Preallocate and touch memory
std::vector<Order> orders(1000000);
for (size_t i = 0; i < orders.size(); i += 4096) {
  volatile char c = *((char*)&orders[i]);  // Touch each page
}
```

---

## Most Likely Questions

**Q1: "Your P99.9 latency is 5ms. Why?"**

A: "Page fault. Data was allocated but not accessed until request. OS had to read from disk (5ms). Fix: preallocate and touch memory at startup using madvise(MADV_POPULATE), or use huge pages (2MB instead of 4KB = fewer faults)."

**Q2: "What's a TLB miss?"**

A: "Virtual address translation. Normally instant (TLB hit = 1ns). Miss: OS walks page table (~50ns). Page fault (address not in RAM): OS reads from disk (~5ms). Miss is fast, fault is slow."

**Q3: "How do you prevent page faults?"**

A: "Three tactics: (1) mlockall() - lock all memory in RAM, (2) madvise(MADV_POPULATE) - touch all pages at startup, (3) huge pages (2MB instead of 4KB) - fewer pages to fault. Most traders use (3): hugetlbfs for critical buffers."

**Q4: "mmap vs read() for log files?"**

A: "mmap for large sequential reads (no syscall overhead), read() for small random reads (fewer page faults). mmap: lazy loading, page faults on first access of each page. read(): explicit control, predictable."

**Q5: "Why is heap allocation slow?"**

A: "Two reasons: (1) system call overhead (brk or mmap), (2) page faults if new pages needed. malloc avoids (1) by pooling, but (2) still happens on first access. Critical path: preallocate, don't allocate in hot loop."

---

## Key Takeaways

1. **Stack: 8MB fixed, grows down**
2. **Heap: unlimited, malloc allocates**
3. **TLB: fast translation cache (1ns hit, 50ns miss)**
4. **Page fault: 5ms to load from disk (avoid!)**
5. **mmap: zero-copy file access, but page faults**
6. **Huge pages: 2MB instead of 4KB, 512x fewer faults**
