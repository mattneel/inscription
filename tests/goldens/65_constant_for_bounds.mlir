module {
  func.func @sum_constant_range() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.constant 5 : i32
    %3 = arith.index_cast %2 : i32 to index
    %4 = arith.constant 1 : index
    %6 = scf.for %5 = %1 to %3 step %4 iter_args(%total_iter = %0) -> (i32) {
      %7 = arith.index_cast %5 : index to i32
      %8 = arith.addi %total_iter, %7 : i32
      scf.yield %8 : i32
    }
    return %6 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @sum_constant_range() : () -> i32
    return %0 : i32
  }
}
