module {
  func.func @ins_make_and_sum(%x: i32, %y: i32) -> i32 {
    %0 = arith.addi %x, %y : i32
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 20 : i32
    %1 = arith.constant 22 : i32
    %2 = func.call @ins_make_and_sum(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
