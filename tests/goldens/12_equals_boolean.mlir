module {
  func.func @is_zero(%x: i32) -> i1 {
    %0 = arith.constant 0 : i32
    %1 = arith.cmpi eq, %x, %0 : i32
    return %1 : i1
  }
}
