module {
  func.func @sum_buffer(%cells: memref<4xi32>) -> i32 {
    %0 = arith.constant 0 : i32
    %1:2 = scf.while (%total_before = %0, %i_before = %0) : (i32, i32) -> (i32, i32) {
      %2 = arith.constant 4 : i32
      %3 = arith.cmpi slt, %i_before, %2 : i32
      scf.condition(%3) %total_before, %i_before : i32, i32
    } do {
    ^bb0(%total_body: i32, %i_body: i32):
      %4 = arith.index_cast %i_body : i32 to index
      %5 = memref.load %cells[%4] : memref<4xi32>
      %6 = arith.addi %total_body, %5 : i32
      %7 = arith.constant 1 : i32
      %8 = arith.addi %i_body, %7 : i32
      scf.yield %6, %8 : i32, i32
    }
    return %1#0 : i32
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
    %6 = arith.constant 1 : i32
    %7 = arith.constant 0 : index
    memref.store %6, %0[%7] : memref<4xi32>
    %8 = arith.constant 2 : i32
    %9 = arith.constant 1 : index
    memref.store %8, %0[%9] : memref<4xi32>
    %10 = arith.constant 3 : i32
    %11 = arith.constant 2 : index
    memref.store %10, %0[%11] : memref<4xi32>
    %12 = arith.constant 4 : i32
    %13 = arith.constant 3 : index
    memref.store %12, %0[%13] : memref<4xi32>
    %14 = func.call @sum_buffer(%0) : (memref<4xi32>) -> i32
    return %14 : i32
  }
}
