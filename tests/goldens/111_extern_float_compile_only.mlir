module {
  func.func private @llvm.sqrt.f64(f64) -> f64

  func.func @compute_root() -> i32 {
    %0 = arith.constant 16.0 : f64
    %1 = func.call @llvm.sqrt.f64(%0) : (f64) -> f64
    %2 = arith.fptosi %1 : f64 to i32
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @compute_root() : () -> i32
    return %0 : i32
  }
}
