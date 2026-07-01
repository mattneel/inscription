module {
  func.func @classify_byte(%b: i8, %enabled: i1) -> i32 {
    %0 = arith.constant 48 : i8
    %1 = arith.constant 57 : i8
    %2 = arith.cmpi uge, %b, %0 : i8
    %3 = arith.cmpi ule, %b, %1 : i8
    %4 = arith.andi %2, %3 : i1
    %5 = arith.constant 65 : i8
    %6 = arith.constant 70 : i8
    %7 = arith.cmpi uge, %b, %5 : i8
    %8 = arith.cmpi ule, %b, %6 : i8
    %9 = arith.andi %7, %8 : i1
    %10 = arith.ori %4, %9 : i1
    %11 = scf.if %10 -> (i32) {
      %12 = scf.if %enabled -> (i32) {
        %13 = arith.constant 7 : i32
        scf.yield %13 : i32
      } else {
        %14 = arith.constant 1 : i32
        scf.yield %14 : i32
      }
      scf.yield %12 : i32
    } else {
      %15 = arith.constant 1 : i32
      scf.yield %15 : i32
    }
    return %11 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 56 : i8
    %1 = arith.constant true
    %2 = func.call @classify_byte(%0, %1) : (i8, i1) -> i32
    return %2 : i32
  }
}
