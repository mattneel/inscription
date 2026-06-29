module {
  func.func @scaled_sum(%a: i32, %b: i32) -> i32 {
    %0 = arith.constant 2 : i32
    %1 = arith.muli %b, %0 : i32
    %2 = arith.addi %a, %1 : i32
    return %2 : i32
  }
}
