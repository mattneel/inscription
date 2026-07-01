module {
  func.func @high_precedence_token(%token_tag: i32, %token_operator_symbol: i8, %token_operator_precedence: i8) -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.cmpi eq, %token_tag, %0 : i32
    %2 = scf.if %1 -> (i32) {
      %3 = arith.constant 5 : i8
      %4 = arith.cmpi ugt, %token_operator_precedence, %3 : i8
      %5 = scf.if %4 -> (i32) {
        %6 = arith.extui %token_operator_precedence : i8 to i32
        scf.yield %6 : i32
      } else {
        %7 = arith.constant 1 : i32
        %8 = arith.cmpi eq, %token_tag, %7 : i32
        %9 = scf.if %8 -> (i32) {
          %10 = arith.constant 1 : i32
          scf.yield %10 : i32
        } else {
          %11 = arith.constant 0 : i32
          scf.yield %11 : i32
        }
        scf.yield %9 : i32
      }
      scf.yield %5 : i32
    } else {
      %12 = arith.constant 1 : i32
      %13 = arith.cmpi eq, %token_tag, %12 : i32
      %14 = scf.if %13 -> (i32) {
        %15 = arith.constant 1 : i32
        scf.yield %15 : i32
      } else {
        %16 = arith.constant 0 : i32
        scf.yield %16 : i32
      }
      scf.yield %14 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : i8
    %2 = arith.constant 1 : i32
    %3 = arith.constant 43 : i8
    %4 = arith.constant 10 : i8
    %5 = func.call @high_precedence_token(%2, %3, %4) : (i32, i8, i8) -> i32
    return %5 : i32
  }
}
