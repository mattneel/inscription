module {
  func.func @checked_nested_owned_index(%i: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant true
    %2 = scf.if %1 -> (i32) {
      %3 = arith.constant 4 : i32
      %4 = arith.index_cast %3 : i32 to index
      %5 = memref.alloc(%4) : memref<?xi32>
      %6 = arith.constant 0 : i32
      %7 = arith.constant 0 : index
      %8 = arith.constant 1 : index
      scf.for %9 = %7 to %4 step %8 {
        memref.store %6, %5[%9] : memref<?xi32>
      }
      %10 = arith.constant 1 : i32
      %11 = arith.constant 0 : index
      memref.store %10, %5[%11] : memref<?xi32>
      %12 = arith.constant 2 : i32
      %13 = arith.constant 1 : index
      memref.store %12, %5[%13] : memref<?xi32>
      %14 = arith.constant 3 : i32
      %15 = arith.constant 2 : index
      memref.store %14, %5[%15] : memref<?xi32>
      %16 = arith.constant 3 : index
      memref.store %3, %5[%16] : memref<?xi32>
      %17 = arith.index_cast %i : i32 to index
      %18 = memref.load %5[%17] : memref<?xi32>
      memref.dealloc %5 : memref<?xi32>
      scf.yield %18 : i32
    } else {
      %19 = arith.constant 0 : i32
      scf.yield %19 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 2 : i32
    %1 = func.call @checked_nested_owned_index(%0) : (i32) -> i32
    return %1 : i32
  }
}
