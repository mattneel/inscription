module {
  func.func @copy_point(%p_x: i32, %p_y: i32) -> (i32, i32) {
    return %p_x, %p_y : i32, i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 7 : i32
    %1 = arith.constant 8 : i32
    %2:2 = func.call @copy_point(%0, %1) : (i32, i32) -> (i32, i32)
    %3 = arith.addi %2#0, %2#1 : i32
    return %3 : i32
  }
}
