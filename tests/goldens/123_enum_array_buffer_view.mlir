module {
  func.func @count_active_modes(%modes_base: memref<?xi8>, %modes_start: i32, %modes_length: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.index_cast %modes_length : i32 to index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%total_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.index_cast %6 : i32 to index
      %8 = arith.index_cast %modes_start : i32 to index
      %9 = arith.addi %8, %7 : index
      %10 = memref.load %modes_base[%9] : memref<?xi8>
      %11 = arith.constant 1 : i8
      %12 = arith.cmpi eq, %10, %11 : i8
      %13 = scf.if %12 -> (i32) {
        %14 = arith.constant 1 : i32
        %15 = arith.addi %total_iter, %14 : i32
        scf.yield %15 : i32
      } else {
        scf.yield %total_iter : i32
      }
      scf.yield %13 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<4xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<4xi8>
    %3 = arith.constant 1 : i8
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<4xi8>
    %5 = arith.constant 2 : i8
    %6 = arith.constant 2 : index
    memref.store %5, %0[%6] : memref<4xi8>
    %7 = arith.constant 3 : index
    memref.store %3, %0[%7] : memref<4xi8>
    %8 = memref.cast %0 : memref<4xi8> to memref<?xi8>
    %9 = arith.constant 0 : i32
    %10 = arith.constant 4 : i32
    %11 = func.call @count_active_modes(%8, %9, %10) : (memref<?xi8>, i32, i32) -> i32
    return %11 : i32
  }
}
