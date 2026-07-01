module {
  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<14xi8>
    %1 = arith.constant 104 : i8
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<14xi8>
    %3 = arith.constant 116 : i8
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<14xi8>
    %5 = arith.constant 2 : index
    memref.store %3, %0[%5] : memref<14xi8>
    %6 = arith.constant 112 : i8
    %7 = arith.constant 3 : index
    memref.store %6, %0[%7] : memref<14xi8>
    %8 = arith.constant 58 : i8
    %9 = arith.constant 4 : index
    memref.store %8, %0[%9] : memref<14xi8>
    %10 = arith.constant 47 : i8
    %11 = arith.constant 5 : index
    memref.store %10, %0[%11] : memref<14xi8>
    %12 = arith.constant 6 : index
    memref.store %10, %0[%12] : memref<14xi8>
    %13 = arith.constant 101 : i8
    %14 = arith.constant 7 : index
    memref.store %13, %0[%14] : memref<14xi8>
    %15 = arith.constant 120 : i8
    %16 = arith.constant 8 : index
    memref.store %15, %0[%16] : memref<14xi8>
    %17 = arith.constant 97 : i8
    %18 = arith.constant 9 : index
    memref.store %17, %0[%18] : memref<14xi8>
    %19 = arith.constant 109 : i8
    %20 = arith.constant 10 : index
    memref.store %19, %0[%20] : memref<14xi8>
    %21 = arith.constant 11 : index
    memref.store %6, %0[%21] : memref<14xi8>
    %22 = arith.constant 108 : i8
    %23 = arith.constant 12 : index
    memref.store %22, %0[%23] : memref<14xi8>
    %24 = arith.constant 13 : index
    memref.store %13, %0[%24] : memref<14xi8>
    %25 = arith.constant 14 : i32
    return %25 : i32
  }
}
