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

  func.func @nested_owned_view() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.constant 3 : index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.constant 2 : i32
      %8 = arith.index_cast %7 : i32 to index
      %9 = memref.alloc(%8) : memref<?xi32>
      %10 = arith.constant 0 : index
      %11 = arith.constant 1 : index
      scf.for %12 = %10 to %8 step %11 {
        memref.store %6, %9[%12] : memref<?xi32>
      }
      %13 = arith.constant 0 : i32
      %14 = func.call @sum_view(%9, %13, %7) : (memref<?xi32>, i32, i32) -> i32
      %15 = arith.addi %total_iter, %14 : i32
      memref.dealloc %9 : memref<?xi32>
      scf.yield %15 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @nested_owned_view() : () -> i32
    return %0 : i32
  }
}
