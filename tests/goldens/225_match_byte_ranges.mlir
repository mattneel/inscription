module {
  func.func @classify_byte(%b: i8) -> i32 {
    %0 = arith.constant 48 : i8
    %1 = arith.constant 57 : i8
    %2 = arith.cmpi uge, %b, %0 : i8
    %3 = arith.cmpi ule, %b, %1 : i8
    %4 = arith.andi %2, %3 : i1
    %5 = scf.if %4 -> (i32) {
      %6 = arith.constant 1 : i32
      scf.yield %6 : i32
    } else {
      %7 = arith.constant 65 : i8
      %8 = arith.constant 70 : i8
      %9 = arith.cmpi uge, %b, %7 : i8
      %10 = arith.cmpi ule, %b, %8 : i8
      %11 = arith.andi %9, %10 : i1
      %12 = scf.if %11 -> (i32) {
        %13 = arith.constant 2 : i32
        scf.yield %13 : i32
      } else {
        %14 = arith.constant 97 : i8
        %15 = arith.constant 102 : i8
        %16 = arith.cmpi uge, %b, %14 : i8
        %17 = arith.cmpi ule, %b, %15 : i8
        %18 = arith.andi %16, %17 : i1
        %19 = scf.if %18 -> (i32) {
          %20 = arith.constant 2 : i32
          scf.yield %20 : i32
        } else {
          %21 = arith.constant 0 : i32
          scf.yield %21 : i32
        }
        scf.yield %19 : i32
      }
      scf.yield %12 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 67 : i8
    %1 = func.call @classify_byte(%0) : (i8) -> i32
    return %1 : i32
  }
}
