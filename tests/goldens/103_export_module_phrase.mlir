module {
  func.func @ins_square(%x: i32) -> i32 {
    %0 = arith.muli %x, %x : i32
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 9 : i32
    %1 = func.call @ins_square(%0) : (i32) -> i32
    return %1 : i32
  }
}
