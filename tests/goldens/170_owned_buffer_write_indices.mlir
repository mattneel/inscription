module {
  func.func @owned_write_indices() -> i32 {
    %0 = arith.constant 4 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi32>
    %3 = arith.constant 0 : i32
    %4 = arith.constant 0 : index
    %5 = arith.constant 1 : index
    scf.for %6 = %4 to %1 step %5 {
      memref.store %3, %2[%6] : memref<?xi32>
    }
    %7 = arith.constant 0 : index
    %8 = arith.index_cast %0 : i32 to index
    %9 = arith.constant 1 : index
    scf.for %10 = %7 to %8 step %9 {
      %11 = arith.index_cast %10 : index to i32
      %12 = arith.constant 1 : i32
      %13 = arith.addi %11, %12 : i32
      %14 = arith.index_cast %11 : i32 to index
      memref.store %13, %2[%14] : memref<?xi32>
    }
    %15 = arith.constant 0 : index
    %16 = memref.load %2[%15] : memref<?xi32>
    %17 = arith.constant 1 : index
    %18 = memref.load %2[%17] : memref<?xi32>
    %19 = arith.addi %16, %18 : i32
    %20 = arith.constant 2 : index
    %21 = memref.load %2[%20] : memref<?xi32>
    %22 = arith.addi %19, %21 : i32
    %23 = arith.constant 3 : index
    %24 = memref.load %2[%23] : memref<?xi32>
    %25 = arith.addi %22, %24 : i32
    memref.dealloc %2 : memref<?xi32>
    return %25 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @owned_write_indices() : () -> i32
    return %0 : i32
  }
}
