module {
  func.func @fill_view(%cells_base: memref<?xi32>, %cells_start: i32, %cells_length: i32, %value: i32) {
    %0 = arith.constant 0 : index
    %1 = arith.index_cast %cells_length : i32 to index
    %2 = arith.constant 1 : index
    scf.for %3 = %0 to %1 step %2 {
      %4 = arith.index_cast %3 : index to i32
      %5 = arith.index_cast %4 : i32 to index
      %6 = arith.index_cast %cells_start : i32 to index
      %7 = arith.addi %6, %5 : index
      memref.store %value, %cells_base[%7] : memref<?xi32>
    }
    return
  }

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

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 0 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi32>
    }
    %6 = arith.constant 1 : i32
    %7 = arith.constant 2 : i32
    %8 = memref.cast %0 : memref<4xi32> to memref<?xi32>
    %9 = arith.constant 7 : i32
    func.call @fill_view(%8, %6, %7, %9) : (memref<?xi32>, i32, i32, i32) -> ()
    %10 = memref.cast %0 : memref<4xi32> to memref<?xi32>
    %11 = arith.constant 4 : i32
    %12 = func.call @sum_view(%10, %1, %11) : (memref<?xi32>, i32, i32) -> i32
    return %12 : i32
  }
}
