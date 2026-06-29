module {
  func.func @move_point(%p_x: i32, %p_y: i32, %dx: i32, %dy: i32) -> i32 {
    %0 = arith.addi %p_x, %dx : i32
    %1 = arith.addi %p_y, %dy : i32
    %2 = arith.addi %0, %1 : i32
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = arith.constant 3 : i32
    %3 = arith.constant 4 : i32
    %4 = func.call @move_point(%0, %1, %2, %3) : (i32, i32, i32, i32) -> i32
    return %4 : i32
  }
}
