module {
  func.func @code_for_door(%door_tag: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.cmpi eq, %door_tag, %0 : i32
    %2 = scf.if %1 -> (i32) {
      %3 = arith.constant 1 : i32
      scf.yield %3 : i32
    } else {
      %4 = arith.constant 1 : i32
      %5 = arith.cmpi eq, %door_tag, %4 : i32
      %6 = scf.if %5 -> (i32) {
        %7 = arith.constant 2 : i32
        scf.yield %7 : i32
      } else {
        %8 = arith.constant 9 : i32
        scf.yield %8 : i32
      }
      scf.yield %6 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 1 : i32
    %2 = func.call @code_for_door(%1) : (i32) -> i32
    return %2 : i32
  }
}
