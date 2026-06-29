module {
  func.func @double_sum(%a: i32, %b: i32) -> i32 {
    %0 = arith.addi %a, %b : i32
    %1 = arith.constant 2 : i32
    %2 = arith.muli %0, %1 : i32
    return %2 : i32
  }
}
