module {
  func.func @make_bytes() -> (memref<?xi8>, i32) {
    %0 = arith.constant 2 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi8>
    %3 = arith.constant 0 : i8
    %4 = arith.constant 0 : index
    %5 = arith.constant 1 : index
    scf.for %6 = %4 to %1 step %5 {
      memref.store %3, %2[%6] : memref<?xi8>
    }
    %7 = arith.constant 42 : i16
    %8 = arith.constant 0 : index
    %9 = arith.trunci %7 : i16 to i8
    memref.store %9, %2[%8] : memref<?xi8>
    %10 = arith.constant 1 : index
    %11 = arith.addi %8, %10 : index
    %12 = arith.constant 8 : i16
    %13 = arith.shrui %7, %12 : i16
    %14 = arith.trunci %13 : i16 to i8
    memref.store %14, %2[%11] : memref<?xi8>
    return %2, %0 : memref<?xi8>, i32
  }

  func.func @main() -> i32 {
    %0:2 = func.call @make_bytes() : () -> (memref<?xi8>, i32)
    %1 = arith.constant 0 : index
    %2 = memref.load %0#0[%1] : memref<?xi8>
    %3 = arith.extui %2 : i8 to i16
    %4 = arith.constant 1 : index
    %5 = arith.addi %1, %4 : index
    %6 = memref.load %0#0[%5] : memref<?xi8>
    %7 = arith.extui %6 : i8 to i16
    %8 = arith.constant 8 : i16
    %9 = arith.shli %7, %8 : i16
    %10 = arith.ori %3, %9 : i16
    %11 = arith.extui %10 : i16 to i32
    memref.dealloc %0#0 : memref<?xi8>
    return %11 : i32
  }
}
