module {
  func.func @make_vec(%x: f64, %y: f64) -> (f64, f64) {
    return %x, %y : f64, f64
  }

  func.func @length_squared(%v_x: f64, %v_y: f64) -> f64 {
    %0 = arith.mulf %v_x, %v_x : f64
    %1 = arith.mulf %v_y, %v_y : f64
    %2 = arith.addf %0, %1 : f64
    return %2 : f64
  }

  func.func @main() -> i32 {
    %0 = arith.constant 3.0 : f64
    %1 = arith.constant 4.0 : f64
    %2:2 = func.call @make_vec(%0, %1) : (f64, f64) -> (f64, f64)
    %3 = func.call @length_squared(%2#0, %2#1) : (f64, f64) -> f64
    %4 = arith.fptosi %3 : f64 to i32
    return %4 : i32
  }
}
