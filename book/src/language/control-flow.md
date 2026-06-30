# Control Flow

Step-level conditionals use adjacent `When` and `Otherwise` sentences. Both branches are required.

```inscription,check
To choose flag flag: i1, giving i32.
Let value be 0.
When flag, value becomes 7.
Otherwise, value becomes 3.
Give value.

To main, giving i32.
Give choose flag true.
```

Loops use punctuation clause lists:

```inscription,check
To sum through n: i32, giving i32.
Let total be 0.
For i from 0 up to n: total becomes total plus i.
Give total.

To main, giving i32.
Give sum through 5.
```

When a loop, `While`, or `Match` is nested inside another clause list, it consumes following semicolon clauses by default. Start the next clause with `then` when it should run in the parent body after the nested controller:

```inscription,check
To fill and sum, giving i32.
Let result be 0.
Let cells be buffer of 4 i32 filled with 0.
When true: For each index i of cells: cells at i becomes i plus 1; then result becomes cells at 0 plus cells at 1 plus cells at 2 plus cells at 3.
Otherwise: result becomes 1.
Give result.

To main, giving i32.
Give fill and sum.
```

Scalar and record-field assignments inside branches and loops are carried through generated `scf` control flow.
