module {
  func.func @main() -> i32 {
    %0 = arith.constant 1 : i8
    %1 = arith.constant 0 : i8
    %2 = arith.cmpi eq, %0, %1 : i8
    %3 = scf.if %2 -> (i32) {
      %4 = arith.constant 0 : i32
      scf.yield %4 : i32
    } else {
      %5 = arith.constant 1 : i8
      %6 = arith.cmpi eq, %0, %5 : i8
      %7 = scf.if %6 -> (i32) {
        %8 = arith.constant 42 : i32
        scf.yield %8 : i32
      } else {
        %9 = arith.constant 1 : i32
        scf.yield %9 : i32
      }
      scf.yield %7 : i32
    }
    return %3 : i32
  }
}
