module {
  func.func @add(%left: i32, %right: i32) -> i32 {
    %0 = arith.addi %left, %right : i32
    return %0 : i32
  }
}
