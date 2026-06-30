module {
  func.func @make_selected(%count: i32) -> (memref<?xi32>, i32) {
    %0 = arith.index_cast %count : i32 to index
    %1 = memref.alloc(%0) : memref<?xi32>
    %2 = arith.constant 9 : i32
    %3 = arith.constant 0 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %3 to %0 step %4 {
      memref.store %2, %1[%5] : memref<?xi32>
    }
    %6 = arith.index_cast %count : i32 to index
    %7 = memref.alloc(%6) : memref<?xi32>
    %8 = arith.constant 1 : i32
    %9 = arith.constant 0 : index
    %10 = arith.constant 1 : index
    scf.for %11 = %9 to %6 step %10 {
      memref.store %8, %7[%11] : memref<?xi32>
    }
    %12 = arith.constant 0 : index
    %13 = memref.load %1[%12] : memref<?xi32>
    %14 = arith.constant 0 : index
    memref.store %13, %7[%14] : memref<?xi32>
    memref.dealloc %1 : memref<?xi32>
    return %7, %count : memref<?xi32>, i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 3 : i32
    %1:2 = func.call @make_selected(%0) : (i32) -> (memref<?xi32>, i32)
    %2 = arith.constant 0 : index
    %3 = memref.load %1#0[%2] : memref<?xi32>
    memref.dealloc %1#0 : memref<?xi32>
    return %3 : i32
  }
}
