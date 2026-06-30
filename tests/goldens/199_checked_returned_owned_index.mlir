module {
  func.func @make_cells(%count: i32) -> (memref<?xi32>, i32) {
    %0 = arith.index_cast %count : i32 to index
    %1 = memref.alloc(%0) : memref<?xi32>
    %2 = arith.constant 0 : i32
    %3 = arith.constant 0 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %3 to %0 step %4 {
      memref.store %2, %1[%5] : memref<?xi32>
    }
    %6 = arith.constant 1 : i32
    %7 = arith.constant 0 : index
    memref.store %6, %1[%7] : memref<?xi32>
    %8 = arith.constant 2 : i32
    %9 = arith.constant 1 : index
    memref.store %8, %1[%9] : memref<?xi32>
    %10 = arith.constant 3 : i32
    %11 = arith.constant 2 : index
    memref.store %10, %1[%11] : memref<?xi32>
    %12 = arith.constant 4 : i32
    %13 = arith.constant 3 : index
    memref.store %12, %1[%13] : memref<?xi32>
    return %1, %count : memref<?xi32>, i32
  }

  func.func @checked_returned_index(%i: i32) -> i32 {
    %0 = arith.constant 4 : i32
    %1:2 = func.call @make_cells(%0) : (i32) -> (memref<?xi32>, i32)
    %2 = arith.index_cast %i : i32 to index
    %3 = memref.load %1#0[%2] : memref<?xi32>
    memref.dealloc %1#0 : memref<?xi32>
    return %3 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 2 : i32
    %1 = func.call @checked_returned_index(%0) : (i32) -> i32
    return %1 : i32
  }
}
