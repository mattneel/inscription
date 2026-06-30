module {
  func.func @modules__Tokens__score_token(%token_tag: i32, %token_operator_symbol: i8, %token_operator_precedence: i8) -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.cmpi eq, %token_tag, %0 : i32
    %2 = scf.if %1 -> (i32) {
      %3 = arith.extui %token_operator_symbol : i8 to i32
      %4 = arith.extui %token_operator_precedence : i8 to i32
      %5 = arith.addi %3, %4 : i32
      scf.yield %5 : i32
    } else {
      %6 = arith.constant 0 : i32
      scf.yield %6 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : i8
    %2 = arith.constant 1 : i32
    %3 = arith.constant 10 : i8
    %4 = arith.constant 5 : i8
    %5 = func.call @modules__Tokens__score_token(%2, %3, %4) : (i32, i8, i8) -> i32
    return %5 : i32
  }
}
