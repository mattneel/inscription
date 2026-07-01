module {
  func.func @owned_bytes_layout() -> i32 {
    %0 = arith.constant 2 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi8>
    %3 = arith.constant 42 : i8
    %4 = arith.constant 0 : index
    memref.store %3, %2[%4] : memref<?xi8>
    %5 = arith.constant 0 : i8
    %6 = arith.constant 1 : index
    memref.store %5, %2[%6] : memref<?xi8>
    %7 = arith.constant 0 : index
    %8 = memref.load %2[%7] : memref<?xi8>
    %9 = arith.extui %8 : i8 to i16
    %10 = arith.constant 1 : index
    %11 = arith.addi %7, %10 : index
    %12 = memref.load %2[%11] : memref<?xi8>
    %13 = arith.extui %12 : i8 to i16
    %14 = arith.constant 8 : i16
    %15 = arith.shli %13, %14 : i16
    %16 = arith.ori %9, %15 : i16
    %17 = arith.extui %16 : i16 to i32
    memref.dealloc %2 : memref<?xi8>
    return %17 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @owned_bytes_layout() : () -> i32
    return %0 : i32
  }
}
