module {
  func.func private @llvm.ctpop.i32(i32) -> i32

  func.func @main() -> i32 {
    %0 = arith.constant 15 : i32
    %1 = func.call @llvm.ctpop.i32(%0) : (i32) -> i32
    return %1 : i32
  }
}
