module {
  func.func @make_cells(%count: i32) -> (memref<?xi32>, i32) {
    %0 = arith.index_cast %count : i32 to index
    %1 = memref.alloc(%0) : memref<?xi32>
    %2 = arith.constant 2 : i32
    %3 = arith.constant 0 : index
    %4 = arith.constant 1 : index
    scf.for %5 = %3 to %0 step %4 {
      memref.store %2, %1[%5] : memref<?xi32>
    }
    return %1, %count : memref<?xi32>, i32
  }

  func.func @nested_caller(%flag: i1) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = scf.if %flag -> (i32) {
      %2 = arith.constant 4 : i32
      %3:2 = func.call @make_cells(%2) : (i32) -> (memref<?xi32>, i32)
      memref.dealloc %3#0 : memref<?xi32>
      scf.yield %3#1 : i32
    } else {
      %4 = arith.constant 1 : i32
      scf.yield %4 : i32
    }
    return %1 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant true
    %1 = func.call @nested_caller(%0) : (i1) -> i32
    return %1 : i32
  }
}
