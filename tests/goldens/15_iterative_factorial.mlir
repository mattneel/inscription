module {
  func.func @factorial_iteratively(%n: i32) -> i32 {
    %0 = arith.constant 1 : i32
    %1:2 = scf.while (%n_before = %n, %acc_before = %0) : (i32, i32) -> (i32, i32) {
      %2 = arith.constant 1 : i32
      %3 = arith.cmpi sgt, %n_before, %2 : i32
      scf.condition(%3) %n_before, %acc_before : i32, i32
    } do {
    ^bb0(%n_body: i32, %acc_body: i32):
      %4 = arith.muli %acc_body, %n_body : i32
      %5 = arith.constant 1 : i32
      %6 = arith.subi %n_body, %5 : i32
      scf.yield %6, %4 : i32, i32
    }
    return %1#1 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 5 : i32
    %1 = func.call @factorial_iteratively(%0) : (i32) -> i32
    return %1 : i32
  }
}
