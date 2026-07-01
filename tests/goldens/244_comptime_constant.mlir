module {
  func.func @square(%x: i32) -> i32 {
    %0 = arith.muli %x, %x : i32
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 16 : i32
    return %0 : i32
  }
}
