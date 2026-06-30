module {
  func.func @make_device() -> (i8, i8) {
    %0 = arith.constant 1 : i8
    %1 = arith.constant 5 : i8
    return %0, %1 : i8, i8
  }

  func.func @main() -> i32 {
    %0:2 = func.call @make_device() : () -> (i8, i8)
    %1 = arith.constant 1 : i8
    %2 = arith.cmpi eq, %0#0, %1 : i8
    %3 = scf.if %2 -> (i32) {
      %4 = arith.extui %0#1 : i8 to i32
      scf.yield %4 : i32
    } else {
      %5 = arith.constant 0 : i32
      scf.yield %5 : i32
    }
    return %3 : i32
  }
}
