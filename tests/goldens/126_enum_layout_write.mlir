module {
  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<2xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 2 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<2xi8>
    }
    %6 = arith.constant 1 : i8
    %7 = arith.constant 9 : i8
    %8 = arith.constant 0 : index
    memref.store %6, %0[%8] : memref<2xi8>
    %9 = arith.constant 1 : index
    %10 = arith.addi %8, %9 : index
    memref.store %7, %0[%10] : memref<2xi8>
    %11 = arith.constant 0 : index
    %12 = memref.load %0[%11] : memref<2xi8>
    %13 = arith.extui %12 : i8 to i32
    %14 = arith.constant 1 : index
    %15 = memref.load %0[%14] : memref<2xi8>
    %16 = arith.extui %15 : i8 to i32
    %17 = arith.addi %13, %16 : i32
    return %17 : i32
  }
}
