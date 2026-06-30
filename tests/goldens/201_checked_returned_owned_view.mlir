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
    %6 = arith.constant 7 : i32
    %7 = arith.constant 1 : index
    memref.store %6, %1[%7] : memref<?xi32>
    return %1, %count : memref<?xi32>, i32
  }

  func.func @checked_returned_view(%start: i32, %count: i32) -> i32 {
    %0 = arith.constant 4 : i32
    %1:2 = func.call @make_cells(%0) : (i32) -> (memref<?xi32>, i32)
    %2 = arith.constant 0 : index
    %3 = arith.index_cast %start : i32 to index
    %4 = arith.addi %3, %2 : index
    %5 = memref.load %1#0[%4] : memref<?xi32>
    memref.dealloc %1#0 : memref<?xi32>
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = func.call @checked_returned_view(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
