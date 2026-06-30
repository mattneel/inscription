module {
  func.func @checked_owned_index(%i: i32) -> i32 {
    %0 = arith.constant 4 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi32>
    %3 = arith.constant 0 : i32
    %4 = arith.constant 0 : index
    %5 = arith.constant 1 : index
    scf.for %6 = %4 to %1 step %5 {
      memref.store %3, %2[%6] : memref<?xi32>
    }
    %7 = arith.constant 1 : i32
    %8 = arith.constant 0 : index
    memref.store %7, %2[%8] : memref<?xi32>
    %9 = arith.constant 2 : i32
    %10 = arith.constant 1 : index
    memref.store %9, %2[%10] : memref<?xi32>
    %11 = arith.constant 3 : i32
    %12 = arith.constant 2 : index
    memref.store %11, %2[%12] : memref<?xi32>
    %13 = arith.constant 3 : index
    memref.store %0, %2[%13] : memref<?xi32>
    %14 = arith.index_cast %i : i32 to index
    %15 = arith.constant 0 : index
    %16 = arith.cmpi sge, %14, %15 : index
    cf.assert %16, "storage lower-bound check failed at line 7"
    %17 = arith.index_cast %0 : i32 to index
    %18 = arith.cmpi slt, %14, %17 : index
    cf.assert %18, "storage upper-bound check failed at line 7"
    %19 = memref.load %2[%14] : memref<?xi32>
    memref.dealloc %2 : memref<?xi32>
    return %19 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 2 : i32
    %1 = func.call @checked_owned_index(%0) : (i32) -> i32
    return %1 : i32
  }
}
