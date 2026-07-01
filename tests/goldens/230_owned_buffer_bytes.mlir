module {
  func.func @owned_bytes_length() -> i32 {
    %0 = arith.constant 5 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi8>
    %3 = arith.constant 104 : i8
    %4 = arith.constant 0 : index
    memref.store %3, %2[%4] : memref<?xi8>
    %5 = arith.constant 101 : i8
    %6 = arith.constant 1 : index
    memref.store %5, %2[%6] : memref<?xi8>
    %7 = arith.constant 108 : i8
    %8 = arith.constant 2 : index
    memref.store %7, %2[%8] : memref<?xi8>
    %9 = arith.constant 3 : index
    memref.store %7, %2[%9] : memref<?xi8>
    %10 = arith.constant 111 : i8
    %11 = arith.constant 4 : index
    memref.store %10, %2[%11] : memref<?xi8>
    memref.dealloc %2 : memref<?xi8>
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @owned_bytes_length() : () -> i32
    return %0 : i32
  }
}
