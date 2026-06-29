module {
  func.func @swap_endpoints() -> i32 {
    %0 = memref.alloca() : memref<3xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 3 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<3xi8>
    }
    %6 = arith.constant 7 : i8
    %7 = arith.constant 0 : index
    memref.store %6, %0[%7] : memref<3xi8>
    %8 = arith.constant 9 : i8
    %9 = arith.constant 2 : index
    memref.store %8, %0[%9] : memref<3xi8>
    %10 = arith.constant 0 : index
    %11 = memref.load %0[%10] : memref<3xi8>
    %12 = arith.constant 2 : index
    %13 = memref.load %0[%12] : memref<3xi8>
    %14 = arith.constant 0 : index
    memref.store %13, %0[%14] : memref<3xi8>
    %15 = arith.constant 2 : index
    memref.store %11, %0[%15] : memref<3xi8>
    %16 = arith.constant 0 : index
    %17 = memref.load %0[%16] : memref<3xi8>
    %18 = arith.extui %17 : i8 to i32
    %19 = arith.constant 2 : index
    %20 = memref.load %0[%19] : memref<3xi8>
    %21 = arith.extui %20 : i8 to i32
    %22 = arith.addi %18, %21 : i32
    return %22 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @swap_endpoints() : () -> i32
    return %0 : i32
  }
}
