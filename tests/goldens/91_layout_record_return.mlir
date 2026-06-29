module {
  func.func @parse_word(%bytes_base: memref<?xi8>, %bytes_start: i32, %bytes_length: i32) -> i16 {
    %0 = arith.constant 0 : index
    %1 = arith.index_cast %bytes_start : i32 to index
    %2 = arith.addi %1, %0 : index
    %3 = memref.load %bytes_base[%2] : memref<?xi8>
    %4 = arith.extui %3 : i8 to i16
    %5 = arith.constant 1 : index
    %6 = arith.addi %2, %5 : index
    %7 = memref.load %bytes_base[%6] : memref<?xi8>
    %8 = arith.extui %7 : i8 to i16
    %9 = arith.constant 8 : i16
    %10 = arith.shli %8, %9 : i16
    %11 = arith.ori %4, %10 : i16
    return %11 : i16
  }

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<2xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 2 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<2xi8>
    }
    %6 = arith.constant 42 : i8
    %7 = arith.constant 0 : index
    memref.store %6, %0[%7] : memref<2xi8>
    %8 = arith.constant 1 : index
    memref.store %1, %0[%8] : memref<2xi8>
    %9 = memref.cast %0 : memref<2xi8> to memref<?xi8>
    %10 = arith.constant 0 : i32
    %11 = arith.constant 2 : i32
    %12 = func.call @parse_word(%9, %10, %11) : (memref<?xi8>, i32, i32) -> i16
    %13 = arith.extui %12 : i16 to i32
    return %13 : i32
  }
}
