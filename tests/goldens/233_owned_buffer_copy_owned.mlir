module {
  func.func @copy_owned() -> i32 {
    %0 = arith.constant 4 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi32>
    %3 = arith.constant 1 : i32
    %4 = arith.constant 0 : index
    memref.store %3, %2[%4] : memref<?xi32>
    %5 = arith.constant 2 : i32
    %6 = arith.constant 1 : index
    memref.store %5, %2[%6] : memref<?xi32>
    %7 = arith.constant 3 : i32
    %8 = arith.constant 2 : index
    memref.store %7, %2[%8] : memref<?xi32>
    %9 = arith.constant 3 : index
    memref.store %0, %2[%9] : memref<?xi32>
    %10 = arith.index_cast %0 : i32 to index
    %11 = memref.alloc(%10) : memref<?xi32>
    %12 = arith.constant 0 : index
    %13 = arith.constant 1 : index
    scf.for %14 = %12 to %10 step %13 {
      %15 = memref.load %2[%14] : memref<?xi32>
      memref.store %15, %11[%14] : memref<?xi32>
    }
    %16 = arith.constant 10 : i32
    %17 = arith.constant 0 : index
    memref.store %16, %11[%17] : memref<?xi32>
    %18 = arith.constant 0 : index
    %19 = memref.load %2[%18] : memref<?xi32>
    %20 = arith.constant 0 : index
    %21 = memref.load %11[%20] : memref<?xi32>
    %22 = arith.addi %19, %21 : i32
    memref.dealloc %11 : memref<?xi32>
    memref.dealloc %2 : memref<?xi32>
    return %22 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @copy_owned() : () -> i32
    return %0 : i32
  }
}
