module {
  func.func @padding_zero() -> i32 {
    %0 = memref.alloca() : memref<6xi8>
    %1 = arith.constant 255 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 6 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<6xi8>
    }
    %6 = arith.constant 1 : i8
    %7 = arith.constant 2 : i16
    %8 = arith.constant 3 : i8
    %9 = arith.constant 0 : index
    memref.store %6, %0[%9] : memref<6xi8>
    %10 = arith.constant 1 : index
    %11 = arith.addi %9, %10 : index
    %12 = arith.constant 0 : i8
    memref.store %12, %0[%11] : memref<6xi8>
    %13 = arith.constant 2 : index
    %14 = arith.addi %9, %13 : index
    %15 = arith.trunci %7 : i16 to i8
    memref.store %15, %0[%14] : memref<6xi8>
    %16 = arith.constant 3 : index
    %17 = arith.addi %9, %16 : index
    %18 = arith.constant 8 : i16
    %19 = arith.shrui %7, %18 : i16
    %20 = arith.trunci %19 : i16 to i8
    memref.store %20, %0[%17] : memref<6xi8>
    %21 = arith.constant 4 : index
    %22 = arith.addi %9, %21 : index
    memref.store %8, %0[%22] : memref<6xi8>
    %23 = arith.constant 5 : index
    %24 = arith.addi %9, %23 : index
    memref.store %12, %0[%24] : memref<6xi8>
    %25 = arith.constant 1 : index
    %26 = memref.load %0[%25] : memref<6xi8>
    %27 = arith.extui %26 : i8 to i32
    return %27 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @padding_zero() : () -> i32
    return %0 : i32
  }
}
