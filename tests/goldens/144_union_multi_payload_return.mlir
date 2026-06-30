module {
  func.func @make_operator() -> (i32, i64, i8, i8) {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : i64
    %2 = arith.constant 0 : i8
    %3 = arith.constant 2 : i32
    %4 = arith.constant 10 : i8
    %5 = arith.constant 5 : i8
    return %3, %1, %4, %5 : i32, i64, i8, i8
  }

  func.func @main() -> i32 {
    %0:4 = func.call @make_operator() : () -> (i32, i64, i8, i8)
    %1 = arith.constant 2 : i32
    %2 = arith.cmpi eq, %0#0, %1 : i32
    %3 = scf.if %2 -> (i32) {
      %4 = arith.extui %0#2 : i8 to i32
      %5 = arith.extui %0#3 : i8 to i32
      %6 = arith.addi %4, %5 : i32
      scf.yield %6 : i32
    } else {
      %7 = arith.constant 0 : i32
      scf.yield %7 : i32
    }
    return %3 : i32
  }
}
