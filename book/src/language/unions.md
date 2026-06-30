# Unions

Unions are nominal tagged values. Variants can be payload-free or carry named payload fields.

```inscription,check
Union Token has eof; operator symbol: u8 and precedence: u8.

To score token token: Token, giving i32.
Give match token:
Token.operator with symbol as op and precedence as prec gives (op as i32) plus (prec as i32);
otherwise gives 0.

To main, giving i32.
Give score token Token.operator with symbol be 10 and precedence be 5.
```

Payload aliases are scoped to the match arm. Unions are not stored in records, buffers, arrays, views, owned buffers, layout records, or extern/export ABI.
