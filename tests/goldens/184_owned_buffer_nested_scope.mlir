module {
  func.func @nested_owned(%flag: i1) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = scf.if %flag -> (i32) {
      %2 = arith.constant 0 : index
      %3 = arith.constant 3 : index
      %4 = arith.constant 1 : index
      %6 = scf.for %5 = %2 to %3 step %4 iter_args(%result_iter = %0) -> (i32) {
        %7 = arith.index_cast %5 : index to i32
        %8 = arith.constant 2 : i32
        %9 = arith.index_cast %8 : i32 to index
        %10 = memref.alloc(%9) : memref<?xi32>
        %11 = arith.constant 0 : index
        %12 = arith.constant 1 : index
        scf.for %13 = %11 to %9 step %12 {
          memref.store %7, %10[%13] : memref<?xi32>
        }
        %14 = arith.constant 0 : index
        %15 = memref.load %10[%14] : memref<?xi32>
        %16 = arith.addi %result_iter, %15 : i32
        %17 = arith.constant 1 : index
        %18 = memref.load %10[%17] : memref<?xi32>
        %19 = arith.addi %16, %18 : i32
        memref.dealloc %10 : memref<?xi32>
        scf.yield %19 : i32
      }
      scf.yield %6 : i32
    } else {
      %20 = arith.constant 1 : i32
      scf.yield %20 : i32
    }
    return %1 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant true
    %1 = func.call @nested_owned(%0) : (i1) -> i32
    return %1 : i32
  }
}
