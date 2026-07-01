module {
  func.func @copy_array() -> i32 {
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
    %9 = arith.index_cast %7 : i32 to index
    %10 = memref.alloc(%9) : memref<?xi32>
    %11 = arith.constant 0 : index
    %12 = arith.constant 1 : index
    scf.for %13 = %11 to %9 step %12 {
      %14 = memref.load %0[%13] : memref<4xi32>
      memref.store %14, %10[%13] : memref<?xi32>
    }
    %15 = arith.constant 10 : i32
    %16 = arith.constant 0 : index
    memref.store %15, %10[%16] : memref<?xi32>
    %17 = arith.constant 0 : index
    %18 = memref.load %10[%17] : memref<?xi32>
    %19 = arith.constant 0 : index
    %20 = memref.load %0[%19] : memref<4xi32>
    %21 = arith.addi %18, %20 : i32
    memref.dealloc %10 : memref<?xi32>
    return %21 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @copy_array() : () -> i32
    return %0 : i32
  }
}
