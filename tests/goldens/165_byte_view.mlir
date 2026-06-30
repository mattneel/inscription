module {
  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<6xi8>
    %1 = arith.constant 97 : i8
    %2 = arith.constant 0 : index
    memref.store %1, %0[%2] : memref<6xi8>
    %3 = arith.constant 98 : i8
    %4 = arith.constant 1 : index
    memref.store %3, %0[%4] : memref<6xi8>
    %5 = arith.constant 99 : i8
    %6 = arith.constant 2 : index
    memref.store %5, %0[%6] : memref<6xi8>
    %7 = arith.constant 100 : i8
    %8 = arith.constant 3 : index
    memref.store %7, %0[%8] : memref<6xi8>
    %9 = arith.constant 101 : i8
    %10 = arith.constant 4 : index
    memref.store %9, %0[%10] : memref<6xi8>
    %11 = arith.constant 102 : i8
    %12 = arith.constant 5 : index
    memref.store %11, %0[%12] : memref<6xi8>
    %13 = arith.constant 2 : i32
    %14 = arith.constant 3 : i32
    %15 = memref.cast %0 : memref<6xi8> to memref<?xi8>
    %16 = arith.constant 0 : index
    %17 = arith.index_cast %13 : i32 to index
    %18 = arith.addi %17, %16 : index
    %19 = memref.load %15[%18] : memref<?xi8>
    %20 = arith.extui %19 : i8 to i32
    %21 = arith.constant 2 : index
    %22 = arith.index_cast %13 : i32 to index
    %23 = arith.addi %22, %21 : index
    %24 = memref.load %15[%23] : memref<?xi8>
    %25 = arith.extui %24 : i8 to i32
    %26 = arith.addi %20, %25 : i32
    return %26 : i32
  }
}
