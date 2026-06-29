module {
  func.func @main() -> i32 {
    %0 = arith.constant 6 : i32
    %1 = arith.constant 4 : i32
    %2 = arith.addi %0, %1 : i32
    return %2 : i32
  }
}
