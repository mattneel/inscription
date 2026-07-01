module {
  func.func @sum_and_drop_cells(%cells: memref<?xi32>, %cells_length: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.index_cast %cells_length : i32 to index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.index_cast %6 : i32 to index
      %8 = memref.load %cells[%7] : memref<?xi32>
      %9 = arith.addi %total_iter, %8 : i32
      scf.yield %9 : i32
    }
    memref.dealloc %cells : memref<?xi32>
    return %5 : i32
  }

  func.func @copy_then_move() -> i32 {
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
    %6 = arith.constant 4 : i32
    %7 = arith.index_cast %6 : i32 to index
    %8 = memref.alloc(%7) : memref<?xi32>
    %9 = arith.constant 0 : index
    %10 = arith.constant 1 : index
    scf.for %11 = %9 to %7 step %10 {
      %12 = memref.load %0[%11] : memref<4xi32>
      memref.store %12, %8[%11] : memref<?xi32>
    }
    %13 = func.call @sum_and_drop_cells(%8, %6) : (memref<?xi32>, i32) -> i32
    return %13 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @copy_then_move() : () -> i32
    return %0 : i32
  }
}
