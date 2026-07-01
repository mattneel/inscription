# Internal Interpreter

Inscription v0.48 added an internal deterministic interpreter for a pure subset of checked Inscription programs. v0.49 exposes that interpreter narrowly through `comptime` scalar/enum phrase-call expressions, while keeping the interpreter itself internal.

The interpreter is not a stable general execution mode. It does not evaluate `package.ins`, does not expose `build.ins`, and does not provide I/O, filesystem, network, environment, process, or extern execution.

Supported internal values include scalar integers, floats, `i1`, nominal enums, records and layout records as values, and tagged unions. Supported pure phrases may use let bindings, scalar/enum/record/union rebinding, record field assignment, `When`/`Otherwise`, counted `For`, bounded-by-fuel `While`, step `Match`, and `Give`.

The user-facing v0.49 `comptime` surface is deliberately smaller: arguments and results are limited to scalar and enum values. Unsupported features fail deterministically instead of being partly simulated. Storage, arrays, buffers, views, owned buffers, layout read/write, extern calls, source-level I/O, file system access, networking, process spawning, heap allocation, arbitrary user-program interpretation, and arbitrary package/build script evaluation remain outside the `comptime` interpreter surface. v0.60 `build.ins` is a separate restricted host-driven Build API, not general user-program interpretation.


In v0.56 the same interpreter groundwork also powers the restricted `build.ins` script surface. Build scripts are not general program interpretation: they may call only the built-in Build workflow API and cannot perform arbitrary I/O, process execution, package source imports, or host API calls.
