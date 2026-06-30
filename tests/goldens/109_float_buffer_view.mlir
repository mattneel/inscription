module {
  func.func @sum_float_view(%cells_base: memref<?xf32>, %cells_start: i32, %cells_length: i32) -> f32 {
    %0 = arith.constant 0.0 : f32
    %1 = arith.constant 0 : index
    %2 = arith.index_cast %cells_length : i32 to index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (f32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.index_cast %6 : i32 to index
      %8 = arith.index_cast %cells_start : i32 to index
      %9 = arith.addi %8, %7 : index
      %10 = memref.load %cells_base[%9] : memref<?xf32>
      %11 = arith.addf %total_iter, %10 : f32
      scf.yield %11 : f32
    }
    return %5 : f32
  }

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<4xf32>
    %1 = arith.constant 1.5 : f32
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xf32>
    }
    %6 = memref.cast %0 : memref<4xf32> to memref<?xf32>
    %7 = arith.constant 0 : i32
    %8 = arith.constant 4 : i32
    %9 = func.call @sum_float_view(%6, %7, %8) : (memref<?xf32>, i32, i32) -> f32
    %10 = arith.fptosi %9 : f32 to i32
    return %10 : i32
  }
}
