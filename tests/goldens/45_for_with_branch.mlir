module {
  func.func @count_odds_below(%n: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1 = arith.constant 0 : index
    %2 = arith.index_cast %n : i32 to index
    %3 = arith.constant 1 : index
    %5 = scf.for %4 = %1 to %2 step %3 iter_args(%count_iter = %0) -> (i32) {
      %6 = arith.index_cast %4 : index to i32
      %7 = arith.constant 2 : i32
      %8 = arith.remsi %6, %7 : i32
      %9 = arith.constant 0 : i32
      %10 = arith.cmpi ne, %8, %9 : i32
      %11 = scf.if %10 -> (i32) {
        %12 = arith.constant 1 : i32
        %13 = arith.addi %count_iter, %12 : i32
        scf.yield %13 : i32
      } else {
        scf.yield %count_iter : i32
      }
      scf.yield %11 : i32
    }
    return %5 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 10 : i32
    %1 = func.call @count_odds_below(%0) : (i32) -> i32
    return %1 : i32
  }
}
