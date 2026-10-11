# Debugging Tools by Layer: Choosing the Right Tool for the Question

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Too Many Tools, Which One to Use?

Every language has debuggers, profilers, sanitizers, logging frameworks, tracing tools.

**The trap:** You try all of them without a clear question.

**The solution:** Choose a tool based on the hypothesis you're testing, not by availability.

## The Layers and Their Tools

```
Layer 1: Static Analysis
  Questions: Type errors? Obvious bugs? Style?
  Tools: mypy, rustc, clippy, eslint, pylint
  Cost: Zero (no execution)
  
Layer 2: Execution & Logs
  Questions: Which code path executed? What were the values?
  Tools: Logging, print statements, stdout
  Cost: Low (one execution)
  
Layer 3: Profiling (Sampling)
  Questions: Where is time spent? Which functions are hot?
  Tools: async-profiler (Java), perf (Linux), Instruments (Mac)
  Cost: Low (background sampling, small overhead)
  
Layer 4: Debugger (Breakpoints)
  Questions: What's the value at this line? What's the stack?
  Tools: gdb, lldb, pdb (Python), jdb (Java)
  Cost: Medium (stop execution, inspect state)
  
Layer 5: Instrumentation (Tracing)
  Questions: Which services called which? In what order? Timing?
  Tools: Datadog, Jaeger, CloudTrace, strace
  Cost: Medium (high-volume logging)
  
Layer 6: Sanitizers
  Questions: Memory leak? Race condition? Undefined behavior?
  Tools: AddressSanitizer, ThreadSanitizer, UBSan
  Cost: Medium (runtime overhead, catches real bugs)
  
Layer 7: Simulation & Reproduction
  Questions: Can I reproduce locally? With what inputs?
  Tools: Chaosmonkey, jepsen, property-based testing
  Cost: High (complex, takes time)
```

## Choosing a Tool: Decision Tree

```
Q1: Is it a type error or obvious mistake?
    → YES: Use static analysis (mypy, rustc, eslint)
    → NO: Go to Q2
    
Q2: Do you know which function is involved?
    → NO: Use profiler (find hot spots first)
    → YES: Go to Q3
    
Q3: Is it a race condition, memory bug, or undefined behavior?
    → YES: Use sanitizer (TSAN, ASAN, UBSan)
    → NO: Go to Q4
    
Q4: Do you need to inspect variable values at a specific line?
    → YES: Use debugger with breakpoints
    → NO: Go to Q5
    
Q5: Is it a distributed system bug (multi-service, timing)?
    → YES: Use tracing (Datadog, Jaeger)
    → NO: Use logging / print (simplest option)
    
Q6: Can you not reproduce locally?
    → YES: Capture logs from production, replay locally if possible
    → Use simulation (Chaosmonkey, jepsen) to test distribution
```

## Language-Specific Cheat Sheet

### Python Debugging

```
Quick debugging:
  breakpoint()                    # Stop execution here (Python 3.7+)
  import pdb; pdb.set_trace()     # Older Python
  
CLI debugger (pdb):
  python -m pdb script.py         # Run with debugger
  (Pdb) l                         # List code
  (Pdb) s                         # Step into
  (Pdb) n                         # Step over
  (Pdb) c                         # Continue
  (Pdb) p variable                # Print variable
  (Pdb) pp variable               # Pretty print
  
Profiling (sync):
  import cProfile
  cProfile.run('my_function()')   # See which functions take time
  
Profiling (async):
  python -m scalene script.py     # Modern, fast profiling
  py-spy record -o out.svg -n -- python script.py
  
Memory profiling:
  pip install memory-profiler
  @profile
  def my_function():
      ...
  python -m memory_profiler script.py
  
Type checking:
  mypy script.py                  # Find type errors
  
Linting:
  pylint script.py                # Find obvious bugs
```

### C++ Debugging

```
Compilation (debug symbols):
  g++ -g -O0 -fsanitize=address,undefined,thread prog.cpp
  
GDB (debugger):
  gdb ./prog                      # Launch debugger
  (gdb) run                       # Run program
  (gdb) b main                    # Breakpoint at main
  (gdb) b filename:linenum        # Breakpoint at line
  (gdb) c                         # Continue
  (gdb) n                         # Step over
  (gdb) s                         # Step into
  (gdb) p variable                # Print variable
  (gdb) bt                        # Backtrace (stack)
  (gdb) quit
  
LLDB (Clang debugger):
  Similar to GDB but on macOS/iOS
  lldb ./prog
  (lldb) run
  (lldb) breakpoint set -n main
  
Profiling (CPU):
  perf record ./prog              # Record execution
  perf report                     # Show results
  
Profiling (memory):
  valgrind --leak-check=full ./prog  # Detect memory leaks
  
Sanitizers:
  g++ -fsanitize=address program.cpp -o program
  g++ -fsanitize=thread program.cpp -o program
  g++ -fsanitize=undefined program.cpp -o program
```

### Java/JVM Debugging

```
Remote debugging:
  java -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=5005 MyApp
  jdb -attach localhost:5005     # Connect debugger
  
Console logging:
  System.out.println("Debug: " + variable);
  
Profiling (sampling):
  java -XX:+UnlockDiagnosticVMOptions -XX:+DebugNonSafepoints \
       -XX:+TraceClassLoading MyApp
  
Async-profiler (best):
  ./profiler.sh -d 30 -f flamegraph.html jps
  # Generates flamegraph of 30 sec execution
  
GC analysis:
  jstat -gc PID 1000              # GC stats every 1 sec
  jstat -gccause PID              # Why is GC running?
  jconsole PID                    # Visual GC stats
  
Thread analysis:
  jconsole PID                    # Visual thread state
  jstack PID > threads.txt        # Thread dump to file
  
Heap analysis:
  jmap -heap PID                  # Show heap info
  jmap -histo:live PID            # Object histogram
  
Thread sanitizer:
  JDK 17+: -XX:+EnableThreadSMR  # Simplified thread management
```

### Rust Debugging

```
Debug symbols:
  [profile.dev]
  debug = true
  
GDB / LLDB:
  cargo build
  gdb ./target/debug/program
  (gdb) run
  
Profiling:
  cargo install flamegraph
  cargo flamegraph --bin program  # Generate flamegraph
  
Memory safety:
  cargo test --lib               # Tests catch many bugs
  cargo clippy                   # Linting (find obvious issues)
  
Panic backtrace:
  RUST_BACKTRACE=1 cargo run
  
Miri (UB detection):
  rustup +nightly component add miri
  cargo +nightly miri test
```

## When to Use Which Tool: Examples

**Symptom 1: Function is slow (takes 10 sec instead of 1 sec)**
  → Use profiler (async-profiler, perf, Instruments)
  → Find which function is hot
  → Fix that function

**Symptom 2: Application crashes with segfault**
  → Use ASAN (AddressSanitizer)
  → Use GDB + backtrace
  → Find which line accesses invalid memory

**Symptom 3: Multi-threaded program hangs**
  → Use TSAN (ThreadSanitizer)
  → Use jstack (Java) or GDB backtrace
  → Find which thread is deadlocked

**Symptom 4: Memory usage grows over time (memory leak)**
  → Use ASAN (Clang)
  → Use valgrind (C/C++)
  → Use jmap (Java)
  → Find which allocation is not freed

**Symptom 5: Distributed system timeout (A calls B calls C, timeout)**
  → Use distributed tracing (Jaeger, Datadog)
  → See which service is slow
  → Then use Layer 4 tools on that service

## Interview: Tools and Diagnosis

**Q: "Your application crashes randomly. How would you debug?"**

Weak:
```
"I'd add logging? Or try a debugger? Hope to catch it?"
```

Strong:
```
"Depends on the crash type:

1. If it's a crash (segfault, assertion):
   - Compile with ASAN + UBSAN (AddressSanitizer, UBSanitizer)
   - Run again, ASAN will tell me exactly where
   
2. If it's a hang (process stops):
   - Use TSAN (ThreadSanitizer) to catch race condition
   - Or use GDB to attach and get backtrace
   
3. If it's random (intermittent):
   - Capture coredump (ulimit -c unlimited)
   - Analyze coredump with GDB: gdb ./prog coredump
   - See stack trace of where it crashed
   
4. If I can reproduce locally:
   - Use debugger with breakpoints
   - Narrow down which line
   
5. If only happens in production:
   - Capture logs + coredump
   - Replay in staging environment if possible
   - Use sanitizers in staging (even if not in prod)
"
```

## Checklist

- [ ] Question clearly stated ("Where is time spent?" vs. "Why is it slow?")
- [ ] Appropriate tool chosen (profiler for 'where', debugger for 'what value')
- [ ] Tool knows where to look (function name, file)
- [ ] Hypothesis before running (what do you expect to see?)
- [ ] Evidence captured (output saved, not lost)

## Common Mistakes

1. **Profiler by default.** "Everything is slow, profile it." Profiler is good for 'where', not 'why'.
2. **Not compiling for debugging.** Compiled with -O3 (optimized), can't use debugger (code is reordered, variables optimized away).
3. **Debugger on production.** Can't use GDB with breakpoints on running production service.
4. **Not thinking about tool cost.** Sanitizers add 10x slowdown; not suitable for production, use in staging.
5. **Choosing tool by familiarity.** "I know GDB so I'll use that" instead of "This hypothesis needs a profiler."

