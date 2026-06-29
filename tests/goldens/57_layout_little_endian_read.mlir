module {
  func.func @little_endian_read() -> i32 {
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
    %9 = arith.constant 0 : index
    %10 = memref.load %0[%9] : memref<2xi8>
    %11 = arith.extui %10 : i8 to i16
    %12 = arith.constant 1 : index
    %13 = arith.addi %9, %12 : index
    %14 = memref.load %0[%13] : memref<2xi8>
    %15 = arith.extui %14 : i8 to i16
    %16 = arith.constant 8 : i16
    %17 = arith.shli %15, %16 : i16
    %18 = arith.ori %11, %17 : i16
    %19 = arith.extui %18 : i16 to i32
    return %19 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @little_endian_read() : () -> i32
    return %0 : i32
  }
}
