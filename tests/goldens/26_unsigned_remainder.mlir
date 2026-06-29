module {
  func.func @unsigned_mod_demo(%x: i32) -> i32 {
    %0 = arith.constant 10 : i32
    %1 = arith.remui %x, %0 : i32
    return %1 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 255 : i32
    %1 = func.call @unsigned_mod_demo(%0) : (i32) -> i32
    return %1 : i32
  }
}
