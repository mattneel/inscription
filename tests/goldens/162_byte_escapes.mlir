module {
  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<2xi8>
    %1 = arith.constant 65 : i8
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<2xi8>
    %3 = arith.constant 10 : i8
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<2xi8>
    %5 = arith.constant 0 : index
    %6 = memref.load %0[%5] : memref<2xi8>
    %7 = arith.extui %6 : i8 to i32
    %8 = arith.constant 1 : index
    %9 = memref.load %0[%8] : memref<2xi8>
    %10 = arith.extui %9 : i8 to i32
    %11 = arith.addi %7, %10 : i32
    return %11 : i32
  }
}
