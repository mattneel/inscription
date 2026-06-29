module {
  func.func @filled_buffer_sum() -> i32 {
    %0 = memref.alloca() : memref<5xi32>
    %1 = arith.constant 3 : i32
    %2 = arith.constant 0 : index
    %3 = arith.constant 5 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %2 to %3 step %4 {
      memref.store %1, %0[%5] : memref<5xi32>
    }
    %6 = arith.constant 0 : i32
    %7:2 = scf.while (%total_before = %6, %i_before = %6) : (i32, i32) -> (i32, i32) {
      %8 = arith.constant 5 : i32
      %9 = arith.cmpi slt, %i_before, %8 : i32
      scf.condition(%9) %total_before, %i_before : i32, i32
    } do {
    ^bb0(%total_body: i32, %i_body: i32):
      %10 = arith.index_cast %i_body : i32 to index
      %11 = memref.load %0[%10] : memref<5xi32>
      %12 = arith.addi %total_body, %11 : i32
      %13 = arith.constant 1 : i32
      %14 = arith.addi %i_body, %13 : i32
      scf.yield %12, %14 : i32, i32
    }
    return %7#0 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @filled_buffer_sum() : () -> i32
    return %0 : i32
  }
}
