module {
  func.func @make_pair(%left: i32, %right: i32) -> (i32, i32) {
    return %left, %right : i32, i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = arith.constant 5 : i32
    %3 = arith.constant 6 : i32
    %4:2 = func.call @make_pair(%2, %3) : (i32, i32) -> (i32, i32)
    %5 = arith.constant 10 : i32
    %6 = arith.muli %4#0, %5 : i32
    %7 = arith.addi %6, %4#1 : i32
    return %7 : i32
  }
}
