# Inscription

Inscription is a deterministic, phrase-shaped compiler that lowers a small prose-like language to MLIR and executes through LLVM 22.

The language is readable, but it is **not** natural-language interpretation: every accepted sentence matches the grammar exactly. The core idea is that a `To ... .` phrase definition introduces a callable phrase, and returning phrases end with an explicit `Give ... .` sentence.

## Status

This repository currently implements **Inscription v0.32**:

- source-visible scalar types: `i1`, signed integers `i8`/`i16`/`i32`/`i64`, unsigned integers `u8`/`u16`/`u32`/`u64`, and floats `f32`/`f64`
- nominal integer-backed enums declared with `Enum TypeName backed by underlying_integer_type has ... .` and cases such as `active be 1`
- nominal tagged unions declared with `Union TypeName has ... .` using payload-free variants and named single- or multi-payload variants
- transparent type aliases declared with `Type AliasName be type_expression.`, including storage aliases for buffers, arrays, and views
- byte literals such as `byte "A"` for scalar `u8` values and byte-string literals such as `bytes "hello"` for compile-time byte sequences used in `u8` storage initialization
- owned dynamic buffers such as `Let cells be owned buffer of n i32 filled with 0.` for local heap-backed mutable storage
- phrase-shaped function definitions and phrase-shaped calls
- scalar-only extern phrase declarations such as `External population count of x: i32, giving i32, as llvm.ctpop.i32.` and float externs such as `External square root of x: f64, giving f64, as llvm.sqrt.f64.`
- scalar-only exported phrase definitions such as `To add x: i32 and y: i32, giving i32, exported as ins_add.` and `To multiply x: f64 by y: f64, giving f64, exported as ins_multiply_f64.`
- deterministic artifact emission with `compile --emit mlir|lowered-mlir|llvm-ir|object|executable|static-library|interface-json|c-header`
- saved compiler intermediates with `compile/run --save-temps DIR`
- deterministic optimization presets with `--opt-level none|basic|aggressive` and `-O0`/`-O1`/`-O2`
- native executable emission with `compile --emit executable -o program`
- static archive emission with `compile --emit static-library -o libname.a`
- explicit additional object linking for executables with repeated `--link-object PATH`
- explicit additional object archiving for static libraries with repeated `--archive-object PATH`
- deterministic interface manifests with `compile --emit interface-json`
- conservative C header generation for exported scalar phrases with `compile --emit c-header`
- value blocks with `expression when condition` and `otherwise expression`
- match expressions such as `match value:` with semicolon-separated `pattern gives expression` arms and required `otherwise gives expression`, including union variant payload binding
- match step blocks such as `Match value:` with semicolon-separated `pattern:` step arms and required `otherwise:`, including union variant payload binding
- explicit returns: returning phrase bodies end with `Give expression.`
- local scalar bindings with `Let name be expression.` and `Let name: type be expression.`
- scalar rebinding with `name becomes expression`
- source-level value records declared with `Record TypeName has ... .` and scalar or enum fields
- layout-aware value records declared with `Layout record TypeName has ... .` or `Packed layout record TypeName has ... .`, including enum fields encoded as their underlying integer
- optional source modules with `Module name.` and imports with `Import name.`
- qualified calls to imported phrases, such as `math.add 1 and 2`, lowered to stable module-qualified MLIR symbols
- top-level typed compile-time constants with `Constant name: type be expression.`, including enum constants, byte literals, and `length of bytes "..."`
- compile-time assertions with `Check expression.` at top level or inside phrase bodies
- runtime requirements with `Require expression.` inside phrase bodies
- local fixed-size stack buffers with `Let name be buffer of LENGTH TYPE filled with expression.` or `Let name be buffer of LENGTH TYPE containing a, b, c.`, where `LENGTH` may be a literal, constant name, or parenthesized compile-time expression, and `TYPE` may be numeric or enum
- local owned dynamic buffers with `Let name be owned buffer of length_expression TYPE filled with expression.`, lexical-scope automatic deallocation, and numeric or enum elements
- inferred byte buffers such as `Let text be buffer of bytes "hello".`, plus `bytes "..."` splices in explicit `u8` buffer `containing` initializers
- storage alias construction such as `Let cells be CellBuffer containing 1, 2, 3, 4.` when `CellBuffer` aliases a fixed-size buffer
- immutable fixed-size local arrays with `Let name be array of LENGTH TYPE containing a, b, c.` or `filled with expression`, with numeric or enum elements
- inferred byte arrays such as `Let text be array of bytes "hello".`, plus `bytes "..."` splices in explicit `u8` array `containing` initializers
- array alias construction such as `Let numbers be Scores filled with 0.` when `Scores` aliases a fixed-size array
- buffer parameter holes with `name: buffer of LENGTH TYPE`
- buffer/view/array/owned-buffer loads with `name at index`, plus mutable buffer/view/owned-buffer stores with `name at index becomes expression`
- borrowed non-owning views over buffers, owned buffers, arrays, or other views with `Let name be view of source from start for count.`
- view parameter holes with `name: view of TYPE`, where `TYPE` may be numeric or enum
- buffer/view/array/owned-buffer length expressions with `length of name`
- optional checked storage mode with `--runtime-checks` for dynamic owned-buffer lengths, owned-buffer indices, array/view/buffer bounds, and layout bounds
- local record values with constructors such as `Point with x be 1 and y be 2`
- record field reads and rebindings with `p.x` and `p.x becomes expression`
- compile-time layout introspection with `size of TypeName`, `alignment of TypeName`, and `offset of field in TypeName`
- explicit layout serialization with `read TypeName from bytes at index` for `u8` buffers/owned buffers/views/arrays and `write value into bytes at index` for writable `u8` buffers/owned buffers/views
- record parameters passed by value and flattened into scalar MLIR operands
- record return values from returning phrases, flattened into scalar MLIR results
- side-effect-only `To ... .` phrases used as standalone steps
- counted `For name from start up to end: ... .` loops, with optional positive literal `by step`
- buffer/view/array/owned-buffer index loops with `For each index name of storage: ... .`
- `While condition: ... .` step blocks lowered as loop-carried SSA values through `scf.while`
- nested `While` loops
- step-level `When condition: ... .` / `Otherwise: ... .` sentence pairs lowered through `scf.if` SSA results
- integer arithmetic: `plus`, `minus`, `times`, `divided by`, and `remainder`
- floating arithmetic: `plus`, `minus`, `times`, and `divided by` for matching `f32` or matching `f64` operands
- ordered floating comparisons returning `i1`
- explicit casts between integers and floats, and between `f32` and `f64`, with no implicit numeric promotion
- bitwise integer operators: `bitwise and`, `bitwise or`, `bitwise xor`, and `bitwise not`
- integer shifts: `shifted left by` and `shifted right by`
- explicit integer, floating, and enum/integer casts with postfix `as type`
- boolean literals: `true` and `false`
- boolean operators: `and`, `or`, and `not`
- comparison expressions that evaluate to `i1`, including enum equality for matching enum types
- match branching over `i1`, integer scalars, enum values, and tagged unions using boolean, integer, byte-literal, enum-case, constant, and union-variant patterns
- parenthesized expressions
- deterministic parsing and semantic checks
- exact MLIR golden conformance tests in [`tests/goldens`](tests/goldens)
- MLIR emission using `func`, `arith`, `scf.if`, `scf.for`, `scf.while`, flattened scalar SSA and flattened scalar function results for records, local `memref.alloca`/`memref.load`/`memref.store` for fixed buffers and arrays, `memref.alloc`/`memref.dealloc` for owned dynamic buffers, private `func.func` declarations for scalar extern phrases, public stable-symbol definitions for exported phrases, and `cf.assert` when runtime assertions are emitted
- tooling output for frontend source MLIR, optimized source MLIR, lowered MLIR, LLVM IR, optional single-object output through LLVM 22 `llc`, native executable output through LLVM 22 `clang`, deterministic static archives through LLVM 22 `llvm-ar`, deterministic interface JSON, and conservative C headers
- LLVM 22 lowering and execution through `mlir-opt`, `mlir-translate`, and `lli`
- no source-level I/O, owned buffer parameters, owned buffer copying/rebinding, resizing, manual deallocation syntax, pointers, array parameters or returns, enum extern/export ABI, enum C header generation, recursive unions, recursive type aliases, parameterized aliases, alias-created nominal identity, C typedef emission, union constants, union buffers/arrays/views, union record fields, extern/export union ABI, C header union generation, match guards, range patterns, wildcard patterns, fallthrough, buffer/view return values, buffer/view/array aliasing beyond conservative same-root rejection, slices, C ABI structs, C ABI annotations, arbitrary pass pipelines, LLVM `opt`, LTO, linker flags beyond explicit `--link-object`/`--archive-object`, extern/exported buffer/view/record/owned-buffer parameters, extern/exported record or owned-buffer returns, executable packaging beyond one output file, shared libraries, record/layout C structs, header installation, heap strings, dynamic strings, source-level `String` type, string parameters or returns, string concatenation or interpolation, null-termination by default, statement-level `return`, `break`, `continue`, macros, import aliases, wildcard imports, generics, global storage, exceptions, result/error values, string constants, byte-array constants, source-level runtime assertion messages, overloading, type coercions, or natural-language inference

See [`docs/inscription-v0.32-spec.md`](docs/inscription-v0.32-spec.md) and [`grammar/inscription-v0.32.ebnf`](grammar/inscription-v0.32.ebnf) for the exact current language and tooling contract. The immutable previous contracts remain in [`docs/`](docs) and [`grammar/`](grammar), including the v0.19 interface metadata contract.

## Requirements

- Python 3.11+
- Pygments for the `highlight` command; installed automatically from `pyproject.toml`
- LLVM/MLIR 22 tools:
  - `mlir-opt`
  - `mlir-translate`
  - `lli`

Tool discovery is intentionally strict. The CLI uses `MLIR_TOOLCHAIN` when set; otherwise it checks `/usr/lib/llvm-22/bin`. Required tools `mlir-opt`, `mlir-translate`, and `lli` must report LLVM/MLIR `22.x`; optional object emission additionally requires LLVM 22 `llc`, optional executable emission requires LLVM 22 `llc` plus `clang`, and optional static-library emission requires LLVM 22 `llc` plus `llvm-ar`.

```sh
export MLIR_TOOLCHAIN=/usr/lib/llvm-22/bin
PYTHONPATH=src python -m inscription check-tools --show-pipeline
```

The deterministic optimization presets reported by `check-tools --show-pipeline` are:

```text
none: <none>
basic: canonicalize, cse
aggressive: canonicalize, cse, sccp, canonicalize, cse, control-flow-sink, loop-invariant-code-motion, canonicalize, cse
```

The default optimization level is `none`. Optimizations run on source MLIR before the lowering pipeline. The lowering pipeline is:

```sh
mlir-opt input.mlir \
  --convert-scf-to-cf \
  --convert-cf-to-llvm \
  --convert-arith-to-llvm \
  --expand-strided-metadata \
  --finalize-memref-to-llvm \
  --convert-func-to-llvm \
  --reconcile-unrealized-casts \
  -o lowered.mlir
mlir-translate --mlir-to-llvmir lowered.mlir -o output.ll
lli output.ll
```

Native executable emission extends the object stage with clang linking:

```sh
llc -relocation-model=pic -filetype=obj output.ll -o output.o
clang output.o -o executable
```

Static library emission reuses the object stage and archives the generated object deterministically:

```sh
llc -relocation-model=pic -filetype=obj output.ll -o output.o
llvm-ar rcsD libinscription.a output.o
```

Additional explicit objects may be passed with repeated `--link-object PATH` for executable extern definitions. Static archive emission uses `llvm-ar rcsD` and may include repeated `--archive-object PATH` inputs after the generated object. No linker flags, library search paths, target triples, clang optimization flags, system `ar`, or separate `ranlib` invocation are added by Inscription.

## Quick start

Run directly from a checkout:

```sh
PYTHONPATH=src python -m inscription check-tools --show-pipeline
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/for_each_fill.ins --verify
PYTHONPATH=src python -m inscription run tests/fixtures/positive/for_each_fill.ins
```

Or install an editable copy:

```sh
python -m pip install -e .
inscription check-tools --show-pipeline
inscription compile tests/fixtures/positive/for_each_fill.ins --verify
inscription highlight tests/fixtures/positive/for_each_fill.ins
inscription run tests/fixtures/positive/for_each_fill.ins
```

`compile` accepts library-style source files without `main`, including record-returning library phrases. `run` executes the lowered module through `lli`; executable fixtures define a no-hole `main` that returns an integer scalar exit status in `0..255`.

## Example program

```text
To fill buffer cells: buffer of 4 i32 with value: i32.
For each index i of cells: cells at i becomes value.

To sum buffer cells: buffer of 4 i32, giving i32.
Let total be 0.
For each index i of cells: total becomes total plus cells at i.
Give total.

To main, giving i32.
Let cells be buffer of 4 i32 filled with 0.
fill buffer cells with 7.
Give sum buffer cells.
```

Compile it to MLIR:

```sh
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/for_each_fill.ins --verify
```

Run it:

```sh
PYTHONPATH=src python -m inscription run tests/fixtures/positive/for_each_fill.ins
echo $?
# 24
```

## CLI

```sh
python -m inscription compile SOURCE [-o OUTPUT] [--emit mlir|lowered-mlir|llvm-ir|object|executable|static-library|interface-json|c-header] [--link-object PATH ...] [--archive-object PATH ...] [--opt-level none|basic|aggressive] [-O0|-O1|-O2] [--save-temps DIR] [--verify] [--module-root ROOT] [--runtime-checks]
python -m inscription highlight SOURCE [-o OUTPUT] [--format terminal|html] [--style STYLE] [--full]
python -m inscription run SOURCE [--module-root ROOT] [--runtime-checks] [--save-temps DIR] [--opt-level none|basic|aggressive] [-O0|-O1|-O2]
python -m inscription check-tools [--show-pipeline] [--require-object] [--require-executable] [--require-static-library]
```

Commands return `2` for compiler, diagnostic, toolchain, or filesystem errors. Imports resolve relative to the root source file directory by default; pass `--module-root ROOT` to resolve module paths from another directory.

`compile --emit mlir` emits the frontend source MLIR and is the default exact-golden artifact. `--emit mlir` remains raw frontend output even with `-O1` or `-O2`. `--emit lowered-mlir` emits MLIR after the configured lowering pipeline. `--emit llvm-ir` emits LLVM IR from `mlir-translate`. `--emit object -o file.o` emits a single native object with LLVM 22 `llc`; it does not link or resolve extern symbols. `--emit executable -o program` emits an object and links it with LLVM 22 `clang`; it requires a root no-hole integer-scalar `main` and does not run the executable. `--emit static-library -o libname.a` emits a deterministic native static archive with LLVM 22 `llvm-ar`; it does not require `main`, does not invoke `clang`, and does not resolve extern symbols. When a compilation contains exported phrases, the root executable `main` entry point is omitted from the archive object so generated C callers can provide their own `main`; normal helper phrases remain available according to existing symbol emission. `--emit interface-json` emits deterministic host-integration metadata for loaded modules, type aliases, constants, enums, unions, records, layout records, exported phrases, and extern phrases. `--emit c-header` emits a deterministic C header for exported scalar phrases only; v0.32 C headers support `i32`, `u32`, `i64`, `u64`, `f32`, and `f64`, reject dotted/non-C exported symbols, and do not include extern declarations. Repeated `--link-object PATH` arguments pass explicit additional objects to clang after the generated object. Repeated `--archive-object PATH` arguments add explicit additional objects to a static archive after the generated object and are valid only with `--emit static-library`. `--opt-level none|basic|aggressive` chooses deterministic MLIR optimization passes before lowering; `-O0`, `-O1`, and `-O2` are aliases for `none`, `basic`, and `aggressive`. Optimization affects lowered MLIR, LLVM IR, object emission, executable emission, static-library emission, and `run`, but not source MLIR, interface JSON, or C header output. `--save-temps DIR` writes deterministic `<stem>.mlir`, `<stem>.lowered.mlir`, `<stem>.ll`, and, for object/executable/static-library emission, `<stem>.o` intermediates; with `basic` or `aggressive` it also writes `<stem>.optimized.mlir`. Interface JSON and C header modes do not create temps unless `--verify` requests the MLIR verification pipeline. `run --save-temps DIR` saves the stages used before execution through `lli`, which remains the default run backend.

`highlight` uses Pygments with a built-in Inscription lexer. The default output is ANSI-colored terminal text. Use `--format html --full -o file.html` to emit a complete HTML document.

## Language summary

A program is an optional module declaration followed by imports, top-level constants, compile-time checks, record declarations, layout-record declarations, enum declarations, union declarations, type alias declarations, extern phrase declarations, exported phrase definitions, and phrase definitions. v0.32 source is sentence-oriented: periods terminate declarations and body sentences, colons introduce clause lists, semicolons separate sibling clauses, and indentation has no semantic meaning:

```text
Module Module.Name.
Import Other.Module.

Constant name: type be expression.
Check expression.

Enum Mode backed by u8 has idle be 0; active be 1.

Union MaybeI32 has none; some value: i32.

Type Count be i32.
Type CellView be view of Count.

External phrase hole: i32, giving i32, as external.symbol.
External side effect code: i32, as host_notify.

To add x: i32 and y: i32, giving i32, exported as ins_add.
Give x plus y.

Record TypeName has field: type.

To phrase with typed holes: type, giving type.
Give expression.

To side effect phrase with typed holes: type.
Require expression.
```


Modules let one source file use phrases from another without adding unqualified names to the caller. Imported declarations are qualified only:

```text
Import Math.

To main, giving i32.
Give Math.add 2 and 3.
```

Module `Math` is resolved as `Math.ins` under the module root and must declare `Module Math.`. Nested modules such as `geometry.points` resolve as `geometry/points.ins`. Imported phrase definitions emit stable symbols such as `@math__add` and `@geometry__points__sum`. Existing unmoduled single-file programs keep their previous MLIR output.

Extern phrase declarations expose scalar-only calls to external MLIR/LLVM symbols without adding bodies or ABI annotations:

```text
External population count of x: i32, giving i32, as llvm.ctpop.i32.
External host notify code: i32, as host_notify.

To main, giving i32.
Give population count of 15.
```

Extern phrases use ordinary phrase-call syntax. Returning externs are expressions, does externs are standalone steps, and imported extern phrases must be qualified like imported normal phrases. The compiler emits private `func.func` declarations for external symbols and does not check whether the host symbol exists at compile time. v0.14 externs are scalar-only: no buffer, view, or record extern parameters and no record extern returns are supported. Inscription does not add C ABI guarantees, linker flags, library names, pointer types, or source string literals for externs.

Exported phrase definitions are the mirror image: they define Inscription bodies with stable public MLIR symbols for host or other LLVM IR callers:

```text
To add left: i32 and right: i32, giving i32, exported as ins_add.
Give left plus right.

To main, giving i32.
Give add 40 and 2.
```

The source call still uses the phrase-shaped name (`add 40 and 2`), while MLIR defines and calls `@ins_add`. Imported exported phrases are still source-qualified by module name. v0.15 exports are scalar-only at the ABI boundary, but their bodies may use local records, buffers, views, `Require` steps, helper phrases, and extern calls. Inscription does not yet provide general linker flags, executable packaging beyond one output file, headers, pointer parameters, buffer/view ABI, or record ABI lowering.

A scalar type is one of `i1`, integer types `i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, `u64`, or float types `f32` and `f64`. An enum type is a nominal top-level integer-backed type with named cases. A union type is a nominal top-level tagged union with payload-free, single-payload, or multi-payload variants. A record type is a nominal top-level name declared with scalar or enum fields. A buffer parameter type is written `buffer of LENGTH TYPE`, where `TYPE` is a numeric scalar type other than `i1` or an enum type, and `LENGTH` is a compile-time integer length. A borrowed view parameter type is written `view of TYPE`, where `TYPE` is a numeric scalar type other than `i1` or an enum type. Owned dynamic buffers are local storage bindings, not source type expressions or phrase parameter types. `i1` is boolean only; integer and float scalar types are numeric types. Signedness is source-semantic: MLIR integers are signless, but Inscription signedness selects division, remainder, ordered comparison, right-shift, widening cast, and dynamic buffer-index conversion operations. A scalar typed hole is written `name: type`; a buffer typed hole is written `name: buffer of LENGTH type`; a view typed hole is written `name: view of type`. The call site mirrors the definition by filling the holes:

```text
To square of n: i32, giving i32.
Give n times n.

To main, giving i32.
Give square of 12.
```

Type aliases are transparent source-level names for existing types:

```text
Type Count be i32.
Type Byte be u8.
Type Scores be array of 4 Count.
Type CellView be view of Count.
```

Aliases can target primitive scalars, enums, records, layout records, unions, fixed-size buffers, fixed-size arrays, and borrowed views. They do not create new nominal identity: `Count` is exactly `i32`, and an alias to `Mode` is exactly the original enum type. Aliases work across modules through qualification, such as `Types.Count`, and mutually recursive aliases are rejected. Storage aliases can be constructed directly when they resolve to a buffer or array:

```text
Type CellBuffer be buffer of 4 i32.
Type CellArray be array of 4 i32.

To main, giving i32.
Let cells be CellBuffer containing 1, 2, 3, 4.
Let numbers be CellArray filled with 2.
Give cells at 0 plus numbers at 1.
```

View aliases are accepted in phrase parameter type positions but cannot be constructed with `filled with` or `containing`. Export and extern restrictions are applied after alias resolution, and generated C headers use resolved primitive scalar types without emitting C `typedef`s.

Enums are nominal integer-backed values with explicit cases:

```text
Enum Mode backed by u8 has idle be 0; active be 1.

To choose mode mode: Mode, giving i32.
Give 7 when mode is equal to Mode.active; otherwise 3.
```

Cases are referenced as `Mode.active` or, for imports, `Protocol.Mode.active`. Enum equality works directly for matching enum types. Enum arithmetic and ordered comparisons are not supported directly; cast to the underlying integer first, for example `mode as u8 is greater than 0`. Enums can appear in constants, phrase parameters/returns, value records, buffers, arrays, views, layout records, and match scrutinees/patterns. Extern/export enum ABI and C header enum generation are not supported in v0.32.

Unions are nominal tagged value types with deterministic declaration-order tags and flattened payload slots:

```text
Union MaybeI32 has none; some value: i32.

To value or zero maybe: MaybeI32, giving i32.
Give match maybe:
MaybeI32.some with value gives value;
MaybeI32.none gives 0;
otherwise gives 0.
```

Constructors are written `MaybeI32.none` for payload-free variants and `MaybeI32.some with value be 42` for single-payload variants and `Token.operator with symbol be 43 and precedence be 10` for multi-payload variants. Imported constructors are qualified, for example `Maybe.MaybeI32.some with value be 7`. Union values can be local bindings, normal phrase parameters, normal phrase returns, guarded value results, match expression results, and whole-value rebinding targets. Payloads are accessed only by binding them in match arms. Patterns bind fields by declared name, as in `Token.operator with symbol and precedence`, or by arm-local aliases, as in `Token.operator with symbol as op and precedence as prec`. Union payloads may be primitive scalars, enums, value records, or layout records; union payloads, buffers, arrays, and views are not supported. Multi-payload fields are written in declaration order, and constructors must use the same order. Unions are not allowed in constants, records, buffers, arrays, owned buffers, views, layout records, extern/export ABI, or C headers in v0.32.

Match expressions provide deterministic multi-way value branching over booleans, integer scalars, enums, and unions:

```text
To code for mode mode: Mode, giving i32.
Give match mode:
Mode.idle gives 0;
Mode.active gives 7;
otherwise gives 1.
```

Match step blocks execute steps and carry outer scalar/record field assignments through nested `scf.if` lowering:

```text
Match mode:
Mode.active: active becomes active plus 1;
otherwise: active becomes active.
```

Patterns are compile-time constants or union variants: enum cases, integer literals/constants, boolean literals/constants, payload-free union variants, and union variants such as `MaybeI32.some with value` or `Token.operator with symbol as op and precedence as prec`. `otherwise` is required and final in v0.32. Union payload bindings are scoped to their arm. There is no fallthrough, wildcard `_`, ranges, OR patterns, guards, destructuring outside union payload binding, or float/record/buffer/view/array matching.

Records are source-level value aggregates with scalar or enum fields. `Record ... has ... .` declarations remain value-only and have no byte layout; the compiler flattens record fields into scalar SSA values and function operands:

```text
Record Point has x: i32; y: i32.

To sum point p: Point, giving i32.
Give p.x plus p.y.

To main, giving i32.
Let p be Point with x be 10 and y be 20.
Give sum point p.
```

Layout records add deterministic Inscription-defined byte metadata while still behaving like value records in normal expression and call contexts:

```text
Layout record Header has tag: u8; length: u16; flags: u8.

Packed layout record Word has value: u16.

To main, giving i32.
Let bytes be buffer of 6 u8 filled with 0.
Let header be Header with tag be 7 and length be 9 and flags be 3.
Write header into bytes at 0.
Let copy be read Header from bytes at 0.
Give size of Header plus offset of flags in Header plus copy.tag as i32.
```

Natural `Layout record` declarations use scalar byte widths and alignments, including enum underlying integer widths, deterministic padding, and final size rounding. `Packed layout record` declarations use consecutive byte offsets, size equal to the sum of field widths, and alignment 1. `size of TypeName`, `alignment of TypeName`, and `offset of field in TypeName` are compile-time `i32` constants. `read TypeName from bytes at index` operates on `u8` buffers, `view of u8`, or `u8` arrays. `write value into bytes at index` operates only on writable `u8` buffers or writable `view of u8`. Layout serialization uses little-endian multi-byte fields and writes padding bytes as zero. Dynamic layout read/write indices are unchecked by default; `--runtime-checks` emits runtime assertions for dynamic layout bounds.

Body sentences may introduce scalar or record `Let` bindings, local buffers, nested-scope owned buffers, immutable local arrays, local views, compile-time `Check` steps, runtime `Require` steps, scalar/record/field rebindings, mutable buffer/view/owned-buffer stores, does phrase calls, counted for loops, buffer/view/array/owned-buffer index loops, while loops, or step-level `When`/`Otherwise` sentence pairs:

```text
Let total be 0.
Require total is greater than or equal to 0.
total becomes total plus 1.
Let point be Point with x be 1 and y be 2.
point.x becomes point.x plus 1.
Let bytes be buffer of 4 u8 filled with 0.
Let numbers be array of 4 i32 containing 1, 2, 3, 4.
bytes at 0 becomes 255.
Let window be view of bytes from 1 for 2.
window at 0 becomes 7.
Write header into bytes at 0.
fill buffer bytes with 9.
For i from 0 up to 4: total becomes total plus i.
For each index i of window: window at i becomes 9.
While total is less than 10: total becomes total plus 1.
When total is greater than 10, total becomes 10.
Otherwise, total becomes total.
```

A top-level constant is introduced with `Constant name: type be expression.`. Constants are compile-time scalar values, emit inline `arith.constant` operations at use sites, and cannot be rebound or shadowed. They may be used in expressions, for-loop bounds, buffer indices, record constructors, layout checks, and buffer lengths. A compile-time assertion is written `Check expression.`; checks emit no MLIR and must not depend on runtime phrase holes, runtime lets, record fields, or buffer loads. A runtime requirement is written `Require expression.` inside a phrase body; a dynamic `require` lowers to a deterministic runtime assertion, while a statically false `require` fails compilation.

A local scalar, record, or union binding is introduced with `Let`. A scalar binding, a whole record, a whole union, or an individual record field is rebound with `becomes` sentences. Rebinding lowers to SSA values, `scf.while` loop-carried results, and `scf.if` results, not memory storage.

A local buffer binding uses fixed-size stack storage:

```text
Constant cell_count: i32 be 8.
Let bytes be buffer of 4 u8 filled with 0.
Let cells be buffer of cell_count i32 filled with zero.
Let primes be buffer of 4 i32 containing 2, 3, 5, 7.
Let header_bytes be buffer of (size of Header) u8 filled with 0.
```

Buffers are initialized with `filled with` or literal `containing` lists, read with `name at index`, and written with `name at index becomes value`.

Owned dynamic buffers use local heap-backed storage:

```text
Let cells be owned buffer of n i32 filled with 0.
Let bytes be owned buffer of count u8 filled with byte "\0".
Let weights be owned buffer of n f64 filled with 1.5.
Let modes be owned buffer of n Mode filled with Mode.idle.
```

The length expression must have type `i32`; compile-time lengths must be at least one. Owned buffers are mutable, expose `length of`, support `For each index`, can be viewed with `view of`, can be passed to `view of TYPE` parameters, and can participate in `u8` layout read/write. They lower to `memref.alloc` and `memref.dealloc`; deallocation happens at lexical-scope exit in reverse declaration order; loop-local owned buffers allocate and deallocate on each iteration, branch-local buffers deallocate before their branch yields, match-arm buffers deallocate before their arm yields, and phrase-body buffers deallocate before return. Cleanup is not guaranteed after a runtime assertion abort. Dynamic length and bounds checks are emitted only with `--runtime-checks`.

`To ..., giving owned buffer of TYPE.` phrases may return owned buffers by ending with a visible owned-buffer binding or a direct call to another owned-buffer-returning phrase:

```text
To make ones count: i32, giving owned buffer of i32.
Let cells be owned buffer of count i32 filled with 1.
Give cells.

To main, giving i32.
Let cells be make ones 7.
Give length of cells.
```

Returning an owned buffer moves ownership to the caller. The callee does not deallocate the returned buffer, but it still deallocates any other live owned buffers before returning. The caller owns the returned buffer after binding it with `Let`, and that binding is deallocated at the caller's lexical-scope exit. Owned-buffer-returning calls must be bound before indexing, viewing, or passing to view parameters, except when directly forwarded as the final value of another owned-buffer-returning phrase. Owned buffers still cannot be copied, rebound, used as phrase parameters, stored in records/unions/storage, exposed through extern/export ABI, initialized with `bytes "..."`, returned from `main` for `run`, or returned through guarded value blocks or match expressions in v0.32.

Byte-oriented literals are compile-time conveniences, not runtime strings:

```text
byte "A"              # u8 value 65
length of bytes "hi"  # i32 value 2
Let text be array of bytes "hello".
Let scratch be buffer of bytes "hello".
Let packet be array of 6 u8 containing bytes "hello", 0.
```

`byte "..."` must decode to exactly one byte. `bytes "..."` decodes to a sequence of UTF-8 bytes plus supported escapes (`\\`, `\"`, `\n`, `\r`, `\t`, `\0`, `\xNN`) and can only initialize `u8` arrays/buffers or be measured with `length of bytes`. It does not create a string object, pointer, heap allocation, or null terminator.

Immutable local arrays use the same fixed-size length and numeric element rules, but source semantics prohibit mutation:

```text
Let numbers be array of 4 i32 containing 1, 2, 3, 4.
Let zeros be array of 8 i32 filled with 0.
Let weights be array of 3 f64 containing 0.25, 0.5, 0.25.
Let modes be array of 3 Mode containing Mode.idle, Mode.active, Mode.failed.
```

Arrays are read with `numbers at i`, expose `length of numbers`, and can be iterated with `For each index`. Arrays can be borrowed with `Let window be view of numbers from start for count.` or passed to `view of TYPE` phrase parameters as read-only full views. Arrays cannot be mutated, rebound, returned, used as phrase parameters, passed to buffer parameters, or used as scalar values. `read TypeName from bytes at index` can read from `u8` arrays, but layout writes cannot target arrays.

Borrowed views are introduced with `Let window be view of source from start for count.`, read with `window at index`, and written with `window at index becomes value` when writable. `source` may be a fixed buffer, owned buffer, array, or view. `length of name` returns a fixed buffer or array's static length, an owned buffer's stored `i32` length, or a view's runtime `i32` length. Fixed buffer and array storage lowers to `memref.alloca`, owned buffers lower to `memref.alloc`/`memref.dealloc`, and views lower to a memref base plus `i32` start and length. Literal/static indices are checked at compile time when the length is known. Dynamic storage bounds remain unchecked by default for v0.11 compatibility; pass `--runtime-checks` to emit runtime assertions for dynamic owned lengths, dynamic storage indices, view creation ranges, view indices, and layout bounds. Buffers and owned buffers can be borrowed by phrase calls through view parameters; fixed buffers can also be borrowed through buffer parameters; arrays can be borrowed through view parameters only. Views cannot be returned, stored in scalar bindings, dynamically sized, heap allocated, rebound, cast, compared, or used as scalar values.


Returning phrases (`To ..., giving T.`) return scalar values, nominal record values, or nominal union values and can accept read-only buffer parameters:

```text
Record Point has x: i32; y: i32.

To make point x: i32 and y: i32, giving Point.
Give Point with x be x and y be y.

To sum buffer cells: buffer of 4 i32, giving i32.
Let total be 0.
Let i be 0.
While i is less than 4: total becomes total plus cells at i; i becomes i plus 1.
Give total.
```

Does phrases (`To ... .` without `giving`) return no value and are used as standalone steps for side effects. Buffer parameters in does phrases are writable:

```text
To fill buffer cells: buffer of 4 i32 with value: i32.
For each index i of cells: cells at i becomes value.
```

Buffer arguments are borrowed; ownership stays with the caller. A read-only buffer parameter from a returning phrase cannot be passed to an effectful does phrase. Passing the same buffer to multiple buffer holes in one call is rejected.

Counted loops iterate from an inclusive start to an exclusive end. The start and end expressions must have the same integer numeric type, and the optional `by` step must be a positive decimal integer literal. The loop index is scoped to the loop body and is read-only:

```text
To sum evens, giving i32.
Let total be 0.
For i from 0 up to 10 by 2: total becomes total plus i.
Give total.
```

`For each index i of buffer: ... .` iterates over valid indices of a fixed-size buffer using an `i32` index. Scalar rebindings inside `For` loops lower through `scf.for` loop-carried SSA values; buffer writes mutate memref-backed storage.

Conditional value blocks return the first matching line, with a required fallback:

```text
To absolute value of n: i32, giving i32.
Give zero minus n when n is less than zero; otherwise n.
```

Multiple conditional lines lower to nested `scf.if` result expressions:

```text
To clamp x: i32 between low: i32 and high: i32, giving i32.
Give low when x is less than low; high when x is greater than high; otherwise x.
```

Bindings are expression helpers and must appear before the value block:

```text
To average of left: i32 and right: i32, giving i32.
Let total be left plus right.
Give total divided by 2.
```

Narrow, wide, signed, and unsigned integer definitions are supported:

```text
To low byte of x: u32, giving u8.
Give x as u8.

To pack high: u8 and low: u8, giving u16.
Give ((high as u16) shifted left by 8) bitwise or (low as u16).
```

Comparison expressions return `i1`; boolean literals are `true` and `false`; boolean operators are strict `i1` expressions:

```text
To is zero x: i32, giving i1.
Give x is equal to 0.

To between one and ten x: i32, giving i1.
Give x is greater than or equal to 1 and x is less than or equal to 10.
```

There are no implicit casts between widths, signedness, or integer/float families. Use postfix `as type` for explicit casts. Same-width integer casts change source signedness without emitting an MLIR op; integer narrowing emits `arith.trunci`; integer widening emits `arith.extsi` or `arith.extui`. Integer-to-float casts emit `arith.sitofp` or `arith.uitofp`; float-to-integer casts emit `arith.fptosi` or `arith.fptoui`; `f32` to `f64` emits `arith.extf`; `f64` to `f32` emits `arith.truncf`. Casts between `i1` and floats are not supported.

Floating-point definitions use `f32` and `f64` and decimal literals. Unannotated floating literals default to `f64`; `zero` takes a floating type when the context expects one. Float arithmetic supports `plus`, `minus`, `times`, and `divided by` for matching float types. `remainder`, bitwise operators, shifts, buffer/view indices, layout fields, and layout serialization remain integer-only. Float comparisons use ordered MLIR predicates, so source syntax does not add NaN/inf checks, fast-math flags, or rounding-mode controls.

```text
To average of left: f64 and right: f64, giving f64.
Give (left plus right) divided by 2.0.

Record Vec2 has x: f64; y: f64.

To length squared of v: Vec2, giving f64.
Give v.x times v.x plus v.y times v.y.
```

Expressions:

```text
120
zero
true
false
name
bytes at i
length of bytes
size of Header
alignment of Header
offset of flags in Header
read Header from bytes at i
square of 12
max of 7 and 3
left plus right
left minus right
left times right
left divided by right
left remainder right
left bitwise and right
left bitwise or right
left bitwise xor right
bitwise not mask
x shifted left by amount
x shifted right by amount
x as u32
Mode.active
Mode.active as u8
not done
left and right
left or right
(a plus b) times 2
x is equal to 0
```

Comparisons:

```text
left is equal to right
left is not equal to right
left is less than right
left is less than or equal to right
left is greater than right
left is greater than or equal to right
mode is equal to Mode.active
mode is not equal to Mode.failed
```

Important v0.32 rules:

- type aliases are transparent source ergonomics and do not change nominal identity, runtime representation, MLIR lowering, or ABI behavior
- owned buffers are local heap-backed mutable storage declared with `Let name be owned buffer of length_expression TYPE filled with expression.`
- owned buffer lengths are `i32`; compile-time lengths must be at least one, and dynamic length checks are emitted with `--runtime-checks`
- owned buffers are automatically deallocated at lexical-scope exit, can be indexed, written, iterated, measured with `length of`, viewed, passed to `view of TYPE` parameters, and returned from ordinary returning phrases as `owned buffer of TYPE`
- returning an owned buffer moves ownership to the caller; returned buffers must be bound before use, and the caller deallocates them at lexical-scope exit
- owned buffers cannot be copied, rebound, used as phrase parameters, stored, exposed through extern/export ABI, initialized with `bytes "..."`, returned from `main` for `run`, or returned through guarded/match expressions in v0.32
- `byte "..."` is a compile-time `u8` scalar literal whose decoded byte length must be exactly one
- `bytes "..."` is a compile-time byte sequence, not a value; it initializes `u8` arrays/buffers, may be spliced into explicit `u8` `containing` lists, and supports `length of bytes "..."`
- byte strings decode source text as UTF-8 bytes and support only `\\`, `\"`, `\n`, `\r`, `\t`, `\0`, and `\xNN` escapes
- aliases can target primitive scalars, enums, records, layout records, unions, buffers, arrays, and views; recursive and parameterized aliases are rejected
- storage aliases that resolve to buffers or arrays can be constructed with `filled with` or `containing`; aliases to views or scalars cannot
- C headers use resolved primitive types for alias-based exported signatures and do not emit C typedefs in v0.32
- enums are nominal integer-backed types with explicit case values, equality comparisons, explicit casts to/from the underlying integer, and no implicit enum/integer conversion
- match expressions and match step blocks branch over `i1`, integer scalar, enum, and union scrutinees
- match expression arms use `pattern gives expression`; match step arms use `pattern:` followed by steps
- match `otherwise` arms are required and must be final in v0.32
- match patterns are enum cases, union variants, byte literals, integer literals/constants, or boolean literals/constants; duplicates are rejected when statically identical
- match expressions can produce scalar, enum, union, value-record, or layout-record values and lower to nested `scf.if`
- tagged unions use declaration-order `i32` tags and flattened payload slots; payloads are bound only by match arms such as `MaybeI32.some with value` or `Token.operator with symbol as op and precedence as prec`
- v0.32 does not add recursive unions, union constants, union storage elements, extern/export union ABI, C header unions, destructuring outside union payload binding, wildcard/range/or patterns, guards, fallthrough, exhaustive matches without otherwise, float matching, or record/storage matching
- enum cases use `Mode.case` or `Module.Mode.case`; imported enum cases are not visible unqualified
- enum values can be used in constants, normal phrase parameters/returns, records, buffers, arrays, views, and layout records; layout records encode enums as their underlying integer
- enum arithmetic, ordered comparisons, extern/export enum ABI, and C header enum generation are not supported in v0.32
- buffers can be literal-initialized with `containing` expression lists; the element count must exactly match the evaluated length
- arrays are immutable fixed-size local storage initialized with `containing` or `filled with`, lowered through local memrefs, and readable with `array at index`
- arrays expose `length of`, support `For each index`, can be viewed, and can be passed to `view of TYPE` parameters as read-only full views
- arrays cannot be mutated, rebound, returned, used as phrase parameters, passed to buffer parameters, or used as scalar values
- layout reads can read from `u8` arrays; layout writes cannot target arrays
- `f32` and `f64` are first-class scalar numeric types and lower to MLIR `f32`/`f64`
- floating literals are decimal only; there are no NaN, infinity, fast-math, or rounding-mode source forms
- floating arithmetic requires matching float operand types and uses `arith.addf`, `arith.subf`, `arith.mulf`, and `arith.divf`; `remainder` remains integer-only
- floating comparisons use ordered `arith.cmpf` predicates and return `i1`
- buffers, views, value records, record returns, constants, checks, requires, extern phrases, and exported phrases can use `f32`/`f64`
- layout records and layout read/write serialization remain integer-only; `main` for `run` and executable emission must still return an integer scalar
- `--opt-level none` is the default and preserves v0.16/v0.17 compile/run behavior
- `-O0`, `-O1`, and `-O2` are aliases for `none`, `basic`, and `aggressive`; conflicting optimization flags are rejected
- `compile --emit mlir` is the default and preserves exact raw source MLIR output even when optimization is requested
- optimization presets affect lowered MLIR, LLVM IR, object emission, executable emission, static-library emission, and `run` only
- `basic` runs `canonicalize, cse`; `aggressive` runs `canonicalize, cse, sccp, canonicalize, cse, control-flow-sink, loop-invariant-code-motion, canonicalize, cse`
- `compile --emit lowered-mlir` and `compile --emit llvm-ir` expose deterministic downstream textual artifacts
- `compile --emit object -o file.o` requires optional LLVM 22 `llc`, emits one object file, and does not link
- `compile --emit executable -o program` requires LLVM 22 `llc` and `clang`, links the generated object with clang, and does not run the executable
- `compile --emit static-library -o libname.a` requires LLVM 22 `llc` and `llvm-ar`, archives the generated object with `llvm-ar rcsD`, does not require `main`, omits the root executable `main` from export-bearing archives, and does not link or resolve extern symbols
- executable emission requires a root no-hole `main` returning an integer scalar
- repeated `--link-object PATH` passes explicit additional objects to clang for extern definitions
- repeated `--archive-object PATH` adds explicit additional objects to static archives after the generated object and is valid only with `--emit static-library`
- unresolved externs may compile to object but fail executable linking with `executable link failed`
- `compile --emit interface-json` requires no `main` and emits deterministic metadata without timestamps, absolute paths, usernames, hostnames, or git hashes
- interface JSON includes type aliases and extern declarations; C headers describe only exported functions provided by the Inscription compilation unit
- `compile --emit c-header` supports exported ABI types `i32`, `u32`, `i64`, `u64`, `f32`, and `f64` in v0.32 and uses generated C parameter names `arg0`, `arg1`, ...
- `compile/run --save-temps DIR` saves produced compiler intermediates under deterministic filenames, including `<stem>.optimized.mlir` for non-`none` optimization
- v0.32 does not expose arbitrary pass pipelines, LLVM `opt`, LTO, linker flags beyond `--link-object`/`--archive-object`, target triples, optimization remarks, inlining, symbol DCE by default, native runtime libraries, executable packaging beyond one output file, shared libraries, C ABI structs, buffer/view C ABI, record/layout C structs, or header installation
- function names are generated from the leading literal words in a phrase definition
- extern phrase declarations have no body and emit external `func.func private` declarations
- exported phrase definitions have bodies and emit public definitions with the symbol named after `as`
- exported phrase signatures are scalar-only at the ABI boundary in v0.15
- returning exported calls are scalar expressions; exported does calls are standalone steps
- exported phrase bodies may still use local records, buffers, views, requirements, helper phrases, and extern calls
- imported exported phrases must be source-qualified, but emitted calls target the exported symbol
- exported symbols cannot duplicate each other or conflict with extern/generated symbols such as `main`
- extern phrase parameters and return values are scalar-only in v0.14
- returning extern calls are expressions; extern does calls are standalone steps
- imported extern phrases must be qualified, and calls target the declared external symbol rather than a module-qualified generated symbol
- duplicate extern declarations for the same external symbol are allowed only when their function types match exactly
- an external symbol cannot conflict with a generated Inscription function symbol such as `main`
- phrase names are unique; there is no overloading
- library compilation does not require `main`; if `main` exists, it must take no holes
- phrase holes plus scalar and record `Let` bindings can be rebound locally with `becomes` sentences
- record declarations are nominal; field names are unique and scalar-only
- record constructors initialize fields in declaration order
- record fields are read with `p.x` and rebound with `p.x becomes expression`
- record parameters are passed by value, flattened to scalar function arguments, and callee field rebinding does not mutate the caller
- `Layout record` adds deterministic byte layout metadata without changing value-record lowering
- `Packed layout record` removes padding and has alignment 1
- layout record fields are integer scalar types only, not `i1`
- `size of TypeName`, `alignment of TypeName`, and `offset of field in TypeName` are compile-time `i32` constants
- layout read/write operations require writable `u8` buffers, owned buffers, or `view of u8`, encode multi-byte fields little-endian, and zero padding bytes on write
- ordinary value-only `Record ... has ... .` declarations cannot be used with layout introspection or layout read/write
- records can be returned by value from returning phrases and lower as flattened scalar MLIR results
- record-returning calls can initialize record lets or whole-record rebindings
- record-returning `main` is compile-only; `run` requires integer-scalar `main`
- records cannot be stored in buffers, nested, addressed, referenced, or lowered as LLVM/C ABI structs
- rebinding a phrase hole does not mutate the caller
- each scalar binding type is fixed after initialization or annotation
- typed `Let` initializers and rebinding right-hand sides must match the binding type
- fixed buffer lengths must be compile-time integer values written as decimal literals, constant names, or parenthesized compile-time expressions; owned buffer lengths are runtime `i32` expressions
- constants are top-level scalar compile-time values, cannot be shadowed, cannot be rebound, and lower inline at use sites
- checks are compile-time assertions, emit no MLIR, require `i1`, and cannot depend on runtime values
- require steps are runtime requirements inside phrase bodies, require `i1`, may depend on runtime values, and lower to `cf.assert` when dynamic
- top-level runtime requirements are invalid; use `Check` for top-level compile-time assertions
- buffer and owned-buffer element types must be integer numeric types, floats, or enums, not `i1`; owned-buffer union elements are rejected
- buffer and owned-buffer fill and store expressions must match the element type
- buffer parameter actuals must exactly match length and element type
- buffer parameters in returning phrases are read-only; buffer parameters in does phrases are writable
- duplicate buffer actuals in one phrase call are rejected
- views are borrowed, non-owning ranges over buffers or other views
- view parameters in returning phrases are read-only; view parameters in does phrases are writable
- buffers and owned buffers can be passed to `view of TYPE` parameters as full-storage views
- `length of buffer` returns the static buffer length as `i32`; `length of owned buffer` returns the stored runtime length; `length of view` returns the view length as `i32`
- buffer index expressions must be integer numeric types, not `i1`
- literal/static buffer or view indices must be in range when the length is known; dynamic storage bounds are unchecked by default and checked with `--runtime-checks`
- buffers, owned buffers, and views are lexical storage objects and cannot be used as scalar values
- views cannot be rebound, returned, stored in records or buffers, heap allocated, or used as scalar values; owned buffers cannot be rebound, copied, or used as scalar values, and owned-buffer-returning calls must be bound before use in v0.32
- phrase calls reject multiple buffer/view/owned-buffer arguments that are known to share the same root storage
- for-loop bounds must be matching integer numeric types; `up to` is exclusive
- for-loop `by` steps must be positive decimal integer literals
- for-loop index bindings are scoped to the loop body, cannot shadow visible bindings, and cannot be rebound
- scalar bindings and assigned record fields inside `For` loops lower through `scf.for` iter_args in deterministic binding/field order
- buffer writes inside `For` loops mutate memref-backed storage
- while conditions must be `i1`
- while-body lets and buffers are scoped to that loop iteration and do not escape
- nested while loops are supported
- `When`/`Otherwise` conditions must be `i1`, and both branches must contain at least one step
- branch-local lets and buffers do not escape
- scalar bindings and assigned record fields in if branches lower to `scf.if` results in deterministic binding/field order
- integer arithmetic, bitwise, and shift operands must be matching integer numeric types, never `i1`; float arithmetic supports only matching `f32` or matching `f64` operands
- source signedness controls `divided by`, `remainder`, ordered comparisons, `shifted right by`, widening casts, and dynamic index conversion
- comparisons require matching integer numeric operands or matching float operands and return `i1`
- there are no implicit casts between signed and unsigned types, widths, or integer/float families
- boolean `and`, `or`, and `not` require `i1` operands and return `i1`
- variables must be initialized by a phrase hole or prior visible `Let`
- phrase calls must match a declared phrase template exactly
- conditional value blocks require `otherwise`
- removed ceremony words such as `Function`, `End function`, `Set`, `Return`, and `call ... with` are not valid Inscription syntax
- unsupported `track`, I/O, dynamic arrays distinct from owned buffers, array parameters/returns, pointers, owned buffer parameters, ownership copies between locals, resizing, manual deallocation syntax, source-level memrefs, buffer/view returns, guarded or match-expression owned-buffer returns, extern/exported buffer/view/record/owned-buffer parameters, extern/exported record or owned-buffer returns, record buffers, nested records, and free prose are rejected

## Tests

Run the full test suite:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
```

The suite includes exact source-MLIR golden conformance files under [`tests/goldens`](tests/goldens). Each `*.ins` source must compile byte-for-byte to its sibling `*.mlir`. v0.16/v0.17/v0.18/v0.19/v0.20/v0.21/v0.22/v0.23/v0.24/v0.25/v0.26/v0.27/v0.28/v0.29/v0.30/v0.31/v0.32 artifact tests also exercise lowered MLIR, LLVM IR, object emission when `llc` is available, executable emission when `clang` is available, static-library emission when `llvm-ar` is available, saved intermediates, optimization presets, generated interface metadata/headers, and C header/archive smoke integration without making lowered or optimized tool output byte-for-byte golden-stable.

With LLVM/MLIR 22 available, verify the toolchain and fixture exit codes:

```sh
PYTHONPATH=src python -m inscription check-tools --show-pipeline
PYTHONPATH=src python -m inscription run tests/fixtures/positive/adjust.ins                # exits 3
PYTHONPATH=src python -m inscription run tests/fixtures/positive/loop_sum.ins              # exits 55
PYTHONPATH=src python -m inscription run tests/fixtures/positive/iterative_factorial.ins   # exits 120
PYTHONPATH=src python -m inscription run tests/fixtures/positive/gcd.ins                   # exits 6
PYTHONPATH=src python -m inscription run tests/fixtures/positive/collatz_steps.ins         # exits 16
PYTHONPATH=src python -m inscription run tests/fixtures/positive/nested_while_multiply.ins # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/u8_cast.ins               # exits 255
PYTHONPATH=src python -m inscription run tests/fixtures/positive/bitwise_flags.ins         # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/shifts.ins                # exits 8
PYTHONPATH=src python -m inscription run tests/fixtures/positive/unsigned_remainder.ins    # exits 5
PYTHONPATH=src python -m inscription run tests/fixtures/positive/unsigned_comparison.ins   # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/buffer_sum.ins            # exits 100
PYTHONPATH=src python -m inscription run tests/fixtures/positive/filled_buffer.ins         # exits 15
PYTHONPATH=src python -m inscription run tests/fixtures/positive/swap_endpoints.ins        # exits 16
PYTHONPATH=src python -m inscription run tests/fixtures/positive/branch_store.ins          # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/loop_writes.ins           # exits 10
PYTHONPATH=src python -m inscription run tests/fixtures/positive/sum_buffer_parameter.ins  # exits 10
PYTHONPATH=src python -m inscription run tests/fixtures/positive/fill_buffer_procedure.ins # exits 28
PYTHONPATH=src python -m inscription run tests/fixtures/positive/copy_buffer_procedure.ins # exits 12
PYTHONPATH=src python -m inscription run tests/fixtures/positive/nested_procedure_calls.ins # exits 24
PYTHONPATH=src python -m inscription run tests/fixtures/positive/u8_buffer_parameter.ins   # exits 36
PYTHONPATH=src python -m inscription run tests/fixtures/positive/counted_loop_sum.ins      # exits 45
PYTHONPATH=src python -m inscription run tests/fixtures/positive/counted_loop_step.ins     # exits 20
PYTHONPATH=src python -m inscription run tests/fixtures/positive/buffer_length.ins         # exits 4
PYTHONPATH=src python -m inscription run tests/fixtures/positive/for_each_buffer_sum.ins   # exits 10
PYTHONPATH=src python -m inscription run tests/fixtures/positive/for_each_fill.ins         # exits 24
PYTHONPATH=src python -m inscription run tests/fixtures/positive/nested_for_multiply.ins   # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/for_with_branch.ins       # exits 5
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_field_access.ins    # exits 30
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_field_rebinding.ins # exits 10
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_loop_carry.ins      # exits 15
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_branch_carry.ins    # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_copy_rebind.ins     # exits 53
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_unsigned_fields.ins # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_buffer_interop.ins  # exits 9
PYTHONPATH=src python -m inscription run tests/fixtures/positive/layout_introspection.ins         # exits 12
PYTHONPATH=src python -m inscription run tests/fixtures/positive/packed_layout_introspection.ins  # exits 8
PYTHONPATH=src python -m inscription run tests/fixtures/positive/layout_roundtrip.ins             # exits 19
PYTHONPATH=src python -m inscription run tests/fixtures/positive/layout_little_endian_write.ins   # exits 12
PYTHONPATH=src python -m inscription run tests/fixtures/positive/layout_little_endian_read.ins    # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/layout_write_procedure.ins       # exits 11
PYTHONPATH=src python -m inscription run tests/fixtures/positive/layout_padding_zero.ins          # exits 0
PYTHONPATH=src python -m inscription run tests/fixtures/positive/constants_layout_checks.ins       # exits 10
PYTHONPATH=src python -m inscription run tests/fixtures/positive/constant_buffer_length.ins        # exits 8
PYTHONPATH=src python -m inscription run tests/fixtures/positive/layout_length_expression.ins      # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/phrase_body_check.ins             # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/constant_bitwise_mask.ins         # exits 15
PYTHONPATH=src python -m inscription run tests/fixtures/positive/constant_for_bounds.ins           # exits 10
PYTHONPATH=src python -m inscription run tests/fixtures/positive/constant_layout_index.ins         # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/extern_ctpop.ins                    # exits 4
PYTHONPATH=src python -m inscription run tests/fixtures/positive/extern_in_loop.ins                  # exits 4
PYTHONPATH=src python -m inscription run tests/fixtures/positive/extern_constant_argument.ins        # exits 4
PYTHONPATH=src python -m inscription run tests/fixtures/positive/export_scalar_gives.ins             # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/export_scalar_does.ins              # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/export_calls_extern.ins             # exits 4
PYTHONPATH=src python -m inscription run tests/fixtures/positive/export_uses_record_local.ins        # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/export_uses_buffer_local.ins        # exits 20
PYTHONPATH=src python -m inscription run tests/fixtures/positive/optimization_arithmetic.ins -O2     # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/optimization_loop.ins -O2           # exits 10
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/phrase_max.ins --emit executable -o /tmp/phrase_max
/tmp/phrase_max                                                                            # exits 7
```

## Repository layout

```text
src/inscription/              compiler implementation
docs/inscription-v0-spec.md   original v0 language and toolchain specification
docs/inscription-v0.1-spec.md v0.1 language and toolchain specification
docs/inscription-v0.2-spec.md v0.2 language and toolchain specification
docs/inscription-v0.3-spec.md v0.3 language and toolchain specification
docs/inscription-v0.4-spec.md v0.4 language and toolchain specification
docs/inscription-v0.5-spec.md v0.5 language and toolchain specification
docs/inscription-v0.6-spec.md v0.6 language and toolchain specification
docs/inscription-v0.7-spec.md v0.7 language and toolchain specification
docs/inscription-v0.8-spec.md v0.8 language and toolchain specification
docs/inscription-v0.9-spec.md v0.9 language and toolchain specification
docs/inscription-v0.10-spec.md v0.10 language and toolchain specification
docs/inscription-v0.11-spec.md v0.11 language and toolchain specification
docs/inscription-v0.12-spec.md v0.12 language and toolchain specification
docs/inscription-v0.13-spec.md v0.13 language and toolchain specification
docs/inscription-v0.14-spec.md v0.14 language and toolchain specification
docs/inscription-v0.15-spec.md v0.15 language and toolchain specification
docs/inscription-v0.16-spec.md v0.16 language and toolchain specification
docs/inscription-v0.17-spec.md v0.17 language and toolchain specification
docs/inscription-v0.18-spec.md v0.18 native executable emission specification
docs/inscription-v0.19-spec.md v0.19 interface manifest and C header specification
docs/inscription-v0.20-spec.md v0.20 static-library tooling specification
docs/inscription-v0.21-spec.md v0.21 floating-point scalar specification
docs/inscription-v0.22-spec.md v0.22 fixed-size array specification
docs/inscription-v0.23-spec.md v0.23 nominal enum specification
docs/inscription-v0.24-spec.md v0.24 match specification
docs/inscription-v0.25-spec.md v0.25 tagged union specification
docs/inscription-v0.26-spec.md v0.26 multi-payload union specification
docs/inscription-v0.27-spec.md v0.27 type alias specification
docs/inscription-v0.28-spec.md v0.28 byte literal specification
docs/inscription-v0.29-spec.md v0.29 owned dynamic buffer specification
docs/inscription-v0.30-spec.md v0.30 nested-scope owned buffer specification
docs/inscription-v0.31-spec.md v0.31 owned buffer return and transfer specification
docs/inscription-v0.32-spec.md current v0.32 prose-punctuation syntax specification
grammar/inscription-v0.ebnf   original v0 grammar
grammar/inscription-v0.1.ebnf v0.1 grammar
grammar/inscription-v0.2.ebnf v0.2 grammar
grammar/inscription-v0.3.ebnf v0.3 grammar
grammar/inscription-v0.4.ebnf v0.4 grammar
grammar/inscription-v0.5.ebnf v0.5 grammar
grammar/inscription-v0.6.ebnf v0.6 grammar
grammar/inscription-v0.7.ebnf v0.7 grammar
grammar/inscription-v0.8.ebnf v0.8 grammar
grammar/inscription-v0.9.ebnf v0.9 grammar
grammar/inscription-v0.10.ebnf v0.10 grammar
grammar/inscription-v0.11.ebnf v0.11 grammar
grammar/inscription-v0.12.ebnf v0.12 grammar
grammar/inscription-v0.13.ebnf v0.13 grammar
grammar/inscription-v0.14.ebnf v0.14 grammar
grammar/inscription-v0.15.ebnf v0.15 grammar
grammar/inscription-v0.16.ebnf v0.16 grammar
grammar/inscription-v0.17.ebnf v0.17 grammar
grammar/inscription-v0.18.ebnf v0.18 grammar
grammar/inscription-v0.19.ebnf v0.19 grammar mirror
grammar/inscription-v0.20.ebnf v0.20 grammar mirror
grammar/inscription-v0.21.ebnf v0.21 grammar mirror
grammar/inscription-v0.22.ebnf v0.22 grammar mirror
grammar/inscription-v0.23.ebnf v0.23 grammar mirror
grammar/inscription-v0.24.ebnf v0.24 grammar mirror
grammar/inscription-v0.25.ebnf v0.25 grammar mirror
grammar/inscription-v0.26.ebnf v0.26 grammar mirror
grammar/inscription-v0.27.ebnf v0.27 grammar mirror
grammar/inscription-v0.28.ebnf v0.28 grammar mirror
grammar/inscription-v0.29.ebnf v0.29 grammar mirror
grammar/inscription-v0.30.ebnf v0.30 grammar mirror
grammar/inscription-v0.31.ebnf v0.31 grammar mirror
grammar/inscription-v0.32.ebnf current v0.32 grammar mirror
tests/goldens/                exact MLIR conformance goldens
tests/                        unit tests and executable fixtures
```
