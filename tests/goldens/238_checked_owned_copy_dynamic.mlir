module {
  func.func @checked_copy_dynamic(%start: i32, %count: i32) -> i32 {
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
    %9 = memref.cast %0 : memref<4xi32> to memref<?xi32>
    %10 = arith.index_cast %count : i32 to index
    %11 = memref.alloc(%10) : memref<?xi32>
    %12 = arith.constant 0 : index
    %13 = arith.constant 1 : index
    scf.for %14 = %12 to %10 step %13 {
      %15 = arith.index_cast %start : i32 to index
      %16 = arith.addi %15, %14 : index
      %17 = memref.load %9[%16] : memref<?xi32>
      memref.store %17, %11[%14] : memref<?xi32>
    }
    %18 = arith.constant 0 : index
    %19 = memref.load %11[%18] : memref<?xi32>
    %20 = arith.addi %count, %19 : i32
    memref.dealloc %11 : memref<?xi32>
    return %20 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = func.call @checked_copy_dynamic(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
