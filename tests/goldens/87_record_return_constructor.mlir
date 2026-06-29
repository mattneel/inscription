module {
  func.func @make_point(%x: i32, %y: i32) -> (i32, i32) {
    return %x, %y : i32, i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 10 : i32
    %1 = arith.constant 20 : i32
    %2:2 = func.call @make_point(%0, %1) : (i32, i32) -> (i32, i32)
    %3 = arith.addi %2#0, %2#1 : i32
    return %3 : i32
  }
}
