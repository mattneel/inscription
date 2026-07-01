module {
  func.func @owned_containing_sum() -> i32 {
    %0 = arith.constant 4 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi32>
    %3 = arith.constant 1 : i32
    %4 = arith.constant 0 : index
    memref.store %3, %2[%4] : memref<?xi32>
    %5 = arith.constant 2 : i32
    %6 = arith.constant 1 : index
    memref.store %5, %2[%6] : memref<?xi32>
    %7 = arith.constant 3 : i32
    %8 = arith.constant 2 : index
    memref.store %7, %2[%8] : memref<?xi32>
    %9 = arith.constant 3 : index
    memref.store %0, %2[%9] : memref<?xi32>
    %10 = arith.constant 0 : i32
    %11 = arith.constant 0 : index
    %12 = arith.index_cast %0 : i32 to index
    %13 = arith.constant 1 : index
    %15 = scf.for %14 = %11 to %12 step %13 iter_args(%total_iter = %10) -> (i32) {
      %16 = arith.index_cast %14 : index to i32
      %17 = arith.index_cast %16 : i32 to index
      %18 = memref.load %2[%17] : memref<?xi32>
      %19 = arith.addi %total_iter, %18 : i32
      scf.yield %19 : i32
    }
    memref.dealloc %2 : memref<?xi32>
    return %15 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @owned_containing_sum() : () -> i32
    return %0 : i32
  }
}
