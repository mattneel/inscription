module {
  func.func @main() -> i32 {
    %0 = arith.constant 3 : i32
    %1 = arith.constant 4 : i32
    %2 = arith.constant 0 : i32
    %3 = arith.constant 0 : i8
    %4 = arith.constant 1 : i32
    %5 = arith.constant 2 : i8
    %6 = arith.cmpi eq, %4, %4 : i32
    %7 = scf.if %6 -> (i32) {
      %8 = arith.addi %0, %1 : i32
      %9 = arith.extui %5 : i8 to i32
      %10 = arith.addi %8, %9 : i32
      scf.yield %10 : i32
    } else {
      %11 = arith.constant 0 : i32
      scf.yield %11 : i32
    }
    return %7 : i32
  }
}
