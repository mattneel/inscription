module {
  func.func @parse_header(%bytes: memref<6xi8>) -> i32 {
    %0 = arith.constant 0 : index
    %1 = memref.load %bytes[%0] : memref<6xi8>
    %2 = arith.constant 2 : index
    %3 = arith.addi %0, %2 : index
    %4 = memref.load %bytes[%3] : memref<6xi8>
    %5 = arith.extui %4 : i8 to i16
    %6 = arith.constant 3 : index
    %7 = arith.addi %0, %6 : index
    %8 = memref.load %bytes[%7] : memref<6xi8>
    %9 = arith.extui %8 : i8 to i16
    %10 = arith.constant 8 : i16
    %11 = arith.shli %9, %10 : i16
    %12 = arith.ori %5, %11 : i16
    %13 = arith.constant 4 : index
    %14 = arith.addi %0, %13 : index
    %15 = memref.load %bytes[%14] : memref<6xi8>
    %16 = arith.extui %1 : i8 to i32
    return %16 : i32
  }

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<6xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 6 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<6xi8>
    }
    %6 = arith.constant 7 : i8
    %7 = arith.constant 0 : index
    memref.store %6, %0[%7] : memref<6xi8>
    %8 = func.call @parse_header(%0) : (memref<6xi8>) -> i32
    return %8 : i32
  }
}
