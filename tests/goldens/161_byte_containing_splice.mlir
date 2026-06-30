module {
  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<6xi8>
    %1 = arith.constant 104 : i8
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<6xi8>
    %3 = arith.constant 101 : i8
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<6xi8>
    %5 = arith.constant 108 : i8
    %6 = arith.constant 2 : index
    memref.store %5, %0[%6] : memref<6xi8>
    %7 = arith.constant 3 : index
    memref.store %5, %0[%7] : memref<6xi8>
    %8 = arith.constant 111 : i8
    %9 = arith.constant 4 : index
    memref.store %8, %0[%9] : memref<6xi8>
    %10 = arith.constant 0 : i8
    %11 = arith.constant 5 : index
    memref.store %10, %0[%11] : memref<6xi8>
    %12 = arith.constant 6 : i32
    return %12 : i32
  }
}
