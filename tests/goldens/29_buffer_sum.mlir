module {
  func.func @buffer_sum() -> i32 {
    %0 = memref.alloca() : memref<4xi8>
    %1 = arith.constant 0 : i8
    %2 = arith.constant 0 : index
    %3 = arith.constant 4 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<4xi8>
    }
    %6 = arith.constant 10 : i8
    %7 = arith.constant 0 : index
    memref.store %6, %0[%7] : memref<4xi8>
    %8 = arith.constant 20 : i8
    %9 = arith.constant 1 : index
    memref.store %8, %0[%9] : memref<4xi8>
    %10 = arith.constant 30 : i8
    %11 = arith.constant 2 : index
    memref.store %10, %0[%11] : memref<4xi8>
    %12 = arith.constant 40 : i8
    %13 = arith.constant 3 : index
    memref.store %12, %0[%13] : memref<4xi8>
    %14 = arith.constant 0 : i32
    %15:2 = scf.while (%total_before = %14, %i_before = %14) : (i32, i32) -> (i32, i32) {
      %16 = arith.constant 4 : i32
      %17 = arith.cmpi slt, %i_before, %16 : i32
      scf.condition(%17) %total_before, %i_before : i32, i32
    } do {
    ^bb0(%total_body: i32, %i_body: i32):
      %18 = arith.index_cast %i_body : i32 to index
      %19 = memref.load %0[%18] : memref<4xi8>
      %20 = arith.extui %19 : i8 to i32
      %21 = arith.addi %total_body, %20 : i32
      %22 = arith.constant 1 : i32
      %23 = arith.addi %i_body, %22 : i32
      scf.yield %21, %23 : i32, i32
    }
    return %15#0 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @buffer_sum() : () -> i32
    return %0 : i32
  }
}
