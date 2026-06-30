module {
  func.func @classify_byte(%b: i8) -> i32 {
    %0 = arith.constant 65 : i8
    %1 = arith.cmpi eq, %b, %0 : i8
    %2 = scf.if %1 -> (i32) {
      %3 = arith.constant 1 : i32
      scf.yield %3 : i32
    } else {
      %4 = arith.constant 10 : i8
      %5 = arith.cmpi eq, %b, %4 : i8
      %6 = scf.if %5 -> (i32) {
        %7 = arith.constant 2 : i32
        scf.yield %7 : i32
      } else {
        %8 = arith.constant 3 : i32
        scf.yield %8 : i32
      }
      scf.yield %6 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 65 : i8
    %1 = func.call @classify_byte(%0) : (i8) -> i32
    return %1 : i32
  }
}
