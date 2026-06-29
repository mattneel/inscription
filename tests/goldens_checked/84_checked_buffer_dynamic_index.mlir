module {
  func.func @checked_dynamic_buffer_index(%i: i32) -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 0 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi32>
    }
    %6 = arith.constant 1 : i32
    %7 = arith.constant 0 : index
    memref.store %6, %0[%7] : memref<4xi32>
    %8 = arith.constant 2 : i32
    %9 = arith.constant 1 : index
    memref.store %8, %0[%9] : memref<4xi32>
    %10 = arith.constant 3 : i32
    %11 = arith.constant 2 : index
    memref.store %10, %0[%11] : memref<4xi32>
    %12 = arith.constant 4 : i32
    %13 = arith.constant 3 : index
    memref.store %12, %0[%13] : memref<4xi32>
    %14 = arith.index_cast %i : i32 to index
    %15 = arith.constant 0 : index
    %16 = arith.cmpi sge, %14, %15 : index
    cf.assert %16, "storage lower-bound check failed at line 7"
    %17 = arith.constant 4 : index
    %18 = arith.cmpi slt, %14, %17 : index
    cf.assert %18, "storage upper-bound check failed at line 7"
    %19 = memref.load %0[%14] : memref<4xi32>
    return %19 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 2 : i32
    %1 = func.call @checked_dynamic_buffer_index(%0) : (i32) -> i32
    return %1 : i32
  }
}
