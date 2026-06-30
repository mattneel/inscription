# Control Flow

Use `When`/`Otherwise` for step-level branching and guarded expressions for value selection.

```inscription,check
To absolute value of n: i32, giving i32.
Let value be 0.
When n is less than zero, value becomes zero minus n.
Otherwise, value becomes n.
Give value.

To main, giving i32.
Give absolute value of -9.
```

Loops carry scalar state through MLIR `scf` regions.

```inscription,check
To sum through n: i32, giving i32.
Let total be 0.
For i from 0 up to n: total becomes total plus i.
Give total.

To main, giving i32.
Give sum through 5.
```

`While` loops use the same punctuation model:

```inscription,check
To factorial of n: i32, giving i32.
Let acc be 1.
Let current be n.
While current is greater than 1: acc becomes acc times current; current becomes current minus 1.
Give acc.

To main, giving i32.
Give factorial of 5.
```
