module {
  func.func @bool_code(%flag: i1) -> i32 {
    %0 = arith.constant 7 : i32
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant false
    %1 = func.call @bool_code(%0) : (i1) -> i32
    return %1 : i32
  }
}
