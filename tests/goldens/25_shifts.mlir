module {
  func.func @shift_demo() -> i32 {
    %0 = arith.constant 1 : i8
    %1 = arith.constant 3 : i8
    %2 = arith.shli %0, %1 : i8
    %3 = arith.extui %2 : i8 to i32
    return %3 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @shift_demo() : () -> i32
    return %0 : i32
  }
}
