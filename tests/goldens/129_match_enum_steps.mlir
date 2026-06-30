module {
  func.func @count_active_modes(%modes_base: memref<?xi8>, %modes_start: i32, %modes_length: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.index_cast %modes_length : i32 to index
    %3 = arith.constant 1 : index
    %5:2 = scf.for %4 = %1 to %2 step %3 iter_args(%active_iter = %0, %failed_iter = %0) -> (i32, i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.index_cast %6 : i32 to index
      %8 = arith.index_cast %modes_start : i32 to index
      %9 = arith.addi %8, %7 : index
      %10 = memref.load %modes_base[%9] : memref<?xi8>
      %12 = arith.constant 1 : i8
      %13 = arith.cmpi eq, %10, %12 : i8
      %11:2 = scf.if %13 -> (i32, i32) {
        %14 = arith.constant 1 : i32
        %15 = arith.addi %active_iter, %14 : i32
        scf.yield %15, %failed_iter : i32, i32
      } else {
        %17 = arith.constant 2 : i8
        %18 = arith.cmpi eq, %10, %17 : i8
        %16:2 = scf.if %18 -> (i32, i32) {
          %19 = arith.constant 1 : i32
          %20 = arith.addi %failed_iter, %19 : i32
          scf.yield %active_iter, %20 : i32, i32
        } else {
          scf.yield %active_iter, %failed_iter : i32, i32
        }
        scf.yield %16#0, %16#1 : i32, i32
      }
      scf.yield %11#0, %11#1 : i32, i32
    }
    %21 = arith.addi %5#0, %5#1 : i32
    return %21 : i32
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
