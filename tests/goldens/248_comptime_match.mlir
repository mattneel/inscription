module {
  func.func @classify(%x: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 9 : i32
    %2 = arith.cmpi sge, %x, %0 : i32
    %3 = arith.cmpi sle, %x, %1 : i32
    %4 = arith.andi %2, %3 : i1
    %5 = scf.if %4 -> (i32) {
      %6 = arith.constant 1 : i32
      scf.yield %6 : i32
    } else {
      %7 = arith.constant 10 : i32
      %8 = arith.constant 19 : i32
      %9 = arith.cmpi sge, %x, %7 : i32
      %10 = arith.cmpi sle, %x, %8 : i32
      %11 = arith.andi %9, %10 : i1
      %12 = scf.if %11 -> (i32) {
        %13 = arith.constant 2 : i32
        scf.yield %13 : i32
      } else {
        %14 = arith.constant 3 : i32
        scf.yield %14 : i32
      }
      scf.yield %12 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 2 : i32
    return %0 : i32
  }
}
