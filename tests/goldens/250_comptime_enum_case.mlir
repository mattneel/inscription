module {
  func.func @active_value() -> i8 {
    %0 = arith.constant 1 : i8
    return %0 : i8
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i8
    %1 = arith.extui %0 : i8 to i32
    return %1 : i32
  }
}
