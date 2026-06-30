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
    %9 = arith.cmpi sge, %start, %3 : i32
    cf.assert %9, "view start check failed at line 4"
    %10 = arith.cmpi sge, %count, %3 : i32
    cf.assert %10, "view count check failed at line 4"
    %11 = arith.cmpi sle, %start, %0 : i32
    cf.assert %11, "view start range check failed at line 4"
    %12 = arith.subi %0, %start : i32
    %13 = arith.cmpi sle, %count, %12 : i32
    cf.assert %13, "view count range check failed at line 4"
    %14 = arith.constant 0 : index
    %15 = arith.index_cast %start : i32 to index
    %16 = arith.addi %15, %14 : index
    %17 = memref.load %2[%16] : memref<?xi32>
    memref.dealloc %2 : memref<?xi32>
    return %17 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = func.call @checked_owned_view(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
