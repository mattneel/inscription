# Hello, Inscription

The smallest useful Inscription program defines `main`, declares that it gives an `i32`, and returns a value with `Give`.

```inscription,check
To main, giving i32.
Give 7.
```

Run it with:

```sh
PYTHONPATH=src python -m inscription run hello.ins
echo $?
```

The process exits with status `7`. Unlike languages with implicit expression bodies, Inscription returning phrases end with an explicit `Give` sentence.
