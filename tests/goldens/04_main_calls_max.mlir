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

  func.func @main() -> i32 {
    %0 = arith.constant 7 : i32
    %1 = arith.constant 3 : i32
    %2 = func.call @max(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
