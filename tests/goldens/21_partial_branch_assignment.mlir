module {
  func.func @decrement_if_positive(%n: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.cmpi sgt, %n, %0 : i32
    %2 = scf.if %1 -> (i32) {
      %3 = arith.constant 1 : i32
      %4 = arith.subi %n, %3 : i32
      scf.yield %4 : i32
    } else {
      %5 = arith.constant 0 : i32
      scf.yield %n : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 5 : i32
    %1 = func.call @decrement_if_positive(%0) : (i32) -> i32
    return %1 : i32
  }
}
