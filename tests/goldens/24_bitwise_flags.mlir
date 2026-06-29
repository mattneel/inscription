module {
  func.func @has_flag(%flags: i32, %mask: i32) -> i1 {
    %0 = arith.andi %flags, %mask : i32
    %1 = arith.constant 0 : i32
    %2 = arith.cmpi ne, %0, %1 : i32
    return %2 : i1
  }

  func.func @main() -> i32 {
    %0 = arith.constant 10 : i32
    %1 = arith.constant 2 : i32
    %2 = func.call @has_flag(%0, %1) : (i32, i32) -> i1
    %3 = scf.if %2 -> (i32) {
      %4 = arith.constant 7 : i32
      scf.yield %4 : i32
    } else {
      %5 = arith.constant 1 : i32
      scf.yield %5 : i32
    }
    return %3 : i32
  }
}
