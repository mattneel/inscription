# Require and Runtime Checks

`Require` is a phrase-body sentence for runtime preconditions. A statically false requirement is a compile-time error; a dynamic requirement lowers to a runtime assertion.

```inscription,check
To safe positive value: i32, giving i32.
Require value is greater than zero.
Give value.

To main, giving i32.
Give safe positive 7.
```

`--runtime-checks` adds compiler-generated checks for dynamic storage bounds, dynamic owned-buffer lengths, view creation, and layout read/write bounds. These checks are independent of user-written `Require` sentences.
