module {
  func.func @main() -> i32 {
    %0 = arith.constant 1.0 : f64
    %1 = arith.fptosi %0 : f64 to i32
    return %1 : i32
  }
}
