module {
  func.func @ins_sum_local_buffer() -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 5 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi32>
    }
    %6 = arith.constant 0 : i32
    %7 = arith.constant 0 : index
    %8 = arith.constant 4 : index
    %9 = arith.constant 1 : index
    %11 = scf.for %10 = %7 to %8 step %9 iter_args(%total_iter = %6) -> (i32) {
      %12 = arith.index_cast %10 : index to i32
      %13 = arith.index_cast %12 : i32 to index
      %14 = memref.load %0[%13] : memref<4xi32>
      %15 = arith.addi %total_iter, %14 : i32
      scf.yield %15 : i32
    }
    return %11 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @ins_sum_local_buffer() : () -> i32
    return %0 : i32
  }
}
