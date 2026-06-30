module {
  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 0 : i32
    %2 = arith.constant 0 : i8
    %3 = arith.constant 10 : i8
    %4 = arith.constant 5 : i8
    %5 = arith.cmpi eq, %0, %0 : i32
    %6 = scf.if %5 -> (i32) {
      %7 = arith.extui %3 : i8 to i32
      %8 = arith.addi %0, %7 : i32
      %9 = arith.extui %4 : i8 to i32
      %10 = arith.addi %8, %9 : i32
      scf.yield %10 : i32
    } else {
      scf.yield %0 : i32
    }
    return %6 : i32
  }
}
