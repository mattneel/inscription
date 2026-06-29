module {
  func.func @view_from_view() -> i32 {
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
      %11 = arith.index_cast %10 : i32 to index
      memref.store %10, %0[%11] : memref<6xi32>
    }
    %12 = arith.constant 1 : i32
    %13 = arith.constant 4 : i32
    %14 = memref.cast %0 : memref<6xi32> to memref<?xi32>
    %15 = arith.constant 2 : i32
    %16 = arith.addi %12, %12 : i32
    %17 = arith.constant 0 : index
    %18 = arith.index_cast %15 : i32 to index
    %19 = arith.constant 1 : index
    %21 = scf.for %20 = %17 to %18 step %19 iter_args(%total_iter = %1) -> (i32) {
      %22 = arith.index_cast %20 : index to i32
      %23 = arith.index_cast %22 : i32 to index
      %24 = arith.index_cast %16 : i32 to index
      %25 = arith.addi %24, %23 : index
      %26 = memref.load %14[%25] : memref<?xi32>
      %27 = arith.addi %total_iter, %26 : i32
      scf.yield %27 : i32
    }
    return %21 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @view_from_view() : () -> i32
    return %0 : i32
  }
}
