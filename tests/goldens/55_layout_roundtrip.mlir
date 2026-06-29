module {
  func.func @roundtrip() -> i32 {
    %0 = memref.alloca() : memref<6xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 6 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<6xi8>
    }
    %6 = arith.constant 7 : i8
    %7 = arith.constant 9 : i16
    %8 = arith.constant 3 : i8
    %9 = arith.constant 0 : index
    memref.store %6, %0[%9] : memref<6xi8>
    %10 = arith.constant 1 : index
    %11 = arith.addi %9, %10 : index
    memref.store %1, %0[%11] : memref<6xi8>
    %12 = arith.constant 2 : index
    %13 = arith.addi %9, %12 : index
    %14 = arith.trunci %7 : i16 to i8
    memref.store %14, %0[%13] : memref<6xi8>
    %15 = arith.constant 3 : index
    %16 = arith.addi %9, %15 : index
    %17 = arith.constant 8 : i16
    %18 = arith.shrui %7, %17 : i16
    %19 = arith.trunci %18 : i16 to i8
    memref.store %19, %0[%16] : memref<6xi8>
    %20 = arith.constant 4 : index
    %21 = arith.addi %9, %20 : index
    memref.store %8, %0[%21] : memref<6xi8>
    %22 = arith.constant 5 : index
    %23 = arith.addi %9, %22 : index
    memref.store %1, %0[%23] : memref<6xi8>
    %24 = arith.constant 0 : index
    %25 = memref.load %0[%24] : memref<6xi8>
    %26 = arith.constant 2 : index
    %27 = arith.addi %24, %26 : index
    %28 = memref.load %0[%27] : memref<6xi8>
    %29 = arith.extui %28 : i8 to i16
    %30 = arith.constant 3 : index
    %31 = arith.addi %24, %30 : index
    %32 = memref.load %0[%31] : memref<6xi8>
    %33 = arith.extui %32 : i8 to i16
    %34 = arith.shli %33, %17 : i16
    %35 = arith.ori %29, %34 : i16
    %36 = arith.constant 4 : index
    %37 = arith.addi %24, %36 : index
    %38 = memref.load %0[%37] : memref<6xi8>
    %39 = arith.extui %25 : i8 to i32
    %40 = arith.extui %35 : i16 to i32
    %41 = arith.addi %39, %40 : i32
    %42 = arith.extui %38 : i8 to i32
    %43 = arith.addi %41, %42 : i32
    return %43 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @roundtrip() : () -> i32
    return %0 : i32
  }
}
