module {
  func.func private @llvm.ctpop.i32(i32) -> i32

  func.func @ins_popcount(%x: i32) -> i32 {
    %0 = func.call @llvm.ctpop.i32(%x) : (i32) -> i32
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 15 : i32
    %1 = func.call @ins_popcount(%0) : (i32) -> i32
    return %1 : i32
  }
}
