module {
  func.func @owned_layout_roundtrip() -> i32 {
    %0 = arith.constant 2 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi8>
    %3 = arith.constant 0 : i8
    %4 = arith.constant 0 : index
    %5 = arith.constant 1 : index
    scf.for %6 = %4 to %1 step %5 {
      memref.store %3, %2[%6] : memref<?xi8>
    }
    %7 = arith.constant 42 : i16
    %8 = arith.constant 0 : index
    %9 = arith.trunci %7 : i16 to i8
    memref.store %9, %2[%8] : memref<?xi8>
    %10 = arith.constant 1 : index
    %11 = arith.addi %8, %10 : index
    %12 = arith.constant 8 : i16
    %13 = arith.shrui %7, %12 : i16
    %14 = arith.trunci %13 : i16 to i8
    memref.store %14, %2[%11] : memref<?xi8>
    %15 = arith.constant 0 : index
    %16 = memref.load %2[%15] : memref<?xi8>
    %17 = arith.extui %16 : i8 to i16
    %18 = arith.constant 1 : index
    %19 = arith.addi %15, %18 : index
    %20 = memref.load %2[%19] : memref<?xi8>
    %21 = arith.extui %20 : i8 to i16
    %22 = arith.shli %21, %12 : i16
    %23 = arith.ori %17, %22 : i16
    %24 = arith.extui %23 : i16 to i32
    memref.dealloc %2 : memref<?xi8>
    return %24 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @owned_layout_roundtrip() : () -> i32
    return %0 : i32
  }
}
