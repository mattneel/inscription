module {
  func.func @ins_multiply_weights(%left: f64, %right: f64) -> f64 {
    %0 = arith.mulf %left, %right : f64
    return %0 : f64
  }

  func.func @main() -> i32 {
    %0 = arith.constant 2.0 : f64
    %1 = arith.constant 3.0 : f64
    %2 = func.call @ins_multiply_weights(%0, %1) : (f64, f64) -> f64
    %3 = arith.fptosi %2 : f64 to i32
    return %3 : i32
  }
}
