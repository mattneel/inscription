module {
  func.func @absolute_using_branch(%n: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.cmpi slt, %n, %0 : i32
    %2 = scf.if %1 -> (i32) {
      %3 = arith.constant 0 : i32
      %4 = arith.subi %3, %n : i32
      scf.yield %4 : i32
    } else {
      scf.yield %n : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 7 : i32
    %2 = arith.subi %0, %1 : i32
    %3 = func.call @absolute_using_branch(%2) : (i32) -> i32
    return %3 : i32
  }
}
