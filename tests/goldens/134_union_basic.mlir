module {
  func.func @value_or_zero(%maybe_tag: i32, %maybe_some_value: i32) -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.cmpi eq, %maybe_tag, %0 : i32
    %2 = scf.if %1 -> (i32) {
      scf.yield %maybe_some_value : i32
    } else {
      %3 = arith.constant 0 : i32
      %4 = arith.cmpi eq, %maybe_tag, %3 : i32
      %5 = scf.if %4 -> (i32) {
        %6 = arith.constant 0 : i32
        scf.yield %6 : i32
      } else {
        %7 = arith.constant 0 : i32
        scf.yield %7 : i32
      }
      scf.yield %5 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 1 : i32
    %2 = arith.constant 7 : i32
    %3 = func.call @value_or_zero(%1, %2) : (i32, i32) -> i32
    return %3 : i32
  }
}
