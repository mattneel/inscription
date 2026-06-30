module {
  func.func @branch_owned(%flag: i1) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = scf.if %flag -> (i32) {
      %2 = arith.constant 4 : i32
      %3 = arith.index_cast %2 : i32 to index
      %4 = memref.alloc(%3) : memref<?xi32>
      %5 = arith.constant 0 : i32
      %6 = arith.constant 0 : index
      %7 = arith.constant 1 : index
      scf.for %8 = %6 to %3 step %7 {
        memref.store %5, %4[%8] : memref<?xi32>
      }
      %9 = arith.constant 7 : i32
      %10 = arith.constant 0 : index
      memref.store %9, %4[%10] : memref<?xi32>
      %11 = arith.constant 0 : index
      %12 = memref.load %4[%11] : memref<?xi32>
      memref.dealloc %4 : memref<?xi32>
      scf.yield %12 : i32
    } else {
      %13 = arith.constant 3 : i32
      scf.yield %13 : i32
    }
    return %1 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant true
    %1 = func.call @branch_owned(%0) : (i1) -> i32
    return %1 : i32
  }
}
