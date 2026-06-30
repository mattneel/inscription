module {
  func.func @cast_float_demo() -> i32 {
    %0 = arith.constant 3.9 : f64
    %1 = arith.fptosi %0 : f64 to i32
    return %1 : i32
  }

  func.func @int_to_float_demo() -> i32 {
    %0 = arith.constant 40 : i32
    %1 = arith.sitofp %0 : i32 to f64
    %2 = arith.constant 2 : i32
    %3 = arith.sitofp %2 : i32 to f64
    %4 = arith.addf %1, %3 : f64
    %5 = arith.fptosi %4 : f64 to i32
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @cast_float_demo() : () -> i32
    %1 = func.call @int_to_float_demo() : () -> i32
    %2 = arith.constant 42 : i32
    %3 = arith.subi %1, %2 : i32
    %4 = arith.addi %0, %3 : i32
    return %4 : i32
  }
}
