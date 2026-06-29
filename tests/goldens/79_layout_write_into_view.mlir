module {
  func.func @layout_write_into_view() -> i32 {
    %0 = memref.alloca() : memref<4xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi8>
    }
    %6 = arith.constant 1 : i32
    %7 = arith.constant 2 : i32
    %8 = memref.cast %0 : memref<4xi8> to memref<?xi8>
    %9 = arith.constant 258 : i16
    %10 = arith.constant 0 : index
    %11 = arith.index_cast %6 : i32 to index
    %12 = arith.addi %11, %10 : index
    %13 = arith.trunci %9 : i16 to i8
    memref.store %13, %8[%12] : memref<?xi8>
    %14 = arith.constant 1 : index
    %15 = arith.addi %12, %14 : index
    %16 = arith.constant 8 : i16
    %17 = arith.shrui %9, %16 : i16
    %18 = arith.trunci %17 : i16 to i8
    memref.store %18, %8[%15] : memref<?xi8>
    %19 = arith.constant 1 : index
    %20 = memref.load %0[%19] : memref<4xi8>
    %21 = arith.extui %20 : i8 to i32
    %22 = arith.constant 2 : index
    %23 = memref.load %0[%22] : memref<4xi8>
    %24 = arith.extui %23 : i8 to i32
    %25 = arith.constant 10 : i32
    %26 = arith.muli %24, %25 : i32
    %27 = arith.addi %21, %26 : i32
    return %27 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @layout_write_into_view() : () -> i32
    return %0 : i32
  }
}
