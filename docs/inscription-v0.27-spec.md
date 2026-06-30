# Inscription v0.27 type alias specification

Inscription v0.27 keeps the v0.26 language and tooling surface and adds transparent type aliases plus ergonomic local construction through aliases to fixed-size buffers and arrays.

Aliases are a source-level convenience only. They do not create new nominal identity, do not change runtime representation, do not change MLIR lowering, and do not change extern/export ABI behavior. After semantic resolution, `type Count be i32` is exactly `i32`, and `type OptionalPoint be MaybePoint` is exactly the original `MaybePoint` union type.

## Alias declarations

```text
type Count be i32
type Byte be u8
type Position be Point
type OptionalPosition be MaybePoint
type CellBuffer be buffer of 4 i32
type Scores be array of 4 i32
type CellView be view of i32
type HeaderBytes be buffer of (size of Header) Byte
```

Rules:

- Type aliases are top-level items and may appear in root files or imported modules.
- Alias names share the type namespace with scalar type names, records, layout records, packed layout records, enums, unions, and other aliases.
- Alias names must not collide with constants.
- Alias names are case-sensitive.
- Alias targets may be primitive scalars, enums, records, layout records, packed layout records, unions, buffers, arrays, or views.
- Buffer, array, and view alias element types follow the existing storage element rules: integer numeric types, `f32`, `f64`, and enums are supported; `i1`, records, views, arrays, buffers, and unions remain unsupported.
- Alias declarations may refer to aliases declared before or after them in the same module.
- Alias declarations may refer to imported aliases by module qualification.
- Direct or indirect alias cycles are rejected deterministically.

Examples of rejected cycles:

```text
type A be A

type A be B
type B be C
type C be A
```

## Alias use in type positions

Aliases may be used wherever their resolved target type is valid:

```text
type Count be i32

total left: Count and right: Count gives Count:
  left plus right
```

```text
type Byte be u8

enum Mode: Byte:
  idle be 0
  active be 1

packed layout record Header:
  mode: Mode
  length: u16
```

Alias resolution is transparent. Two aliases to `i32` are compatible with each other and with direct `i32`; an alias to an enum is still that exact enum, not a new enum. Ordinary context rules still apply after resolution, so an alias to a union is still rejected as a record field, and an alias to an array is still rejected as a phrase parameter.

## Storage alias construction

Aliases that resolve to fixed-size buffers or arrays can be used in local storage bindings:

```text
type CellBuffer be buffer of 4 i32
type CellArray be array of 4 i32

main gives i32:
  let cells be CellBuffer containing 1, 2, 3, 4
  let numbers be CellArray filled with 2
  cells at 0 plus numbers at 1
```

Rules:

- `filled with` and `containing` use the resolved buffer or array length and element type.
- `containing` must provide exactly the resolved length.
- Element expressions are checked with the resolved element type as their expected type.
- A buffer alias binding is mutable storage.
- An array alias binding is immutable storage.
- Aliases to views, scalars, records, enums, unions, or layout records cannot be constructed with `filled with` or `containing`.

View aliases remain useful in phrase parameter positions:

```text
type CellView be view of i32

sum cells cells: CellView gives i32:
  let total be 0
  for each index i of cells:
    total becomes total plus cells at i
  total
```

Buffers, arrays, and views may be passed to a view-alias parameter under the same read-only/writable and aliasing rules as explicit `view of TYPE` parameters.

## Modules

Aliases declared in modules are visible through qualification only:

```text
module Types

type Count be i32
type CellView be view of Count
```

```text
import Types

sum cells cells: Types.CellView gives Types.Count:
  let total: Types.Count be 0
  for each index i of cells:
    total becomes total plus cells at i
  total
```

`Types.Count` resolves to `i32`. If two modules define aliases to the same primitive type, the resulting types are compatible. If they alias different nominal records, enums, or unions with similar spelling, nominal identity remains the identity of the underlying nominal declaration.

## Externs, exports, and C headers

Extern and export restrictions are applied after alias resolution:

```text
type Count be i32

export add counts left: Count and right: Count gives Count as ins_add_counts:
  left plus right
```

The generated C header uses the resolved primitive type:

```c
int32_t ins_add_counts(int32_t arg0, int32_t arg1);
```

v0.27 does not emit C `typedef`s. Aliases to enums, records, unions, buffers, arrays, or views remain rejected at extern/export ABI boundaries according to the existing primitive-scalar ABI rules.

## Interface JSON

Interface JSON includes aliases under each module's `type_aliases` list:

```json
{
  "name": "Count",
  "kind": "type-alias",
  "target": "i32"
}
```

Storage aliases use deterministic resolved target display:

```json
{
  "name": "CellBuffer",
  "kind": "type-alias",
  "target": "buffer of 4 i32"
}
```

Aliases are emitted in source declaration order. Interface format remains `inscription-interface-v1`.

## Still not supported

v0.27 does not add generic aliases, parameterized aliases, value aliases, expression aliases, macros, recursive aliases, alias-created nominal identity, C typedef emission, alias re-exports, overloading, implicit casts, formatter changes, block syntax changes, or custom MLIR dialects.
