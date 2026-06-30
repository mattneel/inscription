module {
  func.func @make_modes() -> (memref<?xi8>, i32) {
    %0 = arith.constant 3 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi8>
    %3 = arith.constant 0 : i8
    %4 = arith.constant 0 : index
    %5 = arith.constant 1 : index
    scf.for %6 = %4 to %1 step %5 {
      memref.store %3, %2[%6] : memref<?xi8>
    }
    %7 = arith.constant 1 : i8
    %8 = arith.constant 1 : index
    memref.store %7, %2[%8] : memref<?xi8>
    return %2, %0 : memref<?xi8>, i32
  }

  func.func @main() -> i32 {
    %0:2 = func.call @make_modes() : () -> (memref<?xi8>, i32)
    %1 = arith.constant 1 : index
    %2 = memref.load %0#0[%1] : memref<?xi8>
    %3 = arith.constant 1 : i8
    %4 = arith.cmpi eq, %2, %3 : i8
    %5 = scf.if %4 -> (i32) {
      %6 = arith.constant 7 : i32
      scf.yield %6 : i32
    } else {
      %7 = arith.constant 3 : i32
      scf.yield %7 : i32
    }
    memref.dealloc %0#0 : memref<?xi8>
    return %5 : i32
  }
}
