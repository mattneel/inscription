module {
  func.func @swap_pair() -> i32 {
    %0 = arith.constant 3 : i32
    %1 = arith.constant 5 : i32
    %2 = arith.constant 10 : i32
    %3 = arith.muli %1, %2 : i32
    %4 = arith.addi %3, %0 : i32
    return %4 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @swap_pair() : () -> i32
    return %0 : i32
  }
}
