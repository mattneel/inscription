module {
  func.func @choose_flag(%flag: i1) -> i32 {
    %0 = arith.constant true
    %1 = arith.cmpi eq, %flag, %0 : i1
    %2 = scf.if %1 -> (i32) {
      %3 = arith.constant 7 : i32
      scf.yield %3 : i32
    } else {
      %4 = arith.constant false
      %5 = arith.cmpi eq, %flag, %4 : i1
      %6 = scf.if %5 -> (i32) {
        %7 = arith.constant 3 : i32
        scf.yield %7 : i32
      } else {
        %8 = arith.constant 1 : i32
        scf.yield %8 : i32
      }
      scf.yield %6 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant true
    %1 = func.call @choose_flag(%0) : (i1) -> i32
    return %1 : i32
  }
}
