module {
  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<2xi8>
    %1 = arith.constant 1 : i8
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<2xi8>
    %3 = arith.constant 5 : i8
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<2xi8>
    %5 = arith.constant 0 : index
    %6 = memref.load %0[%5] : memref<2xi8>
    %7 = arith.constant 1 : index
    %8 = arith.addi %5, %7 : index
    %9 = memref.load %0[%8] : memref<2xi8>
    %10 = arith.constant 1 : i8
    %11 = arith.cmpi eq, %6, %10 : i8
    %12 = scf.if %11 -> (i32) {
      %13 = arith.extui %9 : i8 to i32
      scf.yield %13 : i32
    } else {
      %14 = arith.constant 0 : i32
      scf.yield %14 : i32
    }
    return %12 : i32
  }
}
