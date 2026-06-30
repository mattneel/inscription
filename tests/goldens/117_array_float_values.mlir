module {
  func.func @sum_float_view(%cells_base: memref<?xf64>, %cells_start: i32, %cells_length: i32) -> f64 {
    %0 = arith.constant 0.0 : f64
    %1 = arith.constant 0 : index
    %2 = arith.index_cast %cells_length : i32 to index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (f64) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.index_cast %6 : i32 to index
      %8 = arith.index_cast %cells_start : i32 to index
      %9 = arith.addi %8, %7 : index
      %10 = memref.load %cells_base[%9] : memref<?xf64>
      %11 = arith.addf %total_iter, %10 : f64
      scf.yield %11 : f64
    }
    return %5 : f64
  }

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<3xf64>
    %1 = arith.constant 0.25 : f64
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<3xf64>
    %3 = arith.constant 0.5 : f64
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<3xf64>
    %5 = arith.constant 1.25 : f64
    %6 = arith.constant 2 : index
    memref.store %5, %0[%6] : memref<3xf64>
    %7 = memref.cast %0 : memref<3xf64> to memref<?xf64>
    %8 = arith.constant 0 : i32
    %9 = arith.constant 3 : i32
    %10 = func.call @sum_float_view(%7, %8, %9) : (memref<?xf64>, i32, i32) -> f64
    %11 = arith.fptosi %10 : f64 to i32
    return %11 : i32
  }
}
