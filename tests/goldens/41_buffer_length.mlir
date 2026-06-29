module {
  func.func @length_demo(%cells: memref<4xi32>) -> i32 {
    %0 = arith.constant 4 : i32
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = memref.alloca() : memref<4xi32>
    %1 = arith.constant 0 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi32>
    }
    %6 = func.call @length_demo(%0) : (memref<4xi32>) -> i32
    return %6 : i32
  }
}
