module {
  func.func @low_byte(%x: i32) -> i8 {
    %0 = arith.trunci %x : i32 to i8
    return %0 : i8
  }

  func.func @main() -> i32 {
    %0 = arith.constant 511 : i32
    %1 = func.call @low_byte(%0) : (i32) -> i8
    %2 = arith.extui %1 : i8 to i32
    return %2 : i32
  }
}
