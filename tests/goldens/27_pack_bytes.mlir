module {
  func.func @pack(%high: i8, %low: i8) -> i16 {
    %0 = arith.extui %high : i8 to i16
    %1 = arith.constant 8 : i16
    %2 = arith.shli %0, %1 : i16
    %3 = arith.extui %low : i8 to i16
    %4 = arith.ori %2, %3 : i16
    return %4 : i16
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i8
    %1 = arith.constant 2 : i8
    %2 = func.call @pack(%0, %1) : (i8, i8) -> i16
    %3 = arith.extui %2 : i16 to i32
    return %3 : i32
  }
}
