module {
  func.func private @llvm.ctpop.i32(i32) -> i32

  func.func @sum_population_counts() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.constant 4 : index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = func.call @llvm.ctpop.i32(%6) : (i32) -> i32
      %8 = arith.addi %total_iter, %7 : i32
      scf.yield %8 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @sum_population_counts() : () -> i32
    return %0 : i32
  }
}
