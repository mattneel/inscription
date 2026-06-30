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
    %8 = arith.constant 7 : i32
    %9 = arith.constant 1 : index
    memref.store %8, %3[%9] : memref<?xi32>
    return %3, %count : memref<?xi32>, i32
  }

  func.func @checked_returned_view(%start: i32, %count: i32) -> i32 {
    %0 = arith.constant 4 : i32
    %1:2 = func.call @make_cells(%0) : (i32) -> (memref<?xi32>, i32)
    %2 = arith.constant 0 : i32
    %3 = arith.cmpi sge, %start, %2 : i32
    cf.assert %3, "view start check failed at line 8"
    %4 = arith.cmpi sge, %count, %2 : i32
    cf.assert %4, "view count check failed at line 8"
    %5 = arith.cmpi sle, %start, %1#1 : i32
    cf.assert %5, "view start range check failed at line 8"
    %6 = arith.subi %1#1, %start : i32
    %7 = arith.cmpi sle, %count, %6 : i32
    cf.assert %7, "view count range check failed at line 8"
    %8 = arith.constant 0 : index
    %9 = arith.index_cast %start : i32 to index
    %10 = arith.addi %9, %8 : index
    %11 = memref.load %1#0[%10] : memref<?xi32>
    memref.dealloc %1#0 : memref<?xi32>
    return %11 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = func.call @checked_returned_view(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
