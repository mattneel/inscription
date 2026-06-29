module {
  func.func @sum_required_view(%cells_base: memref<?xi32>, %cells_start: i32, %cells_length: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.cmpi sgt, %cells_length, %0 : i32
    cf.assert %1, "require failed at line 2"
    %2 = arith.constant 0 : index
    %3 = arith.index_cast %cells_length : i32 to index
    %4 = arith.constant 1 : index
    %6 = scf.for %5 = %2 to %3 step %4 iter_args(%total_iter = %0) -> (i32) {
      %7 = arith.index_cast %5 : index to i32
      %8 = arith.index_cast %7 : i32 to index
      %9 = arith.index_cast %cells_start : i32 to index
      %10 = arith.addi %9, %8 : index
      %11 = memref.load %cells_base[%10] : memref<?xi32>
      %12 = arith.addi %total_iter, %11 : i32
      scf.yield %12 : i32
    }
    return %6 : i32
  }

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 3 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi32>
    }
    %6 = memref.cast %0 : memref<4xi32> to memref<?xi32>
    %7 = arith.constant 0 : i32
    %8 = arith.constant 4 : i32
    %9 = func.call @sum_required_view(%6, %7, %8) : (memref<?xi32>, i32, i32) -> i32
    return %9 : i32
  }
}
