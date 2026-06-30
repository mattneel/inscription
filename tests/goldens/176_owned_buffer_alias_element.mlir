module {
  func.func @main() -> i32 {
    %0 = arith.constant 4 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi8>
    %3 = arith.constant 65 : i8
    %4 = arith.constant 0 : index
    %5 = arith.constant 1 : index
    scf.for %6 = %4 to %1 step %5 {
      memref.store %3, %2[%6] : memref<?xi8>
    }
    %7 = arith.constant 0 : index
    %8 = memref.load %2[%7] : memref<?xi8>
    %9 = arith.extui %8 : i8 to i32
    memref.dealloc %2 : memref<?xi8>
    return %9 : i32
  }
}
