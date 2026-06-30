module {
  func.func @choose_maybe(%flag: i1) -> (i32, i32) {
    %0 = arith.constant true
    %1 = arith.cmpi eq, %flag, %0 : i1
    %2:2 = scf.if %1 -> (i32, i32) {
      %3 = arith.constant 0 : i32
      %4 = arith.constant 1 : i32
      %5 = arith.constant 9 : i32
      scf.yield %4, %5 : i32, i32
    } else {
      %6 = arith.constant false
      %7 = arith.cmpi eq, %flag, %6 : i1
      %8:2 = scf.if %7 -> (i32, i32) {
        %9 = arith.constant 0 : i32
        scf.yield %9, %9 : i32, i32
      } else {
        %10 = arith.constant 0 : i32
        scf.yield %10, %10 : i32, i32
      }
      scf.yield %8#0, %8#1 : i32, i32
    }
    return %2#0, %2#1 : i32, i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant true
    %1:2 = func.call @choose_maybe(%0) : (i1) -> (i32, i32)
    %2 = arith.constant 1 : i32
    %3 = arith.cmpi eq, %1#0, %2 : i32
    %4 = scf.if %3 -> (i32) {
      scf.yield %1#1 : i32
    } else {
      %5 = arith.constant 0 : i32
      scf.yield %5 : i32
    }
    return %4 : i32
  }
}
