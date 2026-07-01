module {
  func.func @door_code(%door_tag: i32, %door_locked_code: i8) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.cmpi eq, %door_tag, %0 : i32
    %2 = arith.constant 1 : i32
    %3 = arith.cmpi eq, %door_tag, %2 : i32
    %4 = arith.ori %1, %3 : i1
    %5 = scf.if %4 -> (i32) {
      %6 = arith.constant 1 : i32
      scf.yield %6 : i32
    } else {
      %7 = arith.extui %door_locked_code : i8 to i32
      scf.yield %7 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : i8
    %2 = arith.constant 1 : i32
    %3 = func.call @door_code(%2, %1) : (i32, i8) -> i32
    return %3 : i32
  }
}
