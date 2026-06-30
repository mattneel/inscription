module {
  func.func @point_for_mode(%mode: i8) -> (i32, i32) {
    %0 = arith.constant 0 : i8
    %1 = arith.cmpi eq, %mode, %0 : i8
    %2:2 = scf.if %1 -> (i32, i32) {
      %3 = arith.constant 0 : i32
      scf.yield %3, %3 : i32, i32
    } else {
      %4 = arith.constant 1 : i8
      %5 = arith.cmpi eq, %mode, %4 : i8
      %6:2 = scf.if %5 -> (i32, i32) {
        %7 = arith.constant 3 : i32
        %8 = arith.constant 4 : i32
        scf.yield %7, %8 : i32, i32
      } else {
        %9 = arith.constant 1 : i32
        scf.yield %9, %9 : i32, i32
      }
      scf.yield %6#0, %6#1 : i32, i32
    }
    return %2#0, %2#1 : i32, i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i8
    %1:2 = func.call @point_for_mode(%0) : (i8) -> (i32, i32)
    %2 = arith.addi %1#0, %1#1 : i32
    return %2 : i32
  }
}
