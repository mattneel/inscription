module {
  func.func @guarded_mode(%mode: i8, %enabled: i1) -> i32 {
    %0 = arith.constant 1 : i8
    %1 = arith.cmpi eq, %mode, %0 : i8
    %2 = scf.if %1 -> (i32) {
      %3 = scf.if %enabled -> (i32) {
        %4 = arith.constant 7 : i32
        scf.yield %4 : i32
      } else {
        %5 = arith.constant 1 : i8
        %6 = arith.cmpi eq, %mode, %5 : i8
        %7 = scf.if %6 -> (i32) {
          %8 = arith.constant 3 : i32
          scf.yield %8 : i32
        } else {
          %9 = arith.constant 0 : i32
          scf.yield %9 : i32
        }
        scf.yield %7 : i32
      }
      scf.yield %3 : i32
    } else {
      %10 = arith.constant 1 : i8
      %11 = arith.cmpi eq, %mode, %10 : i8
      %12 = scf.if %11 -> (i32) {
        %13 = arith.constant 3 : i32
        scf.yield %13 : i32
      } else {
        %14 = arith.constant 0 : i32
        scf.yield %14 : i32
      }
      scf.yield %12 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i8
    %1 = arith.constant true
    %2 = func.call @guarded_mode(%0, %1) : (i8, i1) -> i32
    return %2 : i32
  }
}
