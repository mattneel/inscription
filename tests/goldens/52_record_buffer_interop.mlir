module {
  func.func @write_offset(%offset_index: i32, %offset_value: i32, %cells: memref<4xi32>) {
    %0 = arith.index_cast %offset_index : i32 to index
    memref.store %offset_value, %cells[%0] : memref<4xi32>
    return
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
    %6 = arith.constant 2 : i32
    %7 = arith.constant 9 : i32
    func.call @write_offset(%6, %7, %0) : (i32, i32, memref<4xi32>) -> ()
    %8 = arith.constant 2 : index
    %9 = memref.load %0[%8] : memref<4xi32>
    return %9 : i32
  }
}
