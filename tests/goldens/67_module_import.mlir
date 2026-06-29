module {
  func.func @modules__math__add(%a: i32, %b: i32) -> i32 {
    %0 = arith.addi %a, %b : i32
    return %0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 5 : i32
    %1 = arith.constant 6 : i32
    %2 = func.call @modules__math__add(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
