module {
  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 1 : i32
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<4xi32>
    %3 = arith.constant 2 : i32
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<4xi32>
    %5 = arith.constant 3 : i32
    %6 = arith.constant 2 : index
    memref.store %5, %0[%6] : memref<4xi32>
    %7 = arith.constant 4 : i32
    %8 = arith.constant 3 : index
    memref.store %7, %0[%8] : memref<4xi32>
    %9 = memref.alloca() : memref<4xi32>
    %10 = arith.constant 0 : index
    %11 = arith.constant 4 : index
    %12 = arith.constant 1 : index
    scf.for %13 = %10 to %11 step %12 {
      memref.store %3, %9[%13] : memref<4xi32>
    }
    %14 = arith.constant 0 : index
    %15 = memref.load %0[%14] : memref<4xi32>
    %16 = arith.constant 1 : index
    %17 = memref.load %0[%16] : memref<4xi32>
    %18 = arith.addi %15, %17 : i32
    %19 = arith.constant 2 : index
    %20 = memref.load %9[%19] : memref<4xi32>
    %21 = arith.addi %18, %20 : i32
    return %21 : i32
  }
}
