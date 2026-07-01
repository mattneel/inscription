module {
  func.func @consume_cells(%cells: memref<?xi32>, %cells_length: i32) -> i32 {
    memref.dealloc %cells : memref<?xi32>
    return %cells_length : i32
  }

  func.func @guarded_move(%maybe_tag: i32, %maybe_some_value: i32) -> i32 {
    %0 = arith.constant 4 : i32
    %1 = arith.index_cast %0 : i32 to index
    %2 = memref.alloc(%1) : memref<?xi32>
    %3 = arith.constant 1 : i32
    %4 = arith.constant 0 : index
    %5 = arith.constant 1 : index
    scf.for %6 = %4 to %1 step %5 {
      memref.store %3, %2[%6] : memref<?xi32>
    }
    %7 = arith.constant 0 : i32
    %9 = arith.cmpi eq, %maybe_tag, %3 : i32
    %8 = scf.if %9 -> (i32) {
      %10 = arith.cmpi sgt, %maybe_some_value, %7 : i32
      %11 = scf.if %10 -> (i32) {
        %12 = func.call @consume_cells(%2, %0) : (memref<?xi32>, i32) -> i32
        scf.yield %12 : i32
      } else {
        %14 = arith.constant 1 : i32
        %15 = arith.cmpi eq, %maybe_tag, %14 : i32
        %13 = scf.if %15 -> (i32) {
          %16 = func.call @consume_cells(%2, %0) : (memref<?xi32>, i32) -> i32
          scf.yield %16 : i32
        } else {
          %18 = func.call @consume_cells(%2, %0) : (memref<?xi32>, i32) -> i32
          scf.yield %18 : i32
        }
        scf.yield %13 : i32
      }
      scf.yield %11 : i32
    } else {
      %20 = arith.constant 1 : i32
      %21 = arith.cmpi eq, %maybe_tag, %20 : i32
      %19 = scf.if %21 -> (i32) {
        %22 = func.call @consume_cells(%2, %0) : (memref<?xi32>, i32) -> i32
        scf.yield %22 : i32
      } else {
        %24 = func.call @consume_cells(%2, %0) : (memref<?xi32>, i32) -> i32
        scf.yield %24 : i32
      }
      scf.yield %19 : i32
    }
    return %8 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 1 : i32
    %2 = arith.constant 7 : i32
    %3 = func.call @guarded_move(%1, %2) : (i32, i32) -> i32
    return %3 : i32
  }
}
