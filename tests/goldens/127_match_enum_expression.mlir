module {
  func.func @code_for_mode(%mode: i8) -> i32 {
    %0 = arith.constant 0 : i8
    %1 = arith.cmpi eq, %mode, %0 : i8
    %2 = scf.if %1 -> (i32) {
      %3 = arith.constant 0 : i32
      scf.yield %3 : i32
    } else {
      %4 = arith.constant 1 : i8
      %5 = arith.cmpi eq, %mode, %4 : i8
      %6 = scf.if %5 -> (i32) {
        %7 = arith.constant 7 : i32
        scf.yield %7 : i32
      } else {
        %8 = arith.constant 2 : i8
        %9 = arith.cmpi eq, %mode, %8 : i8
        %10 = scf.if %9 -> (i32) {
          %11 = arith.constant 255 : i32
          scf.yield %11 : i32
        } else {
          %12 = arith.constant 1 : i32
          scf.yield %12 : i32
        }
        scf.yield %10 : i32
      }
      scf.yield %6 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i8
    %1 = func.call @code_for_mode(%0) : (i8) -> i32
    return %1 : i32
  }
}
