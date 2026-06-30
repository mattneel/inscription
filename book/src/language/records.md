# Records

Records are nominal value aggregates without byte layout.

```inscription,check
Record Point has x: i32; y: i32.

To main, giving i32.
Let p be Point with x be 3 and y be 4.
Give p.x plus p.y.
```

Record values pass and return by value. The compiler flattens fields to scalar SSA values and function operands/results.
