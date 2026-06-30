module {
  func.func @checked_owned_length(%n: i32) -> i32 {
    %0 = arith.index_cast %n : i32 to index
    %1 = memref.alloc(%0) : memref<?xi32>
    %2 = arith.constant 1 : i32
    %3 = arith.constant 0 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %3 to %0 step %4 {
      memref.store %2, %1[%5] : memref<?xi32>
    }
    memref.dealloc %1 : memref<?xi32>
    return %n : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 5 : i32
    %1 = func.call @checked_owned_length(%0) : (i32) -> i32
    return %1 : i32
  }
}
