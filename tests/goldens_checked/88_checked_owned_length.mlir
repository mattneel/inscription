module {
  func.func @checked_owned_length(%n: i32) -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.cmpi sge, %n, %0 : i32
    cf.assert %1, "owned buffer length check failed at line 2"
    %2 = arith.index_cast %n : i32 to index
    %3 = memref.alloc(%2) : memref<?xi32>
    %4 = arith.constant 0 : index
    %5 = arith.constant 1 : index
    scf.for %6 = %4 to %2 step %5 {
      memref.store %0, %3[%6] : memref<?xi32>
    }
    memref.dealloc %3 : memref<?xi32>
    return %n : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 5 : i32
    %1 = func.call @checked_owned_length(%0) : (i32) -> i32
    return %1 : i32
  }
}
