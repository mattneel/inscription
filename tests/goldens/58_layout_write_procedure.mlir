module {
  func.func @write_pair(%pair_left: i8, %pair_right: i8, %bytes: memref<2xi8>) {
    %0 = arith.constant 0 : index
    memref.store %pair_left, %bytes[%0] : memref<2xi8>
    %1 = arith.constant 1 : index
    %2 = arith.addi %0, %1 : index
    memref.store %pair_right, %bytes[%2] : memref<2xi8>
    return
  }

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<2xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 2 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<2xi8>
    }
    %6 = arith.constant 5 : i8
    %7 = arith.constant 6 : i8
    func.call @write_pair(%6, %7, %0) : (i8, i8, memref<2xi8>) -> ()
    %8 = arith.constant 0 : index
    %9 = memref.load %0[%8] : memref<2xi8>
    %10 = arith.extui %9 : i8 to i32
    %11 = arith.constant 1 : index
    %12 = memref.load %0[%11] : memref<2xi8>
    %13 = arith.extui %12 : i8 to i32
    %14 = arith.addi %10, %13 : i32
    return %14 : i32
  }
}
