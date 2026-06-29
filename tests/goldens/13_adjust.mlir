module {
  func.func @adjust() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = arith.addi %0, %1 : i32
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @adjust() : () -> i32
    return %0 : i32
  }
}
