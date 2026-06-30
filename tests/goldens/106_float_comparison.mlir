module {
  func.func @choose_by_float(%x: f64) -> i32 {
    %0 = arith.constant 1.5 : f64
    %1 = arith.cmpf ogt, %x, %0 : f64
    %2 = scf.if %1 -> (i32) {
      %3 = arith.constant 7 : i32
      scf.yield %3 : i32
    } else {
      %4 = arith.constant 3 : i32
      scf.yield %4 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 2.0 : f64
    %1 = func.call @choose_by_float(%0) : (f64) -> i32
    return %1 : i32
  }
}
