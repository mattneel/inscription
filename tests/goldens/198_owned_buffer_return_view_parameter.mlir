module {
  func.func @sum_view(%cells_base: memref<?xi32>, %cells_start: i32, %cells_length: i32) -> i32 {
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

  func.func @make_cells(%count: i32) -> (memref<?xi32>, i32) {
    %0 = arith.index_cast %count : i32 to index
    %1 = memref.alloc(%0) : memref<?xi32>
    %2 = arith.constant 3 : i32
    %3 = arith.constant 0 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %3 to %0 step %4 {
      memref.store %2, %1[%5] : memref<?xi32>
    }
    return %1, %count : memref<?xi32>, i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 4 : i32
    %1:2 = func.call @make_cells(%0) : (i32) -> (memref<?xi32>, i32)
    %2 = arith.constant 0 : i32
    %3 = func.call @sum_view(%1#0, %2, %1#1) : (memref<?xi32>, i32, i32) -> i32
    memref.dealloc %1#0 : memref<?xi32>
    return %3 : i32
  }
}
