module {
  func.func @owned_buffer_sum(%n: i32) -> i32 {
    %0 = arith.index_cast %n : i32 to index
    %1 = memref.alloc(%0) : memref<?xi32>
    %2 = arith.constant 1 : i32
    %3 = arith.constant 0 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %3 to %0 step %4 {
      memref.store %2, %1[%5] : memref<?xi32>
    }
    %6 = arith.constant 0 : i32
    %7 = arith.constant 0 : index
    %8 = arith.index_cast %n : i32 to index
    %9 = arith.constant 1 : index
    %11 = scf.for %10 = %7 to %8 step %9 iter_args(%total_iter = %6) -> (i32) {
      %12 = arith.index_cast %10 : index to i32
      %13 = arith.index_cast %12 : i32 to index
      %14 = memref.load %1[%13] : memref<?xi32>
      %15 = arith.addi %total_iter, %14 : i32
      scf.yield %15 : i32
    }
    memref.dealloc %1 : memref<?xi32>
    return %11 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 7 : i32
    %1 = func.call @owned_buffer_sum(%0) : (i32) -> i32
    return %1 : i32
  }
}
