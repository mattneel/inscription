module {
  func.func @array_view_sum() -> i32 {
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
    %14 = arith.constant 0 : i32
    %15 = arith.constant 0 : index
    %16 = arith.index_cast %5 : i32 to index
    %17 = arith.constant 1 : index
    %19 = scf.for %18 = %15 to %16 step %17 iter_args(%total_iter = %14) -> (i32) {
      %20 = arith.index_cast %18 : index to i32
      %21 = arith.index_cast %20 : i32 to index
      %22 = arith.index_cast %3 : i32 to index
      %23 = arith.addi %22, %21 : index
      %24 = memref.load %13[%23] : memref<?xi32>
      %25 = arith.addi %total_iter, %24 : i32
      scf.yield %25 : i32
    }
    return %19 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @array_view_sum() : () -> i32
    return %0 : i32
  }
}
