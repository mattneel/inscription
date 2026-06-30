# Scalar Programs

Scalar programs use integer, floating, and boolean expressions. There is no implicit numeric promotion; casts are explicit.

```inscription,check
To average of left: i32 and right: i32, giving i32.
Let total be left plus right.
Give total divided by 2.

To main, giving i32.
Give average of 40 and 44.
```

Floating point arithmetic works for matching float types:

```inscription,check
To rounded weight, giving i32.
Let value: f64 be 6.75.
Give value as i32.
```

Comparisons produce `i1`, which can drive guarded value blocks and `When` sentences.
