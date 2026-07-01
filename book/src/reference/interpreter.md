# Internal Interpreter

Inscription v0.48 adds an internal deterministic interpreter for a pure subset of checked Inscription programs. It is groundwork for future `build.ins`, `comptime`, generated data, and stronger static evaluation.

The interpreter is intentionally not a stable user-facing execution mode. It does not evaluate `package.ins`, does not expose `build.ins`, and does not add `comptime` syntax.

Supported internal values include scalar integers, floats, `i1`, nominal enums, records and layout records as values, and tagged unions. Supported pure phrases may use let bindings, scalar/enum/record/union rebinding, record field assignment, `When`/`Otherwise`, counted `For`, bounded-by-fuel `While`, step `Match`, and `Give`.

Unsupported features fail deterministically instead of being partly simulated. Storage, arrays, buffers, views, owned buffers, layout read/write, extern calls, source-level I/O, file system access, networking, process spawning, heap allocation, and arbitrary user-program interpretation remain outside the v0.48 interpreter.
