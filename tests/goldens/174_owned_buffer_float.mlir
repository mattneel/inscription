module {
  func.func @owned_float_sum() -> i32 {
    %0 = arith.constant 4 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xf64>
    %3 = arith.constant 1.5 : f64
    %4 = arith.constant 0 : index
    %5 = arith.constant 1 : index
    scf.for %6 = %4 to %1 step %5 {
      memref.store %3, %2[%6] : memref<?xf64>
    }
    %7 = arith.constant 0.0 : f64
    %8 = arith.constant 0 : index
    %9 = arith.index_cast %0 : i32 to index
    %10 = arith.constant 1 : index
    %12 = scf.for %11 = %8 to %9 step %10 iter_args(%total_iter = %7) -> (f64) {
      %13 = arith.index_cast %11 : index to i32
      %14 = arith.index_cast %13 : i32 to index
      %15 = memref.load %2[%14] : memref<?xf64>
      %16 = arith.addf %total_iter, %15 : f64
      scf.yield %16 : f64
    }
    %17 = arith.fptosi %12 : f64 to i32
    memref.dealloc %2 : memref<?xf64>
    return %17 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @owned_float_sum() : () -> i32
    return %0 : i32
  }
}
