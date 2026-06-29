module {
  func.func @max(%a: i32, %b: i32) -> i32 {
    %0 = arith.cmpi sgt, %a, %b : i32
    %1 = scf.if %0 -> (i32) {
      scf.yield %a : i32
    } else {
      scf.yield %b : i32
    }
    return %1 : i32
  }
}
