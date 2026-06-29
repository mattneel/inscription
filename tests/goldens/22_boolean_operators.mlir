module {
  func.func @between_one_and_ten(%x: i32) -> i1 {
    %0 = arith.constant 1 : i32
    %1 = arith.cmpi sge, %x, %0 : i32
    %2 = arith.constant 10 : i32
    %3 = arith.cmpi sle, %x, %2 : i32
    %4 = arith.andi %1, %3 : i1
    return %4 : i1
  }

  func.func @outside_one_and_ten(%x: i32) -> i1 {
    %0 = arith.constant 1 : i32
    %1 = arith.cmpi slt, %x, %0 : i32
    %2 = arith.constant 10 : i32
    %3 = arith.cmpi sgt, %x, %2 : i32
    %4 = arith.ori %1, %3 : i1
    return %4 : i1
  }

  func.func @main() -> i32 {
    %0 = arith.constant 7 : i32
    %1 = func.call @between_one_and_ten(%0) : (i32) -> i1
    %2 = func.call @outside_one_and_ten(%0) : (i32) -> i1
    %3 = arith.constant true
    %4 = arith.xori %2, %3 : i1
    %5 = arith.andi %1, %4 : i1
    %6 = scf.if %5 -> (i32) {
      scf.yield %0 : i32
    } else {
      %7 = arith.constant 1 : i32
      scf.yield %7 : i32
    }
    return %6 : i32
  }
}
