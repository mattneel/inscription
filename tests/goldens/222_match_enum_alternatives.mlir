module {
  func.func @code_for_mode(%mode: i8) -> i32 {
    %0 = arith.constant 0 : i8
    %1 = arith.cmpi eq, %mode, %0 : i8
    %2 = arith.constant 2 : i8
    %3 = arith.cmpi eq, %mode, %2 : i8
    %4 = arith.ori %1, %3 : i1
    %5 = scf.if %4 -> (i32) {
      %6 = arith.constant 0 : i32
      scf.yield %6 : i32
    } else {
      %7 = arith.constant 7 : i32
      scf.yield %7 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i8
    %1 = func.call @code_for_mode(%0) : (i8) -> i32
    return %1 : i32
  }
}
