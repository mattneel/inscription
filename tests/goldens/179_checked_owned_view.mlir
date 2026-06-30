module {
  func.func @checked_owned_view(%start: i32, %count: i32) -> i32 {
    %0 = arith.constant 4 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi32>
    %3 = arith.constant 0 : i32
    %4 = arith.constant 0 : index
    %5 = arith.constant 1 : index
    scf.for %6 = %4 to %1 step %5 {
      memref.store %3, %2[%6] : memref<?xi32>
    }
    %7 = arith.constant 7 : i32
    %8 = arith.constant 1 : index
    memref.store %7, %2[%8] : memref<?xi32>
    %9 = arith.constant 0 : index
    %10 = arith.index_cast %start : i32 to index
    %11 = arith.addi %10, %9 : index
    %12 = memref.load %2[%11] : memref<?xi32>
    memref.dealloc %2 : memref<?xi32>
    return %12 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = func.call @checked_owned_view(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
