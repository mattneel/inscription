module {
  func.func @sum_buffer_each(%cells: memref<4xi32>) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.constant 4 : index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.index_cast %6 : i32 to index
      %8 = memref.load %cells[%7] : memref<4xi32>
      %9 = arith.addi %total_iter, %8 : i32
      scf.yield %9 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 0 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi32>
    }
    %6 = arith.constant 1 : i32
    %7 = arith.constant 0 : index
    memref.store %6, %0[%7] : memref<4xi32>
    %8 = arith.constant 2 : i32
    %9 = arith.constant 1 : index
    memref.store %8, %0[%9] : memref<4xi32>
    %10 = arith.constant 3 : i32
    %11 = arith.constant 2 : index
    memref.store %10, %0[%11] : memref<4xi32>
    %12 = arith.constant 4 : i32
    %13 = arith.constant 3 : index
    memref.store %12, %0[%13] : memref<4xi32>
    %14 = func.call @sum_buffer_each(%0) : (memref<4xi32>) -> i32
    return %14 : i32
  }
}
