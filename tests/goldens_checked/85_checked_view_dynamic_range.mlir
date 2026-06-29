module {
  func.func @checked_dynamic_view(%start: i32, %count: i32) -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 0 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi32>
    }
    %6 = arith.constant 7 : i32
    %7 = arith.constant 1 : index
    memref.store %6, %0[%7] : memref<4xi32>
    %8 = arith.cmpi sge, %start, %1 : i32
    cf.assert %8, "view start check failed at line 4"
    %9 = arith.cmpi sge, %count, %1 : i32
    cf.assert %9, "view count check failed at line 4"
    %10 = arith.constant 4 : i32
    %11 = arith.cmpi sle, %start, %10 : i32
    cf.assert %11, "view start range check failed at line 4"
    %12 = arith.subi %10, %start : i32
    %13 = arith.cmpi sle, %count, %12 : i32
    cf.assert %13, "view count range check failed at line 4"
    %14 = memref.cast %0 : memref<4xi32> to memref<?xi32>
    %15 = arith.constant 0 : index
    %16 = arith.index_cast %start : i32 to index
    %17 = arith.addi %16, %15 : index
    %18 = memref.load %14[%17] : memref<?xi32>
    return %18 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = func.call @checked_dynamic_view(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
