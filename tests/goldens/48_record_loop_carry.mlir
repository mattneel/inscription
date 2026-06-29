module {
  func.func @walk_point() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.constant 5 : index
    %3 = arith.constant 1 : index
    %5:2 = scf.for %4 = %1 to %2 step %3 iter_args(%p_x_iter = %0, %p_y_iter = %0) -> (i32, i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.constant 1 : i32
      %8 = arith.addi %p_x_iter, %7 : i32
      %9 = arith.constant 2 : i32
      %10 = arith.addi %p_y_iter, %9 : i32
      scf.yield %8, %10 : i32, i32
    }
    %11 = arith.addi %5#0, %5#1 : i32
    return %11 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @walk_point() : () -> i32
    return %0 : i32
  }
}
