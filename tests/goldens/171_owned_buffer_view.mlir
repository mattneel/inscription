module {
  func.func @owned_view_sum() -> i32 {
    %0 = arith.constant 6 : i32
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
    %15 = arith.constant 2 : i32
    %16 = arith.constant 3 : i32
    %17 = arith.constant 0 : index
    %18 = arith.index_cast %16 : i32 to index
    %19 = arith.constant 1 : index
    %21 = scf.for %20 = %17 to %18 step %19 iter_args(%total_iter = %3) -> (i32) {
      %22 = arith.index_cast %20 : index to i32
      %23 = arith.index_cast %22 : i32 to index
      %24 = arith.index_cast %15 : i32 to index
      %25 = arith.addi %24, %23 : index
      %26 = memref.load %2[%25] : memref<?xi32>
      %27 = arith.addi %total_iter, %26 : i32
      scf.yield %27 : i32
    }
    memref.dealloc %2 : memref<?xi32>
    return %21 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @owned_view_sum() : () -> i32
    return %0 : i32
  }
}
