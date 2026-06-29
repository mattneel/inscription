module {
  func.func @write_indices() -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 0 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi32>
    }
    %6 = scf.while (%i_before = %1) : (i32) -> i32 {
      %7 = arith.constant 4 : i32
      %8 = arith.cmpi slt, %i_before, %7 : i32
      scf.condition(%8) %i_before : i32
    } do {
    ^bb0(%i_body: i32):
      %9 = arith.constant 1 : i32
      %10 = arith.addi %i_body, %9 : i32
      %11 = arith.index_cast %i_body : i32 to index
      memref.store %10, %0[%11] : memref<4xi32>
      %12 = arith.addi %i_body, %9 : i32
      scf.yield %12 : i32
    }
    %13 = arith.constant 0 : index
    %14 = memref.load %0[%13] : memref<4xi32>
    %15 = arith.constant 1 : index
    %16 = memref.load %0[%15] : memref<4xi32>
    %17 = arith.addi %14, %16 : i32
    %18 = arith.constant 2 : index
    %19 = memref.load %0[%18] : memref<4xi32>
    %20 = arith.addi %17, %19 : i32
    %21 = arith.constant 3 : index
    %22 = memref.load %0[%21] : memref<4xi32>
    %23 = arith.addi %20, %22 : i32
    return %23 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @write_indices() : () -> i32
    return %0 : i32
  }
}
