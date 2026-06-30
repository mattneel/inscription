module {
  func.func @choose_token(%flag: i1) -> (i32, i8, i8) {
    %0 = arith.constant true
    %1 = arith.cmpi eq, %flag, %0 : i1
    %2:3 = scf.if %1 -> (i32, i8, i8) {
      %3 = arith.constant 0 : i32
      %4 = arith.constant 0 : i8
      %5 = arith.constant 1 : i32
      %6 = arith.constant 10 : i8
      %7 = arith.constant 5 : i8
      scf.yield %5, %6, %7 : i32, i8, i8
    } else {
      %8 = arith.constant false
      %9 = arith.cmpi eq, %flag, %8 : i1
      %10:3 = scf.if %9 -> (i32, i8, i8) {
        %11 = arith.constant 0 : i32
        %12 = arith.constant 0 : i8
        scf.yield %11, %12, %12 : i32, i8, i8
      } else {
        %13 = arith.constant 0 : i32
        %14 = arith.constant 0 : i8
        scf.yield %13, %14, %14 : i32, i8, i8
      }
      scf.yield %10#0, %10#1, %10#2 : i32, i8, i8
    }
    return %2#0, %2#1, %2#2 : i32, i8, i8
  }

  func.func @main() -> i32 {
    %0 = arith.constant true
    %1:3 = func.call @choose_token(%0) : (i1) -> (i32, i8, i8)
    %2 = arith.constant 1 : i32
    %3 = arith.cmpi eq, %1#0, %2 : i32
    %4 = scf.if %3 -> (i32) {
      %5 = arith.extui %1#1 : i8 to i32
      %6 = arith.extui %1#2 : i8 to i32
      %7 = arith.addi %5, %6 : i32
      scf.yield %7 : i32
    } else {
      %8 = arith.constant 0 : i32
      scf.yield %8 : i32
    }
    return %4 : i32
  }
}
