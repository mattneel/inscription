module {
  func.func @word_roundtrip() -> i32 {
    %0 = memref.alloca() : memref<2xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 2 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<2xi8>
    }
    %6 = arith.constant 42 : i16
    %7 = arith.constant 0 : index
    %8 = arith.trunci %6 : i16 to i8
    memref.store %8, %0[%7] : memref<2xi8>
    %9 = arith.constant 1 : index
    %10 = arith.addi %7, %9 : index
    %11 = arith.constant 8 : i16
    %12 = arith.shrui %6, %11 : i16
    %13 = arith.trunci %12 : i16 to i8
    memref.store %13, %0[%10] : memref<2xi8>
    %14 = arith.constant 0 : index
    %15 = memref.load %0[%14] : memref<2xi8>
    %16 = arith.extui %15 : i8 to i16
    %17 = arith.constant 1 : index
    %18 = arith.addi %14, %17 : index
    %19 = memref.load %0[%18] : memref<2xi8>
    %20 = arith.extui %19 : i8 to i16
    %21 = arith.shli %20, %11 : i16
    %22 = arith.ori %16, %21 : i16
    %23 = arith.extui %22 : i16 to i32
    return %23 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @word_roundtrip() : () -> i32
    return %0 : i32
  }
}
