module {
  func.func @choose_mode(%mode: i8) -> i32 {
    %0 = arith.constant 1 : i8
    %1 = arith.cmpi eq, %mode, %0 : i8
    %2 = scf.if %1 -> (i32) {
      %3 = arith.constant 7 : i32
      scf.yield %3 : i32
    } else {
      %4 = arith.constant 3 : i32
      scf.yield %4 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i8
    %1 = func.call @choose_mode(%0) : (i8) -> i32
    return %1 : i32
  }
}
