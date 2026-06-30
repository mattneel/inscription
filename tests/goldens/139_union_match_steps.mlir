module {
  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : i8
    %2 = arith.constant 10 : i32
    %4 = arith.cmpi eq, %0, %0 : i32
    %3:2 = scf.if %4 -> (i32, i32) {
      %5 = arith.addi %0, %2 : i32
      scf.yield %5, %0 : i32, i32
    } else {
      %7 = arith.constant 1 : i32
      %8 = arith.cmpi eq, %0, %7 : i32
      %6:2 = scf.if %8 -> (i32, i32) {
        %9 = arith.extui %1 : i8 to i32
        %10 = arith.addi %0, %9 : i32
        scf.yield %0, %10 : i32, i32
      } else {
        scf.yield %0, %0 : i32, i32
      }
      scf.yield %6#0, %6#1 : i32, i32
    }
    %11 = arith.addi %3#0, %3#1 : i32
    return %11 : i32
  }
}
