module {
  func.func @branch_store(%flag: i1) -> i32 {
    %0 = memref.alloca() : memref<1xi32>
    %1 = arith.constant 0 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 1 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<1xi32>
    }
    scf.if %flag {
      %6 = arith.constant 7 : i32
      %7 = arith.constant 0 : index
      memref.store %6, %0[%7] : memref<1xi32>
      scf.yield
    } else {
      %8 = arith.constant 3 : i32
      %9 = arith.constant 0 : index
      memref.store %8, %0[%9] : memref<1xi32>
      scf.yield
    }
    %10 = arith.constant 0 : index
    %11 = memref.load %0[%10] : memref<1xi32>
    return %11 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant true
    %1 = func.call @branch_store(%0) : (i1) -> i32
    return %1 : i32
  }
}
