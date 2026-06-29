module {
  func.func @absolute_value(%n: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.cmpi slt, %n, %0 : i32
    %2 = scf.if %1 -> (i32) {
      %3 = arith.subi %0, %n : i32
      scf.yield %3 : i32
    } else {
      scf.yield %n : i32
    }
    return %2 : i32
  }
}
