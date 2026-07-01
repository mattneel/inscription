module {
  func.func @positive_or_zero(%maybe_tag: i32, %maybe_some_value: i32) -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.cmpi eq, %maybe_tag, %0 : i32
    %2 = scf.if %1 -> (i32) {
      %3 = arith.constant 0 : i32
      %4 = arith.cmpi sgt, %maybe_some_value, %3 : i32
      %5 = scf.if %4 -> (i32) {
        scf.yield %maybe_some_value : i32
      } else {
        %6 = arith.constant 1 : i32
        %7 = arith.cmpi eq, %maybe_tag, %6 : i32
        %8 = scf.if %7 -> (i32) {
          %9 = arith.constant 0 : i32
          scf.yield %9 : i32
        } else {
          %10 = arith.constant 0 : i32
          scf.yield %10 : i32
        }
        scf.yield %8 : i32
      }
      scf.yield %5 : i32
    } else {
      %11 = arith.constant 1 : i32
      %12 = arith.cmpi eq, %maybe_tag, %11 : i32
      %13 = scf.if %12 -> (i32) {
        %14 = arith.constant 0 : i32
        scf.yield %14 : i32
      } else {
        %15 = arith.constant 0 : i32
        scf.yield %15 : i32
      }
      scf.yield %13 : i32
    }
    return %2 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 1 : i32
    %2 = arith.constant 7 : i32
    %3 = func.call @positive_or_zero(%1, %2) : (i32, i32) -> i32
    return %3 : i32
  }
}
