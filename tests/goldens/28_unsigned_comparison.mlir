module {
  func.func @unsigned_greater_demo() -> i32 {
    %0 = arith.constant 255 : i8
    %1 = arith.constant 1 : i8
    %2 = arith.cmpi ugt, %0, %1 : i8
    %3 = scf.if %2 -> (i32) {
      %4 = arith.constant 7 : i32
      scf.yield %4 : i32
    } else {
      %5 = arith.constant 1 : i32
      scf.yield %5 : i32
    }
    return %3 : i32
  }

  func.func @main() -> i32 {
    %0 = func.call @unsigned_greater_demo() : () -> i32
    return %0 : i32
  }
}
