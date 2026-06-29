module {
  func.func @local_view_sum() -> i32 {
    %0 = memref.alloca() : memref<6xi32>
    %1 = arith.constant 0 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 6 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<6xi32>
    }
    %6 = arith.constant 0 : index
    %7 = arith.constant 6 : index
    %8 = arith.constant 1 : index
    scf.for %9 = %6 to %7 step %8 {
      %10 = arith.index_cast %9 : index to i32
      %11 = arith.constant 1 : i32
      %12 = arith.addi %10, %11 : i32
      %13 = arith.index_cast %10 : i32 to index
      memref.store %12, %0[%13] : memref<6xi32>
    }
    %14 = arith.constant 2 : i32
    %15 = arith.constant 3 : i32
    %16 = memref.cast %0 : memref<6xi32> to memref<?xi32>
    %17 = arith.constant 0 : index
    %18 = arith.index_cast %15 : i32 to index
    %19 = arith.constant 1 : index
    %21 = scf.for %20 = %17 to %18 step %19 iter_args(%total_iter = %1) -> (i32) {
      %22 = arith.index_cast %20 : index to i32
      %23 = arith.index_cast %22 : i32 to index
      %24 = arith.index_cast %14 : i32 to index
      %25 = arith.addi %24, %23 : index
      %26 = memref.load %16[%25] : memref<?xi32>
      %27 = arith.addi %total_iter, %26 : i32
      scf.yield %27 : i32
    }
    return %21 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @local_view_sum() : () -> i32
    return %0 : i32
  }
}
