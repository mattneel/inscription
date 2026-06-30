module {
  func.func @make_maybe(%flag: i1) -> (i32, i32) {
    %0:2 = scf.if %flag -> (i32, i32) {
      %1 = arith.constant 0 : i32
      %2 = arith.constant 1 : i32
      %3 = arith.constant 42 : i32
      scf.yield %2, %3 : i32, i32
    } else {
      %4 = arith.constant 0 : i32
      scf.yield %4, %4 : i32, i32
    }
    return %0#0, %0#1 : i32, i32
  }

  func.func @value_or_zero(%maybe_tag: i32, %maybe_some_value: i32) -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.cmpi eq, %maybe_tag, %0 : i32
    %2 = scf.if %1 -> (i32) {
      scf.yield %maybe_some_value : i32
    } else {
      %3 = arith.constant 0 : i32
      scf.yield %3 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant true
    %1:2 = func.call @make_maybe(%0) : (i1) -> (i32, i32)
    %2 = func.call @value_or_zero(%1#0, %1#1) : (i32, i32) -> i32
    return %2 : i32
  }
}
