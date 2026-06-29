module {
  func.func @clamp(%x: i32, %low: i32, %high: i32) -> i32 {
    %0 = arith.cmpi slt, %x, %low : i32
    %1 = scf.if %0 -> (i32) {
      scf.yield %low : i32
    } else {
      %2 = arith.cmpi sgt, %x, %high : i32
      %3 = scf.if %2 -> (i32) {
        scf.yield %high : i32
      } else {
        scf.yield %x : i32
      }
      scf.yield %3 : i32
    }
    return %1 : i32
  }
}
