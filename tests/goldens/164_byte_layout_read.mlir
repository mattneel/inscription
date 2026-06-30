module {
  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<2xi8>
    %1 = arith.constant 42 : i8
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<2xi8>
    %3 = arith.constant 0 : i8
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<2xi8>
    %5 = arith.constant 0 : index
    %6 = memref.load %0[%5] : memref<2xi8>
    %7 = arith.extui %6 : i8 to i16
    %8 = arith.constant 1 : index
    %9 = arith.addi %5, %8 : index
    %10 = memref.load %0[%9] : memref<2xi8>
    %11 = arith.extui %10 : i8 to i16
    %12 = arith.constant 8 : i16
    %13 = arith.shli %11, %12 : i16
    %14 = arith.ori %7, %13 : i16
    %15 = arith.extui %14 : i16 to i32
    return %15 : i32
  }
}
