module {
  func.func @sum_through(%n: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 1 : i32
    %2:2 = scf.while (%total_before = %0, %i_before = %1) : (i32, i32) -> (i32, i32) {
      %3 = arith.cmpi sle, %i_before, %n : i32
      scf.condition(%3) %total_before, %i_before : i32, i32
    } do {
    ^bb0(%total_body: i32, %i_body: i32):
      %4 = arith.addi %total_body, %i_body : i32
      %5 = arith.constant 1 : i32
      %6 = arith.addi %i_body, %5 : i32
      scf.yield %4, %6 : i32, i32
    }
    return %2#0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 10 : i32
    %1 = func.call @sum_through(%0) : (i32) -> i32
    return %1 : i32
  }
}
