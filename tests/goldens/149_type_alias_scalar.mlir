module {
  func.func @add_counts(%left: i32, %right: i32) -> i32 {
    %0 = arith.addi %left, %right : i32
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 20 : i32
    %1 = arith.constant 22 : i32
    %2 = func.call @add_counts(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
