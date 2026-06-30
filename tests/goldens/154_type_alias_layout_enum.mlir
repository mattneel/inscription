module {
  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<3xi8>
    %1 = arith.constant 1 : i8
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<3xi8>
    %3 = arith.constant 42 : i8
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<3xi8>
    %5 = arith.constant 0 : i8
    %6 = arith.constant 2 : index
    memref.store %5, %0[%6] : memref<3xi8>
    %7 = arith.constant 0 : index
    %8 = memref.load %0[%7] : memref<3xi8>
    %9 = arith.constant 1 : index
    %10 = arith.addi %7, %9 : index
    %11 = memref.load %0[%10] : memref<3xi8>
    %12 = arith.extui %11 : i8 to i16
    %13 = arith.constant 2 : index
    %14 = arith.addi %7, %13 : index
    %15 = memref.load %0[%14] : memref<3xi8>
    %16 = arith.extui %15 : i8 to i16
    %17 = arith.constant 8 : i16
    %18 = arith.shli %16, %17 : i16
    %19 = arith.ori %12, %18 : i16
    %20 = arith.constant 1 : i8
    %21 = arith.cmpi eq, %8, %20 : i8
    %22 = scf.if %21 -> (i32) {
      %23 = arith.extui %19 : i16 to i32
      scf.yield %23 : i32
    } else {
      %24 = arith.constant 0 : i32
      scf.yield %24 : i32
    }
    return %22 : i32
  }
}
