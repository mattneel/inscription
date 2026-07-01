module {
  func.func @factorial(%n: i32) -> i32 {
    %0 = arith.constant 1 : i32
    %1:2 = scf.while (%result_before = %0, %current_before = %0) : (i32, i32) -> (i32, i32) {
      %2 = arith.cmpi sle, %current_before, %n : i32
      scf.condition(%2) %result_before, %current_before : i32, i32
    } do {
    ^bb0(%result_body: i32, %current_body: i32):
      %3 = arith.muli %result_body, %current_body : i32
      %4 = arith.constant 1 : i32
      %5 = arith.addi %current_body, %4 : i32
      scf.yield %3, %5 : i32, i32
    }
    return %1#0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 120 : i32
    return %0 : i32
  }
}
