module {
  func.func @multiply_counted(%a: i32, %b: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.index_cast %b : i32 to index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.constant 0 : index
      %8 = arith.index_cast %a : i32 to index
      %9 = arith.constant 1 : index
      %11 = scf.for %10 = %7 to %8 step %9 iter_args(%total_iter_for1 = %total_iter) -> (i32) {
        %12 = arith.index_cast %10 : index to i32
        %13 = arith.constant 1 : i32
        %14 = arith.addi %total_iter_for1, %13 : i32
        scf.yield %14 : i32
      }
      scf.yield %11 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 6 : i32
    %1 = arith.constant 7 : i32
    %2 = func.call @multiply_counted(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
