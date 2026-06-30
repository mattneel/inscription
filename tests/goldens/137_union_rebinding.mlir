module {
  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 1 : i32
    %2 = arith.constant 5 : i32
    %3 = arith.cmpi eq, %1, %1 : i32
    %4 = scf.if %3 -> (i32) {
      scf.yield %2 : i32
    } else {
      %5 = arith.constant 0 : i32
      scf.yield %5 : i32
    }
    return %4 : i32
  }
}
