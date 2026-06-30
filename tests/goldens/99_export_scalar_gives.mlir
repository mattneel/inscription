module {
  func.func @ins_add(%left: i32, %right: i32) -> i32 {
    %0 = arith.addi %left, %right : i32
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 40 : i32
    %1 = arith.constant 2 : i32
    %2 = func.call @ins_add(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
