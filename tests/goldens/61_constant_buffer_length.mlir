module {
  func.func @sum_cells(%cells: memref<4xi32>) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.constant 4 : index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.index_cast %6 : i32 to index
      %8 = memref.load %cells[%7] : memref<4xi32>
      %9 = arith.addi %total_iter, %8 : i32
      scf.yield %9 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 2 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi32>
    }
    %6 = func.call @sum_cells(%0) : (memref<4xi32>) -> i32
    return %6 : i32
  }
}
