module {
  func.func @array_sum() -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 1 : i32
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<4xi32>
    %3 = arith.constant 2 : i32
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<4xi32>
    %5 = arith.constant 3 : i32
    %6 = arith.constant 2 : index
    memref.store %5, %0[%6] : memref<4xi32>
    %7 = arith.constant 4 : i32
    %8 = arith.constant 3 : index
    memref.store %7, %0[%8] : memref<4xi32>
    %9 = arith.constant 0 : i32
    %10 = arith.constant 0 : index
    %11 = arith.constant 4 : index
    %12 = arith.constant 1 : index
    %14 = scf.for %13 = %10 to %11 step %12 iter_args(%total_iter = %9) -> (i32) {
      %15 = arith.index_cast %13 : index to i32
      %16 = arith.index_cast %15 : i32 to index
      %17 = memref.load %0[%16] : memref<4xi32>
      %18 = arith.addi %total_iter, %17 : i32
      scf.yield %18 : i32
    }
    return %14 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @array_sum() : () -> i32
    return %0 : i32
  }
}
