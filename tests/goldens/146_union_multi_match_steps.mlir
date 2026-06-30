module {
  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : i8
    %2 = arith.constant 1 : i32
    %3 = arith.constant 2 : i8
    %4 = arith.constant 8 : i32
    %6 = arith.cmpi eq, %2, %0 : i32
    %5:2 = scf.if %6 -> (i32, i32) {
      %7 = arith.addi %0, %0 : i32
      scf.yield %7, %0 : i32, i32
    } else {
      %9 = arith.constant 1 : i32
      %10 = arith.cmpi eq, %2, %9 : i32
      %8:2 = scf.if %10 -> (i32, i32) {
        %11 = arith.extui %3 : i8 to i32
        %12 = arith.addi %0, %11 : i32
        %13 = arith.addi %12, %4 : i32
        scf.yield %0, %13 : i32, i32
      } else {
        scf.yield %0, %0 : i32, i32
      }
      scf.yield %8#0, %8#1 : i32, i32
    }
    %14 = arith.addi %5#0, %5#1 : i32
    return %14 : i32
  }
}
