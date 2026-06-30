module {
  func.func @make_cells(%count: i32) -> (memref<?xi32>, i32) {
    %0 = arith.constant 1 : i32
    %1 = arith.cmpi sge, %count, %0 : i32
    cf.assert %1, "owned buffer length check failed at line 2"
    %2 = arith.index_cast %count : i32 to index
    %3 = memref.alloc(%2) : memref<?xi32>
    %4 = arith.constant 0 : i32
    %5 = arith.constant 0 : index
    %6 = arith.constant 1 : index
    scf.for %7 = %5 to %2 step %6 {
      memref.store %4, %3[%7] : memref<?xi32>
    }
    %8 = arith.constant 0 : index
    memref.store %0, %3[%8] : memref<?xi32>
    %9 = arith.constant 2 : i32
    %10 = arith.constant 1 : index
    memref.store %9, %3[%10] : memref<?xi32>
    %11 = arith.constant 3 : i32
    %12 = arith.constant 2 : index
    memref.store %11, %3[%12] : memref<?xi32>
    %13 = arith.constant 4 : i32
    %14 = arith.constant 3 : index
    memref.store %13, %3[%14] : memref<?xi32>
    return %3, %count : memref<?xi32>, i32
  }

  func.func @checked_returned_index(%i: i32) -> i32 {
    %0 = arith.constant 4 : i32
    %1:2 = func.call @make_cells(%0) : (i32) -> (memref<?xi32>, i32)
    %2 = arith.index_cast %i : i32 to index
    %3 = arith.constant 0 : index
    %4 = arith.cmpi sge, %2, %3 : index
    cf.assert %4, "storage lower-bound check failed at line 11"
    %5 = arith.index_cast %1#1 : i32 to index
    %6 = arith.cmpi slt, %2, %5 : index
    cf.assert %6, "storage upper-bound check failed at line 11"
    %7 = memref.load %1#0[%2] : memref<?xi32>
    memref.dealloc %1#0 : memref<?xi32>
    return %7 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 2 : i32
    %1 = func.call @checked_returned_index(%0) : (i32) -> i32
    return %1 : i32
  }
}
