module {
  func.func @main() -> i32 {
    %0 = arith.constant 65 : i8
    %1 = arith.extui %0 : i8 to i32
    return %1 : i32
  }
}
