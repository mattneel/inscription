module {
  func.func @loop_owned() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.constant 4 : index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.constant 2 : i32
      %8 = arith.index_cast %7 : i32 to index
      %9 = memref.alloc(%8) : memref<?xi32>
      %10 = arith.constant 0 : index
      %11 = arith.constant 1 : index
      scf.for %12 = %10 to %8 step %11 {
        memref.store %6, %9[%12] : memref<?xi32>
      }
      %13 = arith.constant 0 : index
      %14 = memref.load %9[%13] : memref<?xi32>
      %15 = arith.addi %total_iter, %14 : i32
      %16 = arith.constant 1 : index
      %17 = memref.load %9[%16] : memref<?xi32>
      %18 = arith.addi %15, %17 : i32
      memref.dealloc %9 : memref<?xi32>
      scf.yield %18 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @loop_owned() : () -> i32
    return %0 : i32
  }
}
