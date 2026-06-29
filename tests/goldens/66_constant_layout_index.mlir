module {
  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<2xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 2 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<2xi8>
    }
    %6 = arith.constant 42 : i8
    %7 = arith.constant 0 : index
    memref.store %6, %0[%7] : memref<2xi8>
    %8 = arith.constant 1 : index
    memref.store %1, %0[%8] : memref<2xi8>
    %9 = arith.constant 0 : i32
    %10 = arith.index_cast %9 : i32 to index
    %11 = memref.load %0[%10] : memref<2xi8>
    %12 = arith.extui %11 : i8 to i16
    %13 = arith.constant 1 : index
    %14 = arith.addi %10, %13 : index
    %15 = memref.load %0[%14] : memref<2xi8>
    %16 = arith.extui %15 : i8 to i16
    %17 = arith.constant 8 : i16
    %18 = arith.shli %16, %17 : i16
    %19 = arith.ori %12, %18 : i16
    %20 = arith.extui %19 : i16 to i32
    return %20 : i32
  }
}
