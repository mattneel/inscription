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

Union matches can omit `otherwise` when every declared variant is covered:

```inscription,check
Union MaybeI32 has none; some value: i32.

To value or zero maybe: MaybeI32, giving i32.
Give match maybe:
MaybeI32.none gives 0;
MaybeI32.some with value gives value.

To main, giving i32.
Give value or zero MaybeI32.some with value be 42.
```

Use `anything` or `otherwise` when a catch-all branch is clearer or when externally sourced union tags must be handled explicitly.

## Ignoring payload fields

Use `field ignored` when a payload field must be matched but should not introduce a binding:

```inscription,check
Union Token has eof; operator symbol: u8 and precedence: u8.

To precedence token token: Token, giving i32.
Give match token:
Token.operator with symbol ignored and precedence as prec gives prec as i32;
anything gives 0.

To main, giving i32.
Give precedence token Token.operator with symbol be 43 and precedence be 10.
```

Ignored fields still appear in declaration order and count as present for payload pattern completeness. They introduce no binding, so guards and result expressions cannot use the ignored field name unless that name is visible from an outer scope.

`ignored` is only for union payload fields. It is not the whole-value wildcard; use `anything` for that.

## Payload guards

Guards can use payload bindings that are actually introduced:

```inscription,check
Union Token has eof; operator symbol: u8 and precedence: u8.

To high precedence token token: Token, giving i32.
Give match token:
Token.operator with symbol ignored and precedence as prec when prec is greater than 5 gives prec as i32;
Token.operator with symbol ignored and precedence ignored gives 1;
anything gives 0.

To main, giving i32.
Give high precedence token Token.operator with symbol be 43 and precedence be 10.
```
