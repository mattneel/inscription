module {
  func.func @checked_copy_dynamic(%start: i32, %count: i32) -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 1 : i32
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<4xi32>
    %3 = arith.constant 2 : i32
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<4xi32>
    %5 = arith.constant 3 : i32
    %6 = arith.constant 2 : index
    memref.store %5, %0[%6] : memref<4xi32>
    %7 = arith.constant 4 : i32
    %8 = arith.constant 3 : index
    memref.store %7, %0[%8] : memref<4xi32>
    %9 = arith.constant 0 : i32
    %10 = arith.cmpi sge, %start, %9 : i32
    cf.assert %10, "view start check failed at line 3"
    %11 = arith.cmpi sge, %count, %9 : i32
    cf.assert %11, "view count check failed at line 3"
    %12 = arith.cmpi sle, %start, %7 : i32
    cf.assert %12, "view start range check failed at line 3"
    %13 = arith.subi %7, %start : i32
    %14 = arith.cmpi sle, %count, %13 : i32
    cf.assert %14, "view count range check failed at line 3"
    %15 = memref.cast %0 : memref<4xi32> to memref<?xi32>
    %16 = arith.cmpi sge, %count, %1 : i32
    cf.assert %16, "owned buffer copy length check failed at line 4"
    %17 = arith.index_cast %count : i32 to index
    %18 = memref.alloc(%17) : memref<?xi32>
    %19 = arith.constant 0 : index
    %20 = arith.constant 1 : index
    scf.for %21 = %19 to %17 step %20 {
      %22 = arith.index_cast %start : i32 to index
      %23 = arith.addi %22, %21 : index
      %24 = memref.load %15[%23] : memref<?xi32>
      memref.store %24, %18[%21] : memref<?xi32>
    }
    %25 = arith.constant 0 : index
    %26 = memref.load %18[%25] : memref<?xi32>
    %27 = arith.addi %count, %26 : i32
    memref.dealloc %18 : memref<?xi32>
    return %27 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = func.call @checked_copy_dynamic(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
