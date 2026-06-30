module {
  func.func @score_maybe(%maybe_tag: i32, %maybe_some_point_x: i32, %maybe_some_point_y: i32) -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.cmpi eq, %maybe_tag, %0 : i32
    %2 = scf.if %1 -> (i32) {
      %3 = arith.addi %maybe_some_point_x, %maybe_some_point_y : i32
      scf.yield %3 : i32
    } else {
      %4 = arith.constant 0 : i32
      scf.yield %4 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 3 : i32
    %1 = arith.constant 4 : i32
    %2 = arith.constant 0 : i32
    %3 = arith.constant 1 : i32
    %4 = func.call @score_maybe(%3, %0, %1) : (i32, i32, i32) -> i32
    return %4 : i32
  }
}
