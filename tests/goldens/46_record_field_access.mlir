module {
  func.func @sum_point(%p_x: i32, %p_y: i32) -> i32 {
    %0 = arith.addi %p_x, %p_y : i32
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 10 : i32
    %1 = arith.constant 20 : i32
    %2 = func.call @sum_point(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
