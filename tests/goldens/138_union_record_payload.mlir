module {
  func.func @main() -> i32 {
    %0 = arith.constant 3 : i32
    %1 = arith.constant 4 : i32
    %2 = arith.constant 0 : i32
    %3 = arith.constant 1 : i32
    %4 = arith.cmpi eq, %3, %3 : i32
    %5 = scf.if %4 -> (i32) {
      %6 = arith.addi %0, %1 : i32
      scf.yield %6 : i32
    } else {
      %7 = arith.constant 0 : i32
      scf.yield %7 : i32
    }
    return %5 : i32
  }
}
