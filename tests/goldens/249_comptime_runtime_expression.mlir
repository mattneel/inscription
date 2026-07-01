module {
  func.func @square(%x: i32) -> i32 {
    %0 = arith.muli %x, %x : i32
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 36 : i32
    %1 = arith.constant 6 : i32
    %2 = arith.addi %0, %1 : i32
    return %2 : i32
  }
}
