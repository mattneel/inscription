module {
  func.func @collatz_steps(%n: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1:2 = scf.while (%n_before = %n, %steps_before = %0) : (i32, i32) -> (i32, i32) {
      %2 = arith.constant 1 : i32
      %3 = arith.cmpi sgt, %n_before, %2 : i32
      scf.condition(%3) %n_before, %steps_before : i32, i32
    } do {
    ^bb0(%n_body: i32, %steps_body: i32):
      %4 = arith.constant 2 : i32
      %5 = arith.remsi %n_body, %4 : i32
      %6 = arith.constant 0 : i32
      %7 = arith.cmpi eq, %5, %6 : i32
      %8 = scf.if %7 -> (i32) {
        %9 = arith.constant 2 : i32
        %10 = arith.divsi %n_body, %9 : i32
        scf.yield %10 : i32
      } else {
        %11 = arith.constant 3 : i32
        %12 = arith.muli %n_body, %11 : i32
        %13 = arith.constant 1 : i32
        %14 = arith.addi %12, %13 : i32
        scf.yield %14 : i32
      }
      %15 = arith.constant 1 : i32
      %16 = arith.addi %steps_body, %15 : i32
      scf.yield %8, %16 : i32, i32
    }
    return %1#1 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 7 : i32
    %1 = func.call @collatz_steps(%0) : (i32) -> i32
    return %1 : i32
  }
}
