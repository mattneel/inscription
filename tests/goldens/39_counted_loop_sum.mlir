module {
  func.func @sum_counted() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.constant 10 : index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.addi %total_iter, %6 : i32
      scf.yield %7 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @sum_counted() : () -> i32
    return %0 : i32
  }
}
