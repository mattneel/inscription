module {
  func.func @make_ones(%count: i32) -> (memref<?xi32>, i32) {
    %0 = arith.index_cast %count : i32 to index
    %1 = memref.alloc(%0) : memref<?xi32>
    %2 = arith.constant 1 : i32
    %3 = arith.constant 0 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %3 to %0 step %4 {
      memref.store %2, %1[%5] : memref<?xi32>
    }
    return %1, %count : memref<?xi32>, i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 7 : i32
    %1:2 = func.call @make_ones(%0) : (i32) -> (memref<?xi32>, i32)
    memref.dealloc %1#0 : memref<?xi32>
    return %1#1 : i32
  }
}
