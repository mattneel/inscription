module {
  func.func @checked_loop_owned_view(%start: i32, %count: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.constant 1 : index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%result_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.constant 4 : i32
      %8 = arith.index_cast %7 : i32 to index
      %9 = memref.alloc(%8) : memref<?xi32>
      %10 = arith.constant 0 : i32
      %11 = arith.constant 0 : index
      %12 = arith.constant 1 : index
      scf.for %13 = %11 to %8 step %12 {
        memref.store %10, %9[%13] : memref<?xi32>
      }
      %14 = arith.constant 7 : i32
      %15 = arith.constant 1 : index
      memref.store %14, %9[%15] : memref<?xi32>
      %16 = arith.constant 0 : index
      %17 = arith.index_cast %start : i32 to index
      %18 = arith.addi %17, %16 : index
      %19 = memref.load %9[%18] : memref<?xi32>
      memref.dealloc %9 : memref<?xi32>
      scf.yield %19 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = func.call @checked_loop_owned_view(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
