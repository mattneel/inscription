module {
  func.func @average(%left: f64, %right: f64) -> f64 {
    %0 = arith.addf %left, %right : f64
    %1 = arith.constant 2.0 : f64
    %2 = arith.divf %0, %1 : f64
    return %2 : f64
  }

  func.func @main() -> i32 {
    %0 = arith.constant 2.0 : f64
    %1 = arith.constant 4.0 : f64
    %2 = func.call @average(%0, %1) : (f64, f64) -> f64
    %3 = arith.fptosi %2 : f64 to i32
    return %3 : i32
  }
}
