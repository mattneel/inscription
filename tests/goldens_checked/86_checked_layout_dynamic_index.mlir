module {
  func.func @checked_dynamic_layout_index(%start: i32) -> i32 {
    %0 = memref.alloca() : memref<4xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi8>
    }
    %6 = arith.constant 42 : i8
    %7 = arith.constant 1 : index
    memref.store %6, %0[%7] : memref<4xi8>
    %8 = arith.constant 2 : index
    memref.store %1, %0[%8] : memref<4xi8>
    %9 = arith.index_cast %start : i32 to index
    %10 = arith.constant 0 : index
    %11 = arith.cmpi sge, %9, %10 : index
    cf.assert %11, "storage lower-bound check failed at line 7"
    %12 = arith.constant 4 : index
    %13 = arith.constant 2 : index
    %14 = arith.subi %12, %13 : index
    %15 = arith.cmpi sle, %9, %14 : index
    cf.assert %15, "storage range check failed at line 7"
    %16 = memref.load %0[%9] : memref<4xi8>
    %17 = arith.extui %16 : i8 to i16
    %18 = arith.constant 1 : index
    %19 = arith.addi %9, %18 : index
    %20 = memref.load %0[%19] : memref<4xi8>
    %21 = arith.extui %20 : i8 to i16
    %22 = arith.constant 8 : i16
    %23 = arith.shli %21, %22 : i16
    %24 = arith.ori %17, %23 : i16
    %25 = arith.extui %24 : i16 to i32
    return %25 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = func.call @checked_dynamic_layout_index(%0) : (i32) -> i32
    return %1 : i32
  }
}
