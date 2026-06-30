module {
  func.func @while_owned() -> i32 {
    %0 = arith.constant 0 : i32
    %1:2 = scf.while (%total_before = %0, %i_before = %0) : (i32, i32) -> (i32, i32) {
      %2 = arith.constant 4 : i32
      %3 = arith.cmpi slt, %i_before, %2 : i32
      scf.condition(%3) %total_before, %i_before : i32, i32
    } do {
    ^bb0(%total_body: i32, %i_body: i32):
      %4 = arith.constant 2 : i32
      %5 = arith.index_cast %4 : i32 to index
      %6 = memref.alloc(%5) : memref<?xi32>
      %7 = arith.constant 0 : index
      %8 = arith.constant 1 : index
      scf.for %9 = %7 to %5 step %8 {
        memref.store %i_body, %6[%9] : memref<?xi32>
      }
      %10 = arith.constant 0 : index
      %11 = memref.load %6[%10] : memref<?xi32>
      %12 = arith.addi %total_body, %11 : i32
      %13 = arith.constant 1 : index
      %14 = memref.load %6[%13] : memref<?xi32>
      %15 = arith.addi %12, %14 : i32
      %16 = arith.constant 1 : i32
      %17 = arith.addi %i_body, %16 : i32
      memref.dealloc %6 : memref<?xi32>
      scf.yield %15, %17 : i32, i32
    }
    return %1#0 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @while_owned() : () -> i32
    return %0 : i32
  }
}
