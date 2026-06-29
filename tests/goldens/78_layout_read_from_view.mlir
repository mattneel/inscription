module {
  func.func @layout_read_from_view() -> i32 {
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
    %9 = arith.constant 1 : i32
    %10 = arith.constant 2 : i32
    %11 = memref.cast %0 : memref<4xi8> to memref<?xi8>
    %12 = arith.constant 0 : index
    %13 = arith.index_cast %9 : i32 to index
    %14 = arith.addi %13, %12 : index
    %15 = memref.load %11[%14] : memref<?xi8>
    %16 = arith.extui %15 : i8 to i16
    %17 = arith.constant 1 : index
    %18 = arith.addi %14, %17 : index
    %19 = memref.load %11[%18] : memref<?xi8>
    %20 = arith.extui %19 : i8 to i16
    %21 = arith.constant 8 : i16
    %22 = arith.shli %20, %21 : i16
    %23 = arith.ori %16, %22 : i16
    %24 = arith.extui %23 : i16 to i32
    return %24 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @layout_read_from_view() : () -> i32
    return %0 : i32
  }
}
