module {
  func.func @make_indices(%count: i32) -> (memref<?xi32>, i32) {
    %0 = arith.index_cast %count : i32 to index
    %1 = memref.alloc(%0) : memref<?xi32>
    %2 = arith.constant 0 : i32
    %3 = arith.constant 0 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %3 to %0 step %4 {
      memref.store %2, %1[%5] : memref<?xi32>
    }
    %6 = arith.constant 0 : index
    %7 = arith.index_cast %count : i32 to index
    %8 = arith.constant 1 : index
    scf.for %9 = %6 to %7 step %8 {
      %10 = arith.index_cast %9 : index to i32
      %11 = arith.constant 1 : i32
      %12 = arith.addi %10, %11 : i32
      %13 = arith.index_cast %10 : i32 to index
      memref.store %12, %1[%13] : memref<?xi32>
    }
    return %1, %count : memref<?xi32>, i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 4 : i32
    %1:2 = func.call @make_indices(%0) : (i32) -> (memref<?xi32>, i32)
    %2 = arith.constant 0 : index
    %3 = memref.load %1#0[%2] : memref<?xi32>
    %4 = arith.constant 1 : index
    %5 = memref.load %1#0[%4] : memref<?xi32>
    %6 = arith.addi %3, %5 : i32
    %7 = arith.constant 2 : index
    %8 = memref.load %1#0[%7] : memref<?xi32>
    %9 = arith.addi %6, %8 : i32
    %10 = arith.constant 3 : index
    %11 = memref.load %1#0[%10] : memref<?xi32>
    %12 = arith.addi %9, %11 : i32
    memref.dealloc %1#0 : memref<?xi32>
    return %12 : i32
  }
}
