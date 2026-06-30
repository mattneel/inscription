module {
  func.func @sum_cells(%cells_base: memref<?xi32>, %cells_start: i32, %cells_length: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.index_cast %cells_length : i32 to index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.index_cast %6 : i32 to index
      %8 = arith.index_cast %cells_start : i32 to index
      %9 = arith.addi %8, %7 : index
      %10 = memref.load %cells_base[%9] : memref<?xi32>
      %11 = arith.addi %total_iter, %10 : i32
      scf.yield %11 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 3 : i32
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<4xi32>
    %3 = arith.constant 1 : index
    memref.store %1, %0[%3] : memref<4xi32>
    %4 = arith.constant 2 : index
    memref.store %1, %0[%4] : memref<4xi32>
    %5 = arith.constant 3 : index
    memref.store %1, %0[%5] : memref<4xi32>
    %6 = memref.cast %0 : memref<4xi32> to memref<?xi32>
    %7 = arith.constant 0 : i32
    %8 = arith.constant 4 : i32
    %9 = func.call @sum_cells(%6, %7, %8) : (memref<?xi32>, i32, i32) -> i32
    return %9 : i32
  }
}
