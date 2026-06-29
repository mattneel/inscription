module {
  func.func @read_word_checked(%bytes_base: memref<?xi8>, %bytes_start: i32, %bytes_length: i32) -> i32 {
    %0 = arith.constant 2 : i32
    %1 = arith.cmpi sge, %bytes_length, %0 : i32
    cf.assert %1, "require failed at line 5"
    %2 = arith.constant 0 : index
    %3 = arith.index_cast %bytes_start : i32 to index
    %4 = arith.addi %3, %2 : index
    %5 = memref.load %bytes_base[%4] : memref<?xi8>
    %6 = arith.extui %5 : i8 to i16
    %7 = arith.constant 1 : index
    %8 = arith.addi %4, %7 : index
    %9 = memref.load %bytes_base[%8] : memref<?xi8>
    %10 = arith.extui %9 : i8 to i16
    %11 = arith.constant 8 : i16
    %12 = arith.shli %10, %11 : i16
    %13 = arith.ori %6, %12 : i16
    %14 = arith.extui %13 : i16 to i32
    return %14 : i32
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
    %8 = memref.cast %0 : memref<2xi8> to memref<?xi8>
    %9 = arith.constant 0 : i32
    %10 = arith.constant 2 : i32
    %11 = func.call @read_word_checked(%8, %9, %10) : (memref<?xi8>, i32, i32) -> i32
    return %11 : i32
  }
}
