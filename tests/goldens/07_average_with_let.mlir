module {
  func.func @average(%left: i32, %right: i32) -> i32 {
    %0 = arith.addi %left, %right : i32
    %1 = arith.constant 2 : i32
    %2 = arith.divsi %0, %1 : i32
    return %2 : i32
  }
}
