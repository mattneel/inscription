module {
  func.func @sum(%a: i32, %b: i32) -> i32 {
    %0 = arith.addi %a, %b : i32
    return %0 : i32
  }
}
