# Type Aliases

Type aliases are transparent source names for existing types.

```inscription,check
Type Count be i32.

Type Scores be array of 4 Count.

To main, giving i32.
Let values be Scores containing 1, 2, 3, 4.
Give values at 0 plus values at 3.
```

Aliases do not create nominal identity or change runtime representation. Recursive aliases are rejected. C headers use resolved primitive types and do not emit C typedefs.
