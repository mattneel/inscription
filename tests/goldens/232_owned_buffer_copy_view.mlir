module {
  func.func @copy_view() -> i32 {
    %0 = memref.alloca() : memref<6xi32>
    %1 = arith.constant 1 : i32
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<6xi32>
    %3 = arith.constant 2 : i32
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<6xi32>
    %5 = arith.constant 3 : i32
    %6 = arith.constant 2 : index
    memref.store %5, %0[%6] : memref<6xi32>
    %7 = arith.constant 4 : i32
    %8 = arith.constant 3 : index
    memref.store %7, %0[%8] : memref<6xi32>
    %9 = arith.constant 5 : i32
    %10 = arith.constant 4 : index
    memref.store %9, %0[%10] : memref<6xi32>
    %11 = arith.constant 6 : i32
    %12 = arith.constant 5 : index
    memref.store %11, %0[%12] : memref<6xi32>
    %13 = memref.cast %0 : memref<6xi32> to memref<?xi32>
    %14 = arith.index_cast %5 : i32 to index
    %15 = memref.alloc(%14) : memref<?xi32>
    %16 = arith.constant 0 : index
    %17 = arith.constant 1 : index
    scf.for %18 = %16 to %14 step %17 {
      %19 = arith.index_cast %3 : i32 to index
      %20 = arith.addi %19, %18 : index
      %21 = memref.load %13[%20] : memref<?xi32>
      memref.store %21, %15[%18] : memref<?xi32>
    }
    %22 = arith.constant 0 : index
    %23 = memref.load %15[%22] : memref<?xi32>
    %24 = arith.constant 1 : index
    %25 = memref.load %15[%24] : memref<?xi32>
    %26 = arith.addi %23, %25 : i32
    %27 = arith.constant 2 : index
    %28 = memref.load %15[%27] : memref<?xi32>
    %29 = arith.addi %26, %28 : i32
    memref.dealloc %15 : memref<?xi32>
    return %29 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @copy_view() : () -> i32
    return %0 : i32
  }
}
