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

Scalar and record-field assignments inside branches and loops are carried through generated `scf` control flow.
