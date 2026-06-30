module {
  func.func @make_maybe_from_owned() -> (i32, i32) {
    %0 = arith.constant 1 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi32>
    %3 = arith.constant 7 : i32
    %4 = arith.constant 0 : index
    %5 = arith.constant 1 : index
    scf.for %6 = %4 to %1 step %5 {
      memref.store %3, %2[%6] : memref<?xi32>
    }
    %7 = arith.constant 0 : i32
    %8 = arith.constant 0 : index
    %9 = memref.load %2[%8] : memref<?xi32>
    memref.dealloc %2 : memref<?xi32>
    return %0, %9 : i32, i32
  }

  func.func @main() -> i32 {
    %0:2 = func.call @make_maybe_from_owned() : () -> (i32, i32)
    %1 = arith.constant 1 : i32
    %2 = arith.cmpi eq, %0#0, %1 : i32
    %3 = scf.if %2 -> (i32) {
      scf.yield %0#1 : i32
    } else {
      %4 = arith.constant 0 : i32
      scf.yield %4 : i32
    }
    return %3 : i32
  }
}
