module {
  func.func @main() -> i32 {
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
    %9 = arith.constant 1 : index
    %10 = memref.load %2[%9] : memref<?xi8>
    %11 = arith.cmpi eq, %10, %7 : i8
    %12 = scf.if %11 -> (i32) {
      %13 = arith.constant 7 : i32
      scf.yield %13 : i32
    } else {
      scf.yield %0 : i32
    }
    memref.dealloc %2 : memref<?xi8>
    return %12 : i32
  }
}
