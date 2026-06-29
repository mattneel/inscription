module {
  func.func @divide_safely(%x: i32, %divisor: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.cmpi ne, %divisor, %0 : i32
    cf.assert %1, "require failed at line 2"
    %2 = arith.divsi %x, %divisor : i32
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 84 : i32
    %1 = arith.constant 2 : i32
    %2 = func.call @divide_safely(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
