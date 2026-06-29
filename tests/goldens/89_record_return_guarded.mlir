module {
  func.func @choose_point(%flag: i1) -> (i32, i32) {
    %0:2 = scf.if %flag -> (i32, i32) {
      %1 = arith.constant 7 : i32
      %2 = arith.constant 0 : i32
      scf.yield %1, %2 : i32, i32
    } else {
      %3 = arith.constant 0 : i32
      %4 = arith.constant 3 : i32
      scf.yield %3, %4 : i32, i32
    }
    return %0#0, %0#1 : i32, i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant true
    %1:2 = func.call @choose_point(%0) : (i1) -> (i32, i32)
    %2 = arith.addi %1#0, %1#1 : i32
    return %2 : i32
  }
}
