module {
  func.func @factorial(%n: i64) -> i64 {
    %0 = arith.constant 1 : i64
    %1 = arith.cmpi sle, %n, %0 : i64
    %2 = scf.if %1 -> (i64) {
      scf.yield %0 : i64
    } else {
      %3 = arith.subi %n, %0 : i64
      %4 = func.call @factorial(%3) : (i64) -> i64
      %5 = arith.muli %n, %4 : i64
      scf.yield %5 : i64
    }
    return %2 : i64
  }
}
