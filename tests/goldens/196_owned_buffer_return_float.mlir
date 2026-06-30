module {
  func.func @make_floats(%count: i32) -> (memref<?xf64>, i32) {
    %0 = arith.index_cast %count : i32 to index
    %1 = memref.alloc(%0) : memref<?xf64>
    %2 = arith.constant 1.5 : f64
    %3 = arith.constant 0 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %3 to %0 step %4 {
      memref.store %2, %1[%5] : memref<?xf64>
    }
    return %1, %count : memref<?xf64>, i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 4 : i32
    %1:2 = func.call @make_floats(%0) : (i32) -> (memref<?xf64>, i32)
    %2 = arith.constant 0.0 : f64
    %3 = arith.constant 0 : index
    %4 = arith.index_cast %1#1 : i32 to index
    %5 = arith.constant 1 : index
    %7 = scf.for %6 = %3 to %4 step %5 iter_args(%total_iter = %2) -> (f64) {
      %8 = arith.index_cast %6 : index to i32
      %9 = arith.index_cast %8 : i32 to index
      %10 = memref.load %1#0[%9] : memref<?xf64>
      %11 = arith.addf %total_iter, %10 : f64
      scf.yield %11 : f64
    }
    %12 = arith.fptosi %7 : f64 to i32
    memref.dealloc %1#0 : memref<?xf64>
    return %12 : i32
  }
}
